from pathlib import Path
from datetime import datetime, timezone
import fcntl, hashlib, json, re, textwrap, yaml

wt = Path.cwd()
base = Path("artifacts/stage_closed_loop_20260929")
run = base / "runs/codex_failed_contact_v17_historical_initialization_online_full10"
queue = base / "codex-v17-continuation"
report = Path("docs/03_evidence/stage_consistency/2026-09-30-codex-v17-full10-report.md")
now = datetime.now(timezone.utc).isoformat()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())
def write(p, d):
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
def ref(p):
    return {"path": str(p), "sha256": sha(p)}

summary = read(run / "full10-evidence-summary.json")
audit = read(run / "audit.json")
deep = read(run / "deep-audit.json")
manifest = read(run / "manifest.json")
runtime = read(run / "output/status.json")
calls = read(run / "codex-full10-availability-proof.json")
accounting = read(base / "accounting.json")
config = yaml.safe_load((run / "resolved-config.yaml").read_text())
init = read(run / "initialization-comparison.json")
norm = read(run / "reward-reference-diagnostic.json")
tests = read(run / "installed-cpu-validation.json")

assert runtime["started"] == runtime["completed"] == 10 and runtime["success"] == 3
assert runtime["status"] == "exited" and runtime["exit_code"] == 0
assert audit["valid"] and deep["valid"]
assert len(audit["checks"]) == 62 and all(audit["checks"].values())
assert len(deep["checks"]) == 59 and all(deep["checks"].values())
assert len(calls["records"]) == calls["completed"] == 325 and calls["failed"] == 0
assert calls["all_expected_provider"] and not calls["poe_allowed"]
for record in calls["records"]:
    assert sha(run / record["path"]) == record["sha256"]
    assert record["ok"] and record["backend"] == "codex_cli"
    assert record["auth_mode"] == "chatgpt" and record["model"] == "gpt-6-astra"
    assert record["reasoning_effort"] == "low" and record["completed_turns"] == 1
    assert record["process_returncode"] == 0
for name, digest in manifest["source_sha256"].items():
    assert sha(Path(name)) == digest and sha(run / "source" / name) == digest
assert sha(Path(manifest["rng_fixture_manifest"])) == manifest["rng_fixture_manifest_sha256"]
assert len(init["tasks"]) == len(norm["tasks"]) == 10
for t in init["tasks"]:
    assert all(t[k] for k in ["available", "keypoints_equal", "scoring_keypoint_indices_equal", "first_particle_csv_equal", "all_recorded_initial_tensors_equal"])
assert all(t["actual_normalization_exact"] for t in norm["tasks"])
assert summary["native_actions"] == 5585 and summary["action_overrides"] == 0
assert tests["passed"] == 456
processes = read(queue / "process-identities.json")["processes"]
handle_results = {}
for pid, d in processes.items():
    p = Path("/proc") / pid / "stat"
    alive = p.exists() and p.read_text().rsplit(")", 1)[1].split()[19] == d["start_ticks"]
    assert not alive, (pid, "original process still active")
    handle_results[pid] = {"original_start_ticks": d["start_ticks"], "original_process_alive": False}
reviews = []
for item in summary["reviews"]:
    p = run / item["path"]
    assert sha(p) == item["sha256"]
    d = read(p)
    assert d["episode_complete"] and not d["visual_review_pending"] and not d["full_cohort_audit_pending"]
    videos = list((run / "output" / ("episode_" + str(d["task_id"] + 1))).glob("*agentview.mp4"))
    assert len(videos) == 1 and sha(videos[0]) == d["video_fingerprint"]["video_sha256"]
    reviews.append({"task": d["task_id"], "success": d["environment_success"], "actions": d["actions"], "review": ref(p), "video": ref(videos[0])})
assert sorted(d["task"] for d in reviews) == list(range(10))
assert sum(d["success"] for d in reviews) == 3
assert not accounting["current_runs"]
assert accounting["effective_dispatched_completed"] == 371
assert accounting["protected_attempts"] == 100 and accounting["protected_gpu_hours"] == 24.0
assert all(Path(link).exists() for link in re.findall(r"\]\((/[^)]+)\)", report.read_text()))

accepted = {
    "utc": now, "name": manifest["name"], "status": "ACCEPTED_CODEX_ONLINE_DIAGNOSTIC_BASELINE",
    "acceptance_scope": "One frozen complete online ten-task environment cohort >=3/10; all evidence and qualitative limitations retained",
    "acceptance_authority": ref(base / "acceptance-clarification-before-v14-20260930.json"),
    "provider_authority": ref(base / "codex-only-provider-authorization-20260930.json"),
    "physical_gpu": 2, "gpu_uuid": manifest["gpu_uuid"],
    "provider": "codex_cli", "auth_mode": "chatgpt", "model": "gpt-6-astra", "reasoning_effort": "low", "poe_allowed": False,
    "tasks": manifest["tasks"], "seeds": manifest["seeds"],
    "manifest": ref(run / "manifest.json"), "resolved_config": ref(run / "resolved-config.yaml"),
    "frozen_source_directory": str(run / "source"),
    "source_sha256": manifest["source_sha256"],
    "rng_fixture_manifest": {"path": manifest["rng_fixture_manifest"], "sha256": manifest["rng_fixture_manifest_sha256"]},
    "scientific_parent": "codex_fused_carry_v16_historical_initialization_online_full10",
    "parent_config_comparison": ref(run / "parent-config-comparison.json"),
    "single_new_scientific_flag": "main.stage_failed_contact_recheck_enabled=true",
    "reward": "Fresh per-task generated c0_xyz_v1 functions; local numeric evaluations",
    "stage": "Fresh online current observations; no saved reply replay",
    "historical_fixture_scope": "RNG initialization only; no historical reward/action/environment/Stage replay",
    "qd_archive_mode": config["main"]["eds_config"]["qd_archive_mode"],
    "success": 3, "completed": 10, "success_task_ids": [3, 8, 9],
    "strict_historical_poe_model_reproduction": False,
    "independent_heldout_generalization_estimate": False,
    "formal_qd_ed_five_of_ten_goal_achieved": False,
    "report": ref(report),
    "reproduction": "Use recorded manifest argv with the exact frozen source/config/fixture and a new output directory under this existing worktree. Default repository settings are not sufficient. This record does not dispatch another run.",
}
write(run / "accepted-setting.json", accepted)

checkpoint = run / "continuation-checkpoint.json"
checkpoint_archive = run / "continuation-checkpoint-before-finalization.json"
if not checkpoint_archive.exists():
    checkpoint_archive.write_bytes(checkpoint.read_bytes())
write(checkpoint, {
    "utc": now, "phase": "V17_ACCEPTED_DIAGNOSTIC_COMPLETE",
    "run": manifest["name"], "provider": "codex_cli_chatgpt_managed_login",
    "model": "gpt-6-astra", "reasoning_effort": "low", "poe_allowed": False,
    "physical_gpu": 2, "gpu_uuid": manifest["gpu_uuid"],
    "completed": 10, "success": 3, "acceptance_met": True,
    "installed_cpu_tests_passed": 456, "completion_audit_checks": 62, "deep_audit_checks": 59,
    "completed_model_calls": 325, "failed_model_calls": 0,
    "runtime_seconds": runtime["elapsed_seconds"], "original_processes": handle_results,
    "active_owned_worker": None, "active_queue": None, "next_actions": [],
    "further_gpu_work_required_for_this_acceptance": False,
    "report_final": str(report), "accepted_setting": str(run / "accepted-setting.json"),
    "completed_task_reviews": [x["path"] for x in summary["reviews"]],
    "video_index": str(run / "videos.html"),
    "goal_completion_audit": str(run / "goal-completion-audit.json"),
    "goal_status_authority": "The goal service is authoritative; finish its complete transition after final evidence verification.",
    "scientific_conclusion": "Valid single-cohort 3/10: retained BBQ120 and pudding211; new orange214 after failed-contact recheck56. Codex-only online access verified. Seven failures and remaining Stage/occlusion/reference limitations retained.",
    "limitations": ["Not exact old Poe reproduction", "Orange never entered Stage2", "Post-success stable placement unobserved", "Milk expired-hold recovery and marker overlap unresolved", "Cream/butter rechecks did not improve success", "QD archive off; no >=5/10 result", "Development fixed tasks/seeds are not independent held-out validation"],
    "resource_ownership": "All own V17 handles exited. Do not signal peer GPU processes or mutate peer state. No restart required.",
    "future_recommendations_only": ["Expired-hold recovery", "Target-marker overlap controls", "Reward-reference/Stage-history coupling", "Separate frozen QD/ED comparisons and independent validation"],
    "pre_finalization_checkpoint": str(checkpoint_archive),
})

head = f"""**V17 已完成并通过本轮基线恢复验收 — {now}**

单次冻结完整十任务有效 **3/10**，成功 BBQ120、pudding211、orange214；七个失败全部保留。仅当前 Codex 账号官方 CLI / ChatGPT 登录，gpt-6-astra / low，325 次完整调用、0 次失败，Poe 禁止。每任务新 reward/阶段/身份描述，执行期间在线 Stage；reward 数值本地计算。

62+59 项完成/深度审计通过，十任务初始化对齐历史，5,585 个原生七维动作无覆盖，十段视频关键帧审阅完成。新空抓复查在 orange56 恢复 ED，较父版本88提前32步；cream64、butter360虽触发仍失败。Orange成功仍为Stage1，milk释放后恢复、目标标记遮挡和reference历史耦合仍有局限，不等于所有在线语义问题解决。不是旧Poe原样复现，也不是最终QD/ED>=5/10。

原 queue4176486 / supervisor4179420 / worker4180150 已按启动标识确认退出。**不需重启本轮，不启动后续候选，不操作他人GPU进程。** 本研究累计371次、43.37809 GPU小时上界；保留100次/24小时额度未动用。最终结论和下一轮建议见报告。

- [最终报告]({wt / report})
- [冻结基线设置]({wt / run / "accepted-setting.json"})
- [十任务视频]({wt / run / "videos.html"})
- [续接状态]({wt / checkpoint})
- [完成条件审计]({wt / run / "goal-completion-audit.json"})

以下内容为旧进度记录，仅作历史，不得按其中的旧活动PID或未完成计数重启任务：

"""
for p in [Path("HANDOFF_GPU6_GOAL.md"), Path("to_human/current-status.md")]:
    existing = p.read_text()
    separator = "以下内容为旧进度记录，仅作历史，不得按其中的旧活动PID或未完成计数重启任务：\n\n"
    if existing.startswith("**V17 已完成并通过本轮基线恢复验收"):
        existing = existing.split(separator, 1)[1]
    p.write_text(head + existing)

with Path("data/qd-ed-state.lock").open("a+") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    p = Path("research-state.yaml")
    original = p.read_text()
    marker = "\nstage_closed_loop_recovery_20260929:\n"
    prefix, suffix = original.split(marker, 1)
    assert yaml.safe_load(original)["resource_isolation"]["status"] == "ACTIVE"
    assert yaml.safe_load(original)["resource_isolation"]["validation_status"] == "PASS"
    section = yaml.safe_load(suffix)
    section.update({
        "status": "CODEX_V17_ACCEPTED_DIAGNOSTIC_COMPLETE",
        "updated_utc": now, "acceptance_met": True,
        "active_candidate": None, "active_worker_pid": None, "active_pid": None,
        "active_exec_session": None, "active_supervisor_pid": None, "active_continuation_pid": None,
        "current_source_frozen": True, "environment_score_gate_reached": True,
        "normal_target_transport_gate_reached": None,
        "active_protocol": None,
        "completed_protocol": "codex_only_fresh_online_historical_rng_failed_contact_v17",
        "accepted_baseline": manifest["name"],
        "accepted_setting_path": str(run / "accepted-setting.json"),
        "accepted_result": "valid 3/10; success tasks 3,8,9; complete single frozen cohort",
        "latest_complete_condition": manifest["name"],
        "latest_complete_score": "3/10; valid=True",
        "latest_complete_report": str(report), "latest_diagnostic_report": str(report),
        "latest_integrated_tests_passed": 456,
        "latest_integrated_tests_path": str(queue / "v17-installed-tests.log"),
        "cpu_checks": 456,
        "codex_availability_retest": str(run / "codex-full10-availability-proof.json"),
        "continuation_status_path": str(queue / "finalization.json"),
        "final_review_path": str(run / "final-review.json"),
        "goal_completion_audit": str(run / "goal-completion-audit.json"),
        "gpu_worker_status": "OWN_V17_WORKER_SUPERVISOR_QUEUE_EXITED",
        "qualitative_review_complete": True,
        "video_review_scope": "All ten videos preserved; selected keyframes and mechanism windows reviewed, not every frame watched",
        "next_online_candidate": None,
        "required_provider": "codex_cli_chatgpt_managed_login", "poe_allowed": False,
        "goal": "Completed Codex-only baseline recovery acceptance: single frozen complete online cohort >=3/10, preserved failures and full analysis",
    })
    replacement = prefix + marker + textwrap.indent(yaml.safe_dump(section, allow_unicode=True, sort_keys=False, indent=2), "  ")
    assert yaml.safe_load(replacement)["stage_closed_loop_recovery_20260929"]["acceptance_met"] is True
    assert replacement.split(marker, 1)[0] == prefix
    temp = p.with_name("research-state.v17-final.tmp")
    temp.write_text(replacement)
    temp.replace(p)
    fcntl.flock(lock, fcntl.LOCK_UN)

write(queue / "finalization.json", {
    "utc": now, "phase": "V17_ACCEPTED_DIAGNOSTIC_COMPLETE", "run": manifest["name"],
    "completed": 10, "success": 3, "valid": True, "all_reviews_complete": True,
    "original_processes": handle_results, "active_owned_processes": [],
    "report": str(report), "next_online_candidate": None,
    "original_queue_terminal_record_preserved": str(queue / "status.json"),
})
summary["goal_completion_pending_final_report_and_state"] = False
summary["final_report"] = str(report)
summary["accepted_setting"] = str(run / "accepted-setting.json")
summary["finalized_utc"] = now
write(run / "full10-evidence-summary.json", summary)

final_review = {
    "utc": now, "status": "ACCEPTED_SINGLE_FROZEN_CODEX_ONLINE_3_OF_10",
    "accepted_setting": ref(run / "accepted-setting.json"),
    "full_summary": ref(run / "full10-evidence-summary.json"),
    "report": ref(report), "reviews": reviews,
    "completion_audit": ref(run / "audit.json"), "deep_audit": ref(run / "deep-audit.json"),
    "provider_proof": ref(run / "codex-full10-availability-proof.json"),
    "initialization_diagnostic": ref(run / "initialization-comparison.json"),
    "reward_reference_diagnostic": ref(run / "reward-reference-diagnostic.json"),
    "runtime": ref(run / "output/status.json"),
    "original_processes": handle_results,
    "accounting": ref(base / "accounting.json"),
    "acceptance_met": True, "new_gpu_experiments_needed_for_current_goal": False,
    "qualitative_policy": "Selected keyframes from all ten preserved videos reviewed. No extra stable-placement threshold imposed; after-success stability remains unobserved.",
    "limitations": read(checkpoint)["limitations"],
}
write(run / "final-review.json", final_review)

checks = {
    "single_complete_ten_task_cohort": runtime["completed"] == 10 and runtime["started"] == 10,
    "actual_worker_exit_zero": runtime["status"] == "exited" and runtime["exit_code"] == 0,
    "at_least_three_environment_successes": runtime["success"] >= 3,
    "completion_and_deep_audits_all_pass": audit["valid"] and deep["valid"],
    "codex_only_fresh_identity_reward_online_stage": calls["completed"] == 325 and calls["failed"] == 0 and calls["all_expected_provider"] and not calls["poe_allowed"],
    "all_captured_response_fingerprints_verified": all(sha(run / x["path"]) == x["sha256"] for x in calls["records"]),
    "current_and_archived_scientific_sources_match_frozen_manifest": all(sha(Path(n)) == v and sha(run / "source" / n) == v for n,v in manifest["source_sha256"].items()),
    "historical_initialization_inputs_match_all_ten": all(x["all_recorded_initial_tensors_equal"] for x in init["tasks"]),
    "native_actions_and_reward_guidance_consistent": summary["action_overrides"] == 0 and audit["checks"]["ed_steps_match_gate"] and audit["checks"]["reward_gate"],
    "all_ten_reviews_and_video_fingerprints_complete": len(reviews) == 10,
    "seven_failures_preserved": sum(not x["success"] for x in reviews) == 7,
    "final_report_present_and_links_exist": report.exists() and all(Path(x).exists() for x in re.findall(r"\]\((/[^)]+)\)", report.read_text())),
    "known_semantic_and_qualitative_limitations_disclosed": all(s in report.read_text() for s in ["orange 全程仍为 Stage1", "保持在 464", "968", "独立留出集"]),
    "accounting_updated_protected_reserves_preserved": accounting["effective_dispatched_completed"] == 371 and accounting["protected_attempts"] == 100 and accounting["protected_gpu_hours"] == 24.0,
    "own_state_and_handoffs_finalized": yaml.safe_load(Path("research-state.yaml").read_text())["stage_closed_loop_recovery_20260929"]["acceptance_met"] and all("V17 已完成" in p.read_text()[:200] for p in [Path("HANDOFF_GPU6_GOAL.md"), Path("to_human/current-status.md")]),
    "original_worker_supervisor_queue_exited": not any(d["original_process_alive"] for d in handle_results.values()),
}
assert all(checks.values()), checks
write(run / "goal-completion-audit.json", {
    "utc": now, "eligible_for_goal_complete": True, "checks": checks,
    "acceptance_authority": ref(base / "acceptance-clarification-before-v14-20260930.json"),
    "provider_authority": ref(base / "codex-only-provider-authorization-20260930.json"),
    "final_review": ref(run / "final-review.json"), "report": ref(report),
    "own_state": ref(Path("research-state.yaml")),
    "handoffs": [ref(Path("HANDOFF_GPU6_GOAL.md")), ref(Path("to_human/current-status.md"))],
    "checkpoint": ref(checkpoint), "queue_finalization": ref(queue / "finalization.json"),
    "scope": "Current baseline-recovery diagnostic only. The future >=5/10 QD/ED objective is not asserted complete.",
    "goal_service_status_at_audit": "active; all completion requirements passed",
    "goal_service_transition_receipt": str(run / "goal-completion-receipt.json"),
})
print(json.dumps({"status": "FINALIZED_AND_ELIGIBLE_FOR_GOAL_COMPLETE", "success": "3/10", "final_checks": len(checks), "report": str(report), "further_gpu_work": False}, ensure_ascii=False))

