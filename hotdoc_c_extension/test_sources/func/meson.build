project('function', 'c', version : '1.0')

gnome = import('gnome')
files_ = ['function.c', 'function.h']
funclib = shared_library('funclib', files_)

gir = gnome.generate_gir(funclib,
      sources : files_,
      namespace : 'Func',
      nsversion : '1.0',
      identifier_prefix : 'func',
      symbol_prefix : 'func',
      install : true,
)
