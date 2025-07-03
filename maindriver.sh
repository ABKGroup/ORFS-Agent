#!/bin/bash

# Default values
TOTAL_ITERS=6
PARALLEL_RUNS=50
TIMEOUT="45m"
TOTAL_CPUS=110
TOTAL_RAM=220
ECP_WEIGHT=0.5
WL_WEIGHT=0.5
ECP_WEIGHT_SURROGATE=0.5
WL_WEIGHT_SURROGATE=0.5

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -p|--platform)
            platform="$2"
            shift 2
            ;;
        -d|--design)
            design="$2"
            shift 2
            ;;
        -i|--iterations)
            TOTAL_ITERS="$2"
            shift 2
            ;;
        -r|--parallel-runs)
            PARALLEL_RUNS="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -o|--objective)
            objective="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$platform" || -z "$design" ]]; then
    echo "Usage: $0 -p <platform> -d <design> [-i iterations] [-r parallel_runs] [-t timeout] [-o objective]"
    echo "  platform: asap7 or sky130hd"
    echo "  design: aes, ibex, or jpeg"
    echo "  iterations: total number of iterations (default: 6)"
    echo "  parallel_runs: number of parallel runs (default: 50)"
    echo "  timeout: timeout per run (default: 45m)"
    echo "  objective: ecp, wl, or weighted (default: ecp)"
    exit 1
fi

# Set default objective if not specified
objective=${objective:-"ECP"}

# Convert objective to uppercase for consistency
objective="${objective^^}"

# Validate platform
if [[ "$platform" != "asap7" && "$platform" != "sky130hd" ]]; then
    echo "Error: platform must be either asap7 or sky130hd"
    exit 1
fi

# Validate design
if [[ "$design" != "aes" && "$design" != "ibex" && "$design" != "jpeg" ]]; then
    echo "Error: design must be one of: aes, ibex, jpeg"
    exit 1
fi

# Validate objective
if [[ "$objective" != "ECP" && "$objective" != "DWL" && "$objective" != "COMBO" ]]; then
    echo "Error: objective must be one of: ECP, DWL, COMBO"
    exit 1
fi

# Validate weights sum to 1
if [[ "$objective" == "COMBO" ]]; then
    # Ensure jq is installed
    if ! command -v jq &> /dev/null; then
        echo "Error: jq is required but not installed. Please install jq."
        exit 1
    fi

    # Read weights from opt_config.json
    weights=$(jq -r \
      --arg pdk "$platform" \
      --arg design "$design" \
      --arg goal "$objective" \
      '.configurations[] | select(.platform == $pdk and .design == $design and .goal == $goal)' \
      opt_config.json)

    if [[ -z "$weights" || "$weights" == "null" ]]; then
        echo "Error: Could not find weights for platform $platform and design $design in opt_config.json."
        exit 1
    fi

    # Extract real metric weights
    ECP_WEIGHT=$(echo "$weights" | jq -r '.weights.ecp')
    WL_WEIGHT=$(echo "$weights" | jq -r '.weights.dwl')

    # Extract surrogate metric weights
    ECP_WEIGHT_SURROGATE=$(echo "$weights" | jq -r '.weights_surrogate.ecp')
    WL_WEIGHT_SURROGATE=$(echo "$weights" | jq -r '.weights_surrogate.dwl')

    # Validate that the weights sum to 1
    weight_sum=$(echo "$ECP_WEIGHT + $WL_WEIGHT" | bc -l)
    if (( $(echo "$weight_sum != 1" | bc -l) )); then
        echo "Error: ECP_WEIGHT ($ECP_WEIGHT) and WL_WEIGHT ($WL_WEIGHT) must sum to 1."
        exit 1
    fi

    surrogate_weight_sum=$(echo "$ECP_WEIGHT_SURROGATE + $WL_WEIGHT_SURROGATE" | bc -l)
    if (( $(echo "$surrogate_weight_sum != 1" | bc -l) )); then
        echo "Error: ECP_WEIGHT_SURROGATE ($ECP_WEIGHT_SURROGATE) and WL_WEIGHT_SURROGATE ($WL_WEIGHT_SURROGATE) must sum to 1."
        exit 1
    fi

    # Export weights for use in optimize.py
    export ECP_WEIGHT
    export WL_WEIGHT
    export ECP_WEIGHT_SURROGATE
    export WL_WEIGHT_SURROGATE
fi

# Calculate resources per run
cpus_per_run=$(( TOTAL_CPUS / PARALLEL_RUNS ))
ram_per_run=$(( TOTAL_RAM / PARALLEL_RUNS ))

# Ensure minimum resources
if [[ $cpus_per_run -lt 2 ]]; then
    echo "Warning: Not enough CPUs. Reducing parallel runs to $((TOTAL_CPUS / 2))"
    PARALLEL_RUNS=$((TOTAL_CPUS / 2))
    cpus_per_run=2
fi

if [[ $ram_per_run -lt 4 ]]; then
    echo "Warning: Not enough RAM. Reducing parallel runs to $((TOTAL_RAM / 4))"
    PARALLEL_RUNS=$((TOTAL_RAM / 4))
    ram_per_run=4
fi

# Export resource variables for child scripts
export PARALLEL_RUNS
export CPUS_PER_RUN=$cpus_per_run
export RAM_PER_RUN=$ram_per_run
export TIMEOUT

# Create logs directory
mkdir -p logs

# Define the line numbers for DESIGN_CONFIG lines
start_line=9
end_line=15

# Function to comment all DESIGN_CONFIG lines
comment_all_design_configs() {
    sed -i "${start_line},${end_line} s/^\([^#]\)/#\1/" Makefile
}

# Function to uncomment a specific DESIGN_CONFIG line
uncomment_design_config_line() {
    local line_num=$1
    sed -i "${line_num} s/^#//" Makefile
}

# Comment all DESIGN_CONFIG lines first
comment_all_design_configs

# Find the line number matching the desired DESIGN_CONFIG
config_pattern="DESIGN_CONFIG=./designs/${platform}/${design}/config_\\\$(INT_PARAM).mk"
line_num=$(grep -n "$config_pattern" Makefile | cut -d: -f1)

if [ -n "$line_num" ]; then
    # Uncomment the specific DESIGN_CONFIG line
    uncomment_design_config_line $line_num
else
    echo "Error: Could not find DESIGN_CONFIG line for platform: $platform, design: $design"
    exit 1
fi

# Function to create backup
create_backup() {
    local platform=$1
    local design=$2
    local iteration=$3
    local backup_dir="../result_dump_${iteration}"
    
    echo "Creating backup for iteration ${iteration}..."
    mkdir -p "$backup_dir"
    
    # Move config and constraint files
    mv designs/${platform}/${design}/config_*.mk "$backup_dir"/ 2>/dev/null
    mv designs/${platform}/${design}/constraint_*.sdc "$backup_dir"/ 2>/dev/null
    if [[ "$platform" == "asap7" && "$design" == "jpeg" ]]; then
        mv designs/${platform}/${design}/jpeg_encoder15_7nm_*.sdc "$backup_dir"/ 2>/dev/null
    fi
    
    # Move logs
    mkdir -p "$backup_dir/logs_dump"
    mv logs/${platform}/${design}/* "$backup_dir/logs_dump"/ 2>/dev/null
    
    # Move results
    mkdir -p "$backup_dir/results_dump"
    mv results/${platform}/${design}/* "$backup_dir/results_dump"/ 2>/dev/null
    
    # Move platform_design log files from current directory
    mv ${platform}_${design}*.log "$backup_dir"/ 2>/dev/null
    
    echo "Backup created in ${backup_dir}"
}

# Main iteration loop
for i in $(seq 1 $TOTAL_ITERS); do
    echo "Starting iteration $i of $TOTAL_ITERS"
    
    # Run sequential phase
    ./run_sequential.sh "$platform" "$design" "$PARALLEL_RUNS" "$i"
    
    # Run parallel phase with timeout
    timeout "$TIMEOUT" ./run_parallel.sh "$platform" "$design" "$PARALLEL_RUNS" || true
    
    # Kill any remaining parallel jobs
    pkill -P $$ || true
    
    # Create backup of this iteration's results
    create_backup "$platform" "$design" "$i"
    
    # Generate constraints for next iteration (skip for last iteration)
    if [ "$i" -lt "$TOTAL_ITERS" ]; then
        echo "Running optimization for next iteration..."
        python3 optimize.py "$platform" "$design" "$objective" "$PARALLEL_RUNS"
    fi
done

echo "All iterations complete"