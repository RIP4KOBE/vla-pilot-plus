#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

export LIBERO_CONFIG_PATH="${ROOT}/.libero_config"
export PYTHONPATH="${ROOT}/third_party/libero_pro:${PYTHONPATH:-}"
export OPENAI_BASE_URL="${OPENAI_BASE_URL:-https://api.poe.com/v1}"
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export TOKENIZERS_PARALLELISM=false
export TORCHDYNAMO_DISABLE=1

CMD="${1:-run}"
shift || true

case "$CMD" in
  preflight)
    conda run -n vla-pilot python scripts/vls_pi05_ood_eval_runner.py preflight "$@"
    ;;
  init)
    conda run -n vla-pilot python scripts/vls_pi05_ood_eval_runner.py init --episodes 10 "$@"
    ;;
  run)
    conda run -n vla-pilot python scripts/vls_pi05_ood_eval_runner.py run \
      --episodes 10 \
      --gpus "${GPUS:-2,3}" \
      --timeout-seconds "${TIMEOUT_SECONDS:-21600}" \
      --resume \
      "$@"
    ;;
  report)
    conda run -n vla-pilot python scripts/vls_pi05_ood_eval_runner.py write-report --episodes 10 "$@"
    ;;
  audit)
    conda run -n vla-pilot python scripts/vls_pi05_ood_eval_runner.py audit --episodes 10 "$@"
    ;;
  *)
    echo "Usage: $0 {preflight|init|run|report|audit}" >&2
    exit 2
    ;;
esac
