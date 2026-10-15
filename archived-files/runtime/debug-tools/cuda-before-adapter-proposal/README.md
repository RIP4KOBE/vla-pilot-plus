# Unapplied CUDA-before-adapter candidate

This candidate adds exactly one explicit `torch.cuda.init()` for an RDT policy whose configured device type is CUDA, immediately before `Main` creates the adapter. It keeps the original seed calls, environment configuration, adapter/model loading order, loader arguments, post-init, eval, and component initialization. No tensor, warmup, inference, synchronization, device selection, package, or configuration changes are included. The CUDA initialization exception propagates before any adapter or model is created. Other policy types and the RDT CPU branch do not make the added call.

`cuda-before-adapter.patch` is not applied. `metadata.json` records the base commit and source/candidate/patch hashes. The worktree's `main.py` remains unchanged. This is a candidate for review after the separately authorized ordering probe; it is not evidence of a graphics-fault fix.

## Existing seed calls do not ensure CUDA initialization

In the reviewed worktree `main.py:575–579` calls NumPy seed, `torch.manual_seed`, and `torch.cuda.manual_seed` before `create_adapter` at line 600. It does not call `torch.cuda.init` there or allocate a CUDA tensor.

Installed PyTorch source under `/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages` shows:

- `torch/random.py:45–46`: `torch.manual_seed` invokes `cuda.manual_seed_all`.
- `torch/cuda/random.py:109,128`: the CUDA seed functions use `_lazy_call`.
- `torch/cuda/__init__.py:299–314`: when CUDA is not initialized, `_lazy_call` queues the seed callbacks.
- `torch/cuda/__init__.py:328–339`: `init()` invokes `_lazy_init`; an already initialized CUDA state is accepted without repeated initialization.

Thus the existing seed calls are not proof that CUDA was initialized before creating an EGL renderer. This static audit does not establish the live CUDA state after every transitive import and does not claim that CUDA initialization is the causal fault mechanism.

## CPU verification

Run from this directory:

```text
/home/hynx/miniconda3/envs/vla-pilot/bin/python -m pytest -q -p no:cacheprovider test_cuda_before_adapter.py
```

Observed result: **3 passed in 0.14s**. The tests reconstruct the exact candidate from the patch and verify its hash, compile the actual complete `Main.__init__` AST, and mock all model/native/environment operations. They import neither PyTorch nor the production application. Checks cover:

- Original seed calls and arguments, then CUDA init, then exactly one adapter followed by the original loader/post-init order and arguments.
- Identical initialization exception propagates; neither adapter nor model is created.
- RDT CPU, diffusion CUDA, and PI05 CPU preserve their complete original observed call sequence.

`git apply --check` passed; this validation does not apply the patch. No GPU operation, native query, network call, or scientific experiment was performed. Mock tests cannot establish native safety, actual EGL/CUDA ordering, or successful rendering.
