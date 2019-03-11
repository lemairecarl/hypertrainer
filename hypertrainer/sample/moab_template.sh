#!/bin/bash

# SOUMISSION DE LA  TACHE ---------------------------------
#PBS -N $HYPERTRAINER_NAME
#PBS -A scz-823-aa
#PBS -l walltime=0:01:00
#PBS -l nodes=1:gpus=1
#PBS -r n

#PBS -o $HYPERTRAINER_OUTFILE
#PBS -e $HYPERTRAINER_ERRFILE
# ---------------------------------------------------------

# Setup environment
source /clumeq/bin/enable_cc_cvmfs
module load python/3.6

cd $HYPERTRAINER_JOB_DIR
python $HYPERTRAINER_SCRIPT $HYPERTRAINER_CONFIGFILE