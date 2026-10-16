# RSI development branch integration review

Reviewed on 2026-10-16. Scope: integrate [PR #2](https://github.com/RIP4KOBE/vla-pilot-plus/pull/2) into `codex/agentic-rsi`, derived from main, for further development and validation. This is not approval of an online RSI performance claim or a merge of RSI into main.

## Sources and merge decisions

- Main starting commit: `dc3868e0c57143368e68f609e3385afd1a13d88a`.
- Reviewed PR head: `dfaf9be76c0c0e8762dc7e0ebfcc3493b6b8dbf8` (four contributed commits).
- Shared ancestor: `d51cb85f485502e0429c79529872efef2ec59981`.
- Incoming scope: 271 changed files, 68,596 insertions and 272 deletions relative to that ancestor; the GitHub CLI file summary returned only the first 100 files, so review used the full Git diff.
- Direct merge produced 13 conflicted paths. The original PR commits remain ancestors of the integration merge; changes are not squashed into an untraceable source copy.

The old PR modifies the same main, Stage/reward, FKD, π0.5 loader, adapter and configuration surfaces that were subsequently validated on main. Its AGENTS instructions also predate the test suite and point to retired installation commands. These files were not allowed to replace the current implementation.

PR runtime variants are isolated under `rsi/`, with explicit module imports and matching cold/warm evaluation configuration paths. `mode_gate/`, its operational scripts and `baseline/` remain independent experimental packages. New RSI tests live in `rsi/tests/`; their queue-blocking fixture does not affect the main test suite. Main's runtime, guidance code, scientific profiles, instructions and submodule revision are preserved. [integration.json](../../rsi/integration.json) records 49 protected file hashes and source mappings.

The PR requests LeRobot `910e5c6e4b22ae2c5173373133899a5e287ac322`. GitHub confirmed it is two commits ahead of main's pinned fork, touching six files in training configuration, dataset handling, scheduling, π0.5 and training resume. It was downloaded into an ignored separate directory and installed only in an isolated RSI validation venv. Main's LeRobot checkout and original environment were not updated. An initial automatic submodule fetch failed with a TLS error; the pinned archive/API route succeeded and was recorded.

## Material findings

| Finding | Resolution or remaining boundary |
| --- | --- |
| Old runtime would overwrite accepted EDS/Stage behavior | Isolated RSI runtime; retained main files; existing main suite passes |
| Identical package names could route evaluators to the wrong main/config | Explicit `rsi.main`, `rsi.core.*`, `rsi.vlm_query.*` imports, command/source paths and `rsi/configs` for cold/warm evaluators |
| Old adapter prepended main's LeRobot source | Removed that injection in the RSI adapter; the selected RSI environment owns its installed fork |
| Historical planner/campaign paths are machine-specific | Added explicit `VLA_RSI_PLANNER_CONFIG` and `VLA_RSI_CAMPAIGN_CONFIG` overrides; original config snapshots retained |
| Codex account client is a request-file queue | Needs a separately provisioned consumer; no automatic main CLI transport integration or new worker was created |
| Reward generation still uses an independent OpenAI SDK path | Not converted or silently replaced; must be reconciled before a Codex-only online RSI campaign |
| Current campaign differs from early PR design prose | Actual config uses 20 environment/position tasks, planner steering off, first-safe-particle selection and learned failure verification; it is not RDT ObjectSwap C0 |
| Historical experiment fixtures were omitted from the PR | Tests now explicitly report missing-asset skips; original assertions remain when data is available; no fake fixtures or rewritten scores |
| MuJoCo tilted-site test did not rotate its compiled identity-frame site | Fixed the test's `site_sameframe` cache flag; the unsafe-geometry rejection assertion and production controller are unchanged |
| Async tests hung in the filesystem/network sandbox | A minimal `asyncio.to_thread(lambda: 7)` reproduced the sandbox hang and succeeded outside it; local communication tests ran outside the sandbox |

The PR also contains historical scripts with automatic continuation, private paths and non-Codex baseline providers. They are preserved for development/provenance, not executed or presented as the current approved online protocol. No training, policy promotion, remote process management or live model requests were launched.

## Verification

| Check | Result |
| --- | --- |
| Original main tests, original steering environment | **1474 passed, 3 skipped**, 140.61 s |
| RSI + continual-learning baseline tests, isolated RSI environment | **747 passed, 24 skipped**, 47.05 s |
| `scripts/self_improve.py --help` | Passed |
| `scripts/run_full_experiment.py --help` | Passed |
| `python -m rsi.main --cfg job` | Passed; configuration preview only |
| Main protected-file identity and evaluator namespace checks | Passed |

Of the 24 RSI skips: 20 require omitted historical campaign artifacts; one requires the historical baseline config/runtime evidence; one requires the complete 160-file task-variant set (40 available locally); one requires MuJoCo 3.1.6; one is an explicit real-simulator opt-in. These are unverified capabilities, not passed checks. CPU tests used mocked planner/model boundaries and localhost transport, not real policy training.

The isolated venv inherits the existing validated Python 3.12/PyTorch environment and adds the declared FastAPI, Uvicorn and Google SDK dependencies plus the pinned RSI LeRobot source. Its resolved package list is archived. This check is not a from-zero installation claim. [Validation index](validation/rsi-integration-20261016.json) records identities, commands and hashes; raw attempts and logs are retained under ignored `outputs/reviews/agentic-rsi-20261016/`.

New integration edits pass `git diff --check`; the full imported tree retains inherited trailing whitespace/blank-EOF warnings. Reference source, reports and prompts were not reformatted merely to silence them. Imported `baseline/references/` and `baseline/reports/` bytes were checked against the PR; staged files were also scanned for obvious private-key/token literals, with no matches. This is not a comprehensive security review of every contributed line.

## What can proceed

The branch is suitable for reading, CPU mechanism development and provisioning RSI validation. Start with [rsi/README.md](../../rsi/README.md). Before a real campaign, recover/register the missing protocol and baseline evidence, provision assets and the learned verifier, establish a working account Planner, resolve the reward-provider contract, then complete simulator, training, evaluation and promotion checks. Do not inherit historical budgets or worker identities as new authorizations.

The RDT EDS+QD research route should continue from main with the accepted frozen-model protocol. The RSI branch does not yet connect that QD archive to its demonstration/training loop, and does not establish RDT RSI, recursive performance improvement or a new success rate.
