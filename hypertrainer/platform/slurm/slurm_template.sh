#!/bin/bash

# Request resources
#SBATCH --account def-rodrigu1
#SBATCH --time=0-0:10             # time (DD-HH:MM)
#SBATCH --mem=16000M               # memory (per node)
#SBATCH --cpus-per-task=4          # Number of cores (not cpus)
#SBATCH --gres=gpu:1               # Number of GPUs (per node)
#SBATCH -o $HYPERTRAINER_OUTFILE
#SBATCH -e $HYPERTRAINER_ERRFILE
# ---------------------------------------------------------

# Setup environment
module load python/3.6
source $HOME/venv/bin/activate

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