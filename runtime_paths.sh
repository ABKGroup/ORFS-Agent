#!/bin/bash

orfs_agent__has_flow_tree() {
    local root=$1
    [[ -d "$root/designs" && -d "$root/platforms" && -d "$root/scripts" ]]
}

orfs_agent_resolve_flow_home() {
    local script_dir=$1
    local current

    if [[ -n "${FLOW_HOME:-}" ]] && orfs_agent__has_flow_tree "$FLOW_HOME"; then
        printf '%s\n' "$FLOW_HOME"
        return 0
    fi

    current=$script_dir
    while true; do
        if orfs_agent__has_flow_tree "$current"; then
            printf '%s\n' "$current"
            return 0
        fi
        if orfs_agent__has_flow_tree "$current/flow"; then
            printf '%s\n' "$current/flow"
            return 0
        fi
        if [[ "$current" == "/" ]]; then
            break
        fi
        current=$(dirname "$current")
    done

    printf '%s\n' "$script_dir"
}

orfs_agent_prepare_layout() {
    local script_dir=$1
    local flow_home
    local name
    local target
    local link

    flow_home=$(orfs_agent_resolve_flow_home "$script_dir")
    export FLOW_HOME="$flow_home"
    export DESIGN_HOME="${FLOW_HOME}/designs"
    export PLATFORM_HOME="${FLOW_HOME}/platforms"
    export ORFS_AGENT_DESIGNS_ROOT="${FLOW_HOME}/designs"

    for name in designs platforms scripts util test; do
        target="${FLOW_HOME}/${name}"
        link="${script_dir}/${name}"
        if [[ ! -e "$target" ]]; then
            continue
        fi
        if [[ -L "$link" && ! -e "$link" ]]; then
            rm -f "$link"
        fi
        if [[ -e "$link" || -L "$link" ]]; then
            continue
        fi
        ln -s "$target" "$link"
    done
}
