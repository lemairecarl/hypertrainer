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
source $HOME/hypertrainer/venv/bin/activate

# Resolve script path
SCRIPT_ABS_PATH=$(python3 - << EOF
from pathlib import Path
for p in '$HYPERTRAINER_PATH'.split(':'):
	pp = Path(p) / '$HYPERTRAINER_SCRIPT'
	if pp.exists():
		print(pp.absolute())
		break
EOF
)

cd $HYPERTRAINER_JOB_DIR
python $SCRIPT_ABS_PATH $HYPERTRAINER_CONFIGFILE