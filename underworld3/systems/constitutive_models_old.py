## This file has constitutive models that can be plugged into the SNES solvers

from typing_extensions import Self
import sympy
from sympy import sympify
from sympy.vector import gradient, divergence
import numpy as np

from typing import Optional, Callable
from typing import NamedTuple, Union

from petsc4py import PETSc

import underworld3 as uw
from underworld3.systems import SNES_Scalar, SNES_Vector, SNES_Stokes, SNES_SaddlePoint
import underworld3.timing as timing


class Constitutive_Model:
    r"""
    Constititutive laws relate gradients in the unknowns to fluxes of quantities
    (for example, heat fluxes are related to temperature gradients through a thermal conductivity)
    The `Constitutive_Model` class is a base class for building `underworld` constitutive laws

    In a scalar problem, the relationship is

     $$ q_i = k_{ij} \frac{\partial T}{\partial x_j}$$

    and the constitutive parameters describe \( k_{ij}\). The template assumes \( k_{ij} = \delta_{ij} \)

    In a vector problem (such as the Stokes problem), the relationship is

     $$ t_{ij} = c_{ijkl} \frac{\partial u_k}{\partial x_l} $$

    but is usually written to eliminate the anti-symmetric part of the displacement or velocity gradients (for example):

     $$ t_{ij} = c_{ijkl} \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    and the constitutive parameters describe \(c_{ijkl}\). The template assumes
    \( k_{ij} = \frac{1}{2} \left( \delta_{ik} \delta_{jl} + \delta_{il} \delta_{jk} \right) \) which is the
    4th rank identity tensor accounting for symmetry in the flux and the gradient terms.
    """

    @timing.routine_timer_decorator
    def __init__(
        self,
        dim: int,
        u_dim: int,
    ):

        # Define / identify the various properties in the class but leave
        # the implementation to child classes. The constitutive tensor is
        # defined as a template here, but should be instantiated via class
        # properties as required.

        # We provide a function that converts gradients / gradient history terms
        # into the relevant flux term.

        self.dim = dim
        self.u_dim = u_dim
        self._solver = None

        self.Parameters = self._Parameters()
        self.Parameters._solver = None
        self.Parameters._reset = self._reset

        self._material_properties = None

        ## Default consitutive tensor is the identity

        if self.u_dim == 1:
            self._c = sympy.Matrix.eye(self.dim)
        else:  # vector problem
            self._c = uw.maths.tensor.rank4_identity(self.dim)

        self._K = sympy.sympify(1)
        self._C = None

        super().__init__()

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.
        """

        def __init__(inner_self):
            inner_self._solver = None #### should this be here?
    
    @property
    def K(self):
        ''' The constitutive property for this flow law '''
        return self._K 

    @property
    def solver(self):
        """Each constitutive relationship can, optionally, be associated with one solver object.
        and a solver object _requires_ a constitive relationship to be defined."""
        return self._solver

    @solver.setter
    def solver(self, solver_object):
        if isinstance(
            solver_object, (SNES_Scalar, SNES_Vector, SNES_Stokes, SNES_SaddlePoint)
        ):
            self._solver = solver_object
            self.Parameters._solver = solver_object
            self._solver.is_setup = False

    ## Properties on all sub-classes

    @property
    def C(self):
        """The matrix form of the constitutive model (the `c` property)
        that relates fluxes to gradients.
        For scalar problem, this is the matrix representation of the rank 2 tensor.
        For vector problems, the Mandel form of the rank 4 tensor is returned.
        NOTE: this is an immutable object that is _a view_ of the underlying tensor
        """

        d = self.dim
        rank = len(self.c.shape)

        if rank == 2:
            return sympy.Matrix(self._c).as_immutable()
        else:
            return uw.maths.tensor.rank4_to_mandel(self._c, d).as_immutable()

    @property
    def c(self):
        """The tensor form of the constitutive model that relates fluxes to gradients. In scalar
        problems, `c` and `C` are equivalent (matrices), but in vector problems, `c` is a
        rank 4 tensor. NOTE: `c` is the canonical form of the constitutive relationship."""

        return self._c.as_immutable()

    def flux(
        self,
        ddu: sympy.Matrix = None,
        ddu_dt: sympy.Matrix = None,
        u: sympy.Matrix = None,  # may be needed in the case of cylindrical / spherical
        u_dt: sympy.Matrix = None,
    ):

        """Computes the effect of the constitutive tensor on the gradients of the unknowns.
        (always uses the `c` form of the tensor). In general cases, the history of the gradients
        may be required to evaluate the flux.
        """

        c = self.c
        rank = len(c.shape)

        # tensor multiplication

        if rank == 2:
            flux = c * ddu.T
        else:  # rank==4
            flux = sympy.tensorcontraction(
                sympy.tensorcontraction(sympy.tensorproduct(c, ddu), (3, 5)), (0, 1)
            )

        return sympy.Matrix(flux)

    def flux_1d(
        self,
        ddu: sympy.Matrix = None,
        ddu_dt: sympy.Matrix = None,
        u: sympy.Matrix = None,  # may be needed in the case of cylindrical / spherical
        u_dt: sympy.Matrix = None,
    ):

        """Computes the effect of the constitutive tensor on the gradients of the unknowns.
        (always uses the `c` form of the tensor). In general cases, the history of the gradients
        may be required to evaluate the flux. Returns the Voigt form that is flattened so as to
        match the PETSc field storage pattern for symmetric tensors.
        """

        flux = self.flux(ddu, ddu_dt, u, u_dt)

        assert (
            flux.is_symmetric()
        ), "The conversion to Voigt form is only defined for symmetric tensors in underworld"

        return uw.maths.tensor.rank2_to_voigt(flux, dim=self.dim)

    def _reset(self):
        d = self.dim
        self._build_c_tensor()

        if isinstance(
            self._solver, (SNES_Scalar, SNES_Vector, SNES_Stokes, SNES_SaddlePoint)
        ):
            self._solver.is_setup = False

        return

    def _build_c_tensor(self):
        """Return the identity tensor of appropriate rank (e.g. for projections)"""

        d = self.dim
        self._c = self._K * uw.maths.tensor.rank4_identity(d)

        return

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display
        from textwrap import dedent

        ## Docstring (static)
        docstring = dedent(self.__doc__)
        docstring = docstring.replace(r"\(", "$").replace(r"\)", "$")
        display(Markdown(docstring))
        display(
            Markdown(
                rf"This consititutive model is formulated for {self.dim} dimensional equations"
            )
        )

        ## Usually, there are constitutive parameters that can be included in the iputho display


class ViscousFlowModel(Constitutive_Model):
    r"""
    ```python
    class ViscousFlowModel(Constitutive_Model)
    ...
    ```
    ```python
    viscous_model = ViscousFlowModel(dim)
    viscous_model.material_properties = viscous_model.Parameters(viscosity=viscosity_fn)
    solver.constititutive_model = viscous_model
    ```
    $$ \tau_{ij} = \eta_{ijkl} \cdot \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    where \( \eta \) is the viscosity, a scalar constant, `sympy` function, `underworld` mesh variable or
    any valid combination of those types. This results in an isotropic (but not necessarily homogeneous or linear)
    relationship between $\tau$ and the velocity gradients. You can also supply \(\eta_{IJ}\), the Mandel form of the
    constitutive tensor, or \(\eta_{ijkl}\), the rank 4 tensor.

    The Mandel constitutive matrix is available in `viscous_model.C` and the rank 4 tensor form is
    in `viscous_model.c`.  Apply the constitutive model using:

    ```python
    tau = viscous_model.flux(gradient_matrix)
    ```
    ---
    """

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.
        """

        def __init__(
            inner_self,
            viscosity: Union[float, sympy.Function] = None,
        ):

            if viscosity is None:
                viscosity = sympy.sympify(1)

            inner_self._viscosity = sympy.sympify(viscosity)

        @property
        def viscosity(inner_self):
            return inner_self._viscosity

        @viscosity.setter
        def viscosity(inner_self, value: Union[float, sympy.Function]):
            inner_self._viscosity = value
            inner_self._reset()

    def __init__(self, dim):

        u_dim = dim
        super().__init__(dim, u_dim)

        return

    def _build_c_tensor(self):
        """For this constitutive law, we expect just a viscosity function"""

        d = self.dim
        viscosity = self.Parameters.viscosity

        try:
            self._c = 2 * uw.maths.tensor.rank4_identity(d) * viscosity
        except:
            d = self.dim
            dv = uw.maths.tensor.idxmap[d][0]
            if isinstance(viscosity, sympy.Matrix) and viscosity.shape == (dv, dv):
                self._c = 2 * uw.maths.tensor.mandel_to_rank4(viscosity, d)
            elif isinstance(viscosity, sympy.Array) and viscosity.shape == (d, d, d, d):
                self._c = 2 * viscosity
            else:
                raise RuntimeError(
                    "Viscosity is not a known type (scalar, Mandel matrix, or rank 4 tensor"
                )
        return

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display

        super()._ipython_display_()

        ## feedback on this instance
        display(
            Latex(
                r"$\quad\eta = $ "
                + sympy.sympify(self.Parameters.viscosity)._repr_latex_()
            )
        )


class ViscoPlasticFlowModel(ViscousFlowModel):
    r"""
    ```python
    class ViscoPlasticFlowModel(Constitutive_Model)
    ...
    ```
    ```python
    viscoplastic_model = ViscoPlasticFlowModel(dim)
    viscoplastic_model.material_properties = viscoplastic_model.Parameters(
                                                                            viscosity=viscosity_fn
                                                                            yield_stress=yieldstress_fn,
                                                                            min_viscosity=min_viscosity_fn,
                                                                            max_viscosity=max_viscosity_fn,
                                                                            yield_stress_min=float,
                                                                            edot_II_fn=strain_rate_inv_fn
                                                                            )
    solver.constititutive_model = viscoplastic_model
    ```
    $$ \tau_{ij} = \eta_{ijkl} \cdot \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    where \( \eta \) is the viscosity, a scalar constant, `sympy` function, `underworld` mesh variable or
    any valid combination of those types. This results in an isotropic (but not necessarily homogeneous or linear)
    relationship between $\tau$ and the velocity gradients. You can also supply \(\eta_{IJ}\), the Mandel form of the
    constitutive tensor, or \(\eta_{ijkl}\), the rank 4 tensor.


    In a viscoplastic model, this viscosity is actually defined to cap the value of the overall stress at a value known as the *yield stress*.
    In this constitutive law, we are assuming that the yield stress is a scalar limit on the 2nd invariant of the stress. A general, anisotropic
    model needs to define the yield surface carefully and only a sub-set of possible cases is available in `Underworld`

    This constitutive model is a convenience function that simplifies the code at run-time but can be reproduced easily by using the appropriate
    `sympy` functions in the standard viscous constitutive model. **If you see `not~yet~defined` in the definition of the effective viscosity, this means
    that you have not yet defined all the required functions. The behaviour is to default to the standard viscous constitutive law if yield terms are
    not specified.

    The Mandel constitutive matrix is available in `viscoplastic_model.C` and the rank 4 tensor form is
    in `viscoplastic_model.c`.  Apply the constitutive model using:

    ```python
    tau = viscoplastic_model.flux(gradient_matrix)
    ```
    ---
    """

    # Init for VP class (not needed ??)
    def __init__(self, dim):
        super().__init__(dim)

        return

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.

        `sympy.oo` (infinity) for default values ensures that sympy.Min simplifies away
        the conditionals when they are not required
        """

        def __init__(
            inner_self,
            viscosity: Union[float, sympy.Function] = sympy.sympify(1),
            yield_stress: Union[float, sympy.Function] = None,
            min_viscosity: Union[float, sympy.Function] = sympy.oo,
            yield_stress_min: Union[float, sympy.Function] = sympy.oo,
            edot_II_fn: sympy.Function = None,
            epsilon_edot_II: float = None,
        ):

            if edot_II_fn is None:
                edot_II_fn = sympy.symbols(
                    r"\left|\dot\epsilon\right|\rightarrow\textrm{not~yet~defined}"
                )

            if epsilon_edot_II is None:
                epsilon_edot_II = 0  # sympy.sympify(10) ** -10

            inner_self._bg_viscosity = sympy.sympify(viscosity)
            inner_self._yield_stress = sympy.sympify(yield_stress)
            inner_self._yield_stress_min = sympy.sympify(yield_stress_min)
            inner_self._min_viscosity = sympy.sympify(min_viscosity)
            inner_self._max_viscosity = sympy.sympify(max_viscosity)
            inner_self._edot_II_fn = sympy.sympify(edot_II_fn)
            inner_self._epsilon_edot_II = sympy.sympify(epsilon_edot_II)

            return

        @property
        def bg_viscosity(inner_self):
            return inner_self._bg_viscosity

        @bg_viscosity.setter
        def bg_viscosity(inner_self, value: Union[float, sympy.Function]):
            inner_self._bg_viscosity = value
            inner_self._reset()

        @property
        def min_viscosity(inner_self):
            return inner_self._min_viscosity

        @min_viscosity.setter
        def min_viscosity(inner_self, value: Union[float, sympy.Function]):
            inner_self._min_viscosity = value
            inner_self._reset()

        @property
        def yield_stress(inner_self):
            return inner_self._yield_stress

        @yield_stress.setter
        def yield_stress(inner_self, value: Union[float, sympy.Function]):
            inner_self._yield_stress = value
            inner_self._reset()

        @property
        def yield_stress_min(inner_self):
            return inner_self._yield_stress_min

        @yield_stress_min.setter
        def yield_stress_min(inner_self, value: Union[float, sympy.Function]):
            inner_self._yield_stress_min = value
            inner_self._reset()

        @property
        def edot_II_fn(inner_self):
            return inner_self._edot_II_fn

        @edot_II_fn.setter
        def edot_II_fn(inner_self, value: sympy.Function):
            inner_self._edot_II_fn = value
            inner_self._reset()

        @property
        def epsilon_edot_II(inner_self):
            return inner_self._epsilon_edot_II

        @epsilon_edot_II.setter
        def epsilon_edot_II(inner_self, value: float):
            inner_self._epsilon_edot_II = sympy.sympify(value)
            inner_self._reset()

        # This has no setter !!
        @property
        def viscosity(inner_self):

            # detect if values we need are defined or are placeholder symbols

            if isinstance(inner_self.yield_stress, sympy.core.symbol.Symbol):
                return inner_self.bg_viscosity

            if isinstance(inner_self.edot_II_fn, sympy.core.symbol.Symbol):
                return inner_self.bg_viscosity

            # Don't put conditional behaviour in the constitutive law
            # where it is not needed

            if inner_self.yield_stress_min is not None:
                yield_stress = sympy.Max(
                    inner_self.yield_stress_min, inner_self.yield_stress
                )
            else:
                yield_stress = inner_self.yield_stress

            viscosity_yield = yield_stress / (
                2.0 * inner_self.edot_II_fn + inner_self.epsilon_edot_II
            )

            ## Question is, will sympy reliably differentiate something
            ## with so many Max / Min statements. The smooth version would
            ## be a reasonable alternative:

            # effective_viscosity = sympy.sympify(
            #     1 / (1 / inner_self.bg_viscosity + 1 / viscosity_yield),
            # )

            effective_viscosity = sympy.Min(inner_self.bg_viscosity, viscosity_yield)

            # If we want to apply limits to the viscosity but see caveat above

            if inner_self.min_viscosity is not None:

                return sympy.simplify(
                    sympy.Max(
                        effective_viscosity,
                        inner_self.min_viscosity,
                    )
                )

            else:
                return sympy.simplify(effective_viscosity)

        ## ===== End of parameters sub_class

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display

        super()._ipython_display_()

        ## feedback on this instance
        display(
            Latex(
                r"$\quad\eta_\textrm{0} = $ "
                + sympy.sympify(self.Parameters.bg_viscosity)._repr_latex_()
            ),
            Latex(
                r"$\quad\tau_\textrm{y} = $ "
                + sympy.sympify(self.Parameters.yield_stress)._repr_latex_(),
            ),
            Latex(
                r"$\quad|\dot\epsilon| = $ "
                + sympy.sympify(self.Parameters.edot_II_fn)._repr_latex_(),
            ),
            ## Todo: add all the other properties in here
        )

class ViscoElasticPlasticFlowModel(Constitutive_Model):
    r"""
    ```python
    class ViscousFlowModel(Constitutive_Model)
    ...
    ```
    ```python
    viscous_model = ViscousFlowModel(dim)
    viscous_model.material_properties = viscous_model.Parameters(viscosity=viscosity_fn)
    solver.constititutive_model = viscous_model
    ```
    $$ \tau_{ij} = \eta_{ijkl} \cdot \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    where \( \eta \) is the viscosity, a scalar constant, `sympy` function, `underworld` mesh variable or
    any valid combination of those types. This results in an isotropic (but not necessarily homogeneous or linear)
    relationship between $\tau$ and the velocity gradients. You can also supply \(\eta_{IJ}\), the Mandel form of the
    constitutive tensor, or \(\eta_{ijkl}\), the rank 4 tensor.

    The Mandel constitutive matrix is available in `viscous_model.C` and the rank 4 tensor form is
    in `viscous_model.c`.  Apply the constitutive model using:

    ```python
    tau = viscous_model.flux(gradient_matrix)
    ```
    ---

    ```python
    class ViscoElasticFlowModel(Constitutive_Model)
    ...
    ```
    ```python
    viscoelastic_model = ViscoElasticFlowModel(dim)
    viscoelastic_model.material_properties = viscous_model.Parameters(viscosity=viscosity_fn)
    solver.constititutive_model = viscoelastic_model
    ```
    $$ \tau_{ij} = \eta_{ijkl} \cdot \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    where \( \eta \) is the viscosity, a scalar constant, `sympy` function, `underworld` mesh variable or
    any valid combination of those types. This results in an isotropic (but not necessarily homogeneous or linear)
    relationship between $\tau$ and the velocity gradients. You can also supply \(\eta_{IJ}\), the Mandel form of the
    constitutive tensor, or \(\eta_{ijkl}\), the rank 4 tensor.

    The Mandel constitutive matrix is available in `viscous_model.C` and the rank 4 tensor form is
    in `viscous_model.c`.  Apply the constitutive model using:

    ```python
    tau = viscous_model.flux(gradient_matrix)
    ```
    ---
    """

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.
        """

        def __init__(
            inner_self,
            shear_viscosity_0: Union[float, sympy.Function] = 1,
            shear_viscosity_min: Union[float, sympy.Function] = sympy.oo,
            shear_modulus: Union[float, sympy.Function] = sympy.oo,
            dt_elastic: Union[float, sympy.Function] = sympy.oo,
            yield_stress: Union[float, sympy.Function] = sympy.oo,
            yield_stress_min: Union[float, sympy.Function] = sympy.oo,
            strainrate_inv_II: sympy.Function = None,
            stress_star: sympy.Function = None,
            strainrate_inv_II_min: float = 0,
        ):

            if strainrate_inv_II_min is None:
                strainrate_inv_II = sympy.symbols(
                    r"\left|\dot\epsilon\right|\rightarrow\textrm{not\ defined}"
                )

            if stress_star is None:
                stress_star = sympy.symbols(
                    r"\sigma^*\rightarrow\textrm{not\ defined}"
                )

            inner_self._shear_viscosity_0 = sympy.sympify(shear_viscosity_0)
            inner_self._shear_modulus = sympy.sympify(shear_modulus)
            inner_self._dt_elastic = sympy.sympify(dt_elastic)
            inner_self._yield_stress = sympy.sympify(yield_stress)
            inner_self._yield_stress_min = sympy.sympify(yield_stress_min)
            inner_self._shear_viscosity_min = sympy.sympify(shear_viscosity_min)
            inner_self._strainrate_inv_II = sympy.sympify(strainrate_inv_II)
            inner_self._stress_star = sympy.sympify(stress_star)
            inner_self._strainrate_inv_II_min = sympy.sympify(strainrate_inv_II_min)

            return

        @property
        def shear_viscosity_0(inner_self):
            return inner_self._shear_viscosity_0

        @shear_viscosity_0.setter
        def shear_viscosity_0(inner_self, value: Union[float, sympy.Function]):
            inner_self._shear_viscosity_0 = value
            inner_self._reset()

        @property
        def shear_modulus(inner_self):
            return inner_self._shear_modulus

        @shear_modulus.setter
        def shear_modulus(inner_self, value: Union[float, sympy.Function]):
            inner_self._shear_modulus = value
            inner_self._reset()

        @property
        def dt_elastic(inner_self):
            return inner_self._dt_elastic

        @dt_elastic.setter
        def dt_elastic(inner_self, value: Union[float, sympy.Function]):
            inner_self._dt_elastic = value
            inner_self._reset()

        @property
        def ve_effective_viscosity(inner_self):

            # the dt_elastic defaults to infinity, t_relax to zero,
            # so this should be well behaved in the viscous limit

            el_eff_visc = inner_self.shear_viscosity_0 / (
                1 + inner_self.t_relax / inner_self.dt_elastic
            )

            return sympy.simplify(el_eff_visc)

        @property
        def t_relax(inner_self):
            # shear modulus defaults to infinity so t_relax goes to zero
            # in the viscous limit

            return inner_self.shear_viscosity_0 / inner_self.shear_modulus

        @property
        def shear_viscosity_min(inner_self):
            return inner_self.shear_viscosity_min

        @shear_viscosity_min.setter
        def shear_viscosity_min(inner_self, value: Union[float, sympy.Function]):
            inner_self.shear_viscosity_min = value
            inner_self._reset()

        @property
        def yield_stress(inner_self):
            return inner_self._yield_stress

        @yield_stress.setter
        def yield_stress(inner_self, value: Union[float, sympy.Function]):
            inner_self._yield_stress = value
            inner_self._reset()

        @property
        def yield_stress_min(inner_self):
            return inner_self._yield_stress_min

        @yield_stress_min.setter
        def yield_stress_min(inner_self, value: Union[float, sympy.Function]):
            inner_self._yield_stress_min = value
            inner_self._reset()

        @property
        def strainrate_inv_II(inner_self):
            return inner_self._strainrate_inv_II

        @strainrate_inv_II.setter
        def strainrate_inv_II(inner_self, value: sympy.Function):
            inner_self._strainrate_inv_II = value
            inner_self._reset()

        @property
        def stress_star(inner_self):
            return inner_self._stress_star

        @stress_star.setter
        def stress_star(inner_self, value: sympy.Function):
            inner_self._stress_star = value
            inner_self._reset()

        @property
        def strainrate_inv_II_min(inner_self):
            return inner_self._epsilon_edot_II

        @strainrate_inv_II_min.setter
        def strainrate_inv_II_min(inner_self, value: float):
            inner_self._epsilon_edot_II = sympy.sympify(value)
            inner_self._reset()

        # This has no setter !!
        @property
        def viscosity(inner_self):

            # detect if values we need are defined or are placeholder symbols

            if inner_self.yield_stress == sympy.oo:
                return inner_self.ve_effective_viscosity

            if isinstance(inner_self.edot_II_fn, sympy.core.symbol.Symbol):
                return inner_self.ve_effective_viscosity

            el_eff_visc = inner_self.ve_effective_viscosity

            if inner_self.yield_stress_min is not None:
                yield_stress = sympy.Max(
                    inner_self.yield_stress_min, inner_self.yield_stress
                )
            else:
                yield_stress = inner_self.yield_stress

            viscosity_yield = yield_stress / (
                2.0 * inner_self.edot_II_fn + inner_self.strainrate_inv_II_min
            )

            ## Question is, will sympy reliably differentiate something
            ## with so many Max / Min statements. The smooth version would
            ## be a reasonable alternative:

            # effective_viscosity = sympy.sympify(
            #     1 / (1 / inner_self.shear_viscosity_0 + 1 / viscosity_yield),
            # )

            ## It seems to be OK but maybe there are issues with efficiency we
            ## can investigate more carefully.

            effective_viscosity = sympy.Min(el_eff_visc, viscosity_yield)

            # If we want to apply limits to the viscosity but see caveat above

            if inner_self.shear_viscosity_min is not None:
                return sympy.simplify(
                    sympy.Max(
                        effective_viscosity,
                        inner_self.shear_viscosity_min,
                    )
                )

            else:
                return sympy.simplify(effective_viscosity)

    def __init__(self, dim):

        u_dim = dim
        super().__init__(dim, u_dim)

        return

    ## Is this really different from the original ?

    def _build_c_tensor(self):
        """For this constitutive law, we expect just a viscosity function"""

        d = self.dim
        viscosity = self.Parameters.viscosity
        shear_modulus = self.Parameters.shear_modulus
        dt_elastic = self.Parameters.dt_elastic

        try:
            self._c = 2 * uw.maths.tensor.rank4_identity(d) * viscosity
        except:
            d = self.dim
            dv = uw.maths.tensor.idxmap[d][0]
            if isinstance(viscosity, sympy.Matrix) and viscosity.shape == (dv, dv):
                self._c = 2 * uw.maths.tensor.mandel_to_rank4(viscosity, d)
            elif isinstance(viscosity, sympy.Array) and viscosity.shape == (d, d, d, d):
                self._c = 2 * viscosity
            else:
                raise RuntimeError(
                    "Viscosity is not a known type (scalar, Mandel matrix, or rank 4 tensor"
                )
        return

    # Modify flux to use the stress history term
    # This may be preferable to using strain rate which can be discontinuous
    # and harder to map back and forth between grid and particles without numerical smoothing

    def flux(
        self,
        ddu: sympy.Matrix = None,
        ddu_dt: sympy.Matrix = None,
        u: sympy.Matrix = None,  # may be needed in the case of cylindrical / spherical
        u_dt: sympy.Matrix = None,
    ):

        """Computes the effect of the constitutive tensor on the gradients of the unknowns.
        (always uses the `c` form of the tensor). In general cases, the history of the gradients
        may be required to evaluate the flux. For viscoelasticity, the
        """

        c = self.c
        rank = len(c.shape)

        # tensor multiplication

        if rank == 2:
            flux = c * ddu.T
        else:  # rank==4
            flux = sympy.tensorcontraction(
                sympy.tensorcontraction(sympy.tensorproduct(c, ddu), (3, 5)), (0, 1)
            )

        # Now add in the stress history. In the
        # viscous limit, this term is not well behaved
        # and we need to check that

        if self.is_elastic:
            flux = sympy.Matrix(flux) + self.Parameters.stress_star / (
                1 + self.Parameters.dt_elastic / self.Parameters.t_relax
            )

        return sympy.simplify(sympy.Matrix(flux))

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display

        super()._ipython_display_()

        display(Markdown(r"### Viscous deformation"))
        display(
            Latex(
                r"$\quad\eta_\textrm{0} = $ "
                + sympy.sympify(self.Parameters.bg_viscosity)._repr_latex_()
            ),
        )

        ## If elasticity is active:
        display(Markdown(r"#### Elastic deformation"))
        display(
            Latex(
                r"$\quad\mu = $ "
                + sympy.sympify(self.Parameters.shear_modulus)._repr_latex_(),
            ),
            Latex(
                r"$\quad\Delta t_e = $ "
                + sympy.sympify(self.Parameters.dt_elastic)._repr_latex_(),
            ),
            Latex(
                r"$\quad \sigma^* = $ "
                + sympy.sympify(self.Parameters.stress_star)._repr_latex_(),
            ),
        )

        # If plasticity is active
        display(Markdown(r"#### Plastic deformation"))
        display(
            Latex(
                r"$\quad\tau_\textrm{y} = $ "
                + sympy.sympify(self.Parameters.yield_stress)._repr_latex_(),
            ),
            Latex(
                r"$\quad|\dot\epsilon| = $ "
                + sympy.sympify(self.Parameters.edot_II_fn)._repr_latex_(),
            ),
            ## Todo: add all the other properties in here
        )

    @property
    def is_elastic(self):

        # If any of these is not defined, elasticity is switched off

        if self.Parameters.dt_elastic is sympy.oo:
            return False

        if self.Parameters.shear_modulus is sympy.oo:
            return False

        if isinstance(self.Parameters.stress_star, sympy.core.symbol.Symbol):
            return False

        return True

    @property
    def is_viscoplastic(self):

        if self.Parameters.yield_stress == sympy.oo:
            return False

        if isinstance(self.Parameters.edot_II_fn, sympy.core.symbol.Symbol):
            return False

        return True


###

class DiffusionModel(Constitutive_Model):
    r"""
    ```python
    class DiffusionModel(Constitutive_Model)
    ...
    ```
    ```python
    diffusion_model = DiffusionModel(dim)
    diffusion_model.material_properties = diffusion_model.Parameters(diffusivity=diffusivity_fn)
    scalar_solver.constititutive_model = diffusion_model
    ```
    $$ q_{i} = \kappa_{ij} \cdot \frac{\partial \phi}{\partial x_j}  $$

    where \( \kappa \) is a diffusivity, a scalar constant, `sympy` function, `underworld` mesh variable or
    any valid combination of those types. Access the constitutive model using:

    ```python
    flux = diffusion_model.flux(gradient_matrix)
    ```
    ---
    """

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.
        """

        def __init__(
            inner_self,
            diffusivity: Union[float, sympy.Function] = 1,
        ):
            inner_self._diffusivity = diffusivity

        @property
        def diffusivity(inner_self):
            return inner_self._diffusivity

        @diffusivity.setter
        def diffusivity(inner_self, value: Union[float, sympy.Function]):
            inner_self._diffusivity = value
            inner_self._reset()

    def __init__(self, dim):

        self.u_dim = 1
        super().__init__(dim, self.u_dim)

        return

    def _build_c_tensor(self):
        """For this constitutive law, we expect just a diffusivity function"""

        d = self.dim
        kappa = self.Parameters.diffusivity
        self._c = sympy.Matrix.eye(d) * kappa

        return

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display

        super()._ipython_display_()

        ## feedback on this instance
        display(
            Latex(
                r"$\quad\kappa = $ "
                + sympy.sympify(self.Parameters.diffusivity)._repr_latex_()
            )
        )

        return


class TransverseIsotropicFlowModel(Constitutive_Model):
    r"""
    ```python
    class TransverseIsotropicFlowModel(Constitutive_Model)
    ...
    ```
    ```python
    viscous_model = TransverseIsotropicFlowModel(dim)
    viscous_model.material_properties = viscous_model.Parameters(eta_0=viscosity_fn,
                                                                eta_1=weak_viscosity_fn,
                                                                director=orientation_vector_fn)
    solver.constititutive_model = viscous_model
    ```
    $$ \tau_{ij} = \eta_{ijkl} \cdot \frac{1}{2} \left[ \frac{\partial u_k}{\partial x_l} + \frac{\partial u_l}{\partial x_k} \right] $$

    where $\eta$ is the viscosity tensor defined as:

    $$ \eta_{ijkl} = \eta_0 \cdot I_{ijkl} + (\eta_0-\eta_1) \left[ \frac{1}{2} \left[
        n_i n_l \delta_{jk} + n_j n_k \delta_{il} + n_i n_l \delta_{jk} + n_j n_l \delta_{ik} \right] - 2 n_i n_j n_k n_l \right] $$

    and \( \hat{\mathbf{n}} \equiv \left\{ n_i \right\} \) is the unit vector
    defining the local orientation of the weak plane (a.k.a. the director).

    The Mandel constitutive matrix is available in `viscous_model.C` and the rank 4 tensor form is
    in `viscous_model.c`.  Apply the constitutive model using:

    ```python
    tau = viscous_model.flux(gradient_matrix)
    ```
    ---
    """

    class _Parameters:
        """Any material properties that are defined by a constitutive relationship are
        collected in the parameters which can then be defined/accessed by name in
        individual instances of the class.
        """

        def __init__(
            inner_self,
            eta_0: Union[float, sympy.Function] = 1,
            eta_1: Union[float, sympy.Function] = 1,
            director: Union[sympy.Matrix, sympy.Function] = sympy.Matrix([0, 0, 1]),
        ):
            inner_self._eta_0 = eta_0
            inner_self._eta_1 = eta_1
            inner_self._director = director
            # inner_self.constitutive_model_class = const_model

        ## Note the inefficiency below if we change all these values one after the other

        @property
        def eta_0(inner_self):
            return inner_self._eta_0

        @eta_0.setter
        def eta_0(
            inner_self,
            value: Union[float, sympy.Function],
        ):
            inner_self._eta_0 = value
            inner_self._reset()

        @property
        def eta_1(inner_self):
            return inner_self._eta_1

        @eta_1.setter
        def eta_1(
            inner_self,
            value: Union[float, sympy.Function],
        ):
            inner_self._eta_1 = value
            inner_self._reset()

        @property
        def director(inner_self):
            return inner_self._director

        @director.setter
        def director(
            inner_self,
            value: Union[sympy.Matrix, sympy.Function],
        ):
            inner_self._director = value
            inner_self._reset()

    def __init__(self, dim):

        u_dim = dim
        super().__init__(dim, u_dim)

        # default values ... maybe ??
        return

    def _build_c_tensor(self):
        """For this constitutive law, we expect two viscosity functions
        and a sympy matrix that describes the director components n_{i}"""

        d = self.dim
        dv = uw.maths.tensor.idxmap[d][0]

        eta_0 = self.Parameters.eta_0
        eta_1 = self.Parameters.eta_1
        n = self.Parameters.director

        Delta = eta_1 - eta_0

        lambda_mat = uw.maths.tensor.rank4_identity(d) * eta_0

        for i in range(d):
            for j in range(d):
                for k in range(d):
                    for l in range(d):
                        lambda_mat[i, j, k, l] += Delta * (
                            (
                                n[i] * n[k] * int(j == l)
                                + n[j] * n[k] * int(l == i)
                                + n[i] * n[l] * int(j == k)
                                + n[j] * n[l] * int(k == i)
                            )
                            / 2
                            - 2 * n[i] * n[j] * n[k] * n[l]
                        )

        lambda_mat = sympy.simplify(uw.maths.tensor.rank4_to_mandel(lambda_mat, d))

        self._c = uw.maths.tensor.mandel_to_rank4(lambda_mat, d)

    def _ipython_display_(self):
        from IPython.display import Latex, Markdown, display

        super()._ipython_display_()

        ## feedback on this instance
        display(
            Latex(
                r"$\quad\eta_0 = $ "
                + sympy.sympify(self.Parameters.eta_0)._repr_latex_()
            )
        )
        display(
            Latex(
                r"$\quad\eta_1 = $ "
                + sympy.sympify(self.Parameters.eta_1)._repr_latex_()
            )
        )
        display(
            Latex(
                r"$\quad\hat{\mathbf{n}} = $ "
                + sympy.sympify(self.Parameters.director.T)._repr_latex_()
            )
        )