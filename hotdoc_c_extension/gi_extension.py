# -*- coding: utf-8 -*-
#
# Copyright © 2015,2016 Mathieu Duponchelle <mathieu.duponchelle@opencreed.com>
# Copyright © 2015,2016 Collabora Ltd
#
# This library is free software; you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation; either version 2.1 of the License, or (at your option)
# any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""A gobject-introspection extension for Hotdoc.

This extension is implemented as a just-in-time "scanner".

There is nearly no initial scanning done, as we limit
ourselves to caching all the interesting gir nodes (function
nodes, class nodes etc ..), and creating the class hierarchy
graph.

Instead of creating symbols at setup time, we create them
at symbol resolution time, as the symbol for a given class
will always be located in the same page as its C structure.

For example, given a "TestGreeter" object, the C extension
will create the StructSymbol for TestGreeter, and we
will create the "TestGreeter::TestGreeter" class symbol when
the containing page for TestGreeter will have its symbols
resolved (ie during the initial build of the documentation,
or when the page is stale). All properties, signals and
virtual methods attached to this class are added too.

We will also update all the callables at resolution time,
to add gi-specific attributes to them, which the
GIFormatter will make sense of at format-time.

This approach allows incremental rebuilding to be way faster
than the initial build.
"""

import os
import pathlib

from lxml import etree
from collections import defaultdict

from hotdoc.core.symbols import *
from hotdoc.core.extension import Extension, ExtDependency
from hotdoc.core.formatter import Formatter
from hotdoc.core.links import Link, LinkResolver
from hotdoc.core.tree import Page
from hotdoc.core.comment import Comment
from hotdoc.core.exceptions import BadInclusionException
from hotdoc.utils.loggable import warn, Logger

from .gi_formatter import GIFormatter
from .gi_annotation_parser import GIAnnotationParser
from .fundamentals import PY_FUNDAMENTALS, JS_FUNDAMENTALS


Logger.register_warning_code('missing-gir-include', BadInclusionException,
                             'gi-extension')
Logger.silent = True

class Flag (object):
    def __init__ (self, nick, link):
        self.nick = nick
        self.link = link


class RunLastFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Run Last",
                "https://developer.gnome.org/gobject/unstable/gobject-Signals.html#G-SIGNAL-RUN-LAST:CAPS")


class RunFirstFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Run First",
                "https://developer.gnome.org/gobject/unstable/gobject-Signals.html#G-SIGNAL-RUN-FIRST:CAPS")


class RunCleanupFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Run Cleanup",
                "https://developer.gnome.org/gobject/unstable/gobject-Signals.html#G-SIGNAL-RUN-CLEANUP:CAPS")


class NoHooksFlag (Flag):
    def __init__(self):
        Flag.__init__(self, "No Hooks",
"https://developer.gnome.org/gobject/unstable/gobject-Signals.html#G-SIGNAL-NO-HOOKS:CAPS")


class WritableFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Write", None)


class ReadableFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Read", None)


class ConstructFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Construct", None)


class ConstructOnlyFlag (Flag):
    def __init__(self):
        Flag.__init__ (self, "Construct Only", None)


DESCRIPTION=\
"""
Parse a gir file and add signals, properties, classes
and virtual methods.

Can output documentation for various
languages.

Must be used in combination with the C extension.
"""


def pprint_xml(node):
    print (etree.tostring(node, pretty_print=True).decode())


def core_ns(tag):
    return '{http://www.gtk.org/introspection/core/1.0}%s' % tag


def glib_ns(tag):
    return '{http://www.gtk.org/introspection/glib/1.0}%s' % tag


def c_ns(tag):
    return '{http://www.gtk.org/introspection/c/1.0}%s' % tag


class SymbolTarget:
    def __init__(self, extension):
        self.extension = extension
        self.__smart_key_stack = []
        self.__nsmap = {'core': 'http://www.gtk.org/introspection/core/1.0',
                        'c': 'http://www.gtk.org/introspection/c/1.0',
                        'glib': 'http://www.gtk.org/introspection/glib/1.0'}

    def start (self, tag, attrib):
        tag = tag.split('}')[1]
        try:
            func = getattr(self, 'start_%s' % tag)
        except AttributeError:
            return

        func(attrib)

    def end (self, tag):
        tag = tag.split('}')[1]
        try:
            func = getattr(self, 'end_%s' % tag)
        except AttributeError:
            return

        func()

    def __get_klass_name(self, attrib):
        klass_name = attrib.get('{%s}type' % self.__nsmap['c'])
        if not klass_name:
            klass_name = attrib.get('{%s}type-name' % self.__nsmap['glib'])
        return klass_name

    def start_class(self, attrib):
        name = self.__get_klass_name(attrib)
        unique_name = '%s::%s' % (name, name)
        comment = self.extension.app.database.get_comment(unique_name)
        if comment:
            smart_key = '%s.h' % os.path.splitext(comment.filename)[0]
        else:
            smart_key = unique_name

        self.__smart_key_stack.append(smart_key)

        self.extension.get_or_create_symbol(ClassSymbol,
                                            display_name=name,
                                            unique_name=unique_name,
                                            extra={'gi-smart-key': smart_key})

    def end_class(self):
        self.__smart_key_stack.pop()

    def start_function(self, attrib):
        pass

    def close (self):
        return 0

class GIExtension(Extension):
    extension_name = "gi-extension"
    argument_prefix = "gi"

    __gathered_gtk_doc_links = False
    __gtkdoc_hrefs = {}

    def __init__(self, app, project):
        Extension.__init__(self, app, project)

        self.languages = None
        self.language = 'c'

        self.__nsmap = {'core': 'http://www.gtk.org/introspection/core/1.0',
                      'c': 'http://www.gtk.org/introspection/c/1.0',
                      'glib': 'http://www.gtk.org/introspection/glib/1.0'}

        self.__parsed_girs = set()
        self.__node_cache = {}

        # If generating the index ourselves, we will filter these functions
        # out.
        self.__get_type_functions = set({})
        # We need to collect all class nodes and build the
        # hierarchy beforehand, because git class nodes do not
        # know about their children
        self.__class_nodes = {}

        # Only used to reduce debug verbosity
        self.__dropped_symbols = set({})

        self.__smart_filters = set()

        self.__gir_hierarchies = {}
        self.__gir_children_map = defaultdict(dict)

        self.__c_names = {}
        self.__python_names = {}
        self.__javascript_names = {}

        self.__annotation_parser = GIAnnotationParser()

        self.__translated_names = {}

        self._fundamentals = {}

        self.__gen_index_path = None

        self.c_extension = project.extensions.get('c-extension')

    @staticmethod
    def add_arguments (parser):
        group = parser.add_argument_group('GObject-introspection extension',
                DESCRIPTION)
        GIExtension.add_index_argument(group)
        GIExtension.add_sources_argument(group, allow_filters=False)
        group.add_argument ("--languages", action="store",
                nargs='*',
                help="Languages to translate documentation in (c, python,"
                     "javascript), default is to make all languages")

    def parse_config(self, config):
        super(GIExtension, self).parse_config(config)
        self.languages = [l.lower() for l in config.get(
            'languages', [])]
        # Make sure C always gets formatted first
        if 'c' in self.languages:
            self.languages.remove ('c')
            self.languages.insert (0, 'c')
        if not self.languages:
            self.languages = ['c', 'python', 'javascript']
        if self.sources:
            self.c_extension.scanner.set_extension(self)
        for gir_file in self.sources:
            gir_root = etree.parse(gir_file).getroot()
            self.__cache_nodes(gir_root)
        self.__create_hierarchies()

    @staticmethod
    def get_dependencies ():
        return [ExtDependency('c-extension', is_upstream=True)]

    def _make_formatter(self):
        return GIFormatter(self)

    def _get_smart_index_title(self):
        return 'GObject API Reference'

    def _get_all_sources(self):
        headers = [s for s in self.c_extension.sources if s.endswith('.h')]
        return headers

    def setup (self):
        super(GIExtension, self).setup()

        if not self.__gathered_gtk_doc_links:
            self.__gather_gtk_doc_links()
            self.__gathered_gtk_doc_links = True

        if not self.sources:
            return

        self.info('Gathering legacy gtk-doc links')
        self.__scan_sources()
        #self.project.tree.resolving_symbol_signal.connect (self.__resolving_symbol)
        #self.app.link_resolver.resolving_link_signal.connect(self.__translate_link_ref)

    def format_page(self, page, link_resolver, output):
        link_resolver.get_link_signal.connect(self.search_online_links)
        self.formatter.formatting_symbol_signal.connect(self.__formatting_symbol)
        page.meta['extra']['gi-languages'] = ','.join(self.languages)
        for l in self.languages:
            page.meta['extra']['gi-language'] = l
            self.setup_language (l)
            Extension.format_page (self, page, link_resolver, output)

        self.setup_language(None)

        link_resolver.get_link_signal.disconnect(self.search_online_links)
        self.formatter.formatting_symbol_signal.disconnect(self.__formatting_symbol)

    def __scan_sources(self):
        for gir_file in self.sources:
            root = etree.parse(gir_file).getroot()
            self.__scan_node(root)

    def __core_ns(self, tag):
        return '{%s}%s' % tag, self.__nsmap['core']

    def __scan_node(self, node):
        components = self.__get_gi_name_components(node)
        gi_name = '.'.join(components)

        if node.tag == core_ns('class'):
            self.__create_class_symbol (node, gi_name)
        elif node.tag in (core_ns('function'), core_ns('method')):
            self.__create_function_symbol(node)
            return  # No need to iterate any further
        elif node.tag == core_ns('virtual-method'):
            self.__create_vfunc_symbol(node)
            return  # No need to iterate any further
        elif node.tag == core_ns('property'):
            self.__create_property_symbol(node)
            return  # No need to iterate any further
        elif node.tag == glib_ns('signal'):
            self.__create_signal_symbol(node)
            return  # No need to iterate any further
        elif node.tag == core_ns('alias'):
            self.__create_alias_symbol(node, gi_name)
            return  # No need to iterate any further
        elif node.tag in (core_ns('repository'), core_ns('include'),
                core_ns('package'), core_ns('namespace'), core_ns('doc')):
            pass
        elif node.tag == core_ns('record'):
            self.__create_struct_symbol(node)
        elif True:
            print("%s - %s" % (node.tag, node.text))

        for cnode in node:
            self.__scan_node(cnode)

    def __find_gir_file(self, gir_name):
        for source in self.sources:
            if os.path.basename(source) == gir_name:
                return source

        xdg_dirs = os.getenv('XDG_DATA_DIRS') or ''
        xdg_dirs = [p for p in xdg_dirs.split(':') if p]
        xdg_dirs.append(self.project.datadir)
        for dir_ in xdg_dirs:
            gir_file = os.path.join(dir_, 'gir-1.0', gir_name)
            if os.path.exists(gir_file):
                return gir_file
        return None

    def __generate_smart_filters(self, id_prefixes, sym_prefixes, node):
        sym_prefix = node.attrib['{%s}symbol-prefix' % self.__nsmap['c']]
        self.__smart_filters.add(('%s_IS_%s' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_TYPE_%s' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_%s' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_%s_CLASS' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_IS_%s_CLASS' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_%s_GET_CLASS' % (sym_prefixes, sym_prefix)).upper())
        self.__smart_filters.add(('%s_%s_GET_IFACE' % (sym_prefixes, sym_prefix)).upper())

    def __cache_nodes(self, gir_root):
        ns_node = gir_root.find('./{%s}namespace' % self.__nsmap['core'])
        id_prefixes = ns_node.attrib['{%s}identifier-prefixes' % self.__nsmap['c']]
        sym_prefixes = ns_node.attrib['{%s}symbol-prefixes' % self.__nsmap['c']]

        id_key = '{%s}identifier' % self.__nsmap['c']
        for node in gir_root.xpath(
                './/*[@c:identifier]',
                namespaces=self.__nsmap):
            self.__node_cache[node.attrib[id_key]] = node

        id_type = '{%s}type' % self.__nsmap['c']
        class_tag = '{%s}class' % self.__nsmap['core']
        interface_tag = '{%s}interface' % self.__nsmap['core']
        for node in gir_root.xpath(
                './/*[not(self::core:type) and not (self::core:array)][@c:type]',
                namespaces=self.__nsmap):
            name = node.attrib[id_type]
            self.__node_cache[name] = node
            if node.tag in [class_tag, interface_tag]:
                gi_name = '.'.join(self.__get_gi_name_components(node))
                self.__class_nodes[gi_name] = node
                get_type_function = node.attrib.get('{%s}get-type' %
                    self.__nsmap['glib'])
                self.__get_type_functions.add(get_type_function)
                self.__node_cache['%s::%s' % (name, name)] = node
                self.__generate_smart_filters(id_prefixes, sym_prefixes, node)

        for node in gir_root.xpath(
                './/core:property',
                namespaces=self.__nsmap):
            name = '%s:%s' % (self.__get_klass_name(node.getparent()),
                              node.attrib['name'])
            self.__node_cache[name] = node

        for node in gir_root.xpath(
                './/glib:signal',
                namespaces=self.__nsmap):
            name = '%s::%s' % (self.__get_klass_name(node.getparent()),
                               node.attrib['name'])
            self.__node_cache[name] = node

        for node in gir_root.xpath(
                './/core:virtual-method',
                namespaces=self.__nsmap):
            name = '%s:::%s' % (self.__get_klass_name(node.getparent()),
                                node.attrib['name'])
            self.__node_cache[name] = node

        for inc in gir_root.findall('./core:include',
                namespaces = self.__nsmap):
            inc_name = inc.attrib["name"]
            inc_version = inc.attrib["version"]
            gir_file = self.__find_gir_file('%s-%s.gir' % (inc_name,
                inc_version))
            if not gir_file:
                warn('missing-gir-include', "Couldn't find a gir for %s-%s.gir" %
                        (inc_name, inc_version))
                continue

            if gir_file in self.__parsed_girs:
                continue

            self.__parsed_girs.add(gir_file)
            inc_gir_root = etree.parse(gir_file).getroot()
            self.__cache_nodes(inc_gir_root)

    def __create_hierarchies(self):
        for gi_name, klass in self.__class_nodes.items():
            hierarchy = self.__create_hierarchy (klass)
            self.__gir_hierarchies[gi_name] = hierarchy

    def __get_klass_name(self, klass):
        klass_name = klass.attrib.get('{%s}type' % self.__nsmap['c'])
        if not klass_name:
            klass_name = klass.attrib.get('{%s}type-name' % self.__nsmap['glib'])
        return klass_name

    def __create_hierarchy (self, klass):
        klaass = klass
        hierarchy = []
        while (True):
            parent_name = klass.attrib.get('parent')
            if not parent_name:
                break

            if not '.' in parent_name:
                namespace = klass.getparent().attrib['name']
                parent_name = '%s.%s' % (namespace, parent_name)
            parent_class = self.__class_nodes[parent_name]
            children = self.__gir_children_map[parent_name]
            klass_name = self.__get_klass_name (klass)

            if not klass_name in children:
                link = Link(None, klass_name, klass_name)
                sym = QualifiedSymbol(type_tokens=[link])
                children[klass_name] = sym

            klass_name = self.__get_klass_name(parent_class)
            link = Link(None, klass_name, klass_name)
            sym = QualifiedSymbol(type_tokens=[link])
            hierarchy.append (sym)

            klass = parent_class

        hierarchy.reverse()
        return hierarchy

    def __gather_gtk_doc_links (self):
        gtkdoc_dir = os.path.join(self.project.datadir, "gtk-doc", "html")
        if not os.path.exists(gtkdoc_dir):
            print("no gtk doc to gather links from in %s" % gtkdoc_dir)
            return

        for node in os.listdir(gtkdoc_dir):
            dir_ = os.path.join(gtkdoc_dir, node)
            if os.path.isdir(dir_):
                if not self.__parse_devhelp_index(dir_):
                    try:
                        self.__parse_sgml_index(dir_)
                    except IOError:
                        pass

    def __parse_devhelp_index(self, dir_):
        path = os.path.join(dir_, os.path.basename(dir_) + '.devhelp2')
        if not os.path.exists(path):
            return False

        dh_root = etree.parse(path).getroot()
        online = dh_root.attrib.get('online')
        name = dh_root.attrib.get('name')
        if not online:
            if not name:
                return False
            online = 'https://developer.gnome.org/%s/unstable/' % name

        keywords = dh_root.findall('.//{http://www.devhelp.net/book}keyword')
        for kw in keywords:
            name = kw.attrib["name"]
            type_ = kw.attrib['type']
            link = kw.attrib['link']

            if type_ in ['macro', 'function']:
                name = name.rstrip(u' ()')
            elif type_ in ['struct', 'enum']:
                split = name.split(' ', 1)
                if len(split) == 2:
                    name = split[1]
                else:
                    name = split[0]
            elif type_ in ['signal', 'property']:
                anchor = link.split('#', 1)[1]
                split = anchor.split('-', 1)
                if type_ == 'signal':
                    name = '%s::%s' % (split[0], split[1].lstrip('-'))
                else:
                    name = '%s:%s' % (split[0], split[1].lstrip('-'))

            self.__gtkdoc_hrefs[name] = online + link

        self.debug('Gathered %d links from devhelp index %s' % (len(keywords), path))

        return True

    def __parse_sgml_index(self, dir_):
        remote_prefix = ""
        n_links = 0
        path = os.path.join(dir_, "index.sgml")
        with open(path, 'r') as f:
            for l in f:
                if l.startswith("<ONLINE"):
                    remote_prefix = l.split('"')[1]
                elif not remote_prefix:
                    break
                elif l.startswith("<ANCHOR"):
                    split_line = l.split('"')
                    filename = split_line[3].split('/', 1)[-1]
                    title = split_line[1].replace('-', '_')

                    if title.endswith (":CAPS"):
                        title = title [:-5]
                    if remote_prefix:
                        href = '%s/%s' % (remote_prefix, filename)
                    else:
                        href = filename

                    self.__gtkdoc_hrefs[title] = href
                    n_links += 1

        if n_links > 0:
            self.debug('Gathered %d links from sgml index %s' % (n_links, path))

    def __add_annotations (self, formatter, symbol):
        if self.language == 'c':
            annotations = self.__annotation_parser.make_annotations(symbol)

            # FIXME: OK this is format time but still seems strange
            extra_content = formatter.format_annotations (annotations)
            symbol.extension_contents['Annotations'] = extra_content
        else:
            symbol.extension_contents.pop('Annotations', None)

    def __is_introspectable(self, name):
        if name in self._fundamentals:
            return True

        node = self.__node_cache.get(name)

        if node is None:
            return False

        if not name in self.__c_names:
            self.__add_translations(name, node)

        if node.attrib.get('introspectable') == '0':
            return False
        return True

    def __formatting_symbol(self, formatter, symbol):
        symbol.language = self.language

        if type(symbol) in [ReturnItemSymbol, ParameterSymbol]:
            self.__add_annotations (formatter, symbol)

        if isinstance (symbol, QualifiedSymbol):
            return True

        # We discard symbols at formatting time because they might be exposed
        # in other languages
        if self.language != 'c':
            return self.__is_introspectable(symbol.unique_name)

        return True

    def insert_language(self, ref, language):
        p = pathlib.Path(ref)
        return str(pathlib.Path(p.parts[0], language, *p.parts[1:]))

    def __translate_link_ref(self, link):
        page = self.project.tree.get_page_for_symbol(link.id_)

        if self.language is None:
            if page and page.extension_name == 'gi-extension':
                return self.insert_language(link.ref, self.languages[0])
            return None

        fund = self._fundamentals.get(link.id_)
        if fund:
            return fund.ref

        if page and page.extension_name == 'gi-extension':
            if link.ref and self.language != 'c' and not self.__is_introspectable(link.id_):
                return self.insert_language(link.ref, 'c')
            return self.insert_language(link.ref, self.language)

        if link.ref == None:
            return self.__gtkdoc_hrefs.get(link.id_)

        return None

    @classmethod
    def search_online_links(cls, resolver, name):
        href = cls.__gtkdoc_hrefs.get(name)
        if href:
            return Link(href, name, name)
        return None

    def __translate_link_title(self, link):
        fund = self._fundamentals.get(link.id_)
        if fund:
            return fund._title

        if self.language != 'c' and not self.__is_introspectable(link.id_):
            return link._title + ' (not introspectable)'

        translated = self.__translated_names.get(link.id_)
        if translated:
            return translated

        if self.language == 'c' and link.id_ in self.__gtkdoc_hrefs:
            return link.id_

        return None

    def setup_language (self, language):
        self.language = language

        try:
            Link.resolving_title_signal.disconnect(self.__translate_link_title)
        except KeyError:
            pass

        """
        try:
            self.project.tree.page_parser.renaming_page_link_signal.disconnect(
                    self.__rename_page_link)
        except KeyError:
            pass
        """

        if language is not None:
            Link.resolving_title_signal.connect(self.__translate_link_title)
            """
            self.project.tree.page_parser.renaming_page_link_signal.connect(
                    self.__rename_page_link)
            """

        if language == 'c':
            self._fundamentals = {}
            self.__translated_names = self.__c_names
        elif language == 'python':
            self._fundamentals = PY_FUNDAMENTALS
            self.__translated_names = self.__python_names
        elif language == 'javascript':
            self._fundamentals = JS_FUNDAMENTALS
            self.__translated_names = self.__javascript_names
        else:
            self._fundamentals = {}
            self.__translated_names = {}

    def __smart_filter(self, *args, **kwargs):
        name = kwargs['display_name']

        # Simply reducing debug verbosity
        if name in self.__dropped_symbols:
            return None

        type_ = args[0]

        if name in self.__smart_filters:
            self.debug('Dropping %s' % name)
            self.__dropped_symbols.add(name)
            return None

        # Drop get_type functions
        if name in self.__get_type_functions:
            self.debug('Dropping get_type function %s' % name)
            self.__dropped_symbols.add(name)
            return None

        # Drop class structures if not documented as well
        if type_ == StructSymbol:
            node = self.__node_cache.get(name)
            if node is not None:
                disguised = node.attrib.get('disguised')
                if disguised == '1':
                    self.debug("Dropping private structure %s" % name)
                    self.__dropped_symbols.add(name)
                    return None

        if type_ == ExportedVariableSymbol:
            if name in ('__inst', '__t', '__r'):
                return None

        return super(GIExtension, self).get_or_create_symbol(*args, **kwargs)

    # We implement filtering of some symbols
    def get_or_create_symbol(self, *args, **kwargs):
        if self.smart_index:
            res = self.__smart_filter(*args, **kwargs)
            return res
        return super(GIExtension, self).get_or_create_symbol(*args, **kwargs)

    def __unnest_type (self, parameter):
        array_nesting = 0
        array = parameter.find('{http://www.gtk.org/introspection/core/1.0}array')
        while array is not None:
            array_nesting += 1
            parameter = array
            array = parameter.find('{http://www.gtk.org/introspection/core/1.0}array')

        return parameter, array_nesting

    def __type_tokens_from_cdecl (self, cdecl):
        indirection = cdecl.count ('*')
        qualified_type = cdecl.strip ('*')
        tokens = []
        for token in qualified_type.split ():
            if token in ["const", "restrict", "volatile"]:
                tokens.append(token + ' ')
            else:
                link = Link(None, token, token)
                tokens.append (link)

        for i in range(indirection):
            tokens.append ('*')

        return tokens

    def __get_gir_type (self, cur_ns, name):
        namespaced = '%s.%s' % (cur_ns, name)
        klass = self.__class_nodes.get (namespaced)
        if klass is not None:
            return klass
        return self.__class_nodes.get (name)

    def __get_namespace(self, node):
        parent = node.getparent()
        nstag = '{%s}namespace' % self.__nsmap['core']
        while parent is not None and parent.tag != nstag:
            parent = parent.getparent()

        return parent.attrib['name']

    def __type_tokens_from_gitype (self, cur_ns, ptype_name):
        qs = None

        if ptype_name == 'none':
            return None

        gitype = self.__get_gir_type (cur_ns, ptype_name)
        if gitype is not None:
            c_type = gitype.attrib['{http://www.gtk.org/introspection/c/1.0}type']
            ptype_name = c_type

        type_link = Link (None, ptype_name, ptype_name)

        tokens = [type_link]
        tokens += '*'

        return tokens

    def __type_tokens_and_gi_name_from_gi_node (self, gi_node):
        type_, array_nesting = self.__unnest_type (gi_node)

        varargs = type_.find('{http://www.gtk.org/introspection/core/1.0}varargs')
        if varargs is not None:
            ctype_name = '...'
            ptype_name = 'valist'
        else:
            ptype_ = type_.find('{http://www.gtk.org/introspection/core/1.0}type')
            ctype_name = ptype_.attrib.get('{http://www.gtk.org/introspection/c/1.0}type')
            ptype_name = ptype_.attrib.get('name')

        cur_ns = self.__get_namespace(gi_node)

        if ctype_name is not None:
            type_tokens = self.__type_tokens_from_cdecl (ctype_name)
        elif ptype_name is not None:
            type_tokens = self.__type_tokens_from_gitype (cur_ns, ptype_name)
        else:
            type_tokens = []

        namespaced = '%s.%s' % (cur_ns, ptype_name)
        if namespaced in self.__class_nodes:
            ptype_name = namespaced
        return type_tokens, ptype_name

    def __create_parameter_symbol (self, gi_parameter):
        param_name = gi_parameter.attrib['name']

        type_tokens, gi_name = self.__type_tokens_and_gi_name_from_gi_node (gi_parameter)

        res = ParameterSymbol (argname=param_name, type_tokens=type_tokens)
        res.add_extension_attribute ('gi-extension', 'gi_name', gi_name)

        direction = gi_parameter.attrib.get('direction')
        if direction is None:
            direction = 'in'
        res.add_extension_attribute ('gi-extension', 'direction', direction)

        return res, direction

    def __create_return_value_symbol (self, gi_retval, out_parameters):
        type_tokens, gi_name = self.__type_tokens_and_gi_name_from_gi_node(gi_retval)

        if gi_name == 'none':
            ret_item = None
        else:
            ret_item = ReturnItemSymbol (type_tokens=type_tokens)
            ret_item.add_extension_attribute('gi-extension', 'gi_name', gi_name)

        res = [ret_item]

        for out_param in out_parameters:
            ret_item = ReturnItemSymbol (type_tokens=out_param.input_tokens,
                    name=out_param.argname)
            res.append(ret_item)

        return res

    def __create_parameters_and_retval (self, node):
        gi_parameters = node.find('{http://www.gtk.org/introspection/core/1.0}parameters')

        if gi_parameters is None:
            instance_param = None
            gi_parameters = []
        else:
            instance_param = \
            gi_parameters.find('{http://www.gtk.org/introspection/core/1.0}instance-parameter')
            gi_parameters = gi_parameters.findall('{http://www.gtk.org/introspection/core/1.0}parameter')

        parameters = []

        if instance_param is not None:
            param, direction = self.__create_parameter_symbol (instance_param)
            parameters.append (param)

        out_parameters = []
        for gi_parameter in gi_parameters:
            param, direction = self.__create_parameter_symbol (gi_parameter)
            parameters.append (param)
            if direction != 'in':
                out_parameters.append (param)

        retval = node.find('{http://www.gtk.org/introspection/core/1.0}return-value')
        retval = self.__create_return_value_symbol (retval, out_parameters)

        return (parameters, retval)

    def __sort_parameters (self, symbol, retval, parameters):
        in_parameters = []
        out_parameters = []

        for i, param in enumerate (parameters):
            if symbol.is_method and i == 0:
                continue

            direction = param.get_extension_attribute ('gi-extension', 'direction')

            if direction == 'in' or direction == 'inout':
                in_parameters.append (param)
            if direction == 'out' or direction == 'inout':
                out_parameters.append (param)

        symbol.add_extension_attribute ('gi-extension',
                'parameters', in_parameters)

    def __create_signal_symbol (self, node):
        parent_name = self.__get_klass_name(node.getparent())
        klass_name = '%s::%s' % (parent_name, parent_name)
        name = node.attrib['name']
        unique_name = '%s::%s' % (parent_name, name)

        parameters, retval = self.__create_parameters_and_retval (node)
        res = self.get_or_create_symbol(SignalSymbol,
                parameters=parameters, return_value=retval,
                display_name=name, unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name))

        flags = []

        when = node.attrib.get('when')
        if when == "first":
            flags.append (RunFirstFlag())
        elif when == "last":
            flags.append (RunLastFlag())
        elif when == "cleanup":
            flags.append (RunCleanupFlag())

        no_hooks = node.attrib.get('no-hooks')
        if no_hooks == '1':
            flags.append (NoHooksFlag())

        # This is incorrect, it's not yet format time
        extra_content = self.formatter._format_flags (flags)
        res.extension_contents['Flags'] = extra_content

        self.__sort_parameters (res, retval, parameters)

        return res

    def __create_property_symbol (self, node):
        parent_name = self.__get_klass_name(node.getparent())
        klass_name = '%s::%s' % (parent_name, parent_name)
        name = node.attrib['name']
        unique_name = '%s:%s' % (parent_name, name)

        type_tokens, gi_name = self.__type_tokens_and_gi_name_from_gi_node(node)
        type_ = QualifiedSymbol (type_tokens=type_tokens)
        type_.add_extension_attribute('gi-extension', 'gi_name', gi_name)

        flags = []
        writable = node.attrib.get('writable')
        construct = node.attrib.get('construct')
        construct_only = node.attrib.get('construct-only')

        flags.append (ReadableFlag())
        if writable == '1':
            flags.append (WritableFlag())
        if construct_only == '1':
            flags.append (ConstructOnlyFlag())
        elif construct == '1':
            flags.append (ConstructFlag())

        res = self.get_or_create_symbol(PropertySymbol,
                prop_type=type_,
                display_name=name,
                unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name))

        extra_content = self.formatter._format_flags (flags)
        res.extension_contents['Flags'] = extra_content

        return res

    def __create_vfunc_symbol (self, node):
        parent_name = self.__get_klass_name(node.getparent())
        klass_name = '%s::%s' % (parent_name, parent_name)
        name = node.attrib['name']
        unique_name = '%s:::%s' % (parent_name, name)

        parameters, retval = self.__create_parameters_and_retval (node)
        symbol = self.get_or_create_symbol(VFunctionSymbol,
                parameters=parameters,
                return_value=retval, display_name=name,
                unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name))

        self.__sort_parameters (symbol, retval, parameters)

        return symbol

    def __get_symbol_filename(self, unique_name):
        comment = self.app.database.get_comment(unique_name)
        if comment:
            return '%s.h' % os.path.splitext(comment.filename)[0]
        return 'Miscellaneous'

    def __create_alias_symbol (self, node, gi_name):
        name = node.attrib.get(c_ns('type'))
        type_tokens, gi_name = self.__type_tokens_and_gi_name_from_gi_node(node)
        aliased_type = QualifiedSymbol(type_tokens=type_tokens)
        filename = self.__get_symbol_filename(name)
        self.get_or_create_symbol(AliasSymbol, aliased_type=aliased_type,
                display_name=name, filename=filename)

    def __create_class_symbol (self, node, gi_name):
        klass_name = self.__get_klass_name (node)
        unique_name = '%s::%s' % (klass_name, klass_name)
        hierarchy = self.__gir_hierarchies[gi_name]
        children = self.__gir_children_map[gi_name]

        self.get_or_create_symbol(ClassSymbol,
                hierarchy=hierarchy, children=children,
                display_name=klass_name,
                unique_name=unique_name,
                filename=self.__get_symbol_filename(unique_name))

    def __get_return_type_from_callback(self, node):
        return_node = node.find(core_ns('callback')).find(
            core_ns('return-value'))

        return return_node.find(core_ns('type')).attrib[c_ns('type')]

    def __create_struct_symbol(self, node):
        struct_name = node.attrib["{%s}%s" % (
            self.__nsmap['c'], 'type')]
        members = []
        filename = self.__get_symbol_filename(struct_name)
        for field in node.findall(core_ns('field')):
            is_function_pointer = False
            if len(field) and field[0].tag == core_ns('callback'):
                is_function_pointer = True
                type_ = self.__get_return_type_from_callback(field)
                tokens = self.__type_tokens_from_cdecl (type_)
            elif len(field) and field[0].tag == core_ns('array'):
                name = field.attrib['name']
                type_ = field.find(core_ns('array')).attrib[c_ns('type')]
                tokens = self.__type_tokens_from_cdecl (type_)
            else:
                name = field.attrib['name']
                type_ = field.find(core_ns('type')).attrib[c_ns('type')]
                tokens = self.__type_tokens_from_cdecl (type_)

            name = "%s" % (name)
            print("NAme %s -- type: %s -> %s" % (name, type_, tokens))
            qtype = QualifiedSymbol(type_tokens=tokens)
            member = self.get_or_create_symbol(
                FieldSymbol, is_function_pointer=is_function_pointer,
                member_name=name, qtype=qtype,
                filename=filename, display_name=name,
                unique_name=name)
            members.append(member)

        print("Creating %s" % struct_name)
        self.get_or_create_symbol(StructSymbol,
                display_name=struct_name,
                unique_name=struct_name,
                filename=filename, members=members)
        print("Done!")

    def __create_interface_symbol (self, node, symbol, gi_name):
        iface_name = '%s::%s' % (symbol.unique_name, symbol.unique_name)

        return self.get_or_create_symbol(InterfaceSymbol,
                display_name=symbol.display_name,
                unique_name=iface_name)

    def __get_gi_name_components(self, node):
        parent = node.getparent()
        components = [node.attrib.get('name', '')]
        while parent is not None:
            try:
                components.insert(0, parent.attrib['name'])
            except KeyError:
                break
            parent = parent.getparent()
        return components

    def __add_translations(self, unique_name, node):
        id_key = '{%s}identifier' % self.__nsmap['c']
        id_type = '{%s}type' % self.__nsmap['c']

        components = self.__get_gi_name_components(node)
        gi_name = '.'.join(components)

        if id_key in node.attrib:
            self.__python_names[unique_name] = gi_name
            components[-1] = 'prototype.%s' % components[-1]
            self.__javascript_names[unique_name] = '.'.join(components)
            self.__c_names[unique_name] = unique_name
        elif id_type in node.attrib:
            self.__python_names[unique_name] = gi_name
            self.__javascript_names[unique_name] = gi_name
            self.__c_names[unique_name] = unique_name

        return components, gi_name

    def __get_function_name(self, func):
        return func.attrib.get('{%s}identifier' % self.__nsmap['c'])

    def __create_function_symbol (self, node):
        name = self.__get_function_name(node)

        self.__add_translations(name, node)

        gi_params, retval = self.__create_parameters_and_retval (node)

        func = self.get_or_create_symbol(FunctionSymbol,
                                         parameters=gi_params,
                                         return_value=retval,
                                         display_name=name,
                                         unique_name=name,
                                         throws='throws' in node.attrib,
                                         is_method=node.tag.endswith ('method'),
                                         filename=self.__get_symbol_filename(name))

        self.__sort_parameters (func, func.return_value, func.parameters)

    def __update_struct (self, symbol, node):
        self.debug('Updating record %s' % symbol.display_name)
        symbols = []

        components, gi_name = self.__add_translations(symbol.unique_name, node)
        gi_name = '.'.join(components)

        if node.tag == '{%s}class' % self.__nsmap['core']:
            symbols.append(self.__create_class_symbol (symbol, gi_name))
        elif node.tag == '{%s}interface' % self.__nsmap['core']:
            symbols.append(self.__create_interface_symbol (node, symbol, gi_name))

        klass_name = node.attrib.get('{%s}type-name' %
                'http://www.gtk.org/introspection/glib/1.0')

        for sig_node in node.findall('./glib:signal',
                                     namespaces = self.__nsmap):
            symbols.append(self.__create_signal_symbol(
                sig_node, klass_name))
            self.debug("Added signal symbol %s" % sig_node.attrib['name'])

        for prop_node in node.findall('./core:property',
                                     namespaces = self.__nsmap):
            symbols.append(self.__create_property_symbol(
                prop_node, klass_name))
            self.debug("Added property symbol %s" % prop_node.attrib['name'])

        class_struct_name = node.attrib.get('{%s}type-struct' %
                self.__nsmap['glib'])

        parent_comment = None
        if class_struct_name:
            class_struct_name = '%s%s' % (components[0], class_struct_name)
            parent_comment = self.app.database.get_comment(class_struct_name)

        vmethods = node.findall('./core:virtual-method',
                                namespaces = self.__nsmap)

        for vfunc_node in vmethods:
            sym = self.__create_vfunc_symbol (vfunc_node, klass_name)
            symbols.append(sym)

            self.debug("Added vmethod symbol %s" % vfunc_node.attrib['name'])

            if parent_comment:
                comment = parent_comment.params.get (vfunc_node.attrib['name'])
                if comment:
                    block = Comment (name=sym.unique_name,
                                     description=comment.description,
                                     filename=parent_comment.filename)
                    self.app.database.add_comment(block)

        return symbols

    def __update_symbol(self, symbol):
        node = self.__node_cache.get(symbol.unique_name)
        res = []

        if node is None:
            return res

        if type(symbol) in (FunctionSymbol, CallbackSymbol):
            self.__update_function(symbol, node)

        elif type (symbol) in (StructSymbol, AliasSymbol):
            res = self.__update_struct (symbol, node)

        return res

    def __resolving_symbol (self, page, symbol):
        if page.extension_name != self.extension_name:
            return []

        return self.__update_symbol(symbol)

    def __rename_page_link (self, page_parser, original_name):
        return self.__translated_names.get(original_name)

    def _get_smart_key(self, symbol):
        return symbol.extra.get('implementation_filename',
                                super()._get_smart_key(symbol))
