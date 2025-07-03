#!/usr/bin/env python3

import os
import re
import glob
import json
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

@dataclass
class RunResult:
    iteration: int
    run_number: int
    parameters: Dict[str, float]
    final_ecp: Optional[float] = None
    detailed_wl: Optional[float] = None
    
    def __str__(self) -> str:
        params_str = ", ".join(f"{k}={v}" for k, v in self.parameters.items())
        metrics_str = []
        if self.final_ecp is not None:
            metrics_str.append(f"ECP={self.final_ecp:.3f}")
        if self.detailed_wl is not None:
            metrics_str.append(f"WL={self.detailed_wl:.0f}")
        return f"Iter {self.iteration}, Run {self.run_number}: {', '.join(metrics_str)} [{params_str}]"

def get_clock_period(dump_dir: str, run_number: int) -> Optional[float]:
    """Get clock period from SDC file, handling different SDC file patterns"""
    # List of possible SDC file patterns to check
    sdc_patterns = [
        f"constraint_{run_number}.sdc",  # Standard pattern
        "jpeg_encoder15_7nm.sdc",        # JPEG specific pattern
    ]
    
    for pattern in sdc_patterns:
        sdc_file = os.path.join(dump_dir, pattern)
        if os.path.exists(sdc_file):
            with open(sdc_file, 'r') as f:
                for line in f:
                    if 'set clk_period' in line or 'create_clock' in line:
                        try:
                            # Extract the last number from the line
                            numbers = re.findall(r'[-+]?\d*\.?\d+', line)
                            if numbers:
                                return float(numbers[-1])
                        except (IndexError, ValueError):
                            continue
    return None

def parse_metrics(dump_dir: str, logs_dir: str, run_number: int) -> Tuple[Optional[float], Optional[float]]:
    """Parse JSON files to extract final ECP and detailed wirelength"""
    final_ecp = None
    detailed_wl = None
    
    base_dir = os.path.join(logs_dir, f"base_{run_number}")
    if not os.path.exists(base_dir):
        return final_ecp, detailed_wl
        
    # Get clock period from SDC file
    clock_period = get_clock_period(dump_dir, run_number)
    if clock_period is None:
        return final_ecp, detailed_wl
        
    # Get timing metrics from 6_report.json
    timing_file = os.path.join(base_dir, "6_report.json")
    if os.path.exists(timing_file):
        try:
            with open(timing_file, 'r') as f:
                timing_data = json.load(f)
                if 'finish__timing__setup__ws' in timing_data:
                    worst_slack = float(timing_data['finish__timing__setup__ws'])
                    final_ecp = clock_period - worst_slack
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing timing file {timing_file}: {e}")
            
    # Get wirelength from 5_2_route.json
    route_file = os.path.join(base_dir, "5_2_route.json")
    if os.path.exists(route_file):
        try:
            with open(route_file, 'r') as f:
                route_data = json.load(f)
                if 'detailedroute__route__wirelength' in route_data:
                    detailed_wl = float(route_data['detailedroute__route__wirelength'])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            print(f"Error parsing route file {route_file}: {e}")
            
    return final_ecp, detailed_wl

def parse_config_mk(filepath: str) -> Dict[str, float]:
    """Parse config.mk file to extract parameters"""
    parameters = {}
    with open(filepath, 'r') as f:
        for line in f:
            if line.startswith('export'):
                parts = line.strip().split('=', 1)
                if len(parts) == 2:
                    key = parts[0].replace('export', '').strip()
                    value = parts[1].strip()
                    try:
                        parameters[key] = float(value)
                    except ValueError:
                        continue
    return parameters

def process_result_dump(dump_dir: str) -> List[RunResult]:
    """Process a single result dump directory"""
    results = []
    iteration = int(dump_dir.split('_')[-1])
    
    logs_dir = os.path.join(dump_dir, "logs_dump")
    if not os.path.exists(logs_dir):
        print(f"No logs_dump directory found in {dump_dir}")
        return results
    
    base_dirs = glob.glob(os.path.join(logs_dir, "base_*"))
    run_numbers = sorted([int(os.path.basename(d).split('_')[1]) for d in base_dirs])
    
    for run_number in run_numbers:
        final_ecp, detailed_wl = parse_metrics(dump_dir, logs_dir, run_number)
        results.append(RunResult(
            iteration=iteration,
            run_number=run_number,
            parameters={},
            final_ecp=final_ecp,
            detailed_wl=detailed_wl
        ))
    
    return results

def analyze_trends(results: List[RunResult]):
    """Analyze trends across iterations"""
    # Group results by iteration
    iter_results = {}
    for r in results:
        if r.iteration not in iter_results:
            iter_results[r.iteration] = []
        iter_results[r.iteration].append(r)
    
    # Print trend analysis
    print("\nTrend Analysis Across Iterations:")
    print("=================================")
    for iter_num in sorted(iter_results.keys()):
        iter_data = iter_results[iter_num]
        valid_ecp = [r for r in iter_data if r.final_ecp is not None]
        valid_wl = [r for r in iter_data if r.detailed_wl is not None]
        
        print(f"\nIteration {iter_num}:")
        if valid_ecp:
            print("  Top 3 ECPs:")
            sorted_ecp = sorted(valid_ecp, key=lambda x: x.final_ecp)[:3]
            for i, result in enumerate(sorted_ecp, 1):
                print(f"    {i}. ECP={result.final_ecp:.2f} (Run {result.run_number})")
                if result.detailed_wl is not None:
                    print(f"       WL={result.detailed_wl:.0f}")
        
        if valid_wl:
            print("  Top 3 WLs:")
            sorted_wl = sorted(valid_wl, key=lambda x: x.detailed_wl)[:3]
            for i, result in enumerate(sorted_wl, 1):
                print(f"    {i}. WL={result.detailed_wl:.0f} (Run {result.run_number})")
                if result.final_ecp is not None:
                    print(f"       ECP={result.final_ecp:.2f}")

def main():
    dump_dirs = sorted(glob.glob('result_dump_*'))
    
    if not dump_dirs:
        print("No result dump directories found!")
        return
    
    print(f"Found {len(dump_dirs)} result dump directories\n")
    
    all_results = []
    for dump_dir in dump_dirs:
        results = process_result_dump(dump_dir)
        all_results.extend(results)
    
    # Print summary
    print("Summary:")
    print(f"Total runs analyzed: {len(all_results)}")
    valid_ecp = [r for r in all_results if r.final_ecp is not None]
    valid_wl = [r for r in all_results if r.detailed_wl is not None]
    print(f"Runs with valid ECP: {len(valid_ecp)}")
    print(f"Runs with valid WL: {len(valid_wl)}")
    
    if valid_ecp:
        print("\nTop 10 lowest ECPs overall:")
        sorted_ecp = sorted(valid_ecp, key=lambda x: x.final_ecp)[:10]
        for i, result in enumerate(sorted_ecp, 1):
            print(f"{i}. Iter {result.iteration}, Run {result.run_number}: ECP={result.final_ecp:.2f}")
            if result.detailed_wl is not None:
                print(f"   WL={result.detailed_wl:.0f}")
            
    if valid_wl:
        print("\nTop 10 lowest wirelengths overall:")
        sorted_wl = sorted(valid_wl, key=lambda x: x.detailed_wl)[:10]
        for i, result in enumerate(sorted_wl, 1):
            print(f"{i}. Iter {result.iteration}, Run {result.run_number}: WL={result.detailed_wl:.0f}")
            if result.final_ecp is not None:
                print(f"   ECP={result.final_ecp:.2f}")
    
    # Analyze trends across iterations
    analyze_trends(all_results)

if __name__ == "__main__":
    main() 