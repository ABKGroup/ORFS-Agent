export PLATFORM               = asap7

export DESIGN_NAME            = aes_cipher_top
export DESIGN_NICKNAME        = aes

export VERILOG_FILES = $(sort $(wildcard ./designs/src/$(DESIGN_NICKNAME)/*.v))
export SDC_FILE      = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/constraint.sdc

export ABC_AREA                 = 1

export CORE_UTILIZATION         = 40
export CORE_ASPECT_RATIO        = 1
export CORE_MARGIN              = 2
export PLACE_DENSITY_LB_ADDON            = 0.3913
export TNS_END_PERCENT          = 100
export EQUIVALENCE_CHECK       ?=   1
export REMOVE_CELLS_FOR_EQY     = TAPCELL*
export FASTROUTE_TCL = ./designs/$(PLATFORM)/$(DESIGN_NICKNAME)/fastasap.tcl

export CTS_CLUSTER_SIZE = 20
export CTS_CLUSTER_DIAMETER = 100
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT = 3
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT = 3
export SYNTH_FLATTEN = 1
export ENABLE_DPO = 1
export PIN_LAYER_ADJUST = 0.5
export ABOVE_LAYER_ADJUST = 0.5

