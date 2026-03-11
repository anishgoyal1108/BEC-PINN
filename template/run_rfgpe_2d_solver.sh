#!/bin/bash
#
# script for running the split-step Crank-Nicolson GP solver
#
clear
#
# set environment for openmp
#
ulimit -s unlimited
export OMP_STACKSIZE=512M
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-$(nproc)}
#
# compiles the program
#
make clean
make
#
# run the gpe solver program
#
echo "RUNNING REAL TIME PROGRAM"
./rfgpe_2d_solver


