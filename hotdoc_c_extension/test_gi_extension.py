import unittest
from lxml import etree
from hotdoc_c_extension.gi_extension import *

GIR_TEMPLATE = \
'''
<repository version="1.2"
            xmlns="http://www.gtk.org/introspection/core/1.0"
            xmlns:c="http://www.gtk.org/introspection/c/1.0"
            xmlns:glib="http://www.gtk.org/introspection/glib/1.0">
  <include name="GObject" version="2.0"/>
  <package name="test"/>
  <namespace name="Test"
             version="1.0"
             shared-library="libglib-2.0.so.0,libgobject-2.0.so.0,libtestlib.so"
             c:identifier-prefixes="Test"
             c:symbol-prefixes="test">
  %s
  </namespace>
</repository>
'''

ARRAY_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value transfer-ownership="full">
    <doc xml:space="preserve">The list of greetings @greeter can do</doc>
    <array c:type="gchar***">
      <array>
        <type name="utf8"/>
      </array>
    </array>
  </return-value>
</method>
'''

LIST_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value transfer-ownership="full">
    <doc xml:space="preserve">The friends to check</doc>
    <type name="GLib.List" c:type="GList*">
      <type name="Greeter"/>
    </type>
  </return-value>
</method>
'''

STRING_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value transfer-ownership="full">
    <doc xml:space="preserve">something to bar</doc>
    <type name="utf8" c:type="gchar*"/>
  </return-value>
</method>
'''

NONE_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value>
    <type name="none" c:type="void"/>
  </return-value>
</method>
'''

VARARGS_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <parameters>
    <parameter name='...' transfer-ownership="none">
      <varargs/>
    </parameter>
  </parameters>
</method>
'''


UNKNOWN_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value>
    <type/>
  </return-value>
</method>
'''


GI_TYPE = \
'''
<method name="list_greets" c:identifier="test_greeter_list_greets">
  <return-value>
    <type name="GObject.Object"/>
  </return-value>
</method>
'''



class TestGIExtension(unittest.TestCase):
    def assertRetvalTypesEqual(self, symbol_string, ctype_name, gi_name, array_nesting):
        test_data = GIR_TEMPLATE % symbol_string
        gir_root = etree.fromstring (test_data)
        retval = gir_root.find('.//%s/%s' %
                (core_ns ('method'), core_ns('return-value')))
        self.assertTupleEqual (unnest_type (retval), (ctype_name, gi_name, array_nesting))

    def test_array_type(self):
        self.assertRetvalTypesEqual(ARRAY_TYPE, 'gchar***', 'utf8', 2)

    def test_list_type(self):
        self.assertRetvalTypesEqual(LIST_TYPE, 'GList*', 'Greeter', 1)

    def test_string_type(self):
        self.assertRetvalTypesEqual(STRING_TYPE, 'gchar*', 'utf8', 0)

    def test_none_type(self):
        self.assertRetvalTypesEqual(NONE_TYPE, 'void', 'none', 0)

    def test_unknown_type(self):
        self.assertRetvalTypesEqual(UNKNOWN_TYPE, None, 'object', 0)

    def test_gi_type(self):
        self.assertRetvalTypesEqual(GI_TYPE, None, 'GObject.Object', 0)

    def test_varargs_type(self):
        test_data = GIR_TEMPLATE % VARARGS_TYPE
        gir_root = etree.fromstring (test_data)
        param = gir_root.find('.//%s/%s/%s' %
                (core_ns ('method'), core_ns('parameters'), core_ns('parameter')))
        self.assertTupleEqual (unnest_type (param), ('...', 'valist', 0))
