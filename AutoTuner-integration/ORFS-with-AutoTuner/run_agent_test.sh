#!/bin/bash -i
design=$1
pdk=$2
goal=$3
module load anaconda3/23.7.1
source $CONDA_SH
conda activate /home/tool/anaconda/envs/orfs_agent
python analyst_agent_workbench.py aes asap7 ECP_final --num_final_suggestions 5 --max_agent_calls 15 
