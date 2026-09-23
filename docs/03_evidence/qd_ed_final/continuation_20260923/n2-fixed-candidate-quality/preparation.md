# CPU preparation, no recorded-candidate execution

The tool and protocol are prospectively defined. No actual runtime tensor bundle was read and no real Q8 value was computed during preparation. Existing checker/analyzer source, frozen N2 protocol and the implementation helper were read. `manifest-templates.json` includes exact prior membership report references and helper bytes at preparation time; it is deliberately missing root execution authorization. Root must verify the final helper SHA after implementation tests and bind it in the separate authorization before any actual analysis.

Validation command:

```bash
CUDA_VISIBLE_DEVICES='' /home/hynx/miniconda3/envs/vla-pilot/bin/python -m unittest discover -s docs/03_evidence/qd_ed_final/continuation_20260923/n2-fixed-candidate-quality -p test_fixed_pool.py -v
```

Result: **11 tests passed**, 0.117 seconds test body (1.29 seconds process). CPU synthetic tensors are BF16. They pass through the original frozen history and membership helpers plus the new reranker using the actual N2 pure helper. Coverage includes C0 last-batch lineage; Q0 all-occurrence agreement and differing geometry/old-quality rejection; complete tied maxima; a mixed tie that changes deterministic representative without satisfying activity; signed-zero native-byte mismatch despite torch.equal; original-quality tradeoff; nonzero reviewed target index; A/non-A/Unknown strata inclusion; auxiliary score rejection; helper dtype/mutation rejection; selected membership tampering; unchanged Torch CPU RNG; and read authorization rejection before a missing manifest can be opened.

No provider, projector, model, simulator, real episode, or CUDA initialization was involved. CPU helper arithmetic and native storage are validated; GPU bitwise equivalence is not. Actual record compatibility remains subject to fresh audit and every join assertion. The old Q0 archive did not record unique insertion ancestry; agreement of every exact native match is required instead of inventing ancestry.

The activity gate is a fixed-pool necessary engineering check, not success evidence or promotion. Original search proposals would change under N2. All tied maxima and original quality costs remain visible, and no full-archive replay is implemented.
