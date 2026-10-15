#!/usr/bin/env python3
"""Independent offline fixed-grid QD audit. No repository/model/simulator imports.
CPU torch is used only for float32 quantiles and the declared local tie permutation.
The shadow candidate stream is evidence input, not proof of descriptor geometry or
actual model execution. Optional weights-only CPU traces bind saved latent tensors.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import torch
import yaml

FIXED = dict(population_size=16, cem_iters=10, use_cem=False, reward_mode='normal',
    qd_archive_mode='grid_archive', qd_descriptor='target_relative_endpoint_xy',
    qd_grid_shape=[4,4], qd_cell_capacity=1, qd_parent_sampling='sparse_priority',
    qd_sparse_exponent=1.0, qd_bounds_quantiles=[.05,.95], qd_bounds_expand_fraction=.1,
    qd_min_axis_span_m=.08, qd_bounds_update_policy='fixed_initial',
    qd_overflow_policy='clamp_edge', qd_tie_break='stable_fingerprint',
    qd_global_quality_anchor_count=0, qd_secondary_lane_mode='none',
    qd_degenerate_fallback_policy='none', qd_metrics_observer=True,
    chunk_population_mode='fresh', chunk_memory_fraction=0.0,
    elite_carryover_count=0, parent_anchor_count=0,
    search_schedule_mode='legacy_linear',renoise_t_max=3,renoise_t_min=1,
    initial_population_cache=None,ed_population_cache=None,use_initial_cache=False,
    initial_sampling_mode='rbf_diverse_denoise',initial_diversity_descriptor_mode='absolute_eef',
    initial_diversity_scale=20.0,initial_diversity_start_ratio=.8,
    truncated_rollout_mode='rbf_diverse',rollout_diversity_descriptor_mode='absolute_eef',
    rollout_diversity_scale=20.0,rollout_diversity_start_ratio=.6,rollout_diversity_iters='all',
    rollout_diversity_skip_final_steps=0,rollout_diversity_control_mode='fixed',
    parent_weighting_mode='legacy_temperature',parent_coverage_mode='none')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def close(a,b):
    if isinstance(b,dict): return isinstance(a,dict) and set(a)==set(b) and all(close(a[k],v) for k,v in b.items())
    if isinstance(b,list): return isinstance(a,list) and len(a)==len(b) and all(close(x,y) for x,y in zip(a,b))
    if isinstance(b,bool): return a is b
    if b is None: return a is None
    if isinstance(b,int): return type(a) is int and a==b
    if isinstance(b,float): return type(a) in (float,int) and math.isfinite(a) and math.isclose(a,b,rel_tol=2e-6,abs_tol=2e-7)
    return a==b


def freeze_bounds(descriptors):
    d=torch.tensor(descriptors,dtype=torch.float32,device='cpu')
    if not torch.isfinite(d).all():raise ValueError('Descriptors overflow float32')
    q=torch.quantile(d,torch.tensor([.05,.95],dtype=torch.float32),dim=0)
    span=q[1]-q[0]; lo=q[0]-.1*span; hi=q[1]+.1*span
    small=(hi-lo)<.08; center=torch.quantile(d,.5,dim=0)
    lo=torch.where(small,center-.04,lo);hi=torch.where(small,center+.04,hi)
    if not torch.isfinite(lo).all() or not torch.isfinite(hi).all() or not ((hi-lo)>0).all():
        raise ValueError('Bounds must be finite with positive float32 spans')
    payload=dict(descriptors=sorted(d.tolist(),key=lambda x:(x[0],x[1])),quantiles=[.05,.95],
                 expand_fraction=.1,min_axis_span_m=.08,lo=lo.tolist(),hi=hi.tolist())
    return [lo.tolist(),hi.tolist()],digest(payload)


def assign_cells(descriptors,bounds):
    d=torch.tensor(descriptors,dtype=torch.float32,device='cpu')
    lo,hi=torch.tensor(bounds,dtype=torch.float32,device='cpu')
    if not torch.isfinite(d).all() or not torch.isfinite(lo).all() or not torch.isfinite(hi).all() or not ((hi-lo)>0).all():
        raise ValueError('Cell inputs require finite float32 values and positive bounds')
    bins=torch.floor((d-lo)/(hi-lo)*4).long().clamp(0,3)
    return (4*bins[:,1]+bins[:,0]).tolist(),int(((d<lo)|(d>hi)).any(dim=1).sum())


def validate_stream(stream):
    if not isinstance(stream,list) or len(stream)!=11: raise ValueError('Expected initial plus ten scored batches')
    known={}
    for i,batch in enumerate(stream):
        if type(batch.get('iter_idx')) is not int or batch['iter_idx']!=i-1: raise ValueError('Wrong stream iteration sequence')
        d,r,f=(batch.get(k) for k in ('descriptors_xy_m','rewards','fingerprints'))
        if not all(isinstance(x,list) and len(x)==16 for x in (d,r,f)): raise ValueError('Each scored batch must contain16 candidates')
        if any(not isinstance(x,list) or len(x)!=2 or any(type(v) not in (float,int) or not math.isfinite(v) for v in x) for x in d): raise ValueError('Invalid descriptor')
        if any(type(x) not in (float,int) or not math.isfinite(x) for x in r): raise ValueError('Invalid reward')
        if not torch.isfinite(torch.tensor(d,dtype=torch.float32)).all() or not torch.isfinite(torch.tensor(r,dtype=torch.float32)).all():
            raise ValueError('Candidate descriptors/rewards overflow float32')
        if any(not isinstance(x,str) or len(x)!=64 or any(c not in '0123456789abcdef' for c in x) for x in f): raise ValueError('Invalid fingerprint')
        for fp,desc,rew in zip(f,d,r):
            if fp in known and known[fp]!=(desc,rew): raise ValueError('Same latent fingerprint has inconsistent descriptor/reward within a fixed chunk')
            known[fp]=(desc,rew)


def update_archive(archive,visits,batch,bounds):
    cells,overflow=assign_cells(batch['descriptors_xy_m'],bounds);groups={}
    for j,cell in enumerate(cells):
        visits[cell]+=1
        groups.setdefault(cell,[]).append(dict(fingerprint=batch['fingerprints'][j],reward=batch['rewards'][j],
            descriptor=batch['descriptors_xy_m'][j],source_iter=batch['iter_idx']))
    counts=dict(insertions=0,replacements=0,rejections=0,total=16)
    for cell,candidates in sorted(groups.items()):
        winner=min(candidates,key=lambda x:(-x['reward'],x['fingerprint']))
        old=archive.get(cell)
        if old is None or (-winner['reward'],winner['fingerprint'])<(-old['reward'],old['fingerprint']):
            counts['insertions' if old is None else 'replacements']+=1
            counts['rejections']+=len(candidates)-1;archive[cell]=winner
        else: counts['rejections']+=len(candidates)
    return counts,overflow


def allocate_parents(archive,visits,seed,episode,step,iteration):
    occupied=sorted(archive)
    raw={c:1.0/(visits[c]+1.0) for c in occupied};total=sum(raw.values())
    exact={c:16*raw[c]/total for c in occupied};slots={c:math.floor(exact[c]) for c in occupied}
    material=f'{int(seed)}:{int(episode)}:{int(step)}:{int(iteration)}'
    local_seed=int.from_bytes(hashlib.sha256(material.encode('ascii')).digest()[:8],'big') & ((1<<63)-1)
    generator=torch.Generator(device='cpu').manual_seed(local_seed)
    permutation=torch.randperm(len(occupied),generator=generator).tolist()
    rank={occupied[offset]:n for n,offset in enumerate(permutation)}
    ordered=sorted(occupied,key=lambda c:(-(exact[c]-slots[c]),rank[c]))
    for cell in ordered[:16-sum(slots.values())]: slots[cell]+=1
    parents=[c for c in occupied for _ in range(slots[c])]
    return {str(c):slots[c] for c in occupied},{str(c):raw[c] for c in occupied},parents


def reconstruct(stream,seed,episode,step):
    validate_stream(stream);bounds,checksum=freeze_bounds(stream[0]['descriptors_xy_m'])
    archive={};visits=[0]*16
    initial,overflow=update_archive(archive,visits,stream[0],bounds)
    result=dict(bounds=bounds,bounds_checksum=checksum,initial_accounting=initial,
                initial_occupied_cells=len(archive),initial_overflow_count=overflow,iterations=[])
    for i,batch in enumerate(stream[1:]):
        slots,weights,parents=allocate_parents(archive,visits,seed,episode,step,i)
        parent_fingerprints=[archive[c]['fingerprint'] for c in parents]
        parent_rewards=[archive[c]['reward'] for c in parents]
        before=sum(visits);counts,overflow=update_archive(archive,visits,batch,bounds)
        rewards={str(c):x['reward'] for c,x in sorted(archive.items())}
        occupied=len(archive);covered=sum(v>0 for v in slots.values())
        result['iterations'].append(dict(iter_idx=i,parent_slots=slots,parent_weights=weights,parent_cells=parents,
            parent_fingerprints=parent_fingerprints,parent_rewards=parent_rewards,covered_ratio=covered/len(slots),unique_ratio=covered/16,
            accounting=counts,overflow_count=overflow,occupied_cells=occupied,coverage=occupied/16,
            visits=list(visits),visits_before=before,elite_rewards=rewards,best_reward=max(rewards.values()),
            mean_reward=sum(rewards.values())/occupied))
    cell=min(archive,key=lambda c:(-archive[c]['reward'],archive[c]['fingerprint'],c))
    result['selected']=dict(cell=cell,**archive[cell],index=sorted(archive).index(cell))
    result['final_occupied_cells']=len(archive)
    return result


def fingerprint(action):
    if not torch.is_tensor(action) or action.device.type!='cpu' or not torch.isfinite(action).all(): raise ValueError('Invalid CPU action tensor')
    value=action.detach().float().contiguous()
    if not torch.isfinite(value).all():raise ValueError('Action tensor overflows float32')
    return hashlib.sha256(value.numpy().astype('<f4',copy=False).tobytes()).hexdigest()


def audit_trace(payload,metric,reconstructed):
    checks={};covered=[];candidate_batches=[]
    meta=payload.get('metadata',{})
    checks['trace_identity']=all(type(meta.get(k)) is int and meta[k]==metric.get(k) for k in ('task_id','episode','global_step'))
    stages=payload.get('stages',[]); seen=set()
    for stage in stages:
        name,i=stage.get('stage'),stage.get('iter_idx')
        if name not in ('initial','scored','resampled','after_rollout','full_process_after_rollout'): continue
        key=(name,i)
        if key in seen:
            checks['trace_stage_identity_unique']=False
            continue
        seen.add(key)
        initial=name in ('initial','scored')
        valid_iteration=type(i) is int and (i==0 if initial else 0<=i<10)
        checks[f'{name}/{i}/iteration']=valid_iteration
        if not valid_iteration:continue
        if not initial:
            checks[f'{name}/{i}/particle_sources']=stage.get('particle_sources')==['qd_archive_offspring']*16
            checks[f'{name}/{i}/selection_kinds']=stage.get('parent_selection_kinds')==['qd_sparse_priority']*16
        actions=stage.get('actions')
        if not torch.is_tensor(actions) or list(actions.shape)!=[16,64,128]:
            checks[f'{name}/{i}/shape']=False;continue
        fps=[fingerprint(action) for action in actions]
        expected_rewards=(reconstructed['iterations'][i]['parent_rewards'] if name=='resampled' else
            metric['shadow_qd_candidate_stream'][0 if initial else i+1]['rewards'])
        record_scores_valid=True
        for score_key,expected in (('rewards',expected_rewards),('costs',[-r for r in expected_rewards])):
            if score_key not in stage:continue
            value=stage[score_key]
            valid=(torch.is_tensor(value) and value.device.type=='cpu' and list(value.shape)==[16]
                and bool(torch.isfinite(value).all()) and close(value.detach().float().tolist(),expected))
            checks[f'{name}/{i}/{score_key}_join']=valid
            record_scores_valid=record_scores_valid and valid
        if name=='resampled':
            if type(i) is not int or not 0<=i<10: checks[f'{name}/{i}/iteration']=False;continue
            checks[f'parent_tensor_fingerprints/{i}']=fps==reconstructed['iterations'][i]['parent_fingerprints']
            checks[f'parent_selection_kinds/{i}']=stage.get('parent_selection_kinds')==['qd_sparse_priority']*16
            if (checks[f'parent_tensor_fingerprints/{i}'] and checks[f'parent_selection_kinds/{i}']
                and checks[f'{name}/{i}/particle_sources'] and record_scores_valid): covered.append(i)
        else:
            batch=0 if name in ('initial','scored') else i+1
            if type(batch) is not int or not 0<=batch<11: checks[f'{name}/{i}/iteration']=False;continue
            checks[f'candidate_tensor_fingerprints/{name}/{i}']=fps==metric['shadow_qd_candidate_stream'][batch]['fingerprints']
            if checks[f'candidate_tensor_fingerprints/{name}/{i}'] and record_scores_valid:candidate_batches.append(batch-1)
    checks['trace_has_candidate_tensor_evidence']=bool(candidate_batches)
    return checks,sorted(set(covered)),sorted(set(candidate_batches))


def audit_chunk(metric,config,trace_payload=None,expected_mode='eds_qd'):
    checks={}; limits=[]; reconstructed=None;parent_iters=[];candidate_batches=[]
    def check(name,condition): checks[name]='pass' if condition else 'fail'
    try:
        if expected_mode not in ('eds','eds_qd'):raise ValueError('Unsupported method')
        for key,expected in FIXED.items():
            if expected_mode=='eds' and key in ('qd_archive_mode','qd_parent_sampling'): continue
            actual=config.get(key,'normal') if key=='reward_mode' else config.get(key)
            check('config/'+key,close(actual,expected))
        # The reviewed runtime resolves an omitted shuffle_seed to0. Record that origin.
        seed=config.get('shuffle_seed',0)
        check('config/local_shuffle_seed',type(seed) is int)
        check('metric_identity',all(type(metric.get(k)) is int for k in ('episode','task_id','global_step')))
        check('guided_eds_route',metric.get('guidance_type')=='eds')
        check('normal_reward_mode',metric.get('reward_mode')=='normal')
        check('search_enter_and_tensor_shape',metric.get('eds_enter_count')==1 and metric.get('population_shape')==[16,64,128] and type(metric.get('nonfinite_count')) is int and metric['nonfinite_count']==0 and metric.get('execution_horizon_resolved')==8)
        check('search_budget',metric.get('population_size_observed')==16 and metric.get('cem_iters')==10
              and metric.get('eds_iters_executed')==10 and metric.get('score_call_count')==11
              and metric.get('search_evaluation_count')==176)
        stream=metric.get('shadow_qd_candidate_stream')
        check('shadow_enabled_and_checksum',metric.get('shadow_qd_observer_enabled') is True and digest(stream)==metric.get('shadow_qd_observer_checksum'))
        reconstructed=reconstruct(stream,seed,metric['episode'],metric['global_step'])
        check('stream_shape_and_values',True)
        if expected_mode=='eds':
            check('control_archive_off',config.get('qd_archive_mode')=='none' and metric.get('qd_archive_enabled') is False
                  and metric.get('qd_archive_active_for_chunk') is False and metric.get('qd_evaluation_count')==0
                  and metric.get('qd_selected_action_fingerprint') is None
                  and metric.get('qd_parent_slots_by_cell_by_iter')==[])
            check('control_parent_and_selected_sources',metric.get('parent_count_by_source')=={'elite':0,'anchor_offspring':0,'weighted_offspring':160}
                  and metric.get('selected_chunk_population_source')=='fresh'
                  and metric.get('selected_parent_source')=='weighted_offspring')
            check('control_no_qd_selection',all(k in metric and metric[k] is None for k in
                  ('qd_selected_cell','qd_selected_reward','qd_selected_action_fingerprint','qd_global_best_action_fingerprint')))
            check('control_no_archive_updates',metric.get('qd_initial_accounting')=={}
                  and metric.get('qd_initial_occupied_cells')==0 and metric.get('qd_initial_descriptor_overflow_count')==0
                  and metric.get('qd_bounds_xy_m')==[] and metric.get('qd_bounds_source_initial_checksum') is None
                  and all(v==[] for k,v in metric.items() if k.startswith('qd_') and k.endswith('_by_iter')))
        else:
            for key in ('qd_descriptor','qd_grid_shape','qd_cell_capacity','qd_parent_sampling','qd_secondary_lane_mode','qd_global_quality_anchor_count','qd_bounds_update_policy','qd_degenerate_fallback_policy'):
                check('metric/'+key,close(metric.get(key),FIXED[key]))
            check('archive_really_active_in_record',metric.get('qd_archive_enabled') is True and metric.get('qd_archive_active_for_chunk') is True
                  and metric.get('qd_evaluation_count')==176 and metric.get('selected_chunk_population_source')=='qd_archive'
                  and metric.get('selected_parent_source')=='qd_archive')
            check('archive_parent_budget',metric.get('parent_count_by_source')=={'elite':0,'anchor_offspring':0,'weighted_offspring':0,'qd_archive_offspring':160})
            for key in ('qd_degenerate_fallback_used','qd_fallback_used','early_stop_used','chunk_memory_used'):
                check('disabled/'+key,metric.get(key) is False)
            for key in ('qd_global_quality_anchor_activation_count','qd_global_quality_anchor_rescue_count','qd_secondary_parent_activation_count',
                        'qd_secondary_invariant_violation_count','qd_secondary_rebin_discard_count','qd_accounting_violation_count',
                        'qd_elite_monotonicity_violation_count','qd_final_selection_mismatch_count','qd_bounds_expansion_count'):
                check('zero/'+key,type(metric.get(key)) is int and metric[key]==0)
            check('initial_bounds',close(metric.get('qd_bounds_xy_m'),reconstructed['bounds']) and metric.get('qd_bounds_source_initial_checksum')==reconstructed['bounds_checksum'])
            check('fresh_initial_archive',metric.get('qd_initial_accounting')==reconstructed['initial_accounting']
                  and metric.get('qd_initial_occupied_cells')==reconstructed['initial_occupied_cells']
                  and metric.get('qd_initial_descriptor_overflow_count')==reconstructed['initial_overflow_count'])
            field_arrays={
                'qd_bounds_xy_m_by_iter':[reconstructed['bounds']]*10,
                'qd_bounds_checksum_by_iter':[reconstructed['bounds_checksum']]*10,
                'qd_bounds_expanded_by_iter':[False]*10,'qd_archive_rebin_collisions_by_iter':[0]*10,
                'qd_archive_rebin_visit_sum_before_by_iter':[x['visits_before'] for x in reconstructed['iterations']],
                'qd_archive_rebin_visit_sum_after_by_iter':[x['visits_before'] for x in reconstructed['iterations']],
                'qd_parent_slots_by_cell_by_iter':[x['parent_slots'] for x in reconstructed['iterations']],
                'qd_sparse_parent_slots_by_cell_by_iter':[x['parent_slots'] for x in reconstructed['iterations']],
                'qd_parent_weights_by_cell_by_iter':[x['parent_weights'] for x in reconstructed['iterations']],
                'qd_parent_covered_cell_ratio_by_iter':[x['covered_ratio'] for x in reconstructed['iterations']],
                'qd_parent_cell_unique_ratio_by_iter':[x['unique_ratio'] for x in reconstructed['iterations']],
                'qd_occupied_cells_by_iter':[x['occupied_cells'] for x in reconstructed['iterations']],
                'qd_coverage_ratio_by_iter':[x['coverage'] for x in reconstructed['iterations']],
                'qd_cumulative_cell_visits_by_iter':[x['visits'] for x in reconstructed['iterations']],
                'qd_descriptor_overflow_count_by_iter':[x['overflow_count'] for x in reconstructed['iterations']],
                'qd_raw_initial_bounds_overflow_count_by_iter':[x['overflow_count'] for x in reconstructed['iterations']],
                'qd_descriptor_overflow_ratio_by_iter':[x['overflow_count']/16 for x in reconstructed['iterations']],
                'qd_per_cell_elite_reward_by_iter':[x['elite_rewards'] for x in reconstructed['iterations']],
                'qd_archive_best_reward_by_iter':[x['best_reward'] for x in reconstructed['iterations']],
                'qd_archive_mean_elite_reward_by_iter':[x['mean_reward'] for x in reconstructed['iterations']],
                'qd_archive_turnover_ratio_by_iter':[(x['accounting']['insertions']+x['accounting']['replacements'])/16 for x in reconstructed['iterations']],
                'qd_secondary_occupied_cells_by_iter':[0]*10,'qd_secondary_parent_count_by_iter':[0]*10,
                'qd_global_quality_anchor_cell_by_iter':[None]*10,
                'qd_global_quality_anchor_fingerprint_by_iter':[None]*10,
                'qd_global_quality_anchor_rescued_by_iter':[False]*10,
            }
            for stat in ('insertions','replacements','rejections'):
                field_arrays['qd_archive_'+stat+'_by_iter']=[x['accounting'][stat] for x in reconstructed['iterations']]
            for key,value in field_arrays.items(): check('reconstruct/'+key,close(metric.get(key),value))
            winner=reconstructed['selected']
            check('final_global_best_selection',metric.get('qd_selected_cell')==winner['cell']
                  and metric.get('qd_selected_action_fingerprint')==metric.get('qd_global_best_action_fingerprint')==winner['fingerprint']
                  and metric.get('qd_selected_reward')==metric.get('selected_reward')==metric.get('final_best_reward')==winner['reward']
                  and metric.get('selected_idx')==winner['index'])
            if trace_payload is not None:
                trace_checks,parent_iters,candidate_batches=audit_trace(trace_payload,metric,reconstructed)
                for key,value in trace_checks.items():check('trace/'+key,value)
    except (ValueError,TypeError,KeyError,IndexError,OverflowError,RuntimeError,AttributeError) as exc:
        checks['evidence_structure']='fail';limits.append('Evidence cannot be reconstructed: '+type(exc).__name__)
    limits += ['Descriptors/rewards are recorded inputs; this tool does not execute reward code or the RDT projection.',
        'XY descriptor is target-relative projected endpoint after8 commands; reward scoring uses p1..p7, not this endpoint.',
        'Per-cell counts alone do not prove actual parent tensors were consumed. Optional saved traces verify only explicitly listed iterations.',
        'Final selected fingerprint is independently recomputed from candidate records; actual returned/executed tensor is not independently captured here.',
        'The archive is independently reset for each chunk. No cross-chunk/episode learning or recursive self-improvement is established.',
        'Low coverage, all-equal rewards, fingerprint ties, clipping overflow and task failure are valid scientific outcomes.']
    summary=dict(Counter(checks.values()))
    return dict(schema='steering_qd_mechanism_audit_v1',scope='recorded candidate-stream reconstruction; not cohort acceptance',
        mode=expected_mode,effective_shuffle_seed=config.get('shuffle_seed',0),
        shuffle_seed_origin='resolved_config' if 'shuffle_seed' in config else 'reviewed_runtime_default_zero',
        effective_reward_mode=config.get('reward_mode','normal'),
        reward_mode_origin='resolved_config' if 'reward_mode' in config else 'reviewed_runtime_default_normal',summary=summary,checks=checks,recorded_mechanism_valid=bool(checks) and not summary.get('fail'),
        cohort_valid=None,full_parent_tensor_path_verified=parent_iters==list(range(10)),parent_tensor_verified_iterations=parent_iters,candidate_tensor_verified_batches=candidate_batches,
        descriptor_geometry_verified=False,executed_selected_tensor_verified=False,limits=limits,reconstruction=reconstructed)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metrics',type=Path,required=True)
    p.add_argument('--config',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--mode',choices=['eds','eds_qd'],default='eds_qd');p.add_argument('--task',type=int);p.add_argument('--step',type=int)
    p.add_argument('--trace',type=Path,help='Optional weights-only CPU trace; select exactly one metric row')
    args=p.parse_args();raw=args.metrics.read_bytes();config=yaml.safe_load(args.config.read_bytes())
    if 'main' in config:config=config['main']['eds_config']
    rows=[json.loads(x) for x in raw.splitlines() if x.strip()]
    rows=[x for x in rows if (args.task is None or x.get('task_id')==args.task) and (args.step is None or x.get('global_step')==args.step)]
    if args.trace and len(rows)!=1:p.error('--trace requires exactly one selected chunk')
    trace=torch.load(args.trace,map_location='cpu',weights_only=True) if args.trace else None
    reports=[audit_chunk(x,config,trace,expected_mode=args.mode) for x in rows]
    identities=[(x.get('episode'),x.get('task_id'),x.get('global_step')) for x in rows]
    valid=bool(reports) and len(set(identities))==len(identities) and all(x['recorded_mechanism_valid'] for x in reports)
    report=dict(schema='steering_qd_mechanism_run_audit_v1',cohort_valid=None,recorded_mechanism_valid=valid,
        evidence=dict(metrics=str(args.metrics),metrics_read_sha256=hashlib.sha256(raw).hexdigest(),config=str(args.config),
                      config_sha256=hashlib.sha256(args.config.read_bytes()).hexdigest(),trace=str(args.trace) if args.trace else None),
        selected_chunk_count=len(rows),unique_chunk_identities=len(set(identities)),chunks=[dict(identity=i,**x) for i,x in zip(identities,reports)],
        cuda_initialized=torch.cuda.is_initialized())
    args.report.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(report=str(args.report),chunks=len(rows),recorded_mechanism_valid=valid,cuda_initialized=report['cuda_initialized'])))
    return 0 if valid else 1

if __name__=='__main__':raise SystemExit(main())
