set_global_routing_layer_adjustment metal2-metal3 $::env(PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment metal4-$::env(MAX_ROUTING_LAYER) $::env(UP_LAYER_ADJUST)

set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
