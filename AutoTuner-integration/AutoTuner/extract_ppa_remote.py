import os
import json
import sys
from typing import Tuple

def extract_ppa(log_dir: str, clk: float) -> Tuple[float, float, float, float, float, float, float]:
    rpt_file = f"{log_dir}/6_report.json"
    cts_rpt_file = f"{log_dir}/4_1_cts.json"
    large_num = sys.float_info.max
    cts_wl = large_num
    cts_ecp = large_num
    if os.path.exists(cts_rpt_file):
        with open(cts_rpt_file, 'r') as fp:
            data = json.load(fp)
            cts_wl = float(data.get("cts__route__wirelength__estimated", large_num))
            ws = float(data.get("cts__timing__setup__ws", large_num))
            cts_ecp = clk - ws
            if ws == large_num:
                cts_ecp = large_num
            

    if os.path.exists(rpt_file):
        with open(rpt_file, 'r') as fp:
            data = json.load(fp)
            ws = float(data.get("finish__timing__setup__ws", large_num))
            core_area = float(data.get("finish__design__core__area", large_num))
            total_power = float(data.get("finish__power__total", large_num))
        with open(f"{log_dir}/5_2_route.json", 'r') as fp:
            drc_data = json.load(fp)
            drc_count = float(drc_data.get("detailedroute__route__drc_errors", large_num))
            rwl = float(drc_data.get("detailedroute__route__wirelength", large_num))
            ecp = clk - ws
            if ws == large_num:
                ecp = large_num
        return total_power, ecp, core_area, drc_count, rwl, cts_wl, cts_ecp

    return large_num, large_num, large_num, large_num, large_num, cts_wl, cts_ecp

if __name__ == "__main__":
    log_dir = sys.argv[1]
    clk = float(sys.argv[2])
    result = extract_ppa(log_dir, clk)
    print(result)