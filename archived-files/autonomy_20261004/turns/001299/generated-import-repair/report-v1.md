# Arbor node15.6 bounded CPU engineering report

Committed `e4914cb4baf91bbb66f91e25584652eb273b8904` on `exp/n36r3-generated-import-001299` (base `30c6321715df86c5bab623db607bab2811aed56d`). The precise Torch generated import incompatibility is repaired. **Full worker receipt consumption remains gated by a separate existing frozen-alias failure. Release remains disabled.**

Torch's installed instantiator adds its owned temporary directory to `sys.path`; N36 previously rejected that path before generated provenance could be checked. The repair reuses pinned owner/template/content and TemporaryDirectory checks, binds executed owner/template hashes, restricts the directory to the one generated file, guards source/native/namespace discovery, and joins generated execution origins to the existing retained runtime receipt. Full inventory scans remain enabled at attestation. No blanket temporary-directory exemption was added.

54 unique focused tests passed across the final relevant runs: 53 existing provenance/search tests in `tests-3.log`, and the real production-flag bootstrap regression in `tests-7.log`. The real test rejects 11 live faults and six retained-receipt faults, checks CUDA remains uninitialized, and verifies focused generated evidence after temporary-directory cleanup. Exact commands, environments, outputs and elapsed times are in `test-commands-v1.json`. All failed development runs are retained. Measured pytest time: 112.64 s; conservative accounting including uninstrumented smoke runs: 132.64 s / 180 s.

The full live source attestor and runtime receipt producer pass. The full source receipt consumer reports:

`N36 module missing executable receipt: /home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/importlib/_bootstrap.py`

The final CPU receipt artifact retains the complete producer evidence and this error. Only the focused consumer fixture selects generated provenance plus the existing mandatory `os.path` proof; this is explicitly **not** a full runtime acceptance claim. No frozen-alias/provenance check was relaxed.

Only five engineering/test files changed; all other tracked paths and scientific settings match the base. No historical provenance was recreated, no manifests were refreshed, and no GPU, network, simulator, provider, child agent or release work ran. Working tree is clean.

Source delta SHA-256: `0db6142f309261ed60e6936f9de53cb2bd00aca67d1a843c761976a94f0f72c5`. Per-file before/after and individual diff hashes are in `source-delta-hashes.json`; the exact patch is `source-delta.patch`.

Remaining gates: independent engineering review; resolution of the full-consumer frozen-alias failure; then coordinator-controlled fresh recovery identity/inventories/plan/release. No scientific promotion is proposed.
