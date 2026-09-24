# N4 conditional protected-phase independent design review

Verdict: **conditional design acceptance; implementation review pending**. The two exact document hashes are recorded in `design-review-v1.json`. No fundamental protocol contradiction was found. This does not authorize promotion, seed disclosure, dispatch, reservation mutation or formal release.

The design retains complete 12-cell Dev promotion, 60/40 protected originals, the fixed 10/20 and 5/10 success gates relative to controls, the single formal candidate latch, private 240/48 accounting, 14/10h protection and the full 1840s dispatch window. Full QD removal is correctly separated from a parent-only ablation: no archive changes both parent/retention behavior and the Stage spread reference; C0-equivalent active behavior must remain disclosed while retaining the fourth formal arm. No extra protected-phase action-difference or ablation-superiority quota is introduced.

Three concrete counterexamples must be rejected by the implementation:

1. A validation recovery has raw bucket `recovery`, but its allowed phase-hour exemption must derive from its verified original validation cell and parent, never the bucket name or a caller assertion. Raw recovery charges remain unchanged, and formal 10h stays protected.
2. Complete accepted validation with N4 below 10/20 or below a control does not pass. It cannot release unused validation hours or admit formal. Require all complete numeric/control/native/source/accounting gates, settled costs and a separate explicit release event; retain original slots and historical charges.
3. An absent seed in the split private ledger is not evidence of historical non-exposure. Bind the approved original exposure sources and their scope, then recheck private reservations. Reused row0 remains disclosed layout reuse, and no replacement seed block is automatic.

The parent subsequently supplied the provisional metadata-review reference `10cf6516514f8616014e8f3bf34f02ccc1ea591e8f3855d5d6eb4c394a672e6c`; this reviewer did not reopen the registry or independently assert current seed availability. Its reported absence of a known c1 seed intersection is conditional and does not establish new layouts.

Scope: only the two design documents and already-reviewed interfaces; zero tests of the new implementation, zero actual episode/native/protected-result reads, zero GPU/model/provider calls and no W/X edits. R3 and E have received the counterexamples. Stable implementation and dependency hashes remain subject to focused independent CPU review.
