#######################################################################
#                                                                     #
# Makefile for sscn_gpe_solver, a program that solves the 3D time-dep-#
# dent Gross-Pitaevskii equations using the split-step Crank-Nicolson #
# algorithm.                                                          #
#                                                                     #
#######################################################################
#
# source file list
#
src_files = rfgpe_2d_solver.f 
#
# object file list
#
obj_files = rfgpe_2d_solver.o  
#
# print file list
#
print_files = rfgpe_2d_solver.f 
#
# compile command (default: gfortran with OpenMP)
#
f77 = gfortran -march=native -ffast-math -funroll-loops -fopenmp -O3 -cpp
#
# compile flags
#
f77_flags = -c
#
# NVIDIA nvfortran compiler for OpenACC (GPU acceleration)
#
nvf77 = nvfortran -fast -mp -acc -Minfo=accel,mp -gpu=mem:managed -Mpreprocess -DUSE_GPU
nvf77_flags = -c
#
# rule to build main target: sscn_gpe_solver (default: OpenMP/CPU)
#
rfgpe_2d_solver : $(obj_files)
	$(f77) $(obj_files) -o rfgpe_2d_solver
#
# rule for sscn_gpe_solver.o
#
rfgpe_2d_solver.o : rfgpe_2d_solver.f
	$(f77) $(f77_flags) rfgpe_2d_solver.f
#
# GPU target: build with nvfortran and OpenACC
#
gpu : rfgpe_2d_solver.f
	$(nvf77) $(nvf77_flags) rfgpe_2d_solver.f
	$(nvf77) rfgpe_2d_solver.o -o rfgpe_2d_solver_gpu
#
# print directive
#
print : 
	cat $(print_files) > rfgpe_2d_solver_source_code
	a2ps rfgpe_2d_solver_source_code -o rfgpe_2d_solver_source_code.ps
	/bin/rm -f rfgpe_2d_solver_source_code
#
# clean
#
clean : 
	/bin/rm -f $(obj_files) core rfgpe_2d_solver rfgpe_2d_solver_gpu rfgpe_2d_solver_source_code.ps

