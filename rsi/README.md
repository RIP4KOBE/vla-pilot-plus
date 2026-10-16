# Agentic recursive self-improvement

This is the **development and validation branch** for the RSI prototype contributed in [PR #2](https://github.com/RIP4KOBE/vla-pilot-plus/pull/2). It is not an accepted RDT+EDS+QD implementation or a new performance result. See the [integration review](../docs/steering/rsi-integration-review.md) for validation and missing assets.

The accepted steering entrypoints remain `scripts/run_steering.py`, `scripts/evaluate_steering.py` and `scripts/run_pi05.py`. RSI uses **`python -m rsi.main`** and the separate `scripts/self_improve.py` / `scripts/run_full_experiment.py` tools. Run from the repository root.

## Architecture and scope

The prototype primarily targets π0.5: generate candidate trajectories, assess execution and failure, choose RE-STEER or EXPANSION with a learned verifier, collect demonstrations, train an updated policy, compose checkpoint deltas, evaluate gains/forgetting and maintain deployment lineage. `mode_gate/` owns the orchestration; `baseline/` contains separate continual-learning comparison implementations and historical reports.

`rsi/core/`, `rsi/vlm_query/`, `rsi/utils/` and `rsi/configs/` preserve the PR's distinct runtime contracts. This deliberate isolation prevents old Stage parsing, FKD numerical changes, checkpoint loading and server defaults from replacing the accepted main implementation. Shared code may be factored later with explicit behavioral regression. [integration.json](integration.json) records the source commits, relocations and protected main hashes.

The committed campaign is **20 LIBERO-PRO environment/position cells**, with `planner_steering_enabled=false`, first-safe-particle selection and a learned failure verifier. Earlier PR documentation also describes a 40-cell protocol and semantic mode selection. These are different configurations. None is the main RDT ObjectSwap ten-task evaluation.

## Development environment

Use a separate Python environment, with the [main installation dependencies](../docs/steering/installation.md). Do not upgrade LeRobot inside an environment used for the accepted EDS control. Then install:

```bash
python -m pip install -r rsi/requirements-dev.txt
mkdir -p .local/rsi-deps
git clone https://github.com/Treeeplanter/lerobot.git .local/rsi-deps/lerobot
git -C .local/rsi-deps/lerobot checkout --detach 910e5c6e4b22ae2c5173373133899a5e287ac322
python -m pip install --no-deps -e .local/rsi-deps/lerobot
python -c 'import lerobot; from lerobot.configs.train import TrainPipelineConfig; print(lerobot.__file__); assert "freeze_pretrained_processor_stats" in TrainPipelineConfig.__dataclass_fields__'
```

This dependency adds frozen preprocessing statistics, training schedule controls and deterministic resume. Main's `third_party/lerobot` remains unchanged. `rsi/environment.yml` and `rsi/requirements.txt` are historical dependency snapshots, **not portable installation recipes**; they contain old server-specific entries.

The integration check used a new venv inheriting the existing validated steering environment, added the three development packages and installed the pinned LeRobot source in that venv. This is an isolated compatibility check, not a fresh public installation or training acceptance.

## CPU validation

```bash
python scripts/self_improve.py --help
python scripts/run_full_experiment.py --help
python -m rsi.main --cfg job
env -u PYTHONPATH -u VLA_CODEX_ONLY CUDA_VISIBLE_DEVICES='' \
  PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 \
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python -m pytest rsi/tests baseline/tests --import-mode=importlib \
  -q -rs -p no:cacheprovider
```

The preview loads no model and starts no rollout. Tests inject Planner clients; HTTP/WebSocket checks use localhost. A sandbox that blocks sockets or cross-thread asyncio wakeups cannot run those checks. Asset-dependent tests explicitly skip missing historical files, report why, and keep their original assertions when the assets are present. Skips do not establish end-to-end readiness.

Run `python -m pytest tests -q -p no:cacheprovider` in the original steering environment for the accepted main regression suite. Do not use an RSI environment's changed LeRobot to claim a new EDS result.

## Before any online campaign

1. Supply a registered task manifest, state splits, baseline configuration/chunk evidence, demonstration bank, pretrained policy, verifier checkpoint and fresh output/registry paths. The historical `/shared/hengyil6/...` and `/root/...` locations in the PR are not local assets or defaults suitable for a new run.
2. Copy `configs/candidate_experiment.json` and `configs/planner_account.json` to ignored `.local/` files, fix all paths and identifiers, then select them explicitly:

   ```bash
   export VLA_RSI_CAMPAIGN_CONFIG="$PWD/.local/rsi-campaign.json"
   export VLA_RSI_PLANNER_CONFIG="$PWD/.local/rsi-planner.json"
   ```

3. The inherited Codex planner writes requests to a file queue and waits for an independently running account Planner. **It does not start a worker or reuse main's Codex CLI transport automatically.** Never use the historical thread ID as a new worker identity. Reward generation still contains a separate OpenAI SDK path; it has not been unified with the current Codex-only steering contract.
4. Reconcile the campaign protocol and provider contract before launch. Keep models, prompts, budgets, native success and held-out evaluation rules explicit. Old reports and initialization data are not new held-out results.
5. Run the full RSI preflight and staged simulator/training checks after provisioning. Only then start a registered campaign on available GPUs. Do not start the old experiment or resume its queue by copying its commands.

The branch establishes a reviewed code starting point. Online RSI performance, new checkpoint training, deployment promotion and integration of QD with RSI remain unverified.
