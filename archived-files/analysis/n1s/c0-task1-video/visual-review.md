# C0 task1 failure observation — N1S

Complete valid failure:720steps/196.3393s,3/3 successful Stage calls,3guided and87unguided chunks. Source artifact attempt4e1defc31838. Saved initial/query/end frames are indexed by manifest.json.

Stage events:step24 stage1/guidanceOFF because gripper close to cream cheese;step40 stage2/guidanceOFF;step112 stage1/guidanceOFF, explicitly identifying cream cheese outside/right of basket and need to regrasp. No later Stage event. Frame112 shows open gripper near the right side of the basket; the target object is visible outside/right. Frame719 still shows the object outside and an open gripper above the basket.

This is a complete, parseable Stage response sequence, not a transport-format fault or a declaration that the task was complete. ED was inactive for87/90chunks. Long-lived guidanceOFF and lack of a subsequent re-query are observed controller behavior; the cause of failed placement and recovery is not isolated by this single run. Compare matched Q0/N1task1, report activation exposure separately, and retain this as a potential common-controller limitation. Frozen N1S conditions and promotion gates remain the same.
