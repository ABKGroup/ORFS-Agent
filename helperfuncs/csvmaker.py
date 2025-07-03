#!/usr/bin/env python3

import os
import re
import glob
import json
import csv
import argparse
from typing import Dict, List, Tuple, Optional
from pathlib import Path

def get_clock_period(dump_dir: str, run_number: int, design_dir: Optional[str] = None) -> Optional[float]:
    """Get clock period from SDC file"""
    # For standard designs
    sdc_file = os.path.join(dump_dir, f"constraint_{run_number}.sdc")
    
    # For JPEG design
    if not os.path.exists(sdc_file):
        sdc_file = os.path.join(dump_dir, f"jpeg_encoder15_7nm_{run_number}.sdc")
    
    print(f"Reading SDC file: {sdc_file}")  # Debug print
    
    if os.path.exists(sdc_file):
        with open(sdc_file, 'r') as f:
            for line in f:
                line = line.strip()
                print(f"Processing line: {line}")  # Debug print
                # Look for exact TCL format: set clk_period <value>
                if line.startswith('set clk_period '):
                    try:
                        # Remove 'set clk_period ' and any extra whitespace
                        value = line[14:].strip()
                        print(f"Found clock period line, value: {value}")  # Debug print
                        # Skip if it's a TCL variable
                        if value.startswith('$'):
                            continue
                        clk_period = float(value)
                        print(f"Parsed clock period: {clk_period}")  # Debug print
                        return clk_period
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing clock period from line '{line}': {e}")
                        continue
                # Also check create_clock line as backup
                elif 'create_clock' in line and '-period' in line:
                    try:
                        # Find the value after -period
                        parts = line.split('-period')
                        if len(parts) > 1:
                            # Take first word after -period
                            value = parts[1].strip().split()[0]
                            # Skip if it's a TCL variable
                            if value.startswith('$'):
                                continue
                            clk_period = float(value)
                            print(f"Parsed clock period from create_clock: {clk_period}")  # Debug print
                            return clk_period
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing create_clock line '{line}': {e}")
                        continue
    return None

def get_config_parameters(dump_dir: str, run_number: int) -> Dict[str, float]:
    """Extract parameters from config.mk"""
    # Config file is directly in the dump directory as config_i.mk
    config_file = os.path.join(dump_dir, f"config_{run_number}.mk")
    
    parameters = {}
    # All 11 parameters we need from config.mk
    param_keys = [
        'CTS_CLUSTER_SIZE',
        'CTS_CLUSTER_DIAMETER',
        'CELL_PAD_IN_SITES_GLOBAL_PLACEMENT',
        'CELL_PAD_IN_SITES_DETAIL_PLACEMENT',
        'PIN_LAYER_ADJUST',
        'ABOVE_LAYER_ADJUST',
        'SYNTH_FLATTEN',
        'ENABLE_DPO',
        'CORE_UTILIZATION',
        'PLACE_DENSITY_LB_ADDON',
        'TNS_END_PERCENT'
    ]
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('export '):
                    # Remove 'export ' from the start
                    line = line[7:]
                    # Split on '=' and strip whitespace
                    parts = [p.strip() for p in line.split('=', 1)]
                    if len(parts) == 2:
                        key = parts[0]
                        value = parts[1]
                        if key in param_keys:
                            try:
                                parameters[key] = float(value)
                            except ValueError:
                                continue
    
    return parameters

def get_metrics(logs_dir: str, run_number: int, clock_period: Optional[float]) -> Optional[Dict[str, float]]:
    """Extract metrics from JSON reports. Returns None if required files are missing."""
    metrics = {
        'cts_ecp': -1,
        'finish_ecp': -1,
        'cts_wl': -1,
        'detailed_wl': -1
    }
    base_dir = os.path.join(logs_dir, f"base_{run_number}")
    
    # Get CTS metrics from 4_1_cts.json - this is required
    cts_file = os.path.join(base_dir, "4_1_cts.json")
    if not os.path.exists(cts_file):
        return None  # Still skip if 4_1_cts.json is missing as it's our primary data source
        
    try:
        with open(cts_file, 'r') as f:
            cts_data = json.load(f)
            # Extract required metrics
            if 'cts__timing__setup__ws' in cts_data and 'cts__route__wirelength__estimated' in cts_data:
                cts_ws = float(cts_data['cts__timing__setup__ws'])
                if clock_period is not None:
                    metrics['cts_ecp'] = clock_period - cts_ws
                metrics['cts_wl'] = float(cts_data['cts__route__wirelength__estimated'])
            else:
                return None  # Still skip if primary metrics are missing
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"Error parsing CTS file {cts_file}: {e}")
        return None
    
    # Get final metrics from 6_report.json
    final_file = os.path.join(base_dir, "6_report.json")
    if os.path.exists(final_file):
        try:
            with open(final_file, 'r') as f:
                final_data = json.load(f)
                if 'finish__timing__setup__ws' in final_data:
                    finish_ws = float(final_data['finish__timing__setup__ws'])
                    if clock_period is not None:
                        metrics['finish_ecp'] = clock_period - finish_ws
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing final report {final_file}: {e}")
    
    # Get detailed route metrics from 5_2_route.json
    route_file = os.path.join(base_dir, "5_2_route.json")
    if os.path.exists(route_file):
        try:
            with open(route_file, 'r') as f:
                route_data = json.load(f)
                if 'detailedroute__route__wirelength' in route_data:
                    metrics['detailed_wl'] = float(route_data['detailedroute__route__wirelength'])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing route file {route_file}: {e}")
    
    return metrics

def process_result_dump(dump_dir: str, design_dir: Optional[str] = None) -> List[Dict[str, float]]:
    """Process a single result dump directory"""
    results = []
    iteration = int(dump_dir.split('_')[-1])
    logs_dir = os.path.join(dump_dir, "logs_dump")
    
    if not os.path.exists(logs_dir):
        print(f"No logs_dump directory found in {dump_dir}")
        return results
    
    # Find all config files to determine run numbers
    config_files = glob.glob(os.path.join(dump_dir, "config_*.mk"))
    run_numbers = sorted([int(os.path.basename(f).split('_')[1].split('.')[0]) 
                        for f in config_files])
    
    for run_number in run_numbers:
        result = {
            'iteration': iteration, 
            'run': run_number,
            'clock_period': -1,  # Default value for clock period
            # Default values for all config parameters
            'CTS_CLUSTER_SIZE': -1,
            'CTS_CLUSTER_DIAMETER': -1,
            'CELL_PAD_IN_SITES_GLOBAL_PLACEMENT': -1,
            'CELL_PAD_IN_SITES_DETAIL_PLACEMENT': -1,
            'PIN_LAYER_ADJUST': -1,
            'ABOVE_LAYER_ADJUST': -1,
            'SYNTH_FLATTEN': -1,
            'ENABLE_DPO': -1,
            'CORE_UTILIZATION': -1,
            'PLACE_DENSITY_LB_ADDON': -1,
            'TNS_END_PERCENT': -1
        }
        
        # Get clock period first as we need it for ECP calculation
        clock_period = get_clock_period(dump_dir, run_number)
        if clock_period is not None:
            result['clock_period'] = clock_period
        
        # Get metrics - if 4_1_cts.json is missing, skip this run
        metrics = get_metrics(logs_dir, run_number, clock_period)
        if metrics is None:
            continue
            
        # Get config parameters
        params = get_config_parameters(dump_dir, run_number)
        result.update(params)
        
        # Add metrics
        result.update(metrics)
        
        results.append(result)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='Extract metrics from result dumps into CSV')
    parser.add_argument('output', nargs='?', default='results.csv',
                      help='Output CSV file name (default: results.csv)')
    args = parser.parse_args()
    
    # Find all result dump directories
    dump_dirs = sorted(glob.glob('result_dump_*'))
    
    if not dump_dirs:
        print("No result dump directories found!")
        return
    
    print(f"Found {len(dump_dirs)} result dump directories")
    
    # Collect all results
    all_results = []
    for dump_dir in dump_dirs:
        results = process_result_dump(dump_dir)
        all_results.extend(results)
    
    if not all_results:
        print("No results found!")
        return
    
    # Define the exact columns we want in order
    columns = [
        'iteration',
        'run',
        'clock_period',
        'CTS_CLUSTER_SIZE',
        'CTS_CLUSTER_DIAMETER',
        'CELL_PAD_IN_SITES_GLOBAL_PLACEMENT',
        'CELL_PAD_IN_SITES_DETAIL_PLACEMENT',
        'PIN_LAYER_ADJUST',
        'ABOVE_LAYER_ADJUST',
        'SYNTH_FLATTEN',
        'ENABLE_DPO',
        'CORE_UTILIZATION',
        'PLACE_DENSITY_LB_ADDON',
        'TNS_END_PERCENT',
        'cts_ecp',
        'cts_wl',
        'finish_ecp',
        'detailed_wl'
    ]
    
    # Write to CSV
    with open(args.output, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(all_results)
    
    print(f"Results written to {args.output}")
    print(f"Total rows: {len(all_results)}")
    print(f"Columns: {', '.join(columns)}")

if __name__ == "__main__":
    main() 