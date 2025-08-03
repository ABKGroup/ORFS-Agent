# OpenROAD Flow Synthesis Agent (ORFS-Agent)

## Project Overview

The OpenROAD Flow Synthesis Agent (ORFS-Agent) is a project designed to analyze hyperparameter data from OpenROAD physical design flows. It utilizes a Large Language Model (LLM) agent, powered by Anthropic's Claude, to explore this data, identify promising parameter regions, and suggest optimized hyperparameter configurations for specific circuits and Process Design Kits (PDKs). The ultimate goal is to improve metrics like Effective Clock Period (ECP) or Wirelength (WL).

The project involves two main Python scripts:
1.  `parser.py`: Parses raw JSON output from OpenROAD runs into a structured dataset.
2.  `analyst_agent_workbench.py`: An LLM agent that uses the structured dataset to perform analysis and suggest new hyperparameter configurations using Bayesian Optimization.

## Core Components and Functionality

### 1. Data Parser (`parser.py`)

This script is responsible for transforming raw data from OpenROAD runs into a usable format for the LLM agent.

**Key Functionalities:**
*   **Directory Traversal:** Recursively scans a directory structure containing JSON files from OpenROAD flows. The structure is typically organized by circuit name (e.g., `aes_asap7/`) and then by specific run configurations (e.g., `DESIGN_aes__CLK_334.557__...`).
*   **Parameter Extraction:**
    *   Parses hyperparameter values (e.g., `CLK`, `UTIL`, `TNS_End_Percent`) from directory names.
    *   Extracts metrics and other relevant information from various JSON report files within each run's directory (e.g., `4_1_cts.json`, `5_2_route.json`, `6_report.json`).
*   **Data Augmentation:**
    *   Calculates derived metrics such as `ECP_cts`, `ECP_final` (Effective Clock Period for CTS and final stages) and `Fractional_Loss_cts`, `Fractional_Loss_final`.
    *   Uses a predefined dictionary of baseline ECP and Wirelength values for different (PDK, circuit) combinations to compute the fractional loss metrics.
*   **Data Cleaning:** Handles missing files or keys by inserting "N/A" values, ensuring a consistent data structure. It also prunes parameters found to be uninformative during initial analysis (e.g., `AR`, `TD`, `RD`, `POWER_EFFORT`).
*   **Output:** Generates a single JSON file (`output.json`) containing a list of dictionaries, where each dictionary represents a single OpenROAD run with its associated parameters and metrics.

### 2. Analyst Agent Workbench (`analyst_agent_workbench.py`)

This script implements an autonomous LLM agent that interacts with the structured data (`output.json`) to provide optimization insights and suggest new hyperparameter sets.

**Key Functionalities:**
*   **Command-Line Interface:** Accepts arguments for `circuit`, `pdk`, `optimization_goal` (the metric to minimize), `num_final_suggestions` (for Bayesian Optimization), `max_agent_calls` (LLM interactions), and `model_name`.
*   **Data Loading and Preprocessing:**
    *   Loads `output.json`.
    *   Filters the DataFrame based on the provided `circuit` and `pdk`.
    *   Further filters out runs with Design Rule Check (DRC) errors (`detailedroute__route__drc_errors != 0`).
*   **LLM Interaction (Anthropic Claude):**
    *   Uses the `anthropic` Python SDK to communicate with a Claude model.
    *   Manages conversation history and constructs a detailed system prompt.
    *   The system prompt includes content from `prompt.md`, dynamic information about the dataset, and available tool schemas.
*   **Tool-Based Analysis:** Provides the LLM with a suite of Python tools to analyze the data:
    *   `get_current_data_shape`, `list_columns`: Basic data exploration.
    *   `get_data_summary`: Descriptive statistics for specified columns.
    *   `get_value_distribution`: Value counts or binned distributions.
    *   `get_correlations_for_column`: Calculates correlations with the target metric.
    *   `filter_data`: Filters the dataset based on LLM-provided queries.
    *   `get_sample_rows`: Shows sample data, optionally from a temporary filter.
    *   `reset_data_to_all_valid_runs`: Resets the DataFrame to its initial filtered state.
    *   `suggest_new_tool`: Allows the LLM to suggest new tools if needed.
    *   `terminate_interaction`: Allows the LLM to end the session and provide a final summary.
*   **Bayesian Optimization (`suggest_bayesian_optimization_configs` tool):**
    *   Integrates `scikit-optimize` (`skopt`) for Bayesian Optimization.
    *   Dynamically builds the search space for hyperparameters based on `constraints.json`, which defines parameter types (float, integer, categorical) and ranges/values. Handles PDK-specific `CLK` constraints.
    *   The LLM can provide a `training_data_query` to focus the optimizer's training on a specific subset of the historical data.
    *   The tool trains an `skopt.Optimizer` (Gaussian Process surrogate model, Expected Improvement acquisition function) on the (potentially queried) historical data.
    *   It then asks the optimizer to suggest `n_suggestions` new configurations.
    *   Special handling for `CTS_CSIZE` and `CTS_CDIA`: values of '1' (often from baseline runs) are filtered out from the data used to train `skopt`, as the typical search range is different.
*   **State Management (`TOOL_STATE`):** A global dictionary maintains the current state of the DataFrame, initial data snapshots, PDK/circuit info, and final Bayesian optimization suggestions.
*   **System Prompt Guidance:** The `prompt.md` file, along with dynamically generated instructions, guides the LLM's analytical workflow. It emphasizes:
    *   A thorough "Initial Deep Dive" into the data before attempting optimization.
    *   Referencing baseline configurations.
    *   Forming hypotheses and testing them.
    *   Understanding the behavior of the Bayesian optimization tool (i.e., it suggests from the full search space defined in `constraints.json` but is guided by the `training_data_query`).
    *   A mandatory final call to `suggest_bayesian_optimization_configs` for a specified number of diverse suggestions.
*   **Logging and Output:**
    *   Verbose logging to the console and a context-specific file (e.g., `aes_asap7_ECP_final_context_*.txt`).
    *   `final_thought.json`: Contains the LLM's final summary text.
    *   `final_params.json`: Contains the list of hyperparameter configurations suggested by the final call to the Bayesian optimization tool.

## Data Flow

1.  **Raw OpenROAD Data:** JSON files from multiple OpenROAD runs, organized in a specific directory structure.
2.  **`parser.py`:** Processes raw data, extracts parameters and metrics, calculates new metrics, and outputs `output.json`.
3.  **`output.json`:** The primary structured dataset used by the agent.
4.  **`analyst_agent_workbench.py`:**
    *   Loads `output.json` and filters it.
    *   LLM uses analytical tools to explore the data, guided by `prompt.md` and `constraints.json`.
    *   LLM formulates a `training_data_query` for the Bayesian Optimizer.
    *   The `suggest_bayesian_optimization_configs` tool uses this query and `constraints.json` to train `skopt` and generate new configurations.
5.  **Output Files:**
    *   `final_thought.json` (LLM summary)
    *   `final_params.json` (Suggested hyperparameter sets)
    *   Context log file (detailed trace of the agent's session).

## Key Supporting Files

*   **`output.json`**: (Generated by `parser.py`) The main structured dataset.
*   **`constraints.json`**: Defines the search space for each hyperparameter for the Bayesian optimization tool, including types (float, integer, binary/categorical) and ranges/values. Specifies PDK-specific ranges for `CLK`.
*   **`prompt.md`**: A detailed markdown file providing extensive context to the LLM. It includes:
    *   Descriptions of optimization objectives (ECP, WL, Fractional Loss).
    *   Detailed explanations of all tunable hyperparameters, their JSON keys, UI names, types, and ranges.
    *   Notes on baseline configurations for various (circuit, PDK) pairs and their fixed/default settings.
    *   Heuristics on how parameters affect ECP and how to tune for different objectives.
*   **`requirements.txt`**: Lists Python package dependencies (`anthropic`, `pandas`, `numpy`, `python-dotenv`, `scikit-optimize`, `scikit-learn`).
*   **`.env` (example)**: Used to store the `ANTHROPIC_API_KEY`. Alternatively, a `anthropic_key.py` file can be used.
    ```
    ANTHROPIC_API_KEY="your_api_key_here"
    ```
*   **`anthropic_key.py` (alternative for API key)**:
    ```python
    ANTHROPIC_API_KEY = "your_api_key_here"
    ```

## How to Run

1.  **Setup Python Environment:**
    It's recommended to use a virtual environment.
    ```bash
    python3 -m venv .venv_orfs_agent
    source .venv_orfs_agent/bin/activate
    ```
2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Prepare Data:**
    *   Ensure your OpenROAD run data is organized in the expected directory structure.
    *   Run `parser.py` to generate `output.json`.
        ```bash
        python parser.py /path/to/your/openroad_runs_directory
        ```
        (Adjust the path as needed. The script currently assumes the output path for `output.json` is hardcoded or relative to its location).
4.  **Set API Key:**
    *   Create a `.env` file in the project root and add your `ANTHROPIC_API_KEY`.
    *   Alternatively, create `anthropic_key.py` with the key.
5.  **Configure `constraints.json` and `prompt.md`:**
    *   Review and update `constraints.json` to accurately reflect the tunable parameters and their valid ranges/values for your specific use case and PDKs.
    *   Review and update `prompt.md` with relevant baseline information, heuristics, and parameter descriptions.
6.  **Run the Agent:**
    The `run_agent.sh` script automates setting up the environment (if it exists or creates it) and running the agent.
    ```bash
    chmod +x run_agent.sh
    ./run_agent.sh <circuit_name> <pdk_name> <optimization_goal_metric> [num_final_suggestions] [max_agent_calls] [model_name]
    ```
    Example:
    ```bash
    ./run_agent.sh aes asap7 ECP_final 5 15 claude-3-5-sonnet-20240620
    ```
    Or directly using python:
    ```bash
    python analyst_agent_workbench.py aes asap7 ECP_final --num_final_suggestions 5 --max_agent_calls 15
    ```

## Agent Outputs

Upon completion, the agent will typically produce:
*   **Console Output:** A detailed log of the agent's thoughts, tool calls, and results.
*   **Context Log File:** A text file (e.g., `aes_asap7_ECP_final_context_*.txt`) containing the same detailed trace as the console output for the session.
*   **`final_thought.json`**: The LLM's final summary of its analysis and findings.
*   **`final_params.json`**: A JSON list of the hyperparameter configurations suggested by the final call to the Bayesian optimization tool.

## Iterative Development Highlights

The development of this agent involved several iterations and refinements:
*   **Initial data parsing:** Evolved from CSV to a more flexible JSON output.
*   **Parameter analysis:** Led to pruning of non-impactful parameters.
*   **Calculated metrics:** Enhanced the dataset with derived ECP and Fractional Loss values.
*   **Agent Tooling:** Incrementally built and refined the set of tools available to the LLM.
*   **Bayesian Optimization:** Integrated `skopt` for intelligent suggestion generation, replacing an initial placeholder.
*   **Prompt Engineering:** Significant effort was invested in crafting and iteratively refining the system prompt to guide the LLM's behavior, improve its analytical depth, manage its pacing, and help it understand the nuances of the Bayesian optimization tool.
*   **Debugging:** Addressed various issues, including:
    *   Correcting errors in Bayesian optimization data preparation and parameter handling (e.g., `KeyError: 'type'`, `ValueError: Not all points are within the bounds`).
    *   Fixing tool dispatch logic in the agent's main loop.
    *   Clarifying constraints handling for CTS parameters (allowing '1' in historical data but searching a different range).

This iterative process has resulted in a more robust and intelligent agent capable of performing nuanced data analysis and providing data-driven hyperparameter suggestions. 