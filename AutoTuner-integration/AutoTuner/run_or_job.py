import os
import sys
import json
import subprocess
from typing import Tuple, Optional


def extract_ppa(log_dir:str, clk:float) -> Tuple[float, float, float, float, float, float]:
    rpt_file=f"{log_dir}/6_report.json"
    cts_rpt_file=f"{log_dir}/4_1_cts.json"
    large_num = sys.float_info.max
    cts_wl=large_num
    cts_ecp=large_num
    if os.path.exists(cts_rpt_file):
        fp = open(cts_rpt_file, 'r')
        data = json.loads(fp.read().strip())
        fp.close()
        cts_wl = float(data.get("cts__route__wirelength__estimated"), large_num)
        cts_ws = float(data.get("cts__timing__setup__ws"), large_num)
        cts_ecp = clk - cts_ws
        if cts_ws == large_num:
            cts_ecp = large_num
    
    # Parse the JSON data
    if os.path.exists(rpt_file):
        fp = open(rpt_file, 'r')
        data = json.loads(fp.read().strip())
        fp.close()
        
        # Extract the required fields
        ws = float(data.get("finish__timing__setup__ws"), large_num)
        core_area = float(data.get("finish__design__core__area"), large_num)
        total_power = float(data.get("finish__power__total"))
        fp = open(f"{log_dir}/5_2_route.json", 'r')
        drc_data = json.loads(fp.read().strip())
        fp.close()
        drc_count = float(drc_data.get("detailedroute__route__drc_errors"))
        rwl = float(drc_data.get("detailedroute__route__wirelength"))
        ecp = clk - ws
        if ws == large_num:
            ecp = large_num
        return total_power, ecp, core_area, drc_count, rwl, cts_wl, cts_ecp

    return large_num, large_num, large_num, large_num, large_num, cts_wl, cts_ecp

def extract_ppa_remote(log_dir: str, clk: float, server: str) -> Tuple[float, float, float, float, float, float, float]:
    ref_dir=os.path.dirname(os.path.abspath(__file__))
    remote_script = f"{ref_dir}/extract_ppa_remote.py"
    large_num = sys.float_info.max
    python_exe = "/home/tool/anaconda/envs/cluster/bin/python3.10"
    command = f"ssh {server} '{python_exe} {remote_script} {log_dir} {clk}'"
    
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout = result.stdout.decode("utf-8")
    stderr = result.stderr.decode("utf-8")
    if result.returncode == 0:
        return eval(stdout.strip())
    else:
        print(f"Error: {result.stderr}")
        return large_num, large_num, large_num, large_num, large_num, large_num

def get_job_name(design_name:str, clk:float, util:float, ar:float,
            tech:str, density_lb_addon:float, timing_effort:int, is_hier:int,
            power_effort:int, gp_pad:int, dp_pad:int, enable_dpo:int,
            cts_cluster_size:int, cts_cluster_dia:int, gp_rd:int, gp_td:int,
            pin_adj:float, up_adj:float) -> str:
    job_name=f"DESIGN_{design_name}__CLK_{clk}__UTIL_{util}"\
            f"__AR_{ar}__TECH_{tech}__"\
            f"LB_ADDON_{density_lb_addon}__TIMING_EFFORT_{timing_effort}"\
            f"__POWER_EFFORT_{power_effort}__HIER_SYNTH_{is_hier}"\
            f"__GP_PAD_{gp_pad}__DP_PAD_{dp_pad}__RD_{gp_rd}__TD_{gp_td}"\
            f"__DPO_{enable_dpo}__CTS_CSIZE_{cts_cluster_size}"\
            f"__CTS_CDIA_{cts_cluster_dia}__PIN_ADJ_{pin_adj}__UP_ADJ_{up_adj}"
    return job_name

def run_job(design:str, clk_period:float, util:float, ar:float, tech:str,
            density_lb_addon:float, timing_effort:int, is_hier:int,
            power_effort:int, gp_pad:int, dp_pad:int, enable_dpo:int,
            cts_cluster_size:int, cts_cluster_dia:int, gp_rd:int, gp_td:int,
            pin_adj:float, up_adj:float, run_dir:str, server:str,
            cached_netlist:Optional[str] = None,
            timeout:int = 14400) -> Tuple[float, float, float, float, float, float]:
    ref_dir=os.path.dirname(os.path.abspath(__file__))
    ref_script=f"{ref_dir}/run_or_job.sh"
    dq='"'
    if cached_netlist is not None and os.path.exists(cached_netlist):
        run_dir_b = f"{run_dir} {cached_netlist}"
    else:
        run_dir_b = run_dir
    shell_command = f"ssh {server} {dq}{ref_script} {design} {clk_period}"\
                    f" {util} {ar} {tech} {density_lb_addon}"\
                    f" {timing_effort} {power_effort} {is_hier} {gp_pad}"\
                    f" {dp_pad} {enable_dpo} {gp_td} {gp_rd}"\
                    f" {cts_cluster_size} {cts_cluster_dia} {pin_adj}"\
                    f" {up_adj} {run_dir_b}{dq}"
    job_name=get_job_name(design, clk_period, util, ar, tech, density_lb_addon,
                        timing_effort, is_hier, power_effort, gp_pad, dp_pad,
                        enable_dpo, cts_cluster_size, cts_cluster_dia, gp_rd,
                        gp_td, pin_adj, up_adj)
    
    print(f"Running: {shell_command}")
    
    if design == "aes_cipher_top":
        design_name = "aes"
    elif design == "ibex_core":
        design_name = "ibex"
    elif design == "jpeg_encoder":
        design_name = "jpeg"
    else:
        design_name = design
    
    try:
        _ = subprocess.run(shell_command, timeout=timeout, shell=True,
                           check=True, stdout=subprocess.DEVNULL)
        # return extract_ppa(f"{run_dir}/logs/{tech}/{design_name}/{job_name}",
        #         clk_period)
        return extract_ppa_remote(f"{run_dir}/logs/{tech}/{design_name}/{job_name}",
                                clk_period, server)
    except subprocess.TimeoutExpired:
        print(f"Timeout: {timeout} seconds")
        return extract_ppa_remote(f"{run_dir}/logs/{tech}/{design_name}/{job_name}",
                                clk_period, server)
    except subprocess.CalledProcessError as error_message:
        print(f"Error: {error_message}")
        return extract_ppa_remote(f"{run_dir}/logs/{tech}/{design_name}/{job_name}",
                                clk_period, server)
    
if __name__ == "__main__":
    design=sys.argv[1]
    tech=sys.argv[2]
    run_dir="/home/scratch/sakundu/TEST"
    server="pdn"
    cached_netlist=None
    
    clk_period=10.0
    util=45
    ar=1.0
    density_lb_addon=0.2
    timing_effort=100
    is_hier=0
    power_effort=0
    gp_pad=0
    dp_pad=0
    enable_dpo=1
    cts_cluster_size=1
    cts_cluster_dia=1
    gp_rd=1
    gp_td=1
    pin_adj=0.35
    up_adj=0.35
    
    if design == "ibex" and tech == "sky130hd":
        clk_period=10.0
        util=45
        ar=1
        density_lb_addon=0.2
        timing_effort=100
        is_hier=0
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=1
        cts_cluster_size=1
        cts_cluster_dia=1
        gp_rd=1
        gp_td=1
        pin_adj=0.35
        up_adj=0.35
    elif design == "aes" and tech == "asap7":
        clk_period=400
        util=40
        ar=1
        density_lb_addon=0.3913
        timing_effort=100
        is_hier=0
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=1
        cts_cluster_size=1
        cts_cluster_dia=1
        gp_rd=1
        gp_td=1
        pin_adj=0.5
        up_adj=0.5
    elif design == "jpeg" and tech == "sky130hd":
        clk_period=8.0
        util=50
        ar=1
        density_lb_addon=0.15
        timing_effort=100
        is_hier=0
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=1
        cts_cluster_size=1
        cts_cluster_dia=1
        gp_rd=1
        gp_td=1
        pin_adj=0.3
        up_adj=0.3
    elif design == "aes" and tech == "sky130hd":
        clk_period=4.5
        util=20
        ar=1
        density_lb_addon=0.4936
        timing_effort=100
        is_hier=0
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=1
        cts_cluster_size=1
        cts_cluster_dia=1
        gp_rd=1
        gp_td=1
        pin_adj=0.4
        up_adj=0.4
    elif design == "ibex" and tech == "asap7":
        clk_period=1260
        util=40
        ar=1
        density_lb_addon=0.20
        timing_effort=100
        is_hier=0
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=0
        cts_cluster_size=1
        cts_cluster_dia=1
        gp_rd=1
        gp_td=1
        pin_adj=0.5
        up_adj=0.5
    elif design == "jpeg" and tech == "asap7":
        # DESIGN_jpeg__CLK_417.895__UTIL_57.308__AR_1__TECH_asap7__LB_ADDON_0.268__TIMING_EFFORT_15__POWER_EFFORT_30__HIER_SYNTH_1__GP_PAD_0__DP_PAD_0__RD_0__TD_1__DPO_0__CTS_CSIZE_187__CTS_CDIA_41__PIN_ADJ_0.266__UP_ADJ_0.241
        clk_period=417.895
        util=57.308
        ar=1
        density_lb_addon=0.268
        timing_effort=15
        is_hier=1
        power_effort=0
        gp_pad=0
        dp_pad=0
        enable_dpo=1
        cts_cluster_size=187
        cts_cluster_dia=41
        gp_rd=0
        gp_td=1
        pin_adj=0.266
        up_adj=0.241
    
    a = run_job(design, clk_period, util, ar, tech, density_lb_addon,
                timing_effort, is_hier, power_effort, gp_pad, dp_pad,
                enable_dpo, cts_cluster_size, cts_cluster_dia, gp_rd,
                gp_td, pin_adj, up_adj, run_dir, server, cached_netlist)
    
    print(a[0], a[1], a[2], a[3], a[4], a[5])
