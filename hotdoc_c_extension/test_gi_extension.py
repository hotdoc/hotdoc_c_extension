import os
import copy

from collections import OrderedDict
from lxml import etree

from hotdoc.tests.fixtures import HotdocTest
from hotdoc.core.config import Config
from hotdoc.core.comment import Comment
from hotdoc_c_extension.gi_extension import GIExtension, DEFAULT_PAGE

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

    def get_config(self, sitemap_content='gi-index', project_path=''):
        return Config(conf_file=self.get_config_file(sitemap_content,
                                                     project_path=project_path))

    def get_config_file(self, sitemap_content='gi-index', project_path='test'):
        return self._create_project_config_file(
            project_path, sitemap_content=sitemap_content,
            extra_conf={'gi_sources': [self.get_gir(project_path=project_path)],
                        'gi_c_sources': self.get_sources(project_path=project_path),
                        'gi_smart_index': True})

    def build_tree(self, pages, page, node):

        pnode = OrderedDict()
        symbols = []

        for symbol in page.symbols:
            symbols.append(
                OrderedDict({'name': symbol.unique_name,
                 'parent_name': symbol.parent_name}))
        pnode['symbols'] = symbols

        subpages = OrderedDict({})
        for pname in page.subpages:
            subpage = pages[pname]
            self.build_tree(pages, subpage, subpages)

        pnode['subpages'] = subpages
        node[page.source_file] = pnode


    def create_project_and_run(self, project_path='test'):
        app = self.create_application()
        config = self.get_config(project_path=project_path)

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
        config = self.get_config(sitemap_content='gi-index\n	test-gobject-macros.h')

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
            9999, OrderedDict({'name': 'TestUndocumentedFlag', 'parent_name': None}))
        if os.environ.get('PRINT_STRUCTURE'):
            import pprint
            pprint.pprint(structure)
        self.assertDictEqual(structure, nstructure)

    def test_getting_link_for_lang(self):
        app = self.create_project_and_run()
        project = app.project
        tree = project.tree
        pages = tree.get_pages()

        root_subpages = list(project.tree.root.subpages)
        page = pages[root_subpages[0]]
        symbol = page.symbols[0]

        self.assertEqual(symbol.unique_name, 'TEST_GREETER_VERSION')

        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['c/test-greeter.html#TEST_GREETER_VERSION'])

        gi_ext = project.extensions[page.extension_name]

        gi_ext.setup_language('python')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['python/test-greeter.html#TEST_GREETER_VERSION'])

        gi_ext.setup_language('javascript')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['javascript/test-greeter.html#TEST_GREETER_VERSION'])

    def test_getting_link_for_lang_with_subproject(self):
        app = self.create_application()

        content = 'project.markdown\n\ttest.json'
        config = self._create_project_config('project', sitemap_content=content)
        self.get_config_file()

        app.parse_config(config)
        app.run()

        project = app.project.subprojects['test.json']
        root_subpages = list(project.tree.root.subpages)
        tree = project.tree
        pages = tree.get_pages()
        page = pages[root_subpages[0]]
        symbol = page.symbols[0]

        self.assertEqual(symbol.unique_name, 'TEST_GREETER_VERSION')

        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['test-0.2/c/test-greeter.html#TEST_GREETER_VERSION'])

        gi_ext = project.extensions[page.extension_name]

        gi_ext.setup_language('python')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['test-0.2/python/test-greeter.html#TEST_GREETER_VERSION'])

        gi_ext.setup_language('javascript')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['test-0.2/javascript/test-greeter.html#TEST_GREETER_VERSION'])

    def test_getting_link_from_overriden_page(self):
        self._create_md_file(
            'test-greeter.h.markdown',
            (u'# Greeter override\n'))
        app = self.create_project_and_run()
        project = app.project
        tree = project.tree
        pages = tree.get_pages()

        root_subpages = list(project.tree.root.subpages)
        page = pages[root_subpages[0]]
        symbol = page.symbols[0]

        self.assertEqual(symbol.unique_name, 'TEST_GREETER_VERSION')

        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['c/test-greeter-h.html#TEST_GREETER_VERSION'])

        gi_ext = project.extensions[page.extension_name]

        gi_ext.setup_language('python')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['python/test-greeter-h.html#TEST_GREETER_VERSION'])

        gi_ext.setup_language('javascript')
        res = app.link_resolver.resolving_link_signal(symbol.link)
        self.assertEqual(res, ['javascript/test-greeter-h.html#TEST_GREETER_VERSION'])

    def test_link_for_lang_in_another_project(self):
        app = self.create_application()
        self.get_config_file(project_path='obj')

        index_content = "# test_link_for_lang_in_another_project"
        index_path = self._create_md_file('index.md', index_content)

        self.get_config_file(project_path='func')

        content = 'project.markdown\n\tfunc.json\n\tobj.json'
        config = self._create_project_config('project', sitemap_content=content)
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
        with open(os.path.join(app.output, "html", "func-0.2/python/function.html"),
                  'r') as _:
            funchtml = etree.HTML(_.read())
        link = [a for a in funchtml.findall('.//a') if a.text == "Obj.Obj"][0]
        self.assertEqual(link.attrib['href'], 'obj-0.2/python/obj.html#ObjObj')

        with open(os.path.join(app.output, "html", "obj-0.2/python/obj.html"),
                  'r') as _:
            funchtml = etree.HTML(_.read())

        link = [a for a in funchtml.findall('.//a') if a.text == 'Func.f1'][0]
        self.assertEqual(link.attrib['href'], "func-0.2/python/function.html#func_f1")
