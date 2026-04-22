#!/usr/bin/env bash
# VLA-Pilot++ Runner
#
# Usage:
#   bash run.sh                          # LIBERO (default)
#   bash run.sh libero                   # LIBERO with default suite (libero_goal)
#   bash run.sh libero libero_spatial    # LIBERO specific suite
#   bash run.sh calvin                   # CALVIN with default task (drawer_open)
#   bash run.sh calvin light_on          # CALVIN specific task
#
# Extra Hydra overrides can be appended:
#   bash run.sh libero libero_goal main.episode_num=5 main.use_guidance=true

set -e
cd "$(dirname "$0")"

export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

eval "$(conda shell.bash hook)"
conda activate vla-pilot

BACKEND="${1:-libero}"
shift 2>/dev/null || true  # consume first arg if present

case "$BACKEND" in
    libero)
        SUITE="${1:-libero_goal}"
        shift 2>/dev/null || true
        echo "=== Running LIBERO | suite: $SUITE ==="
        python main.py \
            backend=libero \
            backend.libero.suite_name="$SUITE" \
            "$@"
        ;;
    calvin)
        TASK="${1:-drawer_open}"
        shift 2>/dev/null || true
        echo "=== Running CALVIN | task: $TASK ==="
        python main.py \
            backend=calvin \
            policy=diffusion \
            backend.calvin.target_behavior="$TASK" \
            "$@"
        ;;
    *)
        echo "Unknown backend: $BACKEND"
        echo "Usage: bash run.sh [libero|calvin] [suite/task] [hydra_overrides...]"
        exit 1
        ;;
esac
