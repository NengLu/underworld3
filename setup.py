#!/usr/bin/env python

#$ python setup.py build_ext --inplace

from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize

import numpy
import petsc4py

def configure():
    INCLUDE_DIRS = []
    LIBRARY_DIRS = []
    LIBRARIES    = []

    # PETSc
    import os
    PETSC_DIR  = os.environ['PETSC_DIR']
    PETSC_ARCH = os.environ.get('PETSC_ARCH', '')
    from os.path import join, isdir
    if PETSC_ARCH and isdir(join(PETSC_DIR, PETSC_ARCH)):
        INCLUDE_DIRS += [join(PETSC_DIR, PETSC_ARCH, 'include'),
                         join(PETSC_DIR, 'include')]
        LIBRARY_DIRS += [join(PETSC_DIR, PETSC_ARCH, 'lib')]
    else:
        if PETSC_ARCH: pass # XXX should warn ...
        INCLUDE_DIRS += [join(PETSC_DIR, 'include')]
        LIBRARY_DIRS += [join(PETSC_DIR, 'lib')]
    LIBRARIES += ['petsc']

    # PETSc for Python
    INCLUDE_DIRS += [petsc4py.get_include()]

    # NumPy
    INCLUDE_DIRS += [numpy.get_include()]

    return dict(
        include_dirs=INCLUDE_DIRS + [os.curdir] + ['underworld3/petsc4py_additions'],
        libraries=LIBRARIES,
        library_dirs=LIBRARY_DIRS,
        runtime_library_dirs=LIBRARY_DIRS,
    )

extensions = [
    Extension('underworld3.mesh',
              sources = ['underworld3/mesh.pyx'],
              **configure()),
    Extension('underworld3.stokes',
              sources = ['underworld3/stokes.pyx',
                         'underworld3/functions.c'],
              **configure()),
    Extension('underworld3.petsc_types',
              sources = ['underworld3/petsc_types.pyx',],
              **configure()),
    Extension('underworld3.poisson',
              sources = ['underworld3/poisson.pyx',
                         'underworld3/poisson_setup.c'],
              **configure()),
]

setup(name = "underworld3", 
    packages=['underworld3'],
    package_data={'underworld3':['*.pxd',]},
    ext_modules = cythonize(
        extensions, gdb_debug=True, 
        include_path=[petsc4py.get_include()]) )
