#!/bin/bash

# Ensure correct number of arguments
if [ $# -ne 3 ]; then
    echo "Usage: $0 <platform> <design> <parallel_runs>"
    echo "platform: asap7 or sky130hd"
    echo "design: aes, ibex, or jpeg"
    echo "parallel_runs: number of parallel runs"
    exit 1
fi

platform=$1
design=$2
parallel_runs=$3

# Validate platform and design
if [[ ! "$platform" =~ ^(asap7|sky130hd)$ ]]; then
    echo "Error: platform must be asap7 or sky130hd"
    exit 1
fi

if [[ ! "$design" =~ ^(aes|ibex|jpeg)$ ]]; then
    echo "Error: design must be aes, ibex, or jpeg"
    exit 1
fi

# Get resource limits from environment or use defaults
TIMEOUT=${TIMEOUT:-"45m"}
TOTAL_CPUS=${TOTAL_CPUS:-110}
TOTAL_RAM=${TOTAL_RAM:-220}

# Calculate resources per run
cpus_per_run=$((TOTAL_CPUS / parallel_runs))
ram_per_run=$((TOTAL_RAM / parallel_runs))

# Ensure minimum resources
if [ $cpus_per_run -lt 2 ]; then
    echo "Warning: Not enough CPUs. Reducing parallel runs to $((TOTAL_CPUS / 2))"
    parallel_runs=$((TOTAL_CPUS / 2))
    cpus_per_run=2
fi

if [ $ram_per_run -lt 4 ]; then
    echo "Warning: Not enough RAM. Reducing parallel runs to $((TOTAL_RAM / 4))"
    parallel_runs=$((TOTAL_RAM / 4))
    ram_per_run=4
fi

# Function to run a single task
run_task() {
    local task_id=$1
    local start_cpu=$2
    local end_cpu=$3
    
    # Set CPU affinity and memory limits
    taskset -c $start_cpu-$end_cpu make INT_PARAM=$task_id \
        > "logs/${platform}_${design}_run${task_id}.log" 2>&1 &
    
    echo "Started task $task_id on CPUs $start_cpu-$end_cpu"
}

# Create logs directory
mkdir -p logs

# Start parallel tasks
for ((i=1; i<=$parallel_runs; i++)); do
    start_cpu=$(( (i-1) * cpus_per_run ))
    end_cpu=$(( start_cpu + cpus_per_run - 1 ))
    run_task $i $start_cpu $end_cpu
done

# Wait for all background tasks to complete
wait

echo "All tasks completed" 