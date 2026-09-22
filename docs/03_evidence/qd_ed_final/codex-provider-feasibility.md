# Current Codex account: provider feasibility, 2026-09-22

The user reports the old Poe account is unusable and requests use of the current Codex account API. This supersedes the earlier request to repair Poe credentials. The Poe configuration itself remains preserved; no credential value is copied into this report.

## Verified facts

- `codex login status`: ChatGPT login. CLI version0.155.1; locally configured model `gpt-6-astra`. Saved login is not a general-purpose Platform API key. The inherited OpenAI-compatible endpoint host is `rawchat.cn`; its key was not redirected or tested against OpenAI/Poe.
- A CPU-only `codex exec` probe used the existing ChatGPT login after removing API/provider environment overrides. It used `--ignore-user-config`, `--ephemeral`, a read-only sandbox, low reasoning, disabled web search, a synthetic128x128 image and a strict two-field output schema. Model: `gpt-6-astra`.
- Correct output: `{"color":"red","shape":"square"}`; exit0; elapsed16.908629757352173s; input16735 tokens, output19, cached input0. No command/tool execution event was observed. One `item.completed` of type `error` was also observed; its detail was not retained, so this test is successful end-to-end image plumbing evidence only.
- Probe evidence: `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/codex-feasibility-20260922/probe-summary.json`. Zero local GPU use, zero simulator steps, zero episode attempts, no benchmark image/outcome exposure.
- Actual GPU7 CUDA/EGL probe has passed. Latest GPU7 observation:0MiB,0% utilization. Admission still must be checked at dispatch.
- Read-only Codex App Server `account/read` confirms ChatGPT Pro. `account/rateLimits/read` did not return within the bounded30-second request window; remaining quota is unknown. See adjacent `account-readiness.json`. No login/logout, purchase, credit reset or account mutation was requested.

## Supported routes and scientific consequences

1. Current ChatGPT login through Codex CLI/SDK: the synthetic vision path works. It requires a subprocess/SDK adapter; it is not an OpenAI Chat Completions key replacement. Account quota, repeated-call latency, global instruction overhead, provider retries and production Stage behavior remain unverified.
2. Separate OpenAI Platform API key: normal API integration with separately billed usage. No valid official Platform key was established by this inspection. Never substitute a saved login token as a Platform key.
3. Existing third-party API service: requires confirmation that this is the intended service and verification of supported vision models/response shape. Existing environment presence alone does not establish account/model authorization or usability.

No backend or phase gate was changed. Freeze one route and one model for Q0/P2/N1 before evaluating any of them. Preserve original task-level Stage prompt, image identity/order, query triggers and reward functions; disclose and hold common any necessary wrapper, output, temperature or token-limit changes. New baseline results must be compared within this provider condition, with historical Gemini/Poe results identified as a different condition.

Before production dispatch, verify two-image Stage transport, parsing/failure handling, per-call latency and token accounting, truthful request/retry observability, account availability, bounded timeout behavior and a matching same-round control plan. Do not report unavailable HTTP-attempt counts as zero. The smoke result does not establish completion within account quotas or the48-GPU-hour budget. Both frozen baseline profiles allow up to50 triggered Stage queries per episode. At the single synthetic probe latency,50 calls would add about14.1 minutes per episode;240 such episodes would imply about56.4 hours of Stage waiting alone if the GPU remains allocated. This is a worst-case planning illustration, not a measured production latency prediction: real two-image prompts, caching, trigger counts and model load differ. Do not raise the GPU budget or reduce frozen query limits silently.

## Official documentation checked

- [Authentication](https://learn.chatgpt.com/docs/auth): distinguishes ChatGPT subscription login and Platform API-key billing; credentials remain managed by Codex.
- [Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode): `codex exec`, read-only execution, JSONL events, output schemas and ephemeral runs.
- [Developer commands](https://learn.chatgpt.com/docs/developer-commands?surface=cli): image attachments and `--ignore-user-config` while retaining authentication.
- [Codex SDK](https://learn.chatgpt.com/docs/codex-sdk): programmatic control of local Codex and application integration.

## Poe evidence correction

The earlier `poe-readiness-20260922.json` incorrectly inferred `authenticated: true` from GET `/models`200. Preserve that original observation, but supersede the inference with `runtime/provider-adjudication-20260922.json`. The two actual synthetic generation requests returned401 `invalid_api_key`; provider readiness is false. The user independently confirmed the old account is unusable.
