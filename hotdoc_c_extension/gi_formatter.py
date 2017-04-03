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

import os
from hotdoc.core.formatter import Formatter
from hotdoc.core.symbols import *
import lxml.etree


class GIFormatter(Formatter):
    def __init__(self, gi_extension):
        module_path = os.path.dirname(__file__)
        searchpath = [os.path.join(module_path, "templates")]
        Formatter.__init__(self, gi_extension, searchpath)
        self._order_by_parent = True

    def format_annotations (self, annotations):
        template = self.engine.get_template('gi_annotations.html')
        return template.render ({'annotations': annotations})

    def _format_flags (self, flags):
        template = self.engine.get_template('gi_flags.html')
        out = template.render ({'flags': flags})
        return out

    def _format_type_tokens (self, type_tokens):
        if self.extension.language != 'c':
            new_tokens = []
            for tok in type_tokens:
                # FIXME : shouldn't we rather QualifiedSymbol.get_type_link() ?
                if tok not in ['*', 'const ', 'restrict ', 'volatile ']:
                    new_tokens.append (tok)
            return Formatter._format_type_tokens (self, new_tokens)
        return Formatter._format_type_tokens (self, type_tokens)

    def _format_return_value_symbol (self, *args):
        retval = args[0]
        is_void = retval[0] is None or \
                retval[0].get_extension_attribute('gi-extension',
                        'gi_name') == 'none'

        if self.extension.language == 'c':
            if is_void:
                retval = [None]
            else:
                retval = retval[:1]
        elif is_void:
            retval = retval[1:] or [None]

        return Formatter._format_return_value_symbol (self, *args)

    def _format_parameter_symbol (self, parameter):
        if self.extension.language != 'c':
            direction = parameter.get_extension_attribute ('gi-extension',
                    'direction')
            if direction == 'out':
                return (None, False)

            gi_name = parameter.get_extension_attribute ('gi-extension', 'gi_name')

            parameter.extension_contents['type-link'] = self._format_linked_symbol (parameter)
        else:
            parameter.extension_contents.pop('type-link', None)

        res = Formatter._format_parameter_symbol (self, parameter)
        return res

    def _format_linked_symbol (self, symbol):
        if self.extension.language == 'c':
            res = Formatter._format_linked_symbol (self, symbol)
            if symbol == None:
                res = 'void'
            return res

        if not isinstance (symbol, QualifiedSymbol):
            return Formatter._format_linked_symbol (self, symbol)

        gi_name = symbol.get_extension_attribute ('gi-extension', 'gi_name')

        if gi_name is None:
            return Formatter._format_linked_symbol (self, symbol)

        fund = self.extension._fundamentals.get(gi_name)
        if fund:
            link = Link(fund.ref, fund._title, gi_name)
            return self._format_type_tokens ([link])

        res = self._format_type_tokens (symbol.type_tokens)
        return res

    def _format_prototype (self, function, is_pointer, title):
        if self.extension.language == 'c':
            return Formatter._format_prototype (self, function,
                    is_pointer, title)

        params = function.get_extension_attribute ('gi-extension', 'parameters')

        if params is None:
            return Formatter._format_prototype (self, function,
                    is_pointer, title)

        c_name = function._make_name()

        if self.extension.language == 'python':
            template = self.engine.get_template('python_prototype.html')
        else:
            template = self.engine.get_template('javascript_prototype.html')

        if type (function) == SignalSymbol:
            comment = "%s callback for the '%s' signal" % (self.extension.language, c_name)
        elif type (function) == VFunctionSymbol:
            comment = "%s implementation of the '%s' virtual method" % \
                    (self.extension.language, c_name)
        else:
            comment = "%s wrapper for '%s'" % (self.extension.language,
                    c_name)

        res = template.render ({'return_value': function.return_value,
            'function_name': title, 'parameters':
            params, 'comment': comment, 'throws': function.throws,
            'out_params': [], 'is_method': function.is_method})

        return res

    def _format_gi_vmethod (self, vmethod):
        title = vmethod.link.title
        if self.extension.language == 'python':
            vmethod.link.title = 'do_%s' % vmethod._make_name()
            title = 'do_%s' % title
        elif self.extension.language == 'javascript':
            vmethod.link.title = '%s::%s' % (vmethod.gi_parent_name, vmethod._make_name())
            title = 'vfunc_%s' % title
        return self._format_callable (vmethod, "virtual method",
                title)

    def _format_struct (self, struct,):
        if self.extension.language == 'c':
            return Formatter._format_struct (self, struct)
        members_list = self._format_members_list (struct.members, 'Attributes',
                                                  struct)

        template = self.engine.get_template ("python_compound.html")
        out = template.render ({"symbol": struct,
                                "members_list": members_list})
        return (out, False)

    def _format_constant(self, constant):
        if self.extension.language == 'c':
            return Formatter._format_constant (self, constant)

        template = self.engine.get_template('constant.html')
        out = template.render ({'symbol': constant,
                                'definition': None,
                                'constant': constant})
        return (out, False)

    def _format_comment(self, comment, link_resolver):
        ast = comment.extension_attrs['gi-extension']['ast']

        if not comment.description:
            out = u''
        elif ast:
            out = self._docstring_formatter.ast_to_html(
                ast, link_resolver)
        else:
            ast = self._docstring_formatter.comment_to_ast(
                comment, link_resolver)
            out = self._docstring_formatter.ast_to_html(
                ast, link_resolver)
            comment.extension_attrs['gi-extension']['ast'] = ast

        return out

    def get_output_folder(self, page):
        lang_path = self.extension.language or self.extension.languages[0]
        return os.path.join(super().get_output_folder(page), lang_path)

    def patch_page(self, page, symbol, output):
        symbol.update_children_comments()
        for l in self.extension.languages:
            self.extension.setup_language (l)
            self.format_symbol(symbol, self.extension.app.resolver)

            parser = lxml.etree.XMLParser(encoding='utf-8', recover=True)
            page_path = os.path.join(output, l, page.link.ref)
            tree = lxml.etree.parse(page_path, parser)
            root = tree.getroot()
            elems = root.findall('.//div[@id="%s"]' % symbol.unique_name)
            for elem in elems:
                parent = elem.getparent()
                new_elem = lxml.etree.fromstring(symbol.detailed_description)
                parent.replace (elem, new_elem)

            with open(page_path, 'w') as f:
                tree.write_c14n(f)

        self.extension.setup_language(None)
