This is a C extension for [hotdoc](https://github.com/hotdoc/hotdoc)

This extension uses clang to generate symbols for C source code,
and implements its own comment scanner, to speed things up in
situations where the relevant comments are explicitly named, and
the user doesn't need to document static functions.

### Install instructions:

This extension uses the bindings of clang. It explicitly requires
the clang-3.5 bindings, and you will thus need to install clang 3.5
for it to work.

This extension also uses flex for the comment scanner.

On Fedora 22 the dependencies can be installed with:

```
dnf install clang-devel flex python-devel
```

On Debian / Ubuntu:

```
apt-get install libclang-3.5-dev flex python-dev
```

If you use this extension in another environment, please let me know
how you installed these requirements :)

You can then install this extension either through pip:

```
pip install hotdoc_c_extension
```

Or with setup.py if you checked out the code from git:

```
python setup.py install
```

This will of course work in a virtualenv as well.

### Usage:

Just run hotdoc's wizard for more information once the extension is installed with:

```
hotdoc conf --quickstart
```

### Hacking

Checkout the code from github, then run:

```
python setup.py develop
```
