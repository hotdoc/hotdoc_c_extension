# -*- coding: utf-8 -*-
#
# Copyright © 2016 Mathieu Duponchelle <mathieu.duponchelle@opencreed.com>
# Copyright © 2016 Collabora Ltd
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

from hotdoc.core.formatter import Formatter
from hotdoc.parsers.gtk_doc_parser import GtkDocStringFormatter


class CFormatter(Formatter):
    def __init__(self):
        Formatter.__init__(self, [])
        self._docstring_formatter = GtkDocStringFormatter()

    def _format_comment(self, comment, link_resolver):
        return self._docstring_formatter.translate_comment(
            comment, link_resolver, 'html')
