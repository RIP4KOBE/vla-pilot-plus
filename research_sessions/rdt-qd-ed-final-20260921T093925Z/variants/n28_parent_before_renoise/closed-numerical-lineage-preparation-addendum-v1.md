# Numerical lineage preparation addendum v1 — before any tensor read

The preparation scope remains unchanged. Include two further descriptive, preregistered quantities for every selected witness, all eight cells:

1. Exact native boundary components before/after: x == -1 or x == +1; interior-to-boundary and boundary-to-interior transitions, separate from strictly exterior clipping violations. A box-feasible update can reach the boundary, so zero exterior components does not imply no actuator-limit pressure.
2. Before-population centered RMS radius s = sqrt(mean_i ||x_i - mean_j x_j||_2^2), using the native 16x8x3 prefix converted to CPU FP64 and flattened per row. Report each assigned-delta norm / s and aggregate all rows with sample units. When s is zero, ratios are null and the zero-spread call remains in coverage. No fallback scale.

These are observed update-size descriptions, not task-success proxies or scientific promotion gates. Do not label empirical spread as model uncertainty or prior-support probability. No number is an algorithm parameter and no cutoff may be selected after seeing the values. This addendum authorizes preparation only, not loading tensors or implementing an adaptive update.

