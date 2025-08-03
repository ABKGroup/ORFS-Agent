LLM Agent Briefing: Optimizing OpenROAD Hyper-parameters

Your goal is to choose one-shot hyper-parameter sets for OpenROAD physical-design runs, executed (and logged) by Ray Tune / Optuna.
Exactly one of three metrics is minimized per run:

Objective: Effective Clock Period (ECP)
Report field to read: ECP_final (or _cts)
Lower = Better: Yes
Notes:
Definition:
ECP = CLK – WNS (WNS is worst-negative-slack; negative number).
If timing violates (WNS < 0) then ECP is much greater than CLK.
If timing meets (WNS ≥ 0) then ECP is less than or equal to CLK (positive slack lets ECP dip below CLK).

Objective: Wire-length (WL)
Report field to read: detailedroute__route__wirelength
Lower = Better: Yes
Notes: Manhattan total after detailed routing.

Objective: Fractional Loss
Report field to read: Fractional_Loss_final
Lower = Better: Yes
Notes: (ECP / ECP_baseline) + (WL / WL_baseline); every baseline run = 2.0.

A run with detailedroute__route__drc_errors not equal to 0 is invalid.

Inputs & Tunables
Identifiers: circuit is one of {aes, ibex, jpeg} and pdk is one of {asap7, sky130hd}

The following list details the tunable parameters:

JSON Key: CLK
Parameter (UI): Clock Period
Range / Type:
asap7 : 100 – 10 000 ps
sky130hd : 0.5 – 15 ns
PDK-specific?: Yes

JSON Key: UTIL
Parameter (UI): Core Utilisation
Range / Type: 20 – 99 % (integer)
PDK-specific?: –

JSON Key: TNS_End_Percent
Parameter (UI): Timing-repair effort
Range / Type: 0 – 100 %
PDK-specific?: –

JSON Key: GP_PAD
Parameter (UI): Global Padding
Range / Type: 0-3
PDK-specific?: –

JSON Key: DP_PAD
Parameter (UI): Detail Padding
Range / Type: 0-3
PDK-specific?: –

JSON Key: DPO
Parameter (UI): Enable DPO
Range / Type: 0 / 1
PDK-specific?: –

JSON Key: PIN_ADJ
Parameter (UI): Pin-layer adjust
Range / Type: 0.10 – 0.70
PDK-specific?: –

JSON Key: UP_ADJ
Parameter (UI): Above-layer adjust
Range / Type: 0.10 – 0.70
PDK-specific?: –

JSON Key: LB_ADDON
Parameter (UI): Density margin add-on
Range / Type: 0.00 – 0.99
PDK-specific?: –

JSON Key: Flatten Hierarchy
Parameter (UI): 0 (flatten) / 1 (hierarchical) → set HIER_SYNTH = 1−value
Range / Type: –
PDK-specific?: –

JSON Key: CTS_CSIZE
Parameter (UI): CTS cluster size
Range / Type: 10 – 40 (integer). Note: Historical data may contain the value '1' (e.g., from baselines); this value is acknowledged but the Bayesian Optimizer will search for new configurations within the 10-40 range.
PDK-specific?: –

JSON Key: CTS_CDIA
Parameter (UI): CTS cluster dia.
Range / Type: 80 – 120 (integer). Note: Historical data may contain the value '1' (e.g., from baselines); this value is acknowledged but the Bayesian Optimizer will search for new configurations within the 80-120 range.
PDK-specific?: –

ar, gp_rd, gp_td are always 1 (not tuned).

Use the "_final" metric versions when they exist.

Critical Constraints & Baselines
PDK awareness: Units & ranges depend on PDK (see CLK in the list of Inputs & Tunables).
Manufacturability: drc_errors must be zero.
Reference data: wl_dict, ecp_dict, and init_configs give per-(circuit, PDK) baselines. Baselines all have Fractional_Loss = 2.0.

Parameter Effects & How They Move Effective Clock Period
The following describes how each knob affects ECP:

Knob: CLK
Increased Value does this to ECP: Increases the first term in ECP = CLK – WNS; if WNS improves only slightly, ECP can rise.
Decreased Value does this to ECP: Makes target cycle shorter; if it pushes WNS very negative, ECP rises; if timing still met (WNS ≥ 0) ECP falls.
Side-effects: Tight CLK can add buffers, WL increases, power increases.

Knob: UTIL
Increased Value does this to ECP: Higher utilisation crowds cells leading to congestion, which leads to worse WNS, and thus ECP increases.
Decreased Value does this to ECP: More whitespace eases timing leading to WNS less negative / positive, and thus ECP decreases.
Side-effects: WL trend opposite (UTIL increase often WL decrease).

Knob: TNS_End_Percent
Increased Value does this to ECP: Aggressive fixing improves WNS (toward 0 / positive) leading to ECP decrease.
Decreased Value does this to ECP: Minimal fixing leaves WNS very negative leading to ECP increase.
Side-effects: High effort corresponds to WL increase (buffers).

Knob: Padding / LB_ADDON
Increased Value does this to ECP: More space implies better WNS implies ECP decrease (area cost).
Decreased Value does this to ECP: Less space implies risk WNS decrease implies ECP increase.
Side-effects: Area / WL trade.

Knob: DPO = 1
Effect on ECP: Typically improves placement timing leading to ECP decrease.
(No specific effect mentioned for decreased value, as it's an enable/disable toggle)
Side-effects: Runtime increase.

Knob: Flatten (HIER_SYNTH = 0)
Effect on ECP: Global optimisation leads to better WNS leads to ECP decrease.
(No specific effect mentioned for decreased value, as it's a mode selection)
Side-effects: Mem/runtime increase.

Knob: CTS params
Increased Value does this to ECP: Better skew control can reduce WNS leading to ECP decrease if tuned.
(No specific effect mentioned for decreased value)
Side-effects: Tree wire impact.

Objective-Driven Heuristics
The following heuristics are suggested for different objectives:

Aim: Minimise ECP
CLK: Relax CLK only until WNS is approximately 0 (large negative slack is the main enemy).
UTIL: Lower UTIL 5-20 percentage points.
TNS%: 80-100 %.
Other hints: Add padding & turn DPO ON.

Aim: Minimise WL
CLK: Keep or slightly relax CLK (do not tighten).
UTIL: Raise UTIL 5-15 percentage points (watch DRC).
TNS%: 0-20 %.
Other hints: Padding low; DPO optional.

Aim: Minimise FracLoss
CLK: If ECP dominating loss: small CLK relax + small UTIL drop + mid TNS%. If WL dominating: small UTIL raise + TNS% decrease.
UTIL: Balance each case.
TNS%: (Covered by CLK interaction)
Other hints: (None specified beyond CLK/UTIL adjustments)

Ray Tune / Optuna in One-Shot Mode
Define PDK-aware search space (see the list of Inputs & Tunables for parameter ranges).
Enqueue baseline config first.
LLM outputs K candidate configs → framework runs them.
Objective function returns the chosen _final metric; infeasible if drc_errors > 0.
Framework logs JSON for the next reasoning round.
Quick Parameter Definitions (What they are in isolation):

Clock Period (CLK): Target time for one clock cycle; dictates chip operating speed.
Core Utilization (UTIL): Percentage of core area filled by standard cells; controls design density.
TNS End Percent: Percentage of timing violations the tool attempts to fix.
Global Padding: Coarse extra spacing around cells during initial placement for routability.
Detail Padding: Finer-grained extra spacing during detailed placement for local congestion.
Enable DPO: Toggles an advanced, detailed placement optimization stage.
Pin Layer Adjust: Modifies routing resource allocation on lower metal layers (M2/M3).
Above Layer Adjust: Modifies routing resource allocation on higher metal layers (M4+).
Density Margin Add-On: Additional safety margin to reduce target global placement density.
Flatten Hierarchy: Decides if the design's modular structure is removed for synthesis/placement.
CTS Cluster Size: Maximum number of clock sinks (flip-flops) grouped per clock tree branch.
CTS Cluster Diameter: Maximum physical span allowed for each clock tree cluster.

Baseline Configuration Context:

The provided "baseline" ECP and WL values were achieved using specific initial configurations. These serve as "above average" starting points for comparison. For any (circuit, pdk) combination:

Tunable Parameter Settings (from init_configs):
aes, asap7: CLK: 400ps, UTIL: 40, LB_ADDON: 0.3913, PIN_ADJ: 0.5, UP_ADJ: 0.5, DPO: 1
aes, sky130hd: CLK: 4.5ns, UTIL: 20, LB_ADDON: 0.4936, PIN_ADJ: 0.4, UP_ADJ: 0.4, DPO: 1
ibex, sky130hd: CLK: 10.0ns, UTIL: 45, LB_ADDON: 0.2, PIN_ADJ: 0.35, UP_ADJ: 0.35, DPO: 0
ibex, asap7: CLK: 1260ps, UTIL: 40, LB_ADDON: 0.2, PIN_ADJ: 0.5, UP_ADJ: 0.5, DPO: 0
jpeg, sky130hd: CLK: 8.0ns, UTIL: 50, LB_ADDON: 0.15, PIN_ADJ: 0.3, UP_ADJ: 0.3, DPO: 1
jpeg, asap7: CLK: 1100ps, UTIL: 30, LB_ADDON: 0.4127, PIN_ADJ: 0.5, UP_ADJ: 0.5, DPO: 1

Note that the clock period is passed in without units and uses different units in both cases, so you should pass in general values in the hundreds for clock period in asap7 and as a rule between 100 and ten thousand, but sky130hd is between 0.5 and 15.

Default/Fixed Settings for Baselines (from base_config):
TNS_End_Percent (timing_effort): 100
HIER_SYNTH (is_hier=0 implies flattened): 0 (Flattened Design)
GP_PAD: 0
DP_PAD: 0
CTS_CSIZE: 1 (Note: This value is outside the typical tunable range of 10-40 used for Bayesian Optimization search, but present in baselines.)
CTS_CDIA: 1 (Note: This value is outside the typical tunable range of 80-120 used for Bayesian Optimization search, but present in baselines.)
Other fixed: ar:1, gp_rd:1, gp_td:1

Resulting Baseline Metrics:
Wirelength (wl_dict):
aes, asap7: 75438.0
aes, sky130hd: 589825.0
ibex, asap7: 115285.0
ibex, sky130hd: 808423.0
jpeg, asap7: 300326.0
jpeg, sky130hd: 1374966.0

ECP (ecp_dict):
aes, asap7: 459.921
aes, sky130hd: 4.721
ibex, asap7: 1361.547
ibex, sky130hd: 11.543
jpeg, asap7: 1148.04
jpeg, sky130hd: 7.731

Fractional Loss: For these baseline runs, the Fractional_Loss_final (if calculated for ECP or WL individually against itself) would be 2.0, i.e. 1 from each.

Understand that the tunable ranges for parameters like CLK (e.g., asap7: 100-10000 ps; sky130hd: 0.5-15.0 ns) offer broader exploration beyond these specific baseline CLK values.
