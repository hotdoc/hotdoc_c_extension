import cchardet
from ..c_comment_scanner.c_comment_scanner import extract_comments

from hotdoc.core.symbols import *
from hotdoc.utils.loggable import debug


def unicode_dammit(data):
    encoding = cchardet.detect(data)['encoding']
    return data.decode(encoding, errors='replace')


class CCommentExtractor:
    def __init__(self, extension, comment_parser):
        self.extension = extension
        self.app = extension.app
        self.project = extension.project
        self.__raw_comment_parser = comment_parser

    def parse_comments(self, filenames):
        for filename in filenames:
            with open (filename, 'rb') as f:
                debug('Getting comments in %s' % filename)
                lines = []
                header = filename.endswith('.h')
                skip_next_symbol = header
                # FIXME Use the lexer for that!
                for l in f.readlines():
                    l = unicode_dammit(l)
                    lines.append(l)
                    if skip_next_symbol and l.startswith("#pragma once"):
                        skip_next_symbol = False

                cs = extract_comments (''.join(lines))
                for c in cs:
                    if c[3]:
                        line = lines[c[1] - 1]

                        comment = (len(line) - len(line.lstrip(' '))) * ' ' + c[0]
                        block = self.__raw_comment_parser.parse_comment(comment,
                            filename, c[1], c[2], self.project.include_paths)
                        if block is not None:
                            self.app.database.add_comment(block)
                    elif not skip_next_symbol:
                        if header:
                            self.__create_macro_from_raw_text(c, filename)
                    else:
                        skip_next_symbol = False

    def __create_macro_from_raw_text(self, raw, filename):
        mcontent = raw[0].replace('\t', ' ')
        mcontent = mcontent.split(' ', 1)[1]
        split = mcontent.split('(', 1)
        name = split[0]
        if not (' ' in name or '\t' in name) and len(split) == 2:
            args = split[1].split(')', 1)[0].split(',')
            if args:
                stripped_name = name.strip()
                return self.__create_function_macro_symbol(stripped_name,
                    filename, raw[1], raw[0])

        name = mcontent.split(' ', 1)[0]
        stripped_name = name.strip()
        return self.__create_constant_symbol(stripped_name, filename, raw[1], raw[0])

    def __create_function_macro_symbol (self, name, filename, lineno, original_text):
        comment = self.app.database.get_comment(name)

        return_value = [None]
        if comment:
            return_tag = comment.tags.get ('returns')
            if return_tag:
                return_value = [ReturnItemSymbol ()]
                return_value[0].add_extension_attribute ('gi-extension', 'owner_name', name)

        parameters = []

        if comment:
            for param_name in comment.params:
                parameter = ParameterSymbol (argname=param_name)
                parameter.add_extension_attribute ('gi-extension', 'owner_name', name)
                parameters.append (parameter)

        sym = self.extension.get_or_create_symbol(
            FunctionMacroSymbol, return_value=return_value,
            parameters=parameters, original_text=original_text,
            display_name=name, filename=filename, lineno=lineno)

        return sym

    def __create_constant_symbol (self, name, filename, lineno, original_text):
        return self.extension.get_or_create_symbol(ConstantSymbol,
                original_text=original_text,
                display_name=name, filename=filename,
                lineno=lineno)
