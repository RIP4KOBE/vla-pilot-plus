These twenty small files contain Python, NumPy, Torch CPU and Torch CUDA RNG
states captured during the accepted historical-initialization calibration.
They contain no environment states, actions, Stage replies, or reward functions.

`fixture-manifest.json` is byte-identical to the calibration manifest and already
uses relative `fixtures/` paths. Its SHA-256 is
`628c429d457def157c9163be94a1202721673f97f1e43aa6446e5a06889c6043`.
`audit.json` is the original hash-bound calibration audit. Its historical replay
result is provenance for initialization, not a new online performance result.

Run `python scripts/prepare_steering_assets.py verify-rng` from the repository
root for a CPU-only integrity check. Runtime restoration additionally checks
task, seed, phase, CUDA-stream count and post-restore state signatures. Each
task restores `prepare` immediately before task preparation and `rollout`
immediately before `_run_episode`, with `episode_policy_rng_mode=continuous`.
The mode is explicitly named `historical_fixture_v1`; ordinary runs need not use
it. Relocating this whole directory does not require changing the manifest hash.

Task 0–9 seeds: 44, 235, 43, 546, 6, 621, 197, 87, 151, 548.
