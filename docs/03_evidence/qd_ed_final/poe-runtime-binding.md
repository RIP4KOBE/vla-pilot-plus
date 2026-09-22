# Authorized Poe runtime binding

The user confirmed on 2026-09-22 that this continuation must retain the Poe configuration and credentials. `scripts/qd_ed_poe_launch.py` selects only `OPENAI_BASE_URL` and `OPENAI_API_KEY` from the existing `/home/hynx/VLA-Pilot++/.env`. It evaluates no shell expressions or variable substitutions and creates no credential artifact, log, or fingerprint. Its optional `--credentials-file` supports an explicitly selected local file and temporary unit-test fixtures.

The endpoint must be exactly `https://api.poe.com/v1`; no endpoint override is supported. The selected plan must point to the supplied public runtime manifest. Before exec, that manifest must have `provider_ready: true`, the frozen endpoint, model `gemini-2.5-flash`, and `credential_env_name: OPENAI_API_KEY`. The Stage client's Google-before-OpenAI precedence remains unchanged in source. The wrapper selects `OPENAI_API_KEY` by the frozen Poe environment convention and excludes `GOOGLE_API_KEY` from both the authorized file and the inherited environment, preventing that field from taking precedence. This naming choice does not establish credential validity; readiness is verified separately, and the wrapper makes no API request. The worktree has no `.env`, preventing `main.py` from reintroducing a Google field through its existing local dotenv load.

As of the 2026-09-22 continuation, a safe metadata comparison confirmed that the root `.env` values for `GOOGLE_API_KEY` and `OPENAI_API_KEY` were identical. Separate synthetic POST checks using each field both returned HTTP 401 `invalid_api_key`. There is no verified Poe credential, and this was not a Google field shadowing a working OpenAI key. The actual runtime retains `provider_ready: false` while awaiting the user's update of `OPENAI_API_KEY`; a successful authenticated check is still required before launch.

The wrapper replaces itself with `/home/hynx/miniconda3/envs/vla-pilot/bin/python` running this worktree's fixed `scripts/qd_ed_final_runner.py`, with structured arguments for `run`, `validate-plan`, `print-command`, or `reconcile-ledger`. It accepts no arbitrary executable or shell command. The runner retains its own source/input hashes, GPU7 exclusivity, phase authorization, accounting, and provider checks.

Example (paths contain no credentials):

```bash
/home/hynx/miniconda3/envs/vla-pilot/bin/python scripts/qd_ed_poe_launch.py \
  --runtime-manifest /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/setup_manifest.json \
  run --plan data/qd-ed-final-plan.json --split dev --iteration baseline
```

CPU tests use temporary placeholder credentials and mock `execve`; they cover host and manifest rejection, explicit Poe/OpenAI selection, exclusion of both file and inherited Google keys, secret-free diagnostics, and the fixed interpreter/script argument vector. They do not load models, create GPU contexts, or call a provider.
