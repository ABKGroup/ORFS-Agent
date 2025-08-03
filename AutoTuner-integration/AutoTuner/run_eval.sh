#!/bin/bash
## Add OPENROAD_EXE path if you have different exe file
# export OPENROAD_EXE=""
export DESIGN_DEF=$(readlink -f "$1")
export DESIGN_SDC=$(readlink -f "$2")
DESIGN=$3
export RUN_DIR=$(readlink -f ./autotune_configs)
export DESIGN_CONFIG="${RUN_DIR}/${DESIGN}_nangate45.mk"

## Provide the full path of OpenROAD-flow-scripts/flow
MAKE_HOME=""
export FLOW_VARIANT="eval_${DESIGN}"
cd $MAKE_HOME
make eval_update_design PRIVATE_DIR=${RUN_DIR}
