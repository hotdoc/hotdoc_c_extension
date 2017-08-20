import os
from lxml import etree

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

NODE_CACHE = {}
# We need to collect all class nodes and build the
# hierarchy beforehand, because git class nodes do not
# know about their children
CLASS_NODES = {}

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

def cache_nodes(gir_root, all_girs):
    ns_node = gir_root.find('./{%s}namespace' % NS_MAP['core'])
    id_prefixes = ns_node.attrib['{%s}identifier-prefixes' % NS_MAP['c']]
    sym_prefixes = ns_node.attrib['{%s}symbol-prefixes' % NS_MAP['c']]

    id_key = '{%s}identifier' % NS_MAP['c']
    for node in gir_root.xpath(
            './/*[@c:identifier]',
            namespaces=NS_MAP):
        NODE_CACHE[node.attrib[id_key]] = node

    id_type = '{%s}type' % NS_MAP['c']
    class_tag = '{%s}class' % NS_MAP['core']
    interface_tag = '{%s}interface' % NS_MAP['core']
    for node in gir_root.xpath(
            './/*[not(self::core:type) and not (self::core:array)][@c:type]',
            namespaces=NS_MAP):
        name = node.attrib[id_type]
        NODE_CACHE[name] = node
        if node.tag in [class_tag, interface_tag]:
            gi_name = '.'.join(get_gi_name_components(node))
            CLASS_NODES[gi_name] = node
            NODE_CACHE['%s::%s' % (name, name)] = node
            generate_smart_filters(id_prefixes, sym_prefixes, node)

    for node in gir_root.xpath(
            './/core:property',
            namespaces=NS_MAP):
        name = '%s:%s' % (get_klass_name(node.getparent()),
                          node.attrib['name'])
        NODE_CACHE[name] = node

    for node in gir_root.xpath(
            './/glib:signal',
            namespaces=NS_MAP):
        name = '%s::%s' % (get_klass_name(node.getparent()),
                           node.attrib['name'])
        NODE_CACHE[name] = node

    for node in gir_root.xpath(
            './/core:virtual-method',
            namespaces=NS_MAP):
        name = get_symbol_names(node)[0]
        NODE_CACHE[name] = node

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
