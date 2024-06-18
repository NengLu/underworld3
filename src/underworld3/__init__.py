"""## Underworld3 Python package
`Underworld3` is a finite element, particle-in-cell geodynamics code that produces 
mathematically self-describing models through an interface with `sympy` Underworld3 builds upon the `PETSc` 
parallel finite element and solver package, using their `petsc4py` library. 

A common pattern for building `underworld3` models is to develop python scripts in notebook-friendly form
(e.g. with `jupytext`) which are thoroughly documented through markdown descriptions. `underworld` objects 
are similarly documented so that their underlying algorithmic and mathemcical structure can be examined in 
a notebook.

`python` scripts built this way will also be compatible with `mpirun` for parallel execution.

## Documentation

The underworld documentation is in two parts: the user manual / theory manual is a hand-written document that is built from this repository automatically 
from the sources in the `Jupyterbook` directory. This api documentation is autogenerated from the code and its annotations. There are two version of 
each documentation package that are published online. The main (stable) branch

- https://underworldcode.github.io/underworld3/main/FrontPage.html
- https://underworldcode.github.io/underworld3/main_api/index.html

The development branch has similar documentation:

- https://underworldcode.github.io/underworld3/development/FrontPage.html
- https://underworldcode.github.io/underworld3/development_api/index.html


## Building / installation

Refer to the Dockerfile for uw3 build instructions.  

To install from the repository
```shell
pip install .
```

The in-place `pip` installation may be helpful for developers (after the above)

```shell
pip install -e .
```

To clean the git repository or all files ... be careful.
```shell
./clean.sh
```

## Testing and documentation

Run the `pytest` testing suite with
```shell
./test.sh
```

This API documentation is build with 
```shell
./docs.sh
```

Open `uw3_api_docs/index.html` to browse. 

"""

from mpi4py import MPI  # for initialising MPI
import petsc4py as _petsc4py
import sys

_petsc4py.init(sys.argv)

from petsc4py import PETSc

# pop the default petsc Signal handler to let petsc errors appear in python
# unclear if this is the appropriate way see discussion
# https://gitlab.com/petsc/petsc/-/issues/1066

PETSc.Sys.popErrorHandler()


def view():
    from IPython.display import Latex, Markdown, display
    from textwrap import dedent
    import inspect

    ## Docstring (static)
    docstring = dedent(__doc__)
    # docstring = docstring.replace("$", "$").replace("$", "$")
    display(Markdown(docstring))

    return


# PETSc.Log().begin()

# Bundle these utils
from ._var_types import *
from .utilities._petsc_tools import *
from .utilities._nb_tools import *

# Needed everywhere
import underworld3.mpi
from underworld3.utilities import _api_tools

import underworld3.adaptivity
import underworld3.coordinates
import underworld3.discretisation
import underworld3.meshing
import underworld3.constitutive_models
import underworld3.maths
import underworld3.swarm
import underworld3.systems
import underworld3.maths
import underworld3.utilities
import underworld3.kdtree
import underworld3.cython
import underworld3.scaling
import underworld3.visualisation
import numpy as _np

# Info for JIT modules.
# These dicts should be populated by submodules
# which define cython/c based classes.
# We use ordered dictionaries because the
# ordering can be important when linking in libraries.
# Note that actually what we want is an ordered set (which Python
# doesn't natively provide). Hence for the key/value pair,
# the value is always set to `None`.

from collections import OrderedDict as _OD

_libfiles = _OD()
_libdirs = _OD()
_incdirs = _OD({_np.get_include(): None})


# def _is_notebook() -> bool:
#     """
#     Function to determine if the python environment is a Notebook or not.

#     Returns 'True' if executing in a notebook, 'False' otherwise

#     Script taken from https://stackoverflow.com/a/39662359/8106122
#     """

#     try:
#         shell = get_ipython().__class__.__name__
#         if shell == "ZMQInteractiveShell":
#             return True  # Jupyter notebook or qtconsole
#         elif shell == "TerminalInteractiveShell":
#             return False  # Terminal running IPython
#         else:
#             return False  # Other type (?)
#     except NameError:
#         return False  # Probably standard Python interpreter


# is_notebook = _is_notebook()


## -------------------------------------------------------------

# pdoc3 over-rides. pdoc3 has a strange path-traversal algorithm
# that seems to have trouble finding modules if we move this
# dictionary to any other location in the underworld3 tree

__pdoc__ = {}

# Cython files cannot be documented. We should move pure
# python out of these files if we can

__pdoc__["kdtree"] = False
__pdoc__["cython"] = False
# __pdoc__["function.analytic"] = False

# Here we nuke some of the placeholders in the parent class so that they do not mask the
# child class modifications

__pdoc__["systems.constitutive_models.Constitutive_Model.Parameters"] = False


## Add an options dictionary for arbitrary underworld things