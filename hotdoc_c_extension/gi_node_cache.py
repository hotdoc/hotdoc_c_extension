import os
from collections import defaultdict
from lxml import etree
import networkx as nx
from hotdoc.core.symbols import QualifiedSymbol
from hotdoc_c_extension.gi_utils import *


# Boilerplate GObject macros we don't want to expose
SMART_FILTERS = set()

def generate_smart_filters(id_prefixes, sym_prefixes, node):
    sym_prefix = node.attrib['{%s}symbol-prefix' % NS_MAP['c']]
    SMART_FILTERS.add(('%s_IS_%s' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_TYPE_%s' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_%s' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_%s_CLASS' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_IS_%s_CLASS' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_%s_GET_CLASS' % (sym_prefixes, sym_prefix)).upper())
    SMART_FILTERS.add(('%s_%s_GET_IFACE' % (sym_prefixes, sym_prefix)).upper())


HIERARCHY_GRAPH = nx.DiGraph()


ALL_GI_TYPES = {}


# Avoid parsing gir files multiple times
PARSED_GIRS = set()

def find_gir_file(gir_name, all_girs):
    if gir_name in all_girs:
        return all_girs[gir_name]

    xdg_dirs = os.getenv('XDG_DATA_DIRS') or ''
    xdg_dirs = [p for p in xdg_dirs.split(':') if p]
    xdg_dirs.append(DATADIR)
    for dir_ in xdg_dirs:
        gir_file = os.path.join(dir_, 'gir-1.0', gir_name)
        if os.path.exists(gir_file):
            return gir_file
    return None


TRANSLATED_NAMES = {l: {} for l in OUTPUT_LANGUAGES}


NON_INTROSPECTABLE_SYMBOLS = set()


def translate(unique_name, node):
    components = get_gi_name_components(node)
    gi_name = '.'.join(components)

    if c_ns('identifier') in node.attrib:
        TRANSLATED_NAMES['python'][unique_name] = gi_name
        components[-1] = 'prototype.%s' % components[-1]
        TRANSLATED_NAMES['javascript'][unique_name] = '.'.join(components)
        TRANSLATED_NAMES['c'][unique_name] = unique_name
    elif c_ns('type') in node.attrib:
        TRANSLATED_NAMES['python'][unique_name] = gi_name
        TRANSLATED_NAMES['javascript'][unique_name] = gi_name
        TRANSLATED_NAMES['c'][unique_name] = unique_name
    else:
        TRANSLATED_NAMES['python'][unique_name] = node.attrib.get('name')
        TRANSLATED_NAMES['javascript'][unique_name] = node.attrib.get('name')
        TRANSLATED_NAMES['c'][unique_name] = node.attrib.get('name')

    if node.attrib.get('introspectable') == '0':
        NON_INTROSPECTABLE_SYMBOLS.add(unique_name)

def append(unique_name, node):
    translate (unique_name, node)


def update_hierarchies(cur_ns, node):
    gi_name = '.'.join(get_gi_name_components(node))
    ALL_GI_TYPES[gi_name] = get_klass_name(node)
    parent_name = node.attrib.get('parent')
    if not parent_name:
        return

    if not '.' in parent_name:
        parent_name = '%s.%s' % (cur_ns, parent_name)

    HIERARCHY_GRAPH.add_edge(parent_name, gi_name)


def get_parent_link(gi_name, res):
    parents = HIERARCHY_GRAPH.predecessors(gi_name)
    if parents:
        get_parent_link(parents[0], res)
    ctype_name = ALL_GI_TYPES[gi_name]
    qs = QualifiedSymbol(type_tokens=[Link(None, ctype_name, ctype_name)])
    res.append(qs)


def get_parents_hierarchy(gi_name):
    res = []
    parents = HIERARCHY_GRAPH.predecessors(gi_name)
    if not parents:
        return []
    get_parent_link(parents[0], res)
    return res


def get_children(gi_name):
    res = {}
    children = HIERARCHY_GRAPH.successors(gi_name)
    for gi_name in children:
        ctype_name = ALL_GI_TYPES[gi_name]
        res[ctype_name] = QualifiedSymbol(type_tokens=[Link(None, ctype_name, ctype_name)])
    return res


def cache_nodes(gir_root, all_girs):
    ns_node = gir_root.find('./{%s}namespace' % NS_MAP['core'])
    id_prefixes = ns_node.attrib['{%s}identifier-prefixes' % NS_MAP['c']]
    sym_prefixes = ns_node.attrib['{%s}symbol-prefixes' % NS_MAP['c']]

    id_key = '{%s}identifier' % NS_MAP['c']
    for node in gir_root.xpath(
            './/*[@c:identifier]',
            namespaces=NS_MAP):
        append (node.attrib[id_key], node)

    id_type = '{%s}type' % NS_MAP['c']
    class_tag = '{%s}class' % NS_MAP['core']
    interface_tag = '{%s}interface' % NS_MAP['core']
    for node in gir_root.xpath(
            './/*[not(self::core:type) and not (self::core:array)][@c:type]',
            namespaces=NS_MAP):
        name = node.attrib[id_type]
        append (name, node)
        if node.tag in [class_tag, interface_tag]:
            update_hierarchies (ns_node.attrib.get('name'), node)
            append('%s::%s' % (name, name), node)
            generate_smart_filters(id_prefixes, sym_prefixes, node)

    for node in gir_root.xpath(
            './/core:property',
            namespaces=NS_MAP):
        name = '%s:%s' % (get_klass_name(node.getparent()),
                          node.attrib['name'])
        append (name, node)

    for node in gir_root.xpath(
            './/glib:signal',
            namespaces=NS_MAP):
        name = '%s::%s' % (get_klass_name(node.getparent()),
                           node.attrib['name'])
        append (name, node)

    for node in gir_root.xpath(
            './/core:virtual-method',
            namespaces=NS_MAP):
        name = get_symbol_names(node)[0]
        append (name, node)

    for inc in gir_root.findall('./core:include',
            namespaces = NS_MAP):
        inc_name = inc.attrib["name"]
        inc_version = inc.attrib["version"]
        gir_file = find_gir_file('%s-%s.gir' % (inc_name, inc_version), all_girs)
        if not gir_file:
            warn('missing-gir-include', "Couldn't find a gir for %s-%s.gir" %
                    (inc_name, inc_version))
            continue

        if gir_file in PARSED_GIRS:
            continue

        PARSED_GIRS.add(gir_file)
        inc_gir_root = etree.parse(gir_file).getroot()
        cache_nodes(inc_gir_root, all_girs)
        del inc_gir_root
