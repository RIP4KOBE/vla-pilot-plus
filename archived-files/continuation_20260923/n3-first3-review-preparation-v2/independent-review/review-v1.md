# N3 first-three independent review

PASS within the source-only and synthetic CPU scope. No actual N3 output was read, and this review grants no execution authority.

The original reader accepted three malformed traces: an extra duplicate archive allocation, an allocation moved after final selection, and initial effective quality moved after final selection. The revised reader rejects all three. Its exact-count and causal-order checks match the production logging sequence. The inherited reporter/auditor still supplies accepted representative, source/plan, native previous-feedback and complete metric-count gates.

Validation: **39 CPU tests passed in 1.91 s** (32 author + 7 independent, partly overlapping). Additional cases cover unmodified full trace, BF16/FP32 native-identity mismatch, a whole-search common scalar offset, and duplicate native tied maxima.

Reviewed reader SHA: `207561761dfb0ec5d0c004cbd2c652f48aa5a19581a244c7eaed20312570bab7`. Protocol SHA: `3bcb283e71b48ba91953fee676751bf3b67d8667fb7f330cd5b120e677fe3fe8`. Freeze SHA: `1d219effe23c9f78bfd0e0d27d354e6b9894ffd62db459b789f7a99f42efb054`. All eight frozen files and all eleven scientific source files were verified against W `bd618b931eb9d8fc2c01b978c4ef220c9bb03889`; metadata report/plan hashes are listed in review-v1.json for separate actual authorization.

No remaining blocker found in this bounded review. This is not proof of online activity or performance. Actual normalized Stage input remains Unknown; ordering changes do not prove changed archive membership, future proposals or physical benefit.
