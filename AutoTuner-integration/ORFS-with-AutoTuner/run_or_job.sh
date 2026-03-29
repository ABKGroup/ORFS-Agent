#!/bin/bash

set -euo pipefail

if [[ -n "${OPENROAD_SETUP_SCRIPT:-}" && -f "${OPENROAD_SETUP_SCRIPT}" ]]; then
  # shellcheck source=/dev/null
  source "${OPENROAD_SETUP_SCRIPT}"
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

resolve_flow_home() {
  local current="$SCRIPT_DIR"
  while true; do
    if [[ -d "${current}/flow" ]]; then
      printf '%s\n' "${current}/flow"
      return 0
    fi
    if [[ "$current" == "/" ]]; then
      break
    fi
    current=$(dirname "$current")
  done
  return 1
}

# export OPENROAD_EXE=""
design="$1"
export CLK_PERIOD="$2"
export ABC_CLOCK_PERIOD_IN_PS="$2"
export CORE_UTILIZATION="$3"
export CORE_ASPECT_RATIO="$4"
tech="$5"
export PLACE_DENSITY_LB_ADDON="$6"
export TNS_END_PERCENT="$7"
export RECOVER_POWER="$8"
export SYNTH_HIERARCHICAL="$9"
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT="${10}"
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT="${11}"
export ENABLE_DPO="${12}"
export GPL_TIMING_DRIVEN="${13}"
export GPL_ROUTABILITY_DRIVEN="${14}"
export CTS_CLUSTER_SIZE="${15}"
export CTS_CLUSTER_DIAMETER="${16}"
## NG45: 0.5, ASAP7: 0.5
export PIN_LAYER_ADJUST="${17}"
## NG45: 0.25, ASAP7: 0.5
export UP_LAYER_ADJUST="${18}"
export WORK_HOME="${19}"
run_dir="${ORFS_AGENT_AUTOTUNER_DIR:-$(cd "${SCRIPT_DIR}/../AutoTuner" && pwd)}"
MAKE_HOME="${ORFS_AGENT_FLOW_HOME:-$(resolve_flow_home)}"
tech_lower="${tech,,}"

export NUM_CORES=4
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4

if [ "$#" -ge 20 ]; then
    export CACHED_NETLIST="${20}"
fi

export FASTROUTE_TCL="${run_dir}/autotune_configs/fastroute_${tech_lower}.tcl"
export RUN_DIR="${run_dir}/autotune_configs"

cd "$MAKE_HOME"
if [ "$tech_lower" == "ng45" ]; then
  export IO_PLACER_H="metal5 metal3"
  export IO_PLACER_V="metal6 metal4"
elif [ "$tech_lower" == "asap7" ]; then
  export IO_PLACER_H="M4 M6"
  export IO_PLACER_V="M5 M7"
elif [ "$tech_lower" == "sky130hd" ]; then
  export IO_PLACER_H="met3"
  export IO_PLACER_V="met2"
fi

echo "run_dir: $run_dir"
echo "MAKE HOME: $MAKE_HOME"
echo "WORK HOME: $WORK_HOME"
## Config file
echo "CONFIG: ${RUN_DIR}/${design}_${tech_lower}.mk"

job_name="DESIGN_${design}__CLK_${CLK_PERIOD}__UTIL_${CORE_UTILIZATION}"
job_name="${job_name}__AR_${CORE_ASPECT_RATIO}"
job_name="${job_name}__TECH_${tech}__LB_ADDON_${PLACE_DENSITY_LB_ADDON}"
job_name="${job_name}__TIMING_EFFORT_${TNS_END_PERCENT}"
job_name="${job_name}__POWER_EFFORT_${RECOVER_POWER}"
job_name="${job_name}__HIER_SYNTH_${SYNTH_HIERARCHICAL}"
job_name="${job_name}__GP_PAD_${CELL_PAD_IN_SITES_GLOBAL_PLACEMENT}"
job_name="${job_name}__DP_PAD_${CELL_PAD_IN_SITES_DETAIL_PLACEMENT}"
job_name="${job_name}__RD_${GPL_ROUTABILITY_DRIVEN}"
job_name="${job_name}__TD_${GPL_TIMING_DRIVEN}__DPO_${ENABLE_DPO}"
job_name="${job_name}__CTS_CSIZE_${CTS_CLUSTER_SIZE}"
job_name="${job_name}__CTS_CDIA_${CTS_CLUSTER_DIAMETER}"
job_name="${job_name}__PIN_ADJ_${PIN_LAYER_ADJUST}"
job_name="${job_name}__UP_ADJ_${UP_LAYER_ADJUST}"

export FLOW_VARIANT="${job_name}"
make tunereport PRIVATE_DIR="${RUN_DIR}" DESIGN_CONFIG="${RUN_DIR}/${design}_${tech_lower}.mk"
