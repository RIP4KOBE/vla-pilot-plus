# RDT EDS OOD Evaluation Runner

This directory contains the resumable runner for LIBERO OOD evaluation requested on 2026-06-06.

The runner auto-loads root `.env` and `.env.local` if present. These files are ignored by git in this worktree. You can either put local keys there or export keys in the shell before starting:

```bash
export OPENAI_API_KEY=<redacted>
export GOOGLE_API_KEY=<redacted>
```

`GOOGLE_API_KEY` is required because this evaluation explicitly enables `perception.gemini_grounding.enabled=true`. If the same Poe/OpenAI-compatible key is used for Gemini in your deployment, export it as `GOOGLE_API_KEY` for this run.

Start in tmux:

```bash
cd /home/hynx/VLA-Pilot++/.worktrees/feat/rdt_ed_steering_integration
docs/03_evidence/eds_steering/ood_eval/run_ood_eval.sh start --gpus 0,1,2,3 --max-parallel 4
```

Monitor:

```bash
tmux attach -t rdt_eds_ood_eval
tail -f docs/03_evidence/eds_steering/ood_eval/job_status.csv
tail -f docs/03_evidence/eds_steering/ood_eval/logs/<job_id>.log
```
