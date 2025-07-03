#!/usr/bin/env python3

import json
import os
import sys
import re
import numpy as np
from typing import Dict, List, Any, Tuple, Optional
import anthropic
import csv
import random

from inspectfuncs import *
from modelfuncs import *
from agglomfuncs import *

def process_log_file(log_path: str) -> Dict[str, Any]:
    """Process a single log file to extract relevant metrics"""
    run_data = {
        'file': os.path.basename(log_path),
        'success': False,
        'metrics': {},
        'errors': []
    }
    
    with open(log_path, 'r') as f:
        content = f.read()
        
        # Extract timing information
        timing_metrics = extract_timing_metrics(content)
        run_data['metrics'].update(timing_metrics)
        
        # Extract wirelength information
        wl_metrics = extract_wirelength_metrics(content)
        run_data['metrics'].update(wl_metrics)
        
        # Extract any errors
        errors = extract_errors(content)
        run_data['errors'].extend(errors)
        
        # Determine success based on completion markers and errors
        run_data['success'] = is_run_successful(content, errors)
        
    return run_data

def extract_timing_metrics(log_content: str) -> Dict[str, float]:
    """Extract timing-related metrics from log content"""
    metrics = {}
    
    # Extract worst slack (final)
    slack_match = re.search(r'(?:worst slack|WNS):\s*([-\d.]+)', log_content, re.IGNORECASE)
    if slack_match:
        metrics['worst_slack'] = float(slack_match.group(1))
        
    # Extract CTS worst slack
    cts_slack_match = re.search(r'(?:CTS|Clock Tree) (?:worst slack|WNS):\s*([-\d.]+)', log_content, re.IGNORECASE)
    if cts_slack_match:
        metrics['cts_ws'] = float(cts_slack_match.group(1))
        
    # Extract clock period
    period_match = re.search(r'[Cc]lock period:\s*([\d.]+)', log_content)
    if period_match:
        metrics['clock_period'] = float(period_match.group(1))
        
    # Extract TNS
    tns_match = re.search(r'(?:Total negative slack|TNS):\s*([-\d.]+)', log_content, re.IGNORECASE)
    if tns_match:
        metrics['tns'] = float(tns_match.group(1))
        
    return metrics

def extract_wirelength_metrics(log_content: str) -> Dict[str, float]:
    """Extract wirelength-related metrics from log content"""
    metrics = {}
    
    # Extract total wirelength
    wl_match = re.search(r'Total wirelength: ([\d.]+)', log_content)
    if wl_match:
        metrics['total_wirelength'] = float(wl_match.group(1))
        
    # Extract estimated wirelength after CTS
    cts_wl_match = re.search(r'Estimated wirelength: ([\d.]+)', log_content)
    if cts_wl_match:
        metrics['cts_wirelength'] = float(cts_wl_match.group(1))
        
    return metrics

def extract_errors(log_content: str) -> List[str]:
    """Extract error messages from log content"""
    errors = []
    
    # Look for common error patterns
    error_patterns = [
        r'Error: .*',
        r'ERROR: .*',
        r'FATAL: .*',
        r'Failed: .*'
    ]
    
    for pattern in error_patterns:
        matches = re.finditer(pattern, log_content, re.MULTILINE)
        errors.extend(match.group(0) for match in matches)
        
    return errors

def is_run_successful(log_content: str, errors: List[str]) -> bool:
    """Determine if a run was successful based on log content and errors"""
    if errors:
        return False
        
    # Look for completion markers
    completion_markers = [
        'Flow complete',
        'Finished successfully'
    ]
    
    return any(marker in log_content for marker in completion_markers)

class OptimizationWorkflow:
    def __init__(self, platform: str, design: str, objective: str):
        self.platform = platform
        self.design = design
        self.objective = objective.upper()  # Convert to uppercase
        
        # Load configuration
        self.config = self._load_config()
        
        # Find the design configuration
        configurations = self.config.get('configurations', [])
        for config in configurations:
            if (
                config['platform'].lower() == self.platform.lower()
                and config['design'].lower() == self.design.lower()
                and config['goal'].upper() == self.objective
            ):
                self.design_config = config
                break
        else:
            raise ValueError(
                f"No configuration found for platform={self.platform}, design={self.design}, objective={self.objective}"
            )
        
        # Define initial clock periods for each design and platform
        initial_clock_periods = {
            ('asap7', 'aes'): 400,     # in picoseconds
            ('asap7', 'ibex'): 1260,   # in picoseconds
            ('asap7', 'jpeg'): 1100,   # in picoseconds
            ('sky130hd', 'aes'): 4.5,  # in nanoseconds
            ('sky130hd', 'ibex'): 10.0,# in nanoseconds
            ('sky130hd', 'jpeg'): 8.0, # in nanoseconds
        }

        # Get the initial clock period for the current platform and design
        key = (self.platform.lower(), self.design.lower())
        if key in initial_clock_periods:
            self.initial_clk_period = initial_clock_periods[key]
        else:
            raise ValueError(f"Initial clock period not defined for platform={self.platform}, design={self.design}")

        # Calculate clock period range
        min_clk = self.initial_clk_period * 0.7
        max_clk = self.initial_clk_period * 1.3

        # Define parameter names in the expected order
        self.parameter_names = [
            'core_util',
            'cell_pad_global',
            'cell_pad_detail', 
            'synth_flatten',
            'pin_layer',
            'above_layer',
            'tns',
            'lb_addon',
            'cts_size',
            'cts_diameter',
            'enable_dpo',
            'clk_period'
        ]
        
        # Set all parameter constraints including clock period range
        self.param_constraints = {
            'core_util': {'type': 'int', 'range': [20, 99]},
            'cell_pad_global': {'type': 'int', 'range': [0, 4]},
            'cell_pad_detail': {'type': 'int', 'range': [0, 4]},
            'synth_flatten': {'type': 'int', 'range': [0, 1]},
            'pin_layer': {'type': 'float', 'range': [0.2, 0.7]},
            'above_layer': {'type': 'float', 'range': [0.2, 0.7]},
            'tns': {'type': 'int', 'range': [70, 100]},
            'lb_addon': {'type': 'float', 'range': [0.00, 0.99]},
            'cts_size': {'type': 'int', 'range': [10, 40]},
            'cts_diameter': {'type': 'int', 'range': [80, 120]},
            'enable_dpo': {'type': 'int', 'range': [0, 1]},
            'clk_period': {'type': 'float', 'range': [min_clk, max_clk]}
        }
        
        # Load initial parameters and SDC context
        self.initial_params = self._load_initial_params()
        self.sdc_context = self._load_sdc_context()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from 'opt_config.json'."""
        with open('opt_config.json', 'r') as f:
            config = json.load(f)
        return config
        
    def _load_initial_params(self) -> Dict[str, Any]:
        """Load initial parameters from the design's config.mk file"""
        config_path = f"designs/{self.platform}/{self.design}/config.mk"
        params = {}
        with open(config_path, 'r') as f:
            for line in f:
                if line.startswith('export'):
                    parts = line.strip().split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].replace('export', '').strip()
                        value = parts[1].strip()
                        params[key] = value
        return params
        
    def _load_sdc_context(self) -> Dict[str, Any]:
        """Load SDC context including special case for JPEG"""
        sdc_context = {}
        
        # Determine SDC filename based on platform/design
        if self.platform.lower() == 'asap7' and self.design.lower() == 'jpeg':
            sdc_file = 'jpeg_encoder15_7nm.sdc'
        else:
            sdc_file = 'constraint.sdc'
            
        sdc_path = f"designs/{self.platform}/{self.design}/{sdc_file}"
        
        # Read SDC file
        try:
            with open(sdc_path, 'r') as f:
                sdc_content = f.read()
                
            # Extract clock period
            clock_period_match = re.search(r'set clk_period\s+([\d.]+)', sdc_content)
            if clock_period_match:
                sdc_context['clock_period'] = float(clock_period_match.group(1))
                
            # Store full content for context
            sdc_context['content'] = sdc_content
            sdc_context['filename'] = sdc_file
            
        except Exception as e:
            print(f"Warning: Could not load SDC file {sdc_path}: {str(e)}")
            sdc_context['error'] = str(e)
            
        return sdc_context
        
    def _generate_llm_prompt(self, stage: str, data: Dict[str, Any]) -> str:
        """Generate LLM prompt for different stages"""

        # Include parameter constraints in the prompt
        constraints_text = "Parameter Constraints:\n"
        for param, info in self.param_constraints.items():
            param_type = info['type']
            param_range = info['range']
            constraints_text += f"- {param} ({param_type}, range: {param_range})\n"

        # Construct the prompt based on the stage
        if stage == 'inspect':
            prompt = (
                f"**Stage: Inspect**\n"
                "In this stage, we analyze the data from previous optimization runs to identify patterns, trends, and insights.\n\n"
                f"Data to analyze:\n{json.dumps(data, indent=2)}\n\n"
                "Please analyze the data and provide insights on:\n"
                "1. Key patterns in successful vs unsuccessful runs.\n"
                "2. Parameter ranges that appear promising.\n"
                "3. Any timing or wirelength trends.\n"
                "4. Recommendations for subsequent runs.\n"
            )
        elif stage == 'model':
            prompt = (
                f"**Stage: Model**\n"
                "In this stage, we decide how to model the optimization problem based on the data analysis.\n\n"
                f"Data for modeling:\n{json.dumps(data, indent=2)}\n\n"
                "Please suggest:\n"
                "1. Appropriate modeling techniques.\n"
                "2. Key parameters to focus on.\n"
                "3. Surrogate model recommendations.\n"
                "4. Acquisition function choices.\n"
            )
        elif stage == 'agglomerate':
            prompt = (
                f"**Stage: Agglomerate**\n"
                "In this stage, we generate new parameter combinations to explore in the next optimization runs.\n\n"
                "Please provide a list of new parameter sets to try, ensuring they respect the domain constraints below.\n\n"
                f"{constraints_text}\n"
                "Each parameter set should be a dictionary with parameter names and their suggested values.\n"
                "**Important:** Make sure all parameter sets satisfy the domain constraints before suggesting them.\n"
            )
        else:
            prompt = (
                f"**Stage: {stage.capitalize()}**\n"
                f"Data:\n{json.dumps(data, indent=2)}\n\n"
                "Please provide guidance based on the above data.\n"
            )

        return prompt

    def _call_llm(self, stage: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Call Claude to get recommendations for optimization parameters"""
        print(f"\n=== Calling LLM for {stage} stage ===")
        
        # Hardcode API key
        api_key = #PUT YOUR KEY HERE
        
        client = anthropic.Anthropic(api_key=api_key)
        
        tools = [
            {
                "name": "configure_inspection",
                "description": "Configure data inspection parameters",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "n_clusters": {
                            "type": "integer",
                            "description": "Number of clusters for structure analysis",
                            "minimum": 2,
                            "maximum": 10
                        },
                        "correlation_threshold": {
                            "type": "number",
                            "description": "Threshold for considering correlations significant",
                            "minimum": 0,
                            "maximum": 1
                        }
                    },
                    "required": ["n_clusters", "correlation_threshold"]
                }
            },
            {
                "name": "configure_model",
                "description": "Configure modeling approach",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "kernel_type": {
                            "type": "string",
                            "enum": ["rbf", "matern", "rational"],
                            "description": "Type of kernel to use"
                        },
                        "preprocessing": {
                            "type": "string",
                            "enum": ["standard", "robust", "none"],
                            "description": "Type of preprocessing to apply"
                        },
                        "acquisition": {
                            "type": "string",
                            "enum": ["ei", "ucb", "pi"],
                            "description": "Acquisition function to use"
                        },
                        "surrogate_weight": {
                            "type": "number",
                            "description": "Weight to give surrogate values",
                            "minimum": 0,
                            "maximum": 1
                        }
                    },
                    "required": ["kernel_type", "preprocessing", "acquisition", "surrogate_weight"]
                }
            },
            {
                "name": "configure_selection",
                "description": "Configure point selection strategy",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "method": {
                            "type": "string",
                            "enum": ["entropy", "kmeans", "hybrid", "graph"],
                            "description": "Selection method to use"
                        },
                        "quality_weight": {
                            "type": "number",
                            "description": "Weight between quality and diversity",
                            "minimum": 0,
                            "maximum": 1
                        },
                        "uncertainty_bonus": {
                            "type": "number",
                            "description": "Weight for uncertainty in quality scores",
                            "minimum": 0,
                            "maximum": 1
                        }
                    },
                    "required": ["method", "quality_weight", "uncertainty_bonus"]
                }
            }
        ]

        # Get data summaries
        if stage == 'inspect':
            print("Generating data distribution and structure summaries...")
            # Extract X and Y from successful runs if available
            X = []
            Y = []
            if 'log_data' in data and 'runs' in data['log_data']:
                for run in data['log_data']['runs']:
                    if run['success'] and 'metrics' in run:
                        obj = self._calculate_objective(run)
                        if obj['value'] is not None or obj['surrogate'] is not None:
                            # Use parameters as X
                            params = []
                            for param in self.param_constraints.keys():
                                params.append(float(run.get('parameters', {}).get(param, 0)))
                            X.append(params)
                            # Use objective as Y
                            Y.append(obj['value'] if obj['value'] is not None else obj['surrogate'])
            
            if X and Y:
                dist_summary = inspect_data_distribution(np.array(X), np.array(Y))
                struct_summary = inspect_data_structure(np.array(X))
            else:
                print("No successful runs found, using empty summaries")
                dist_summary = {}
                struct_summary = {}
        else:
            dist_summary = {}
            struct_summary = {}

        # Generate context message
        context_message = self._generate_llm_prompt(stage, data)
        print(f"Generated prompt with context for {stage}")
        
        print("Making LLM API call...")
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=2048,
            tools=tools,
            messages=[{
                "role": "user",
                "content": context_message
            }]
        )

        # Extract configurations
        configs = {}
        print("\nReceived tool calls from LLM:")
        for block in response.content:
            if block.type == 'tool_use':
                print(f"- {block.name}: {block.input}")
                if block.name == 'configure_inspection':
                    configs['inspection'] = block.input
                elif block.name == 'configure_model':
                    configs['model'] = block.input
                elif block.name == 'configure_selection':
                    configs['selection'] = block.input

        # Add default configs if missing
        for key, default in [
            ('inspection', {"n_clusters": 5, "correlation_threshold": 0.5}),
            ('model', {"kernel_type": "matern", "preprocessing": "robust", 
                      "acquisition": "ei", "surrogate_weight": 0.8}),
            ('selection', {"method": "hybrid", "quality_weight": 0.7, 
                          "uncertainty_bonus": 0.2})
        ]:
            if key not in configs:
                print(f"Warning: No {key} config from LLM, using defaults: {default}")
                configs[key] = default
        
        return configs

    def run_iteration(self, num_runs: int) -> None:
        """Run a complete iteration of the optimization workflow"""
        print(f"\n=== Starting optimization iteration for {self.platform}/{self.design} ===")
        print(f"Objective: {self.objective}")
        print(f"Number of runs requested: {num_runs}")
        
        # Step 1: Inspect logs
        print("\nStep 1: Inspecting logs...")
        log_data = self.inspect_logs()
        print(f"Found {log_data['summary']['total_runs']} total runs, "
              f"{log_data['summary']['successful_runs']} successful")
        
        # Get LLM recommendations for inspection and analysis
        print("\nGetting LLM recommendations for inspection...")
        inspect_configs = self._call_llm('inspect', {
            'log_data': log_data,
            'initial_params': self.initial_params,
            'sdc_context': self.sdc_context
        })
        print(f"LLM inspection config: {inspect_configs['inspection']}")
        
        # Step 2: Analyze metrics with LLM config
        print("\nStep 2: Analyzing metrics...")
        metrics = self.analyze_metrics(
            log_data, 
            n_clusters=inspect_configs['inspection']['n_clusters'],
            correlation_threshold=inspect_configs['inspection']['correlation_threshold']
        )
        print(f"Processed metrics for {len(metrics.get('objectives', []))} successful runs")
        
        # Get LLM recommendations for modeling based on inspection results
        print("\nGetting LLM recommendations for modeling...")
        model_configs = self._call_llm('model', {
            'log_data': log_data,
            'metrics': metrics,
            'initial_params': self.initial_params,
            'sdc_context': self.sdc_context,
            'inspection_results': inspect_configs
        })
        print(f"LLM model config: {model_configs['model']}")
        
        # Step 3: Evaluate models with LLM config
        print("\nStep 3: Evaluating models...")
        model_results = self.evaluate_models(
            log_data, metrics,
            kernel_type=model_configs['model']['kernel_type'],
            preprocessing=model_configs['model']['preprocessing'],
            acquisition=model_configs['model']['acquisition'],
            surrogate_weight=model_configs['model']['surrogate_weight']
        )
        
        # Get LLM recommendations for parameter selection based on all previous results
        print("\nGetting LLM recommendations for parameter selection...")
        selection_configs = self._call_llm('agglomerate', {
            'log_data': log_data,
            'metrics': metrics,
            'model_results': model_results,
            'initial_params': self.initial_params,
            'sdc_context': self.sdc_context,
            'inspection_results': inspect_configs,
            'model_configs': model_configs
        })
        print(f"LLM selection config: {selection_configs['selection']}")
        
        # Step 4: Generate parameters with LLM config
        print("\nStep 4: Generating parameters...")
        self.generate_parameters(
            log_data, metrics, model_results, num_runs,
            selection_method=selection_configs['selection']['method'],
            quality_weight=selection_configs['selection']['quality_weight'],
            uncertainty_bonus=selection_configs['selection']['uncertainty_bonus']
        )

    def inspect_logs(self) -> Dict[str, Any]:
        """Step 1: Inspect all logs so far"""
        log_dir = f"logs/{self.platform}/{self.design}"
        log_data = {
            'runs': [],
            'summary': {
                'total_runs': 0,
                'successful_runs': 0,
                'failed_runs': 0
            }
        }
        
        # Ensure log directory exists
        if not os.path.exists(log_dir):
            return log_data
            
        # Process each log file
        for log_file in os.listdir(log_dir):
            if log_file.endswith('.log'):
                run_data = process_log_file(os.path.join(log_dir, log_file))
                log_data['runs'].append(run_data)
                
                # Update summary
                log_data['summary']['total_runs'] += 1
                if run_data['success']:
                    log_data['summary']['successful_runs'] += 1
                else:
                    log_data['summary']['failed_runs'] += 1
                    
        return log_data
        
    def analyze_metrics(self, log_data: Dict[str, Any], n_clusters: int, correlation_threshold: float) -> Dict[str, Any]:
        """Step 2: Analyze metrics from log data with improved analysis"""
        metrics = {
            'objectives': [],
            'surrogates': [],
            'correlations': {},
            'structure_analysis': {}
        }
        
        # Extract feature vectors and objectives
        feature_vectors = []
        objective_values = []
        surrogate_values = []
        
        for run in log_data['runs']:
            if run['success'] and 'metrics' in run:
                run_metrics = run['metrics']
                obj_values = self._calculate_objective(run)
                
                if obj_values['value'] is not None or obj_values['surrogate'] is not None:
                    # Extract parameter values as features
                    params = []
                    for param in self.parameter_names:
                        params.append(float(run.get('parameters', {}).get(param, self.initial_params.get(param, 0))))
                    feature_vectors.append(params)
                    
                    objective_values.append(obj_values['value'] if obj_values['value'] is not None else np.nan)
                    surrogate_values.append(obj_values['surrogate'] if obj_values['surrogate'] is not None else np.nan)
                    
                    # Track correlations and other metrics
                    if obj_values['value'] is not None:
                        metrics['objectives'].append(obj_values['value'])
                    if obj_values['surrogate'] is not None:
                        metrics['surrogates'].append(obj_values['surrogate'])
                    
                    if obj_values['value'] is not None and obj_values['surrogate'] is not None:
                        if 'real_vs_surrogate' not in metrics['correlations']:
                            metrics['correlations']['real_vs_surrogate'] = []
                        metrics['correlations']['real_vs_surrogate'].append({
                            'real': obj_values['value'],
                            'surrogate': obj_values['surrogate']
                        })
        
        if feature_vectors:
            X = np.array(feature_vectors)
            Y = np.array(objective_values)
            Y_surrogate = np.array(surrogate_values)
            
            # Use improved inspection functions
            metrics['distribution_analysis'] = inspect_data_distribution(X, Y, Y_surrogate)
            metrics['structure_analysis'] = inspect_data_structure(X, Y, {
                'n_clusters': n_clusters,
                'correlation_threshold': correlation_threshold
            })
            
            # Extract model recommendations if available (from new functions)
            if 'model_recommendations' in metrics['structure_analysis']:
                metrics['model_recommendations'] = metrics['structure_analysis']['model_recommendations']
            
            # Add objective-specific metrics
            if self.objective == 'ECP':
                metrics['clock_period_impact'] = {}
                for run in log_data['runs']:
                    if run['success'] and 'metrics' in run:
                        period = float(run['metrics'].get('clock_period', 0))
                        if period > 0:
                            if period not in metrics['clock_period_impact']:
                                metrics['clock_period_impact'][period] = {
                                    'final_slack': [],
                                    'cts_slack': []
                                }
                            if 'worst_slack' in run['metrics']:
                                metrics['clock_period_impact'][period]['final_slack'].append(
                                    float(run['metrics']['worst_slack']))
                            if 'cts_ws' in run['metrics']:
                                metrics['clock_period_impact'][period]['cts_slack'].append(
                                    float(run['metrics']['cts_ws']))
            
            elif self.objective == 'DWL':
                metrics['wirelength_progression'] = []
                for run in log_data['runs']:
                    if run['success'] and 'metrics' in run:
                        if 'cts_wirelength' in run['metrics'] and 'total_wirelength' in run['metrics']:
                            metrics['wirelength_progression'].append({
                                'cts': float(run['metrics']['cts_wirelength']),
                                'final': float(run['metrics']['total_wirelength'])
                            })
        
        return metrics
        
    def evaluate_models(self, log_data: Dict[str, Any], metrics: Dict[str, Any], 
                       kernel_type: str, preprocessing: str, acquisition: str, surrogate_weight: float) -> Dict[str, Any]:
        """Step 3: Use improved model functions to evaluate parameter quality"""
        model_results = {}
        
        # Build context from log data and metrics
        context = {
            'log_data': log_data,
            'metrics': metrics,
            'design_config': self.design_config,
            'initial_params': self.initial_params,
            'model_recommendations': metrics.get('model_recommendations', {})
        }
        
        # Use model recommendations if available (from new functions)
        if 'model_recommendations' in metrics:
            kernel_type = metrics['model_recommendations'].get('kernel_type', kernel_type)
            preprocessing = 'robust' if metrics['model_recommendations'].get('needs_feature_scaling', True) else 'none'
        
        # Call appropriate model functions with improved modeling
        if self.objective == 'ECP':
            model_results = evaluate_timing_model(context)
        elif self.objective == 'DWL':
            model_results = evaluate_wirelength_model(context)
        
        # Add model configuration used
        model_results['configuration'] = {
            'kernel_type': kernel_type,
            'preprocessing': preprocessing,
            'acquisition': acquisition,
            'surrogate_weight': surrogate_weight
        }
        
        return model_results
        
    def generate_parameters(self, log_data: Dict[str, Any], metrics: Dict[str, Any],
                          model_results: Dict[str, Any], num_runs: int,
                          selection_method: str = 'hybrid', quality_weight: float = 0.7,
                          uncertainty_bonus: float = 0.2, model_config: Dict[str, Any] = None) -> None:
        """Step 4: Generate parameter combinations and write to CSV"""
        # Get list of parameters to optimize from constraints
        param_names = list(self.param_constraints.keys())
        print(f"\nGenerating parameters for {len(param_names)} variables:")
        for name in param_names:
            print(f"  - {name}: {self.param_constraints[name]}")
        
        # Extract successful runs for training data
        successful_params = []
        successful_objectives = []
        for run in log_data.get('runs', []):
            if run.get('success', False) and 'metrics' in run:
                params = {}
                for param in param_names:
                    params[param] = float(run.get('parameters', {}).get(param, self.initial_params.get(param, 0)))
                successful_params.append(params)
                
                obj = self._calculate_objective(run)
                successful_objectives.append(obj['value'] if obj['value'] is not None else obj['surrogate'])
        
        print(f"Using {len(successful_params)} successful runs as training data")
        
        # Convert to numpy arrays
        if successful_params:
            X = np.array([[params[name] for name in param_names] for params in successful_params])
            y = np.array(successful_objectives)
        else:
            print("Warning: No successful runs, using initial parameters as base")
            X = np.array([[float(self.initial_params.get(name, 0)) for name in param_names]])
            y = np.array([0.0])
        
        # Get kernel type from model config
        kernel_type = model_config.get('kernel_type', 'matern') if model_config else 'matern'
        print(f"\nCreating surrogate model with {kernel_type} kernel")
        model = create_model(X, y, kernel_type=kernel_type)
        
        # Generate candidates
        n_candidates = num_runs * 10
        print(f"Generating {n_candidates} candidate points")
        candidates = latin_hypercube(n_candidates, len(param_names))
        
        # Scale candidates to parameter ranges
        for i, param in enumerate(param_names):
            constraints = self.param_constraints[param]
            min_val = float(constraints['range'][0])
            max_val = float(constraints['range'][1])
            candidates[:, i] = candidates[:, i] * (max_val - min_val) + min_val
        
        # Get predictions
        predictions, uncertainties = model.predict(candidates, return_std=True)
        
        # Select points
        print(f"\nSelecting points using {selection_method} method")
        print(f"Quality weight: {quality_weight}, Uncertainty bonus: {uncertainty_bonus}")
        quality_scores = create_quality_scores(candidates, y, predictions, uncertainties)
        selected_indices = select_points(
            candidates, quality_scores,
            method=selection_method,
            n_points=num_runs,
            config={"quality_weight": quality_weight, 
                   "uncertainty_bonus": uncertainty_bonus}
        )
        
        selected_params = candidates[selected_indices]
        
        # Validate domain constraints
        print("\nValidating domain constraints...")
        valid_params = []
        for params in selected_params:
            param_dict = {name: value for name, value in zip(param_names, params)}
            if self._validate_domain_constraints(param_dict):
                valid_params.append(param_dict)
            else:
                print("Warning: Parameter set failed domain constraints")
        
        print(f"Found {len(valid_params)} valid parameter sets out of {len(selected_params)}")
        
        # Generate more if needed
        while len(valid_params) < num_runs:
            needed = num_runs - len(valid_params)
            print(f"Generating {needed} additional parameter sets...")
            new_candidates = latin_hypercube(needed, len(param_names))
            for i, param in enumerate(param_names):
                constraints = self.param_constraints[param]
                min_val = float(constraints['range'][0])
                max_val = float(constraints['range'][1])
                new_candidates[:, i] = new_candidates[:, i] * (max_val - min_val) + min_val
            
            for params in new_candidates:
                param_dict = {name: value for name, value in zip(param_names, params)}
                if self._validate_domain_constraints(param_dict):
                    valid_params.append(param_dict)
                if len(valid_params) >= num_runs:
                    break
        
        # Write to CSV
        print(f"\nWriting {num_runs} parameter sets to CSV...")
        self._write_params_to_csv(valid_params[:num_runs])
    
    def _calculate_objective(self, run: Dict[str, Any]) -> Dict[str, float]:
        """Calculate objective value and surrogate from run metrics"""
        metrics = run.get('metrics', {})
        result = {'value': None, 'surrogate': None}
        
        if self.objective == 'ECP':
            if 'clock_period' in metrics:
                period = float(metrics['clock_period'])
                # Real ECP from final worst slack
                if 'worst_slack' in metrics:
                    result['value'] = period - float(metrics['worst_slack'])
                # Surrogate ECP from CTS worst slack
                if 'cts_ws' in metrics:
                    result['surrogate'] = period - float(metrics['cts_ws'])
                    
        elif self.objective == 'DWL':
            # Real wirelength from detailed route
            if 'total_wirelength' in metrics:
                result['value'] = float(metrics['total_wirelength'])
            # Surrogate wirelength from CTS
            if 'cts_wirelength' in metrics:
                result['surrogate'] = float(metrics['cts_wirelength'])
                
        elif self.objective == 'COMBO':
            # Get weights from environment variables
            try:
                ecp_weight = float(os.environ.get('ECP_WEIGHT'))
                wl_weight = float(os.environ.get('WL_WEIGHT'))
                ecp_weight_surrogate = float(os.environ.get('ECP_WEIGHT_SURROGATE'))
                wl_weight_surrogate = float(os.environ.get('WL_WEIGHT_SURROGATE'))
            except (ValueError, TypeError):
                raise ValueError("Weights not properly set in environment variables.")
            
            # Calculate real ECP and WL values
            ecp_value = None
            wl_value = None
            if 'clock_period' in metrics:
                clock_period = float(metrics['clock_period'])
                if 'worst_slack' in metrics:
                    ecp_value = clock_period - float(metrics['worst_slack'])
                if 'total_wirelength' in metrics:
                    wl_value = float(metrics['total_wirelength'])

            # Calculate surrogate ECP and WL values
            ecp_surrogate = None
            wl_surrogate = None
            if 'clock_period' in metrics:
                clock_period = float(metrics['clock_period'])
                if 'cts_ws' in metrics:
                    ecp_surrogate = clock_period - float(metrics['cts_ws'])
                if 'cts_wirelength' in metrics:
                    wl_surrogate = float(metrics['cts_wirelength'])

            # Calculate weighted objective for real values
            if ecp_value is not None and wl_value is not None:
                result['value'] = ecp_weight * ecp_value + wl_weight * wl_value
            elif ecp_value is not None:
                result['value'] = ecp_weight * ecp_value
            elif wl_value is not None:
                result['value'] = wl_weight * wl_value

            # Calculate weighted surrogate objective
            if ecp_surrogate is not None and wl_surrogate is not None:
                result['surrogate'] = ecp_weight_surrogate * ecp_surrogate + wl_weight_surrogate * wl_surrogate
            elif ecp_surrogate is not None:
                result['surrogate'] = ecp_weight_surrogate * ecp_surrogate
            elif wl_surrogate is not None:
                result['surrogate'] = wl_weight_surrogate * wl_surrogate

        return result
    
    def _validate_domain_constraints(self, params: Dict[str, Any]) -> bool:
        """Validate parameter combinations against domain constraints"""
        # 1. Core utilization vs cell padding
        core_util = float(params.get('core_util', 0))
        gp_pad = float(params.get('cell_pad_global', 0))
        dp_pad = float(params.get('cell_pad_detail', 0))
        
        if core_util > 80 and (gp_pad > 2 or dp_pad > 2):
            print(f"Domain constraint failed: core_util > 80 and gp_pad > 2 or dp_pad > 2")
            return False
            
        # 2. TNS end percent vs place density
        tns_end = float(params.get('tns', 0))
        place_density = float(params.get('lb_addon', 0))
        
        if tns_end < 70 and place_density > 0.7:
            print(f"Domain constraint failed: tns_end < 70 and place_density > 0.7")
            return False
            
        # 3. CTS cluster constraints
        cts_size = float(params.get('cts_size', 0))
        cts_diameter = float(params.get('cts_diameter', 0))
        
        if cts_size > 30 and cts_diameter < 100:
            print(f"Domain constraint failed: cts_size > 30 and cts_diameter < 100")
            return False
            
        return True
    
    def _write_params_to_csv(self, params_list: List[Dict[str, Any]]) -> None:
        """Write the new parameter sets to the expected CSV file for the next iteration"""
        csv_file = f"designs/{self.platform}/{self.design}/{self.platform}_{self.design}.csv"
        
        # Ensure parameters are in correct order and properly typed
        with open(csv_file, 'w', newline='\n') as f:  # Explicitly use Unix line endings
            writer = csv.writer(f)
            # Write header in correct order
            writer.writerow(self.parameter_names)
            
            # Write parameter rows
            for params in params_list:
                row = []
                for param_name in self.parameter_names:
                    value = params.get(param_name)
                    if value is None:
                        print(f"Warning: Missing value for parameter {param_name}")
                        continue
                        
                    # Apply type constraints
                    constraint = self.param_constraints[param_name]
                    param_type = constraint['type']
                    param_range = constraint['range']
                    
                    try:
                        # First convert to float for uniform handling
                        value = float(value)
                            
                        # Apply range constraints if they exist
                        if param_range is not None:
                            min_val, max_val = param_range
                            range_size = max_val - min_val
                            
                            # If value is too far out of range, resample uniformly
                            if value > max_val + range_size or value < min_val - range_size:
                                value = random.uniform(min_val, max_val)
                                print(f"Resampled {param_name} to {value} (was too far out of range)")
                            else:
                                # Otherwise just clamp to range
                                value = max(min_val, min(max_val, value))

                        # Convert to final type after range enforcement
                        if param_type == 'int':
                            value = int(round(value))
                            
                    except (ValueError, TypeError) as e:
                        print(f"Error converting {param_name} value '{value}' to {param_type}: {e}")
                        continue
                        
                    row.append(value)
                    
                if len(row) == len(self.parameter_names):
                    writer.writerow(row)
                else:
                    print(f"Warning: Skipping incomplete parameter set")
                    
        print(f"New parameter sets written to {csv_file}")

    def _parse_llm_output(self, llm_response: str) -> List[Dict[str, Any]]:
        """Parse the LLM's response and enforce parameter constraints"""
        try:
            param_sets = json.loads(llm_response)
        except json.JSONDecodeError as e:
            print(f"Error parsing LLM response: {e}")
            return []

        constrained_params = []
        for param_set in param_sets:
            ordered_params = {}
            valid = True
            for param in self.parameter_names:
                value = param_set.get(param)
                if value is None:
                    print(f"Parameter '{param}' is missing in the LLM output.")
                    valid = False
                    break
                    
                constraint = self.param_constraints.get(param)
                if constraint:
                    param_type = constraint['type']
                    param_range = constraint['range']
                    
                    try:
                        # First convert to float for uniform handling
                        value = float(value)

                        # Apply range constraints if they exist
                        if param_range is not None:
                            min_val, max_val = param_range
                            range_size = max_val - min_val
                            
                            # If value is too far out of range, resample uniformly
                            if value > max_val + range_size or value < min_val - range_size:
                                value = random.uniform(min_val, max_val)
                                print(f"Resampled {param} to {value} (was too far out of range)")
                            else:
                                # Otherwise just clamp to range
                                value = max(min_val, min(max_val, value))

                        # Convert to final type after range enforcement
                        if param_type == 'int':
                            value = int(round(value))
                        elif param_type != 'float':
                            raise ValueError(f"Unsupported parameter type: {param_type}")

                        ordered_params[param] = value
                    except (ValueError, TypeError) as e:
                        print(f"Parameter '{param}' has invalid value '{value}': {e}")
                        valid = False
                        break
                else:
                    print(f"Unknown parameter '{param}' in parameter set.")
                    valid = False
                    break
                    
            if valid and self._validate_domain_constraints(ordered_params):
                constrained_params.append(ordered_params)
            else:
                print(f"Parameter set {ordered_params} failed validation and will be discarded.")
                
        return constrained_params

    def generate_initial_parameters(self, num_runs: int) -> None:
        """Generate initial random parameters and write them to CSV using the same method as subsequent iterations"""
        params_list = []
        for _ in range(num_runs):
            params = {}
            for param in self.parameter_names:
                info = self.param_constraints[param]
                param_type = info['type']
                min_value, max_value = info['range']
                if param_type == 'int':
                    value = random.randint(int(min_value), int(max_value))
                elif param_type == 'float':
                    value = random.uniform(min_value, max_value)
                else:
                    continue  # Skip unsupported types
                params[param] = value
            params_list.append(params)

        # Use the same method to write parameters to CSV
        self._write_params_to_csv(params_list)

def main():
    if len(sys.argv) != 5:
        print("Usage: optimize.py <platform> <design> <objective> <num_runs>")
        sys.exit(1)
        
    platform = sys.argv[1]
    design = sys.argv[2]
    objective = sys.argv[3]
    num_runs = int(sys.argv[4])
    
    workflow = OptimizationWorkflow(platform, design, objective)
    workflow.run_iteration(num_runs)  # Use the run_iteration method instead of individual steps

if __name__ == "__main__":
    main() 