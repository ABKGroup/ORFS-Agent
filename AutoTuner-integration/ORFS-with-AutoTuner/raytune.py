import os
import sys
import optuna
import random
from ray import tune, train
from run_or_job import run_job
from ray.tune.search import ConcurrencyLimiter
from ray.tune.search.optuna import OptunaSearch
from ray.tune.schedulers import ASHAScheduler, AsyncHyperBandScheduler
from ray.tune.search.sample import Float, Categorical


def get_search_space(design, run_dir, tech="nangate45"):
    if tech == "nangate45":
        clk_period = tune.uniform(0.1, 10.0)
    elif tech == "asap7":
        clk_period = tune.uniform(100, 10000)
    elif tech == "sky130hd":
        clk_period = tune.uniform(0.5, 15.0)
    else:
        clk_period = tune.uniform(100, 10000)
    
    search_space = {
        "design": design,
        "tech": tech,
        "run_dir": run_dir,
        "clk_period": clk_period,
        "util": tune.uniform(20.0, 99.0),
        "ar": 1,
        "density_lb_addon": tune.uniform(0.0, 0.99),
        "timing_effort": tune.choice([x for x in range(101)]),
        "power_effort": 0,
        "is_hier": tune.choice([0, 1]),
        "gp_pad": tune.choice([x for x in range(0, 4)]),
        "dp_pad": tune.choice([x for x in range(0, 4)]),
        "enable_dpo": tune.choice([0, 1]),
        "cts_cluster_size": tune.choice([x for x in range(10, 40)] + [1]),
        "cts_cluster_dia": tune.choice([x for x in range(80, 120)] + [1]),
        "gp_rd": 1,
        "gp_td": 1,
        "pin_adj": tune.uniform(0.1, 0.7),
        "up_adj": tune.uniform(0.1, 0.7)
    }
    return search_space

def get_init_sample(design, tech):
    init_configs = {
        ("aes", "asap7"): {
            "clk_period": 400,
            "util": 40,
            "density_lb_addon": 0.3913,
            "pin_adj": 0.5,
            "up_adj": 0.5,
            "enable_dpo": 1
        },
        ("aes", "sky130hd"): {
            "clk_period": 4.5,
            "util": 20,
            "density_lb_addon": 0.4936,
            "pin_adj": 0.4,
            "up_adj": 0.4,
            "enable_dpo": 1
        },
        ("ibex", "sky130hd"): {
            "clk_period": 10.0,
            "util": 45,
            "density_lb_addon": 0.2,
            "pin_adj": 0.35,
            "up_adj": 0.35,
            "enable_dpo": 0
        },
        ("ibex", "asap7"): {
            "clk_period": 1260,
            "util": 40,
            "density_lb_addon": 0.2,
            "pin_adj": 0.5,
            "up_adj": 0.5,
            "enable_dpo": 0
        },
        ("jpeg", "sky130hd"): {
            "clk_period": 8.0,
            "util": 50,
            "density_lb_addon": 0.15,
            "pin_adj": 0.3,
            "up_adj": 0.3,
            "enable_dpo": 1
        },
        ("jpeg", "asap7"): {
            "clk_period": 1100,
            "util": 30,
            "density_lb_addon": 0.4127,
            "pin_adj": 0.5,
            "up_adj": 0.5,
            "enable_dpo": 1
        }
    }

    base_config = {
        # "design": design,
        # "tech": tech,
        # "run_dir": run_dir,
        # "ar": 1,
        "timing_effort": 100,
        # "power_effort": 0,
        "is_hier": 0,
        "gp_pad": 0,
        "dp_pad": 0,
        "cts_cluster_size": 1,
        "cts_cluster_dia": 1,
        # "gp_rd": 1,
        # "gp_td": 1
    }

    config = init_configs.get((design, tech), {})
    config.update(base_config)
    return [config]

def validate_initial_sample(sample, search_space):
    for key, value in sample.items():
        if key not in search_space:
            print(f"Warning: Key '{key}' not in search_space.")
            continue

        param = search_space[key]

        if isinstance(param, Float):  # For tune.uniform
            low, high = param.lower, param.upper
            if not (low <= value <= high):
                raise ValueError(f"Value for '{key}' ({value}) is outside range {low}-{high}.")
        elif isinstance(param, Categorical):  # For tune.choice
            choices = param.categories
            if value not in choices:
                raise ValueError(f"Value for '{key}' ({value}) is not in allowed choices {choices}.")
        else:
            print(f"Unsupported search space type for key '{key}'.")

class rayTune():
    def __init__(self, design:str):
        self.design = design
        self.sample_id_counter = 0
        ## Initialize a dictonary, takes design and tech as input and outputs wl
        self.wl_dict = {
            "aes": {
                "asap7": 75438.0,
                "sky130hd": 589825.0,
            },
            "ibex": {
                "asap7": 115285.0,
                "sky130hd": 808423.0,
            },
            "jpeg": {
                "asap7": 300326,
                "sky130hd": 1374966.0,
            }
        }
        
        self.ecp_dict = {
            "aes": {
                "asap7": 459.921,
                "sky130hd": 4.721,
            },
            "ibex": {
                "asap7": 1361.547,
                "sky130hd": 11.543,
            },
            "jpeg": {
                "asap7": 1148.04,
                "sky130hd": 7.731,
            }
        }
        
    def objective(self, config):
        design = config["design"]
        clk_period = round(config["clk_period"], 3)
        util = round(config["util"], 3)
        ar = round(config["ar"], 3)
        tech = config["tech"]
        density_lb_addon = round(config["density_lb_addon"], 3)
        timing_effort = config["timing_effort"]
        power_effort = config["power_effort"]
        is_hier = config["is_hier"]
        gp_pad = config["gp_pad"]
        dp_pad = config["dp_pad"]
        enable_dpo = config["enable_dpo"]
        cts_cluster_size = config["cts_cluster_size"]
        cts_cluster_dia = config["cts_cluster_dia"]
        gp_rd = config["gp_rd"]
        gp_td = config["gp_td"]
        pin_adj = round(config["pin_adj"], 3)
        up_adj = round(config["up_adj"], 3)
        
        run_dir = config["run_dir"]
        self.sample_id_counter += 1
        servers = ["hgr", "gpl", "dpl", "opc", "eda", "npc", "soi", "dme"]
        server = random.choice(servers)
        ## Please provide the correct path for the cached netlist
        cached_netlist = None
        ppa = run_job(design, clk_period, util, ar, tech, density_lb_addon,
                timing_effort, is_hier, power_effort, gp_pad, dp_pad,
                enable_dpo, cts_cluster_size, cts_cluster_dia, gp_rd, gp_td,
                pin_adj, up_adj, run_dir, server, cached_netlist)
        
        max_value = sys.float_info.max
        wl_ecp = max_value
        if ppa[4] != max_value and ppa[0] != max_value:
            wl_ecp = ppa[4] / self.wl_dict[design][tech] + ppa[1] / self.ecp_dict[design][tech]
        
        ## If DRC is greater than 50 then we discard that run
        if ppa[3] > 50:
            train.report({"power": max_value, "performance": max_value, "WL_ECP": max_value,
            "area": max_value, "wirelength": max_value, 'CTS_WL': ppa[5],
            'CTS_ECP': ppa[6],})
        else:
            train.report({"power": ppa[0], "performance": ppa[1], "WL_ECP": wl_ecp,
            "area": ppa[2], "wirelength": ppa[4], 'CTS_WL': ppa[5],
            'CTS_ECP': ppa[6],})

    def __call__(self, tech="ng45", obj="area"):
        ## set run_directory where you want to run your autotuner job
        run_dir=f"/home/scratch/sakundu/MLCAD/OBJ_{self.design}_{tech}_{obj}"
        if not os.path.exists(run_dir):
            os.makedirs(run_dir)
            
        search_space = get_search_space(f"{self.design}", run_dir, tech)
        self.obj = obj
        self.tech = tech
        
        initial_samples = get_init_sample(design, tech, run_dir)
        for sample in initial_samples:
            validate_initial_sample(sample, search_space)
            
        optuna_search = OptunaSearch(metric=obj, mode="min", points_to_evaluate=initial_samples)

        algo = ConcurrencyLimiter(optuna_search, max_concurrent=25)
        scheduler = AsyncHyperBandScheduler(metric=obj, mode="min", max_t=14400)
        
        
        # Profile a correct path for the log_dir
        log_dir = f"/home/fetzfs_projects/rdf_2024/sakundu/Amur_ICML" \
                 f"/AutoTunerLog/MLCAD/ray_results_{self.design}_{tech}_{obj}"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        analysis = tune.run(
            self.objective,
            search_alg=algo,
            scheduler=scheduler,
            num_samples=1000,
            config=search_space,
            progress_reporter=tune.CLIReporter(metric_columns=[obj]),
            name=f"{self.design}_{tech}_{obj}",
            storage_path=log_dir,
            log_to_file=True,
        )

design=sys.argv[1]
tech=sys.argv[2]
obj=sys.argv[3]
r = rayTune(design)
r(tech, obj)
