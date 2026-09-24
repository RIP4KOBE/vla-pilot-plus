# One invalid N4 Dev Stage timeout: bounded engineering diagnosis

The recorded counts are internally consistent; this evidence does **not** show a collector counting bug. All12 per-call Stage records sum exactly to both the Stage and provider episode totals:12 logical calls,10 completed turns,3 failed calls,10 usage-complete calls. Nine calls succeeded; step80 belongs to both completed and failed sets, so10+3−1=12. The latency/token counter sums also match exactly.

| Step | Result | Seconds | Completed/usage-complete | Saved sanitized stream |
|---|---|---:|---|---|
|72|codex_timeout|90.193849|0/0|thread.started, turn.started, error|
|80|codex_timeout|90.186252|1/1|thread.started, turn.started, agent_message, turn.completed|
|240|codex_timeout|90.208963|0/0|thread.started, turn.started, error|

`core/codex_stage.py:242–252` waits for the **CLI process** to finish for90s. On expiry it stops that owned process, parses its available stdout to preserve completion/usage, then unconditionally raises `codex_timeout`. `_parse_events` counts completion/usage at153–194; `_record_transport_result` independently adds a failed call at270–292. Consequently step80 correctly has observed completion and77 output tokens while remaining a failed timed-out Stage request. Its raw response being preserved is not successful semantic acceptance. Event receipt timestamps and exit/cleanup durations were not recorded; whether completion preceded90s or arrived during cleanup is **Unknown**.

Steps72/240 contain no completed turn or usage. Their zero token increments are observed subtotals, not evidence that no tokens were consumed. The episode flags `provider_token_usage_complete=false`; known totals108105 input /67840 cached input /750 output /259 reasoning are partial totals. CLI internal HTTP attempts/retries remain null. The retained `error` event kind does not reveal its cause; temporary stderr/event payloads are not preserved as reviewed public evidence and were not accessed.

`main.py:1210–1266` computes episode deltas and marks usage complete only when every logical call has complete usage. Frozen runner `episode_compute` carries that false status, and `validate_result` requires complete token telemetry before the Stage-transport gate. Frozen N4 `transport_recovery_eligibility` additionally requires complete costs and the exact transport gate (`scripts/qd_ed_n4_plan.py:337–369`). This failed call set therefore cannot satisfy the existing recovery contract. The old invalid cell,90s condition and missing cells stay unchanged.

The exact attempt's GPU3 kernel record has `faults=[]`. The monitor matches Xid by PCI, owned PID and process lifetime (`supervisor-support.py:121–151`). No owned GPU fault is evidenced here; this does not exclude all possible driver faults or explain remote-service delay. The only emitted log extracts are three fixed `codex_timeout` tokens with line references329,332,355; no prompt, response, argv or credential text is included.

Increasing timeout alone is **not established as sufficient**. Successful calls ranged24.214–89.344s, including two near90s, so additional time may avoid some expirations. But the two incomplete error-bearing streams and the completed-turn/process-exit distinction remain unresolved. A future condition should first preserve passive sanitized lifecycle timing, completion observation, return code and before/after-cleanup boundaries; missing usage must stay Unknown. Any changed bound or completion policy would be a new prospective matched condition, with full process cost and the same one-application-attempt policy unless independently authorized. This review selects no new timeout, accepts no delayed old result and authorizes no retry.

Scope and hashes are in `diagnosis-v1.json`: one explicitly named Dev attempt's Stage/compute/kernel metadata, at most20 sanitized log lines (three emitted), W source only; zero native/image/peer/protected-result/credential reads, GPU/model/provider calls or production/ledger mutations.
