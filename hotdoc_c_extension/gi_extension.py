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

This extension parses a .gir file and extract comments from specified
source files. Parsing the comments ourself allows us to smartly build
the index based on the comments location.
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
from hotdoc.core.exceptions import BadInclusionException, InvalidOutputException
from hotdoc.utils.loggable import warn, Logger
from hotdoc.utils.utils import OrderedSet

from .gi_formatter import GIFormatter
from .gi_annotation_parser import GIAnnotationParser
from .fundamentals import FUNDAMENTALS

from hotdoc.parsers.gtk_doc import GtkDocParser
from .utils.utils import CCommentExtractor


Logger.register_warning_code('missing-gir-include', BadInclusionException,
                             'gi-extension')
Logger.register_warning_code('no-location-indication', InvalidOutputException,
                             'gi-extension')

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


DEFAULT_PAGE = "Miscellaneous.default_page"
DEFAULT_PAGE_COMMENT = """/**
* Miscellaneous.default_page:
* @title: Miscellaneous
* @short-description: Miscellaneous unordered symbols
*
* Unordered miscellaneous symbols that were not properly documented
*/
"""


OUTPUT_LANGUAGES = ['c', 'python', 'javascript']


class GIExtension(Extension):
    extension_name = "gi-extension"
    argument_prefix = "gi"

    __gathered_gtk_doc_links = False
    __gtkdoc_hrefs = {}

    # Caches are shared between all instances
    __node_cache = {}
    __parsed_girs = set()
    __translated_names = {l: {} for l in OUTPUT_LANGUAGES}
    __aliased_links = {l: {} for l in OUTPUT_LANGUAGES}
    # We need to collect all class nodes and build the
    # hierarchy beforehand, because git class nodes do not
    # know about their children
    __class_nodes = {}

    def __init__(self, app, project):
        Extension.__init__(self, app, project)

        self.languages = None

        self.__nsmap = {'core': 'http://www.gtk.org/introspection/core/1.0',
                      'c': 'http://www.gtk.org/introspection/c/1.0',
                      'glib': 'http://www.gtk.org/introspection/glib/1.0'}

        self.__smart_filters = set()

        self.__gir_hierarchies = {}
        self.__gir_children_map = defaultdict(dict)

        self.__annotation_parser = GIAnnotationParser()

        self.__current_output_filename = None
        self.__class_gtype_structs = {}
        self.__default_page = DEFAULT_PAGE

    @staticmethod
    def add_arguments (parser):
        group = parser.add_argument_group('GObject-introspection extension',
                DESCRIPTION)
        GIExtension.add_index_argument(group)
        GIExtension.add_sources_argument(group, allow_filters=False)
        GIExtension.add_sources_argument(group, prefix='gi-c')
        group.add_argument ("--languages", action="store",
                nargs='*',
                help="Languages to translate documentation in %s"
                     ", default is to make all languages" % str (OUTPUT_LANGUAGES))

    def parse_config(self, config):
        super(GIExtension, self).parse_config(config)
        self.c_sources = config.get_sources('gi-c')
        self.languages = [l.lower() for l in config.get(
            'languages', [])]
        # Make sure C always gets formatted first
        if 'c' in self.languages:
            self.languages.remove ('c')
            self.languages.insert (0, 'c')
        if not self.languages:
            self.languages = OUTPUT_LANGUAGES
        for gir_file in self.sources:
            gir_root = etree.parse(gir_file).getroot()
            self.__cache_nodes(gir_root)
        self.__create_hierarchies()

    def _make_formatter(self):
        return GIFormatter(self)

    def _get_smart_index_title(self):
        return 'GObject API Reference'

    def _get_all_sources(self):
        return [s for s in self.c_sources if s.endswith('.h')]

    def setup (self):
        commonprefix = os.path.commonprefix(list(self._get_all_sources()))
        self.__default_page = os.path.join(os.path.dirname(commonprefix),
            DEFAULT_PAGE)

        super(GIExtension, self).setup()

        if not GIExtension.__gathered_gtk_doc_links:
            self.__gather_gtk_doc_links()
            GIExtension.__gathered_gtk_doc_links = True

        if not self.sources:
            return

        self.__scan_comments()
        self.__scan_sources()
        self.app.link_resolver.resolving_link_signal.connect_after(self.__translate_link_ref, self.languages[0])

    def __scan_comments(self):
        comment_parser = GtkDocParser(self.project)
        block = comment_parser.parse_comment(DEFAULT_PAGE_COMMENT,
                                             DEFAULT_PAGE, 0, 0)
        self.app.database.add_comment(block)

        stale_c, unlisted = self.get_stale_files(self.c_sources)
        CCommentExtractor(self, comment_parser).parse_comments(stale_c, self.__smart_filters)

    def format_page(self, page, link_resolver, output):
        link_resolver.get_link_signal.connect(self.search_online_links)

        prev_l = None
        page.meta['extra']['gi-languages'] = ','.join(self.languages)
        for l in self.languages:
            self.formatter.formatting_symbol_signal.connect(self.__formatting_symbol, l)
            page.meta['extra']['gi-language'] = l
            self.setup_language (l, prev_l)
            Extension.format_page (self, page, link_resolver, output)
            prev_l = l
            self.formatter.formatting_symbol_signal.disconnect(self.__formatting_symbol, l)

        self.setup_language(None, l)
        page.meta['extra']['gi-language'] = self.languages[0]

        link_resolver.get_link_signal.disconnect(self.search_online_links)

    def write_out_page(self, output, page):
        prev_l = None
        for l in self.languages:
            page.meta['extra']['gi-language'] = l
            self.setup_language (l, prev_l)
            Extension.write_out_page (self, output, page)
            prev_l = l
        self.setup_language(None, l)

    def write_out_sitemap(self, opath):
        for l in self.languages:
            GIFormatter.sitemap_language = l
            lopath = os.path.join(os.path.dirname(opath), '%s-%s' % (l, os.path.basename(opath)))
            Extension.write_out_sitemap (self, lopath)
        GIFormatter.sitemap_language = None

    @staticmethod
    def get_dependencies ():
        return [ExtDependency('c-extension', is_upstream=True, optional=True)]

    def __scan_sources(self):
        for gir_file in self.sources:
            root = etree.parse(gir_file).getroot()
            self.__scan_node(root)

    def __core_ns(self, tag):
        return '{%s}%s' % tag, self.__nsmap['core']

    def __get_structure_name(self, node):
        return node.attrib[c_ns('type')]

    def __get_symbol_names(self, node):
        if node.tag in (core_ns('class')):
            _ = self.__get_klass_name (node)
            return _, _, _
        elif node.tag in (core_ns('interface')):
            _ = self.__get_klass_name (node)
            return _, _, _
        elif node.tag in (core_ns('function'), core_ns('method'), core_ns('constructor')):
            _ = self.__get_function_name(node)
            return _, _, _
        elif node.tag == core_ns('virtual-method'):
            klass_node = node.getparent()
            ns = klass_node.getparent()
            klass_structure_node = ns.xpath(
                './*[@glib:is-gtype-struct-for="%s"]' % klass_node.attrib['name'],
                namespaces=self._GIExtension__nsmap)[0]
            parent_name = self.__get_structure_name(klass_structure_node)
            name = node.attrib['name']
            unique_name = '%s::%s' % (parent_name, name)
            return unique_name, name, unique_name
        elif node.tag == core_ns('field'):
            structure_node = node.getparent()
            parent_name = self.__get_structure_name(structure_node)
            name = node.attrib['name']
            unique_name = '%s::%s' % (parent_name, name)
            return unique_name, name, unique_name
        elif node.tag == core_ns('property'):
            parent_name = self.__get_klass_name(node.getparent())
            klass_name = '%s::%s' % (parent_name, parent_name)
            name = node.attrib['name']
            unique_name = '%s:%s' % (parent_name, name)
            return unique_name, name, klass_name
        elif node.tag == glib_ns('signal'):
            parent_name = self.__get_klass_name(node.getparent())
            klass_name = '%s::%s' % (parent_name, parent_name)
            name = node.attrib['name']
            unique_name = '%s::%s' % (parent_name, name)
            return unique_name, name, klass_name
        elif node.tag == core_ns('alias'):
            _ = node.attrib.get(c_ns('type'))
            return _, _, _
        elif node.tag == core_ns('record'):
            _ = self.__get_structure_name(node)
            return _, _, _
        elif node.tag in (core_ns('enumeration'), core_ns('bitfield')):
            _ = node.attrib[c_ns('type')]
            return _, _, _

        return None, None, None

    def __scan_node(self, node, parent_name=None):
        gi_name = self.__get_gi_name (node)

        if 'moved-to' in node.attrib:
            return False
        if node.tag == core_ns('class'):
            self.__create_structure(ClassSymbol, node, gi_name)
        elif node.tag in (core_ns('function'), core_ns('method'), core_ns('constructor')):
            self.__create_function_symbol(node, parent_name)
        elif node.tag == core_ns('virtual-method'):
            self.__create_vfunc_symbol(node, parent_name)
        elif node.tag == core_ns('property'):
            self.__create_property_symbol(node, parent_name)
        elif node.tag == glib_ns('signal'):
            self.__create_signal_symbol(node, parent_name)
        elif node.tag == core_ns('alias'):
            self.__create_alias_symbol(node, gi_name, parent_name)
        elif node.tag == core_ns('record'):
            self.__create_structure(StructSymbol, node, gi_name)
        elif node.tag == core_ns('interface'):
            self.__create_structure(InterfaceSymbol, node, gi_name)
        elif node.tag == core_ns('enumeration'):
            self.__create_enum_symbol(node)
        elif node.tag == core_ns('bitfield'):
            self.__create_enum_symbol(node)
        elif node.tag == core_ns('callback'):
            self.__create_callback_symbol(node, parent_name)
        elif node.tag == core_ns('field'):
            pass
        else:
            for cnode in node:
                self.__scan_node(cnode)

    def __create_callback_symbol (self, node, parent_name):
        parameters = []
        parameters_nodes = node.find(core_ns('parameters'))
        name = node.attrib[c_ns('type')]
        if parameters_nodes is None:
            parameters_nodes = []
        for child in parameters_nodes:
            parameter = self.__create_parameter_symbol (child,
                                                        name)
            parameters.append (parameter[0])

        return_type = self.__get_return_type_from_callback(node)
        if return_type:
            tokens = self.__type_tokens_from_cdecl (return_type)
            return_value = [ReturnItemSymbol(type_tokens=tokens)]
        else:
            return_value = [ReturnItemSymbol(type_tokens=[])]
        self.__add_symbol_attrs(return_value[0], owner_name=name)

        filename = self.__get_symbol_filename(name)
        sym = self.get_or_create_symbol(
            CallbackSymbol, node, parameters=parameters,
            return_value=return_value, display_name=name,
            filename=filename, parent_name=parent_name)

        return sym

    def __create_enum_symbol (self, node, spelling=None):
        name = node.attrib[c_ns('type')]

        filename = self.__get_symbol_filename(name)
        members = []
        for field in node.findall(core_ns('member')):
            member = self.get_or_create_symbol(
                Symbol, node, display_name=field.attrib[c_ns('identifier')],
                filename=filename)
            member.enum_value = field.attrib['value']
            members.append(member)

        return self.get_or_create_symbol(
            EnumSymbol, node, members=members,
            anonymous=False, display_name=name,
            filename=filename, raw_text=None)

    def __find_structure_pagename(self, node, unique_name, is_class):
        filename = self.__get_symbol_filename(unique_name)
        if filename != self.__default_page:
            return filename

        if not is_class:
            sym = self.__class_gtype_structs.get(node.attrib['name'])
            if sym and sym.filename:
                return sym.filename

        filenames = []
        for cnode in node:
            cunique_name = self.__get_symbol_names(cnode)[0]
            if not cunique_name:
                continue
            fname = self.__get_symbol_filename(cunique_name)
            if fname != self.__default_page:
                if cnode.tag == core_ns('constructor'):
                    filenames.insert(0, fname)
                else:
                    filenames.append(fname)

        unique_filenames = list(OrderedSet(filenames))
        if not filenames:
            # Did not find any symbols, trying to can get information
            # about the class structure linked to that object class.
            nextnode = node.getnext()
            name = node.attrib['name']
            if nextnode is not None and nextnode.tag == core_ns('record'):
                nextnode_classfor = nextnode.attrib.get(glib_ns(
                    'is-gtype-struct-for'))
                if nextnode_classfor == name:
                    nunique_name = self.__get_symbol_names(nextnode)[0]
                    filename = self.__get_symbol_filename(nunique_name)

            if filename == self.__default_page:
                self.warn("no-location-indication",
                          "No way to determine where %s should land"
                          " putting it to %s."
                          " Document the symbol for smart indexing to work" % (
                              unique_name, os.path.basename(filename)))
        else:
            filename = unique_filenames[0]
            if len(unique_filenames) > 1:
                self.warn("no-location-indication",
                          " Going wild here to determine where %s needs to land"
                          " as we could detect the following possibilities: %s."
                          % (unique_name, unique_filenames))
            else:
                self.debug(" No class comment for %s determined that it should"
                            " land into %s with all other class related documentation."
                            % (unique_name, os.path.basename(filename)))

        return filename

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
            name = self.__get_symbol_names(node)[0]
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
                self.__add_symbol_attrs(sym, owner_name=klass_name)
                children[klass_name] = sym

            klass_name = self.__get_klass_name(parent_class)
            link = Link(None, klass_name, klass_name)
            sym = QualifiedSymbol(type_tokens=[link])
            self.__add_symbol_attrs(sym, owner_name=klass_name)
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

        # self.info('Gathered %d links from devhelp index %s' % (len(keywords), path))

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
        if symbol.get_extension_attribute(self.extension_name, 'language') == 'c':
            annotations = self.__annotation_parser.make_annotations(symbol)

            # FIXME: OK this is format time but still seems strange
            if annotations:
                extra_content = formatter.format_annotations (annotations)
                symbol.extension_contents['Annotations'] = extra_content
        else:
            symbol.extension_contents.pop('Annotations', None)

    def __is_introspectable(self, name, language):
        if name in FUNDAMENTALS[language]:
            return True

        node = self.__node_cache.get(name)

        if node is None:
            return False

        if not name in self.__translated_names['c']:
            self.__add_translations(name, node)

        if node.attrib.get('introspectable') == '0':
            return False

        return True

    def __formatting_symbol(self, formatter, symbol, language):
        symbol.add_extension_attribute(self.extension_name, 'language', language)

        if type(symbol) in [ReturnItemSymbol, ParameterSymbol]:
            self.__add_annotations (formatter, symbol)

        if isinstance (symbol, QualifiedSymbol):
            return True

        # We discard symbols at formatting time because they might be exposed
        # in other languages
        if language != 'c':
            return self.__is_introspectable(symbol.unique_name, language)

        return True

    def insert_language(self, ref, language, project):
        if not ref.startswith(project.sanitized_name + '/'):
            return language + '/' + ref

        p = pathlib.Path(ref)
        return str(pathlib.Path(p.parts[0], language, *p.parts[1:]))

    def __translate_link_ref(self, link, language):
        fund = FUNDAMENTALS[language].get(link.id_)
        if fund:
            return fund.ref

        aliased_link = self.__aliased_links[language].get(link.id_)
        if aliased_link:
            return self.__translate_link_ref(aliased_link, language)

        page = self.project.get_page_for_symbol(link.id_)
        if page:
            if page.extension_name != self.extension_name:
                return None

            project = self.project.get_project_for_page (page)
            if link.ref and language != 'c' and not self.__is_introspectable(link.id_, language):
                return self.insert_language(link.ref, 'c', project)

            res = self.insert_language(link.ref, language, project)
            return res

        if link.ref is None:
            return self.__gtkdoc_hrefs.get(link.id_)

        return None

    @classmethod
    def search_online_links(cls, resolver, name):
        href = cls.__gtkdoc_hrefs.get(name)
        if href:
            return Link(href, name, name)
        return None

    def __translate_link_title(self, link, language):
        fund = FUNDAMENTALS[language].get(link.id_)
        if fund:
            return fund._title

        if language != 'c' and not self.__is_introspectable(link.id_, language):
            return link._title + ' (not introspectable)'

        aliased_link = self.__aliased_links[language].get(link.id_)
        if aliased_link:
            return self.__translate_link_title(aliased_link, language)

        translated = self.__translated_names[language].get(link.id_)
        if translated:
            return translated

        if language == 'c' and link.id_ in self.__gtkdoc_hrefs:
            return link.id_

        return None

    def setup_language (self, language, prev_l):
        if prev_l:
            Link.resolving_title_signal.disconnect(self.__translate_link_title,
                                                   prev_l)
            self.app.link_resolver.resolving_link_signal.disconnect(self.__translate_link_ref, prev_l)
        else:
            self.app.link_resolver.resolving_link_signal.disconnect(self.__translate_link_ref, self.languages[0])


        if language is not None:
            Link.resolving_title_signal.connect(self.__translate_link_title,
                                                language)
            self.app.link_resolver.resolving_link_signal.connect(self.__translate_link_ref, language)
        else:
            self.app.link_resolver.resolving_link_signal.connect_after(self.__translate_link_ref, self.languages[0])

    # We implement filtering of some symbols
    def get_or_create_symbol(self, *args, **kwargs):
        args = list(args)
        node = None
        if len(args) > 1:
            node = args.pop(1)
        aliases = kwargs.get('aliases', [])

        if self.smart_index:
            name = kwargs['display_name']
            if kwargs.get('filename', self.__default_page) == self.__default_page:
                unique_name = kwargs.get('unique_name', kwargs.get('display_name'))
                kwargs['filename'] = self.__get_symbol_filename(unique_name)
                if kwargs.get('filename', self.__default_page) == self.__default_page:
                    self.warn("no-location-indication",
                              "No way to determine where %s should land"
                              " putting it to %s."
                              " Document the symbol for smart indexing to work" % (
                              name, os.path.basename(self.__default_page)))

        res = super(GIExtension, self).get_or_create_symbol(*args, **kwargs)

        if node is not None and res:
            self.__node_cache[res.unique_name] = node
            for alias in aliases:
                self.__node_cache[alias] = node

        return res

    def __unnest_type (self, parameter):
        array_nesting = 0
        array = parameter.find('{http://www.gtk.org/introspection/core/1.0}array')
        glist = None
        if array is None:
            array = parameter.find(core_ns('type[@name="GLib.List"]'))
            glist = parameter

        while array is not None:
            array_nesting += 1
            parameter = array
            array = parameter.find('{http://www.gtk.org/introspection/core/1.0}array')
            if array is None:
                array = parameter.find(core_ns('type[@name="GLib.List"]'))

        if glist is not None:
            parameter = glist

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

    def __add_symbol_attrs(self, symbol, **kwargs):
        for key, val in kwargs.items():
            symbol.add_extension_attribute(self.extension_name, key, val)

    def __get_symbol_attr(self, symbol, attrname):
        return symbol.extension_attributes.get(self.extension_name, {}).get(
            attrname, None)

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

        # gchar ** is being typed to utf8* by GI, special case it.
        if array_nesting == 1 and type_.attrib.get(c_ns('type')) == 'gchar**':
            ctype_name = 'gchar**'

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

        return type_tokens, ptype_name, ctype_name, array_nesting

    def __create_parameter_symbol (self, gi_parameter, owner_name):
        param_name = gi_parameter.attrib['name']

        type_tokens, gi_name, ctype_name, array_nesting = self.__type_tokens_and_gi_name_from_gi_node (gi_parameter)

        direction = gi_parameter.attrib.get('direction')
        if direction is None:
            direction = 'in'

        res = ParameterSymbol(argname=param_name, type_tokens=type_tokens)
        self.__add_symbol_attrs(res, gi_name=gi_name, owner_name=owner_name,
                                direction=direction, array_nesting=array_nesting)

        return res, direction

    def __create_return_value_symbol (self, gi_retval, out_parameters, owner_name):
        type_tokens, gi_name, ctype_name, array_nesting = self.__type_tokens_and_gi_name_from_gi_node(gi_retval)

        if gi_name == 'none':
            ret_item = None
        else:
            ret_item = ReturnItemSymbol (type_tokens=type_tokens)
            self.__add_symbol_attrs(ret_item, gi_name=gi_name,
                                    owner_name=owner_name,
                                    array_nesting=array_nesting)

        res = [ret_item]

        for out_param in out_parameters:
            ret_item = ReturnItemSymbol (type_tokens=out_param.input_tokens,
                    name=out_param.argname)
            self.__add_symbol_attrs(ret_item, owner_name=owner_name)
            res.append(ret_item)

        return res

    def __create_parameters_and_retval (self, node, owner_name):
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
            param, direction = self.__create_parameter_symbol (instance_param,
                                                               owner_name)
            parameters.append (param)

        out_parameters = []
        for gi_parameter in gi_parameters:
            param, direction = self.__create_parameter_symbol (gi_parameter,
                                                               owner_name)
            parameters.append (param)
            if direction != 'in':
                out_parameters.append (param)

        retval = node.find('{http://www.gtk.org/introspection/core/1.0}return-value')
        retval = self.__create_return_value_symbol (retval, out_parameters,
                                                    owner_name)

        return (parameters, retval)

    def __sort_parameters (self, symbol, retval, parameters):
        in_parameters = []
        out_parameters = []

        for i, param in enumerate (parameters):
            if isinstance(symbol, MethodSymbol) and i == 0:
                continue

            direction = param.get_extension_attribute ('gi-extension', 'direction')

            if direction == 'in' or direction == 'inout':
                in_parameters.append (param)
            if direction == 'out' or direction == 'inout':
                out_parameters.append (param)

        self.__add_symbol_attrs(symbol, parameters=in_parameters)

    def __get_gi_name (self, node):
        components = self.__get_gi_name_components(node)
        return '.'.join(components)

    def __create_signal_symbol (self, node, parent_name):
        unique_name, name, klass_name = self.__get_symbol_names(node)

        parameters, retval = self.__create_parameters_and_retval (node,
                                                                  unique_name)

        parent_node = node.getparent()
        parent_gi_name = self.__get_gi_name(parent_node)
        parent_link = Link(None, parent_name, parent_name)

        instance_param = ParameterSymbol(argname='self', type_tokens=[parent_link, '*'])
        self.__add_symbol_attrs (instance_param, gi_name=parent_gi_name,
            owner_name=unique_name, direction='in')
        parameters.insert (0, instance_param)

        udata_link = Link(None, 'gpointer', 'gpointer')
        udata_param = ParameterSymbol(argname='user_data', type_tokens=[udata_link])
        self.__add_symbol_attrs (udata_param, gi_name='gpointer',
            owner_name=unique_name, direction='in')
        parameters.append (udata_param)

        res = self.get_or_create_symbol(SignalSymbol, node,
                parameters=parameters, return_value=retval,
                display_name=name, unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name),
                parent_name=parent_name)

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

    def __create_property_symbol (self, node, parent_name):
        unique_name, name, klass_name = self.__get_symbol_names(node)

        type_tokens, gi_name, ctype_name, array_nesting = self.__type_tokens_and_gi_name_from_gi_node(node)
        type_ = QualifiedSymbol (type_tokens=type_tokens)
        self.__add_symbol_attrs(type_, gi_name=gi_name, owner_name=unique_name,
                                array_nesting=array_nesting)

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

        res = self.get_or_create_symbol(PropertySymbol, node,
                prop_type=type_,
                display_name=name,
                unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name),
                parent_name=parent_name)

        extra_content = self.formatter._format_flags (flags)
        res.extension_contents['Flags'] = extra_content

        return res

    def __create_vfunc_symbol (self, node, parent_name):
        klass_node = node.getparent()
        ns = klass_node.getparent()
        gtype_struct = klass_node.attrib.get(glib_ns('type-struct'))

        klass_comment = self.app.database.get_comment('%s%s' %
            (ns.attrib['name'], gtype_struct))

        unique_name, name, klass_name = self.__get_symbol_names(node)

        if klass_comment:
            param_comment = klass_comment.params.get(name)
            if (param_comment):
                self.app.database.add_comment(
                    Comment(name=unique_name,
                            description=param_comment.description,
                            annotations=param_comment.annotations))

        parameters, retval = self.__create_parameters_and_retval (node,
                                                                  unique_name)
        symbol = self.get_or_create_symbol(VFunctionSymbol, node,
                parameters=parameters,
                return_value=retval, display_name=name,
                unique_name=unique_name,
                filename=self.__get_symbol_filename(klass_name),
                parent_name=parent_name,
                aliases=[unique_name.replace('::', '.')])

        self.__sort_parameters (symbol, retval, parameters)

        return symbol

    def __get_symbol_filename(self, unique_name):
        if self.__current_output_filename:
            return self.__current_output_filename

        comment = self.app.database.get_comment(unique_name)
        if comment and comment.filename:
            return '%s.h' % os.path.splitext(comment.filename)[0]

        return self.__default_page

    def __create_alias_symbol (self, node, gi_name, parent_name):
        name = self.__get_symbol_names(node)[0]

        type_tokens, gi_name, ctype_name, array_nesting = self.__type_tokens_and_gi_name_from_gi_node(node)
        aliased_type = QualifiedSymbol(type_tokens=type_tokens)
        self.__add_symbol_attrs(aliased_type, owner_name=name,
                                array_nesting=array_nesting)
        filename = self.__get_symbol_filename(name)

        alias_link = [l for l in type_tokens if isinstance(l, Link)]
        for lang in ('python', 'javascript'):
            fund_type = FUNDAMENTALS[lang].get(ctype_name)
            if fund_type:
                # The alias name is now conciderd as a FUNDAMENTAL type.
                FUNDAMENTALS[lang][name] = fund_type
            else:
                if alias_link:
                    self.__aliased_links[lang][name] = alias_link[0]

        return self.get_or_create_symbol(AliasSymbol, node,
                                         aliased_type=aliased_type,
                                         display_name=name,
                                         filename=filename,
                                         parent_name=parent_name)

    def __create_structure(self, symbol_type, node, gi_name):
        if node.attrib.get(glib_ns('fundamental')) == '1':
            self.debug('%s is a fundamental type, not an actual '
                       'object class' % (node.attrib['name']))
            return

        unique_name, unused_name, klass_name = self.__get_symbol_names(node)
        # Hidding class private structures
        if node.attrib.get('disguised') == '1' and \
                unique_name.endswith(('Priv', 'Private')):
            self.debug('%s seems to be a GObject class private structure, hiding it.'
                       % (unique_name))
            return

        filename = self.__find_structure_pagename(node, unique_name,
                                                  symbol_type == ClassSymbol)

        self.__current_output_filename = filename
        parent_name = unique_name
        if symbol_type == ClassSymbol:
            res = self.__create_class_symbol(node, gi_name,
                                            klass_name,
                                            unique_name,
                                            filename)
            class_struct =  node.attrib.get(glib_ns('type-struct'))
            if class_struct:
                self.__class_gtype_structs[class_struct] = res
        elif symbol_type == StructSymbol:
            # If we are working with a Class structure,
            class_symbol = self.__class_gtype_structs.get(node.attrib['name'])
            if class_symbol:
                parent_name = class_symbol.unique_name

                # Class struct should never be renderer on their own,
                # smart_key will lookup the value in that dict
                self.__class_gtype_structs[unique_name] = class_symbol
            res = self.__create_struct_symbol(node, unique_name, filename,
                                              class_symbol.unique_name if class_symbol else None)

            if class_symbol:
                class_symbol.extra['class_structure'] = res
        else:  # Interface
            res = self.__create_interface_symbol(node, unique_name, filename)
            class_struct =  node.attrib.get(glib_ns('type-struct'))
            if class_struct:
                self.__class_gtype_structs[class_struct] = res

        for cnode in node:
            if cnode.tag in [core_ns('record'), core_ns('union')]:
                continue
            self.__scan_node(cnode, parent_name=parent_name)

        self.__current_output_filename = None

        return res

    def __create_class_symbol (self, node, gi_name, klass_name,
                               unique_name, filename):
        hierarchy = self.__gir_hierarchies[gi_name]
        children = self.__gir_children_map[gi_name]

        members, raw_text = self.__get_structure_members(node, filename,
                                                         klass_name,
                                                         unique_name)

        res = self.get_or_create_symbol(ClassSymbol, node,
                                        hierarchy=hierarchy,
                                        children=children,
                                        display_name=klass_name,
                                        unique_name=unique_name,
                                        filename=filename,
                                        raw_text=raw_text,
                                        members=members,
                                        parent_name=unique_name)

        return res

    def __get_array_type(self, node):
        array = node.find(core_ns('array'))
        if array is None:
            return None

        return array.attrib[c_ns('type')]

    def __get_return_type_from_callback(self, node):
        return_node = node.find(core_ns('return-value'))
        array_type = self.__get_array_type(return_node)
        if array_type:
            return array_type

        return return_node.find(core_ns('type')).attrib[c_ns('type')]

    def __get_structure_members(self, node, filename, struct_name, parent_name,
                                is_union=False, indent=4 * ' ',
                                concatenated_name=None, in_union=False):
        if is_union:
            sname = ''
        else:
            sname = struct_name + ' ' if struct_name is not None else ''

        struct_str = "%s%s{" % ('union ' if is_union else 'struct ', sname)
        members = []
        for field in node.getchildren():
            if field.tag in [core_ns('record'), core_ns('union')]:
                if not concatenated_name:
                    concatenated_name = parent_name

                if struct_name and struct_name != parent_name:
                    concatenated_name += '.' + struct_name

                new_union = field.tag == core_ns('union')
                union_members, union_str = self.__get_structure_members(
                    field, filename, field.attrib.get('name', None),
                    parent_name, indent=indent + 4 * ' ',
                    is_union=new_union, concatenated_name=concatenated_name,
                    in_union=in_union or new_union)
                struct_str += "\n%s%s" % (indent, union_str)
                members += union_members
                continue
            elif field.tag != core_ns('field'):
                continue

            children = field.getchildren()
            if not children:
                continue

            if field.attrib.get('private', False):
                continue

            type_gi_name = None
            if children[0].tag == core_ns('callback'):
                field_name = field.attrib['name'] + '()'
                type_ = self.__get_return_type_from_callback(children[0])

                struct_str += "\n%s%s %s (" % (indent, type_, field_name[:-2])
                parameters_nodes = children[0].find(core_ns('parameters'))
                if parameters_nodes is not None:
                    for j, gi_parameter in enumerate(parameters_nodes):
                        param_name = gi_parameter.attrib['name']
                        type_tokens, gi_name, ctype_name, array_nesting = \
                            self.__type_tokens_and_gi_name_from_gi_node(gi_parameter)
                        struct_str += "%s%s %s" % (', ' if j else '', ctype_name, param_name)
                struct_str += ");"

                # Weed out vmethods, handled separately
                continue
            else:
                field_name = field.attrib['name']
                array_type = self.__get_array_type(field)
                if array_type:
                    type_ = array_type
                else:
                    type_node = field.find(core_ns('type'))
                    type_ = type_node.attrib[c_ns('type')]
                    type_gi_name = type_node.attrib.get('name')
                struct_str += "\n%s%s %s;" % (indent, type_, field_name)


            name = "%s.%s" % (concatenated_name or struct_name, field_name)
            aliases = ["%s::%s" % (struct_name, field_name)]

            tokens = self.__type_tokens_from_cdecl (type_)
            qtype = QualifiedSymbol(type_tokens=tokens)

            self.__add_symbol_attrs(qtype, owner_name=struct_name)
            member = self.get_or_create_symbol(
                FieldSymbol, field,
                member_name=field_name, qtype=qtype,
                filename=filename, display_name=name,
                unique_name=name, parent_name=parent_name,
                aliases=aliases)
            self.__add_symbol_attrs(member, owner_name=struct_name,
                                    gi_name=type_gi_name,
                                    in_union=in_union)
            members.append(member)

        if is_union and struct_name:
            struct_str += '\n%s} %s;' % (indent[3:], struct_name)
        else:
            struct_str += '\n%s};' % indent[3:]

        return members, struct_str

    def __create_struct_symbol(self, node, struct_name, filename,
                               parent_name):

        members, raw_text = self.__get_structure_members(
            node, filename, struct_name,
            parent_name=struct_name)

        return self.get_or_create_symbol(StructSymbol, node,
                                  display_name=struct_name,
                                  unique_name=struct_name,
                                  anonymous=False,
                                  filename=filename,
                                  members=members,
                                  parent_name=parent_name,
                                  raw_text=raw_text)

    def __create_interface_symbol (self, node, unique_name, filename):
        return self.get_or_create_symbol(InterfaceSymbol, node,
                display_name=unique_name,
                unique_name=unique_name,
                filename=filename)

    def __get_gi_name_components(self, node):
        parent = node.getparent()
        if 'name' in node.attrib:
            components = [node.attrib.get('name')]
        else:
            components = []

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
            self.__translated_names['python'][unique_name] = gi_name
            components[-1] = 'prototype.%s' % components[-1]
            self.__translated_names['javascript'][unique_name] = '.'.join(components)
            self.__translated_names['c'][unique_name] = unique_name
        elif id_type in node.attrib:
            self.__translated_names['python'][unique_name] = gi_name
            self.__translated_names['javascript'][unique_name] = gi_name
            self.__translated_names['c'][unique_name] = unique_name

        return components, gi_name

    def __get_function_name(self, func):
        return func.attrib.get('{%s}identifier' % self.__nsmap['c'])

    def __create_function_symbol (self, node, parent_name):
        name = self.__get_symbol_names(node)[0]

        self.__add_translations(name, node)

        gi_params, retval = self.__create_parameters_and_retval (node,
                                                                 name)

        if node.tag.endswith ('method'):
            if node.getparent().attrib.get(glib_ns('is-gtype-struct-for')):
                type_ = ClassMethodSymbol
            else:
                type_ = MethodSymbol
        elif node.tag==core_ns('constructor'):
            type_ = ConstructorSymbol
        else:
            type_ = FunctionSymbol
            parent_name = None
        func = self.get_or_create_symbol(type_, node,
                                         parameters=gi_params,
                                         return_value=retval,
                                         display_name=name,
                                         unique_name=name,
                                         throws='throws' in node.attrib,
                                         filename=self.__get_symbol_filename(name),
                                         parent_name=parent_name)

        self.__sort_parameters (func, func.return_value, func.parameters)
        return func

    def __rename_page_link (self, page_parser, original_name):
        return self.__translated_names.get(original_name)

    def _get_smart_key(self, symbol):
        if self.__class_gtype_structs.get(symbol.unique_name):
            # Working with a Class Structure, not adding it anywhere
            return None

        return symbol.extra.get('implementation_filename',
                                super()._get_smart_key(symbol))
