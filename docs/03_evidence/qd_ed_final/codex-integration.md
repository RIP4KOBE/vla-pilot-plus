# Codex managed-login Stage integration

The user explicitly selected the existing Codex login on2026-09-22. The new common Stage condition is `codex_login_astra_low_v1`: `gpt-6-astra`, low reasoning, official CLI0.155.1, saved ChatGPT login,90-second call timeout and one application invocation per query. Original Poe files remain untouched.

## Implementation and checks

- `core/codex_stage.py` reuses the original Stage prompt, image encoder/order, parser and fallback. A separate public policy module defines all CLI options and fingerprints. The original Gemini/OpenAI-compatible backend remains the default outside the explicit study override.
- The CLI receives116 frozen skill disables, plus disabled tools/plugins/apps/delegation/web search. Local prompt inspection found CLI0.155.1 requires `SKILL.md` file paths for these overrides; folder paths left the catalog enabled. The final policy encodes this version-specific behavior. Neither global skill settings nor credential files were edited.
- Main startup uses a cache-only guidance reader with Codex; no unused OpenAI client or dummy API key is created. Missing cache, ancillary grounding/SAM3 or failed Codex initialization stop the run.
- The launcher preserves `HOME/CODEX_HOME`, clears alternative provider authentication only in the child environment, and checks managed ChatGPT login. Runner verifies source/runtime hashes, exact CLI path/version/hash, public policy, frozen skills metadata and physical GPU7 admission before every dispatch.
- Codex telemetry records real logical calls, completed/failed calls, observed token usage and latency. Internal HTTP send/retry counts remain null. Event records reconcile with whole-episode totals; missing usage or transport violations cannot pass scientific result validation. Legacy HTTP-provider telemetry keeps its original semantics.
- Timeout cleanup terminates the owned CLI descendants while retaining the outer runner's process group. No simulator branch rollout was added.

Integrated CPU validation: **673 passed in40.74s**, with the known mocked-CUDA-disabled and NetworkX deprecation warnings. No GPU was initialized by these tests.

## Actual transport evidence

The first production-adapter probe was rejected because an error-type CLI event contained a skill-context warning. Preserve it at `runtime/codex-stage-production-probe-20260922/result.json`; it was not an episode and never became success evidence.

After correcting skill disable paths, the same two synthetic images and unchanged Stage task template passed: Stage2, guidance yes, exactly one turn, one complete usage record, zero failed calls, only an agent-message item. Observed latency33.5436s; input9780 tokens, cached0, output69, reasoning21. This is transport/parsing evidence only, not robot accuracy or an estimate of full-study quota sufficiency.

Final evidence under artifact root:

- `runtime/codex-stage-production-probe-v2-20260922/result.json`
- `runtime/codex-stage-production-probe-v2-20260922/public-policy.json`
- `runtime/codex-setup-manifest.json`

Effective public policy SHA256: `92755b006b497972f9f5563b7ceb1580bc36b2e4b4923804257f223eda9e5221`.
CLI binary SHA256: `0753dfe1d8b87a52436deb13eb1c549661ef4c84fee2c5aa688385eebeccb761`.
Unchanged Stage template SHA256: `758d71a441496074410428b005a068a18b6d92273b9278c1181334cf9e67005b`.

## Execution condition

Apply the new provider identically to Q0, P2/C0 and N1, and re-establish the20 preregistered baseline cells before candidate evaluation. The algorithm hypothesis, seed mapping, episode/time budgets, protected validation/formal reservations and GPU7-only rule remain unchanged. All GPU wall time waiting for Codex counts. No comparison against a historical Poe score establishes a QD improvement.
