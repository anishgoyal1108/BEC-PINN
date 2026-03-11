#!/bin/bash
#
# script for saving the results of the 2d gpe solver (dtap)
# Optional files only moved if present.
#
FILE=./sim_folder
if [ -d "$FILE" ]; then
    echo "The $FILE directory already exists, please rename it first."
else
    echo "No $FILE directory exists, creating it now."
    mkdir ./sim_folder
    cp ./*.f ./sim_folder/. 2>/dev/null || true
    cp ./rfgpe_2d_solver_general_inputs.dat ./sim_folder/. 2>/dev/null || true
    cp ./dtap_inputs.dat ./sim_folder/. 2>/dev/null || true
    cp ./*.sh ./sim_folder/. 2>/dev/null || true
    cp ./*.gnu ./sim_folder/. 2>/dev/null || true
    cp ./Makefile ./sim_folder/. 2>/dev/null || true
    for f in ./wf_ascii_???.dat; do [ -e "$f" ] && mv "$f" ./sim_folder/.; done || true
    [ -f ./initial_wf.dat ] && cp ./initial_wf.dat ./sim_folder/. || true
    [ -f ./final_wf.dat ] && cp ./final_wf.dat ./sim_folder/. || true
    [ -f ./circulation.dat ] && mv ./circulation.dat ./sim_folder/. || true
    [ -f ./initial_pot.dat ] && mv ./initial_pot.dat ./sim_folder/. || true
    [ -f ./final_pot.dat ] && mv ./final_pot.dat ./sim_folder/. || true
    for f in ./*.gif; do [ -e "$f" ] && mv "$f" ./sim_folder/.; done || true
    for f in ./*.out; do [ -e "$f" ] && mv "$f" ./sim_folder/.; done || true
fi
exit 0
