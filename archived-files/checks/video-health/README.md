# Completed episode video delivery checks

Run from the repository root while the recorded source remains frozen:

```sh
CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python .worktrees/exp/steering-integration/checks/audit_completed_videos.py
```

The helper reads all three final cohorts and only processes tasks with completed compute records plus a unique nonempty terminal agentview video. It never reads an unfinished episode video. Existing reports are reused only while video/compute/action hashes, method/task/episode/seed/path, source fingerprint, and the recorded checker identity match. The original checker source is retained under `helper-source/`; its reports stay immutable and each index item retains its actual checker SHA. Unknown checker versions are rejected. New reports and the index are written here; raw runs and source files are not changed.

`index.json` and `index.md` list absolute and run-relative video paths, SHA256, task/seed/outcome, full decoded frame count, resolution, frame rate, duration, and report hashes. A valid file must pass ffprobe, decode fully with CPU ffmpeg and error escalation, and have one frame per action at the recorder's frozen 10 fps. A broad 64–4096 pixel even-dimension check catches implausible resolution; actual dimensions are reported. Pixel semantics and overlays are not independently assessed.

This is a delivery check. It never changes task success or scientific validity. `all_30_videos_indexed` and `all_indexed_delivery_valid` must both be true for a complete healthy video delivery; pending entries remain explicit. `validation.json` records the first real 11-video check; `validation-v2.json` adds cache ownership checks and records four focused corruption tests. Re-run at task milestones and once after all three cohorts finish to complete the 30-video index. Run final frozen evidence aggregation before any post-cohort source patch.
