"""Build a reviewable patch only; does NOT edit frozen running source."""
from pathlib import Path
import difflib
root=Path.cwd(); changes={}
def add(path,transform):
 old=(root/path).read_text();new=transform(old);assert old!=new;changes[path]=(old,new)
def guard(old):
 anchor="    executed_list = list(raw_list); executed_list[-1] = command\n"
 insert="""    payload = None
    payload_aligned = False
    if runner.config.get('payload_release_enabled', False):
        from core.stage_release_guard import payload_geometry, aligned_payload, apply
        payload = payload_geometry(runner)
        payload_aligned = aligned_payload(payload, runner.config.get('payload_release_margin_m', .005))
        command, reason = apply(state, float(raw_list[-1]), command, reason, step=step,
            width=observed_width(runner), distance=distance, geometry=payload, config=runner.config)
"""
 assert anchor in old;old=old.replace(anchor,insert+anchor)
 anchor="        gripper_width_m=observed_width(runner)))"
 insert="""        gripper_width_m=observed_width(runner), payload_geometry=payload,
        payload_aligned=payload_aligned, payload_release_until=state.get('payload_release_until'),
        semantic_stage=state.get('current_stage')))"""
 assert anchor in old;return old.replace(anchor,insert)
add('core/stage_grasp_guard.py',guard)
def main(old):
 anchor='        output_raw_path = os.path.join(guidance_functions_dir, \'output_raw.txt\')\n'
 insert="""        reward_contract = self.config.get('reward_contract')
        if reward_contract:
            if reward_contract != 'c0_xyz_v1':
                raise ValueError('Unknown numerical reward contract')
            from core.c0_reward_contract import validate_task
            validate_task(self, key_points, episode_dir)

"""
 assert anchor in old;return old.replace(anchor,insert+anchor)
add('main.py',main)
def runner(old):
 old=old.replace("assert resolved['main']['episode_policy_rng_mode']=='per_seed_v1'","assert resolved['main']['episode_policy_rng_mode'] in {'per_seed_v1','continuous'}")
 old=old.replace("'policy_rng':'per_seed_v1; same initial policy RNG for each environment seed independent of episode ordering',","'policy_rng':resolved['main']['episode_policy_rng_mode'],")
 anchor="SOURCES = ['main.py','core/stage_evidence.py','core/stage_contact_handoff.py',"
 insert="""SOURCES = ['core/stage_release_guard.py','core/c0_reward_contract.py',
    'vlm_query/c0_contract_v1/guidance_template.txt','vlm_query/c0_contract_v1/guidance_template_libero.txt',
    'vlm_query/c0_contract_v1/stage_template.txt','vlm_query/c0_contract_v1/segmentation_planning_template.txt',
    'main.py','core/stage_evidence.py','core/stage_contact_handoff.py',"""
 assert anchor in old;old=old.replace(anchor,insert)
 anchor="    per_task=[]\n"
 assert anchor in old;old=old.replace(anchor,"    config=yaml.safe_load((folder/'resolved-config.yaml').read_text())\n"+anchor)
 anchor="        checks['release_allowed_at_goal']=all(not r['override'] for r in guarded if r['goal_aligned'])"
 insert="""        payload_enabled=config['main'].get('payload_release_enabled',False)
        checks['release_allowed_at_goal']=all(not r['override'] or
            (payload_enabled and r['reason']=='complete_policy_requested_payload_release' and r['executed_action'][-1]<0)
            for r in guarded if r['goal_aligned'])
        if payload_enabled:
            starts={};valid_release=True;dwell=config['main'].get('payload_release_dwell_steps',8)
            for r in guarded:
                episode=r['episode'];step=r['global_step']
                if r['reason']=='allow_policy_release_payload_over_destination':
                    valid_release &= (r['raw_action'][-1]<0 and r['executed_action'][-1]<0 and
                        r['payload_aligned'] and r['semantic_stage']==2 and r['visual_hold'] and
                        .005<r['gripper_width_m']<.075 and r['target_distance_m']<.12)
                    starts[episode]=step
                elif r['reason']=='complete_policy_requested_payload_release':
                    valid_release &= (episode in starts and 0<step-starts[episode]<dwell and r['executed_action'][-1]<0)
            checks['release_initiated_by_policy_and_bounded']=valid_release
    if config['main'].get('reward_contract'):
        proofs=[out/f'episode_{i+1}/vlm_agent/c0_reward_contract.json' for i in range(len(manifest['tasks']))]
        checks['numerical_reward_contract']=all(p.exists() and json.loads(p.read_text()).get('valid')
            and json.loads(p.read_text()).get('contract')=='c0_xyz_v1' for p in proofs)"""
 assert anchor in old;return old.replace(anchor,insert)
add('scripts/stage_closed_loop_run.py',runner)
patch=''.join(''.join(difflib.unified_diff(a.splitlines(True),b.splitlines(True),fromfile='a/'+name,tofile='b/'+name)) for name,(a,b) in changes.items())
p=root/'artifacts/stage_closed_loop_20260929/pending-release-integration.patch';p.write_text(patch);print(p, len(patch))
