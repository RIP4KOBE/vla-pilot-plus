#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKTREE_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
RUNNER="${SCRIPT_DIR}/ood_eval_runner.py"
SESSION="${OOD_TMUX_SESSION:-rdt_eds_ood_eval}"
GPU_LIST="${OOD_GPU_LIST:-0,1,2,3}"
MAX_PARALLEL="${OOD_MAX_PARALLEL:-}"
TIMEOUT_SECONDS="${OOD_JOB_TIMEOUT_SECONDS:-28800}"

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
  run_ood_eval.sh init
  run_ood_eval.sh preflight
  run_ood_eval.sh status
  run_ood_eval.sh report
  run_ood_eval.sh verify
  run_ood_eval.sh run [--gpus 0,1,2,3] [--max-parallel N] [--timeout-seconds S]
  run_ood_eval.sh start [--gpus 0,1,2,3] [--max-parallel N] [--timeout-seconds S]
  run_ood_eval.sh attach
  run_ood_eval.sh tail [job_id]

Environment:
  OPENAI_API_KEY is required for VLM guidance generation.
  GOOGLE_API_KEY is required because perception.gemini_grounding.enabled=true is requested.
  If you only have GEMINI_API_KEY, export GOOGLE_API_KEY="$GEMINI_API_KEY" before start/run.
USAGE
}

require_keys() {
  local missing=0
  if [[ -z "${OPENAI_API_KEY:-}" ]]; then
    echo "BLOCKED: OPENAI_API_KEY is missing. Export OPENAI_API_KEY=<redacted> and rerun." >&2
    missing=1
  fi
  if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
    echo "BLOCKED: GOOGLE_API_KEY is missing. Gemini grounding is enabled; export GOOGLE_API_KEY=<redacted> and rerun." >&2
    missing=1
  fi
  return "${missing}"
}

parse_run_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --gpus)
        GPU_LIST="$2"; shift 2 ;;
      --max-parallel)
        MAX_PARALLEL="$2"; shift 2 ;;
      --timeout-seconds)
        TIMEOUT_SECONDS="$2"; shift 2 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 2 ;;
    esac
  done
  if [[ -z "${MAX_PARALLEL}" ]]; then
    IFS=',' read -r -a _gpus <<< "${GPU_LIST}"
    MAX_PARALLEL="${#_gpus[@]}"
  fi
}

cmd="${1:-}"
shift || true
load_local_env

case "${cmd}" in
  init)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" init
    ;;
  preflight)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" preflight
    ;;
  status)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" status
    ;;
  report)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" report
    ;;
  verify)
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" verify
    ;;
  run)
    parse_run_args "$@"
    require_keys
    cd "${WORKTREE_ROOT}"
    export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.poe.com/v1}"
    conda run -n vla-pilot python "${RUNNER}" run \
      --gpus "${GPU_LIST}" \
      --max-parallel "${MAX_PARALLEL}" \
      --timeout-seconds "${TIMEOUT_SECONDS}"
    ;;
  start)
    parse_run_args "$@"
    require_keys
    cd "${WORKTREE_ROOT}"
    conda run -n vla-pilot python "${RUNNER}" init
    if tmux has-session -t "${SESSION}" 2>/dev/null; then
      echo "tmux session already exists: ${SESSION}"
      exit 0
    fi
    tmux new-session -d -s "${SESSION}" -c "${WORKTREE_ROOT}"
    tmux set-environment -t "${SESSION}" OPENAI_API_KEY "${OPENAI_API_KEY}"
    tmux set-environment -t "${SESSION}" GOOGLE_API_KEY "${GOOGLE_API_KEY}"
    tmux set-environment -t "${SESSION}" OPENAI_BASE_URL "${OPENAI_BASE_URL:-https://api.poe.com/v1}"
    tmux set-environment -t "${SESSION}" OOD_GPU_LIST "${GPU_LIST}"
    tmux set-environment -t "${SESSION}" OOD_MAX_PARALLEL "${MAX_PARALLEL}"
    tmux set-environment -t "${SESSION}" OOD_JOB_TIMEOUT_SECONDS "${TIMEOUT_SECONDS}"
    tmux send-keys -t "${SESSION}" "cd '${WORKTREE_ROOT}' && '${SCRIPT_DIR}/run_ood_eval.sh' run --gpus '${GPU_LIST}' --max-parallel '${MAX_PARALLEL}' --timeout-seconds '${TIMEOUT_SECONDS}'" C-m
    echo "Started tmux session: ${SESSION}"
    echo "Attach: tmux attach -t ${SESSION}"
    ;;
  attach)
    tmux attach -t "${SESSION}"
    ;;
  tail)
    if [[ $# -gt 0 ]]; then
      tail -f "${SCRIPT_DIR}/logs/$1.log"
    else
      tail -f "${SCRIPT_DIR}/job_status.csv"
    fi
    ;;
  ""|-h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: ${cmd}" >&2
    usage
    exit 2
    ;;
esac
