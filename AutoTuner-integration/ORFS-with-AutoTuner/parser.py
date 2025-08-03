import os
import json
import re

def parse_folder_name(folder_name):
    """Parses the folder name to extract parameters."""
    params = {}
    # Expecting format like: DESIGN_aes__CLK_123.45__UTIL_67.89__TIMING_EFFORT_29...
    
    parts = folder_name.split('__')

    first_part = parts.pop(0) if parts else folder_name
    if first_part.startswith("DESIGN_"):
        try:
            params['DESIGN'] = first_part.split('_', 1)[1] # e.g., 'aes'
        except IndexError:
            params['DESIGN'] = 'unknown' 
    else:
        # If it doesn't start with DESIGN_, it's a regular parameter part
        parts.insert(0, first_part)

    for part in parts:
        if not part: 
            continue

        last_underscore_idx = part.rfind('_')
        
        if last_underscore_idx != -1:
            key_candidate = part[:last_underscore_idx]
            value_candidate_str = part[last_underscore_idx+1:]
            
            # Try to convert value to float or int
            try:
                if '.' in value_candidate_str:
                    parsed_value = float(value_candidate_str)
                else:
                    parsed_value = int(value_candidate_str)
                params[key_candidate] = parsed_value
            except ValueError:
                # If conversion fails, it's a string value (e.g., TECH_asap7 -> {"TECH": "asap7"})
                # Or it could be that the key itself had an underscore and the value was part of it.
                # e.g. if a part was "SOME_KEY_WITH_STRING" and we expect "SOME_KEY_WITH_STRING" : "FLAG"
                # For now, assume last part is value if conversion failed.
                params[key_candidate] = value_candidate_str 
        else:
            # No underscore, consider it a flag or a key with an implicit value (e.g. True)
            # For now, just store the part as a key with a placeholder.
            # This might need adjustment based on actual folder naming conventions for such cases.
            params[part] = "FLAG_PARAM" # Or True, or handle as error/log

    # Rename TIMING_EFFORT to TNS_End_Percent if it exists
    if "TIMING_EFFORT" in params:
        params["TNS_End_Percent"] = params.pop("TIMING_EFFORT")
        
    # Remove AR, TD, RD, and POWER_EFFORT if they exist
    for key_to_remove in ["AR", "TD", "RD", "POWER_EFFORT"]:
        if key_to_remove in params:
            del params[key_to_remove]
            
    return params

def get_numeric_value(value):
    """Helper to convert a value to float/int, or return None if N/A or not convertible."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str) and value.lower() == "n/a":
        return None
    try:
        return float(value) # Attempt to convert strings that might be numbers
    except (ValueError, TypeError):
        return None

def process_files(root_dir, output_json_filename):
    """Processes all parameter folders and writes the specified data to a JSON file."""
    all_runs_data = []

    original_metrics = {
        ("sky130hd", "ibex"): {
            "Orig_ECP_cts": 10.84, "Orig_WL_cts": 550963,
            "Orig_ECP_final": 11.54, "Orig_WL_final": 808423
        },
        ("asap7", "ibex"): {
            "Orig_ECP_cts": 1308.00, "Orig_WL_cts": 93005,
            "Orig_ECP_final": 1361.00, "Orig_WL_final": 115285
        },
        ("sky130hd", "aes"): {
            "Orig_ECP_cts": 5.34, "Orig_WL_cts": 428916,
            "Orig_ECP_final": 4.72, "Orig_WL_final": 589825
        },
        ("asap7", "aes"): {
            "Orig_ECP_cts": 432.00, "Orig_WL_cts": 61103,
            "Orig_ECP_final": 460.00, "Orig_WL_final": 75438
        }
    }

    keys_to_extract_map = {
        "4_1_cts.json": [
            "cts__timing__setup__ws", "cts__timing__setup__tns",
            "cts__timing__drv__setup_violation_count", "cts__route__wirelength__estimated"
        ],
        "5_2_route.json": [
            "detailedroute__route__wirelength", "detailedroute__route__drc_errors",
            "detailedroute__route__vias"
        ],
        "6_report.json": [
            "finish__timing__setup__ws", "finish__timing__setup__tns",
            "finish__timing__drv__setup_violation_count", "finish__timing__drv__hold_violation_count",
            "finish__power__total", "finish__design__instance__utilization",
            "finish__design__instance__count__class:timing_repair_buffer"
        ]
    }

    if not os.path.isdir(root_dir):
        print(f"Error: Root directory '{root_dir}' not found.")
        return

    for circuit_pdk_name in os.listdir(root_dir):
        circuit_pdk_full_path = os.path.join(root_dir, circuit_pdk_name)
        if not os.path.isdir(circuit_pdk_full_path) or circuit_pdk_name.startswith('.'):
            continue

        for param_folder_name in os.listdir(circuit_pdk_full_path):
            param_folder_path = os.path.join(circuit_pdk_full_path, param_folder_name)
            if not os.path.isdir(param_folder_path) or not param_folder_name.startswith("DESIGN_"):
                continue

            current_run_data = {}
            pdk = "unknown"
            circuit = "unknown"

            if "aes_" in circuit_pdk_name: circuit = 'aes'
            elif "ibex_" in circuit_pdk_name: circuit = 'ibex'
            current_run_data['circuit'] = circuit
            
            if "_asap7" in circuit_pdk_name: pdk = 'asap7'
            elif "_sky130hd" in circuit_pdk_name: pdk = 'sky130hd'
            current_run_data['pdk'] = pdk

            folder_params = parse_folder_name(param_folder_name)
            current_run_data.update(folder_params)

            for json_file_basename, specific_keys in keys_to_extract_map.items():
                json_full_path = os.path.join(param_folder_path, json_file_basename)
                
                if os.path.exists(json_full_path) and os.path.isfile(json_full_path):
                    try:
                        with open(json_full_path, 'r') as f:
                            file_json_data = json.load(f)
                        for key in specific_keys:
                            current_run_data[key] = file_json_data.get(key, "N/A")
                    except json.JSONDecodeError:
                        print(f"Warning: Could not decode JSON from {json_full_path}. Marking its keys as 'N/A (JSON Error)'.")
                        for key in specific_keys:
                            current_run_data[key] = "N/A (JSON Error)"
                    except Exception as e:
                        print(f"Warning: Error reading {json_full_path}: {e}. Marking its keys as 'N/A (Read Error)'.")
                        for key in specific_keys:
                            current_run_data[key] = "N/A (Read Error)"
                else: 
                    for key in specific_keys:
                        current_run_data[key] = "N/A"
            
            # Calculations
            clk_period = get_numeric_value(folder_params.get("CLK"))

            cts_ws = get_numeric_value(current_run_data.get("cts__timing__setup__ws"))
            if clk_period is not None and cts_ws is not None:
                current_run_data["ECP_cts"] = clk_period - cts_ws
            else:
                current_run_data["ECP_cts"] = "N/A"

            finish_ws = get_numeric_value(current_run_data.get("finish__timing__setup__ws"))
            if clk_period is not None and finish_ws is not None:
                current_run_data["ECP_final"] = clk_period - finish_ws
            else:
                current_run_data["ECP_final"] = "N/A"

            run_orig_metrics = original_metrics.get((pdk, circuit))

            ecp_cts_val = get_numeric_value(current_run_data["ECP_cts"])
            cts_wl_est = get_numeric_value(current_run_data.get("cts__route__wirelength__estimated"))
            if run_orig_metrics and ecp_cts_val is not None and cts_wl_est is not None and \
               run_orig_metrics["Orig_ECP_cts"] != 0 and run_orig_metrics["Orig_WL_cts"] != 0:
                loss_ecp_cts = ecp_cts_val / run_orig_metrics["Orig_ECP_cts"]
                loss_wl_cts = cts_wl_est / run_orig_metrics["Orig_WL_cts"]
                current_run_data["Fractional_Loss_cts"] = loss_ecp_cts + loss_wl_cts
            else:
                current_run_data["Fractional_Loss_cts"] = "N/A"

            ecp_final_val = get_numeric_value(current_run_data["ECP_final"])
            dr_wl = get_numeric_value(current_run_data.get("detailedroute__route__wirelength"))
            if run_orig_metrics and ecp_final_val is not None and dr_wl is not None and \
               run_orig_metrics["Orig_ECP_final"] != 0 and run_orig_metrics["Orig_WL_final"] != 0:
                loss_ecp_final = ecp_final_val / run_orig_metrics["Orig_ECP_final"]
                loss_wl_final = dr_wl / run_orig_metrics["Orig_WL_final"]
                current_run_data["Fractional_Loss_final"] = loss_ecp_final + loss_wl_final
            else:
                current_run_data["Fractional_Loss_final"] = "N/A"

            all_runs_data.append(current_run_data)

    if not all_runs_data:
        print("No data successfully processed. Writing an empty list to JSON.")
        with open(output_json_filename, 'w') as f:
            json.dump([], f, indent=4)
        return

    try:
        with open(output_json_filename, 'w') as f:
            json.dump(all_runs_data, f, indent=4)
        print(f"Successfully wrote data to {output_json_filename}")
    except Exception as e:
        print(f"Error writing JSON to file {output_json_filename}: {e}")

if __name__ == "__main__":
    data_directory = "aes_ibex_asap7_sky130hd_json"
    output_file = "output.json"
    process_files(data_directory, output_file) 