# Index-only cap compatibility — CPU preparation

The isolated reader adds `CAPS['index_file'] = 20 * MiB` and uses it only for role `index` at the declared per-file check and bounded physical-read cap. The original accepted reader is untouched. `reader-diff-v1.patch` contains the exact three-line functional delta. The copied CPU boundary is byte-identical (SHA256 `04ace3fea4d5d0c191dc210ba012da9bdc9daf7eaa2d6aecbf70a9186c6ea33b`). Reversing the three edits restores the complete accepted reader SHA256 `38920670ae27e3d5cd468f16ee679d72db83dc2ae1715fa303a08f3c20fe823c`.

All other limits and semantics remain unchanged: other metadata and input manifest 16 MiB, aggregate metadata including manifest 128 MiB, bundle/ZIP/storage/event/call/coverage caps, native bindings, and CPU boundary. This is not an algorithm change or evidence rejection; the root-reported original 16 MiB inventory failure remains historical and no actual index or tensor was read here.

15 focused tests passed on the first run in 0.1486469531 seconds of the cumulative 60-second cap. They cover:

- Index at 16 MiB+1 and exactly 20 MiB accepted; 20 MiB+1 refused before loader/open.
- Every non-index metadata role remains limited to 16 MiB; manifest exact16/16+1 and metadata aggregate exact128/128+1 boundaries unchanged.
- Physical-read branch requests exactly declared bytes+1, rejects short/excess/hash changes, and retains normal metadata caching. Stat size drift and role relabel fail before payload open.
- Full-file reverse source identity, unchanged boundary hash, and a real four-byte owned physical-file read/hash/cache check.

To stay within the preparation's 4 MiB disk bound, large boundary inputs are synthetic in-memory byte streams; controlled stat/open fixtures invoke the normal `Reader.blob` physical-read branch. They do not pretend to be actual large files or actual index semantics. The sole on-disk payload is four synthetic bytes. Numerical/tensor tests were deliberately not repeated because their code is byte-identical.

The unchanged CPU boundary enforced two-CPU affinity, thread limits2, CUDA hidden, 8 GiB RLIMIT_AS and network/process/file-read restrictions. Guard denials were0; Torch was never imported. No actual data, Git history, live source/state/budget, model/API/simulator or GPU work occurred. `cpu-checks-v1.log` and `cpu-results-v1.json` retain the single successful run; there were no failed runs to preserve.

Exact command:

```text
CUDA_VISIBLE_DEVICES='' OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -I -B /home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n26_clean_output_rbf/bounded-witness-index-cap-preparation-v1/run_index_cap_checks_v1.py
```

The delivery manifest hashes all regular files except itself; its external SHA is supplied separately. Real input binding and read release remain root-only, and CPU acceptance does not release another read or GPU execution.
