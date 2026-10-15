# Native PyTorch UUID correction — CPU evidence only

Commit `c11f436887d7d631f0cfb6341ba6999fc92275b9` preserves the previous `675c2f4d07e787a7e160a2a26312c8ab2e4a19f6` source. Four files change: audit-backend identity serialization, worker receipt metadata checks, v2 preflight diagnostic persistence, and focused backend tests. Admission/authority/limits, scientific source, profiles, arithmetic, corpus and tolerances are unchanged by this commit.

The defect is that PyTorch 2.7.1 exposes `torch._C._CUuuid`, not a Python string. The previous correction accepted historical serialized strings but rejected the native object. CPU import introspection confirmed this installed native class and its public `bytes` property with CUDA uninitialized. The [official v2.7.1 CUDA binding](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/csrc/cuda/Module.cpp) registers the native class, sixteen-byte representation and string formatter (lines 991–999), and binds the device `uuid` property to the native value (1038–1039).

Only strings or the exact installed native class are accepted. Native values are serialized through their public string conversion, then checked against all sixteen bytes. Generic objects, forged class names, malformed or inconsistent byte/string values and wrong devices fail. JSON-safe raw UUID, public type, optional byte hex and canonical GPU-prefixed identity are retained. Worker receipt verification checks these representations. Preflight failures retain only public identity diagnostics: expected GPU/UUID, sanitized mask, count, current logical device, type and parsed identity or malformed marker. No extra CUDA observation/retry is introduced.

The failed workers did not record their actual raw UUID. The historical accounted probe recorded a bare serialized UUID; the static binding and faithful native-type fixture reproduce the type defect. This is not proof of either failed worker's live UUID, and not proof that the corrected code has passed actual GPU arithmetic.

Reproducible command (from this implementation worktree):

```sh
PYTHONPATH=.. OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 /home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -p n23_v2_cpu_pathguard_v1 -q tests/test_qd_ed_n23_backend.py --basetemp=../n23-v2-guarded-fixtures-native-uuid-v1 > ../cpu-native-uuid-v1.log 2>&1
```

Result: **137 passed in 32.58s**, path guard reports zero blocked reads. The native fixture replaces the exact installed class symbol with a faithful public str/16-byte class because a CUDA-free production native instance was not constructed. Device API calls are mocked, actual arithmetic tests remain CPU. Tests cover string/prefixed/case/native forms, arbitrary/forged objects, byte agreement, all ownership checks, JSON serialization, C0/N23 worker receipt consistency and persisted pre-arithmetic failure diagnostics. No GPU/provider/model/simulator or actual outcome/ledger read occurred.

Both previous attempts remain invalid and charged. This correction alone grants no further execution. The newly frozen second engineering exception is a subsequent, separate CPU admission task; root alone may review/adopt/integrate/release it.
