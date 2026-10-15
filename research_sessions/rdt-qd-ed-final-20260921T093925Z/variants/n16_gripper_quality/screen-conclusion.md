# N16 near-target close quality: terminal-pool screen only

The SHA-verified matched-Dev terminal-population screen (`readonly_screen.py`) asks whether any candidate combines a positive gripper command and projected EEF reach within 2 cm at the same action step. This is a fixed descriptive threshold from the earlier four-path audit, not a measured grasp threshold or a new simulator result.

In N7, such candidates exist at task 0 steps 296/304/512, task 3 steps 624/632, and never in its guided task 6 or task 9 decisions. N7 selected them at two of the three task-0 opportunities and neither task-3 opportunity. N11 selected one at task 3 step 16 and succeeded; it also selected one at task 6 step 96 and failed. Thus projected near-close status is neither sufficient nor necessary for full-episode success. A terminal-only selection adjustment cannot repair the early task-3 path or task 9 from those exposed pools. A proposed archive/ED quality change could alter candidate generation, but that unexecuted effect is unknown; the present evidence does not justify freezing a bonus strength or spending the remaining Dev budget on it.

No N16 algorithm was implemented or dispatched. The executable screen and JSON are retained as negative evidence, without accessing validation or formal identities.
