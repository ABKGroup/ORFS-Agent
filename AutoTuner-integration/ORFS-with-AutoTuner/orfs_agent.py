import os
import sys
import time
import pandas as pd
import multiprocessing as mp
from time import sleep
from run_or_job import run_job
from analyst_agent_workbench import run_agent_workbench

def get_init_sample(design, tech):
    init_configs = {
        ("aes", "asap7"): {
            "CLK": 400,
            "UTIL": 40,
            "LB_ADDON": 0.3913,
            "PIN_ADJ": 0.5,
            "UP_ADJ": 0.5,
            "DPO": 1
        },
        ("aes", "sky130hd"): {
            "CLK": 4.5,
            "UTIL": 20,
            "LB_ADDON": 0.4936,
            "PIN_ADJ": 0.4,
            "UP_ADJ": 0.4,
            "DPO": 1
        },
        ("ibex", "sky130hd"): {
            "CLK": 10.0,
            "UTIL": 45,
            "LB_ADDON": 0.2,
            "PIN_ADJ": 0.35,
            "UP_ADJ": 0.35,
            "DPO": 0
        },
        ("ibex", "asap7"): {
            "CLK": 1260,
            "UTIL": 40,
            "LB_ADDON": 0.2,
            "PIN_ADJ": 0.5,
            "UP_ADJ": 0.5,
            "DPO": 0
        },
        ("jpeg", "sky130hd"): {
            "CLK": 8.0,
            "UTIL": 50,
            "LB_ADDON": 0.15,
            "PIN_ADJ": 0.3,
            "UP_ADJ": 0.3,
            "DPO": 1
        },
        ("jpeg", "asap7"): {
            "CLK": 1100,
            "UTIL": 30,
            "LB_ADDON": 0.4127,
            "PIN_ADJ": 0.5,
            "UP_ADJ": 0.5,
            "DPO": 1
        }
    }

    base_config = {
        "TNS_End_Percent": 100,
        "HIER_SYNTH": 0,
        "GP_PAD": 0,
        "DP_PAD": 0,
        "CTS_CSIZE": 1,
        "CTS_CDIA": 1,
    }

    config = init_configs.get((design, tech), {}).copy()
    config.update(base_config)
    return config

## Function to get the base wl and ecp
def get_base_wl_ecp(design, tech):
    wl_dict = {
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
    
    ecp_dict = {
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
    wl = wl_dict.get(design, {}).get(tech, None)
    ecp = ecp_dict.get(design, {}).get(tech, None)
    return wl, ecp

def map_output_dic(or_resutl, design, tech):
    output_dict = {
        "cts__timing__setup__ws": or_resutl[0] if len(or_resutl) > 0 else "N/A",
        "cts__timing__setup__tns": or_resutl[1] if len(or_resutl) > 1 else "N/A",
        "cts__timing__drv__setup_violation_count": or_resutl[2] if len(or_resutl) > 2 else "N/A",
        "cts__route__wirelength__estimated": or_resutl[3] if len(or_resutl) > 3 else "N/A",
        "detailedroute__route__wirelength": or_resutl[4] if len(or_resutl) > 4 else "N/A", 
        "detailedroute__route__drc_errors": or_resutl[5] if len(or_resutl) > 5 else "N/A", 
        "detailedroute__route__vias": or_resutl[6] if len(or_resutl) > 6 else "N/A", 
        "finish__timing__setup__ws": or_resutl[7] if len(or_resutl) > 7 else "N/A", 
        "finish__timing__setup__tns": or_resutl[8] if len(or_resutl) > 8 else "N/A", 
        "finish__timing__drv__setup_violation_count": or_resutl[9] if len(or_resutl) > 9 else "N/A", 
        "finish__timing__drv__hold_violation_count": or_resutl[10] if len(or_resutl) > 10 else "N/A", 
        "finish__power__total": or_resutl[11] if len(or_resutl) > 11 else "N/A", 
        "finish__design__instance__utilization": or_resutl[12] if len(or_resutl) > 12 else "N/A", 
        "finish__design__instance__count__class:timing_repair_buffer": or_resutl[13] if len(or_resutl) > 13 else "N/A", 
        "ECP_cts": or_resutl[14] if len(or_resutl) > 14 else "N/A",
        "ECP_final": or_resutl[15] if len(or_resutl) > 15 else "N/A", 
    }
    
    base_wl, base_ecp = get_base_wl_ecp(design, tech)
    cts_ecp = output_dict["ECP_cts"]
    cts_wl = output_dict["cts__route__wirelength__estimated"]
    if cts_ecp != "N/A" and cts_wl != "N/A":
       output_dict["Fractional_Loss_cts"] = (cts_wl / base_wl) + (cts_ecp / base_ecp)
    else:
        output_dict["Fractional_Loss_cts"] = "N/A"

    final_ecp = output_dict["ECP_final"]
    final_wl = output_dict["detailedroute__route__wirelength"]
    if final_ecp != "N/A" and final_wl != "N/A":
        output_dict["Fractional_Loss_final"] = (final_wl / base_wl) + (final_ecp / base_ecp)
    else:
        output_dict["Fractional_Loss_final"] = "N/A"
    
    return output_dict

def report_run_time(start_time, message):
    elapsed_time = time.time() - start_time
    hours, remainder = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"[INFO] {message} {int(hours)}h {int(minutes)}m {int(seconds)}s")
    return

def run_or(config, design, tech, run_dir, server, run_id):
    clk_period = round(config["CLK"], 3)
    util = round(config["UTIL"], 3)
    ar = 1
    density_lb_addon = round(config["LB_ADDON"], 3)
    timing_effort = int(config["TNS_End_Percent"])
    is_hier = int(config["HIER_SYNTH"])
    power_effort = 0
    gp_pad = int(config["GP_PAD"])
    dp_pad = int(config["DP_PAD"])
    enable_dpo = int(config["DPO"])
    cts_cluster_size = config["CTS_CSIZE"]
    cts_cluster_dia = config["CTS_CDIA"]
    gp_rd = 1
    gp_td = 1
    pin_adj = round(config["PIN_ADJ"], 3)
    up_adj = round(config["UP_ADJ"], 3)
    or_result = run_job(design, clk_period, util, ar, tech, density_lb_addon,
                        timing_effort, is_hier, power_effort, gp_pad, dp_pad,
                        enable_dpo, cts_cluster_size, cts_cluster_dia, gp_rd,
                        gp_td, pin_adj, up_adj, run_dir, server, run_id)
    output_dict = map_output_dic(or_result, design, tech)
    output_dict["circuit"] = design
    output_dict["pdk"] = tech
    ## Merge the output dictionary with the config
    output_dict.update(config)
    print(f"[INFO] Run ID: {run_id}, Server: {server}, Result: {output_dict}")
    return output_dict

class ORFSAgent:
    def __init__(self, design, tech, goal):
        self.design = design
        self.tech = tech
        self.goal = goal
        self.main_df = pd.DataFrame()
        self.log_dir = f"./logs/{tech}/{design}/{goal}"
        self.num_parallel_trials = 25
        self.max_agent_calls = 30
        self.total_trials = 1000
        self.check_goal()
        self.base_dir="/home/scratch/sakundu/MLCAD"
        self.run_dir=f"{self.base_dir}/OBJ_{self.design}_{self.tech}_{self.goal}"
        self.servers = ["rtl", "mleda", "mlcad", "cad"]
        self.run_id = 0
        self.pool = mp.Pool(processes=self.num_parallel_trials)
        # 
        ## Create the log directory if it doesn't exist
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)
        
    def check_goal(self):
        if self.goal not in ["detailedroute__route__wirelength", "ECP_final", "Fractional_Loss_final"]:
            print(f"[ERROR] Invalid goal: {self.goal}. Must be one of 'detailedroute__route__wirelength', 'ECP_final', or 'Fractional_Loss_final'.")
            raise ValueError("Goal must be one of 'detailedroute__route__wirelength', 'ECP_final', or 'Fractional_Loss_finalrformance'.")
    
    def objective(self, param, server, run_id):
        """Modified to be a static function that returns results instead of modifying shared state"""
        run_result = run_or(param, self.design, self.tech, self.run_dir, server, run_id)
        run_result['run_id'] = run_id  # Add run ID for tracking
        print(f"[INFO] Run ID: {run_id}, Server: {server}, Result: {run_result}")
        return run_result
    
    def __call__(self):
        """Main function to run the agent"""
        print(f"[INFO] Starting ORFS Agent for design: {self.design}, tech: {self.tech}, goal: {self.goal}")
        print(f"[INFO] Log directory: {self.log_dir}")
        print(f"[INFO] Run directory: {self.run_dir}")
        print(f"[INFO] Total trials: {self.total_trials}, Parallel trials: {self.num_parallel_trials}")
        print(f"[INFO] Max agent calls: {self.max_agent_calls}")
        ## Check if the main df is empty
        if self.main_df.empty:
            self.main_df = pd.read_csv(f"./init_data/{self.design}_{self.tech}_sampled.csv")
        
        ## Now we have the base results
        running_jobs = []  # List of tuples: (AsyncResult, run_id, param_dict, server)
        best_cost = float('inf')  # Initialize best cost to infinity
        best_df = pd.DataFrame()  # DataFrame to store the best results
        while self.run_id < self.total_trials:
            ## Check for completed jobs first and collect their results
            completed_indices = []
            for i, (job, job_run_id, param_dict, server) in enumerate(running_jobs):
                if job.ready():  # This is non-blocking - just checks if job is done
                    completed_indices.append(i)
                    try:
                        result = job.get()  # No timeout - get the result immediately since job.ready() returned True
                        # Add result to the main DataFrame
                        self.main_df = pd.concat([self.main_df, pd.DataFrame([result])], ignore_index=True)
                        if result[self.goal] != "N/A" and best_cost > float(result[self.goal]):
                            best_cost = result[self.goal]
                            best_df = pd.DataFrame([result])
                            print(f"[INFO] New best cost found: {best_cost} for run ID {job_run_id}")
                        print(f"[INFO] Completed job {job_run_id} successfully")
                    except Exception as e:
                        print(f"[ERROR2] Job {job_run_id} failed with error: {e}")
                        
            
            # Remove completed jobs from running_jobs (in reverse order to maintain indices)
            for i in reversed(completed_indices):
                running_jobs.pop(i)
            
            ## Check how many jobs to run in parallel based on running jobs
            num_jobs_running = len(running_jobs)
            
            new_sample_count = self.num_parallel_trials - num_jobs_running
            if new_sample_count + self.run_id > self.total_trials:
                new_sample_count = self.total_trials - self.run_id
            
            print(f"[INFO] New sample: {new_sample_count}, Running jobs: {num_jobs_running}, Total trials: {self.total_trials}, Run ID: {self.run_id}")
            
            if new_sample_count > 0:
                ## Now get the parameters for the next run
                print(f"[INFO] Running agent workbench to get new parameters.")
                # Request exactly the number of configurations we can actually launch
                num_configs_to_request = min(new_sample_count, 5)  # Request all slots we can fill
                start_time = time.time()
                params_df = run_agent_workbench(self.main_df, self.design,
                                               self.tech, self.goal,
                                               num_configs_to_request,
                                               self.max_agent_calls, self.log_dir)
                report_run_time(start_time, f"Param generation (Count: {num_configs_to_request}) run time:")
                
                if params_df is None or params_df.empty:
                    print("[ERROR] Agent workbench returned no parameters. Skipping this iteration.")
                    continue
                
                print(f"[INFO] New parameters obtained: {len(params_df)} configurations for {new_sample_count} available slots")
                
                ## For each parameter (row) in the DataFrame, convert to dict and run the objective function
                # Use ALL the parameters we got, up to the number of available slots
                params_used = 0
                for _, row in params_df.iterrows():
                    if self.run_id >= self.total_trials or params_used >= new_sample_count:
                        break
                    
                    param_dict = row.to_dict()
                    server = self.servers[self.run_id % len(self.servers)]
                    current_run_id = self.run_id
                    self.run_id += 1
                    params_used += 1
                    
                    # Submit job to pool
                    result = self.pool.apply_async(run_or, args=(param_dict, self.design, self.tech, self.run_dir, server, current_run_id))
                    running_jobs.append((result, current_run_id, param_dict, server))
                    print(f"[INFO] Submitted job {current_run_id} to server {server}")
                
                # If we didn't get enough configs from the agent, we'll try again in the next iteration
                if params_used < new_sample_count:
                    print(f"[INFO] Only used {params_used} out of {new_sample_count} available slots. Will request more configurations in next iteration.")

            # If we have running jobs but no new samples to submit, wait a bit
            if running_jobs and new_sample_count == 0:
                print("[INFO] Waiting for running jobs to complete before proceeding.")
                sleep(30)  # Wait 30 seconds before checking again
            elif len(running_jobs) == self.num_parallel_trials:
                print(f"[INFO] {len(running_jobs)} jobs running. Sleeping for 60 seconds.")
                sleep(60)  # Increased sleep time since jobs take longer
            else:
                print(f"[INFO] {len(running_jobs)} jobs running. Sleeping for 10 seconds.")
                sleep(5)
            
            ## Print the best cost found so far
            if best_cost != float('inf'):
                print(f"[INFO] Current best cost: {best_cost} for run ID {best_df.get('run_id', 'N/A')}")
            else:
                print("[INFO] No valid results found yet.")
        
        ## Wait for all remaining jobs to complete and collect their results
        print(f"[INFO] Waiting for {len(running_jobs)} remaining jobs to complete...")
        for job, job_run_id, param_dict, server in running_jobs:
            try:
                print(f"[INFO] Waiting for job {job_run_id} to complete...")
                result = job.get()  # Wait indefinitely for completion (no timeout)
                # Add result to the main DataFrame
                self.main_df = pd.concat([self.main_df, pd.DataFrame([result])], ignore_index=True)
                if result[self.goal] != "N/A" and best_cost > float(result[self.goal]):
                    best_cost = result[self.goal]
                    best_df = pd.DataFrame([result])
                    print(f"[INFO] New best cost found: {best_cost} for run ID {job_run_id}")
                print(f"[INFO] Completed job {job_run_id} successfully")
            except Exception as e:
                print(f"[ERROR1] Final job {job_run_id} failed with error: {e}")
        
        # Close the pool
        self.pool.close()
        self.pool.join()
        
        ## Save the main DataFrame to a CSV file
        output_file = f"{self.log_dir}/results.csv"
        self.main_df.to_csv(output_file, index=False)
        print(f"[INFO] Best cost found: {best_df.to_dict(orient='records')}")
        print(f"[INFO] All trials completed. Results saved to {output_file}")
        
if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python orfs_agent.py <design> <tech> <goal>")
        sys.exit(1)
    
    design = sys.argv[1]
    tech = sys.argv[2]
    goal = sys.argv[3]
    print(f"Starting ORFS Agent for design: {design}, tech: {tech}, goal: {goal}")
    agent = ORFSAgent(design, tech, goal)
    agent()  # Run the agent
    print(f"Results saved to {agent.log_dir}/results.csv")
