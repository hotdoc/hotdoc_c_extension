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

import os, sys, linecache, pkgconfig, glob, subprocess

from hotdoc_c_extension.clang import cindex
from ctypes import *
from fnmatch import fnmatch

from hotdoc.core import file_includer
from hotdoc.core.base_extension import BaseExtension
from hotdoc.core.exceptions import ParsingException, BadInclusionException, HotdocException
from hotdoc.core.symbols import *
from hotdoc.core.comment_block import comment_from_tag
from hotdoc.core.links import Link

from hotdoc.parsers.gtk_doc_parser import GtkDocParser

from hotdoc.utils.loggable import (info as core_info, warn, Logger,
    debug as core_debug)

from .c_comment_scanner.c_comment_scanner import get_comments
from .c_html_formatter import CHtmlFormatter

def ast_node_is_function_pointer (ast_node):
    if ast_node.kind == cindex.TypeKind.POINTER and \
            ast_node.get_pointee().get_result().kind != \
            cindex.TypeKind.INVALID:
        return True
    return False


def info(message):
    core_info(message, domain='c-extension')


def debug(message):
    core_debug(message, domain='c-extension')


Logger.register_warning_code('clang-diagnostic', ParsingException,
                             'c-extension')
Logger.register_warning_code('clang-heisenbug', ParsingException,
                             'c-extension')
Logger.register_warning_code('clang-flags', ParsingException,
                             'c-extension')
Logger.register_warning_code('bad-c-inclusion', BadInclusionException,
                             'c-extension')
Logger.register_warning_code('clang-headers-not-found', HotdocException,
                             'c-extension')


CLANG_HEADERS_WARNING = (
'Did not find clang headers. Please report a bug with the output of the'
'\'llvm-config --version\' and \'llvm-config --prefix\' commands')


def get_clang_headers():
    version = subprocess.check_output(['llvm-config', '--version']).strip().decode()
    prefix = subprocess.check_output(['llvm-config', '--prefix']).strip().decode()

    for lib in ['lib', 'lib64']:
        p = os.path.join(prefix, lib, 'clang', version, 'include')
        if os.path.exists(p):
            return p

    warn('clang-headers-not-found', CLANG_HEADERS_WARNING)

def get_clang_libdir():
    return subprocess.check_output(['llvm-config', '--libdir']).strip().decode()

class ClangScanner(object):
    def __init__(self, doc_repo, doc_db):
        if not cindex.Config.loaded:
            # Let's try and find clang ourselves first
            clang_libdir = get_clang_libdir()
            if os.path.exists(clang_libdir):
                cindex.Config.set_library_path(clang_libdir)
            cindex.Config.set_compatibility_check(False)

        self.__raw_comment_parser = GtkDocParser(doc_repo)
        self.doc_repo = doc_repo
        self.__doc_db = doc_db

    def scan(self, filenames, options, incremental, full_scan,
             full_scan_patterns, fail_fast=False):
        index = cindex.Index.create()
        flags = cindex.TranslationUnit.PARSE_INCOMPLETE | cindex.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD

        info('scanning %d C source files' % len(filenames))
        self.filenames = filenames

        # FIXME: er maybe don't do that ?
        args = ["-Wno-attributes"]
        args.append ("-isystem%s" % get_clang_headers())
        args.extend (options)
        self.symbols = {}
        self.parsed = set({})

        debug('CFLAGS %s' % ' '.join(args))

        header_guarded = set()

        for filename in self.filenames:
            if filename in self.parsed:
                continue

            do_full_scan = any(fnmatch(filename, p) for p in full_scan_patterns)
            if do_full_scan:
                debug('scanning %s' % filename)

                tu = index.parse(filename, args=args, options=flags)

                for diag in tu.diagnostics:
                    s = diag.format()
                    warn('clang-diagnostic', 'Clang issue : %s' % str(diag))

                self.__parse_file (filename, tu, full_scan)
                if (cindex.conf.lib.clang_isFileMultipleIncludeGuarded(tu, tu.get_file(filename))):
                    header_guarded.add(filename)

                for include in tu.get_includes():
                    fname = os.path.abspath(str(include.include))
                    if (cindex.conf.lib.clang_isFileMultipleIncludeGuarded(tu, tu.get_file(fname))):
                        if fname in self.filenames:
                            header_guarded.add(fname)
                    self.__parse_file (fname, tu, full_scan)

        if not full_scan:
            for filename in filenames:
                with open (filename, 'r') as f:
                    skip_next_symbol = filename in header_guarded
                    debug('Getting comments in %s' % filename)
                    cs = get_comments (filename)
                    for c in cs:
                        if c[4]:
                            block = self.__raw_comment_parser.parse_comment(c[0],
                                c[1], c[2], c[3], self.doc_repo.include_paths)
                            if block is not None:
                                self.doc_repo.doc_database.add_comment(block)
                        elif not skip_next_symbol:
                            if filename.endswith('.h'):
                                self.__create_macro_from_raw_text(c)
                        else:
                            skip_next_symbol = False

        return True

    def set_extension(self, extension):
        self.__doc_db = extension

    def __parse_file (self, filename, tu, full_scan):
        if filename in self.parsed:
            return

        self.parsed.add (filename)

        if filename not in self.filenames:
            return

        debug('scanning %s' % filename)

        start = tu.get_location (filename, 0)
        end = tu.get_location (filename, int(os.path.getsize(filename)))
        extent = cindex.SourceRange.from_locations (start, end)
        cursors = self.__get_cursors(tu, extent)

        # Happens with empty source files
        if cursors is None:
            return

        if filename in self.filenames:
            self.__create_symbols (cursors, tu)

    # That's the fastest way of obtaining our ast nodes for a given filename
    def __get_cursors (self, tu, extent):
        tokens_memory = POINTER(cindex.Token)()
        tokens_count = c_uint()

        cindex.conf.lib.clang_tokenize(tu, extent, byref(tokens_memory),
                byref(tokens_count))

        count = int(tokens_count.value)

        if count < 1:
            return

        cursors = (cindex.Cursor * count)()
        cindex.conf.lib.clang_annotateTokens (tu, tokens_memory, tokens_count,
                cursors)

        return cursors

    def __create_symbols(self, nodes, tu):
        for node in nodes:
            node._tu = tu

            # This is dubious, needed to parse G_DECLARE_FINAL_TYPE
            # investigate further (fortunately this doesn't seem to
            # significantly impact performance ( ~ 5% )
            if node.kind == cindex.CursorKind.TYPE_REF:
                node = node.get_definition()
                if not node:
                    continue

                if not str(node.location.file) in self.filenames:
                    continue

            if node.spelling in self.symbols:
                continue

            sym = None
            func_dec = self.__getFunctionDeclNode(node)
            if func_dec and func_dec.spelling not in self.symbols:
                sym = self.__create_function_symbol(func_dec)
            elif node.kind == cindex.CursorKind.VAR_DECL:
                sym = self.__create_exported_variable_symbol (node)
            elif node.kind == cindex.CursorKind.TYPEDEF_DECL:
                sym = self.__create_typedef_symbol (node)
            elif node.kind == cindex.CursorKind.STRUCT_DECL and node.spelling:
                sym = self.__create_struct_symbol(node)
            elif node.kind == cindex.CursorKind.ENUM_DECL and node.spelling:
                sym = self.__create_enum_symbol(node)

            if sym is not None:
                self.symbols[sym.unique_name] = sym
            self.__create_symbols(node.get_children(), tu)

    def __getFunctionDeclNode(self, node):
        if not node.location.file:
            return None
        elif node.location.file.name.endswith(".h"):
            if node.kind == cindex.CursorKind.FUNCTION_DECL:
                return node
            else:
                return None

        if node.kind != cindex.CursorKind.COMPOUND_STMT:
            return None

        if node.semantic_parent.kind == cindex.CursorKind.FUNCTION_DECL:
            return node.semantic_parent

        return None

    def __apply_qualifiers (self, type_, tokens):
        if type_.is_const_qualified():
            tokens.append ('const ')
        if type_.is_restrict_qualified():
            tokens.append ('restrict ')
        if type_.is_volatile_qualified():
            tokens.append ('volatile ')

    def make_c_style_type_name (self, type_):
        tokens = []
        while (type_.kind == cindex.TypeKind.POINTER):
            self.__apply_qualifiers(type_, tokens)
            tokens.append ('*')
            type_ = type_.get_pointee()

        if type_.kind == cindex.TypeKind.TYPEDEF:
            d = type_.get_declaration ()
            link = Link (None, d.displayname, d.displayname)

            tokens.append (link)
            self.__apply_qualifiers(type_, tokens)
        elif type_.kind == cindex.TypeKind.UNEXPOSED:
            d = type_.get_declaration()
            if d.spelling:
                tokens.append(Link(None, d.displayname, d.displayname))
            else:
                tokens.append('__UNKNOWN__')
            if d.kind == cindex.CursorKind.STRUCT_DECL:
                tokens.append ('struct ')
            elif d.kind == cindex.CursorKind.ENUM_DECL:
                tokens.append ('enum ')
        else:
            tokens.append (type_.spelling + ' ')

        tokens.reverse()
        return tokens

    def __create_callback_symbol (self, node):
        parameters = []

        return_value = None

        for child in node.get_children():
            if not return_value:
                t = node.underlying_typedef_type
                res = t.get_pointee().get_result()
                type_tokens = self.make_c_style_type_name (res)
                return_value = [ReturnItemSymbol(type_tokens=type_tokens)]
            else:
                type_tokens = self.make_c_style_type_name (child.type)
                parameter = ParameterSymbol (argname=child.displayname,
                        type_tokens=type_tokens)
                parameters.append (parameter)

        if not return_value:
            return_value = [ReturnItemSymbol(type_tokens=[])]

        sym = self.__doc_db.get_or_create_symbol(CallbackSymbol, parameters=parameters,
                return_value=return_value, display_name=node.spelling,
                filename=str(node.location.file), lineno=node.location.line)
        return sym

    def __parse_public_fields (self, decl):
        tokens = decl.translation_unit.get_tokens(extent=decl.extent)
        delimiters = []

        filename = str(decl.location.file)

        start = decl.extent.start.line
        end = decl.extent.end.line + 1
        original_lines = [linecache.getline(filename, i).rstrip() for i in range(start,
            end)]

        public = True
        if (self.__locate_delimiters(tokens, delimiters)):
            public = False

        children = []
        for child in decl.get_children():
            children.append(child)

        delimiters.reverse()
        if not delimiters:
            return '\n'.join (original_lines), children

        public_children = []
        children = []
        for child in decl.get_children():
            children.append(child)
        children.reverse()
        if children:
            next_child = children.pop()
        else:
            next_child = None
        next_delimiter = delimiters.pop()

        final_text = []

        found_first_child = False

        for i, line in enumerate(original_lines):
            lineno = i + start
            if next_delimiter and lineno == next_delimiter[1]:
                public = next_delimiter[0]
                if delimiters:
                    next_delimiter = delimiters.pop()
                else:
                    next_delimiter = None
                continue

            if not next_child or lineno < next_child.location.line:
                if public or not found_first_child:
                    final_text.append (line)
                continue

            if lineno == next_child.location.line:
                found_first_child = True
                if public:
                    final_text.append (line)
                    public_children.append (next_child)
                while next_child.location.line == lineno:
                    if not children:
                        public = True
                        next_child = None
                        break
                    next_child = children.pop()

        return ('\n'.join(final_text), public_children)

    def __locate_delimiters (self, tokens, delimiters):
        public_pattern = "/*<public>*/"
        private_pattern = "/*<private>*/"
        protected_pattern = "/*<protected>*/"
        had_public = False
        for tok in tokens:
            if tok.kind == cindex.TokenKind.COMMENT:
                comment = ''.join(tok.spelling.split())
                if public_pattern == comment:
                    had_public = True
                    delimiters.append((True, tok.location.line))
                elif private_pattern == comment:
                    delimiters.append((False, tok.location.line))
                elif protected_pattern == comment:
                    delimiters.append((False, tok.location.line))
        return had_public

    def __create_struct_symbol (self, node, spelling=None):
        spelling = spelling or node.spelling
        raw_text, public_fields = self.__parse_public_fields (node)
        members = []
        for field in public_fields:
            type_tokens = self.make_c_style_type_name (field.type)
            is_function_pointer = ast_node_is_function_pointer (field.type)
            qtype = QualifiedSymbol(type_tokens=type_tokens)
            name = '%s.%s' % (spelling, field.spelling)
            member = self.__doc_db.get_or_create_symbol(FieldSymbol, is_function_pointer=is_function_pointer,
                    member_name=field.spelling, qtype=qtype, filename=str(node.location.file),
                    display_name=name, unique_name=name)
            members.append (member)

        if not public_fields:
            raw_text = None

        anonymous = not node.spelling

        return self.__doc_db.get_or_create_symbol(StructSymbol, raw_text=raw_text,
                members=members, anonymous=anonymous,
                display_name=spelling,
                filename=str(node.location.file), lineno=node.location.line)

    def __create_enum_symbol (self, node, spelling=None):
        spelling = spelling or node.spelling
        members = []
        for member in node.get_children():
            member_value = member.enum_value
            # FIXME: this is pretty much a macro symbol ?
            member = self.__doc_db.get_or_create_symbol(Symbol, display_name=member.spelling,
                    filename=str(member.location.file),
                    lineno=member.location.line)
            member.enum_value = member_value
            members.append (member)

        anonymous = not node.spelling

        start = node.extent.start.line
        end = node.extent.end.line + 1
        original_lines = [linecache.getline(str(node.location.file), i).rstrip() for i in range(start,
            end)]
        raw_text = '\n'.join(original_lines)

        return self.__doc_db.get_or_create_symbol(EnumSymbol, members=members,
                anonymous=anonymous, raw_text=raw_text, display_name=spelling,
                filename=str(node.location.file), lineno=node.location.line)

    def __create_alias_symbol (self, node):
        type_tokens = self.make_c_style_type_name(node.underlying_typedef_type)
        aliased_type = QualifiedSymbol (type_tokens=type_tokens)
        return self.__doc_db.get_or_create_symbol(AliasSymbol, aliased_type=aliased_type,
                display_name=node.spelling, filename=str(node.location.file),
                lineno=node.location.line)

    def __create_typedef_symbol (self, node):
        t = node.underlying_typedef_type
        decl = t.get_declaration()
        if ast_node_is_function_pointer (t):
            sym = self.__create_callback_symbol (node)
        elif not decl.spelling and decl.kind == cindex.CursorKind.STRUCT_DECL: # typedef struct {} foo;
            sym = self.__create_struct_symbol (decl, spelling=node.spelling)
        elif not decl.spelling and decl.kind == cindex.CursorKind.ENUM_DECL: # typedef enum {} bar;
            sym = self.__create_enum_symbol (decl, spelling=node.spelling)
        else:
            sym = self.__create_alias_symbol (node)

        return sym

    def __create_macro_from_raw_text(self, raw):
        mcontent = raw[0].replace('\t', ' ')
        mcontent = mcontent.split(' ', 1)[1]
        split = mcontent.split('(', 1)
        name = split[0]
        if not (' ' in name or '\t' in name) and len(split) == 2:
            args = split[1].split(')', 1)[0].split(',')
            if args:
                stripped_name = name.strip()
                return self.__create_function_macro_symbol(stripped_name,
                    raw[1], raw[2], raw[0])

        name = mcontent.split(' ', 1)[0]
        stripped_name = name.strip()
        return self.__create_constant_symbol(stripped_name, raw[1], raw[2], raw[0])

    def __create_function_macro_symbol (self, name, filename, lineno, original_text):
        comment = self.doc_repo.doc_database.get_comment(name)

        return_value = [None]
        if comment:
            return_tag = comment.tags.get ('returns')
            if return_tag:
                return_value = [ReturnItemSymbol ()]

        parameters = []

        if comment:
            for param_name in comment.params:
                parameter = ParameterSymbol (argname=param_name)
                parameters.append (parameter)

        sym = self.__doc_db.get_or_create_symbol(FunctionMacroSymbol, return_value=return_value,
                parameters=parameters, original_text=original_text,
                display_name=name,
                filename=filename, lineno=lineno)
        return sym

    def __create_constant_symbol (self, name, filename, lineno, original_text):
        return self.__doc_db.get_or_create_symbol(ConstantSymbol,
                original_text=original_text,
                display_name=name, filename=filename,
                lineno=lineno)

    def __create_function_symbol (self, node):
        parameters = []

        type_tokens = self.make_c_style_type_name (node.result_type)
        return_value = [ReturnItemSymbol (type_tokens=type_tokens)]

        for param in node.get_arguments():
            type_tokens = self.make_c_style_type_name (param.type)
            parameter = ParameterSymbol (argname=param.displayname,
                    type_tokens=type_tokens)
            parameters.append (parameter)

        sym = self.__doc_db.get_or_create_symbol(FunctionSymbol, parameters=parameters,
                return_value=return_value, display_name=node.spelling,
                filename=str(node.location.file), lineno=node.location.line,
                extent_start=node.extent.start.line,
                extent_end=node.extent.end.line)

        return sym

    def __create_exported_variable_symbol (self, node):
        l = linecache.getline (str(node.location.file), node.location.line)
        split = l.split()

        start = node.extent.start.line
        end = node.extent.end.line + 1
        filename = str(node.location.file)
        original_lines = [linecache.getline(filename, i).rstrip() for i in range(start,
            end)]
        original_text = '\n'.join(original_lines)

        type_tokens = self.make_c_style_type_name(node.type)
        type_qs = QualifiedSymbol(type_tokens=type_tokens)

        sym = self.__doc_db.get_or_create_symbol(ExportedVariableSymbol, original_text=original_text,
                display_name=node.spelling, filename=str(node.location.file),
                lineno=node.location.line, type_qs=type_qs)
        return sym


def flags_from_config(config, path_resolver):
    flags = []

    for package in config.get('pkg_config_packages') or []:
        flags.extend(pkgconfig.cflags(package).split(' '))

    extra_flags = config.get('extra_c_flags') or []
    for flag in extra_flags:
        flags.extend([f for f in flag.split()])

    return flags

DESCRIPTION =\
"""
Parse C source files to extract comments and symbols.
"""


class CExtension(BaseExtension):
    extension_name = 'c-extension'
    argument_prefix = 'c'
    flags = None

    def __init__(self, doc_repo):
        BaseExtension.__init__(self, doc_repo)
        self.doc_repo = doc_repo
        file_includer.include_signal.connect(self.__include_file_cb)
        self.scanner = ClangScanner(self.doc_repo, self)
        self.formatters = {'html': CHtmlFormatter()}

    # pylint: disable=no-self-use
    def __include_file_cb(self, include_path, line_ranges, symbol_name):
        if not include_path.endswith(".c") or not symbol_name:
            return None

        if not line_ranges:
            line_ranges = [(1, -1)]
        symbol = self.doc_repo.doc_database.get_symbol(symbol_name)
        if symbol and symbol.filename != include_path:
            symbol = None

        if not symbol:
            scanner = ClangScanner(self.doc_repo, self)
            scanner.scan([include_path], CExtension.flags,
                         self.doc_repo.incremental, True, ['*.c', '*.h'])
            symbol = self.doc_repo.doc_database.get_symbol(symbol_name)

            if not symbol:
                warn('bad-c-inclusion',
                     "Trying to include symbol %s but could not be found in "
                     "%s" % (symbol_name, include_path))
                return None

        res = ''
        for n, (start, end) in enumerate(line_ranges):
            if n != 0:
                res += "\n...\n"

            start += symbol.extent_start - 2
            if end > 0:
                end += (symbol.extent_start - 1)  # We are inclusive here
            else:
                end = symbol.extent_end

            with open(include_path, "r") as _:
                res += "\n".join(_.read().split("\n")[start:end])

        if res:
            return res, 'c'

        return None

    def _get_smart_index_title(self):
        return 'C API Reference'

    def get_or_create_symbol(self, *args, **kwargs):
        kwargs['language'] = 'c'
        return super(CExtension, self).get_or_create_symbol(*args, **kwargs)

    def setup(self):
        stale, unlisted = self.get_stale_files(CExtension.sources)
        self.scanner.scan(stale, CExtension.flags,
                          self.doc_repo.incremental, False, ['*.h'])

    @staticmethod
    def add_arguments (parser):
        group = parser.add_argument_group('C extension', DESCRIPTION)
        CExtension.add_index_argument(group)
        CExtension.add_sources_argument(group)
        CExtension.add_paths_argument(group, "include-directories",
                help_="List extra include directories here")
        group.add_argument ("--pkg-config-packages", action="store", nargs="+",
                dest="pkg_config_packages", help="Packages the library depends upon")
        group.add_argument ("--extra-c-flags", action="store", nargs="+",
                dest="extra_c_flags", help="Extra C flags (-D, -U, ..)")

    @staticmethod
    def parse_config(doc_repo, config):
        CExtension.parse_standard_config(config)
        CExtension.flags = flags_from_config(config, doc_repo)
        for dir_ in CExtension.include_directories:
            CExtension.flags.append('-I%s' % dir_)
