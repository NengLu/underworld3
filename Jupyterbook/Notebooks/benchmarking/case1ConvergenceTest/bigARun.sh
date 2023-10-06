#!/bin/bash
mkdir case1a
cp generalRunner.sh case1a/generalRunner.sh
cp autoanalyser.py case1a/autoanalyser.py 
cp case1General.py case1a/case1General.py
cd case1a



## you can change the settings for your case by setting the following parameters for your run
RA=10000 ## Rayeligh number of your simulation
NUM_LOOPS=100 ## number of loops the simulation will do. At the end each loop, the program saves and restarts from the ground up
## the number of total timesteps will be NUM_LOOPS * NUM_STEPS
STOPPING_TIME=0.3 ## time you want it to stop at 
T_DEGREE=3
Q_DEGREE=4
WIDTH=1
SPEEDUP=1
USE_SWARM=False

## loop over each of the resolutions
for i in 6 8 10 12 14 16
do
    sh generalRunner.sh --res $i --Ra $RA --num_loops $NUM_LOOPS --stoppingTime $STOPPING_TIME --TDegree $T_DEGREE --qdegree $Q_DEGREE --width $WIDTH --speedUp $SPEEDUP --useSwarm $USE_SWARM &
done
wait ## wait for all proccesses to stop 

## go analyse all of them
python3 autoanalyser.py
