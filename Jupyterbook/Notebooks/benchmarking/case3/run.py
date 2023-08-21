## this code gets run first

# %% [markdown]
# # Constant viscosity convection, Cartesian domain (benchmark)
# 
# 
# 
# This example solves 2D dimensionless isoviscous thermal convection with a Rayleigh number, for comparison with the [Blankenbach et al. (1989) benchmark](https://academic.oup.com/gji/article/98/1/23/622167).
# 
# We set up a v, p, T system in which we will solve for a steady-state T field in response to thermal boundary conditions and then use the steady-state T field to compute a stokes flow in response.
# 

# %%
import petsc4py
from petsc4py import PETSc
from mpi4py import MPI
import math

import underworld3 as uw
from underworld3.systems import Stokes
from underworld3 import function

import os 
import numpy as np
import sympy
from copy import deepcopy 
import pickle
import matplotlib.pyplot as plt

from underworld3.utilities import generateXdmf
#os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE" # solve locking issue when reading file
#os.environ["HDF5"]
comm = MPI.COMM_WORLD

## here lets write a little input that gets the resolution, save_severy, Ra, restart
import argparse



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set parameters for the program.")

    # Add arguments for resolution (res), save_every, Re (Ra), restart, and nsteps with default values
    parser.add_argument("--res", type=int, default=12, help="Resolution (int)")
    parser.add_argument("--save_every", type=int, default=10, help="Save frequency (int)")
    parser.add_argument("--Ra", type=float, default=216000, help="Representing Re (float) but saved to 'Ra'")
    parser.add_argument("--restart", type=lambda x: (str(x).lower() == 'true'), default=False, help="Restart (bool)")
    parser.add_argument("--nsteps", type=int, default=100, help="Number of steps (int)")

    args = parser.parse_args()
    # Assign values from args to variables
    Ra = args.Ra
    res = args.res
    print("here")
    print(res)
    save_every = args.save_every
    restart = args.restart
    nsteps = args.nsteps
    # Print the received values (or process them further if needed)
    print(f"Received values:\nRes: {res}\nSave_every: {save_every}\nRa: {Ra}\nRestart: {restart}\nNsteps: {nsteps}")



# ### Set parameters to use 
k = 1.0 #### diffusivity     

boxLength = 1.5 
boxHeight = 1.0
tempMin   = 0.
tempMax   = 1.

viscosity = 1

tol = 1e-5


VDegree = 2
PDegree = 1
TDegree = 1

##########
# parameters needed for saving checkpoints
# can set outdir to None if you don't want to save anything
outdir = "./results" 
outfile = outdir + "/output" + str(res)


if (restart == True): 
    infile = None
else:
    infile = outfile

prev_res = res
if uw.mpi.rank == 0:
    os.makedirs(outdir, exist_ok = True)

## setup the mesh, solver and everything
meshbox = uw.meshing.UnstructuredSimplexBox(
                                                minCoords=(0.0, 0.0), 
                                                maxCoords=(boxLength, boxHeight), 
                                                cellSize=1.0 /res,
                                                qdegree = 3
                                        )
## the mesh variables
v_soln = uw.discretisation.MeshVariable("U", meshbox, meshbox.dim, degree=VDegree) # degree = 2
p_soln = uw.discretisation.MeshVariable("P", meshbox, 1, degree=PDegree) # degree = 1
t_soln = uw.discretisation.MeshVariable("T", meshbox, 1, degree=TDegree) # degree = 3
t_0 = uw.discretisation.MeshVariable("T0", meshbox, 1, degree=TDegree) # degree = 3

stokes = Stokes(
    meshbox,
    velocityField=v_soln,
    pressureField=p_soln,
    solver_name="stokes",
)

stokes.tolerance = tol


stokes.constitutive_model = uw.systems.constitutive_models.ViscousFlowModel(meshbox.dim)

stokes.constitutive_model.Parameters.viscosity=viscosity
stokes.saddle_preconditioner = 1.0 / viscosity


# velocity boundary conditions
stokes.add_dirichlet_bc((0.0,), "Right", (0,))
stokes.add_dirichlet_bc((0, ), "Left", (0,))

# now fot the top and bottom
# We have no-slip on the top and bottom, so the velocity on the top and bottom are zero
stokes.add_dirichlet_bc((0,0), "Top", (0,1))
stokes.add_dirichlet_bc((0,0), "Bottom", (0,1))


# add the body force term
buoyancy_force = Ra * t_soln.sym[0]
stokes.bodyforce = sympy.Matrix([0, buoyancy_force])


# Dealing with the temperature
adv_diff = uw.systems.AdvDiffusionSLCN(
    meshbox,
    u_Field=t_soln,
    V_Field=v_soln,
    solver_name="adv_diff",
)

adv_diff.constitutive_model = uw.systems.constitutive_models.DiffusionModel(meshbox.dim)
adv_diff.constitutive_model.Parameters.diffusivity = k
adv_diff.f = 1


adv_diff.theta = 0.5

# boundary conditions for temperature
# on the top with have isothermal
adv_diff.add_dirichlet_bc(0, "Top")
# on the bottom we have insulating (uw3 assumes this condition)

# on the left and right walls we have a reflective symmetry, which is the same
# as insulating, so, on the top and bottom uw3 also assumes the correct boundary conditions
adv_diff.petsc_options["pc_gamg_agg_nsmooths"] = 5

# %% [markdown]
# ### Set initial temperature field 
# 
# The initial temperature field is set to a sinusoidal perturbation. 

# %%
import math, sympy

if infile is None:
    pertStrength = 0.1
    deltaTemp = tempMax - tempMin

    with meshbox.access(t_soln, t_0):
        t_soln.data[:] = 0.
        t_0.data[:] = 0.

    with meshbox.access(t_soln):
        for index, coord in enumerate(t_soln.coords):
            # print(index, coord)
            pertCoeff = math.cos( math.pi * coord[0]/boxLength ) * math.sin( math.pi * coord[1]/boxLength )
        
            t_soln.data[index] = tempMin + deltaTemp*(boxHeight - coord[1]) + pertStrength * pertCoeff
            t_soln.data[index] = max(tempMin, min(tempMax, t_soln.data[index]))
            
        
    with meshbox.access(t_soln, t_0):
        t_0.data[:,0] = t_soln.data[:,0]

else:
    meshbox_prev = uw.meshing.UnstructuredSimplexBox(
                                                            minCoords=(0.0, 0.0), 
                                                            maxCoords=(boxLength, boxHeight), 
                                                            cellSize=1.0/prev_res,
                                                            qdegree = 3,
                                                            regular = False
                                                        )
    
    # T should have high degree for it to converge
    # this should have a different name to have no errors
    v_soln_prev = uw.discretisation.MeshVariable("U2", meshbox_prev, meshbox_prev.dim, degree=VDegree) # degree = 2
    p_soln_prev = uw.discretisation.MeshVariable("P2", meshbox_prev, 1, degree=PDegree) # degree = 1
    t_soln_prev = uw.discretisation.MeshVariable("T2", meshbox_prev, 1, degree=TDegree) # degree = 3

    # force to run in serial?
    
    v_soln_prev.read_from_vertex_checkpoint(infile + ".U.0.h5", data_name="U")
    p_soln_prev.read_from_vertex_checkpoint(infile + ".P.0.h5", data_name="P")
    t_soln_prev.read_from_vertex_checkpoint(infile + ".T.0.h5", data_name="T")

    #comm.Barrier()
    # this will not work in parallel?
    #v_soln_prev.load_from_h5_plex_vector(infile + '.U.0.h5')
    #p_soln_prev.load_from_h5_plex_vector(infile + '.P.0.h5')
    #t_soln_prev.load_from_h5_plex_vector(infile + '.T.0.h5')

    with meshbox.access(v_soln, t_soln, p_soln):    
        t_soln.data[:, 0] = uw.function.evaluate(t_soln_prev.sym[0], t_soln.coords)
        p_soln.data[:, 0] = uw.function.evaluate(p_soln_prev.sym[0], p_soln.coords)

        #for velocity, encounters errors when trying to interpolate in the non-zero boundaries of the mesh variables 
        v_coords = deepcopy(v_soln.coords)

        v_soln.data[:] = uw.function.evaluate(v_soln_prev.fn, v_coords)

    meshbox.write_timestep_xdmf(filename = outfile, meshVars=[v_soln, p_soln, t_soln], index=0)

    del meshbox_prev
    del v_soln_prev
    del p_soln_prev
    del t_soln_prev


# %% [markdown]
# ### Some plotting and analysis tools 

# %%
# check the mesh if in a notebook / serial
# allows you to visualise the mesh and the mesh variable
'''FIXME: change this so it's better'''

def v_rms(mesh = meshbox, v_solution = v_soln): 
    # v_soln must be a variable of mesh
    v_rms = math.sqrt(uw.maths.Integral(mesh, v_solution.fn.dot(v_solution.fn)).evaluate())
    return v_rms


#print(f'initial v_rms = {v_rms()}')

# %% [markdown]
# #### Surface integrals
# Since there is no uw3 function yet to calculate the surface integral, we define one.  \
# The surface integral of a function, $f_i(\mathbf{x})$, is approximated as:  
# 
# \begin{aligned}
# F_i = \int_V f_i(\mathbf{x}) S(\mathbf{x})  dV  
# \end{aligned}
# 
# With $S(\mathbf{x})$ defined as an un-normalized Gaussian function with the maximum at $z = a$  - the surface we want to evaluate the integral in (e.g. z = 1 for surface integral at the top surface):
# 
# \begin{aligned}
# S(\mathbf{x}) = exp \left( \frac{-(z-a)^2}{2\sigma ^2} \right)
# \end{aligned}
# 
# In addition, the full-width at half maximum is set to 1/res so the standard deviation, $\sigma$ is calculated as: 
# 
# \begin{aligned}
# \sigma = \frac{1}{2}\frac{1}{\sqrt{ 2 log 2}}\frac{1}{res} 
# \end{aligned}
# 

# %%
# function for calculating the surface integral 
def surface_integral(mesh, uw_function, mask_fn):

    calculator = uw.maths.Integral(mesh, uw_function * mask_fn)
    value = calculator.evaluate()

    calculator.fn = mask_fn
    norm = calculator.evaluate()

    integral = value / norm

    return integral

if infile == None:
    timeVal =  []    # time values
    vrmsVal =  []  # v_rms values 
    NuVal =  []      # Nusselt number values

    start_step = 0
    time = 0
else:
    with open(infile + "markers.pkl", 'rb') as f:
        loaded_data = pickle.load(f)
        timeVal = loaded_data[0]
        vrmsVal = loaded_data[1]
        NuVal = loaded_data[2]

    with open(infile+"step.pkl", 'rb') as f:
        start_step = pickle.load(f)
    
    with open(infile+"time.pkl", "rb") as f:
        time = pickle.load(f)

t_step = start_step



    
#### Convection model / update in time

print("started the time loop")
while t_step < nsteps + start_step:

    ## solve step
    stokes.solve(zero_init_guess=True) # originally True

    delta_t = 0.5 * stokes.estimate_dt() # originally 0.5
    adv_diff.solve(timestep=delta_t, zero_init_guess=False) # originally False

    ## update values
    vrmsVal.append(v_rms())
    timeVal.append(time)

    ## save values and print them
    if (t_step % save_every == 0 and t_step > 0) or (t_step+1==nsteps) :
        if uw.mpi.rank == 0:
            print("Timestep {}, dt {}, v_rms {}".format(t_step, timeVal[t_step], vrmsVal[t_step]), flush = True)
            print("Saving checkpoint for time step: ", t_step, "total steps: ", nsteps+start_step , flush = True)
            print(timeVal)
            plt.plot(timeVal, vrmsVal)
            plt.savefig(outdir + "vrms.png")
            plt.clf()
        meshbox.write_timestep_xdmf(filename = outfile, meshVars=[v_soln, p_soln, t_soln], index=0)
        meshbox.write_timestep_xdmf(filename = outfile, meshVars=[v_soln, p_soln, t_soln], index=t_step)

    if uw.mpi.rank == 0:
        with open(outfile+"markers.pkl", 'wb') as f:
            pickle.dump([timeVal, vrmsVal, NuVal], f)

    ## iterate

    time += delta_t
    t_step += 1

    ## here is where we will start next ime
    if (uw.mpi.rank == 0):
        with open(outfile+"step.pkl", "wb") as f:
            pickle.dump(t_step, f)

    if (uw.mpi.rank == 0):
        with open(outfile + "time.pkl", "wb") as f:
            pickle.dump(time, f)


# save final mesh variables in the run 
meshbox.write_timestep_xdmf(filename = outfile, meshVars=[v_soln, p_soln, t_soln], index=0)
if (uw.mpi.rank == 0):
    plt.plot(timeVal, vrmsVal)
    plt.savefig(outdir + "vrms.png")
    plt.clf()

