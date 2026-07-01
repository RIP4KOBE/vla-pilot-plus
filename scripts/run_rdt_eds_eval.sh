#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNER="${SCRIPT_DIR}/rdt_eds_eval_runner.py"
SESSION="${RDT_EDS_EVAL_TMUX_SESSION:-rdt_eds_eval}"
LIBERO_PRO_ROOT="${WORKTREE_ROOT}/third_party/libero_pro"
LIBERO_CONFIG_PATH_LOCAL="${WORKTREE_ROOT}/.libero_config"

load_local_env() {
  local env_file
  for env_file in "${WORKTREE_ROOT}/.env" "${WORKTREE_ROOT}/.env.local"; do
    if [[ -f "${env_file}" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "${env_file}"
      set +a
    fi
  done
}

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_rdt_eds_eval.sh preflight
  scripts/run_rdt_eds_eval.sh init --level level2 --episodes 3
  scripts/run_rdt_eds_eval.sh init --level level3 --episodes 10
  scripts/run_rdt_eds_eval.sh start --level level2 --episodes 3 --gpus 0,1 --timeout-seconds 28800
  scripts/run_rdt_eds_eval.sh start --level level3 --episodes 10 --gpus 0,1 --timeout-seconds 28800
  scripts/run_rdt_eds_eval.sh start --level level4 --episodes 10 --gpus 0,1,2,3 --timeout-seconds 86400 --resume
  scripts/run_rdt_eds_eval.sh write-level4-report --episodes 10
  scripts/run_rdt_eds_eval.sh attach
  scripts/run_rdt_eds_eval.sh help
USAGE
}

require_keys() {
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "BLOCKED: OPENAI_API_KEY missing" >&2
    exit 2
  fi
  if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
    echo "BLOCKED: GOOGLE_API_KEY missing" >&2
    exit 2
  fi
}

load_local_env
cmd="${1:-help}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "${cmd}" in
  preflight)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" preflight
    ;;
  init)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" init "$@"
    ;;
  write-level4-report)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" write-level4-report "$@"
    ;;
  start)
    require_keys
    level="level3"
    episodes="10"
    gpus="0"
    timeout_seconds="28800"
    resume_flag=""
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --level)
          level="$2"
          shift 2
          ;;
        --episodes)
          episodes="$2"
          shift 2
          ;;
        --gpus)
          gpus="$2"
          shift 2
          ;;
        --timeout-seconds)
          timeout_seconds="$2"
          shift 2
          ;;
        --resume)
          resume_flag="--resume"
          shift
          ;;
        -h|--help)
          usage
          exit 0
          ;;
        *)
          echo "Unknown argument: $1" >&2
          usage
          exit 2
          ;;
      esac
    done
    cd "${WORKTREE_ROOT}"
    if tmux has-session -t "${SESSION}" 2>/dev/null; then
      echo "tmux session already exists: ${SESSION}"
      echo "Attach: tmux attach -t ${SESSION}"
      exit 0
    fi
    tmux new-session -d -s "${SESSION}" -c "${WORKTREE_ROOT}"
    tmux set-environment -t "${SESSION}" OPENAI_API_KEY "${OPENAI_API_KEY}"
    tmux set-environment -t "${SESSION}" GOOGLE_API_KEY "${GOOGLE_API_KEY}"
    tmux set-environment -t "${SESSION}" GEMINI_API_KEY "${GEMINI_API_KEY:-${GOOGLE_API_KEY}}"
    tmux set-environment -t "${SESSION}" OPENAI_BASE_URL "${OPENAI_BASE_URL:-https://api.poe.com/v1}"
    tmux set-environment -t "${SESSION}" LIBERO_CONFIG_PATH "${LIBERO_CONFIG_PATH_LOCAL}"
    tmux set-environment -t "${SESSION}" PYTHONPATH "${LIBERO_PRO_ROOT}:${PYTHONPATH:-}"
    tmux send-keys -t "${SESSION}" "cd '${WORKTREE_ROOT}' && conda run -n vla-pilot python '${RUNNER}' run-level --level '${level}' --episodes '${episodes}' --gpus '${gpus}' --timeout-seconds '${timeout_seconds}' ${resume_flag}" C-m
    echo "Started tmux session: ${SESSION}"
    echo "Attach: tmux attach -t ${SESSION}"
    ;;
  attach)
    tmux attach -t "${SESSION}"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Unknown command: ${cmd}" >&2
    usage
    exit 2
    ;;
esac
