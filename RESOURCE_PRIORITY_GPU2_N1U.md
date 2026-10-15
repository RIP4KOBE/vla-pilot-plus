# CURRENT — N1W GPU2 queue launched

2026-09-24T07:19:01.596388+00:00: approvedN1W30primary+max5typedStage-timeout recoveries,max1percell. QueuePID3262566,startticks9715863,boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. GPU2/EGL1only,sharedsingleworker,idle120s.237CPUtestspassed6.85s;fullsource/model/input/providercheckspassed33.98s. NoextraGPUprobe/liveStagecall. Source `c75ff0f4eb4c8ae23dfc41b5f7449e99c06ff9ee`,plan `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/data/qd-ed-n1w-approved-plan.json` SHA `fa3408e75f49385178987db533b9d00d4fefb8f1dfa24647fd245cf9fe5980c2`,runtimeSHA `7de5b438a09b10b9c44db5e5508dac960a80724c279ed9bd358ba62252f3bc39`.

Stagecondition codex_login_astra_low_json_transport_fallback_180s_v1, publicpolicySHA 47b97a211a069a6f104f7928e32aeaa0f72031e7a948ee320ee1ef3416fdd6d2. OldN1Vclosedandunchanged. First2N1implementationchecks countin30,notasuccessscreen. PreserveHEAD/code/runtime/planbyteswhilequeuealive. Sharedstart115attempts/16.1696985304GPUh,caps13/125/60/40/12,total250/48h,protected60/40attempts14/10h. GPU3held. Status `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/runtime/n1w-gpu2/status.json`;livehelper `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/runtime/n1w_progress.py`. Estimated6–8hpluswait/recovery,subjecttoprotectedresources.

---

# CURRENT — N1W approved; preparation underway

2026-09-24T07:15:08.966777+00:00: Latest user approval authorizes N1W onGPU2,30primary+max5Stage-timeout recoveries,onepercell. Shared250/48h;caps13/125/60/40/12;protected60/40attempts14/10h. Authorization /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/resource/n1w-approved/authorization.json SHA 445306c7023e0cba6a5affeaf2afab5af91bb393b9b39bf64341ba17b2c11258. ExistingN1Vremainsclosedandunchanged. NewStageacceptanceisapprovedbutnotyetdispatched;CPUtests/freezeinprogress. Do not resume competingGPU3queues.

---

# CURRENT — N1V closed incomplete; proposed parser fix is inactive

2026-09-24T07:02:43.337384+00:00: N1V1/30 dispatched,0scientifically valid,1invalid,0recoveries,29undispatched; N1untested. Atstep152 the5thStagecall completed97.145s withJSON/usage but erroritem causedcodex_unexpected_item. Notcodex_timeout; noautomaticrecovery. GPU2worker/queue exited,sharedlockreleased,Xidempty. Shared115/250attempts,16.1696985304/48GPUh; caps13/124/60/40/13unchanged;100attempts/24hprotected.

Executed sourcec0a2b2a851a1b35ccd99d5bec5b4d4ddaeb5d394,planSHAd91ef55173c76c1f2df308f57912a515fa3e7006d23dbf0d255f4aa3e7e7fefc. Report `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/docs/03_evidence/qd_ed_n1v/2026-09-24-final-report.md`; audit `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/n1v/final-audit.json`. Post-close opt-inparserfix passed202CPUtests; oldpolicyunchanged,newpolicystillrejectedbyactiveN1Vrunner. NoGPU/liveStagecall added. N1Wproposal `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/experiments/iteration_001_execution_intent/n1w-transport-fallback-proposal.md` needsexplicitapproval before acceptance-policy/bucket changes: same250/48h,transfer1recoverytoDev,new30primary+max5timeoutrecoveries. No oldoutcome relabeling orpooling. This notice supersedes activeN1V/pendingN1Vbudget text below.

---

# CURRENT — N1V GPU2 approved, implementation/preflight underway

Latest direct user instruction: “批准 N1V 方案并继续 GPU2 实验（建议）”. Approval /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/resource/n1v-approved/authorization.json SHA 531c66107cafe3ad650b974f459f0f4a3ddc085042dd8354d7e59b562af87015. Shared caps13/124/60/40/13, total250attempts/48GPUh; validation60+14h/formal40+10h protected. This supersedes the earlier 06:30 GPU3/original-cap notice prospectively. Historical N4 and N1U results remain unchanged. GPU3 remains held; N1V will hold the shared single-worker lease. Source/protocol CPU tests and freeze precede dispatch.

---

CURRENT USER OVERRIDE — see RESOURCE_PRIORITY_USER_GPU3_N4_20260924.md; authorization 199f5621939fe0ca23fc779abf62085120e4b7c2032ef19144df593778c41281. Older GPU2 priority/current-cap claims below are historical and superseded.

# CURRENT — Stage diagnostics complete; N1V proposal awaits approval

2026-09-24T04:55:56.644134+00:00: User asked to continue. CPU observability repair committed337196e8672a2309b06d221c9f3436bc81cf9083;153tests passed6.63s. Six prespecified CPU-only live calls all completed with usage,10.03–27.31s,112.19s total,58746input/377output tokens. No GPU2 episode added, no Stage/model/timeout/acceptance changes. Historical timeout not reproduced; root cause and long-run reliability remain unproven. Evidence `/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-gpu6-20260922T063626Z/analysis/stage-transport-diagnostics-20260924/audit.json`. N1U remains closed with N1 untested; no old result relabeled or pooled.

Existing user GPU2 priority honored: GPU3 N4 supervisor3021562 paused at04:52:25UTC AFTER C0/task0 and Q0/task0 completed and their audits finished; no active episode aborted. Selected N4/task0 remains undispatched. Queue exited, shared runner lock available. Pause proof resource/gpu3-priority-boundary-pause-20260924/status.json and verification.json. Do not automatically resume the GPU3 queue or launch its remaining plan while this resource hold is active.

Budget synchronization defect identified: prior approved transfer was only reflected in GPU2 worktree; parent retained old20/100/60/40/20 caps. Both state files now reflect already-approved11/122/60/40/7, global240/48unchanged. Ledger actual baseline13 exceeds that prior cap11 by2; preserve this actual use, no reclassification. Shared114attempts (baseline13,development94,recovery7),16.081373451GPUh,zero running. After validation/formal100attempts/24h protected, effective remaining development/recovery capacity is26attempts/7.918626549GPUh. Source caps in older parent may be stricter; they do not grant extra authority.

Concrete N1V proposal NOT approved/applied yet: `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/experiments/iteration_001_execution_intent/n1v-bounded-recovery-proposal.md`. Request global240->250attempts, still48GPUh/protectedvalidation60+14h/formal40+10h; caps13/124/60/40/13 fund30new main cells plus at most6prospectively eligible Stage-timeout recovery episodes, max1percell, no legal-task-failure retry. New30 task-interleaved C0/Q0/N1 cells, same originalalgorithm/seeds/commonStage180, no application retries and no old-cohort pooling. Requires explicit approval before changing hard total/recovery rules or GPU dispatch. Async question pending; do not treat silence as approval. Full follow-up report: `/home/hynx/VLA-Pilot++/.worktree/exp/rdt-qd-ed-gpu6-20260922T063626Z/docs/03_evidence/qd_ed_n1u/2026-09-24-stage-diagnostics-followup.md`.

---

