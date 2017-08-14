# -*- coding: utf-8 -*-
#
# Copyright © 2017 Thibault Saunier <tsaunier@gnome.org>
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

from hotdoc.core.symbols import *

class GISymbolIface:
    def __init__(self, children):
        self._children = children or {}

    @staticmethod
    def from_tokens(type_, c_tokens, langs_tokens, **kwargs):
        children = {}
        for lang, tokens in langs_tokens.items():
            if tokens:
                if lang != 'c':
                    tokens = [tok for tok in tokens if tok not in ['*',
                                                                   'const ',
                                                                   'restrict ',
                                                                   'volatile ']]

                children[lang] = type_(type_tokens=tokens, children=None, **kwargs)

        return type_(type_tokens=c_tokens, children=children, **kwargs)

    def get_children_symbols(self):
        return self._children.values()

    def get(self, language):
        return self._children.get(language, self)


class GIQualifiedSymbol(GISymbolIface, QualifiedSymbol):
    def __init__(self, *args, **kwargs):
        GISymbolIface.__init__(self, kwargs.pop('children'))
        QualifiedSymbol.__init__(self, *args, **kwargs)


class GIReturnItemSymbol(GISymbolIface, ReturnItemSymbol):
    def __init__(self, *args, **kwargs):
        GISymbolIface.__init__(self, kwargs.pop('children'))
        ReturnItemSymbol.__init__(self, *args, **kwargs)

class GIParameterSymbol(GISymbolIface, ParameterSymbol):
    def __init__(self, *args, **kwargs):
        GISymbolIface.__init__(self, kwargs.pop('children'))
        ParameterSymbol.__init__(self, *args, **kwargs)

    def get_lang_tokens(self):
        res = {}
        for lang, child in self._children.items():
            if child.input_tokens:
                res[lang] = child.input_tokens

        return res
