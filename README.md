# ORFS-Agent: Tool-Using Agents for Chip Design Optimization

## Overview

ORFS-Agent is an LLM-guided iterative optimizer for OpenROAD-flow-scripts (ORFS). It analyzes archived OpenROAD runs, proposes new parameter settings, and feeds the next batch of flow configurations back into ORFS.

This `ORFS-Agent-clean` tree is the MLCAD-era codebase updated with the journal-extension runtime used by `todaes-to-go.tex`. In particular, it now supports:

- `claude-sonnet-4-6` via direct Anthropic API
- Claude on Vertex AI via the Anthropic SDK
- `kimi-k2.5` via Moonshot's OpenAI-compatible endpoint
- optional external context tools during candidate generation:
  - `web_search` via DuckDuckGo or Brave
  - `openalex_lookup` for paper / abstract metadata

## Project Structure

- `optimize.py` - main optimization loop and archived-run analysis
- `llm_support.py` - provider selection, tool calling, and external-context plumbing
- `maindriver.sh` - top-level iterative driver
- `run_sequential.sh` - CSV / config / SDC generation for each iteration
- `run_parallel.sh` - parallel ORFS execution wrapper
- `Makefile` - ORFS-compatible flow makefile with `INT_PARAM` support
- `opt_config.json` - parameter ranges, weights, and design-specific prompts
- `env.md` - human-fill template for provider and search credentials

## Repository Layout

This tree assumes the ORFS flow assets come from the paper baseline checkout of OpenROAD-flow-scripts.

- Baseline ORFS commit: `ce8d36a`
- Expected flow tree: `flow/designs`, `flow/platforms`, `flow/scripts`, `flow/util`, `flow/test`

When this repo is placed inside an `OpenROAD-flow-scripts` checkout, the shell wrappers now auto-detect the sibling `flow/` directory, export `FLOW_HOME`, and create local symlinks for the required subtrees when they are missing. That keeps logs, reports, results, and `result_dump_*` archives local to `ORFS-Agent-clean/` while still reusing the ORFS baseline assets.

## Environment Setup

### Prerequisites

1. A checkout of OpenROAD-flow-scripts at commit `ce8d36a`
2. Ubuntu/Debian-like environment
3. Sufficient compute for the chosen design / parallelism

### Python Packages

```bash
python3 -m venv .venv_orfs_agent
source .venv_orfs_agent/bin/activate
pip install numpy pandas scikit-learn scipy anthropic openai google-auth requests pyyaml python-dotenv scikit-optimize
```

### System Packages

```bash
sudo apt-get update
sudo apt-get install jq bc timeout
```

## LLM Providers and Context Tools

Select the active provider with `ORFS_AGENT_LLM_PROVIDER`:

- `anthropic` - direct Claude API via `ANTHROPIC_API_KEY`
- `claude-vertex` - Claude on Vertex AI via ADC plus Vertex project / region
- `kimi` - Moonshot / Kimi via `MOONSHOT_API_KEY`

Optional runtime controls:

- `ORFS_AGENT_MODEL` - override the default provider model ID
- `ORFS_AGENT_ENABLE_CONTEXT_TOOLS` - set to `0` to disable web / OpenAlex calls
- `ORFS_AGENT_MAX_TOOL_ROUNDS` - cap tool-call loops per LLM turn
- `ORFS_AGENT_WEB_SEARCH_PROVIDER` - `duckduckgo` (default) or `brave`
- `BRAVE_SEARCH_API_KEY` - required only when using Brave
- `OPENALEX_API_KEY` - optional, improves OpenAlex limits

The main optimization loop can call `web_search` and `openalex_lookup` before proposing parameter candidates. This is the retrieval-enabled setup used for the journal-extension experiments.

Credential and setup examples live in `env.md`.

## Configuration Notes

Before running the optimizer:

- make sure the chosen `flow/designs/<platform>/<design>/config.mk` exposes the parameters you want to tune
- keep the journal-extension `llm_support.py` and `optimize.py` together
- use `opt_config.json` to control parameter bounds, objective weights, and prompt context

The generated `config_<n>.mk` files and derived SDCs are written into the design directory used by ORFS, and each completed iteration is archived locally under `result_dump_<iteration>/`.

## Running the Optimization

### Basic Usage

```bash
chmod +x maindriver.sh run_parallel.sh run_sequential.sh
./maindriver.sh -p <platform> -d <design> [options]
```

### Command-Line Options

- `-p, --platform` - `asap7` or `sky130hd`
- `-d, --design` - `aes`, `ibex`, or `jpeg`
- `-i, --iterations` - serial optimization iterations
- `-r, --parallel-runs` - parallel runs per iteration
- `-t, --timeout` - timeout per parallel phase
- `-o, --objective` - `ECP`, `DWL`, or `COMBO`

### Example Runs

```bash
./maindriver.sh -p asap7 -d aes -o ECP
./maindriver.sh -p sky130hd -d ibex -o COMBO -i 8 -r 30 -t 60m
./maindriver.sh -p asap7 -d jpeg -o DWL -r 20 -t 90m
```

## Output Structure

Each iteration produces:

- `result_dump_<iteration>/`
  - `config_*.mk`
  - `constraint_*.sdc` or `jpeg_encoder15_7nm_*.sdc`
  - `logs_dump/`
  - `results_dump/`
- `logs/` - live per-run execution logs
- `results/`, `reports/`, `objects/` - local ORFS work products

## Notes on Reproduction

- The original MLCAD paper used Claude 3.5 Sonnet.
- This updated tree adds the journal-extension provider stack: latest Sonnet defaults, Kimi K2.5, Claude on Vertex, and optional retrieval.
- Retrieval can be turned off cleanly with `ORFS_AGENT_ENABLE_CONTEXT_TOOLS=0` for search/no-search ablations.

## License

BSD 3-Clause. See `LICENSE`.

## Citation

**ORFS-agent: Tool-Using Agents for Chip Design Optimization**  
*Amur Ghose, Andrew B. Kahng, Sayak Kundu, and Zhiang Wang*  
MLCAD 2025
