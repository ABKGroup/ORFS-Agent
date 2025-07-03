eda_expert_prompt = """You are an expert EDA (Electronic Design Automation) engineer with deep expertise in Bayesian optimization, OpenROAD, and physical design flows.
You have extensive experience optimizing chip designs through intelligent parameter tuning and design space exploration.
You understand the intricacies of placement, routing, timing closure, and how different optimization parameters affect overall PPA (Power, Performance, Area) metrics.
You are well-versed in statistical analysis, machine learning approaches for design optimization, and modern EDA methodologies.
Your goal is to provide expert guidance on EDA flows, parameter optimization strategies, and design space exploration techniques."""


asap7_pdk_description = """ASAP7 is a predictive 7nm PDK developed by Arizona State University that provides an open-source platform for academic research in advanced node designs. 
It includes comprehensive device models, design rules, and standard cell libraries that enable realistic exploration of cutting-edge physical design challenges."""

sky130_pdk_description = """The SkyWater 130nm PDK (sky130) is an open-source process design kit developed in collaboration with Google and SkyWater Technology Foundry, 
offering a mature and manufacturable platform for chip design. It provides a complete suite of documentation, models, and design resources that enable real-world chip 
tape-outs while being accessible to the open-source community."""



eda_guidelines = {
    "asap7": {
        "aes": {
            "DWL": """For ASAP7 AES focusing on minimizing detailed wire length:
1. Use a moderate or slightly higher CORE_UTIL (e.g., 70–75) to avoid excessive congestion.
2. Increase GP_PAD (2–3) and DP_PAD (2–3) for extra spacing, which can help reduce routing detours.
3. ENABLE_DPO = 1 to let the tool run advanced detailed placement optimization steps.
4. PIN_LAYER_ADJUST = 0.5 and ABOVE_LAYER_ADJUST = 0.5 to balance routing resource usage.
5. PLACE_DENSITY_LB_ADDON = 0.15 or so to keep local density from pushing cells too close.
6. FLATTEN can be 0 if hierarchy is beneficial, or 1 if flattening helps reduce wire snaking.
7. For clock constraints, set CLOCK_PERIOD to a relaxed value (e.g., 1200–1500 ps) so the tool emphasizes wire length over tight timing.""",

            "ECP": """For ASAP7 AES focusing on achieving an effective (tight) clock period:
1. Set CLOCK_PERIOD aggressively (e.g., 800–1000 ps) to push timing closure.
2. Slightly reduce CORE_UTIL (e.g., 60–65) to allow more whitespace for buffering and routing.
3. Keep GP_PAD and DP_PAD in the lower range (0–1) to pack cells more tightly, improving timing QoR in some flows.
4. ENABLE_DPO = 1 to let the tool optimize placement for timing.
5. PIN_LAYER_ADJUST = 0.3 and ABOVE_LAYER_ADJUST = 0.3 to allow enough routing resources at critical metal layers.
6. PLACE_DENSITY_LB_ADDON = 0.05 or less to avoid artificially over-spreading cells.
7. FLATTEN = 1 if your design structure benefits from a monolithic perspective for timing closure.""",

            "COMBO": """For ASAP7 AES balancing wire length and clock period:
1. Choose a moderate CLOCK_PERIOD (around 1100–1200 ps) to keep timing feasible without excessive overhead.
2. CORE_UTIL in the 65–70 range for a moderate cell density that helps wire length while still meeting timing.
3. GP_PAD = 1–2 and DP_PAD = 1–2 for balanced cell spacing.
4. ENABLE_DPO = 1 to let the detailed placer re-optimize for both timing and wire length.
5. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 for balanced metal usage.
6. PLACE_DENSITY_LB_ADDON ~ 0.1 to keep local densities from becoming hotspots.
7. FLATTEN depends on design hierarchy; try 0 if hierarchy is well-structured, else 1.""",

            "CTS": """For ASAP7 AES using CTS as a proxy or surrogate:
1. Adjust CTS_CLUSTER_SIZE to around 20–25 and CTS_CLUSTER_DIAMETER to ~100 µm to cluster clock sinks efficiently.
2. TNS_END_PERCENT can be set to around 80, ensuring you fix violations on the most critical endpoints first.
3. If focusing more on wire length, allow a slightly larger CTS_CLUSTER_DIAMETER to reduce buffer insertion overhead.
4. If focusing on timing, reduce CTS_CLUSTER_DIAMETER to tighten sink clusters, improving local skew control.
5. Combine this with appropriate CLOCK_PERIOD settings (900–1300 ps) depending on your performance target.
6. Keep ENABLE_DPO = 1 for post-CTS optimization, or 0 if you prefer a simpler flow.""" 
        },
        "jpeg": {
            "DWL": """For ASAP7 JPEG focusing on detailed wire length:
1. CLOCK_PERIOD = 1300–1500 ps to loosen timing constraints.
2. CORE_UTIL = 75–80 if the design can handle moderate crowding; else reduce to 70 if congestion is severe.
3. GP_PAD = 3–4 and DP_PAD = 2–3 to reduce potential routing detours.
4. ENABLE_DPO = 1 to refine placement at the detailed level.
5. PIN_LAYER_ADJUST = 0.5, ABOVE_LAYER_ADJUST = 0.5 to distribute routing usage evenly across layers.
6. PLACE_DENSITY_LB_ADDON ~ 0.2 to avoid local hotspots.
7. FLATTEN = 0 if hierarchical modules help manage wire length; 1 if flattening yields better wire distribution.""",

            "ECP": """For ASAP7 JPEG focusing on tight clock period:
1. Aggressive CLOCK_PERIOD (900–1100 ps) to push performance.
2. Keep CORE_UTIL around 65–70 to leave room for buffers and routing.
3. GP_PAD = 1–2 and DP_PAD = 1–2 to maintain moderate spacing.
4. ENABLE_DPO = 1 for improved cell arrangement for timing closure.
5. PIN_LAYER_ADJUST = 0.3, ABOVE_LAYER_ADJUST = 0.3 for critical routing resource allocation.
6. PLACE_DENSITY_LB_ADDON = 0.05–0.1 for minimal over-spreading.
7. FLATTEN = 1 often helps in performance-critical flows for JPEG if the hierarchy complicates timing paths.""",

            "COMBO": """For ASAP7 JPEG balancing wire length and clock period:
1. CLOCK_PERIOD = ~1200 ps to strike a balance between performance and routing overhead.
2. CORE_UTIL in the 70–75 range, with GP_PAD = 2 and DP_PAD = 2 for balanced spacing.
3. ENABLE_DPO = 1 to let the flow refine placement/timing post-global placement.
4. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 to keep routing resources flexible.
5. PLACE_DENSITY_LB_ADDON = 0.1–0.15, preventing too-tight hotspots.
6. FLATTEN is optional; evaluate netlist hierarchy vs. wire distribution on a case-by-case basis.""",

            "CTS": """For ASAP7 JPEG using CTS parameters as a proxy:
1. CTS_CLUSTER_SIZE = 15–25 and CTS_CLUSTER_DIAMETER = 80–100 µm depending on block-level clock tree complexity.
2. TNS_END_PERCENT = 70–90 to systematically fix the worst endpoints first.
3. Slightly increase CTS_CLUSTER_DIAMETER if wire length is the bigger worry (to reduce buffer duplication).
4. If tight timing is critical, lower CTS_CLUSTER_DIAMETER to group sinks more tightly.
5. Combine with a balanced CORE_UTIL (around 70) and moderate CLOCK_PERIOD (1100–1300 ps)."""
        },
        "ibex": {
            "DWL": """For ASAP7 Ibex (RISC-V) focusing on minimizing detailed wire length:
1. CLOCK_PERIOD = 1400–1700 ps to allow more relaxed timing, focusing on short wires.
2. CORE_UTIL = 70–75, balancing density to avoid over-congestion on key modules (e.g., ALU).
3. GP_PAD = 2–3, DP_PAD = 2–3 to ensure enough spacing in critical regions, preventing routing detours.
4. ENABLE_DPO = 1 so the placer can optimize location of RISC-V specific logic clusters.
5. PIN_LAYER_ADJUST = 0.5, ABOVE_LAYER_ADJUST = 0.5 to keep routing balanced across layers 2/3 and 4+.
6. PLACE_DENSITY_LB_ADDON ~ 0.15 to prevent the core areas from overpacking.
7. FLATTEN can be 0 if the Ibex hierarchy is well-partitioned; 1 if flattening helps reduce long nets.""",
            
            "ECP": """For ASAP7 Ibex focusing on tighter clock period:
1. CLOCK_PERIOD = 1000–1300 ps to push performance while staying realistic for a small RISC-V core.
2. CORE_UTIL = 65–70 to allow whitespace for buffering, especially around the ALU and register file.
3. GP_PAD = 1–2, DP_PAD = 1–2 to keep cells closer, potentially reducing path delay at the expense of more routing congestion.
4. ENABLE_DPO = 1 to let the flow aggressively optimize timing-critical regions.
5. PIN_LAYER_ADJUST = 0.3, ABOVE_LAYER_ADJUST = 0.3 to reserve more routing margin for critical paths.
6. PLACE_DENSITY_LB_ADDON = 0.05–0.1 to avoid excessive spreading that hurts timing.
7. FLATTEN = 1 can help if Ibex's hierarchy is generating suboptimal paths for the CPU pipeline.""",
            
            "COMBO": """For ASAP7 Ibex balancing wire length and clock period:
1. CLOCK_PERIOD = ~1300–1400 ps to keep a modest performance target while not inflating wire usage.
2. CORE_UTIL = 70, GP_PAD = 2, DP_PAD = 2 for even distribution of cell blocks, balancing spacing.
3. ENABLE_DPO = 1 to capture post-global placement optimization for both wire length and timing.
4. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 to allow a middle-ground approach on routing usage.
5. PLACE_DENSITY_LB_ADDON = 0.1–0.15, preventing hotspots but not overly spreading cells.
6. FLATTEN can be 0 or 1 depending on design hierarchy specifics—try 0 first if hierarchy is well-defined.""",

            "CTS": """For ASAP7 Ibex using CTS parameters:
1. CTS_CLUSTER_SIZE = 20–25 to group the clock sinks in the pipeline stages cohesively.
2. CTS_CLUSTER_DIAMETER = ~90–100 µm for balanced clock tree building without too many buffers.
3. TNS_END_PERCENT = 80–90 to focus on the majority of critical endpoints first.
4. Larger CTS_CLUSTER_DIAMETER can reduce total wire, but watch for skew impacts.
5. Smaller CTS_CLUSTER_DIAMETER tightens local timing at the cost of extra clock buffers.
6. Combine with moderate CORE_UTIL (around 70) and CLOCK_PERIOD ~1300 ps to keep a balanced approach."""
        }
    },
    "sky130": {
        "aes": {
            "DWL": """For Sky130 AES focusing on minimizing detailed wire length:
1. CLOCK_PERIOD = 5.0–7.0 ns (less aggressive timing) to allow longer paths, focusing on wire efficiency.
2. CORE_UTIL = 70–80 if design size allows; that sweet spot often reduces wire bloat.
3. GP_PAD = 2–3, DP_PAD = 2–3 for better routing channels.
4. ENABLE_DPO = 1 to refine detailed placement for wire length.
5. PIN_LAYER_ADJUST = 0.5, ABOVE_LAYER_ADJUST = 0.5 to keep a balanced route distribution across metal layers.
6. PLACE_DENSITY_LB_ADDON = 0.15–0.2 helps avoid cell clustering that inflates wire length.
7. FLATTEN = 0 if the hierarchy helps manage wire routing across modules.""",

            "ECP": """For Sky130 AES focusing on tight clock period:
1. CLOCK_PERIOD = 3.5–4.5 ns to push performance in a 130nm node context.
2. CORE_UTIL = 60–65, leaving whitespace for buffers.
3. Lower GP_PAD and DP_PAD (0–1) to pack cells, but watch for congestion.
4. ENABLE_DPO = 1 to allow for post-placement timing improvements.
5. PIN_LAYER_ADJUST = 0.3, ABOVE_LAYER_ADJUST = 0.3 to prioritize routing resources in critical layers.
6. PLACE_DENSITY_LB_ADDON = 0.05–0.1 to avoid too much spreading.
7. FLATTEN = 1 if the AES module hierarchy adds too many hierarchical boundaries for critical paths.""",

            "COMBO": """For Sky130 AES balancing wire length and clock period:
1. CLOCK_PERIOD = ~5.0 ns (moderate) to allow some slack but still push performance.
2. CORE_UTIL ~ 70 for a middle ground on density vs. routing feasibility.
3. GP_PAD = 1–2, DP_PAD = 1–2 for balanced cell spacing.
4. ENABLE_DPO = 1 to let the EDA tool iterate on timing while preserving wire length.
5. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 to ensure consistent usage of routing layers.
6. PLACE_DENSITY_LB_ADDON ~ 0.1 to ensure local hotspots don't force huge wire lengths.
7. FLATTEN can be 0 or 1 depending on netlist structure; evaluate with a quick trial.""",

            "CTS": """For Sky130 AES using CTS parameters as a surrogate:
1. CTS_CLUSTER_SIZE = 20–30 for moderate cluster grouping; AES designs often benefit from midrange cluster sizes.
2. CTS_CLUSTER_DIAMETER = 90–110 µm so skew balancing is manageable without excessive buffering.
3. TNS_END_PERCENT = 80–90 to focus on the worst 80-90% of timing endpoints first.
4. If wire length is still too high, increase the CTS_CLUSTER_DIAMETER or reduce clustering to reduce buffer duplication.
5. If timing is more critical, decrease CTS_CLUSTER_DIAMETER to cluster sinks more tightly, at the cost of slightly more routing.
6. Combine with a moderate CORE_UTIL (65–70) and an intermediate CLOCK_PERIOD (4.5–5.5 ns)."""
        },
        "jpeg": {
            "DWL": """For Sky130 JPEG focusing on detailed wire length:
1. Relax CLOCK_PERIOD to 6.0–8.0 ns so the router is less forced to add buffers or detour paths.
2. CORE_UTIL = 75–80 if the design size is moderate; else 70 if there's congestion risk.
3. GP_PAD = 3–4, DP_PAD = 2–4 for wider channels to reduce wire detours.
4. ENABLE_DPO = 1 to help the detailed placer trim total wire length.
5. PIN_LAYER_ADJUST = 0.5, ABOVE_LAYER_ADJUST = 0.5 for an even distribution of routing across layers.
6. PLACE_DENSITY_LB_ADDON ~ 0.2 to maintain some separation between cells.
7. FLATTEN can remain 0 unless you suspect hierarchical boundaries are inflating wire length.""",

            "ECP": """For Sky130 JPEG focusing on a tighter clock period:
1. CLOCK_PERIOD = 4.0–5.0 ns in a 130nm context to push performance but remain realistic.
2. CORE_UTIL = 60–70, leaving enough whitespace for buffering.
3. GP_PAD = 1–2, DP_PAD = 1–2 to avoid large gaps in placement that can hurt timing.
4. ENABLE_DPO = 1 for advanced optimization post-global placement.
5. PIN_LAYER_ADJUST = 0.3, ABOVE_LAYER_ADJUST = 0.3 if layers 2/3 or 4/5 are critical for timing routes.
6. PLACE_DENSITY_LB_ADDON = 0.05–0.1 to prevent over-spreading and maintain timing-friendly placements.
7. FLATTEN = 1 if the JPEG design is large and hierarchical boundaries create extra critical path buffers.""",

            "COMBO": """For Sky130 JPEG balancing wire length and clock period:
1. CLOCK_PERIOD = 5.0–6.0 ns for moderate performance push.
2. CORE_UTIL = ~70–75, balancing cell density vs. routing complexity.
3. GP_PAD = 1–2, DP_PAD = 1–3 for moderate spacing.
4. ENABLE_DPO = 1 for iterative improvement in placement & timing.
5. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 to allow a balanced routing strategy.
6. PLACE_DENSITY_LB_ADDON = 0.1–0.15 for preventing overly tight cluster areas.
7. FLATTEN = 0 or 1 based on hierarchical complexities (try 0 first, then 1 if wire length is still high).""",

            "CTS": """For Sky130 JPEG using CTS parameters:
1. CTS_CLUSTER_SIZE = 15–20, CTS_CLUSTER_DIAMETER = 80–100 µm, depending on how the JPEG modules are structured.
2. TNS_END_PERCENT = 70–80 to address most critical endpoints.
3. Larger CTS_CLUSTER_DIAMETER reduces duplication of buffers (potentially lowering wire length).
4. Smaller CTS_CLUSTER_DIAMETER tightens sink grouping and may improve timing at the cost of extra buffers.
5. Combine with a moderate CLOCK_PERIOD (5–6 ns) and CORE_UTIL around 70 for balanced results.
6. ENABLE_DPO can remain 1 to refine post-CTS placement for final wire length or timing adjustments."""
        },
        "ibex": {
            "DWL": """For Sky130 Ibex (RISC-V) focusing on minimizing detailed wire length:
1. CLOCK_PERIOD = 6.0–8.0 ns to allow relaxed timing, focusing on wire reduction.
2. CORE_UTIL = 70–75 to balance density without choking critical CPU pipeline logic.
3. GP_PAD = 2–3, DP_PAD = 2–3 to create enough space for signal routing around ALU and register file cells.
4. ENABLE_DPO = 1 so the placement tool can fine-tune the CPU core arrangement.
5. PIN_LAYER_ADJUST = 0.5, ABOVE_LAYER_ADJUST = 0.5 for an even distribution across layers 2/3 and 4+.
6. PLACE_DENSITY_LB_ADDON ~ 0.15–0.2 to avoid hotspots that lead to longer wires.
7. FLATTEN can be 0 if the Ibex design is well-partitioned into logical modules; 1 if flattening helps reduce net detours.""",
            
            "ECP": """For Sky130 Ibex focusing on tighter clock period:
1. CLOCK_PERIOD = 4.0–5.0 ns, which is fairly tight in 130nm, but may be achievable for a small RISC-V core.
2. CORE_UTIL = 60–65, leaving headroom for buffers and critical path optimization.
3. GP_PAD = 1–2, DP_PAD = 1–2 to keep distances short but watch for routing bottlenecks.
4. ENABLE_DPO = 1 to let the tool push timing-critical paths more aggressively.
5. PIN_LAYER_ADJUST = 0.3, ABOVE_LAYER_ADJUST = 0.3 to prioritize key layers for CPU pipeline routing.
6. PLACE_DENSITY_LB_ADDON = 0.05–0.1 so you don’t inadvertently spread cells and lengthen short critical paths.
7. FLATTEN = 1 if hierarchy is impeding timing closure (especially around pipeline stages).""",

            "COMBO": """For Sky130 Ibex balancing wire length and clock period:
1. CLOCK_PERIOD = ~5.0–6.0 ns to maintain decent performance without massive wire overhead.
2. CORE_UTIL = 70, with GP_PAD = 1–2 and DP_PAD = 2–3 for moderate spacing.
3. ENABLE_DPO = 1 to refine the CPU core placement after global placement.
4. PIN_LAYER_ADJUST = 0.4, ABOVE_LAYER_ADJUST = 0.4 to maintain a balanced metal utilization.
5. PLACE_DENSITY_LB_ADDON = 0.1–0.15 so you avoid intense clustering that inflates wire length.
6. FLATTEN = 0 or 1—evaluate based on how the Ibex pipeline is structured; flatten if hierarchical boundaries create overhead.""",

            "CTS": """For Sky130 Ibex using CTS parameters:
1. CTS_CLUSTER_SIZE = 15–25 to cluster pipeline clock sinks sensibly, preventing over-buffering.
2. CTS_CLUSTER_DIAMETER = 80–100 µm, balancing local skew control vs. buffer duplication.
3. TNS_END_PERCENT = 70–90 to address the majority of timing violations in the CPU pipeline.
4. If wire length is a bigger priority, use a slightly larger CTS_CLUSTER_DIAMETER to reduce clock buffer insertion.
5. If tight pipeline timing is key, lower CTS_CLUSTER_DIAMETER to cluster the sinks more closely.
6. Combine with moderate CORE_UTIL (65–70) and CLOCK_PERIOD in the 5–6 ns range for a decent compromise."""
        }
    }
}

parameter_ranges = """The OpenROAD flow has several key input parameters with specific valid ranges:

CLOCK_PERIOD: Target clock period in nanoseconds (float). This is design-dependent with no fixed range.

CORE_UTIL: Core utilization percentage (integer) ranging from 20 to 99. Controls how tightly cells are packed.

GP_PAD and DP_PAD: Cell padding for global and detailed placement respectively (integers), both ranging from 0 to 4 sites.

ENABLE_DPO: Detailed placement optimization flag (integer), either 0 (disabled) or 1 (enabled).

PIN_LAYER_ADJUST and ABOVE_LAYER_ADJUST: Layer resource adjustment percentages (floats) for routing, both ranging from 0.2 to 0.7.
PIN_LAYER_ADJUST affects metal2/3 layers while ABOVE_LAYER_ADJUST affects metal4 and above.

PLACE_DENSITY_LB_ADDON: Additional lower bound increase for local placement density (float), ranging from 0.00 to 0.99.

FLATTEN: Design hierarchy flattening flag (integer), either 0 (preserve hierarchy) or 1 (flatten).

CTS_CLUSTER_SIZE: Target clock tree synthesis sink cluster size (integer), ranging from 10 to 40 sinks per cluster.

CTS_CLUSTER_DIAMETER: Target CTS sink cluster diameter in micrometers (integer), ranging from 80 to 120 µm.

TNS_END_PERCENT: Percentage of violating endpoints to repair (integer), ranging from 0 to 100."""

# Global metadata for timing units
timing_units = {
    "asap7": "picoseconds (ps)",
    "sky130": "nanoseconds (ns)"
}

default_parameters = {
    "asap7": {
        "aes": {
            "CLOCK_PERIOD": 400,  # ps
            "CORE_UTILIZATION": 40,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY": 0.65,
            "TNS_END_PERCENT": 100,
            "ABC_AREA": 1,
            "EQUIVALENCE_CHECK": 1
        },
        "jpeg": {
            "CLOCK_PERIOD": 1100,  # ps
            "CORE_UTILIZATION": 30,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY": 0.60,
            "TNS_END_PERCENT": 100,
            "ABC_AREA": 1,
            "EQUIVALENCE_CHECK": 1
        },
        "ibex": {
            "CLOCK_PERIOD": 1260,  # ps
            "CORE_UTILIZATION": 40,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY_LB_ADDON": 0.20,
            "ENABLE_DPO": 0,
            "TNS_END_PERCENT": 100
        }   
    },
    "sky130": {
        "aes": {
            "CLOCK_PERIOD": 4.5,  # ns
            "CORE_UTILIZATION": 20,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY": 0.60,
            "TNS_END_PERCENT": 100,
            "ABC_AREA": 1,
            "REMOVE_ABC_BUFFERS": 1
        },
        "jpeg": {
            "CLOCK_PERIOD": 8.0,  # ns
            "CORE_UTILIZATION": 50,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY_LB_ADDON": 0.15,
            "TNS_END_PERCENT": 100,
            "ABC_AREA": 1,
            "REMOVE_ABC_BUFFERS": 1
        },
        "ibex": {
            "CLOCK_PERIOD": 10.0,  # ns
            "CORE_UTILIZATION": 45,
            "CORE_ASPECT_RATIO": 1,
            "CORE_MARGIN": 2,
            "PLACE_DENSITY_LB_ADDON": 0.2,
            "TNS_END_PERCENT": 100,
            "REMOVE_ABC_BUFFERS": 1
        }
    }
}

default_parameter_guideline = """When optimizing parameters, consider these guidelines for working with defaults:

1. Default parameters represent stable, tested configurations - use them as anchoring points
2. For initial exploration, limit parameter changes to ±30% from defaults unless there's strong justification
3. When deviating from defaults:
   - Document the rationale clearly
   - Test changes incrementally rather than making large jumps
   - Monitor impact carefully, especially on metrics not being directly optimized
4. Some parameters are more sensitive to changes than others:
   - CLOCK_PERIOD: Stay within ±20% initially
   - CORE_UTILIZATION: Changes of more than ±15% can significantly impact results
   - Density parameters: Small changes (±0.1) can have large effects
5. Consider interactions between parameters:
   - Changing multiple defaults simultaneously increases risk
   - Some parameters have compensating effects (e.g., utilization vs density)
6. Return to defaults if optimizations don't show clear improvements
7. Maintain a "control" run with defaults for comparison"""


import openai
import os
from typing import Dict, Any

def get_optimization_data(pdk: str, circuit: str, goal: str, use_surrogate: bool = False) -> Dict[str, Any]:
    """
    Gather optimization-related data to be passed to GPT for prompt generation.
    
    Args:
        pdk (str): PDK name ('asap7' or 'sky130')
        circuit (str): Design name ('aes', 'jpeg', 'ibex')
        goal (str): Primary optimization goal ('DWL', 'ECP', 'COMBO')
        use_surrogate (bool): Whether to use CTS metrics as surrogate
        
    Returns:
        dict: Structured data for GPT prompt generation
    """
    valid_goals = ['DWL', 'ECP', 'COMBO']
    if goal not in valid_goals:
        raise ValueError(f"Goal must be one of {valid_goals}")
        
    data = {
        'pdk': {
            'name': pdk,
            'description': asap7_pdk_description if pdk == 'asap7' else sky130_pdk_description
        },
        'circuit': circuit,
        'optimization': {
            'primary_goal': goal,
            'use_surrogate': use_surrogate,
            'guidelines': eda_guidelines[pdk][circuit][goal],
            'cts_guidelines': eda_guidelines[pdk][circuit]['CTS'] if use_surrogate else None
        },
        'defaults': {
            'parameters': default_parameter_guideline,
            'config': eda_guidelines[pdk][circuit]
        },
        'expert_context': eda_expert_prompt
    }
    
    return data
def get_optimization_prompt(pdk: str, circuit: str, goal: str, use_surrogate: bool = False) -> str:
    """
    Generate optimization prompt using GPT based on provided parameters.
    
    Args:
        pdk (str): PDK name ('asap7' or 'sky130')
        circuit (str): Design name ('aes', 'jpeg', 'ibex')
        goal (str): Primary optimization goal ('DWL', 'ECP', 'COMBO')
        use_surrogate (bool): Whether to use CTS metrics as surrogate
        
    Returns:
        str: Generated optimization prompt
    """
    data = get_optimization_data(pdk, circuit, goal, use_surrogate)
    
    system_message = """You are an expert EDA optimization system. Generate a concise prompt 
    for a Bayesian optimization agent working with OpenROAD. The prompt should incorporate the 
    provided PDK details, circuit specifications, optimization goals, and guidelines."""
    if goal == "COMBO":
        system_message += """ For this COMBO optimization, the objective is specifically to 
    minimize the fractional sum (DWL/DWL_orig + ECP/ECP_orig) where DWL and ECP are the 
    current detailed wire length and effective clock period values, and DWL_orig and ECP_orig 
    are their original baseline values."""
    
    system_message += """ Make sure to return a response that is a valid prompt, i.e. it 
    should use the second person, and not the first person."""
    
    try:
        openai_key = #PUT YOUR KEY HERE
        if not openai_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
            
        client = openai.OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model="o1-preview",
            messages=[
                {"role": "user", "content": system_message + "\n\n" + str(data)}
            ],
            temperature=1,
            max_completion_tokens=5000
        )
        print(response)
        return response.choices[0].message.content
    except Exception as e:
        raise Exception(f"Failed to generate optimization prompt: {str(e)}")

if __name__ == "__main__":
    # Example usage showing prompt generation via GPT
    try:
        prompt = get_optimization_prompt('asap7', 'ibex', 'COMBO', use_surrogate=True)
        print("Generated Optimization Prompt:")
        print(prompt)
    except Exception as e:
        print(f"Error: {str(e)}")