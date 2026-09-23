# Root-only integration and execution steps

Status: CPU-tested proposal only; no source integration, plan freeze, provider call or GPU dispatch. Complete/review the running freshboot C0 first. Treat a non-passing engineering prerequisite as a closed gate for this batch.

1. Create the new prospective Arbor evidence node and accept prospective-protocol.md. Integrate reviewed collector/auditor code from E into W only after the live run terminates. Copy this owned directory into W, including independent supervisor-support.py. That support copy only adds optional allowed-key arguments to the reviewed class/lock context; the original wrapper file is unchanged. Do not execute from E or copy its research-state/data locks over W.
2. Run the existing collector/auditor regression suite and this directory's CPU tests. Commit final source/protocol. Keep GPU3/current boot, original native dependency freeze, runtime/cache/model inventory and Stage binding. Explicitly verify task5 runtime cache/input binding; runner validation enforces its frozen dev hashes. No new model probe is needed.
3. Name the **actual plan used by** node5.5 (if the queue emitted a hardware child plan, use that one) and its immutable attempt-result.json. Builder links both digests/source. It checks model/input/profile manifest digests but leaves full model-byte verification to the original same-process queue cache. It requires terminal journals under the real lock and never writes state/ledger.

After integration only, with full committed source SHA:

```bash
W=/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z
A=/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z
P="$W/docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft"
PY=/home/hynx/miniconda3/envs/vla-pilot/bin/python
PAIRS_HEAD='<full committed HEAD after collector/support/protocol integration>'
COMMON_PLAN='<explicit actual node5.5 frozen plan path>'
COMMON_RESULT='<explicit original C0 attempt directory>/attempt-result.json'
OUT="$A/continuation_20260923/observed-pairs-v1"
"$PY" "$P/observed-pairs.py" prepare --source-head "$PAIRS_HEAD" \
  --base-plan "$COMMON_PLAN" --common-result "$COMMON_RESULT" \
  --output "$OUT/plan.unfrozen.json"
"$PY" "$P/observed-pairs.py" preview --plan "$OUT/plan.unfrozen.json"
```

`prepare` is fail-closed and will not overwrite any draft. Its output is frozen:false. `preview` uses original build_command with the new observed profile and prints only public argv. Perform the existing CPU Hydra composition for all four argv and record only allowlisted resolved fields: source/profile identifiers, algorithm configuration, task/seed/init binding, Stage public binding, episode timeout and decision_evidence.enabled=true. Freeze a **new copy** with reviewed preview paths/digests and fresh frozen_at; never overwrite the unfrozen or previous plan.

Only after root review/admission, explicit execution is:

```bash
"$PY" "$P/observed-pairs.py" run --plan "$OUT/plan.frozen.json" \
  --status-path "$OUT/queue-status.json"
```

This retains one real shared runner lock across the fixed four rows, so it may wait behind external work and then wait for GPU3's120-second idle window. It does not preempt another process. A failure stops remaining rows. Original runner ledger terminals/costs stay unchanged; complete evidence audit results are written per attempt under eds_eval/decision-evidence-audit.json. Root must review before any later explicit recovery/remaining-row proposal.

Sources to freeze include original r.REQUIRED_CODE, queue/probe/runtime setup, the independent support script, native-dependency-freeze.json, original and observed profile manifests, this protocol/entrypoint, core/decision_evidence.py and **scripts/audit_decision_evidence.py explicitly** (scripts are not covered by core's recursive fingerprinting). Preserve the original base plan's scientific configs/protocols and explicit prerequisite evidence digests. Root must use one final source HEAD for all four rows; no mid-batch source edits.

CPU test command (safe in E):

```bash
PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft/test_observed_pairs.py
PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  docs/03_evidence/qd_ed_final/continuation_20260923/observed-pairs-draft/test_supervisor_support.py
```

Results:4 proposal tests and10 support tests PASS. Support tests retain the nine existing locks/Xid/runner-finally cases and add explicit multi-key acceptance/external-key rejection. Compile checks PASS. AST comparison confirms normalize_boot, ObservedWait and supervise_calls are unchanged; only Monitor/shared_runner_lease gained the allowed-key interface/status, and the old CLI is omitted. No production source, state, ledger or plan was changed. See cpu-validation.json.
