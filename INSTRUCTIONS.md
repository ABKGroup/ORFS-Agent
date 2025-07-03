Welcome ! First, you will need to setup OpenROAD-flow-scripts from the commit hash provided in the paper.

Once you do this, you will need to first change the Makefile. Look at the provided Makefile and see how it uses an INT_PARAM setting to allow parallel runs.

In particular, please note that this makefile change is NOT changing any of the key properties of OpenROAD, but simply enabling better parallel execution.

Under normal OpenROAD, there exists a config.mk under the circuit, PDK pair, which specifies the hyperparameter. Under our setup, there is instead a config_{INT_PARAM}.mk, along with corresponding log folders (Please ctrl-f INT_PARAM in the Makefile) that, together, allow parallel runs.

After you have made these changes, please find an appropriate GCP instance (preferred) OR AWS cloud EC2 machine to run your experiments (recommended). If not, you may use local servers.

Please only use Ubuntu/Debian machines, allow 25 parallel runs with at least 8 GB per run, and 8 vCPUs or equivalent per run.

You will first need to decide how many parallel runs you can support with your setup. Once you do this, open maindriver.sh.

TOTAL_ITERS=6 # Number of "serial" runs
PARALLEL_RUNS=50 # Number of parallel runs PER serial run
TIMEOUT="45m" # After this, an element of a parallel run is automatically killed.
TOTAL_CPUS=110 # In vCPU units
TOTAL_RAM=220 # In GB
ECP_WEIGHT=0.5 # Weight with which the final ECP enters the objective.
WL_WEIGHT=0.5 # Weight with which final WL enters the objective.
ECP_WEIGHT_SURROGATE=0.5 # The weight with which the post-CTS ECP enters the objective.
WL_WEIGHT_SURROGATE=0.5 # The weight with which the post-CTS WL enters the objecctive.

These are the default parameters. In particular, you can see that the above case encodes joint WL-ECP optimization with equal weights.

Note that here, the total number of attempted runs will be 300. And the max runtime is 4.5 hours (45 minutes * 6).

For larger circuits, such as ASAP7 JPEG, etc., we recommend 20-25G of RAM per parallel run. Otherwise, there will be errors from a lack of memory.

Once you have finalized your parameters based on your local setup, run maindriver.sh. We recommend running ASAP7 AES first.

Before you run a circuit, you may need to change the config.mk inside it. For an example of how this looks like, look at the exampleaes config.mk. This is done because a majority of the default config.mk files do not possess a definition for the parameters we are optimizing, and the regex will not catch them and modify them.

You will need to modify the PLACE_DENSITY variable, present in some config.mk files, to the equivalent LB ADDON place density instead. The values appear in the exampleaes/configchanges.mk file.

These are the values for LB ADDON PLACE DENSITY you should put in :

- **(aes, asap7)**: 0.3913  
- **(aes, sky130hd)**: 0.4936  
- **(ibex, sky130hd)**: 0.2  
- **(ibex, asap7)**: 0.2  
- **(jpeg, sky130hd)**: 0.15  
- **(jpeg, asap7)**: 0.4127

Further, make sure to use the provided tcl scripts and link them in the configuration. Look at the fastasap and fastsky tcl files, and how it is linked in config.mk provided, for config.mk.

# IMPORTANT : YOU NEED TO PUT YOUR API KEY FOR ANTHROPIC IN LINE 308 OF OPTIMIZE.PY, AND OPENAI API KEY IN LINE 418 OF PROMPTS.PY

Now, each iteration, you will see something like the asap7_aes.csv in the designs/asap7/aes directory, or asap7_ibex.csv in the designs/asap7/ibex directory, and so on, as we complete one iteration of the TOTAL_ITERS.

Once you are done, you will see some folders like result_dump_{1,2,3..} in the directory outside the flow directory.

Use the helperfuncs.py files to work with them. You can see the best ECP/wirelength values, extract the JSON-level logs to CSV, and so on.

### GENERATING YOUR PROMPTS AFRESH ###

The metadata-level prompts and instructions appear in opt_config.json and also in optimize.py.

If, for some reason, you wish to generate the prompts afresh, look into prompts.py. Make sure to re-format the output of prompts.py *exactly* into the format of opt_config.json.
