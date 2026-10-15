# Task1 completed matched N21/N22 trace contrast

Both task1 arms completed720 action steps and passed their independent native audit; both failed the task. The read-only comparison verifies referenced bundle hashes and matches task/seed/init identities. All66 canonical pools, raw provider scores and effective scores compare equal in native dtype with `torch.equal`; all90 decoded action chunks, all compared parent fingerprints and Stage bindings are unchanged. Six guided decisions occur in both runs. The additional continuous-close condition has no observed decision effect on this path.

This differs from task0, where the first changed executed chunk was at step24 after a changed effective score and parent allocation. Neither comparison establishes task benefit: task0 and task1 both fail in both arms. Positive shaping/rank counters relative to raw provider quality must not be mistaken for differences between N21 and N22. Task1 equality is a measured path-specific result, not a claim that the methods are equivalent on all tasks or that future Stage calls are deterministic.

Source: `task1-trace-contrast-result-v1.json`, SHA256 `1dcdb35abcbef1758a05ba925bfbebb4d0c54dd2b0730090910a99cb314eeec9`. No new simulation, provider/model call, GPU dispatch or scientific-source change. The frozen40-cell N22 experiment continues under its original futility/promotion rule.
