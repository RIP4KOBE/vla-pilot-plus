"""Format the already frozen reader output only; never open attempt roots."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path

BASE=Path(__file__).parent
OUT=BASE/'output-v1'
assert os.environ.get('CUDA_VISIBLE_DEVICES') == ''
reader=BASE/'read_closed_loop.py'
assert hashlib.sha256(reader.read_bytes()).hexdigest() == '1212c3c9675403dc0e8f3b97948ab8d6d9a5f873ccfa615564041da3fe5c309f'
spec=importlib.util.spec_from_file_location('frozen_pure_reader_helpers',reader)
r=importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
assert not r.torch.cuda.is_initialized()
source=OUT/'closed-loop-sequence.json'
data=source.read_bytes()
assert hashlib.sha256(data).hexdigest() == 'b8a7c7bce23975ff1f421c7e7cd87eccc7d2517549301f4a81fb34189d1affa4'
arms=json.loads(data)['arms']
n2=next(a for a in arms if a['arm']=='N2')
off=n2['summary']['first_on_to_off_step']
steps=n2['actual_steps']
post=r.motion_summary([s for s in steps if s['global_step']>=off],next(s for s in steps if s['global_step']==off-1))
keypoints=[]
for arm in arms:
    first,last=arm['decisions'][0],arm['decisions'][-1]
    links=[d['keypoint_link_from_previous'] for d in arm['decisions'][1:]]
    assert all(d['status']=='recorded_same_index_only' for d in links)
    keypoints.append({'arm':arm['arm'],'boundary_interval':[first['global_step'],last['global_step']],
        'same_index_links':len(links),'meaning':'recorded tracker-array coordinates; not verified object attachment, nonfallback or target',
        'net_displacement_m':[r.distance(a,b) for a,b in zip(first['keypoints']['value'],last['keypoints']['value'])],
        'sampled_path_length_m':[sum(d['displacement_m'][i] for d in links) for i in range(first['keypoints']['shape'][0])]})
extract={'input_sha256':hashlib.sha256(data).hexdigest(),'formatter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    'n2_complete_post_off_motion':post,'keypoint_same_index_descriptions':keypoints,
    'cuda_initialized':r.torch.cuda.is_initialized(),'reads':'already generated authorized sequence only; no new attempt reads'}
r.xjson(OUT/'descriptive-extract-v1.json',extract)
text='''# Task0 post-outcome sequence findings

This is descriptive Dev exploration of exactly the three authorized, completed task0 arms. It does not change N2, the ongoing cohort or any acceptance rule. All three fresh frozen-source audits accepted complete evidence; each has 90 decisions and 720 actions. All three original outcomes are condition-valid task failures, with the last action returning terminated=false, truncated=true, success=false. CPU only; CUDA remained uninitialized. No model/provider/projector/simulator call, target map, image, free-text Stage reply, invalid attempt or other episode was used.

The data do **not** show an initially earlier N2 guidance cutoff. The first ON-to-OFF boundary is N2 step 24, C0 step 24, and Q0 step 16. The difference is subsequent reactivation: N2 0, C0 7, Q0 5. N2 stays OFF for the remaining 696 actions. At each arm's first OFF, the structured log records “reward rose above 80%”, a successful Stage query, Stage 1 retained and guidance=false; no actual normalized reward value is recorded. Later states and queries have diverged, so this chronology does not establish that keeping guidance on would improve the outcome.

| Arm | All OFF-to-ON boundaries | Last guided action | Successful queries / limit |
|---|---|---:|---:|
'''
for a in arms:
    s=a['summary']
    text+=f"| {a['arm']} | {s['all_off_to_on_steps']} | {s['last_guided_executed_step']} | {s['query_status_counts'].get('ok',0)} / 50 |\n"
text+='''
N2's five structured queries are at steps 24, 32, 144, 584, 592, all successful. Stage stays 1 at 24, then becomes 2, 0, 2, 0, respectively; guidance remains false after the first query. There is no logged skipped/failed query or limit exhaustion. Between boundaries, lack of a trigger event is not a new decision or failed query. The source uses reward triggers only while guidance is on, alongside boundary gripper-change triggers; this source rule and the observed no-reactivation sequence are separate from any causal explanation of failure.

After N2 goes OFF, the EEF continues moving; it does not stop at the guidance boundary. Using the actual post-action observation at step 23 as the origin, and all contiguous action responses 24–719:

'''
text+=f"- EEF start {post['eef_start']}; end {post['eef_end']}. Net displacement **{post['eef_net_displacement_m']:.6f} m**; accumulated path **{post['eef_path_length_m']:.6f} m** over {post['contiguous_observed_edges']} consecutive observed edges. These are spatial displacements, not target progress.\n"
text+=f"- Command sign changes: {post['command_sign_changes']}. Finger qpos at first/last post-OFF observations: {post['gripper_qpos_start']} / {post['gripper_qpos_end']}. Command signs and finger movement do not establish capture/contact.\n"
text+='''- The full report retains every Stage/guidance run and its motion. Notably, N2 steps 144–583 are Stage 0/OFF: EEF path 0.447414 m and net 0.116862 m, with negative gripper commands through step 575, a positive two-action interval at 576–577, then negative again. At 584, the logged Stage gripper input is positive even though the previous chunk's last command is negative. This agrees with the source's use of the previous chunk's first command at a fresh boundary; it is not a reconstructed physical gripper event.

All selected guided candidates have unambiguous native-content raw/internal quality associations: C0 29/29, Q0 52/52, N2 3/3. Unguided scores remain Unknown. N2's actual selected scalars are:

| Decision step | Original raw provider quality | Internal Q8 | Selected raw gap to same-final-pool raw best |
|---:|---:|---:|---:|
'''
for d in n2['decisions']:
    if d['use_guidance']:
        q=d['quality']; m=d['recorded_metric_quality']
        text+=f"| {d['global_step']} | {q['selected_raw_provider_quality']} | {q['selected_internal_quality']} | {m['qd_selected_raw_gap']} |\n"
text+='''
No Q8/raw magnitude substitution is made. The earlier checkpoint's step-0 raw tradeoff is retained; this report does not turn selection activity into performance evidence. Actual normalized Stage inputs, unexecuted outcomes and unique archive insertion ancestry remain Unknown.

Keypoints remain available at all 90 decision boundaries in each arm, with 12 points and 89 adjacent same-index links. The following is a complete index-level description for N2 from boundary 0 to 712 (no target/object name is assigned):

| Recorded index | Net displacement (m) | Sampled path (m) |
|---:|---:|---:|
'''
k=next(k for k in keypoints if k['arm']=='N2')
for i,(net,path) in enumerate(zip(k['net_displacement_m'],k['sampled_path_length_m'])):
    text+=f'| {i} | {net:.9f} | {path:.9f} |\n'
text+='''
These keypoint coordinates change, but the collector does not record object attachment continuity, background membership or tracker fallback status. They cannot independently prove real object motion, grasp, release or current target progress. Per-step object pose/contact is absent. All target-relative quantities are Unknown because no map was supplied. Optional selected-projection tracking diagnostics were deliberately not evaluated; no projection was recomputed.

`inputs-and-audit.json` contains the complete source/input hash manifest and all three admission/fresh-audit records; `closed-loop-sequence.json` retains full allowlisted Stage events, decision contexts, pre-reset actions/observations, keypoints and native selected-quality joins. `comparison.md` lists every actual state run. `descriptive-extract-v1.json` is derived only from the saved sequence and records this formatter and input hashes. Original source, protocol, terminal results and audit files are unchanged. No new threshold or causal/performance gate was introduced.
'''
with (OUT/'findings-v1.md').open('x') as f:f.write(text)
print(json.dumps({'post_off':{k:post[k] for k in ('eef_net_displacement_m','eef_path_length_m','contiguous_observed_edges','command_sign_changes')},'artifacts':{name:hashlib.sha256((OUT/name).read_bytes()).hexdigest() for name in ('findings-v1.md','descriptive-extract-v1.json')},'cuda_initialized':r.torch.cuda.is_initialized()}))
