#==============================================================================
# Autotuner Make extension
#==============================================================================

# Report parameters using $(RUN_DIR)/report_param.sh
$(LOG_DIR)/report_param.log:
	@$(RUN_DIR)/report_param.sh | tee -a $(LOG_DIR)/report_param.log
	

.PHONY: tunereport
tunereport: $(LOG_DIR)/6_report.log \
        $(RESULTS_DIR)/6_final.v \
        $(RESULTS_DIR)/6_final.sdc \
        $(RESULTS_DIR)/6_final.def

.PHONY: eval_design
eval_design: check_design_files
	@mkdir -p $(RESULTS_DIR) $(LOG_DIR) $(REPORTS_DIR) $(OBJECTS_DIR)
	$(TIME_CMD) $(OPENROAD_CMD) -no_splash $(RUN_DIR)/eval_design.tcl -metrics $(LOG_DIR)/6_report.json 2>&1 | tee -a $(abspath $(LOG_DIR)/eval_run.log)

eval_update_design: eval_design
	(export DESIGN_SDC=$(RESULTS_DIR)/updated_clks.sdc; \
	$(TIME_CMD) $(OPENROAD_CMD) -no_splash $(RUN_DIR)/eval_design.tcl -metrics $(LOG_DIR)/final_report.json 2>&1 | tee -a $(abspath $(LOG_DIR)/eval_update_run.log))
	

.PHONY: check_design_files
check_design_files:
	@test -f $(DESIGN_DEF) || (echo "Error: $(DESIGN_DEF) does not exist!" && exit 1)
	@test -f $(DESIGN_SDC) || (echo "Error: $(DESIGN_SDC) does not exist!" && exit 1)
 
