#!/usr/bin/env python3
"""Recompute descriptive diagnostic findings from the immutable branch traces."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import math

D=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def distance(a,b):return math.dist(a,b)
def source_contacts(trace):
    out=[]
    for i,state in enumerate(trace):
        for contact in state['contacts']:
            names=(contact['geom1'] or '',contact['geom2'] or '')
            if any('orange_juice_1' in name for name in names):
                out.append({'step':i,'geom1':names[0],'geom2':names[1]})
    return out
def branch(trace):
    initial,final=trace[0],trace[-1]
    obj='orange_juice_1'
    start=initial['object_pose'][obj]['xyz']
    end=final['object_pose'][obj]['xyz']
    contacts=source_contacts(trace)
    return {'states':len(trace),'transitions':len(trace)-1,
            'source_displacement_m':distance(start,end),
            'eef_source_initial_distance_m':distance(initial['eef_xyz'],start),
            'eef_source_final_distance_m':distance(final['eef_xyz'],end),
            'eef_source_min_distance_m':min(distance(x['eef_xyz'],x['object_pose'][obj]['xyz']) for x in trace),
            'success_any':any(x['success'] for x in trace),
            'source_contact_pairs':sorted({(x['geom1'],x['geom2']) for x in contacts}),
            'gripper_source_contact_count':sum(any(t in (x['geom1']+' '+x['geom2']).lower()
                for t in ('gripper','finger')) for x in contacts)}
def main():
    plan=json.loads((D/'plan.frozen.json').read_text()); output=Path(plan['output_dir'])
    result=json.loads((output/'result.json').read_text());attempt=json.loads((D/'attempt-result.json').read_text())
    assert result['status']=='COMPLETED_CONTRAST' and result['resources']=={'resets':4,'settling_steps':20,'transitions':32}
    assert result['official_task_success_rate'] is None and attempt['outcome_valid'] is False
    parity=all(result['dry_run_a'][i]==result['dry_run_b'][i] for i in range(9))
    selected_parity=all(result['dry_run_a'][i]==result['selected_branch'][i] for i in range(9))
    assert parity and selected_parity
    branches={name:branch(result[name]) for name in ('dry_run_a','dry_run_b','selected_branch','archive_branch')}
    summary={'schema':'n4-same-state-diagnostic-analysis-v1','diagnostic_only':True,
             'official_task_success_rate':None,'attempt_id':plan['attempt_id'],
             'plan_sha256':sha(D/'plan.frozen.json'),'result_sha256':sha(output/'result.json'),
             'attempt_result_sha256':sha(D/'attempt-result.json'),
             'same_action_parity_exact':parity,'selected_branch_parity_exact':selected_parity,
             'different_command_indices':result['different_command_indices'],
             'resources':result['resources'],'gpu_process_wall_seconds':attempt['gpu_process_wall_seconds'],
             'branches':branches,
             'source_displacement_between_branches_m':distance(
                 result['selected_branch'][-1]['object_pose']['orange_juice_1']['xyz'],
                 result['archive_branch'][-1]['object_pose']['orange_juice_1']['xyz']),
             'selected_vs_archive_final_eef_source_distance_delta_m':
                 branches['selected_branch']['eef_source_final_distance_m']-
                 branches['archive_branch']['eef_source_final_distance_m'],
             'interpretation_limit':'Only the first eight commands of one exposed Dev task9 decision; not task success or all search candidates.'}
    path=D/'analysis-v1.json'
    with path.open('x') as f:json.dump(summary,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'analysis':str(path),'sha256':sha(path),'summary':{
        'selected_final_distance_m':branches['selected_branch']['eef_source_final_distance_m'],
        'archive_final_distance_m':branches['archive_branch']['eef_source_final_distance_m'],
        'source_between_branches_m':summary['source_displacement_between_branches_m']}}))
if __name__=='__main__':main()
