# Common Stage provider amendment, 2026-09-22

Status: preregistered before any new online outcome. Applies to Q0, P2/C0, N1 and any later comparisons in this provider condition. The N1 algorithm hypothesis and its original promotion criteria are unchanged.

## Authorization and scope

The user reports Poe is unusable and explicitly instructs: “直接用codex登录使用”. Use the currently saved ChatGPT login managed by official Codex CLI. Do not extract, copy or repurpose login tokens. Preserve the original Poe configuration. Do not use the inherited third-party API key or silently fall back to another service.

Use the current configured and successfully probed model `gpt-6-astra`, with low reasoning, through pinned Codex CLI0.155.1. Freeze the executable hash and effective public invocation policy before dispatch. This replaces Gemini2.5Flash/Poe and is a common experimental condition change, not a QD mechanism improvement. Historical scores remain historical and cannot establish a new-provider advantage.

## Common input and behavior contract

- Preserve the existing Stage task prompt template, task-specific Stage descriptions, initial annotated image and current image identity/order, query triggers,50-query limit, parsed Stage/guidance grammar and conservative parse-error behavior.
- Preserve cached canonical reward functions, RDT/Object EMA and encoder weights, perception/keypoints, action execution, strict perturbations, task/success definitions, seed/init identities and QD/EDS compute settings.
- Keep all unused guidance-generation/grounding API paths inactive and fail closed if the frozen cache contract is violated. The experiment must not require a dummy API key or call an expired Poe account merely to initialize an unused client.
- Codex has different built-in instructions and inference controls. Legacy API temperature0 and256-token request settings cannot be claimed identical through CLI; disclose that difference. Use one common restricted wrapper, no tool execution, no agent delegation, no web search and no automatic skill invocation inside Stage calls. Validate final text with the unchanged Stage parser.
- Application attempts: one CLI invocation per triggered Stage query, with a90-second timeout. CLI transport retries remain managed internally; no unsupported built-in provider override is claimed to disable them. Record every failed or timed-out invocation. Preserve the existing1800-second episode timeout across baseline arms unless a separate pre-outcome engineering amendment is recorded.

## Cost and evidence accounting

Record actual CLI invocation attempts, completed turns, failed calls, observed input/cached/output/reasoning tokens and call latency. Unknown HTTP send/retry counts must be null and explicitly marked unobserved, never zero or renamed logical-call counts. Reject tool use, extra turns and unaccounted successful calls. Failed-call usage that is unavailable remains explicitly unknown and cannot be used to claim a lower total cost. Keep old HTTP-provider telemetry semantics on the legacy path.

All allocated GPU wall time, including waiting for Codex, counts toward48 GPU-hours. Every dispatched episode counts toward240 attempts, including failures. Existing validation14h/formal10h GPU reservations and all episode reservations remain protected. The first paired Q0/P2 cells establish actual runtime behavior; they are ordinary counted baseline episodes, not free probes or success-based stopping opportunities.

The prior synthetic single-image probe established transport feasibility only. No production success-rate, Stage accuracy, account quota sufficiency or whole-study runtime claim follows from it. Before dispatch, test the actual adapter with two synthetic images and the unchanged Stage prompt, verify parsing/usage and failure cleanup, compose all baseline commands, and freeze source/config/runtime fingerprints. Do not inspect fresh validation/formal outcomes during this preparation.

## Interpretation

Re-establish Q0 and P2 on the same20 preregistered Dev cells under this Codex condition before evaluating N1. Use the same provider condition for candidate validation, controls and final ablations. N1 still differs from Q0 only in its descriptor; provider migration must not be presented as a candidate-specific change. Any inability to complete due to quota or infrastructure is recorded separately from task success and does not justify changing seeds, dropping failures, or expanding budgets.
