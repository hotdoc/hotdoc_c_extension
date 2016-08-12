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

from pkg_resources import parse_version as V
from setuptools import setup, find_packages
from distutils.core import Extension
from distutils.errors import DistutilsExecError
from distutils.dep_util import newer_group
from distutils.spawn import spawn
from distutils.command.build_ext import build_ext as _build_ext

from hotdoc_c_extension.utils.setup_utils import VersionList

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
                raise DistutilsExecError,\
                        ("Make sure flex is installed on your system")

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

known_clang_versions = VersionList([V('3.2'), V('3.3'), V('3.4'), V('3.5'), V('3.7')])

try:
    clang_version = subprocess.check_output(['llvm-config', '--version'])
except OSError as e:
    print "Error when trying to figure out the clang version"
    print "llvm-config is probably not installed\n"
    raise e
except subprocess.CalledProcessError as e:
    print "\nUnknown error when trying to figure out the clang version\n"
    raise e

try:
    clang_bindings_version = known_clang_versions.find_le(V(clang_version))
except ValueError as e:
    print "No bindings found for clang version %s" % clang_version
    raise e

if clang_bindings_version == V('3.7'):
    clang_bindings_version = V('3.7.dev234765')

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
        'hotdoc_c_extension': ['VERSION.txt'],
    },
    entry_points = {'hotdoc.extensions': 'get_extension_classes = hotdoc_c_extension.c_extension:get_extension_classes'},
    cmdclass = {'build_ext': build_ext},
    ext_modules = [c_comment_scanner_module],
    install_requires = [
        'clang==%s' % str(clang_bindings_version),
        'pkgconfig==1.1.0',
    ]
)
