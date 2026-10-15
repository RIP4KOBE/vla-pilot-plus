# Task3: one score change without an executed-action change

Both N21 and N22 task3 attempts completed native-valid failures. Their110 corresponding canonical batches have identical native candidate pools and raw provider scores. The hold condition changes one candidate's effective quality at step624, iteration5. All compared parent fingerprints and all90 decoded action chunks remain equal. Guidance activity also remains equal.

The Stage binding at step624 has a different archive cost-spread scale, while the selected raw reward, Stage initialization reward and normalized reward compare equal. No changed executed action follows. Thus this path demonstrates a local scoring effect with no observed control or task benefit; a nonzero shaping count would overstate its practical effect if presented alone.

Evidence: `task3-trace-contrast-result-v1.json`, SHA256 `046755ebecd9c13b9a9584b27c2fe0e0a3533a3992aa66a2eee3cfce0ad52f59`, produced by the sibling hashed read-only reader from accepted native audits and verified tensor-bundle references. This is a completed exposed-Dev path comparison, with no new simulator, model, provider or GPU call. The four complete task quadruples are16/40 planned cells and all failures; the frozen cohort continues task4.
