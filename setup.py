from setuptools import setup, find_packages

setup(
    name = "hotdoc-c-extension",
    version = "0.6",
    keywords = "C clang hotdoc",
    url='https://github.com/MathieuDuponchelle/hotdoc-c-extension',
    author_email = 'mathieu.duponchelle@opencreed.com',
    license = 'LGPL',
    description = "An extension for hotdoc that parses C using clang",
    author = "Mathieu Duponchelle",
    packages = find_packages(),
    entry_points = {'hotdoc.extensions': 'get_extension_classes = c_extension:get_extension_classes'},
    install_requires = [
        'hotdoc>=0.6',
        'clang',
    ]
)
