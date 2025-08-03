import os
import json
import sys
from typing import Tuple

def extract_ppa(log_dir: str, clk: float):
    rpt_file = f"{log_dir}/6_report.json"
    cts_rpt_file = f"{log_dir}/4_1_cts.json"
    route_rpt_file = f"{log_dir}/5_2_route.json"
    na_value = "N/A"
    cts_ecp = na_value
    cts_tns = na_value
    cts_wns = na_value
    cts_drv = na_value
    cts_wl = na_value
    if os.path.exists(cts_rpt_file):
        with open(cts_rpt_file, 'r') as fp:
            data = json.load(fp)
            cts_wl = float(data.get("cts__route__wirelength__estimated", na_value))
            cts_wns = float(data.get("cts__timing__setup__ws", na_value))
            if cts_wns != na_value:
                cts_ecp = clk - cts_wns
            cts_tns = float(data.get("cts__timing__setup__tns", na_value))
            cts_drv = float(data.get("cts__timing__drv__setup_violation_count", na_value))
        
    drt_wire_length = na_value
    drt_drc_count = na_value
    drt_via_count = na_value
    if os.path.exists(route_rpt_file):
        with open(route_rpt_file, 'r') as fp:
            data = json.load(fp)
            drt_wire_length = float(data.get("detailedroute__route__wirelength", na_value))
            drt_drc_count = float(data.get("detailedroute__route__drc_errors", na_value))
            drt_via_count = float(data.get("detailedroute__route__vias", na_value))

    finish_wns = na_value
    finish_tns = na_value
    finish_setup_drv = na_value
    finish_hold_drv = na_value
    finish_power = na_value
    finish_util = na_value
    finish_buf_count = na_value
    finish_ecp = na_value
    
    if os.path.exists(rpt_file):
        with open(rpt_file, 'r') as fp:
            data = json.load(fp)
            finish_wns = float(data.get("finish__timing__setup__ws", na_value))
            finish_tns = float(data.get("finish__timing__setup__tns", na_value))
            finish_setup_drv = float(data.get("finish__timing__drv__setup_violation_count", na_value))
            finish_hold_drv = float(data.get("finish__timing__drv__hold_violation_count", na_value))
            finish_util = float(data.get("finish__design__instance__utilization", na_value))
            finish_power = float(data.get("finish__power__total", na_value))
            finish_buf_count = float(data.get("finish__design__instance__count__class:timing_repair_buffer", na_value))
            
            if finish_wns != na_value:
                finish_ecp = clk - finish_wns
        
    return cts_wns, cts_tns, cts_drv, cts_wl, drt_wire_length, drt_drc_count, \
            drt_via_count, finish_wns, finish_tns, finish_setup_drv, \
            finish_hold_drv, finish_power, finish_util, finish_buf_count, \
            cts_ecp, finish_ecp

if __name__ == "__main__":
    log_dir = sys.argv[1]
    clk = float(sys.argv[2])
    result = extract_ppa(log_dir, clk)
    print(result)