# underworld3

## Documentation

The underworld documentation is in two parts: the user manual / theory manual is a jupyterbook that is built from this repository automatically from the sources in the `Jupyterbook` directory

- https://underworldcode.github.io/underworld3/FrontPage.html

The API documentation is built ... 


## Building

Refer to the Dockerfile for uw3 build instructions.  

For development, building inplace will prob be preferable.  Remove
any existing installations using `clean.sh` then run

```shell
python3 setup.py develop 
```

The in-place `pip` installation may be helpful for developers (after the above)

```shell
pip install -e .
```


For in place usage, you will usually need to set an appropriate PYTHONPATH.


## Development milestones

Reproduce the existing UW2 examples and extend to spherical / cylindrical

- [x] Spherical stokes
- [x] Buoyancy driven stokes (various geometries)
- [x] Compositional Buoyancy (Rayleigh-Taylor) level set
- [x] Compositional Buoyancy (Rayleigh-Taylor) via swarms (benchmark)
- [x] Advection/diffusion (slcn)
- [x] Advection/diffusion (swarm)
- [x] Constant viscosity convection
- [x] Convection, strongly temp-dep viscosity (stagnant lid)
- [x] Non-linear viscosity convection 
- [ ] Quantitative Convection benchmarks (various geometries)
- [ ] Viscoelasticity (linear) benchmarks 
- [x] Inertial terms (Navier-Stokes benchmarks)
- [x] Anisotropic viscosity


### Checklist

Ingredients in achieving the above

[[T](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L174)] Topology & Meshing
- [x] spherical annulus - https://github.com/julesghub/cubie
- [x] Cartesian
- [x] Different element types (at least Linear / Quadratic & Hex, Tet)

[[D](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L268)] Disc 

- [x] Cont Galerkin 
- [ ] ~Disc Galerkin~
- [x] Semi-lagrangian
- [x] Free-slip BC on surface

[[P](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L73)] Physics

- [x] Stokes-Boussinesq
- [x] Temp-dep rheology
- [x] Buoyancy driven convection
- [x] Non-linear viscosity / yielding
- [ ] Viscoelasticity
- [x] Navier-Stokes / interial terms
- [ ] Energy equation, resolve bdry layers
- [ ] ~kermit the 🐸~

[[S](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L354)] Solvers

- [x] SNES - generic
- [x] Block Stokes solvers
- [x] Semi-lagrangian
- [x] Swarm-projected history tems
- [ ] ~TS~  (address this later)

PIC for composition
- [x] Viscosity, buoyancy, ... 
- [x] Nearest neighbour (k-d tree ? 🌳 )
- [ ] ~2D - L2 projection into FEM space (Petsc shall provide)~
- [ ] ~3D - L2 projection into FEM space (Petsc shall provide but not in 3D)~
- [x] Petsc Integrals
- [x] uw.function evaluate (for Sympy functions)

[[O1](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L218) [O2](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L382)] Output

- [x] HDF5 -> XDMF -> Paraview
- [ ] LavaVu  

[[V](https://github.com/underworldcode/underworld3/blob/master/src/ex1.c#L35)] Exact solutions
- [ ] MMS
- [ ] Analytical 
  - https://www.solid-earth-discuss.net/se-2017-71/se-2017-71.pdf
  -https://www.researchgate.net/publication/304784132_Benchmark_solutions_for_Stokes_flows_in_cylindrical_and_spherical_geometry


### Tasks

  - [x] Solver options - robust for viscosity contrasts, customisable and quick.
  - [ ] Investigate generalising context managers. 
  - [ ] Proper quadratic mesh interpolations for deformed meshes.
  - [ ] DMLabels for higher order meshes, ie. using a label to set values in a Vec. How do you label mid-points?
  - [ ] Further integrals/reduction operators on fields variables.
  - [x] nKK nanoflann exposure.
  - [ ] create developer docs for software stack and general development strategy.
