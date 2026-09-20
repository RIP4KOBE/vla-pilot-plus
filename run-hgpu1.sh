#!/usr/bin/env bash
set -Eeuo pipefail

source /root/.config/vls/env.sh
cd "$VLS_REPO_ROOT"

exec python main.py \
    policy.pi05.pretrained_path="$PI05_CHECKPOINT_PATH" \
    policy.pi05.tokenizer_path="$PALIGEMMA_TOKENIZER_PATH" \
    "$@"
