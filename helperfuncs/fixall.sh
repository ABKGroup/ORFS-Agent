#!/bin/bash

echo "Starting cleanup..."

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

# Comment all DESIGN_CONFIG lines initially
comment_all_design_configs

# Loop over each line from start_line to end_line
for line_num in $(seq $start_line $end_line); do
    echo "Processing line $line_num in Makefile"

    # Uncomment the current line
    uncomment_design_config_line $line_num

    # Extract platform and design from the uncommented line
    config_line=$(sed -n "${line_num}p" Makefile)
    platform=$(echo "$config_line" | awk -F'/' '{print $(NF-3)}')
    design=$(echo "$config_line" | awk -F'/' '{print $(NF-2)}')

    echo "Running make clean_all for platform: $platform, design: $design"

    # Run make clean_all
    make clean_all

    # Remove generated files for this design
    design_dir="designs/${platform}/${design}"
    if [ -d "$design_dir" ]; then
        echo "Cleaning up generated files in $design_dir"

        # Remove config_i.mk files
        rm -f "${design_dir}"/config_*.mk

        # Remove constraint_i.sdc files
        rm -f "${design_dir}"/constraint_*.sdc

        # Remove specific sdc files for asap7/jpeg
        if [ "$platform" == "asap7" ] && [ "$design" == "jpeg" ]; then
            rm -f "${design_dir}"/jpeg_encoder15_7nm_*.sdc
        fi

        # Remove CSV files
        rm -f "${design_dir}"/*.csv
    fi

    # Remove logs and results specific to this platform and design
    rm -rf logs/${platform}/${design}/*
    rm -rf results/${platform}/${design}/*

    echo "Cleanup completed for platform: $platform, design: $design."

    # Comment the current line back
    comment_all_design_configs
done

# Ensure all DESIGN_CONFIG lines are commented at the end
comment_all_design_configs

echo "All DESIGN_CONFIG lines are now commented in the Makefile."
echo "Cleanup completed." 