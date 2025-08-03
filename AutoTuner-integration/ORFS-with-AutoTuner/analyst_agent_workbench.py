import argparse
import json
import pandas as pd
import numpy as np
import uuid
import traceback
import os
from dotenv import load_dotenv
import anthropic # type: ignore
import time # For retry delay
import random # For placeholder BayesOpt, can be removed if BayesOpt is robust

# For Bayesian Optimization
from skopt import Optimizer
from skopt.space import Real, Integer, Categorical
from skopt.utils import use_named_args # For easier handling of parameters

# --- Global State for Tools ---
TOOL_STATE = {
    "current_df": pd.DataFrame(),
    "initial_df_shape": (0, 0), # Shape of data after circuit/pdk filter, before DRC filter
    "initial_df_all_valid_runs": pd.DataFrame(), # Shape after circuit/pdk AND DRC filter
    "pdk": None, # Will be set from args
    "circuit": None, # Will be set from args
    "num_final_suggestions": 5, # Default, will be updated by args
    "final_bayesian_suggestions": None # To store the result of the final BayesOpt call
}

# --- Tool Python Functions ---
# Forward declaration for log_to_file_and_console, as it's defined in run_agent_workbench
# but used by store_all_valid_runs_df. This is a bit of a hack for standalone functions.
# A class-based approach for the agent would encapsulate this better.
_log_func = print 

def set_logger(logger_func):
    global _log_func
    _log_func = logger_func

def log_to_file_and_console(message):
    _log_func(message)

def initialize_tools_data(df_after_circuit_pdk_filter):
    TOOL_STATE["current_df"] = df_after_circuit_pdk_filter.copy()
    TOOL_STATE["initial_df_shape"] = df_after_circuit_pdk_filter.shape

def store_all_valid_runs_df(df_after_drc_filter):
    TOOL_STATE["initial_df_all_valid_runs"] = df_after_drc_filter.copy()
    log_to_file_and_console("[INTERNAL] Stored snapshot of all valid runs. Shape: " + str(df_after_drc_filter.shape))

def reset_data_to_all_valid_runs():
    if TOOL_STATE["initial_df_all_valid_runs"].empty:
        return "Error: The initial set of all valid runs was not stored or is empty. Cannot reset."
    TOOL_STATE["current_df"] = TOOL_STATE["initial_df_all_valid_runs"].copy()
    return "DataFrame has been reset to all valid runs for the current circuit/PDK. New shape: (" + str(TOOL_STATE['current_df'].shape[0]) + ", " + str(TOOL_STATE['current_df'].shape[1]) + ")"

def get_current_data_shape():
    df = TOOL_STATE["current_df"]
    return {"rows": df.shape[0], "columns": df.shape[1]}

def list_columns():
    return list(TOOL_STATE["current_df"].columns)

def get_data_summary(columns_list=None, include_dtypes=False):
    df = TOOL_STATE["current_df"]
    if df.empty: return "Current data subset is empty."
    try:
        target_cols = columns_list if columns_list and len(columns_list) > 0 else df.columns
        valid_cols = [col for col in target_cols if col in df.columns]
        if not valid_cols: return "Error: None of specified columns " + str(target_cols) + " found."
        summary = df[valid_cols].describe(include='all').to_string()
        if include_dtypes: 
            dtypes = df[valid_cols].dtypes.to_string()
            return "Data Summary:\n" + summary + "\n\nData Types:\n" + dtypes
        return "Data Summary:\n" + summary
    except Exception as e: return "Error in get_data_summary: " + str(e) + "\n" + traceback.format_exc()

def get_value_distribution(column_name, bins=10, top_n=10):
    # Work on a copy of the relevant column from current_df to avoid SettingWithCopyWarning
    # when modifying dtypes, then update TOOL_STATE if conversion happens.
    if TOOL_STATE["current_df"].empty: return "Current data subset is empty."
    if column_name not in TOOL_STATE["current_df"].columns: 
        return "Error: Column '" + column_name + "' not found."
    
    series_to_analyze = TOOL_STATE["current_df"][column_name].copy()

    try:
        if not pd.api.types.is_numeric_dtype(series_to_analyze):
            converted_series = pd.to_numeric(series_to_analyze, errors='coerce')
            # Only update the global state if the conversion actually changed the dtype
            # or if it's now numeric (even if it was object with numbers before)
            if pd.api.types.is_numeric_dtype(converted_series):
                 TOOL_STATE["current_df"][column_name] = converted_series
                 series_to_analyze = TOOL_STATE["current_df"][column_name] # use the updated series from global state

        if pd.api.types.is_numeric_dtype(series_to_analyze):
            valid_data = series_to_analyze.dropna()
            if valid_data.empty:
                return {"type": "numerical", "message": "No valid data points to create distribution."}
            counts, bin_edges = np.histogram(valid_data, bins=bins)
            return {"type": "numerical", "bin_edges": list(bin_edges), "counts": [int(c) for c in counts]}
        else:
            counts = series_to_analyze.value_counts().nlargest(top_n).to_dict()
            other_count = len(series_to_analyze) - sum(counts.values())
            if other_count > 0: counts["_OTHER_VALUES_"] = other_count
            # Ensure all keys in counts are strings for JSON compatibility
            return {"type": "categorical", "distribution": {str(k): int(v) for k, v in counts.items()}}
    except Exception as e: return "Error in get_value_distribution for " + column_name + ": " + str(e) + "\n" + traceback.format_exc()

def get_correlations_for_column(target_column_name, other_columns_list=None, top_n=10):
    if TOOL_STATE["current_df"].empty: return "Current data subset is empty."
    if target_column_name not in TOOL_STATE["current_df"].columns:
        return "Error: Target column '" + target_column_name + "' not found."

    # Ensure target column is numeric in TOOL_STATE["current_df"]
    if not pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][target_column_name]):
        original_dtype = TOOL_STATE["current_df"][target_column_name].dtype
        converted_target_col = pd.to_numeric(TOOL_STATE["current_df"][target_column_name].copy(), errors='coerce')
        if converted_target_col.isnull().all() and not TOOL_STATE["current_df"][target_column_name].isnull().all(): # if all became NaN and weren't before
             return "Error: Target column '" + target_column_name + "' could not be converted to numeric (all values are non-numeric). Original dtype: " + str(original_dtype)
        TOOL_STATE["current_df"][target_column_name] = converted_target_col
        if not pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][target_column_name]): # Check again after assignment
             return "Error: Target column '" + target_column_name + "' is not numeric even after attempting conversion. Final dtype: " + str(TOOL_STATE["current_df"][target_column_name].dtype)
    
    # Process other columns for numeric conversion
    current_df_cols = TOOL_STATE["current_df"].columns
    cols_to_correlate_with = []
    
    potential_other_cols = other_columns_list if other_columns_list and len(other_columns_list) > 0 \
        else [col for col in current_df_cols if col != target_column_name and pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][col])] # default to already numeric

    if other_columns_list and len(other_columns_list) > 0: # If specific list given, try to convert them
        for col_name in other_columns_list:
            if col_name in current_df_cols and col_name != target_column_name:
                if not pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][col_name]):
                    converted_other_col = pd.to_numeric(TOOL_STATE["current_df"][col_name].copy(), errors='coerce')
                    TOOL_STATE["current_df"][col_name] = converted_other_col # Update global state
                if pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][col_name]):
                    cols_to_correlate_with.append(col_name)
    else: # Default to all *other* columns that are already numeric or can be made numeric
        for col_name in current_df_cols:
            if col_name != target_column_name:
                if not pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][col_name]):
                    converted_other_col = pd.to_numeric(TOOL_STATE["current_df"][col_name].copy(), errors='coerce')
                    TOOL_STATE["current_df"][col_name] = converted_other_col
                if pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][col_name]):
                    cols_to_correlate_with.append(col_name)
                    
    if not cols_to_correlate_with: return "No suitable *other* numeric columns found to correlate with '" + target_column_name + "'."
    
    # Ensure target_column_name is in the list if not already, and all are valid for correlation
    final_cols_for_corr = [target_column_name] + [col for col in cols_to_correlate_with if col != target_column_name]
    # Use .loc with a list of valid columns that are confirmed numeric in the current_df
    df_for_corr = TOOL_STATE["current_df"].loc[:, [c for c in final_cols_for_corr if c in TOOL_STATE["current_df"].columns and pd.api.types.is_numeric_dtype(TOOL_STATE["current_df"][c])]]

    if target_column_name not in df_for_corr.columns:
         return "Error: Target column '" + target_column_name + "' was lost or is not numeric after processing other columns for correlation."

    try:
        correlations = df_for_corr.corr(numeric_only=True)[target_column_name].drop(target_column_name, errors='ignore')
        if correlations.empty:
            return "No valid correlations could be computed for '" + target_column_name + "' with the selected other columns."
        top_abs_corr = correlations.abs().nlargest(top_n)
        return correlations.loc[top_abs_corr.index].to_dict()
    except Exception as e: return "Error in get_correlations_for_column for " + target_column_name + ": " + str(e) + "\n" + traceback.format_exc()

def filter_data(query_string):
    df = TOOL_STATE["current_df"]
    if df.empty: return "Current data subset is empty. Cannot filter."
    try:
        original_rows = df.shape[0]
        TOOL_STATE["current_df"] = df.query(query_string) 
        new_rows = TOOL_STATE["current_df"].shape[0]
        return "Filter '" + query_string + "' applied. Data shape changed from (" + str(original_rows) + ", " + str(df.shape[1]) + ") to (" + str(new_rows) + ", " + str(TOOL_STATE['current_df'].shape[1]) + "). Rows removed: " + str(original_rows - new_rows) + "."
    except Exception as e: return "Error applying filter '" + query_string + "': " + str(e) + ". DataFrame unchanged."

def get_sample_rows(n_rows=3, query_string=None):
    df_to_sample = TOOL_STATE["current_df"]
    if df_to_sample.empty: return "Current data subset is empty."
    header = "Sample of " + str(n_rows) + " rows from current data (" + str(df_to_sample.shape[0]) + " total entries)"
    try:
        if query_string:
            temp_filtered_df = df_to_sample.query(query_string)
            if temp_filtered_df.empty: return "Temporary filter '" + query_string + "' resulted in 0 rows."
            df_to_sample = temp_filtered_df
            header = "Sample of " + str(n_rows) + " rows, temp filter '" + query_string + "' (" + str(df_to_sample.shape[0]) + " matching)"
        
        actual_n_rows = min(n_rows, df_to_sample.shape[0])
        if actual_n_rows == 0: # Handles df_to_sample being empty or n_rows being 0
             return header + ":\n(No rows to sample)"
        return header + ":\n" + df_to_sample.sample(actual_n_rows).to_string()
    except Exception as e: return "Error in get_sample_rows: " + str(e) + "\n" + traceback.format_exc()

def suggest_bayesian_optimization_configs(target_metric_to_minimize, n_suggestions=5, training_data_query=None, validation_data_query=None):
    log_to_file_and_console("[BAYESOPT] Called suggest_bayesian_optimization_configs.")
    log_to_file_and_console("[BAYESOPT] Target metric: " + str(target_metric_to_minimize))
    log_to_file_and_console("[BAYESOPT] N suggestions: " + str(n_suggestions))

    df_for_bo = TOOL_STATE["current_df"].copy()
    if training_data_query:
        log_to_file_and_console("[BAYESOPT] Applying training data query: " + str(training_data_query))
        try:
            df_for_bo = df_for_bo.query(training_data_query)
            if df_for_bo.empty:
                return "Error: The training_data_query resulted in an empty dataset. Cannot train BayesOpt model."
            log_to_file_and_console("[BAYESOPT] Data for BO after query. Shape: " + str(df_for_bo.shape))
        except Exception as e:
            return "Error applying training_data_query '" + str(training_data_query) + "': " + str(e)
    else:
        log_to_file_and_console("[BAYESOPT] Using all current data for BO. Shape: " + str(df_for_bo.shape))

    if validation_data_query:
        log_to_file_and_console("[BAYESOPT] Note: validation_data_query '" + str(validation_data_query) + "' is acknowledged but not used by this skopt implementation yet.")

    try:
        with open("constraints.json", 'r') as f:
            constraints_map = json.load(f)
    except FileNotFoundError:
        return "Error: constraints.json not found. Cannot define search space."
    except json.JSONDecodeError:
        return "Error: constraints.json is not valid JSON. Cannot define search space."

    current_pdk = TOOL_STATE.get("pdk")
    if not current_pdk:
        return "Error: PDK not found in TOOL_STATE. Cannot determine CLK constraints."

    # Define search space for skopt
    search_space = []
    param_names = [] # To maintain order for skopt

    for param_name, details in constraints_map.items():
        param_names.append(param_name)
        if param_name == "CLK":
            if details.get("pdk_specific") and current_pdk in details:
                pdk_constraint = details[current_pdk]
                if pdk_constraint["type"] == "float":
                    search_space.append(Real(pdk_constraint["range"][0], pdk_constraint["range"][1], name=param_name))
                elif pdk_constraint["type"] == "integer":
                    search_space.append(Integer(pdk_constraint["range"][0], pdk_constraint["range"][1], name=param_name))
            else:
                return "Error: CLK constraint for PDK '" + str(current_pdk) + "' not defined in constraints.json."
        elif details["type"] == "float":
            search_space.append(Real(details["range"][0], details["range"][1], name=param_name))
        elif details["type"] == "integer":
            search_space.append(Integer(details["range"][0], details["range"][1], name=param_name))
        elif details["type"] == "binary": # Using Categorical for binary
            search_space.append(Categorical(details["values"], name=param_name))

    if target_metric_to_minimize not in df_for_bo.columns:
        return "Error: Target metric '" + str(target_metric_to_minimize) + "' not found in the dataset provided for Bayesian Optimization."
    
    df_for_bo[target_metric_to_minimize] = pd.to_numeric(df_for_bo[target_metric_to_minimize], errors='coerce')

    # Prepare data for skopt: X_observed (features), y_observed (target)
    X_observed_list = []
    y_observed_list = []

    # Convert feature columns to numeric where appropriate and handle NaNs
    for col_name in param_names:
        if col_name in df_for_bo.columns:
            param_constraint = constraints_map[col_name]
            col_type = ""
            if col_name == "CLK": # Handle PDK-specific parameter to get its type
                if param_constraint.get("pdk_specific") and current_pdk in param_constraint:
                    col_type = param_constraint[current_pdk]["type"]
                else:
                    # Should have been caught earlier when defining search_space, but good to be safe
                    return "Error: CLK constraint type for PDK '" + str(current_pdk) + "' not found during data prep."
            else: # Non-PDK-specific parameters
                col_type = param_constraint["type"]
            
            if col_type in ["float", "integer"]:
                 df_for_bo[col_name] = pd.to_numeric(df_for_bo[col_name], errors='coerce')
        else:
            return "Error: Parameter '" + str(col_name) + "' from constraints.json not found in dataset for BO."

    # Drop rows where target or any feature is NaN after conversion
    df_for_bo_cleaned = df_for_bo.dropna(subset=[target_metric_to_minimize] + param_names).copy()

    if df_for_bo_cleaned.empty:
        return "Error: After cleaning (removing NaNs in target or features), no data remains for Bayesian Optimization training."
    log_to_file_and_console("[BAYESOPT] Data for BO after NaN cleaning. Shape: " + str(df_for_bo_cleaned.shape))

    # --- BEGIN ADDED FILTERING FOR CTS PARAMETERS ---
    original_rows_before_cts_filter = df_for_bo_cleaned.shape[0]
    if 'CTS_CSIZE' in df_for_bo_cleaned.columns:
        df_for_bo_cleaned = df_for_bo_cleaned[df_for_bo_cleaned['CTS_CSIZE'] != 1]
        log_to_file_and_console(f"[BAYESOPT] Filtered out rows where CTS_CSIZE is 1. New shape: {df_for_bo_cleaned.shape}")
    if 'CTS_CDIA' in df_for_bo_cleaned.columns:
        df_for_bo_cleaned = df_for_bo_cleaned[df_for_bo_cleaned['CTS_CDIA'] != 1]
        log_to_file_and_console(f"[BAYESOPT] Filtered out rows where CTS_CDIA is 1. New shape: {df_for_bo_cleaned.shape}")
    
    if df_for_bo_cleaned.empty:
        return "Error: After filtering out CTS values of 1, no data remains for Bayesian Optimization training."
    if df_for_bo_cleaned.shape[0] < original_rows_before_cts_filter:
        log_to_file_and_console(f"[BAYESOPT] Note: {original_rows_before_cts_filter - df_for_bo_cleaned.shape[0]} rows with CTS_CSIZE=1 or CTS_CDIA=1 were excluded from optimizer training data.")
    # --- END ADDED FILTERING FOR CTS PARAMETERS ---

    X_observed_list = df_for_bo_cleaned[param_names].values.tolist()
    y_observed_list = df_for_bo_cleaned[target_metric_to_minimize].tolist()

    if not X_observed_list or not y_observed_list:
        return "Error: No valid historical data (X_observed, y_observed) to train the Bayesian Optimizer after processing."
    if len(X_observed_list) < 2: # skopt often needs at least 2 points to start GP
        return ("Error: Insufficient historical data points (" + str(len(X_observed_list)) +
                ") to train the Bayesian Optimizer. Need at least 2. Consider broadening training_data_query or checking data quality.")

    try:
        # --- BEGIN ADDED DEBUG LOGGING ---
        log_to_file_and_console("[BAYESOPT DEBUG] Checking if observed points are within search space bounds...")
        out_of_bounds_details = []
        for i, x_point in enumerate(X_observed_list):
            point_details = []
            is_point_out_of_bounds = False
            for j, dim_value in enumerate(x_point):
                current_dim = search_space[j]
                param_name = current_dim.name
                
                if isinstance(current_dim, Categorical):
                    if dim_value not in current_dim.categories:
                        is_point_out_of_bounds = True
                        point_details.append(f"Param '{param_name}' (Categorical): Value {dim_value} not in categories {current_dim.categories}")
                elif isinstance(current_dim, (Real, Integer)):
                    low, high = current_dim.low, current_dim.high
                    if not (low <= dim_value <= high):
                        is_point_out_of_bounds = True
                        point_details.append(f"Param '{param_name}' (Numeric): Value {dim_value} not in range [{low}, {high}]")
                # else: # Should not happen if search_space is built correctly
                #     log_to_file_and_console(f"[BAYESOPT DEBUG] Unknown dimension type for {param_name}: {type(current_dim)}")
            
            if is_point_out_of_bounds:
                out_of_bounds_details.append(f"  Point index {i} (from df_for_bo_cleaned original index: {df_for_bo_cleaned.index[i]}): {'; '.join(point_details)}")

        if out_of_bounds_details:
            log_to_file_and_console("[BAYESOPT DEBUG] Found points out of bounds:")
            for detail in out_of_bounds_details:
                log_to_file_and_console(detail)
            # Optionally, we could return an error here instead of letting skopt raise it,
            # but letting skopt raise it is also fine as it's more direct.
            # return {"error": "Data points out of bounds. See logs for details."}
        else:
            log_to_file_and_console("[BAYESOPT DEBUG] All observed points appear to be within search space bounds.")
        # --- END ADDED DEBUG LOGGING ---

        optimizer = Optimizer(
            dimensions=search_space,
            base_estimator="GP",      # Gaussian Process
            acq_func="EI",           # Expected Improvement
            random_state=None        # For reproducibility, set an int, else None
        )

        log_to_file_and_console("[BAYESOPT] Telling optimizer about " + str(len(X_observed_list)) + " observed points.")
        optimizer.tell(X_observed_list, y_observed_list)

        log_to_file_and_console("[BAYESOPT] Asking optimizer for " + str(n_suggestions) + " new suggestions.")
        suggested_points = optimizer.ask(n_points=n_suggestions)

        suggestions = []
        for point in suggested_points:
            config = {}
            for i, param_name in enumerate(param_names):
                # skopt Real space can return numpy float types, ensure Python native types
                if isinstance(point[i], np.integer):
                    config[param_name] = int(point[i])
                elif isinstance(point[i], np.floating):
                    config[param_name] = float(round(point[i], 3)) # Keep rounding for floats
                else:
                    config[param_name] = point[i] # For Categorical (binary)
            suggestions.append(config)

        log_to_file_and_console("[BAYESOPT] Generated " + str(len(suggestions)) + " configurations using scikit-optimize.")
        return {"suggested_configurations": suggestions}

    except Exception as e:
        return "Error during Bayesian Optimization with skopt: " + str(e) + "\n" + traceback.format_exc()

PYTHON_TOOLS_MAP = {
    "get_current_data_shape": get_current_data_shape,
    "list_columns": list_columns,
    "get_data_summary": get_data_summary,
    "get_value_distribution": get_value_distribution,
    "get_correlations_for_column": get_correlations_for_column,
    "filter_data": filter_data,
    "get_sample_rows": get_sample_rows,
    "reset_data_to_all_valid_runs": reset_data_to_all_valid_runs,
    "suggest_bayesian_optimization_configs": suggest_bayesian_optimization_configs,
    "suggest_new_tool": lambda suggested_tool_name, suggested_tool_description: log_to_file_and_console("[LLM TOOL SUGGESTION]\nName: " + str(suggested_tool_name) + "\nDescription: " + str(suggested_tool_description)) or "New tool suggestion noted: " + str(suggested_tool_name) 
}

ANTHROPIC_TOOL_SCHEMAS = [
    {
        "name": "get_current_data_shape",
        "description": "Returns the current shape (rows, columns) of the active DataFrame.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "list_columns",
        "description": "Returns a list of available column names in the current DataFrame.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "get_data_summary",
        "description": "Returns descriptive statistics for specified columns or all columns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "columns_list": {"type": "array", "items": {"type": "string"}, "description": "Optional. List of column names to summarize. Defaults to all."},
                "include_dtypes": {"type": "boolean", "description": "Optional. If True, includes data types. Defaults to False."}
            }
        }
    },
    {
        "name": "get_value_distribution",
        "description": "Value counts for categorical or binned distribution for numerical columns. Attempts to convert column to numeric if it's not already.",
        "input_schema": {
            "type": "object",
            "properties": {
                "column_name": {"type": "string", "description": "The column to analyze."},
                "bins": {"type": "integer", "default": 10, "description": "Number of bins for numerical data. Defaults to 10."},
                "top_n": {"type": "integer", "default": 10, "description": "Max unique values for categorical. Defaults to 10."}
            },
            "required": ["column_name"]
        }
    },
    {
        "name": "get_correlations_for_column",
        "description": "Top N correlations between a target numeric column and other numeric columns. Attempts to convert columns to numeric if they are not already.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_column_name": {"type": "string", "description": "The primary numeric column for correlation."},
                "other_columns_list": {"type": "array", "items": {"type": "string"}, "description": "Optional. List of other numeric columns. Defaults to all others."},
                "top_n": {"type": "integer", "default": 10, "description": "Number of top correlations. Defaults to 10."}
            },
            "required": ["target_column_name"]
        }
    },
    {
        "name": "filter_data",
        "description": "Filters the active DataFrame. THIS MODIFIES THE DATA FOR SUBSEQUENT CALLS. Returns new shape and rows removed.",
        "input_schema": {
            "type": "object",
            "properties": {"query_string": {"type": "string", "description": "Pandas query string (e.g., \"`col_name` > 0 and `another_col` == 'value'\"). Note: column names with spaces or special characters must be enclosed in backticks."}},
            "required": ["query_string"]
        }
    },
    {
        "name": "get_sample_rows",
        "description": "Shows sample rows. Can sample from a temporarily filtered view (does not modify main data).",
        "input_schema": {
            "type": "object",
            "properties": {
                "n_rows": {"type": "integer", "default": 3, "description": "Number of sample rows. Defaults to 3."},
                "query_string": {"type": "string", "description": "Optional temporary pandas query string to sample from a subset."}
            }
        }
    },
    {
        "name": "reset_data_to_all_valid_runs",
        "description": "Resets the active DataFrame to the initial set of all valid runs (i.e., after initial circuit, PDK, and DRC error filtering). Useful if subsequent filters have made the DataFrame too small or empty.",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "suggest_new_tool",
        "description": "Suggest a new tool that would be helpful for the analysis. Provide a name and a detailed description of what the tool should do and what its inputs/outputs might be.",
        "input_schema": {
            "type": "object",
            "properties": {
                "suggested_tool_name": {"type": "string", "description": "A concise name for the suggested tool (e.g., 'plot_histogram')."},
                "suggested_tool_description": {"type": "string", "description": "Detailed description of the tool's purpose, inputs, and expected output or behavior."}
            },
            "required": ["suggested_tool_name", "suggested_tool_description"]
        }
    },
    {
        "name": "terminate_interaction",
        "description": "Signals completion of the analysis. Provide a final summary of your findings.",
        "input_schema": {
            "type": "object",
            "properties": {"final_summary": {"type": "string", "description": "A comprehensive summary of findings."}},
            "required": ["final_summary"]
        }
    },
    {
        "name": "suggest_bayesian_optimization_configs",
        "description": "Suggests a list of hyperparameter configurations using scikit-optimize Bayesian Optimization. Useful for proposing new runs based on historical data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "target_metric_to_minimize": {
                    "type": "string",
                    "description": "The name of the column in the dataset that the optimization should aim to minimize (e.g., 'ECP_final', 'detailedroute__route__wirelength')."
                },
                "n_suggestions": {
                    "type": "integer",
                    "default": 5,
                    "description": "Number of new configurations to suggest. Defaults to 5. For the final call before termination, use the value specified by the --num_final_suggestions startup argument."
                },
                "training_data_query": {
                    "type": "string",
                    "description": "Optional. A pandas query string (e.g., \"`CLK` < 1000 and `UTIL` > 50\"). If provided, the optimizer will train its model only on data matching this query. Defaults to using all data in the agent's current DataFrame."
                },
                "validation_data_query": {
                    "type": "string",
                    "description": "Optional. A pandas query string to select a subset for validating the surrogate model's predictions. Currently a placeholder, no actual validation performed by this tool."
                }
            },
            "required": ["target_metric_to_minimize"]
        }
    }
]

def run_agent_workbench(main_df=None, circuit=None, pdk=None,
                        optimization_goal=None, num_final_suggestions=None,
                        max_agent_calls=None, log_dir="./"):
    parser = argparse.ArgumentParser(description="Anthropic LLM Agent Workbench for OpenROAD Data Exploration.")
    parser.add_argument("circuit", type=str, help="Name of the circuit")
    parser.add_argument("pdk", type=str, help="Name of the PDK")
    parser.add_argument("optimization_goal", type=str, help="Optimization goal key from output.json")
    parser.add_argument("--model_name", type=str, default="claude-sonnet-4-20250514", help="Anthropic model name to use.")
    parser.add_argument("--max_agent_calls", type=int, default=30, help="Maximum number of calls to the agent.")
    parser.add_argument("--num_final_suggestions", type=int, default=5, help="Number of configurations for the BayesOpt tool to suggest in the final step.")
    
    args = parser.parse_args()
    
    
    ## Add circuit, pdk, num_final_suggestion and optimization goal it args if they are not None
    if circuit is not None: args.circuit = circuit
    if pdk is not None: args.pdk = pdk
    if optimization_goal is not None: args.optimization_goal = optimization_goal
    if num_final_suggestions is not None: args.num_final_suggestions = num_final_suggestions
    if max_agent_calls is not None: args.max_agent_calls = max_agent_calls
    
    TOOL_STATE["num_final_suggestions"] = args.num_final_suggestions
    
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        try:
            from anthropic_key import ANTHROPIC_API_KEY as direct_key # type: ignore
            api_key = direct_key
            print("INFO: Loaded ANTHROPIC_API_KEY from anthropic_key.py")
        except (ImportError, AttributeError):
            if "ANTHROPIC_API_KEY" not in os.environ: 
                print("Error: ANTHROPIC_API_KEY not found in environment, .env file, or anthropic_key.py.")
                return
            else: 
                api_key = os.environ["ANTHROPIC_API_KEY"]

    try:
        client = anthropic.Anthropic(api_key=api_key)
    except Exception as e:
        print("Error initializing Anthropic client: " + str(e))
        return
        
    session_uuid = uuid.uuid4()
    context_file_name = log_dir + "/" + args.circuit + "_" + args.pdk + "_" + args.optimization_goal + "_context_" + str(session_uuid) + ".txt"
    conversation_history = []

    def local_log_to_file_and_console(log_item):
        # print(log_item)
        with open(context_file_name, 'a', encoding='utf-8') as f:
            f.write(str(log_item) + "\n")
    
    set_logger(local_log_to_file_and_console) 

    log_to_file_and_console("[SETUP] Agent session started. Circuit: " + args.circuit + ", PDK: " + args.pdk + ", Goal: Minimize '" + args.optimization_goal + "'. Model: " + args.model_name + ". Context: " + context_file_name + ". Num final suggestions: " + str(args.num_final_suggestions))
    TOOL_STATE["pdk"] = args.pdk
    TOOL_STATE["circuit"] = args.circuit

    try:
        if main_df is None:
            with open("output.json", 'r', encoding='utf-8') as f: all_data = json.load(f)
            main_df = pd.DataFrame(all_data)
        log_to_file_and_console("[DATA LOADING] Loaded output.json. Total entries: " + str(len(main_df)))
        
        filtered_df_circuit_pdk = main_df[(main_df['circuit'] == args.circuit) & (main_df['pdk'] == args.pdk)]
        if filtered_df_circuit_pdk.empty:
            log_to_file_and_console("[DATA FILTERING ERROR] No data for circuit '" + args.circuit + "' and PDK '" + args.pdk + "'. Exiting.")
            return
        initialize_tools_data(filtered_df_circuit_pdk)
        log_to_file_and_console("[INITIAL DATA FILTER] Data filtered for circuit/PDK. Entries for agent: " + str(TOOL_STATE['current_df'].shape[0]))

        drc_column = 'detailedroute__route__drc_errors'
        current_df_copy = TOOL_STATE['current_df'].copy()

        if drc_column not in current_df_copy.columns:
            log_to_file_and_console("[DATA FILTERING WARNING] DRC column '" + drc_column + "' not found. Storing current data as 'all_valid_runs'.")
            store_all_valid_runs_df(current_df_copy)
            TOOL_STATE['current_df'] = current_df_copy 
        else:
            current_df_copy[drc_column] = pd.to_numeric(current_df_copy[drc_column], errors='coerce')
            initial_drc_filtered_df = current_df_copy[current_df_copy[drc_column] == 0].copy()
            
            if initial_drc_filtered_df.empty:
                log_to_file_and_console("[DATA FILTERING WARNING] No runs with '" + drc_column + "' == 0 found after coercing to numeric. 'all_valid_runs' will be empty.")
            
            TOOL_STATE['current_df'] = initial_drc_filtered_df
            store_all_valid_runs_df(initial_drc_filtered_df)
            log_to_file_and_console("[INITIAL DRC FILTER] Data filtered for '" + drc_column + "' == 0. Entries for agent: " + str(TOOL_STATE['current_df'].shape[0]))

        if TOOL_STATE['current_df'].empty:
             log_to_file_and_console("[CRITICAL] After initial and DRC filtering, the dataset for the agent is empty. Exiting.")
             return

    except Exception as e:
        log_to_file_and_console("[CRITICAL ERROR] Failed to load/filter data: " + str(e) + "\n" + traceback.format_exc())
        return

    prompt_md_content = ""
    try:
        with open("prompt.md", 'r', encoding='utf-8') as f: prompt_md_content = f.read()
        log_to_file_and_console("[INFO] Successfully loaded prompt.md")
    except FileNotFoundError:
        log_to_file_and_console("[WARNING] prompt.md not found. Proceeding without its content.")
    except Exception as e:
        log_to_file_and_console("[WARNING] Error reading prompt.md: " + str(e) + ". Proceeding without its content.")

    tool_schemas_for_prompt = json.dumps(ANTHROPIC_TOOL_SCHEMAS, indent=2)
    
    system_prompt = (
        prompt_md_content + "\n\n---\n\n" +
        "You are an Analyst Agent. Your task is to explore a dataset for circuit '" + args.circuit + "' with PDK '" + args.pdk + "'. " +
        "Your primary optimization goal is to understand factors that help MINIMIZE the metric: '" + args.optimization_goal + "'.\\n" +
        "CRITICAL CONSTRAINT: The initial dataset has ALREADY been filtered for runs where `detailedroute__route__drc_errors` is 0. You are working with valid runs.\\n" +
        "You have a maximum of " + str(args.max_agent_calls) + " interactions. Make each call count!\\n" +
        "The initial dataset of valid runs has " + str(TOOL_STATE['current_df'].shape[0]) + " entries and " + str(TOOL_STATE['current_df'].shape[1]) + " columns.\\n" +
        "A small sample row from your current dataset (if not empty):\\n" + 
        (TOOL_STATE['current_df'].sample(min(1, len(TOOL_STATE['current_df']))).to_string() if not TOOL_STATE['current_df'].empty else "(Dataset is currently empty or too small for sampling)") + "\\n\\n" +
        "TOOLS AVAILABLE:\\n" + tool_schemas_for_prompt + "\\n\\n" +
        "**Your Analytical Workflow (Perform this diligently BEFORE final suggestions):**\\n" +
        "0. **Initial Deep Dive (Crucial First Step):** Dedicate your initial ~5-7 turns (or more if needed) to a thorough understanding of the dataset. Do NOT rush to `suggest_bayesian_optimization_configs` (not even for exploration) until you have a solid grasp of the data landscape, key distributions, and initial correlations. This foundational analysis is critical.\\n" +
        "1. **Understand the Landscape:** Use `get_data_summary` (with `include_dtypes=True`), `get_value_distribution` for key parameters (especially '" + args.optimization_goal + "', 'CLK', 'UTIL', 'TNS_End_Percent', 'LB_ADDON'), and `get_correlations_for_column` for '" + args.optimization_goal + "'. Iterate on these tools to build a comprehensive picture.\\n" +
        "2. **Reference Baselines:** The `prompt.md` content (provided above) contains baseline configurations for (circuit, PDK) pairs (e.g., for 'aes' with 'asap7', baseline CLK is 400ps, UTIL 40, etc.). After your initial data exploration, explicitly compare characteristics of your overall dataset and particularly good-performing runs against these baseline values. For instance, are the best ECP_final values achieved with CLK near, above, or below the baseline CLK? How does UTIL in top runs compare to baseline UTIL?\\\\n" +
        "3. **Hypothesize and Filter:** Based on your deep dive (correlations, distributions, baseline comparisons), form well-reasoned hypotheses. For example, if low CLK and high TNS_End_Percent seem to correlate with good '" + args.optimization_goal + "', filter the data to investigate this subset further using `filter_data` and `get_sample_rows` or `get_data_summary` on the subset. Test multiple hypotheses if necessary.\\\\n" +
        "4. **Iterative Exploration (Optional, and only after solid initial analysis):** ONLY IF your initial deep dive (steps 0-3) has yielded strong hypotheses and a clear direction, you MIGHT use `suggest_bayesian_optimization_configs` with a `training_data_query` to see what kind of suggestions it provides. This is for exploration, not for the final output yet. You can then analyze these intermediate suggestions if you wish, or refine your query. If your initial analysis is inconclusive, spend more turns on steps 1-3.\\\\n" +
        "   **Note on `suggest_bayesian_optimization_configs` behavior:** The `training_data_query` helps the optimizer learn from a specific subset of data. However, when the tool *suggests new points*, it explores the full parameter ranges defined in `constraints.json`. If its suggestions seem too far from your queried region, you might need an even more restrictive `training_data_query` for further *exploratory* calls, or simply acknowledge this exploratory behavior for the *final* set of suggestions.\\\\n" +
        "5. **Develop a Rationale:** Before generating final suggestions, you should have a clear rationale, derived from your exploration, about what parameter regions seem promising and why, especially in relation to the optimization goal and known baselines.\\n\\n" +
        "**Final Configuration Generation (Mandatory Final Steps):**\\n" +
        "Your ultimate task is to propose a set of promising hyperparameter configurations. To do this:\\\\n" +
        "    a. **DO NOT** manually list specific parameter values in your textual analysis or final summary as the *primary* output of your work. Your analysis leads to the BayesOpt call.\\\\n" +
        "    b. You **MUST** use the `suggest_bayesian_optimization_configs` tool for the final generation of configurations. The `training_data_query` for this final call should be based on your comprehensive analysis and rationale developed in the steps above. This query should reflect your strongest beliefs about promising regions. Be aware that the tool will generate suggestions from the full search space (defined in `constraints.json`) but will be guided by the data within your query.\\\\n" +
        "    c. When you are ready to generate this final set, or if you are approaching your `max_agent_calls` limit, call `suggest_bayesian_optimization_configs` and request " + str(args.num_final_suggestions) + " suggestions (this is the `n_suggestions` parameter for the tool call). THIS IS A MANDATORY STEP. Aim for these suggestions to explore somewhat diverse but promising areas based on your analysis. The " + str(args.num_final_suggestions) + " suggestions should ideally be meaningfully distinct from each other to explore different potential optima within the promising region you've identified; avoid requesting suggestions that are extremely close or redundant.\\\\n" +
        "    d. After the `suggest_bayesian_optimization_configs` tool provides the configurations (which will be stored automatically), your next step should be to use the `terminate_interaction` tool. Your `final_summary` for `terminate_interaction` should briefly recap your main insights and state that the suggested configurations were generated by the optimization tool and have been saved to `final_params.json`. The summary itself will be saved to `final_thought.json`.\\\\n\\\\n" +
        "**General Notes:**\\\\n" +
        "If a tool modifies the dataset (e.g., `filter_data`), subsequent analysis will be on the modified data. Use `reset_data_to_all_valid_runs` to revert if needed.\\\\n" +
        "You can use `suggest_new_tool` to propose a new tool if you find the current toolkit insufficient."
    )

    log_to_file_and_console("\n[SYSTEM INITIAL PROMPT TO LLM]\n" + system_prompt)
    conversation_history.append({"role": "user", "content": system_prompt}) 
    
    for call_count in range(1, args.max_agent_calls + 1):
        log_to_file_and_console("\n[AGENT TURN " + str(call_count) + "/" + str(args.max_agent_calls) + "]")
        
        try:
            log_to_file_and_console("Waiting for LLM response...")
            if not conversation_history:
                log_to_file_and_console("[ERROR] Conversation history is empty. Aborting turn.")
                break

            response = client.messages.create(
                model=args.model_name,
                max_tokens=4000,
                tools=ANTHROPIC_TOOL_SCHEMAS,
                messages=conversation_history 
            )
            log_to_file_and_console("[LLM RAW RESPONSE (Stop Reason: " + str(response.stop_reason) + ")]\nContent Blocks: " + str(len(response.content)))

            assistant_response_message_content = []
            has_text_response = any(block.type == 'text' for block in response.content)
            if has_text_response:
                full_text_response = "".join([block.text for block in response.content if block.type == 'text'])
                log_message = "[LLM THOUGHTS/REASONING]\n" + full_text_response
                log_to_file_and_console(log_message)
                assistant_response_message_content.append({"type": "text", "text": full_text_response})
            
            if response.stop_reason == "tool_use":
                log_to_file_and_console("LLM requested tool use.")
                for block in response.content:
                    if block.type == 'tool_use':
                        assistant_response_message_content.append({"type": "tool_use", "id": block.id, "name": block.name, "input": block.input})
            
            if assistant_response_message_content:
                 conversation_history.append({"role": "assistant", "content": assistant_response_message_content})
            elif not has_text_response and response.stop_reason != "tool_use":
                log_to_file_and_console("[LLM NOTE] LLM response did not contain text or tool_use. Stop Reason: " + str(response.stop_reason))

            if response.stop_reason == "tool_use":
                tool_results_for_next_llm_call = []
                should_terminate_session = False
                for block in response.content: 
                    if block.type == 'tool_use':
                        tool_name = block.name
                        tool_input = block.input if block.input is not None else {} 
                        tool_use_id = block.id
                        log_message = (
                            "[EXECUTING LLM TOOL CALL]\n" +
                            "Tool: " + str(tool_name) + "\n" +
                            "Input: " + str(tool_input) + "\n" + 
                            "ID: " + str(tool_use_id)
                        )
                        log_to_file_and_console(log_message)
                        
                        # --- ADDED DEBUG LOGGING FOR TOOL DISPATCH ---
                        log_to_file_and_console(f"[DEBUG DISPATCH] Received tool_name: '{tool_name}' (type: {type(tool_name)})")
                        log_to_file_and_console(f"[DEBUG DISPATCH] PYTHON_TOOLS_MAP keys: {list(PYTHON_TOOLS_MAP.keys())}")
                        # --- END ADDED DEBUG LOGGING ---

                        if tool_name == "terminate_interaction":
                            final_summary = tool_input.get("final_summary", "No final summary provided by LLM.")
                            log_message = "[LLM ACTION] Terminating interaction. Final Summary: " + str(final_summary)
                            log_to_file_and_console(log_message)
                            tool_results_for_next_llm_call.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": "Interaction terminated by agent. Summary: " + str(final_summary)})
                            should_terminate_session = True 

                            # Write final thought and params to JSON files
                            with open("final_thought.json", 'w', encoding='utf-8') as f_thought:
                                json.dump({"final_summary": final_summary}, f_thought, indent=4)
                                log_to_file_and_console("[OUTPUT] final_thought.json has been written.")
                            if TOOL_STATE["final_bayesian_suggestions"] is not None:
                                with open("final_params.json", 'w', encoding='utf-8') as f_params:
                                    json.dump(TOOL_STATE["final_bayesian_suggestions"], f_params, indent=4)
                                    log_to_file_and_console("[OUTPUT] final_params.json has been written with BayesOpt suggestions.")
                            else:
                                log_to_file_and_console("[OUTPUT WARNING] final_params.json was not written because no final Bayesian suggestions were captured.")
                            break # Exit the tool processing loop for this LLM response block
                        
                        # General tool handling
                        elif tool_name in PYTHON_TOOLS_MAP:
                            try:
                                result = PYTHON_TOOLS_MAP[tool_name](**tool_input)
                                # Special handling for suggest_bayesian_optimization_configs to capture final suggestions
                                if tool_name == "suggest_bayesian_optimization_configs":
                                    tool_output_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                                    # Capture final suggestions if this call was for the final number of suggestions
                                    n_suggestions_requested_in_call = tool_input.get('n_suggestions')
                                    if n_suggestions_requested_in_call is None:
                                        for schema in ANTHROPIC_TOOL_SCHEMAS:
                                            if schema["name"] == "suggest_bayesian_optimization_configs":
                                                n_suggestions_requested_in_call = schema["input_schema"].get("properties", {}).get("n_suggestions", {}).get("default", 5)
                                                break
                                    
                                    if n_suggestions_requested_in_call == TOOL_STATE["num_final_suggestions"]:
                                        if isinstance(result, dict) and "suggested_configurations" in result:
                                            TOOL_STATE["final_bayesian_suggestions"] = result["suggested_configurations"]
                                            log_to_file_and_console(f"[INTERNAL] Captured {len(result['suggested_configurations'])} final Bayesian optimization suggestions based on n_suggestions={n_suggestions_requested_in_call}.")
                                        else:
                                            log_to_file_and_console(f"[INTERNAL WARNING] Final call to BayesOpt (n_suggestions={n_suggestions_requested_in_call}) did not return expected dictionary with 'suggested_configurations'. Result was: {result}")
                                else: # For all other tools, or if not final bayesopt
                                    tool_output_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)

                                log_message = "[PYTHON TOOL EXECUTION RESULT - " + str(tool_name) + "]\\n" + tool_output_str
                                log_to_file_and_console(log_message)
                                tool_results_for_next_llm_call.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": tool_output_str})

                            except Exception as e:
                                error_msg = "Error executing tool '" + str(tool_name) + "': " + str(e) + "\\n" + traceback.format_exc()
                                log_message = "[PYTHON TOOL EXECUTION ERROR - " + str(tool_name) + "]\\n" + error_msg
                                log_to_file_and_console(log_message)
                                tool_results_for_next_llm_call.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": error_msg, "is_error": True})
                        else:
                            # This case should ideally not be reached if LLM uses tools from schema
                            log_message = "[EXECUTION ERROR] Unknown tool '" + str(tool_name) + "' requested by LLM. It's not 'terminate_interaction' and not in PYTHON_TOOLS_MAP."
                            log_to_file_and_console(log_message)
                            tool_results_for_next_llm_call.append({"type": "tool_result", "tool_use_id": tool_use_id, "content": "Error: Unknown tool '" + str(tool_name) + "'.", "is_error": True})
                
                if tool_results_for_next_llm_call:
                    conversation_history.append({"role": "user", "content": tool_results_for_next_llm_call})
                
                if should_terminate_session:
                    log_to_file_and_console("Terminate interaction tool was processed. Ending agent session.")
                    break 
            
            elif response.stop_reason == 'max_tokens':
                 log_to_file_and_console("[LLM NOTE] Max tokens reached. Claude's response may be truncated.")
            elif response.stop_reason == 'end_turn' and not has_text_response:
                 log_to_file_and_console("[LLM NOTE] End turn signal received without any text response.")

        except anthropic.APIError as e:
            log_to_file_and_console("[ANTHROPIC API ERROR " + str(call_count) + "] " + str(e) + "\n" + traceback.format_exc())
            if isinstance(e, (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError)):
                log_to_file_and_console("Attempting retry after API error...")
                time.sleep(5) 
                continue 
            else:
                break 
        except Exception as e:
            log_to_file_and_console("[RUNTIME ERROR " + str(call_count) + "] " + str(e) + "\n" + traceback.format_exc())
            break 

        if call_count >= args.max_agent_calls:
            log_to_file_and_console("\n[SYSTEM] Maximum agent call limit (" + str(args.max_agent_calls) + ") reached. Terminating analysis.")
            break

    log_to_file_and_console("\n[FINALIZATION] Analyst agent session concluded. Context log saved to " + context_file_name)

    # Fallback: Write final thought and params if session ended due to max_calls or error after suggestions were made
    if not os.path.exists("final_thought.json") and conversation_history:
        # Try to get the last assistant text message as a fallback summary if terminate_interaction wasn't called
        fallback_summary = "Session ended before explicit terminate_interaction. Check conversation history in log for details."
        for i in range(len(conversation_history) - 1, -1, -1):
            if conversation_history[i]["role"] == "assistant":
                content = conversation_history[i]["content"]
                if isinstance(content, list) and content and isinstance(content[0], dict) and content[0]["type"] == "text":
                    fallback_summary = content[0]["text"]
                    break
                elif isinstance(content, str): # Older format, just in case
                    fallback_summary = content
                    break
        with open("final_thought.json", 'w', encoding='utf-8') as f_thought:
            json.dump({"final_summary": fallback_summary}, f_thought, indent=4)
            log_to_file_and_console("[OUTPUT FALLBACK] final_thought.json has been written with fallback summary.")
    
    # Handle final suggestions and file output
    final_suggestions_df = None
    if TOOL_STATE["final_bayesian_suggestions"] is not None:
        final_suggestions_df = pd.DataFrame(TOOL_STATE["final_bayesian_suggestions"])
        # final_suggestions_df.to_csv("final_params.csv", index=False)
        log_to_file_and_console("[OUTPUT] final_params.csv has been written with final Bayesian optimization suggestions.")
    
    # if not os.path.exists("final_params.json") and TOOL_STATE["final_bayesian_suggestions"] is not None:
    #     with open("final_params.json", 'w', encoding='utf-8') as f_params:
    #         json.dump(TOOL_STATE["final_bayesian_suggestions"], f_params, indent=4)
    #         log_to_file_and_console("[OUTPUT FALLBACK] final_params.json has been written with captured BayesOpt suggestions.")
    # elif not os.path.exists("final_params.json"):
    #     log_to_file_and_console("[OUTPUT WARNING] final_params.json was not written (no final suggestions and no fallback needed/possible).")
    
    return final_suggestions_df

if __name__ == "__main__":
    run_agent_workbench()
