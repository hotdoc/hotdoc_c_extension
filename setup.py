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

import os, subprocess

from setuptools import setup, find_packages
from distutils.core import Extension
from distutils.errors import DistutilsExecError
from distutils.dep_util import newer_group
from distutils.spawn import spawn
from distutils.command.build_ext import build_ext as _build_ext

source_dir = os.path.abspath('./')
def src(filename):
    return os.path.join(source_dir, filename)


class FlexExtension (Extension):
    def __init__(self, flex_sources, *args, **kwargs):
        Extension.__init__(self, *args, **kwargs)
        self.__flex_sources = [src(s) for s in flex_sources]

    def __build_flex(self):
        src_dir = os.path.dirname (self.__flex_sources[0])
        built_scanner_path = src(os.path.join (src_dir, 'scanner.c'))

        self.sources.append(built_scanner_path)
        if newer_group(self.__flex_sources, built_scanner_path):
            cmd = ['flex', '-o', built_scanner_path]
            for s in self.__flex_sources:
                cmd.append (s)
            try:
                spawn(cmd, verbose=1)
            except DistutilsExecError:
                raise DistutilsExecError(("Make sure flex is installed on your system"))

    def build_custom (self, build_path):
        if self.__flex_sources:
            self.__build_flex()


class build_ext(_build_ext):
    def run(self):
        for extension in self.extensions:
            build_path = None
            for output in self.get_outputs():
                name = os.path.splitext(os.path.basename (output))[0]
                if extension.name.endswith(name):
                    build_path = os.path.dirname(output)

            if hasattr (extension, 'build_custom'):
                extension.build_custom (build_path)

        _build_ext.run(self)
        return True


c_comment_scanner_module = FlexExtension(
                            ['hotdoc_c_extension/c_comment_scanner/scanner.l'],
                            'hotdoc_c_extension.c_comment_scanner.c_comment_scanner',
                            sources =
                            ['hotdoc_c_extension/c_comment_scanner/scannermodule.c'],
                            depends =
                            ['hotdoc_c_extension/c_comment_scanner/scanner.l',
                            'hotdoc_c_extension/c_comment_scanner/scanner.h'])

with open(os.path.join('hotdoc_c_extension', 'VERSION.txt'), 'r') as _:
    VERSION = _.read().strip()

setup(
    name = "hotdoc_c_extension",
    version = VERSION,
    keywords = "C clang hotdoc",
    url='https://github.com/hotdoc/hotdoc_c_extension',
    author_email = 'mathieu.duponchelle@opencreed.com',
    license = 'LGPLv2.1+',
    description = "An extension for hotdoc that parses C using clang",
    author = "Mathieu Duponchelle",
    packages = find_packages(),
    package_data = {
        '': ['*.html'],
        'hotdoc_c_extension': ['VERSION.txt'],
        'hotdoc_c_extension.transition_scripts': ['translate_sections.sh'],
    },
    entry_points = {'hotdoc.extensions': 'get_extension_classes = hotdoc_c_extension.extensions:get_extension_classes'},
    scripts=['hotdoc_c_extension/transition_scripts/hotdoc_gtk_doc_porter',
             'hotdoc_c_extension/transition_scripts/hotdoc_gtk_doc_scan_parser'],
    cmdclass = {'build_ext': build_ext},
    ext_modules = [c_comment_scanner_module],
    install_requires = [
        'pkgconfig==1.1.0',
    ]
)
