# Passive N7 diagnostic stopped after task3

Report SHA-256: `ca5bb714dfca5d4ef8aa7322eb639087472e42612d2923aa7e80a52ef437c744`. Frozen plan SHA-256: `c068373479272eb682d774192126ed7d09ddc36b1743548960d823ea1705dc80`. Both repeats ran serially on GPU3.

| Task | Original → repeat outcome | Frozen Stage valid | Guided tracked | Stable adjacent pairs | ≥1 cm shifts (same original steps) | Immediate same-stage next guided | Action hashes equal |
| ---: | :---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0 → 0 | yes | 17/17 | 17 | 5 (5) | 3 | 90/90 |
| 3 | 0 → 0 | no | 13/13 | 13 | 6 (2) | 2 | 3/90 |

Task0 replicated all 90 action fingerprints and 17 selected-latent fingerprints from the original N7 Dev run. Task3 had a Codex Stage stream/item error at global step 24. Although its 90 decision contexts and all native bundles audit cleanly, the frozen transport gate marks the full cell invalid. Its six tracked shifts cannot count toward the design gate.

Two Dev dispatches consumed 822.954 GPU-process seconds (0.228598 h). The private ledger and state reconcile at 184 total, 97 development attempts, and 24.179518/48 GPUh. No retry or task6/9 dispatch occurred; validation and formal splits remained closed.

**Design gate not met:** only task0 is scientifically valid. No N10 algorithm is promoted from this diagnostic. Object-pose tracking status does not prove physical contact or a causal counterfactual.
