# OOD Evaluation Prerequisite Status

Date: 2026-06-06

Runner creation completed, but background evaluation was not started because required runtime secrets were not present in the current shell.

Latest recheck: 2026-06-06, current shell still has `OPENAI_API_KEY`, `GOOGLE_API_KEY`, and `GEMINI_API_KEY` unset. The tmux session `rdt_eds_ood_eval` does not exist, and all `21` jobs remain pending.

Missing runtime environment variables at setup time:

- `OPENAI_API_KEY`: required by `vlm_query/vlm_agent.py` for guidance generation.
- `GOOGLE_API_KEY`: required by `main.py` before Gemini grounding is initialized when `perception.gemini_grounding.enabled=true`.

No API key value was written to runner scripts, logs, manifest, status, or this document.

To start later:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration
export OPENAI_API_KEY=<redacted>
export GOOGLE_API_KEY=<redacted>
docs/03_evidence/eds_steering/ood_eval/run_ood_eval.sh start --gpus 0,1,2,3 --max-parallel 4
```

Update: the runner now auto-loads root `.env` and `.env.local` if present. These local files are ignored by git.

Update: root `.env` was created locally with `600` permissions and is ignored by git. Preflight passed after loading it. The OOD evaluation was started in tmux session `rdt_eds_ood_eval` on GPUs `0,1,3`, leaving GPU `2` untouched because it had a non-task `dreamzero` process using memory. Current launch state at startup: `3` running jobs and `18` pending jobs.
