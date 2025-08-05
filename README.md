# ORFS-Agent: Tool-Using Agents for Chip Design Optimization

## Overview

ORFS-Agent is an LLM-based iterative optimization agent for automating parameter tuning in open-source hardware design flows. This implementation integrates with OpenROAD-flow-scripts (ORFS) to optimize chip design parameters using large language models that adaptively explore and refine parameter configurations.

The agent demonstrates improvements in wirelength and effective clock period by over 13% while using 40% fewer optimization iterations compared to baseline Bayesian optimization approaches. The framework is modular and model-agnostic, working with different LLMs without requiring fine-tuning.


## Project Structure

The ORFS-Agent consists of several key components:

### Core Python Modules

- **`optimize.py`**: Main optimization script that processes OpenROAD log files and coordinates the optimization workflow
- **`inspectfuncs.py`**: Data analysis and inspection tools for understanding parameter space and design metrics
- **`modelfuncs.py`**: Machine learning utilities including Gaussian Process modeling, kernel selection, and preprocessing
- **`agglomfuncs.py`**: Data aggregation and synthesis functions for combining results across multiple runs
- **`constraint_optimizer.py`**: Constraint handling and parameter space definition
- **`prompts.py`**: LLM prompt templates and interaction management

### Execution Scripts

- **`maindriver.sh`**: Primary execution script that orchestrates the entire optimization workflow
- **`run_sequential.sh`**: Handles sequential optimization phases and parameter generation
- **`run_parallel.sh`**: Manages parallel execution of multiple design runs
- **`Makefile`**: Modified OpenROAD Makefile supporting parallel runs with INT_PARAM configuration

### Configuration Files

- **`opt_config.json`**: Parameter constraints, ranges, and optimization settings for different design-PDK combinations
- **`INSTRUCTIONS.md`**: Setup and execution instructions

### Helper Utilities

- **`helperfuncs/csvmaker.py`**: CSV data generation and formatting utilities
- **`helperfuncs/examine.py`**: Data examination and validation tools
- **`helperfuncs/fixall.sh`**: Batch processing and cleanup utilities

## Key Features

- **Multi-objective Optimization**: Supports optimization of Effective Clock Period (ECP), wirelength (WL), or weighted combinations
- **Parallel Execution**: Efficient parallel processing of multiple design configurations
- **Adaptive Parameter Exploration**: LLM-guided parameter space exploration with constraint handling
- **Multiple PDK Support**: Supports ASAP7 and Sky130HD process design kits
- **Circuit Flexibility**: Works with various circuits including AES, IBEX, and JPEG

## Environment Setup

### Prerequisites

1. **OpenROAD-flow-scripts**: Install and configure OpenROAD-flow-scripts from the specific commit ([ce8d36a](https://github.com/The-OpenROAD-Project/OpenROAD-flow-scripts/tree/ce8d36a)) referenced in the paper.
2. **Operating System**: Ubuntu/Debian-based system (required)
3. **Hardware Resources**: 
   - Minimum 8 vCPUs per parallel run
   - 8+ GB RAM per parallel run (20-25GB for larger circuits like JPEG)
   - For default configuration: 110 vCPUs and 220GB RAM total

### Python Environment Setup

```bash
# Create virtual environment
python3 -m venv .venv_orfs_agent
source .venv_orfs_agent/bin/activate

# Install required packages
pip install numpy pandas scikit-learn scipy anthropic python-dotenv scikit-optimize
```

### Required Dependencies

The system requires the following Python packages:
- `numpy` - Numerical computing
- `pandas` - Data manipulation and analysis
- `scikit-learn` - Machine learning utilities
- `scipy` - Scientific computing
- `anthropic` - LLM API integration (if using Anthropic models)
- `python-dotenv` - Environment variable management
- `scikit-optimize` - Bayesian optimization

### Additional System Dependencies

```bash
# Install required system tools
sudo apt-get update
sudo apt-get install jq bc timeout
```

## Configuration

### 1. OpenROAD-flow-scripts Setup

First, modify your OpenROAD Makefile to support parallel runs:

- Replace single `DESIGN_CONFIG` with multiple parametrized configurations. Instead of a single `config.mk`, the flow uses `config_{INT_PARAM}.mk` to enable parallel runs.
- Add `INT_PARAM` support for parallel execution.
- Use the provided [Makefile](./Makefile) as a reference for required changes.

### 2. Parameter Configuration

Edit `opt_config.json` to define:

- **Parameter Constraints**: Valid ranges for each tunable parameter
- **Optimization Weights**: Relative importance of different metrics
- **PDK-specific Settings**: Process-dependent parameter bounds

Example configuration structure:
```json
{
  "parameter_constraints": {
    "CORE_UTIL": {"type": "int", "range": [20, 99]},
    "PIN_LAYER_ADJUST": {"type": "float", "range": [0.2, 0.7]}
  },
  "configurations": [
    {
      "platform": "asap7",
      "design": "aes", 
      "goal": "COMBO",
      "weights": {"ecp": 0.5, "dwl": 0.5}
    }
  ]
}
```

### 3. Design-Specific Configuration

Before running an optimization, you may need to adjust the `config.mk` file for your chosen design, as the default files may not define all tunable parameters.

- **Placement Density**: The `PLACE_DENSITY` variable in some `config.mk` files must be replaced with `LB_ADDON_PLACE_DENSITY`. Use the following values:
  - **(aes, asap7)**: 0.3913  
  - **(aes, sky130hd)**: 0.4936  
  - **(ibex, sky130hd)**: 0.2  
  - **(ibex, asap7)**: 0.2  
  - **(jpeg, sky130hd)**: 0.15  
  - **(jpeg, asap7)**: 0.4127

- **TCL Scripts**: Ensure you are using the provided custom TCL scripts (`fastasap.tcl`, `fastsky.tcl`). You must link these in the `config.mk` file for your design. Refer to the example configuration changes in `exampleaes/configchanges.mk` for guidance.

### 4. Resource Planning

Configure resource allocation in `maindriver.sh`:

```bash
TOTAL_ITERS=6        # Number of serial optimization iterations
PARALLEL_RUNS=50     # Parallel runs per iteration
TIMEOUT="45m"        # Timeout per run
TOTAL_CPUS=110       # Total available vCPUs
TOTAL_RAM=220        # Total available RAM (GB)
ECP_WEIGHT=0.5       # Weight for ECP in the final objective
WL_WEIGHT=0.5        # Weight for Wirelength in the final objective
ECP_WEIGHT_SURROGATE=0.5 # Weight for post-CTS ECP in the surrogate model
WL_WEIGHT_SURROGATE=0.5  # Weight for post-CTS WL in the surrogate model
```

### 5. API Key Setup

The agent requires API keys for LLM providers. You will need to add them directly into the source code:

- **Anthropic API Key**: In `optimize.py`, find the placeholder for the Anthropic API key and insert your key.
- **OpenAI API Key**: In `prompts.py`, find the placeholder for the OpenAI API key and insert your key. This is required for prompt generation functionalities.

**Note**: For improved security, consider modifying the scripts to load keys from environment variables using the `python-dotenv` package.

## Running the Optimization

### Basic Usage

```bash
# Make scripts executable
chmod +x maindriver.sh run_parallel.sh run_sequential.sh

# Run optimization
./maindriver.sh -p <platform> -d <design> [options]
```

### Command Line Options

- **`-p, --platform`**: Target PDK (`asap7` or `sky130hd`)
- **`-d, --design`**: Circuit design (`aes`, `ibex`, or `jpeg`)
- **`-i, --iterations`**: Number of optimization iterations (default: 6)
- **`-r, --parallel-runs`**: Parallel runs per iteration (default: 50)
- **`-t, --timeout`**: Timeout per run (default: 45m)
- **`-o, --objective`**: Optimization goal (`ECP`, `DWL`, or `COMBO`)

### Example Runs

```bash
# Optimize AES circuit on ASAP7 for ECP
./maindriver.sh -p asap7 -d aes -o ECP

# Optimize IBEX on Sky130HD with custom settings
./maindriver.sh -p sky130hd -d ibex -o COMBO -i 8 -r 30 -t 60m

# Large circuit optimization (JPEG)
./maindriver.sh -p asap7 -d jpeg -o DWL -r 20 -t 90m
```

## Output Structure

Each optimization run generates:

- **`../result_dump_<iteration>/`**: Archived results for each iteration
  - `config_*.mk`: Generated configuration files
  - `constraint_*.sdc`: Timing constraint files
  - `logs_dump/`: OpenROAD execution logs
  - `results_dump/`: Synthesis and P&R results

- **`logs/`**: Real-time execution logs organized by platform/design

- **CSV files**: Parameter configurations and results tracking

## License

This project is licensed under the BSD 3-Clause License. See the `LICENSE` file for details.

## Citation

This work is based on the research paper:

**ORFS-agent: Tool-Using Agents for Chip Design Optimization**  
*Amur Ghose, Andrew B. Kahng, Sayak Kundu, and Zhiang Wang*  
University of California San Diego  
arXiv:2506.08332v1 [cs.AI] 12 Jun 2025 | MLCAD 2025
Available at: https://arxiv.org/pdf/2506.08332

## PLEASE READ CAREFULLY FOR REPLICATION, REPRODUCTION AND USAGE !

For the purposes of replication or usage, you may be interested in using this as a flow within OR-AutoTuner, OpenROAD's official BO tool.

Look within the AutoTuner-integration folder for an example of this. Within the ORFS-with-AutoTuner subdirectory, a more streamlined version of ORFS-agent appears in orfs_agent.py, which can be useful if you wish to run your experiments with a restrictive time and/or token budget.

Note that the results of the original paper were obtained with Claude-3.5 Sonnet and you *must* ensure that your key for replication and/or running of the tool can support frequent tool calls to the model.
