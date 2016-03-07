/*
 * Hotdoc python extension for fast retrieval of C code comments.
 *
 * Copyright 2015 Mathieu Duponchelle <mathieu.duponchelle@opencredd.com>
 * Copyright 2015 Collabora Ltd.
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301 USA
 */

#include "scanner.h"

static PyObject *
scanner_get_comments (PyObject *self, PyObject *args)
{
  const char *filename;
  PyObject *list;

  if (!PyArg_ParseTuple(args, "s", &filename))
    return NULL;

  list = PyList_New (0);
  scan_filename (filename, list);

  Py_INCREF (list);
  return list;
}

static PyMethodDef ScannerMethods[] = {
  {"get_comments",  scanner_get_comments, METH_VARARGS, "Get comments from a filename."},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC
initc_comment_scanner(void)
{
  (void) Py_InitModule("c_comment_scanner", ScannerMethods);
}

