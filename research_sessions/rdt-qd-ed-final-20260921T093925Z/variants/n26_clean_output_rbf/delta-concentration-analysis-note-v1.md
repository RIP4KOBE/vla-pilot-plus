# Conditional descriptive analysis of captured update concentration

This note selects no successor and releases no data read. N26 Dev is still running. It supplements the existing numerical questions without changing any frozen source, protocol or accepted reader.

After accepted terminal reconstruction and a separate bounded witness read, the already exported 16 per-particle `delta.l2` values can characterize the actual stored model-output update. For each covered call let `e_i = delta.l2[i]^2`, `E = sum(e_i)`, and, when `E > 0`, `p_i = e_i/E`. Report:

- effective particle participation `1 / sum(p_i^2)` (1 for a single nonzero row, 16 for equal energy in all rows);
- largest two rows' share of total squared-update magnitude;
- number of rows with exactly zero measured update.

For an all-zero update, participation and shares are undefined; retain the call and its zero-update status. Preserve the complete accepted first-valid N25/N26 coverage, including failed tasks and zero-guided episodes. Summarize by arm and initial/rollout phase, without selecting favorable calls or treating calls as independent tasks. No additional tensor, model, API or simulator access is needed beyond the previously proposed bounded read and its scalar output.

These quantities describe scheduler-before `after-before`, not the recorded operand, gradient, final selected action or physical displacement. Concentration may arise from legitimate pairwise geometry, clipping support, native rounding or their interaction; it is not automatically a defect. Equal participation is not an efficacy target. Together with absorption and range-transition statistics, it may distinguish a globally nonzero update that affects few particles from one spread over the population. A new algorithm still requires a falsifiable task-related hypothesis and prospective matched evaluation.
