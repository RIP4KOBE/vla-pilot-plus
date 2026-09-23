# Direct final-population membership: prospective CPU check

Read `protocol.md`. The runtime schema was inspected read-only; no final membership has been calculated with this checker. Root must review these source/protocol digests and provide a new explicit execution authorization before either real run. The existing historical reports are immutable inputs, not outputs to be amended. The script refuses any other episode/report digest.

The frozen production source stores Q0 archive elites directly in `final_selection.population`; C0 stores its actual final population. This checker tests native tensor identity and the original final selection. It does not run an archive, model or projector. C0 qualities come from the identical last canonical batch. Q0 qualities require all exact native matching occurrences to agree, except the selected slot's explicitly recorded final quality. Ambiguous insertion occurrence, conflicting historical qualities and the earlier tail Unknowns are preserved.

Four disposable CPU tests cover C0's last-batch quality and repeated slots/all ties, a historical candidate absent from Q0's actual final pool, Q0 quality/tail ambiguity, and native dtype/selected-index/final-C0 inconsistency rejection:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  docs/03_evidence/qd_ed_final/continuation_20260923/final-population-membership/test_membership.py
```

After root authorization, a manifest must contain:

```json
{
  "schema": "qd-ed-final-membership-input-v1",
  "script_sha256": "<reviewed check_membership.py SHA>",
  "protocol_sha256": "<reviewed protocol.md SHA>",
  "execution_authorization": {"path": "<new root authorization>", "sha256": "<SHA>"},
  "historical_report": {"path": "<explicit t00-c0-v1 or t00-q0-v1 candidate report>", "sha256": "<fixed report SHA>"},
  "historical_checker": {
    "path": "<E>/docs/03_evidence/qd_ed_final/continuation_20260923/candidate-tail-availability/check_candidates.py",
    "sha256": "5ed4a49c0e9b62e43e5b98915e8bca252c6f598ce23a339d68b154e22906a839"
  }
}
```

The new authorization binds `script={path,sha256}`, `protocol={path,sha256}` and the two `allowed_episode_keys`. Use one manifest/new output per episode. The execution flag is not itself permission:

```bash
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python \
  <E>/docs/03_evidence/qd_ed_final/continuation_20260923/final-population-membership/check_membership.py \
  --manifest <A>/continuation_20260923/final-membership/input-t00-c0-v1.json \
  --output-dir <A>/continuation_20260923/final-membership/t00-c0-v1 --execute-reviewed
```

No original source, queue, ledger, episode outcome, historical report, target map, tail threshold or promotion gate is changed. Final availability cannot establish an unexecuted candidate's physical behavior or success. Any actual schema/identity failure is preserved for review, not weakened away.
