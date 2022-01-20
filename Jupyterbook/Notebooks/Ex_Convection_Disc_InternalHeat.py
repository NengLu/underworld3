# # Convection in a disc with internal heating and rigid boundaries
#
#

# +
import petsc4py
from petsc4py import PETSc

import underworld3 as uw
from underworld3.systems import Stokes
from underworld3 import function

import numpy as np

# options = PETSc.Options()
# options["help"] = None
# options["pc_type"]  = "svd"
# options["dm_plex_check_all"] = None
# options.getAll()

# +
import meshio

meshball = uw.meshes.SphericalShell(dim=2, 
                                    radius_inner=0.0,
                                    radius_outer=1.0, cell_size=0.05,
                                    degree=1, verbose=False)

meshball.dm.view()


# +
# check the mesh if in a notebook / serial

import mpi4py

if mpi4py.MPI.COMM_WORLD.size==1:    
    import numpy as np
    import pyvista as pv
    import vtk

    pv.global_theme.background = 'white'
    pv.global_theme.window_size = [750, 750]
    pv.global_theme.antialiasing = True
    pv.global_theme.jupyter_backend = 'pythreejs'
    pv.global_theme.smooth_shading = True
    pv.global_theme.camera['viewup'] = [0.0, 1.0, 0.0] 
    pv.global_theme.camera['position'] = [0.0, 0.0, -5.0]     
    
    pvmesh = meshball.mesh2pyvista()
    
    pl = pv.Plotter()

    # pl.add_mesh(pvmesh,'Black', 'wireframe', opacity=0.5)
    pl.add_mesh(pvmesh, cmap="coolwarm", edge_color="Black", show_edges=True, 
                  use_transparency=False, opacity=0.5)

    pl.show()
# -

v_soln = uw.mesh.MeshVariable('U',    meshball, meshball.dim, degree=2 )
p_soln = uw.mesh.MeshVariable('P',    meshball, 1, degree=1 )
t_soln = uw.mesh.MeshVariable("T",    meshball, 1, degree=3)
t_0    = uw.mesh.MeshVariable("T0",   meshball, 1, degree=3)


# +
# swarm  = uw.swarm.Swarm(mesh=meshball)
# T1 = uw.swarm.SwarmVariable("Tminus1", swarm, 1)
# X1 = uw.swarm.SwarmVariable("Xminus1", swarm, 2)
# swarm.populate(fill_param=3)


# +
# Create Stokes object

stokes = Stokes(meshball, velocityField=v_soln, pressureField=p_soln, 
                u_degree=2, p_degree=1, solver_name="stokes", verbose=True)

# Set solve options here (or remove default values
# stokes.petsc_options.getAll()
stokes.petsc_options.delValue("ksp_monitor")

# Constant visc
stokes.viscosity = 1.

# Velocity boundary conditions
stokes.add_dirichlet_bc( (0.,0.), "Upper" , (0,1) )


# +
# Create a density structure / buoyancy force
# gravity will vary linearly from zero at the centre 
# of the sphere to (say) 1 at the surface

import sympy

radius_fn = sympy.sqrt(meshball.rvec.dot(meshball.rvec)) # normalise by outer radius if not 1.0
unit_rvec = meshball.rvec / (1.0e-10+radius_fn)
gravity_fn = radius_fn

# Some useful coordinate stuff 

x = meshball.N.x
y = meshball.N.y

r  = sympy.sqrt(x**2+y**2)
th = sympy.atan2(y+1.0e-5,x+1.0e-5)

Rayleigh = 1.0e4
H_int = 100
expt_name = "Disc_Ra1e4_H10"

# +
# Create adv_diff object

# Set some things
k = 1.0
h = 10
r_i = 0.5
r_o = 1.0

adv_diff = uw.systems.AdvDiffusion(meshball, 
                                   u_Field=t_soln, 
                                   V_Field=v_soln,
                                   solver_name="adv_diff", 
                                   degree=3,
                                   verbose=False)

adv_diff.k = k
adv_diff.f = h
adv_diff.theta = 0.5
adv_diff.petsc_options["pc_gamg_agg_nsmooths"]= 1


# +
# Define T boundary conditions via a sympy function

import sympy
abs_r  = sympy.sqrt(meshball.rvec.dot(meshball.rvec))
init_t = 0.01 * sympy.sin(15.0*th) * sympy.sin(np.pi*(r-r_i)/(r_o-r_i)) + (r_o-r)/(r_o-r_i)

adv_diff.add_dirichlet_bc(  0.0,  "Upper" )

with meshball.access(t_0, t_soln):
    t_0.data[...] = uw.function.evaluate(init_t, t_0.coords).reshape(-1,1)
    t_soln.data[...] = t_0.data[...]
# +
buoyancy_force = Rayleigh * t_soln.fn 
stokes.bodyforce = gravity_fn * unit_rvec * buoyancy_force  

# check the stokes solve converges
stokes.solve()

# +
# Check the diffusion part of the solve converges 
# adv_diff.solve(timestep=0.01*stokes.estimate_dt())
# -




# +
# check the mesh if in a notebook / serial

import mpi4py

if mpi4py.MPI.COMM_WORLD.size==1:

    import numpy as np
    import pyvista as pv
    import vtk

    pv.global_theme.background = 'white'
    pv.global_theme.window_size = [750, 750]
    pv.global_theme.antialiasing = True
    pv.global_theme.jupyter_backend = 'pythreejs'
    pv.global_theme.smooth_shading = True
    
    pv.start_xvfb()
    
    pvmesh = meshball.mesh2pyvista(elementType=vtk.VTK_TRIANGLE)

    with meshball.access():
        usol = stokes.u.data.copy()
  
    pvmesh.point_data["T"]  = uw.function.evaluate(t_soln.fn, meshball.data)
 
    arrow_loc = np.zeros((stokes.u.coords.shape[0],3))
    arrow_loc[:,0:2] = stokes.u.coords[...]
    
    arrow_length = np.zeros((stokes.u.coords.shape[0],3))
    arrow_length[:,0:2] = usol[...] 
    
    pl = pv.Plotter()

    # pl.add_mesh(pvmesh,'Black', 'wireframe')
    
    pl.add_mesh(pvmesh, cmap="coolwarm", edge_color="Black", show_edges=True, scalars="T",
                  use_transparency=False, opacity=0.5)
    
    pl.add_arrows(arrow_loc, arrow_length, mag=0.01)
    #pl.add_arrows(arrow_loc2, arrow_length2, mag=1.0e-1)
    
    # pl.add_points(pdata)

    pl.show(cpos="xy")
# -




def plot_T_mesh(filename):

    import mpi4py

    if mpi4py.MPI.COMM_WORLD.size==1:

        import numpy as np
        import pyvista as pv
        import vtk

        pv.global_theme.background = 'white'
        pv.global_theme.window_size = [750, 750]
        pv.global_theme.antialiasing = True
        pv.global_theme.jupyter_backend = 'pythreejs'
        pv.global_theme.smooth_shading = True
        pv.global_theme.camera['viewup'] = [0.0, 1.0, 0.0] 
        pv.global_theme.camera['position'] = [0.0, 0.0, 5.0] 

        pvmesh = meshball.mesh2pyvista(elementType=vtk.VTK_TRIANGLE)

        points = np.zeros((t_soln.coords.shape[0],3))
        points[:,0] = t_soln.coords[:,0]
        points[:,1] = t_soln.coords[:,1]

        point_cloud = pv.PolyData(points)

        with meshball.access():
            point_cloud.point_data["T"] = t_soln.data.copy()

        with meshball.access():
            usol = stokes.u.data.copy()

        pvmesh.point_data["T"]  = uw.function.evaluate(t_soln.fn, meshball.data)

        arrow_loc = np.zeros((stokes.u.coords.shape[0],3))
        arrow_loc[:,0:2] = stokes.u.coords[...]

        arrow_length = np.zeros((stokes.u.coords.shape[0],3))
        arrow_length[:,0:2] = usol[...] 

        pl = pv.Plotter()


        pl.add_arrows(arrow_loc, arrow_length, mag=0.00002, opacity=0.75)

        pl.add_points(point_cloud, cmap="coolwarm", 
                      render_points_as_spheres=False,
                      point_size=10, opacity=0.66
                    )
        

        pl.add_mesh(pvmesh,'Black', 'wireframe', opacity=0.75)

        pl.remove_scalar_bar("T")
        pl.remove_scalar_bar("mag")

        pl.screenshot(filename="{}.png".format(filename), window_size=(1280,1280), 
                      return_img=False)
        # pl.show()

# +
# Convection model / update in time

expt_name="output/{}".format(expt_name)

for step in range(0,250):
    
    stokes.solve()
    
    delta_t = 5.0*stokes.estimate_dt() 
    adv_diff.solve(timestep=delta_t)
    
    # stats then loop
    tstats = t_soln.stats()
    
    if mpi4py.MPI.COMM_WORLD.rank==0:
        print("Timestep {}, dt {}".format(step, delta_t))
        print(tstats)
        
#     plot_T_mesh(filename="{}_step_{}".format(expt_name,step))


    savefile = "{}_ts_{}.h5".format(expt_name,step)
    meshball.save(savefile)
    v_soln.save(savefile)
    t_soln.save(savefile)
    meshball.generate_xdmf(savefile)
    

    
# -


# savefile = "output_conv/convection_cylinder.h5".format(step) 
# meshball.save(savefile)
# v_soln.save(savefile)
# t_soln.save(savefile)
# meshball.generate_xdmf(savefile)


# +

import mpi4py

if mpi4py.MPI.COMM_WORLD.size==1:

    import numpy as np
    import pyvista as pv
    import vtk

    pv.global_theme.background = 'white'
    pv.global_theme.window_size = [750, 750]
    pv.global_theme.antialiasing = True
    pv.global_theme.jupyter_backend = 'pythreejs'
    pv.global_theme.smooth_shading = True
    
    pv.start_xvfb()
    
    pvmesh = meshball.mesh2pyvista(elementType=vtk.VTK_TRIANGLE)
    
    
    points = np.zeros((t_soln.coords.shape[0],3))
    points[:,0] = t_soln.coords[:,0]
    points[:,1] = t_soln.coords[:,1]

    point_cloud = pv.PolyData(points)

    with meshball.access():
        point_cloud.point_data["T"] = t_soln.data.copy()


    with meshball.access():
        usol = stokes.u.data.copy()
  
    pvmesh.point_data["T"]  = uw.function.evaluate(t_soln.fn, meshball.data)
 
    arrow_loc = np.zeros((stokes.u.coords.shape[0],3))
    arrow_loc[:,0:2] = stokes.u.coords[...]
    
    arrow_length = np.zeros((stokes.u.coords.shape[0],3))
    arrow_length[:,0:2] = usol[...] 
    
    pl = pv.Plotter()
   
    pl.add_arrows(arrow_loc, arrow_length, mag=0.00002, opacity=0.75)
    #pl.add_arrows(arrow_loc2, arrow_length2, mag=1.0e-1)
    
    
    pl.add_points(point_cloud, cmap="coolwarm", 
                  render_points_as_spheres=True,
                  point_size=7.5, opacity=0.25
                )
    
    
    pl.add_mesh(pvmesh,'Black', 'wireframe', opacity=0.75)


    pl.show(cpos="xy")
# -




