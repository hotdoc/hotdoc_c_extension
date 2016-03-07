/* -*- Mode: C -*-
 * GObject introspection: C lexer
 *
 * Copyright (c) 1997 Sandro Sigala  <ssigala@globalnet.it>
 * Copyright (c) 2007-2008 Jürg Billeter  <j@bitron.ch>
 * Copyright (c) 2010 Andreas Rottmann <a.rottmann@gmx.at>
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
 * OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 * IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
 * NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
 * THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

%{
#include "scanner.h"

extern int yylex (PyObject *comments, const char *filename);
#define YY_DECL int yylex (PyObject *comments, const char *filename)
static int yywrap (void);
static void parse_comment ();
%}

%option nounput
%option yylineno

%%

"/*"              { parse_comment (comments, filename); }

.|\n		  { }

%%

static int
yywrap (void)
{
  return 1;
}

static char *
realloc_and_concat(char *str, char *s2)
{
    int len = 0;
    char *s;

    if (str != NULL)
        len = strlen(str);

    len += (strlen(s2) + 1) * sizeof(*s2);
    s = realloc(str, len);
    strcat(s, s2);
    return s;
}

#define BUFSIZE 1024

static void
parse_comment (PyObject *comments, const char *filename)
{
  int c1, c2;
  int comment_lineno;
  int cursor;

  c1 = input();
  c2 = input();

  comment_lineno = yylineno - 1;
  if (c2 != EOF && (c1 != '/' && c2 != '*' && c2 != '/')) {
    char *comment = (char *) malloc(sizeof(char) * 3);
    char buf[BUFSIZE];
    cursor = 0;

    comment[0] = '/';
    comment[1] = '*';
    comment[2] = '\0';
    while (c2 != EOF && !(c1 == '*' && c2 == '/'))
    {
      buf[cursor++] = c1;

      if (cursor >= BUFSIZE - 1) {
        buf[cursor] = 0;
        comment = realloc_and_concat (comment, buf);
        cursor = 0;
      }

      c1 = c2;
      c2 = input();
    }

    buf[cursor] = 0;
    comment = realloc_and_concat (comment, buf);
    comment = realloc_and_concat (comment, "*/");

    PyObject *item = Py_BuildValue ("(ssii)", comment,
        strdup(filename), /* Sic .. */
        comment_lineno,
        yylineno);
    PyList_Append (comments, item);
  } else {
    while (c2 != EOF && !(c1 == '*' && c2 == '/'))
    {
      c1 = c2;
      c2 = input();
    }

    return;
  }
}

int
scan_filename (const char *filename, PyObject *comments)
{
  yylineno = 1;
  yyin = fopen (filename, "r");

  yylex (comments, filename);

  fclose (yyin);

  return 0;
}
