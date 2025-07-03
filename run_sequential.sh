#!/bin/bash

# Validate arguments
if [[ $# -ne 4 ]]; then
    echo "Usage: $0 <platform> <design> <parallel_runs> <iteration>"
    exit 1
fi

platform=$1
design=$2
parallel_runs=$3
iteration=$4

# Get the absolute path to the script's directory
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Define CSV file with an absolute path
csv_file="${SCRIPT_DIR}/designs/${platform}/${design}/${platform}_${design}.csv"

# Function to clean up old result dumps from previous experiments
cleanup_old_result_dumps() {
    echo "Cleaning up result dumps from previous experiments..."
    rm -rf ../result_dump_*
}

# Function to generate initial random parameters from base config
generate_initial_parameters() {
    local config_file="designs/${platform}/${design}/config.mk"
    
    # Remove old CSV if it exists
    rm -f "$csv_file"
    
    # Create CSV header
    echo -n "core_util,cell_pad_global,cell_pad_detail,synth_flatten,pin_layer,above_layer,tns,lb_addon,cts_size,cts_diameter,enable_dpo,clk_period" > "$csv_file"
    echo >> "$csv_file"  # Add newline with Unix ending
    
    # Extract current values from config.mk
    local core_util=$(grep "CORE_UTILIZATION" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local cts_size=$(grep "CTS_CLUSTER_SIZE" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local cts_diameter=$(grep "CTS_CLUSTER_DIAMETER" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local cell_pad_global=$(grep "CELL_PAD_IN_SITES_GLOBAL_PLACEMENT" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local cell_pad_detail=$(grep "CELL_PAD_IN_SITES_DETAIL_PLACEMENT" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local synth_flatten=$(grep "SYNTH_FLATTEN" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local enable_dpo=$(grep "ENABLE_DPO" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local pin_layer=$(grep "PIN_LAYER_ADJUST" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local above_layer=$(grep "ABOVE_LAYER_ADJUST" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local tns=$(grep "TNS_END_PERCENT" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    local lb_addon=$(grep "PLACE_DENSITY_LB_ADDON" "$config_file" | cut -d'=' -f2 | tr -d ' ')
    
    # Get clock period from SDC file
    local sdc_file
    if [[ "$platform" == "asap7" && "$design" == "jpeg" ]]; then
        sdc_file="designs/${platform}/${design}/jpeg_encoder15_7nm.sdc"
    else
        sdc_file="designs/${platform}/${design}/constraint.sdc"
    fi
    local clk_period=$(grep "set clk_period" "$sdc_file" | awk '{print $3}')
    
    # Generate random variations (5-10%) for each numeric parameter
    for i in $(seq 1 $parallel_runs); do
        # Random perturbation factor between 0.95 and 1.05 (±5%)
        local factor=$(awk -v seed=$RANDOM 'BEGIN{srand(seed); print 0.95 + rand() * 0.1}')
        
        # Perturb values while respecting constraints
        local new_core_util=$(awk -v val=$core_util -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 20 ? 20 : (new > 99 ? 99 : new)
        }')
        local new_cts_size=$(awk -v val=$cts_size -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 10 ? 10 : (new > 40 ? 40 : new)
        }')
        local new_cts_diameter=$(awk -v val=$cts_diameter -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 80 ? 80 : (new > 120 ? 120 : new)
        }')
        local new_cell_pad_global=$(awk -v val=$cell_pad_global -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 0 ? 0 : (new > 3 ? 3 : new)
        }')
        local new_cell_pad_detail=$(awk -v val=$cell_pad_detail -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 0 ? 0 : (new > 3 ? 3 : new)
        }')
        local new_pin_layer=$(awk -v val=$pin_layer -v f=$factor 'BEGIN{
            new=val * f;
            print new < 0.2 ? 0.2 : (new > 0.7 ? 0.7 : new)
        }')
        local new_above_layer=$(awk -v val=$above_layer -v f=$factor 'BEGIN{
            new=val * f;
            print new < 0.2 ? 0.2 : (new > 0.7 ? 0.7 : new)
        }')
        local new_tns=$(awk -v val=$tns -v f=$factor 'BEGIN{
            new=int(val * f);
            print new < 0 ? 0 : (new > 100 ? 100 : new)
        }')
        local new_lb_addon=$(awk -v val=$lb_addon -v f=$factor 'BEGIN{
            new=val * f;
            print new < 0.2 ? 0.2 : (new > 0.99 ? 0.99 : new)
        }')
        local new_clk_period=$(awk -v val=$clk_period -v f=$factor 'BEGIN{printf "%.2f", val * f}')
        
        # Keep boolean values as is
        echo "$new_core_util,$new_cell_pad_global,$new_cell_pad_detail,$synth_flatten,$new_pin_layer,$new_above_layer,$new_tns,$new_lb_addon,$new_cts_size,$new_cts_diameter,$enable_dpo,$new_clk_period" >> "$csv_file"
    done
}

# Function to clean up previous run's CSV
cleanup_previous_run() {
    if [ -f "$csv_file" ]; then
        echo "Cleaning up CSV from previous run: $csv_file"
        rm -f "$csv_file"
    fi
}

# Function to copy optimized parameters from optimize.py
copy_optimized_parameters() {
    if [ -f "$csv_file" ]; then
        echo "Found new parameters CSV from optimize.py at $csv_file"
        # CSV file is already in the correct location, no need to move
        echo "CSV file is ready for use: $csv_file"
    else
        echo "Error: Expected CSV file $csv_file not found. Make sure optimize.py generated new parameters."
        exit 1
    fi
}

# Function to generate new config and constraint files
generate_new_files() {
    # Remove cd commands to keep the working directory consistent

    # For first iteration, generate initial random parameters
    if [ "$iteration" -eq 1 ]; then
        generate_initial_parameters
    else
        copy_optimized_parameters
    fi

    # Proceed with generating new config and constraint files
    # Base SDC filename
    if [[ "$platform" == "asap7" && "$design" == "jpeg" ]]; then
        base_sdc="${SCRIPT_DIR}/designs/${platform}/${design}/jpeg_encoder15_7nm.sdc"
    else
        base_sdc="${SCRIPT_DIR}/designs/${platform}/${design}/constraint.sdc"
    fi

    # Change to the design directory
    cd "${SCRIPT_DIR}/designs/${platform}/${design}"

    i=1
    tail -n +2 "$csv_file" | while IFS=',' read -r core_util cell_pad_global cell_pad_detail synth_flatten pin_layer above_layer tns lb_addon cts_size cts_diameter enable_dpo clk_period; do
        # Create a copy of the base config.mk for this iteration
        cp config.mk config_$i.mk

        # Update the config_$i.mk file with direct values from CSV
        sed -i "s|export CORE_UTILIZATION.*|export CORE_UTILIZATION = $core_util|" config_$i.mk
        sed -i "s|export CTS_CLUSTER_SIZE.*|export CTS_CLUSTER_SIZE = $cts_size|" config_$i.mk
        sed -i "s|export CTS_CLUSTER_DIAMETER.*|export CTS_CLUSTER_DIAMETER = $cts_diameter|" config_$i.mk
        sed -i "s|export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT.*|export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = $cell_pad_global|" config_$i.mk
        sed -i "s|export CELL_PAD_IN_SITES_DETAIL_PLACEMENT.*|export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = $cell_pad_detail|" config_$i.mk
        sed -i "s|export SYNTH_FLATTEN.*|export SYNTH_FLATTEN = $synth_flatten|" config_$i.mk
        sed -i "s|export ENABLE_DPO.*|export ENABLE_DPO = $enable_dpo|" config_$i.mk
        sed -i "s|export PIN_LAYER_ADJUST.*|export PIN_LAYER_ADJUST = $pin_layer|" config_$i.mk
        sed -i "s|export ABOVE_LAYER_ADJUST.*|export ABOVE_LAYER_ADJUST = $above_layer|" config_$i.mk
        sed -i "s|export TNS_END_PERCENT.*|export TNS_END_PERCENT = $tns|" config_$i.mk
        sed -i "s|export PLACE_DENSITY_LB_ADDON.*|export PLACE_DENSITY_LB_ADDON = $lb_addon|" config_$i.mk

        # Create new SDC file with appropriate name
        if [[ "$platform" == "asap7" && "$design" == "jpeg" ]]; then
            new_sdc="jpeg_encoder15_7nm_$i.sdc"
        else
            new_sdc="constraint_$i.sdc"
        fi

        # Copy and update SDC file with Unix line endings
        cp "$base_sdc" "$new_sdc"
        sed -i "s/set clk_period.*/set clk_period $clk_period/" "$new_sdc"
        # Convert to Unix line endings
        tr -d '\r' < "$new_sdc" > "${new_sdc}.tmp" && mv "${new_sdc}.tmp" "$new_sdc"

        # Update the SDC file path in the config_$i.mk
        sed -i "s|export SDC_FILE.*|export SDC_FILE = ./designs/${platform}/${design}/$new_sdc|" config_$i.mk

        # Increment the iteration counter
        i=$((i + 1))

        # Break after parallel_runs iterations
        if [ $i -gt $parallel_runs ]; then
            break
        fi
    done

    # No need to change directories afterward
}

# Main execution
if [ "$iteration" -eq 1 ]; then
    # For first iteration, clean up any CSV from previous run
    cleanup_previous_run
fi

# Clean up and generate new files
make clean_all
generate_new_files

echo "Sequential phase completed for iteration $iteration" 