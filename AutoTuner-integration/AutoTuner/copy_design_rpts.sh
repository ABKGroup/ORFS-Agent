#!/bin/bash

# Set the root of the search and the destination root
SRC_ROOT="/home/scratch/sakundu/MLCAD"
DEST_ROOT="/home/fetzfs_projects/rdf_2024/sakundu/Amur_ICML/AutoTuner/to_amur"  # <-- Change this to your desired destination

# Find all directories matching the pattern
find "$SRC_ROOT" -mindepth 5 -maxdepth 5 -type d | while read -r dir; do
    # Check if 4_1_cts.json exists in this directory
    if [[ -f "$dir/4_1_cts.json" ]]; then
        # Extract <tech>, <design>, <rpt_dir> from the path
        # Path: .../<tech>/<design>/<rpt_dir>
        tech=$(basename "$(dirname "$(dirname "$dir")")")
        design=$(basename "$(dirname "$dir")")
        rpt_dir=$(basename "$dir")

        # Create destination directory
        dest_dir="$DEST_ROOT/${design}_${tech}/$rpt_dir"
        mkdir -p "$dest_dir"

        # Copy files if they exist
        for f in 4_1_cts.json 5_2_route.json 6_report.json; do
            if [[ -f "$dir/$f" ]]; then
                cp "$dir/$f" "$dest_dir/"
            fi
        done

        echo "Copied files from $dir to $dest_dir"
    fi
done