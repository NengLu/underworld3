# To add a new cell, type '# %%'
# To add a new markdown cell, type '# %% [markdown]'
# %%
from petsc4py import PETSc
import underworld3 as uw
from underworld3.stokes import Stokes
import numpy as np
import sympy

options = PETSc.Options()
# options["help"] = None

# options["pc_type"]  = "svd"

options["ksp_rtol"] =  1.0e-8
# options["ksp_monitor_short"] = None
# options["ksp_monitor_true_residual"] = None
# options["ksp_converged_reason"] = None

# options["snes_type"]  = "qn"
# options["snes_type"]  = "nrichardson"
options["snes_converged_reason"] = None
options["snes_monitor"] = None
# options["snes_monitor_short"] = None
# options["snes_view"]=None
# options["snes_test_jacobian"] = None
options["snes_rtol"] = 1.0e-7
# options["snes_max_it"] = 1
# options["snes_linesearch_monitor"] = None


# %%
n_els = 64
v_degree = 1
mesh = uw.Mesh(elementRes=(n_els,n_els))

# %%
# NL problem 
# Create solution functions
from underworld3.function import AnalyticSolNL_velocity, AnalyticSolNL_bodyforce, AnalyticSolNL_viscosity 
r = mesh.r
eta0 = 1.
n = 1
r0 = 1.5
params = (eta0, n, r0) 
sol_bf   = AnalyticSolNL_bodyforce( *params, *r )
sol_vel  = AnalyticSolNL_velocity(  *params, *r )
sol_visc = AnalyticSolNL_viscosity( *params, *r )

# %%
stokes = Stokes(mesh, u_degree=v_degree, p_degree=v_degree-1 )
bnds = mesh.boundary
stokes.add_dirichlet_bc( sol_vel, [bnds.LEFT, bnds.RIGHT],  [0,1] )  # left/right: function, markers, components
stokes.add_dirichlet_bc( sol_vel, [bnds.TOP,  bnds.BOTTOM], [1, ] )  # top/bottom: function, markers, components

# I'm actually not sure why we need the -ve here... something's amiss.
stokes.bodyforce = -sol_bf  
# %%
# do linear first to get reasonable starting place
print("Linear solve")
stokes.viscosity = 1.
stokes.solve()
# %%
print("Non Linear solve")
# get strainrate
sr = stokes.strainrate
# not sure if the following is needed as div_u should be zero
sr -= (stokes.div_u/mesh.dim)*sympy.eye(mesh.dim)
# second invariant of strain rate
inv2 = sr[0,0]**2 + sr[0,1]**2 + sr[1,0]**2 + sr[1,1]**2
inv2 = 1/2*inv2
inv2 = sympy.sqrt(inv2)
alpha_by_two = 2/r0 - 2
stokes.viscosity = 2*eta0*inv2**alpha_by_two
stokes.solve(init_guess_up=stokes.up_local)

# %%
vel_soln_fem = stokes.u_local.array
vel_soln_ana = stokes.u_local.array.copy()
# %%
vel_soln_ana_shaped = vel_soln_ana.reshape(mesh.data.shape)
# %%
for index, coord in enumerate(mesh.data):
    # interface to this is still yuck... 
    vel_soln_ana_shaped[index] = sol_vel.evalf(subs={mesh.N.x:coord[0], mesh.N.y:coord[1]}).to_matrix(mesh.N)[0:2]
from numpy import linalg as LA
l2diff = LA.norm(vel_soln_fem - vel_soln_ana)
print("Diff norm = {}".format(l2diff))
if not np.allclose(l2diff, 0.0367,rtol=1.e-2):
    raise RuntimeError("Solve did not produce expected result.")
if not np.allclose(vel_soln_fem, vel_soln_ana, rtol=1.e-2):
    raise RuntimeError("Solve did not produce expected result.")
