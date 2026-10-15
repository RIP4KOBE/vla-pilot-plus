# Fixed 6 cm projected contact-entry audit

This Dev-only screen applies one prespecified rule to the 33 SHA-verified N7 guided decisions: on the selected terminal candidate's projected nine-point EEF path, find the first transition from outside to inside a 6 cm 3D radius around target keypoint 0. Its length is the Euclidean EEF displacement during that projected action step; the gripper sign is the selected decoded command for the same step. If there is no outside→inside transition, entry length and sign are **Unknown**. `audit_contact_entry.py` and `contact-entry-audit-v1.json` contain the reproducible calculation and per-decision rows.

| Subsequent target-keypoint shift | Decisions | Entry observed | Already inside at projected start | Mean entry step length when observed | Gripper +1 / -1 at entry |
| --- | ---: | ---: | ---: | ---: | ---: |
| ≥1 cm | 7 | 3 | 4 | 2.47 cm | 2 / 1 |
| <1 cm | 26 | 13 | 4 | 2.08 cm | 4 / 9 |

All four shifted decisions with Unknown entry started **inside** the 6 cm projected radius. Among the three shifted decisions with a defined entry, step lengths were 1.21, 2.62 and 3.59 cm, overlapping the 0.88–4.13 cm range of the 13 non-shift decisions with defined entry. The group mean difference is only 0.39 cm and is based on correlated chunks from four episodes. The +1 sign is a commanded gripper state, not measured contact. This fixed feature does not cleanly discriminate subsequent target motion; the chosen entry definition is unavailable for most shifted chunks.

For each of the seven shift decisions, the script also inspects its other 15 terminal candidates, using the same projected path and native provider score. An alternative qualifies only if its entry step is strictly shorter and its native score is no more than 0.02 below the selected score. Four decisions have Unknown selected entry, so no lower-entry comparison is defined. Of the remaining three, **one** has a qualifying alternative: task 3, step 8, candidate 1 has projected entry length 0.80 cm versus the selected 1.21 cm and score lower by 0.00177. Six of 13 non-shift decisions with defined entry also have qualifying shorter alternatives, so structural availability is not specific to perturbation. No alternative was executed; its task outcome is Unknown.

The projected path and keypoint are already policy-visible inputs, not measured EEF–object contact. Keypoint tracking validity is absent from these bundles, and no physical counterfactual exists. This audit gives weak support for a standalone entry-step penalty as N10, especially after N9's unsuccessful lateral-sweep penalty. It leaves open a different hypothesis based on verified chunk-boundary feedback and a stable cross-chunk descriptor, which would need its own frozen online test.
