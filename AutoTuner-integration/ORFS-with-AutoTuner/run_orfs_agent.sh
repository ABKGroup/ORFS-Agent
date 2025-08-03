#!/bin/bash -i
design=$1
pdk=$2
goal=$3
module load anaconda3/23.7.1
source $CONDA_SH
conda activate /home/tool/anaconda/envs/orfs_agent
python orfs_agent.py $design $pdk $goal
