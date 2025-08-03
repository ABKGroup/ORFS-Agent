export DESIGN_NICKNAME = jpeg
export DESIGN_NAME = jpeg_encoder
export PLATFORM    = nangate45

export VERILOG_FILES = $(sort $(wildcard ./designs/src/$(DESIGN_NICKNAME)/*.v))
export VERILOG_INCLUDE_DIRS = ./designs/src/$(DESIGN_NICKNAME)/include
export SDC_FILE      		  ?= $(RUN_DIR)/$(DESIGN_NAME).sdc
export ABC_AREA = 1

export CORE_UTILIZATION ?= 45
export PLACE_DENSITY_LB_ADDON ?= 0.20
export TNS_END_PERCENT        ?= 100
export EQUIVALENCE_CHECK     ?=   0

