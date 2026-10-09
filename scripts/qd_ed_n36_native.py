"""N36 same-worker CPU evidence audit, derived from frozen N31 lineage checks. No production proposal/helper invocation.

Independently recomputes native projection/provider/descriptor/cells and archive
retention/visits/parents, plus binary64 proposal and physical trigger arithmetic. Pre-substitution commitments do not replay the model.
"""
from scripts.qd_ed_n36_arithmetic import verify_scores, verify_assignment, verify_parents
from collections import defaultdict
import json
import math
from pathlib import Path
import torch
from scripts.qd_ed_n31_reference import require, same, optional, shape, native_id, fingerprint, terminal_bool
from scripts.qd_ed_n36_reference import reconstruct, observation_same
from scripts.qd_ed_n36_lifecycle import equal
from scripts.qd_ed_n36_lifecycle import replay
import hashlib
from scripts.qd_ed_n30_native import provider_target

MODE='nonprogress_tangent_v1'
GATE='n36_nonprogress_tangent_audit'
ARMS=('N36',)
OVERHEAD_EXCLUDES=['Main_packet','provider_recognition','score_validate','adapter_capture_origin_copy','archive_snapshot_observer','whole_selection','N34_source_hashing','N36_source_hashing','N36_lifecycle_and_origin_observer']


def packet_identity(context, packet, target_binding):
    cv=context['values']
    require(isinstance(packet,dict) and type(packet.get('episode')) is int
        and packet['episode']==context['episode'] and optional(packet['keypoints'],cv['keypoints'])
        and packet['tracker']==cv.get('keypoint_tracking_snapshot'),'Main/context identity')
    for name,n in (('observed_eef',3),('hand_quaternion_xyzw',4),('gripper_qpos',2)):
        if packet.get(name) is not None:
            require(torch.is_tensor(packet[name]) and packet[name].shape==(n,) and packet[name].is_floating_point(), 'observation shape')
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
    nonfinite=any(packet.get(k) is not None and not bool(torch.isfinite(packet[k]).all())
        for k in ('observed_eef','hand_quaternion_xyzw','gripper_qpos'))
    return identity,'nonfinite_observation' if nonfinite else None,points[index]


def audit_events(profile, metrics, events, compute, *, expected_runtime=None, arithmetic_device="cpu"):
    require(profile in ARMS,'profile')
    if profile=='N36':
        require(isinstance(expected_runtime,dict) and set(expected_runtime)=={'binding','config_sha256','source_hashes'}, 'external N36 runtime trust anchor required')
    else:
        require(expected_runtime is None, 'control runtime binding must be absent')
    eligibility,lifecycle=replay(events)
    arithmetic=verify_scores(events,device=arithmetic_device)
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
    counts={'schema' :'n36-independent-nonprogress-tangent-v1','profile':profile,'guided_decisions':len(guided),'compute_expected':expected,
        'canonical_batches_verified':11*len(guided),'canonical_candidates_verified':176*len(guided),
        'parent_rounds_verified':0,'opportunities_verified':0,'changed_proposals_verified':0,
        'ambiguous_content_sources':0,'observation_contexts_verified':0,'executed_actions_verified':0,
        'native_delta_count_total':0,'decoded_delta_count_total':0,'zero_decoded_delta_memory_opportunities':0,
        'memory_proposals_retained_after_update':0,'other15_commitments_verified':0,'selected_proposal_content_decisions':0}
    if profile!='N36':
        require(not any(e['event'].startswith('n36_') for e in events),'control N36 markers')
        require(all('capture_dwell_proposal' not in m for m in metrics),'control N36 metrics')
        return counts
    require(not any(e['event'].startswith(('n30_','n31_','n32_','n34_','n35_')) for e in events),'mixed profile markers')
    groups=defaultdict(list)
    for e in events:groups[e['decision_id']].append(e)
    require(set(groups)=={e['decision_id'] for e in contexts},'unknown decision')
    byseq={e['sequence']:e for e in events};previous=None;mi=0
    for context in contexts:
        rows=groups[context['decision_id']];kinds=defaultdict(list)
        for e in rows:
            require(e['episode']==context['episode'],'episode mismatch')
            # replay() validates every event against the ordered recorder epoch,
            # which advances between automatic_reset_boundary and step_returned.
            kinds[e['event']].append(e)
        def one(k):
            require(len(kinds[k])==1,'missing/duplicate '+k);return kinds[k][0]
        p_event=one('n36_observation_context');packet=p_event['values']['packet']
        identity,skip,target=packet_identity(context,packet,provider_target(context))
        identity.update(expected_runtime['binding']);identity['decision_id']=context['decision_id']
        if context['values']['use_guidance']:
            require(one('n36_boundary_entry')['values']['identity']==identity
                and one('n36_selected_occurrence')['values']['identity']==identity,'lifecycle context identity')
        require(context['sequence']<p_event['sequence']<one('policy_action_decode')['sequence'],'packet order')
        if previous is not None and context['global_step']>0 and not terminal_bool(previous['values']['terminated']):
            require(previous['global_step']==context['global_step']-1,'previous observed step')
            obs=previous['values']['observation']
            for key,native_key,n in [('observed_eef','robot0_eef_pos',3),('hand_quaternion_xyzw','robot0_eef_quat',4),('gripper_qpos','robot0_gripper_qpos',2)]:
                if packet[key] is not None:
                    require(native_key in obs and observation_same(packet[key],obs[native_key].reshape(n)),'previous raw observation '+key)
        if kinds['pre_reset_outcome']:previous=kinds['pre_reset_outcome'][-1]
        counts['observation_contexts_verified']+=1
        if not context['values']['use_guidance']:
            require(not any(kinds[x] for x in ('n36_canonical_cache','n36_capture_dwell_opportunity','n36_archive_update')),'unguided cache')
            continue
        runtime=one('n36_native_runtime')['values']
        metric=metrics[mi];mi+=1
        canon=kinds['canonical_candidate_batch'];cache=kinds['n36_canonical_cache'];updates=kinds['n36_archive_update'];ops=kinds['n36_capture_dwell_opportunity']
        require(len(canon)==len(cache)==len(updates)==11 and len(ops)==10
            and [e['values']['iter_idx'] for e in canon]==list(range(-1,10)),'canonical opportunity coverage')
        require(runtime=={k:arithmetic[k] for k in ('device','torch_version','cuda_version','torch_build')} | {'dtype':str(canon[0]['values']['candidates'].dtype)}, 'actual arithmetic runtime/build/dtype')
        require(len(kinds['parent_allocation'])==10,'parent coverage')
        archive={};insert=0;entries=[];fixed_bounds=None;reasons=[];changed=0;proposals=[];visits=torch.zeros(16,dtype=torch.long)
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

                verify_parents(archive,visits,arc,ov['config'],identity,it)
                best_cell,best=min(archive.items(),key=lambda kv:(-kv[1]['reward'],kv[1]['fingerprint'],kv[0]))
                ar={'cell':best_cell,'source_iter':best['source_iter'],'insert_sequence':best['insert_sequence'],'fingerprint':best['fingerprint'],'native_identity':native_id(best['plan'])}
                require(ov['iteration']==it and ov['identity']==identity and ov['archive']==ar and ov['slot']==15,'archive global best/identity/slot')
                matches=[e for e in entries if e['iteration']==best['source_iter'] and e['fingerprint']==best['fingerprint'] and same(e['plan'],best['plan'])]
                require(matches and ov['matching_occurrences']==[e['occurrence'] for e in matches]
                    and ov['association']==('unique_occurrence' if len(matches)==1 else 'identical_content_multiple_occurrences'),'occurrence ambiguity')
                first=matches[0]
                for e in matches:
                    require(float(e['quality'])==best['reward'] and float(e['cost'])==best['cost'] and all(optional(e[k],first[k]) for k in ('projection','quality','cost','source_origin','cast_origin')),'duplicate disagreement')
                bound=ov['source'];require(set(bound)==set(first),'source fields')
                for k,value in first.items():require(same(bound[k],value) if torch.is_tensor(value) else bound[k]==value,'source '+k)
                for k in packet:require(observation_same(ov['observation'][k],packet[k]) if torch.is_tensor(packet[k]) else ov['observation'][k]==packet[k],'snapshot '+k)
                require(ov['binding']==expected_runtime['binding'] and packet.get('task_id')==ov['binding']['task_id']
                    and ov['source_hashes']==expected_runtime['source_hashes']
                    and ov['config_sha256']==expected_runtime['config_sha256']
                    and hashlib.sha256(json.dumps(ov['config'],sort_keys=True,allow_nan=False).encode()).hexdigest()==ov['config_sha256'], 'external runtime/source/config binding')
                require(ov['config']['observed_jaw_approach_mode']=='observed_jaw_approach_v1'
                    and ov['config']['nonprogress_tangent_mode']==MODE
                    and ov['config']['closure_intent_mode']=='off' and ov['config']['n35_runtime_binding'] is None
                    and ov['config']['n34_runtime_binding']==ov['binding']
                    and ov['config']['capture_dwell_proposal_mode']=='off'
                    and ov['config']['archive_eligible_capture_mode']=='off'
                    and ov['config']['n36_runtime_binding']==ov['binding'], 'N36 actual config')
                candidate,arrival,reason,path=(None,None,skip,None) if skip else reconstruct(first['plan'],target,packet['observed_eef'],packet['hand_quaternion_xyzw'],packet['gripper_qpos'],eligible=eligibility[context['decision_id']])
                require(ov['memory_eligible']==eligibility[context['decision_id']] and ov['template_occurrence']==best['occurrence_id'],'latched memory/direct template')
                require(equal(ov['path'],path),'independent tangent geometry/clipping/native encoding')
                def decode(x):
                    a=x[:8,[39,40,41,42,43,44,10]].float().clone();a[:,-1]=torch.where(a[:,-1]<0,-1.,1.);return a
                require(ov['native_delta_count']==(0 if candidate is None else int((candidate.contiguous().view(torch.uint8).reshape(-1,candidate.element_size())!=
                        best['plan'].contiguous().view(torch.uint8).reshape(-1,candidate.element_size())).any(dim=1).sum()))
                    and ov['decoded_delta_count']==(0 if candidate is None else int((decode(candidate)!=decode(best['plan'])).sum())),'native/decoded deltas including zero')
                require(optional(candidate,ov['candidate']) and arrival==ov['arrival_index'] and reason==ov['reason'],'independent proposal')
                require(same(ov['actual_scored_population'],actions) and ov['ordinary_other15']=={'dtype':str(actions.dtype),'shape':[15,64,128],'native_identity':native_id(actions[:15])},'scored batch/other15 commitment')
                ordinary=shape(ov['ordinary_population'],(16,64,128),True)
                require(same(ordinary[:15],actions[:15]) and same(ordinary[15],ov['original_post_rollout_slot15']),'actual ordinary population preserved')
                require(same(actions[15],candidate if candidate is not None else ov['original_post_rollout_slot15']),'slot15 binding')
                counts['native_delta_count_total']+=ov['native_delta_count']
                counts['decoded_delta_count_total']+=ov['decoded_delta_count']
                counts['zero_decoded_delta_memory_opportunities']+=int(ov['memory_eligible'] and ov['decoded_delta_count']==0)
                reasons.append(reason);changed+=candidate is not None
                if candidate is not None:proposals.append(candidate)
                counts['ambiguous_content_sources']+=int(len(matches)>1)
                counts['other15_commitments_verified']+=1
            entries.extend(current)
            # Native cell IDs are independently recomputed below on the bound device.
            cells=u['cell_ids'];require(type(cells) is torch.Tensor and cells.dtype==torch.int64 and cells.shape==(16,) and bool(((cells>=0)&(cells<16)).all()),'native cells')
            desc=shape(u['descriptors'],(16,2));lo=shape(u['bounds_lo'],(2,));hi=shape(u['bounds_hi'],(2,))
            require(desc.dtype==lo.dtype==hi.dtype==torch.float32 and bool((hi>lo).all()),'native descriptor/bounds')
            if fixed_bounds is None:fixed_bounds=(lo,hi)
            require(same(lo,fixed_bounds[0]) and same(hi,fixed_bounds[1]),'fixed bounds')
            verify_assignment(actions,packet['keypoints'].to(actions),u,it==-1,device=arithmetic_device)
            visits+=torch.bincount(cells,minlength=16)
            require(u['cumulative_visits'].dtype==torch.int64 and torch.equal(visits,u['cumulative_visits']),'actual archive cumulative visits')
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
                        'parent_cell_id':None if parent is None else int(parent[j]),'insert_sequence':insert,'plan':best['plan'],'occurrence_id':best['occurrence']};insert+=1
            snapshots=[{k:v for k,v in e.items() if k!='plan'} for _,e in sorted(archive.items())]
            require(u['archive']==snapshots,'independent retention/tie/insert sequence')
            if it>=0 and ops[it]['values']['reason']=='nonprogress_tangent' and ops[it]['values']['candidate'] is not None:
                counts['memory_proposals_retained_after_update']+=int(any(x['occurrence_id']==(it+1)*16+15 for x in snapshots))
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
        scalar=metric.get('capture_dwell_proposal');require(isinstance(scalar,dict) and set(scalar)=={'schema','mode','canonical_batches','canonical_occurrences','opportunities','changed','reasons','overhead_seconds','overhead_scope','overhead_excludes','native_delta_counts','decoded_delta_counts','memory_eligible'},'scalar fields')
        require(scalar['schema']=='n36-nonprogress-tangent-scalar-v1' and scalar['mode']==MODE and scalar['canonical_batches']==11
            and scalar['canonical_occurrences']==176 and scalar['opportunities']==10 and scalar['changed']==changed and scalar['reasons']==reasons
            and type(scalar['overhead_seconds']) in (int,float) and math.isfinite(scalar['overhead_seconds']) and scalar['overhead_seconds']>=0
            and scalar['overhead_scope']=='decision_init_record_prepare_apply_including_observer' and scalar['overhead_excludes']==OVERHEAD_EXCLUDES,'scalar counts/overhead')
        require(scalar['native_delta_counts']==[op['values']['native_delta_count'] for op in ops]
            and scalar['decoded_delta_counts']==[op['values']['decoded_delta_count'] for op in ops]
            and scalar['memory_eligible']==eligibility[context['decision_id']],'scalar native/decoded/memory telemetry')
        counts['parent_rounds_verified']+=10;counts['opportunities_verified']+=10;counts['changed_proposals_verified']+=changed
        counts['executed_actions_verified']+=len(executed);counts['selected_proposal_content_decisions']+=int(any(same(best['plan'],p) for p in proposals))
    from scripts.qd_ed_n36_response import summarize
    counts['physical_response']=summarize(events)
    opportunities=[e['values'] for e in events if e['event']=='n36_capture_dwell_opportunity']
    counts['eligible_opportunities']=sum(x['memory_eligible'] for x in opportunities)
    counts['detour_insertions']=sum(x['reason']=='nonprogress_tangent' and x['candidate'] is not None for x in opportunities)
    counts['arithmetic']=arithmetic
    counts['lifecycle']=lifecycle
    counts['runtime_identity']=expected_runtime
    return counts


def audit_output(output, report, *, expected_runtime, arithmetic_device="cpu"):
    """Compose with the unchanged generic native audit; never authorize dispatch."""
    from scripts import audit_decision_evidence as generic
    require(report.get('accepted') is True and report.get('evidence_complete') is True,
            'generic native audit must pass first')
    output=Path(output)
    metrics=[json.loads(line) for line in (output/'eds_eval/eds_metrics.jsonl').read_text().splitlines() if line.strip()]
    compute=[json.loads(line) for line in (output/'eds_eval/episode_compute.jsonl').read_text().splitlines() if line.strip()]
    require(len(compute)==1, 'one episode compute record required')
    root=output/'eds_eval/decision_evidence/episode_000'
    events=generic.load_events(root,json.loads((root/'status.json').read_text()))
    result=dict(report)
    result[GATE]=audit_events('N36',metrics,events,compute[0],expected_runtime=expected_runtime,arithmetic_device=arithmetic_device)
    return result
