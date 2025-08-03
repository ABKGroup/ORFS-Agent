utl::set_metrics_stage "finish__update__{}"
source $::env(SCRIPTS_DIR)/util.tcl
source $::env(SCRIPTS_DIR)/report_metrics.tcl

# Temporarily disable sta's threading due to random failures
sta::set_thread_count 1

proc load_design {design_def sdc_file} {
  # Read liberty files
  source $::env(SCRIPTS_DIR)/read_liberty.tcl

  read_lef $::env(TECH_LEF)
  read_lef $::env(SC_LEF)
  if {[info exist ::env(ADDITIONAL_LEFS)]} {
    foreach lef $::env(ADDITIONAL_LEFS) {
      read_lef $lef
    }
  }

  # Read DEF file 
  read_def $design_def

  # Read SDC file
  read_sdc $sdc_file

  if [file exists $::env(PLATFORM_DIR)/derate.tcl] {
    source $::env(PLATFORM_DIR)/derate.tcl
  }

  source $::env(PLATFORM_DIR)/setRC.tcl

  if { [info exists ::env(LIB_MODEL)] && $::env(LIB_MODEL) == "CCS" } {
    puts "Using CCS delay calculation"
    set_delay_calculator prima
  }
}

load_design $::env(DESIGN_DEF) $::env(DESIGN_SDC)
set_propagated_clock [all_clocks]

# Ensure all OR created (rsz/cts) instances are connected
global_connect

# Delete routing obstructions for final DEF
source $::env(SCRIPTS_DIR)/deleteRoutingObstructions.tcl
deleteRoutingObstructions

# Run extraction and STA
if {[info exist ::env(RCX_RULES)]} {

  # Set RC corner for RCX
  # Set in Platform config.mk
  if {[info exist ::env(RCX_RC_CORNER)]} {
    set rc_corner $::env(RCX_RC_CORNER)
  }

  # RCX section
  define_process_corner -ext_model_index 0 X
  extract_parasitics -ext_model_file $::env(RCX_RULES)

  # Write Spef
  write_spef $::env(RESULTS_DIR)/6_final.spef
  file delete $::env(DESIGN_NAME).totCap

  # Read Spef for OpenSTA
  read_spef $::env(RESULTS_DIR)/6_final.spef

} else {
  puts "OpenRCX is not enabled for this platform."
}

source [file join $::env(SCRIPTS_DIR) "write_ref_sdc.tcl"]
report_cell_usage

report_metrics 6 "finish"

