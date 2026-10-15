# N29 phase-A native input-domain clarification v1

This root clarification precedes implementation/test execution and leaves the frozen real-arithmetic formula unchanged. It supplements hypothesis-and-cpu-phase-a-v1.md, following executor static critique. It is an ordinary CPU design decision under the existing task, not a GPU/episode release.

1. Check the original native raw operand P's nonzero support against strict -1<B<1 before scaling. A zero beta must not hide an illegal original operand.
2. If a row of native P contains nonzero values but the prescribed FP32 square/sum/sqrt produces n_i==0, reject as norm-underflow input. Do not introduce epsilon or retain the unscaled nonzero operand through the n_i==0 branch.
3. If the computed FP32 centered before matrix contains a nonzero value but the prescribed FP32 RMS computation gives s==0, reject as spread-underflow input. Genuinely all-zero centered input keeps the specified zero-spread semantics.
4. All overflow/nonfinite intermediate quantities reject rather than silently fall back. These finite-precision input-domain restrictions may create a new runtime failure and must remain visible in implementation, tests and later protocol. They are not retrospective correctness claims about prior runs.

Retain critique: duplicate parents can shrink empirical spread, outliers can enlarge it, and true zero spread suppresses this repulsion while original renoise remains. Empirical spread is not uncertainty calibration; N27 task2 success remains counterevidence against a universal harm claim. Root has authorized continuing phase-A preparation without further routine-choice questions.

