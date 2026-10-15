# CPU startup preflight v2 — passed within its limited scope

The single amended run passed Torch import and synthetic CPU BF16 clamp/cumsum plus FP32 norm checks with **zero guard rejections**. CPU and interop threads were both 2, CUDA was invisible and uninitialized, and research payload reads were zero. Runtime was **1.158809794 seconds**; adding the preserved first failed startup gives **2.340774762 seconds** of the shared 30-second envelope.

Only the four exact resolved interpreter/tqdm metadata paths in the root-frozen amendment were added to the read-only allowlist. The existing owned `tempfile.tempdir` configuration, other file/network/process/CUDA guards, synthetic operations and lack of temporary-directory write permission were retained. The exact metadata exception was used four times in this run; there was no general dependency-root permission expansion.

The original v1 strict-guard failure, script, input manifest, log and closure remain unchanged. New v2 script, manifest, diff, output and closure are separately hash-bound. The original success result samples its cumulative timer slightly before its final elapsed field; this closure reports the sum of the two final elapsed values.

**This pass establishes CPU startup and nine literal synthetic-value operations only.** It establishes no CUDA arithmetic parity, native payload associations, geometry comparison, scientific improvement or full extractor readiness. No .pt, attempt, metrics or closed research-result data was read. No study source/state/ledger was modified, and the old geometry scope remains closed. No new geometry run was authorized or performed.
