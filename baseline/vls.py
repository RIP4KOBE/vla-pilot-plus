"""Frozen v44 + native VLS, with paired episodes and independent output ownership.

The four training campaigns do not import this evaluator. One CPU supervisor
holds one baseline GPU lock and runs a fresh VLS process for each context.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

from .config import cpu_environment
from .experiment import task_order
from .io import append_json, digest, read_json, safe_output, write_json
from .protocol import Protocol
from .scope import scope_identity
from .vls_provider import PROVIDER, REFERENCE, REWARD_MODEL, SOURCE_COMMIT, STAGE_MODEL

PROJECT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def load_settings(path):
    cfg = read_json(path)
    if cfg.get("method") != "v44_vls" or cfg.get("schema_version") != "v44-vls-baseline-v2":
        raise ValueError("expected the independent frozen-v44 VLS configuration")
    if cfg.get("split") != "fixed_development_probe":
        raise ValueError("this evaluator only exposes fixed development probes")
    if 6 not in cfg["protected_gpu_indices"] or cfg["device"] != "cuda:0":
        raise ValueError("GPU6 must remain protected; use one explicit CUDA device")
    if (cfg.get("provider"), cfg.get("official_source_commit"), cfg["stage_model"], cfg["reward_model"]) != (
            PROVIDER, SOURCE_COMMIT, STAGE_MODEL, REWARD_MODEL):
        raise ValueError("use the pinned official VLS API models; task planners are not supported")
    if "stage_reasoning" in cfg or cfg["provider_timeout_ms"] <= 0:
        raise ValueError("use official generation defaults and a bounded API timeout")
    if cfg["sample_count"] < 1 or cfg["stage_query_limit"] < 1:
        raise ValueError("invalid VLS inference budget")
    return cfg


def build_runtime_config(cfg, context, output):
    """Override all live destinations; no production registry or data is loaded."""
    output = Path(output).resolve()
    runtime = deepcopy(read_json(cfg["runtime_template"]))
    runtime.update(device=cfg["device"], seed=context["seed"])
    runtime["backend"] = {"backend": "libero", "libero": {
        **runtime["backend"]["libero"],
        "suite_name": context["runtime_suite"], "task_id": context["task_index"],
        "task_ids_filter": [context["task_index"]], "episode_num": 1,
        "auto_apply_perturbations": False, "auto_reset": False, "init_states": True,
        "max_episode_steps": cfg["max_episode_steps"], "num_steps_wait": cfg["num_steps_wait"],
        "observation_width": cfg["observation_width"], "observation_height": cfg["observation_height"],
        "render_gpu_device_id": cfg["render_gpu_device_id"],
    }}
    runtime["policy"] = {"type": "pi05", "pi05": {
        "pretrained_path": cfg["checkpoint"], "tokenizer_path": cfg["tokenizer"],
        "num_inference_steps": cfg["inference_steps"], "action_chunk_horizon": cfg["execution_horizon"],
    }}
    runtime["main"].update(
        episode_num=1, output_dir=str(output), env_seed=context["seed"],
        policy_seed=context.get("policy_seed", context["seed"]), init_state_id=context["init_state_id"],
        max_episode_steps=cfg["max_episode_steps"], use_guidance=True, use_vlm_stage_recognition=True,
        cached_functions_dir=None, fail_on_episode_error=True, sample_batch_size=cfg["sample_count"],
        vlm_query_limit=cfg["stage_query_limit"], debug_draw_trajectory=False,
    )
    runtime["mode_gate"] = {
        "enabled": False, "auto_start_expansion_worker": False,
        "theta0_checkpoint": cfg["checkpoint"],
        **{key: str(output / "disabled_learning" / key) for key in (
            "registry_root", "incident_root", "snapshot_root", "slow_loop_root")},
    }
    perception = runtime["perception"]
    perception["keypoint_detector"]["device"] = cfg["device"]
    # Replace inherited provider settings completely, including account/ledger paths.
    perception["gemini_grounding"] = {"enabled": False, "model": cfg["stage_model"]}
    perception["gemini"] = {
        "model": cfg["stage_model"], "api_key": None,
        "timeout_ms": cfg["provider_timeout_ms"], "max_provider_calls": cfg["stage_query_limit"],
        "call_ledger_path": str(output / "stage_provider_calls.jsonl"),
        "stage_template_path": str(REFERENCE / "vlm_query/stage_template.txt"),
    }
    perception["vlm_agent"] = {
        "model": cfg["reward_model"], "api_key": None, "base_url": None,
        "temperature": 1.0, "max_completion_tokens": 2000, "timeout_ms": cfg["provider_timeout_ms"],
        "query_template_dir": str(REFERENCE / "vlm_query"),
    }
    return runtime


def verify_engine(cfg):
    recorded = read_json(cfg["engine_manifest"])["files"]
    changed = [name for name, sha in recorded.items() if digest(PROJECT / name) != sha]
    if changed:
        raise ValueError(f"VLS engine changed after registration: {changed}")
    return recorded


def read_rows(path):
    import json
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def verified_reference(cfg, protocol, contexts, *, hash_assets=False):
    root = Path(cfg["reference_run"])
    summary = read_json(root / "summary.json")
    rows = read_rows(root / "episodes.jsonl")
    if (summary["method"] != "pi05_v44" or summary["artifact"] is not None
            or summary["split"] != cfg["split"] or summary["protocol_sha256"] != protocol.digest
            or summary["experiment_scope"] != scope_identity(cfg)
            or [r["context"] for r in rows] != contexts):
        raise ValueError("raw v44 reference is not the exact paired development evaluation")
    if Path(cfg["checkpoint"]).resolve() != Path(summary["base"]["checkpoint"]).resolve():
        raise ValueError("checkpoint differs from raw v44 reference")
    if hash_assets:
        for name, expected in summary["base"]["files"].items():
            if digest(Path(cfg["checkpoint"]) / name) != expected:
                raise ValueError(f"v44 asset changed: {name}")
        for name, expected in summary["base"]["tokenizer_files"].items():
            if digest(Path(cfg["tokenizer"]) / name) != expected:
                raise ValueError(f"v44 tokenizer changed: {name}")
    return summary, rows


def summarize(rows, cfg, protocol, reference, paired_rows, total):
    if [r["context"] for r in rows] != [r["context"] for r in paired_rows[:len(rows)]]:
        raise ValueError("episode results are not a unique ordered prefix of the reference")
    if any(r.get("valid") is not True for r in rows):
        raise ValueError("aborted/invalid episodes cannot be scored as failures")
    per_task, per_variant = defaultdict(list), defaultdict(list)
    for row in rows:
        per_task[row["context"]["task_key"]].append(int(row["success"]))
        per_variant[row["context"]["perturbation_variant"]].append(int(row["success"]))
    rates = {k: sum(v) / len(v) for k, v in per_task.items()}
    comparisons = defaultdict(int)
    for row, raw in zip(rows, paired_rows):
        comparisons[f"v44_{int(raw['success'])}_vls_{int(row['success'])}"] += 1
    return {
        "schema_version": "baseline-evaluation-v1", "method": "v44_vls", "artifact": None,
        "provider": cfg["provider"], "official_source_commit": cfg["official_source_commit"],
        "reward_model": cfg["reward_model"], "stage_model": cfg["stage_model"],
        "base": reference["base"], "protocol_sha256": protocol.digest, "experiment_scope": scope_identity(cfg),
        "split": cfg["split"], "metric_role": "development_heldout", "seed": cfg["seed"],
        "episodes": len(rows), "episodes_planned": total, "successes": sum(r["success"] for r in rows),
        "micro_success": sum(r["success"] for r in rows) / len(rows) if rows else None,
        "macro_success": sum(rates.values()) / len(rates) if rates else None,
        "per_task_success": rates,
        "per_variant": {k: {"successes": sum(v), "episodes": len(v), "success_rate": sum(v) / len(v)}
                        for k, v in per_variant.items()},
        "environment_steps": sum(r["steps"] for r in rows), "seconds": sum(r["seconds"] for r in rows),
        "interventions": sum(r["interventions"] for r in rows),
        "stage_queries": sum(r["stage_queries"] for r in rows), "paired_outcomes": dict(comparisons),
        "partial_development_check": len(rows) != total, "updated_at": now(),
    }


def execute_episode(config_path, output):
    cfg = load_settings(config_path)
    output = Path(output).resolve()
    context = read_json(output / "context.json")
    verify_engine(cfg)
    # The supervisor owns the GPU lock; children inherit its single UUID.
    gpu = read_json(output.parent / "gpu.json")
    if (gpu["index"] in cfg["protected_gpu_indices"]
            or os.environ.get("CUDA_VISIBLE_DEVICES") != gpu["uuid"]):
        raise ValueError("episode CUDA device differs from the protected supervisor allocation")
    protocol = Protocol(cfg["protocol"])
    if context not in protocol.contexts(cfg["split"], cfg["seed"], task_order(cfg, protocol)):
        raise ValueError("episode is outside the frozen development contexts")
    runtime_cfg = build_runtime_config(cfg, context, output)
    write_json(output / "config.json", runtime_cfg)
    start = time.monotonic()
    progress = {"status": "running", "phase": "initializing", "steps": 0, "chunks": 0,
                "interventions": 0, "stage_queries": 0, "pid": os.getpid(), "context": context}

    def report(**values):
        progress.update(values, updated_at=now())
        write_json(output / "status.json", progress)

    report()
    app = None
    try:
        from omegaconf import OmegaConf
        from dotenv import load_dotenv
        from .vls_provider import VLSGeminiStageRecognizer, official_engine_factories
        load_dotenv(PROJECT / ".env")
        import main as engine
        from .environment import reset_environment, simulator_status
        from .io import seed_all
        seed_all(context["seed"])
        with official_engine_factories(engine):
            app = engine.Main(OmegaConf.create(runtime_cfg))
        if app.mode_aware_runtime is not None or app.mode_gate_controller is not None:
            raise RuntimeError("frozen VLS must not initialize the self-improvement runtime")
        recognizer = app.gemini_stage_recognizer
        if not isinstance(recognizer, VLSGeminiStageRecognizer):
            raise RuntimeError("official Gemini API stage recognizer unavailable; no provider fallback")
        if app.vlm_agent.config["model"] != REWARD_MODEL:
            raise RuntimeError("reward generator is not the pinned official VLS model")
        write_json(output / "provider_identity.json", {
            "provider": PROVIDER, "official_source_commit": SOURCE_COMMIT,
            "stage_model": recognizer.model, "stage_transport": "google_genai.generate_content",
            "reward_model": app.vlm_agent.config["model"], "reward_transport": "openai.chat.completions",
            "credentials_source": ".env", "task_dependency": None,
        })
        app.policy.eval().requires_grad_(False)
        versions = {n: p._version for n, p in app.policy.named_parameters()}
        app.success_count = 0
        app.policy.reset()
        app.video_recorder.clear()
        provenance = reset_environment(app.adapter, context)
        write_json(output / "environment.json", provenance)
        report(phase="guidance_preparation")
        app.perform_task_for_episode(str(output))
        if not app.guidance_fns or not any(app.guidance_fns.values()):
            raise RuntimeError("VLS produced no guidance functions")
        write_json(output / "guidance_manifest.json", {
            "files": {str(p.relative_to(output)): digest(p) for p in (output / "vlm_agent").rglob("*")
                      if p.is_file() and p.suffix in (".txt", ".json", ".png")},
            "reward_model": cfg["reward_model"], "stage_model": cfg["stage_model"],
            "provider": PROVIDER, "official_source_commit": SOURCE_COMMIT, "sample_count": cfg["sample_count"],
        })
        original_step, original_select = app.adapter.step, app.policy.select_action
        original_recognize = recognizer.identify_stage_and_guidance
        final_info = {}

        def step(action):
            nonlocal final_info
            observation, reward, terminated, truncated, info = original_step(action)
            state = simulator_status(app.adapter)
            success = bool(info.get("success", info.get("is_success", False)))
            timeout = state["done"] and not success
            final_info = {**info, "success": success, "simulator_timestep": state["timestep"],
                          "simulator_horizon": state["horizon"], "TimeLimit.truncated": bool(timeout)}
            progress["steps"] += 1
            append_json(output / "actions.jsonl", {"step": progress["steps"],
                        "action": action.detach().cpu().tolist(), "success": success,
                        "simulator_timestep": state["timestep"]})
            if progress["steps"] % 20 == 0 or terminated or truncated or timeout:
                report(phase="rollout")
            return observation, reward, terminated, bool(truncated or timeout), final_info

        def select(*args, **kwargs):
            kwargs["verbose"] = False
            if kwargs.get("generate_new_chunk"):
                report(phase="sampling")
            result = original_select(*args, **kwargs)
            if kwargs.get("generate_new_chunk"):
                progress["chunks"] += 1
                guided = bool(kwargs.get("use_guidance") and kwargs.get("guidance_fns"))
                progress["interventions"] += int(guided)
                append_json(output / "chunks.jsonl", {"chunk": progress["chunks"],
                            "step": progress["steps"], "steering": guided,
                            "stage": kwargs.get("current_stage"), "guide_scale": kwargs.get("guide_scale")})
            return result

        def recognize(*args, **kwargs):
            report(phase="stage_planning", stage_queries=progress["stage_queries"] + 1)
            result = original_recognize(*args, **kwargs)
            append_json(output / "stage_decisions.jsonl", {"step": progress["steps"],
                        "stage": int(result[0]), "guidance": bool(result[1])})
            return result

        app.adapter.step, app.policy.select_action = step, select
        recognizer.identify_stage_and_guidance = recognize
        # Preparation consumes random numbers; policy noise starts at its paired seed.
        seed_all(context.get("policy_seed", context["seed"]))
        report(phase="rollout")
        app._run_episode(0, str(output))
        if not final_info or (not final_info["success"] and not final_info["TimeLimit.truncated"]):
            raise RuntimeError("episode ended without native success or simulator timeout")
        if versions != {n: p._version for n, p in app.policy.named_parameters()}:
            raise RuntimeError("frozen VLS changed policy parameters during evaluation")
        row = {k: progress[k] for k in ("steps", "chunks", "interventions", "stage_queries")}
        row.update(context=context, success=final_info["success"], valid=True, environment=provenance,
                   seconds=time.monotonic() - start, weights_frozen=True,
                   termination_reason="success" if final_info["success"] else "simulator_horizon",
                   simulator_timestep=final_info["simulator_timestep"], simulator_horizon=final_info["simulator_horizon"])
        write_json(output / "result.json", row)
        report(status="complete", phase="complete", success=row["success"])
    except BaseException as exc:
        report(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        if app is not None:
            try:
                app.adapter.close()
            finally:
                if getattr(app, "gemini_stage_recognizer", None) is not None:
                    app.gemini_stage_recognizer.close()
                if getattr(app, "vlm_agent", None) is not None:
                    app.vlm_agent.client.close()


def evaluate(config_path, run_name, gpu_index, resume=False):
    cfg = load_settings(config_path)
    protocol = Protocol(cfg["protocol"])
    contexts = protocol.contexts(cfg["split"], cfg["seed"], task_order(cfg, protocol))
    engine = verify_engine(cfg)
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_index)
    from .resources import isolated_device
    with isolated_device(cfg):
        output = Path(cfg["output_root"]) / run_name if resume else safe_output(cfg["output_root"], run_name)
        if resume and (output.resolve().parent != Path(cfg["output_root"]).resolve() or not output.is_dir()):
            raise ValueError("invalid VLS resume directory")
        lock = (output / "controller.lock").open("a+")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        plan = {"config": cfg, "contexts": contexts, "engine": engine,
                "evaluator_sha256": digest(Path(__file__)),
                "runtime_template_sha256": digest(cfg["runtime_template"])}
        if resume and read_json(output / "plan.json") != plan:
            raise ValueError("VLS resume configuration/contexts/code differ")
        write_json(output / "plan.json", plan)
        write_json(output / "config.json", cfg)
        write_json(output / "gpu.json", {"index": gpu_index, "uuid": os.environ["CUDA_VISIBLE_DEVICES"]})
        state = {"status": "running", "method": "v44_vls", "pid": os.getpid(), "gpu_index": gpu_index,
                 "episodes_planned": len(contexts), "episodes_completed": 0, "started_at": now()}

        def report(**updates):
            state.update(updates, updated_at=now())
            write_json(output / "status.json", state)

        rows = []
        report(phase="validating_v44_assets")
        try:
            reference, paired = verified_reference(cfg, protocol, contexts, hash_assets=True)
            write_json(output / "base_identity.json", reference["base"])
            for index, context in enumerate(contexts):
                if (output / "stop.request").exists():
                    report(status="stopped", phase="episode_boundary")
                    return
                episode_output = output / f"episode_{index + 1:03d}"
                result_file = episode_output / "result.json"
                if not result_file.exists():
                    if episode_output.exists():
                        # Keep failed attempts intact; retries are explicit and never scored.
                        archived = output / f"aborted_episode_{index + 1:03d}_{time.time_ns()}"
                        episode_output.rename(archived)
                    episode_output.mkdir()
                    write_json(episode_output / "context.json", context)
                    log_path = episode_output / "run.log"
                    report(phase="evaluate", current_episode=index + 1, current_task=context["task_key"],
                           current_episode_dir=str(episode_output))
                    with log_path.open("w") as log:
                        worker = subprocess.Popen([sys.executable, "-u", "-m", "baseline.vls", "episode",
                            "--config", str(Path(config_path).resolve()), "--output", str(episode_output)],
                            cwd=PROJECT, stdout=log, stderr=subprocess.STDOUT)
                        report(worker_pid=worker.pid)
                        returncode = worker.wait()
                    if returncode or not result_file.exists():
                        raise RuntimeError(f"episode {index + 1} aborted (exit {returncode}); inspect {log_path}")
                row = read_json(result_file)
                rows.append(row)
                summary = summarize(rows, cfg, protocol, reference, paired, len(contexts))
                write_json(output / "summary.json", summary)
                # Rebuild from verified atomic episode results when resuming.
                write_json(output / "episodes.json", rows)
                report(episodes_completed=len(rows), successes=summary["successes"], micro_success=summary["micro_success"])
                print(f"VLS {len(rows)}/{len(contexts)} success={row['success']} steps={row['steps']} steering_chunks={row['interventions']}", flush=True)
            report(status="complete", phase="complete")
        except BaseException as exc:
            report(status="failed", error_type=type(exc).__name__, error=str(exc))
            raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "evaluate", "episode"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--run-name")
    parser.add_argument("--gpu", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    os.chdir(PROJECT)
    cpu_environment()
    os.environ.pop("MUJOCO_EGL_DEVICE_ID", None)
    os.environ.setdefault("MUJOCO_GL", "egl")
    os.environ.setdefault("PYOPENGL_PLATFORM", "egl")
    if args.command == "plan":
        import json
        cfg = load_settings(args.config)
        protocol = Protocol(cfg["protocol"])
        contexts = protocol.contexts(cfg["split"], cfg["seed"], task_order(cfg, protocol))
        reference, _ = verified_reference(cfg, protocol, contexts)
        verify_engine(cfg)
        print(json.dumps({"method": cfg["method"], "tasks": len(task_order(cfg, protocol)),
                          "episodes": len(contexts), "sample_count": cfg["sample_count"],
                          "reference_success": reference["micro_success"], "scope": scope_identity(cfg)}, indent=2))
    elif args.command == "episode":
        if args.output is None:
            parser.error("episode requires --output")
        execute_episode(args.config, args.output)
    else:
        if args.run_name is None or args.gpu is None:
            parser.error("evaluate requires --run-name and --gpu")
        evaluate(args.config, args.run_name, args.gpu, args.resume)


if __name__ == "__main__":
    main()
