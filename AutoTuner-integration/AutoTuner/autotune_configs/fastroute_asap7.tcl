set_global_routing_layer_adjustment M2-M3 $::env(PIN_LAYER_ADJUST)
set_global_routing_layer_adjustment M4-$::env(MAX_ROUTING_LAYER) $::env(UP_LAYER_ADJUST)

set_routing_layers -signal $::env(MIN_ROUTING_LAYER)-$::env(MAX_ROUTING_LAYER)
