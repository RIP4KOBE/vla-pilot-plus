# Review v1 is not the final activity-gate review

After review-v1 was written, root identified a stronger consumer-association requirement: canonical cross-cell comparator changes need not be comparisons used by the actual QD selector. The v1 positive conclusion therefore does not establish that the activity gate is sufficient. Its fixed event-count/order reproductions and CPU test results remain valid.

The producer is narrowing the activity witness to the actual final global-selection pool. W `core/qd_ed.py:547` selects across that pool, while `core/rdt_policy_steer.py:6665` obtains its exact native rows and selected member. Candidate comparisons unrelated to the selected maximum must remain descriptive. A follow-up review-v2 will check the revised source and focused synthetic negative cases before any actual read authorization.

No N3 scientific data was read for either review or this clarification. No execution is authorized by these artifacts.
