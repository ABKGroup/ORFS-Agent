#!/bin/bash
## Run AES on ASAP7
design="aes" # 1
clk_perio="400" # 2
core_utilization="40" # 3
core_aspect_ratio="1" # 4
tech="asap7" # 5
place_density_lb_addon="0.39" # 6
tns_end_percent="100" # 7
recover_power="0" # 8
synth_hierarchical="0" # 9
gp_pad="0" # 10
dp_pad="0" # 11
enable_dpo="1" # 12
gp_td="1" # 13
gp_rd="1" # 14
cts_cluster_size="1" # 15
cts_cluster_diameter="1" # 16
pin_layer_adjust="0.5" # 17
up_layer_adjust="0.5" # 18
work_homw="." # 19
./run_or_job.sh $design $clk_perio $core_utilization $core_aspect_ratio $tech \
                $place_density_lb_addon $tns_end_percent $recover_power \
                $synth_hierarchical $gp_pad $dp_pad $enable_dpo $gp_td $gp_rd \
                $cts_cluster_size $cts_cluster_diameter $pin_layer_adjust \
                $up_layer_adjust $work_homw