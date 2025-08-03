export DESIGN_NICKNAME = ibex
export DESIGN_NAME = ibex_core
export PLATFORM    = sky130hd

export VERILOG_FILES = $(sort $(wildcard ./designs/src/$(DESIGN_NICKNAME)/*.v))

# export SDC_FILE      ?= ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/constraint.sdc
export SDC_FILE      		 ?= $(RUN_DIR)/$(DESIGN_NAME).sdc

# Adders degrade ibex setup repair
export ADDER_MAP_FILE :=

export CORE_UTILIZATION ?= 45
export PLACE_DENSITY_LB_ADDON ?= 0.2
export TNS_END_PERCENT ?= 100

export FASTROUTE_TCL ?= ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastroute.tcl

export REMOVE_ABC_BUFFERS = 1
