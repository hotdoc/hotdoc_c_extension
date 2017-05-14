import os
import copy

from collections import OrderedDict
from lxml import etree

from hotdoc.tests.fixtures import HotdocTest
from hotdoc.core.config import Config
from hotdoc.core.database import Database
from hotdoc.core.comment import Comment
from hotdoc.utils.loggable import Logger
from hotdoc_c_extension.gi_extension import GIExtension, DEFAULT_PAGE

Logger.silent = True

HERE = os.path.realpath(os.path.dirname(__file__))

# Hack to avoid parsing online links -- taking time for nothing
GIExtension._GIExtension__gathered_gtk_doc_links = True


STRUCTURE = \
    OrderedDict([('gi-index',
                  OrderedDict([('symbols', []),
                               ('subpages',
                                OrderedDict([('test-greeter.h',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'TEST_GREETER_VERSION'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TEST_GREETER_UPDATE_GREET_COUNT'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterCountUnit'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterThing'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'test_greeter_do_foo_bar'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass::do_greet'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass::do_nothing'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'test_greeter_deprecated_function'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'test_greeter_get_translate_function'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'test_greeter_greet'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter:count-greets'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter::greeted'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter.parent'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter.greet_count'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter.peer'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter.count_greets'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeter'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass.parent_class'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass.do_greet()'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass.do_nothing()'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterClass'),
                                                                          ('parent_name',
                                                                           'TestGreeter')]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterLanguage'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestGreeterTranslateFunction'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestSomeStruct.plop'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestSomeStruct'),
                                                                          ('parent_name',
                                                                           None)])]),
                                                           ('subpages',
                                                            OrderedDict())])),
                                             ('test-gobject-macros.h',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'test_derivable_new'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'TestDerivable.parent_instance'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'TestDerivable'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'TestDerivableClass.parent_class'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'TestDerivableClass._padding'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'TestDerivableClass'),
                                                                          ('parent_name',
                                                                           'TestDerivable')]),
                                                             OrderedDict([('name',
                                                                           'test_final_new'),
                                                                          ('parent_name',
                                                                           'TestFinal')]),
                                                             OrderedDict([('name',
                                                                           'TestFinal'),
                                                                          ('parent_name',
                                                                           'TestFinal')]),
                                                             OrderedDict([('name',
                                                                           'TestFinalClass.parent_class'),
                                                                          ('parent_name',
                                                                           'TestFinal')]),
                                                             OrderedDict([('name',
                                                                           'TestFinalClass'),
                                                                          ('parent_name',
                                                                           'TestFinal')])]),
                                                           ('subpages',
                                                            OrderedDict())])),
                                             ('test-interface.h',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'TestInterfaceInterface::do_something'),
                                                                          ('parent_name',
                                                                           'TestInterface')]),
                                                             OrderedDict([('name',
                                                                           'test_interface_do_something'),
                                                                          ('parent_name',
                                                                           'TestInterface')]),
                                                             OrderedDict([('name',
                                                                           'TestInterface'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'TestInterfaceInterface.parent_iface'),
                                                                          ('parent_name',
                                                                           'TestInterface')]),
                                                             OrderedDict([('name',
                                                                           'TestInterfaceInterface.do_something()'),
                                                                          ('parent_name',
                                                                           'TestInterface')]),
                                                             OrderedDict([('name',
                                                                           'TestInterfaceInterface'),
                                                                          ('parent_name',
                                                                           'TestInterface')])]),
                                                           ('subpages',
                                                            OrderedDict())])),
                                             ('Miscellaneous.default_page',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'TestUndocumentedFlag'),
                                                                          ('parent_name',
                                                                           None)])]),
                                                           ('subpages',
                                                            OrderedDict())])),
                                             ('test-other-file.h',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'test_bar_ze_bar'),
                                                                          ('parent_name',
                                                                           None)]),
                                                             OrderedDict([('name',
                                                                           'test_bar_ze_foo'),
                                                                          ('parent_name',
                                                                           None)])]),
                                                           ('subpages',
                                                            OrderedDict())])),
                                             ('c_subfolder/test_subfolder.h',
                                              OrderedDict([('symbols',
                                                            [OrderedDict([('name',
                                                                           'test_c_function_in_subfolder'),
                                                                          ('parent_name',
                                                                           None)])]),
                                                           ('subpages',
                                                            OrderedDict())]))]))]))])


class TestGiExtension(HotdocTest):

    def create_application(self):
        self.maxDiff = None
        app = super().create_application()
        self.assertEqual(app.extension_classes['gi-extension'], GIExtension)

        return app

    def get_gir(self, project_path='test'):
        girname = project_path.capitalize() + '-1.0.gir'

        return os.path.join(HERE, 'test_sources', project_path, girname)

    def get_sources(self, project_path='test'):
        return [os.path.join(HERE, 'test_sources/', project_path, '*.[ch]'),
                os.path.join(HERE, 'test_sources/', project_path, '*/*.[ch]')]

    def get_config(self, sitemap_content='gi-index', project_path='test',
                   extra_conf=None):
        return Config(conf_file=self.get_config_file(sitemap_content,
                                                     project_path=project_path,
                                                     extra_conf=extra_conf))

    def get_config_file(self, sitemap_content='gi-index', project_path='test',
                        extra_conf=None):
        if extra_conf is None:
            extra_conf = {}
        extra_conf.update({'gi_sources': [self.get_gir(project_path=project_path)],
                        'gi_c_sources': self.get_sources(project_path=project_path),
                        'gi_smart_index': True,
                        'html_theme': None})

        return self._create_project_config_file(
            project_path, sitemap_content=sitemap_content,
            extra_conf=extra_conf)

    def build_tree(self, pages, page, node):
        pnode = OrderedDict()
        symbols = []

        for symbol in page.symbols:
            symbols.append(
                OrderedDict([('name', symbol.unique_name),
                             ('parent_name', symbol.parent_name)]))
        pnode['symbols'] = symbols

        subpages = OrderedDict({})
        for pname in page.subpages:
            subpage = pages[pname]
            self.build_tree(pages, subpage, subpages)

        pnode['subpages'] = subpages
        node[page.source_file] = pnode

    def create_project_and_run(self, project_path='test',
                               extra_conf=None):
        app = self.create_application()
        config = self.get_config(project_path=project_path,
                                 extra_conf=extra_conf)

        app.parse_config(config)
        app.run()

        return app

    def test_output_structure(self):
        app = self.create_project_and_run()

        tree = app.project.tree
        root = tree.root
        self.assertEqual(root.source_file, 'gi-index')
        self.assertEqual(list(root.subpages),
                         ['test-greeter.h', 'test-gobject-macros.h',
                          'test-interface.h', DEFAULT_PAGE,
                          'test-other-file.h', 'c_subfolder/test_subfolder.h'])
        pages = tree.get_pages()

        structure = OrderedDict()
        self.build_tree(pages, root, structure)

        if os.environ.get('PRINT_STRUCTURE'):
            import pprint
            pprint.pprint(structure)
        self.assertDictEqual(structure, STRUCTURE)

    def test_reorder_classes(self):
        app = self.create_application()
        self._create_md_file('test-gobject-macros.h.markdown',
                             '---\nsymbols:\n  - TestFinal\n  - TestDerivable\n...\n')
        config = self.get_config(
            sitemap_content='gi-index\n	test-gobject-macros.h')

        app.parse_config(config)
        app.database.add_comment(
            Comment(name="TestUndocumentedFlag",
                    filename=os.path.join(
                        HERE, 'test_sources/test/', "test-greeter.h"),
                    description="Greeter than great"))
        app.run()

        project = app.project
        tree = project.tree
        root = tree.root

        tree = app.project.tree
        pages = tree.get_pages()
        structure = OrderedDict()

        page = pages['test-gobject-macros.h']
        symbol_names = list(page.symbol_names)
        self.assertEqual(symbol_names[0], 'TestFinal')
        self.assertEqual(symbol_names[1], 'TestDerivable')
        self.assertEqual(page.comment.title.description, 'Derivable and more')

    def test_adding_symbol_doc(self):
        app = self.create_application()
        config = self.get_config()

        app.parse_config(config)
        app.database.add_comment(
            Comment(name="TestUndocumentedFlag",
                    filename=os.path.join(
                        HERE, 'test_sources/test/', "test-greeter.h"),
                    description="Greeter than great"))
        app.run()

        project = app.project
        tree = project.tree
        root = tree.root

        tree = app.project.tree
        pages = tree.get_pages()
        structure = OrderedDict()
        self.build_tree(pages, root, structure)

        nstructure = copy.deepcopy(STRUCTURE)
        del nstructure['gi-index']['subpages'][DEFAULT_PAGE]
        nstructure['gi-index']['subpages']['test-greeter.h']['symbols'].insert(
            9999, OrderedDict([('name', 'TestUndocumentedFlag'), ('parent_name', None)]))
        if os.environ.get('PRINT_STRUCTURE'):
            import pprint
            pprint.pprint(structure)
        self.assertDictEqual(structure, nstructure)

    def get_html(self, app, filename, project=None, language='c'):
        filename = os.path.join(language, filename)
        if project is not None:
            filename = os.path.join(project.sanitized_name, filename)

        with open(os.path.join(app.output, "html", filename), 'r') as _:
            _html = etree.HTML(_.read())
        return _html

    def assertLinkEqual(self, app, filename, text, expected_link, n_link=0):
        filename = os.path.join(app.output, "html", filename)
        with open(filename, 'r') as _:
            funchtml = etree.HTML(_.read())

        try:
            link = [a for a in funchtml.findall('.//a') if a.text == text][n_link]
        except Exception as _:
            self.assertIsNone("Could not find %s on the %sth link in file %s: %s"
                            % (text, n_link, filename, _))

        self.assertEqual(link.attrib['href'], expected_link)

    def test_link_for_lang_in_another_project(self):
        app = self.create_application()
        self.get_config_file(project_path='obj')

        index_content = "# test_link_for_lang_in_another_project"
        index_path = self._create_md_file('index.md', index_content)

        self.get_config_file(project_path='func')

        content = 'project.markdown\n\tfunc.json\n\tobj.json'
        config = self._create_project_config(
            'project', sitemap_content=content)
        self.get_config_file()
        app.parse_config(config)

        app.database.add_comment(
            Comment(name="func_f1",
                    filename=os.path.join(
                        HERE, 'test_sources/func/', "function.h"),
                    description="Linking to #ObjObj"))

        app.database.add_comment(
            Comment(name="ObjObj",
                    filename=os.path.join(
                        HERE, 'test_sources/obj/', "obj.h"),
                    description="Linking to #func_f1"))

        app.run()

        # Make sure that the link from the func project to the second
        # properly take into account the current language
        self.assertLinkEqual(app, "func-0.2/python/function.html", "Obj.Obj",
                             'obj-0.2/python/obj.html#ObjObj')

        self.assertLinkEqual(app, "obj-0.2/python/obj.html", 'Func.f1',
                             "func-0.2/python/function.html#func_f1")

        self.assertLinkEqual(app, "func-0.2/python/function.html", 'Obj.Obj',
                             "obj-0.2/python/obj.html#ObjObj", n_link=1)

    def test_out_arg(self):
        app = self.create_project_and_run(project_path='func')

        _html = self.get_html(app, "function.html", language='python')
        elem = _html.find(
            './/div[@id="func_out_arg"]//h4[@id="returns-a-tuple-made-of"]')
        self.assertIsNotNone(
            elem, "Out args should be documented as tuples in python")

        _html = self.get_html(app, "function.html")
        elem = _html.find(
            './/div[@id="func_out_arg"]//h4[@id="returns-a-tuple-made-of"]')
        self.assertIsNone(
            elem, "No way to return several values in C! Found :\n %s" % elem)

        elem = _html.find('.//div[@id="func_no_out_arg"]//h4[@id="returns"]')
        self.assertIsNotNone(elem, "Could not find simple return "
                             "documentation for 'func_out_arg'")

    def test_no_out_arg(self):
        app = self.create_project_and_run(project_path='func')

        def get_node(_html, id_):
            return _html.find('.//div[@id="func_no_out_arg"]//h4[@id="%s"]' % id_)

        _html = self.get_html(app, "function.html")
        elem = get_node(_html, "returns")
        self.assertIsNotNone(elem, "Could not find simple return "
                             "documentation for 'func_no_out_arg'")

        elem = get_node(_html, "returns-a-tuple-made-of")
        self.assertIsNone(elem, "No way to return several values in C!")

        _html = self.get_html(app, "function.html", language='python')
        elem = get_node(_html, "returns-a-tuple-made-of")
        self.assertIsNone(
            elem, "func_no_out_arg return one signle arg, found:\n%s" % elem)

    def test_render_structure(self):
        app = self.create_application()
        app.parse_config(self.get_config(project_path='obj',
                                         extra_conf={'languages': ['python']}))

        app.database.add_comment(
            Comment(name="ObjObj",
                    filename=os.path.join(HERE, 'test_sources/obj/', "obj.h"),
                    description="Nothing"))

        app.run()

        _html = self.get_html(app, "obj.html", language='python')
        struct_fieldnames = [i.text for i in _html.findall(
            './/div[@id="ObjObjClass"]//code')]
        self.assertEqual(struct_fieldnames,
                         ['ObjObjClass.parent:', 'ObjObjClass.a_string:', 'ObjObjClass._padding:'])

    def test_python_argument_formating(self):
        app = self.create_project_and_run(project_path='func',
                                          extra_conf={'languages': ['python']})
        func = app.database.get_symbol('func_no_out_arg')
        param = func.parameters[0]
        app.project.extensions['gi-extension'].formatter._format_parameter_symbol(param)
        self.assertTrue('*' not in param.extension_contents['type-link'],
                          param.extension_contents['type-link'])

    def test_python_const_gchar_strut_members(self):
        app = self.create_project_and_run(project_path='obj',
                                          extra_conf={'languages': ['python']})

        # const gchar * should link to unicode strings in python
        html = self.get_html(app, "Miscellaneous.html", language='python')
        link_to_a_string = html.find('.//tr[@id="ObjObjClass.a_string"]//a[@title="unicode"]')
        self.assertEqual(link_to_a_string .text, "unicode")
