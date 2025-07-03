set_global_routing_layer_adjustment met1-met2 $::env(PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment met3-$::env(MAX_ROUTING_LAYER) $::env(ABOVE_LAYER_ADJUST)

set_routing_layers -clock $::env(MIN_CLK_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER) 
