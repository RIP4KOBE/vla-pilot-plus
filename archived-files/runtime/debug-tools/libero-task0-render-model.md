# Scene/model coexistence child — prepared, not launched by executor

Script SHA256: `82981d32eaf709ac3c7e4232749b92baeb86994fa98bdd49c81347819d715e70`

Source HEAD: `9b1b4727a50c11ee0a36bb96aa64810807439039`

The new artifact reuses the unchanged, previously passing static Guard
(`237f1c4125488379f2230c3cd854808c3bc330979d09c120ad10dfb7497fd115`).
It does not modify the earlier script/evidence, production code, dependencies,
research state or runner. Six CPU fake tests passed in 0.09 seconds and syntax
compilation passed; no GPU, simulator or model was instantiated during preparation.

The fixed sequence retains one real frozen task0 scene/init row0:

1. Render agentview128 with depth, wrist128 with depth, agentview640 RGB.
2. Load frozen production RDT/T5/SigLIP; call to(cuda:0), eval, post_init with
   adapter=None and batch size 1, reset; render the same three cameras.
3. Process native helper's deterministic synthetic observation/task (seed193735),
   encode text, call original `_predict_unguided(..., B=1)` once, synchronize CUDA0,
   validate finite [1,64,128] output and exact B1 compute; render the three cameras.

There is no added synchronization after loading and no make_current/context repair.
No DINO, Stage, actions, reset or settling transitions are performed. Standard
mj_step1/forward remain counted with unchanged simulation time; mj_step/mj_step2/
MjSim.step are rejected before executing. Total render cap32 includes construction
and set_init; the CPU mock has four internal plus nine explicit renders.

Read-only buffer observations use existing context.con.offWidth/offHeight and
sim.model.vis.global_.offwidth/offheight fields before/after each render. These are
not native EGL queries and do not establish when production first resized a buffer.
RGB shape/dtype/finite/nonuniform and depth finite are required for completion;
pixel hashes are recorded, but equality across boundaries is not a pass criterion.

CLI:

```sh
/home/hynx/miniconda3/envs/vla-pilot/bin/python \
  /mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/runtime/debug-tools/libero-task0-render-model.py \
  --contract <frozen-contract.json> --contract-sha256 <sha256>
```

`libero-task0-render-model-contract-template.json` specifies all field names.
Root fills the reserved resource/output binding and SHA lists, performs one full
checkpoint/encoder/inventory verification, and supplies the frozen GPU3/EGL0/offline
environment. The child verifies contract, runtime, seeds, profile, inventory-file,
policy-configuration and source hashes, and matches actual imported dependency paths
and hashes. It compares policy config against native.policy_configuration and reuses
native.synthetic_observation; it never invokes native.child_probe or its simulator
ban. Source records include current runner.REQUIRED_CODE, native helper and protocol.
The six dependency modules are listed in the script's DEPENDENCY_MODULES constant.

Root owns admission, exclusivity, GPU wall-time accounting, Xid correlation and the
external600-second ceiling. The child also sets a600-second alarm, which cannot
guarantee interruption of blocked native code. There are no retries or hidden
alternative conditions. Files are append-only/new, with native faulthandler stderr.

Evidence contract for the supervisor:

- `scene_model_events.jsonl`: event=`render_exit` with phase names
  `before_model_load`, `after_model_load`, `after_prediction_sync`; each has three
  prescribed cameras on completion. Internal construction/init frames use their
  own phases. Every native/render/major model boundary has entry/exit records.
- event=`prediction_evidence`: raw_prediction_shape/dtype/finite/sha256, compute,
  synthetic_seed and num_inference_steps, emitted after synchronization.
- event=`completed` and `render-model-evidence.json`: resource identity, same
  prediction fields, predict_unguided_invocations=1, camera/native counters,
  mj_step_or_mj_step2_calls=0, action_vectors_executed=0, stage_calls=0,
  dino_model_loads=0, task_success=null and diagnostic_only=true.
- A Python error produces event=`failed`; native abort can leave only an entry.

Limits: production also constructs its adapter before loading the policy, but its
seeded episode reset/init and five settling actions occur after loading; this
diagnostic binds row0 beforehand. Production C0's first inference is guided EDS
with population16, not this single unguided B1 call. The diagnostic also omits
keypoint640 depth/segmentation and other full-pipeline components. A failure boundary
narrows this condition's preceding work without proving causation. A pass only
excludes this narrow coexistence condition as sufficient to reproduce the fault;
it establishes neither episode safety nor scientific improvement or success rate.
