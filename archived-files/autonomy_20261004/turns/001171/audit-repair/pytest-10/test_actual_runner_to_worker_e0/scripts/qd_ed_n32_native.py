"""N32 same-worker CPU evidence audit. No production proposal/helper invocation.

Retains original native tensors. GPU descriptor/cell arithmetic is inherited from
recorded native assignment; archive retention and proposal arithmetic replay are
independent. Pre-substitution commitments do not replay the model.
"""
from collections import defaultdict
import json
import math
from pathlib import Path
import torch
from scripts.qd_ed_n31_reference import require, same, optional, shape, native_id, fingerprint, terminal_bool
from scripts.qd_ed_n32_reference import enumerate_parents
import hashlib
from scripts.qd_ed_n30_native import provider_target

MODE='archive_eligible_capture_v1'
GATE='n32_capture_dwell_audit'
ARMS=('C0','Q0','N32')
OVERHEAD_EXCLUDES=['Main_packet','provider_recognition','score_validate','adapter_capture_origin_copy','archive_snapshot_observer','whole_selection','source_hashing','CUDA_cost_not_measured_on_CPU']


def packet_identity(context, packet, target_binding):
    cv=context['values']
    require(isinstance(packet,dict) and type(packet.get('episode')) is int
        and packet['episode']==context['episode'] and optional(packet['keypoints'],cv['keypoints'])
        and packet['tracker']==cv.get('keypoint_tracking_snapshot'),'Main/context identity')
    for name,n in (('observed_eef',3),('hand_quaternion_xyzw',4),('gripper_qpos',2)):
        if packet.get(name) is not None:shape(packet[name],(n,))
    identity={'episode':context['episode'],'stage':cv['stage'],'step':context['global_step'],
        'provider':None if target_binding is None else target_binding[1]}
    if target_binding is None:return identity,'unrecognized_target',None
    points=packet['keypoints']
    if points is None:return identity,'target_unavailable',None
    index=target_binding[0]
    require(points.ndim==2 and points.shape[1]==3 and 0<=index<len(points),'target index/shape')
    tr=packet['tracker']
    if tr is None:return identity,'tracking_unavailable',None
    require(isinstance(tr,dict) and type(tr.get('instance_id')) is int and type(tr.get('generation')) is int
        and isinstance(tr.get('targets'),dict),'tracking identity')
    state=tr['targets'].get(str(index))
    if state is not None:require(isinstance(state,dict),'target tracking type')
    if state is None or state.get('valid') is not True or state.get('status') not in {'tracked','static_background'}:
        return identity,'tracking_unavailable',None
    identity.update(target_index=index,tracker_instance=tr['instance_id'],tracker_generation=tr['generation'],target_status=state['status'])
    return identity,None,points[index]


def audit_events(profile, metrics, events, compute, *, expected_runtime=None):
    require(profile in ARMS,'profile')
    if profile == 'N32':
        require(isinstance(expected_runtime, dict) and set(expected_runtime) == {'binding', 'config_sha256', 'source_hashes'}, 'N32 trusted runtime identity required')
        require(not any(e['event'].startswith('n31_') for e in events), 'mixed N31 evidence')
    contexts=[e for e in events if e['event']=='decision_context']
    guided=[e for e in contexts if e['values']['use_guidance']]
    require(len(guided)==len(metrics)==compute.get('guided_chunks'),'guided coverage')
    scored=[e for e in guided if e['values']['providers'] and e['values']['keypoints'] is not None]
    require(contexts and all(type(e['values']['use_guidance']) is bool for e in contexts),'real decision contexts required')
    n,u=len(guided),sum(not e['values']['use_guidance'] for e in contexts)
    require(n+u==len(contexts) and type(compute.get('unguided_chunks')) is int
        and compute['unguided_chunks']==u and compute.get('policy_counters_available') is True,'compute available/context counts')
    expected={'guided_chunks':n,'model_forward_calls':21*n+5*u,'model_batch_rows':336*n+5*u,
        'rbf_gradient_calls':19*n,'rbf_gradient_batch_rows':304*n,'reward_scoring_batches':16*len(scored),
        'reward_evaluations':256*sum(len(e['values']['providers']) for e in scored)}
    require(all(compute.get(k)==v for k,v in expected.items()),'source-derived Q0 cost counts')
    counts={'schema' :'n32-independent-capture-dwell-v1','profile':profile,'guided_decisions':len(guided),'compute_expected':expected,
        'canonical_batches_verified':11*len(guided),'canonical_candidates_verified':176*len(guided),
        'parent_rounds_verified':0,'opportunities_verified':0,'changed_proposals_verified':0,
        'ambiguous_content_sources':0,'observation_contexts_verified':0,'executed_actions_verified':0,
        'other15_commitments_verified':0,'selected_proposal_content_decisions':0}
    if profile=='N32':counts['runtime_identity']=expected_runtime
    if profile!='N32':
        require(not any(e['event'].startswith('n32_') for e in events),'control N32 markers')
        require(all('capture_dwell_proposal' not in m for m in metrics),'control N32 metrics')
        return counts
    require(not any(e['event'].startswith('n30_') for e in events),'N30 mixed markers')
    groups=defaultdict(list)
    for e in events:groups[e['decision_id']].append(e)
    require(set(groups)=={e['decision_id'] for e in contexts},'unknown decision')
    byseq={e['sequence']:e for e in events};previous=None;mi=0
    for context in contexts:
        rows=groups[context['decision_id']];kinds=defaultdict(list)
        for e in rows:
            require(e['episode']==context['episode'],'episode mismatch')
            if e['event'].startswith('n32_'):require(e['reset_sequence']==context['reset_sequence'],'reset mismatch')
            kinds[e['event']].append(e)
        def one(k):
            require(len(kinds[k])==1,'missing/duplicate '+k);return kinds[k][0]
        p_event=one('n32_observation_context');packet=p_event['values']['packet']
        identity,skip,target=packet_identity(context,packet,provider_target(context))
        require(type(packet.get('task_id')) is int and packet['task_id']==expected_runtime['binding']['task_id']==compute.get('task_id'), 'N32 observed task binding')
        require(context['sequence']<p_event['sequence']<one('policy_action_decode')['sequence'],'packet order')
        if previous is not None and context['global_step']>0 and not terminal_bool(previous['values']['terminated']):
            require(previous['global_step']==context['global_step']-1,'previous observed step')
            obs=previous['values']['observation']
            for key,native_key,n in [('observed_eef','robot0_eef_pos',3),('hand_quaternion_xyzw','robot0_eef_quat',4),('gripper_qpos','robot0_gripper_qpos',2)]:
                if packet[key] is not None:
                    require(native_key in obs and same(packet[key],obs[native_key].reshape(n)),'previous raw observation '+key)
        if kinds['pre_reset_outcome']:previous=kinds['pre_reset_outcome'][-1]
        counts['observation_contexts_verified']+=1
        if not context['values']['use_guidance']:
            require(not any(kinds[x] for x in ('n32_canonical_cache','n32_archive_eligible_opportunity','n32_archive_update')),'unguided cache')
            continue
        metric=metrics[mi];mi+=1
        canon=kinds['canonical_candidate_batch'];cache=kinds['n32_canonical_cache'];updates=kinds['n32_archive_update'];ops=kinds['n32_archive_eligible_opportunity']
        require(len(canon)==len(cache)==len(updates)==11 and len(ops)==10
            and [e['values']['iter_idx'] for e in canon]==list(range(-1,10)),'canonical opportunity coverage')
        require(len(kinds['parent_allocation'])==10,'parent coverage')
        archive={};insert=0;entries=[];fixed_bounds=None;reasons=[];changed=0;proposals=[]
        for b,(ca,ce,ue) in enumerate(zip(canon,cache,updates)):
            it=b-1;cv=ca['values'];v=ce['values'];u=ue['values'];actions=shape(cv['candidates'],(16,64,128),True);rewards=shape(cv['effective_quality'],(16,),True)
            require(actions.dtype==rewards.dtype and v['identity']==identity and v['iter_idx']==u['iter_idx']==it
                and v['role']==('canonical_initial' if it==-1 else 'canonical_offspring')
                and v['site']==('initial_population' if it==-1 else 'rollout') and v['occurrence_start']==16*b
                and p_event['sequence']<ce['sequence']<ca['sequence']<ue['sequence'],'canonical identities/order')
            mask=torch.zeros((1,1,128),dtype=actions.dtype);mask[:,:,[10,39,40,41,42,43,44]]=1
            require(same(v['action_mask'],mask) and bool((actions*(1-mask)==0).all()),'mask')
            short=context['values']['providers']==[]
            source=byseq.get(v['scoring_batch_id'])
            if short:
                require(source is None and v['scoring_batch_id'] is None and skip=='unrecognized_target'
                    and v['projected_outcomes'] is None and v['source_origins'] is None and v['cast_origins'] is None
                    and v['projection_status']=='Unknown_original_score_short_circuit' and same(rewards,torch.zeros_like(rewards))
                    and not kinds['scoring_inputs'] and not kinds['provider_return'] and not kinds['scoring_aggregate'],
                    'empty-provider original short-circuit only')
                xyz=None
                effects=[e for e in kinds['effective_quality'] if e['values']['scoring_scope']=={'role':v['role'],'iter_idx':it,'site':v['site']}]
            else:
                require(source is not None and source['event']=='scoring_inputs' and source['decision_id']==context['decision_id']
                    and source['sequence']<ce['sequence'],'scoring batch binding')
                sv=source['values'];scope=sv['scoring_scope']
                require(scope=={'role':v['role'],'iter_idx':it,'site':v['site']} and same(sv['samples'],actions),'score population/scope')
                xyz=shape(sv['projected_xyz'],(16,9,3),True)
                require(xyz.dtype==actions.dtype and v['projection_status']=='original_canonical'
                    and same(v['projected_outcomes'],xyz[:,1:9]) and same(v['cast_origins'],xyz[:,0]),'original outcomes1:9')
                require(optional(sv['keypoints'],packet['keypoints'].to(sv['keypoints']) if packet['keypoints'] is not None else None),'score target')
                require(len(v['source_origins'])==len(sv['projection_origin_sequences'])==16,'origin coverage')
                effects=[e for e in kinds['effective_quality'] if e['values']['scoring_batch_id']==source['sequence']]
            require(len(effects)==1 and same(effects[0]['values']['quality'],rewards)
                and same(effects[0]['values']['costs'],-rewards),'original score/quality')
            current=[]
            for j in range(16):
                if xyz is not None:
                    origin=byseq.get(sv['projection_origin_sequences'][j]);o=origin['values'] if origin else {}
                    require(origin is not None and origin['event']=='projection_origin' and origin['decision_id']==context['decision_id']
                        and origin['sequence']<source['sequence'] and same(v['source_origins'][j],o['source_eef_position'])
                        and same(o['cast_eef_start'],xyz[j,0]) and same(o['source_eef_position'].to(xyz),xyz[j,0]),'source/cast origin')
                entry={'iteration':it,'row':j,'occurrence':len(entries)+j,'plan':actions[j],
                    'projection':None if xyz is None else xyz[j,1:9],
                    'source_origin':None if xyz is None else v['source_origins'][j],
                    'cast_origin':None if xyz is None else xyz[j,0],
                    'projection_status':v['projection_status'],'quality':rewards[j],'cost':-rewards[j],
                    'fingerprint':fingerprint(actions[j]),'native_identity':native_id(actions[j]),'scoring_batch_id':v['scoring_batch_id']}
                current.append(entry)
            require(v['native_identities']==[e['native_identity'] for e in current],'cache native bytes')
            if it>=0:
                op=ops[it];ov=op['values'];require(op['sequence']<(source['sequence'] if source else ce['sequence']) and updates[b-1]['sequence']<op['sequence'],'opportunity timing')
                allocation=kinds['parent_allocation'][it]['values'];arc=kinds['archive_parent_allocation'][it]['values']
                require(allocation['elite_count']==0 and allocation['parent_indices'].dtype==torch.int64 and torch.equal(allocation['parent_indices'],torch.arange(16))
                    and len(allocation['offspring_sources'])==len(arc['parent_lanes'])==16
                    and all(lane=='quality' for lane in arc['parent_lanes'])
                    and allocation['offspring_sources']==['qd_archive_offspring']*16, 'ordinary no-survivor QD parent lanes')
                cells=arc['parent_cell_ids'];require(torch.is_tensor(cells) and cells.shape==(16,),'parent cell shape')
                require(cells.dtype==torch.int64 and allocation['parent_cell_ids'].dtype==torch.int64 and torch.equal(allocation['parent_cell_ids'],cells),'parent native cell identity')
                for j,cell in enumerate(cells.tolist()):
                    require(cell in archive,'parent cell absent from prior archive');parent_entry=archive[cell]
                    require(same(allocation['source_population'][j],parent_entry['plan'])
                        and arc['parent_fingerprints'][j]==parent_entry['fingerprint']
                        and allocation['source_quality'].dtype==allocation['source_costs'].dtype==torch.float32
                        and float(allocation['source_quality'][j])==float(arc['parent_rewards'][j])==parent_entry['reward']
                        and float(allocation['source_costs'][j])==float(arc['parent_costs'][j])==parent_entry['cost'],
                        'parent action/native reward/cost comes from prior archive')

                require(skip is None and all(packet.get(k) is not None for k in
                    ('observed_eef','hand_quaternion_xyzw','gripper_qpos')), 'N32 required provenance absent')
                require(ov['iteration']==it and ov['identity']==identity and ov['slot']==15, 'N32 identity/slot')
                require(ov['binding']==expected_runtime['binding'] and ov['source_hashes']==expected_runtime['source_hashes']
                    and ov['config_sha256']==expected_runtime['config_sha256'], 'N32 task/source/config/run binding')
                require(hashlib.sha256(json.dumps(ov['config'],sort_keys=True,allow_nan=False).encode()).hexdigest()==ov['config_sha256']
                    and ov['config']['archive_eligible_capture_mode']==MODE
                    and ov['config']['capture_dwell_proposal_mode']=='off'
                    and ov['config']['n32_runtime_binding']==ov['binding'], 'N32 actual config')
                for k in packet:
                    require(optional(ov['observation'][k],packet[k]) if torch.is_tensor(packet[k]) else ov['observation'][k]==packet[k], 'N32 packet '+k)
                parents, selected, candidate, arrival, reason = enumerate_parents(archive, entries, it, mask, target, packet)
                require(len(ov['parents'])==len(parents), 'N32 all occupied parents required')
                for actual, wanted in zip(ov['parents'], parents):
                    require(set(actual)==set(wanted), 'N32 parent fields')
                    for key in wanted:
                        if key == 'source':
                            require(set(actual[key])==set(wanted[key]), 'N32 source fields')
                            for field,value in wanted[key].items():
                                require(same(actual[key][field],value) if torch.is_tensor(value) else actual[key][field]==value, 'N32 source '+field)
                        else:
                            require(actual[key]==wanted[key], 'N32 parent '+key)
                require(selected==ov['selected_cell'] and optional(candidate,ov['candidate'])
                    and arrival==ov['arrival_index'] and reason==ov['reason'], 'N32 independent selection')
                ordinary=shape(ov['original_post_rollout_population'],(16,64,128),True)
                require(same(ov['actual_scored_population'],actions) and same(ordinary[:15],actions[:15]), 'N32 other15/scored parity')
                require(same(actions[15],candidate if candidate is not None else ordinary[15]), 'N32 slot15')
                for boundary in ('prepare','apply'):
                    before,after=ov[boundary+'_rng_before'],ov[boundary+'_rng_after']
                    require(set(before)==set(after)=={'cpu','device'}, 'N32 RNG fields')
                    for device in before:
                        x,y=before[device],after[device]
                        if device=='device' and x is None:
                            require(y is None, 'N32 CPU RNG device')
                        else:
                            require(type(x) is torch.Tensor and type(y) is torch.Tensor
                                and x.dtype==y.dtype==torch.uint8 and x.ndim==y.ndim==1
                                and x.numel()>0 and torch.equal(x,y), 'N32 RNG parity')
                reasons.append(reason);changed+=candidate is not None
                if candidate is not None:proposals.append(candidate)
                counts['ambiguous_content_sources']+=sum(len(p['matching_occurrences'])>1 for p in parents)
                counts['other15_commitments_verified']+=1
            entries.extend(current)
            # Native cell IDs are attested original GPU assignments, not recomputed.
            cells=u['cell_ids'];require(type(cells) is torch.Tensor and cells.dtype==torch.int64 and cells.shape==(16,) and bool(((cells>=0)&(cells<16)).all()),'native cells')
            desc=shape(u['descriptors'],(16,2));lo=shape(u['bounds_lo'],(2,));hi=shape(u['bounds_hi'],(2,))
            require(desc.dtype==lo.dtype==hi.dtype==torch.float32 and bool((hi>lo).all()),'native descriptor/bounds')
            if fixed_bounds is None:fixed_bounds=(lo,hi)
            require(same(lo,fixed_bounds[0]) and same(hi,fixed_bounds[1]),'fixed bounds')
            parent=u['parent_cell_ids']
            if it==-1:require(parent is None,'initial parent')
            else:
                allocation=kinds['parent_allocation'][it]['values']
                require(type(parent) is torch.Tensor and parent.shape==(16,) and parent.dtype==torch.int64,'parent cells')
                arc=kinds['archive_parent_allocation'][it]['values'];require(torch.equal(parent,arc['parent_cell_ids']),'recorded parent association')
            for cell in sorted(set(cells.tolist())):
                candidates=[e for e,j in zip(current,cells.tolist()) if j==cell]
                best=min(candidates,key=lambda e:(-float(e['quality']),e['fingerprint']))
                incumbent=archive.get(cell)
                if incumbent is None or (-float(best['quality']),best['fingerprint'])<(-incumbent['reward'],incumbent['fingerprint']):
                    j=best['row'];archive[cell]={'cell_id':cell,'reward':float(best['quality']),'cost':float(best['cost']),
                        'descriptor_xy_m':desc[j].tolist(),'fingerprint':best['fingerprint'],'source_iter':it,
                        'parent_cell_id':None if parent is None else int(parent[j]),'insert_sequence':insert,'plan':best['plan']};insert+=1
            snapshots=[{k:v for k,v in e.items() if k!='plan'} for _,e in sorted(archive.items())]
            require(u['archive']==snapshots,'independent retention/tie/insert sequence')
        final=one('final_selection')['values'];best_cell,best=min(archive.items(),key=lambda kv:(-kv[1]['reward'],kv[1]['fingerprint'],kv[0]))
        require(final['selection_rule']=='archive_global_best' and same(final['selected_latent'],best['plan'].unsqueeze(0))
            and final['selected_quality']==best['reward'] and final['selected_cost']==best['cost'],'final archive choice')
        ordered=[entry for _,entry in sorted(archive.items())]
        require(same(final['population'],torch.stack([entry['plan'] for entry in ordered]))
            and final['selected_index']==sorted(archive).index(best_cell), 'final archive population/order')
        decoded=one('policy_action_decode')['values'];actions=best['plan'].float()[None,:8,[39,40,41,42,43,44,10]].clone();actions[:,:,-1]=torch.where(actions[:,:,-1]<0,-1.,1.)
        require(same(decoded['selected_latent'],best['plan'].float().unsqueeze(0)) and same(decoded['action_chunk'],actions)
            and same(one('decision_committed')['values']['action_chunk'],actions),'native representation/decoder/commit')
        executed=kinds['executed_action'];outcomes=kinds['pre_reset_outcome'];returned=kinds['step_returned'];horizon=one('decision_committed')['values']['execution_horizon']
        require(0<len(executed)==len(outcomes)==len(returned)<=horizon<=8,'execution coverage')
        ended=False
        for j,(act,out,ret) in enumerate(zip(executed,outcomes,returned)):
            require(not ended and act['global_step']==out['global_step']==ret['global_step']==context['global_step']+j
                and act['sequence']<out['sequence']<ret['sequence'] and same(act['values']['action_numpy'],actions[0,j]),'executed prefix')
            require(terminal_bool(out['values']['terminated'])==terminal_bool(ret['values']['terminated']),'terminal binding')
            ended=terminal_bool(ret['values']['terminated']) or terminal_bool(ret['values']['truncated'])
        require(ended or len(executed)==horizon,'unfinished prefix')
        scalar=metric.get('capture_dwell_proposal');require(isinstance(scalar,dict) and set(scalar)=={'schema','mode','canonical_batches','canonical_occurrences','opportunities','changed','reasons','overhead_seconds','overhead_scope','overhead_excludes','costs','provider_http_telemetry'},'scalar fields')
        require(scalar['schema']=='n32-archive-eligible-scalar-v1' and scalar['mode']==MODE and scalar['canonical_batches']==11
            and scalar['canonical_occurrences']==176 and scalar['opportunities']==10 and scalar['changed']==changed and scalar['reasons']==reasons
            and type(scalar['overhead_seconds']) in (int,float) and math.isfinite(scalar['overhead_seconds']) and scalar['overhead_seconds']>=0
            and scalar['overhead_scope']=='decision_init_record_prepare_apply_including_observer' and scalar['overhead_excludes']==OVERHEAD_EXCLUDES,'scalar counts/overhead')
        require(scalar['provider_http_telemetry']=='Unknown' and set(scalar['costs'])=={'selector_cpu_seconds','transfer_sync_seconds','recording_seconds'}
            and all(type(v) in (int,float) and math.isfinite(v) and v>=0 for v in scalar['costs'].values()), 'N32 measured costs/Unknown HTTP')
        counts['parent_rounds_verified']+=10;counts['opportunities_verified']+=10;counts['changed_proposals_verified']+=changed
        counts['executed_actions_verified']+=len(executed);counts['selected_proposal_content_decisions']+=int(any(same(best['plan'],p) for p in proposals))
    return counts


def counts(profile,metrics,report,guided_count=None, *, expected_runtime=None):
    require(profile in ARMS and report.get('accepted') is True and report.get('evidence_complete') is True,'generic audit incomplete')
    n=len(metrics);gate=report.get(GATE);observed=report['observed_counts']
    require(isinstance(gate,dict) and gate.get('schema')=='n32-independent-capture-dwell-v1' and gate.get('profile')==profile
        and gate.get('guided_decisions')==n and gate.get('canonical_batches_verified')==11*n
        and gate.get('canonical_candidates_verified')==176*n and observed.get('canonical_candidate_batch',0)==11*n,'profile-bound native gate missing/downgraded')
    if guided_count is not None:require(type(guided_count) is int and guided_count==n,'terminal guided count')
    for m in metrics:
        require(m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
            and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count'))
            and m.get('qd_archive_active_for_chunk') is (profile!='C0') and m.get('qd_quality_mode','provider')=='provider','frozen search counts/modes')
    if profile=='N32':
        require(isinstance(expected_runtime,dict) and gate.get('runtime_identity')==expected_runtime, 'N32 trusted runtime gate missing/different')
        require(gate.get('parent_rounds_verified')==gate.get('opportunities_verified')==gate.get('other15_commitments_verified')==10*n
            and sum(m.get('capture_dwell_proposal',{}).get('changed',-1) for m in metrics)==gate.get('changed_proposals_verified')
            and all(m.get('capture_dwell_proposal',{}).get('mode')==MODE for m in metrics),'N32 marker deletion/count mismatch')
    else:require(all('capture_dwell_proposal' not in m for m in metrics),'control mode')
    return {k:v for k,v in gate.items() if type(v) is int},{}


def from_output(profile,output,report,guided_count=None, *, expected_runtime=None):
    output=Path(output);mp=output/'eds_eval/eds_metrics.jsonl';cp=output/'eds_eval/episode_compute.jsonl'
    require(not mp.is_symlink() and (mp.is_file() or not mp.exists()) and cp.is_file() and not cp.is_symlink(),'metrics/compute path')
    metrics=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()] if mp.is_file() else []
    rows=[json.loads(x) for x in cp.read_text().splitlines() if x.strip()];require(len(rows)==1,'episode compute count')
    compute_check(rows[0],report,len(metrics))
    return counts(profile,metrics,report,rows[0]['guided_chunks'] if guided_count is None else guided_count,expected_runtime=expected_runtime)


def audit_output(profile,output,report,backend, *, expected_runtime):
    from scripts import audit_decision_evidence as generic
    require(backend.report()['kind']=='cpu','N32 CPU native audit only')
    output=Path(output);mp=output/'eds_eval/eds_metrics.jsonl';cp=output/'eds_eval/episode_compute.jsonl'
    metrics=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()] if mp.is_file() else []
    compute=[json.loads(x) for x in cp.read_text().splitlines() if x.strip()];require(len(compute)==1,'compute missing')
    root=output/'eds_eval/decision_evidence/episode_000';events=generic.load_events(root,json.loads((root/'status.json').read_text()))
    report=dict(report);report[GATE]=audit_events(profile,metrics,events,compute[0],expected_runtime=expected_runtime);counts(profile,metrics,report,compute[0]['guided_chunks'],expected_runtime=expected_runtime)
    return report


def compute_check(compute,report,n):
    gate=report.get(GATE,{});expected=gate.get('compute_expected')
    if gate.get('profile')=='N32':
        require(compute.get('task_id')==gate.get('runtime_identity',{}).get('binding',{}).get('task_id'), 'N32 compute task')
    require(isinstance(expected,dict) and expected.get('guided_chunks')==n
        and compute.get('policy_counters_available') is True and all(compute.get(k)==v for k,v in expected.items()),
        'bound independent compute gate differs')
