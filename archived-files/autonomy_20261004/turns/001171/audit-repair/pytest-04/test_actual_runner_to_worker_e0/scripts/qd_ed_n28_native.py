"""N28 profile-bound native audit; historical controls retain their exact audits."""
import json
from pathlib import Path
import torch
from scripts import qd_ed_n27_native as old
from scripts import qd_ed_n24_native as base_counts
from scripts.qd_ed_n28_reference import audit_witness,require,exact,SOURCE,INPUT
ARMS=('C0','Q0','N27','N28')
GATE='n28_parent_before_renoise_audit'
MODE=old.MODE
SLOTS=(('initial',-1),)+tuple(('parent',i) for i in range(10))
PARENT_FIELDS=(old.FIELDS-{'model_output_before','model_output_after'})|{'parent_offspring_before','parent_offspring_after'}
metric_rows=old.metric_rows


def scalar(row):
    if row.get('phase')=='initial':return old.scalar(row)
    require(row.get('schema')=='n28-parent-rbf-call-summary-v1' and row.get('source')==SOURCE
        and row.get('input_source')==INPUT and row.get('input_binding')=='selected_offspring_before_original_renoise'
        and row.get('phase')=='parent' and row.get('denoising_step') is None and row.get('timestep') is None
        and row.get('rollout_diversity_placement')=='parent_before_renoise_v1'
        and type(row.get('parent_allocation_sequence')) is int
        and row.get('update_operand_semantics')=='unconstrained_native_parent_proposal_before_feasible_ray'
        and row.get('after_semantics')=='assigned_parent_offspring; not model output or final action',
        'N28 parent scalar semantics missing')
    # Reuse unchanged scalar arithmetic field checks, after independently requiring
    # actual parent semantics above. This copy is never returned as old evidence.
    common={**row,'schema':'n27-rbf-call-summary-v1','source':old.SOURCE,
      'input_source':'model_output_sample_v1','input_binding':'same_forward_unmodified_model_output',
      'update_operand_semantics':'unconstrained_native_proposal_before_feasible_ray','denoising_step':0,'timestep':0}
    old.scalar(common)


def call_rows(metric):
    require(metric.get('initial_diversity_descriptor_mode')==metric.get('rollout_diversity_descriptor_mode')==MODE,'N28 mode absent')
    initial=metric.get('initial_direction_rbf_evidence_by_step');groups=metric.get('rollout_direction_rbf_evidence_by_iter')
    rounds=metric.get('rollout_rbf_steps_by_iter')
    require(isinstance(initial,list) and len(initial)==4==metric.get('initial_diversity_steps')
        and isinstance(groups,list) and len(groups)==10 and isinstance(rounds,list) and len(rounds)==10
        and metric.get('rollout_diversity_steps_applied')==0,'N28 initial/parent/post-forward counts differ')
    require([x.get('denoising_step') for x in initial]==[0,1,2,3]
        and all(x.get('phase')=='initial' and x.get('iteration')==-1 for x in initial),'N28 initial schedule differs')
    for i,(rows,info) in enumerate(zip(groups,rounds)):
        n=(3,2,2,2,2,1,1,1,1,1)[i]
        require(len(rows)==1 and rows[0].get('phase')=='parent' and rows[0].get('iteration')==i
            and info.get('iter_idx')==i and info.get('n_trunc_steps')==n and info.get('step_indices')==[]
            and info.get('step_flags')==[False]*n and info.get('step_count')==0 and info.get('fallback_used') is False,
            'N28 parent/unchanged denoise schedule differs')
    rows=initial+[g[0] for g in groups]
    for x in rows:scalar(x)
    require(all(x['global_step']==metric.get('global_step') for x in rows),'N28 metric decision differs')
    require(all(a['timestep']>b['timestep'] for a,b in zip(initial,initial[1:])),'N28 initial time differs')
    return rows


def counts(profile,metrics,report,guided_count=None):
    require(profile in ARMS,'N28 unknown profile')
    if profile!='N28':
        require(not report.get(GATE),'N28 candidate gate on control')
        return old.counts(profile,metrics,report,guided_count)
    counts,aux=base_counts.counts('N23',metrics,report,guided_count)
    require(not report.get(old.GATE) and not report.get(old.control.GATE),'N28 cross-profile gate')
    gate=report.get(GATE,{})
    rows=[x for m in metrics for x in call_rows(m)]
    require(gate.get('schema')=='n28-native-parent-rbf-audit-v1' and gate.get('accepted') is True
        and gate.get('guided_decisions')==len(metrics) and gate.get('all_call_summaries_verified')==len(rows)
        and gate.get('witness_calls_verified')==(11 if metrics else 0)
        and gate.get('parent_boundaries_verified')==(10 if metrics else 0),'N28 profile gate absent/incomplete')
    for key,expected in {'zero_gradient_calls':sum(x['zero_gradient'] for x in rows),
        'clipped_components':sum(x['clipped_components'] for x in rows),'limited_rows':sum(x['limited_rows'] for x in rows),
        'realized_nonzero_delta_components':sum(x['realized_nonzero_delta_components'] for x in rows)}.items():
        require(gate.get(key)==expected,'N28 scalar aggregate differs');counts[key]=expected
    counts.update({k:gate[k] for k in ('all_call_summaries_verified','witness_calls_verified','parent_boundaries_verified')})
    return counts,aux


def from_output(profile,output,report,guided_count=None):
    require(profile in ARMS,'N28 unknown profile')
    if profile!='N28':
        require(not report.get(GATE),'N28 gate on control');return old.from_output(profile,output,report,guided_count)
    base_counts.from_output('N23',output,report,guided_count)
    return counts(profile,metric_rows(output),report,guided_count)


def audit_events(profile,metrics,events,compute,backend):
    own=[e for e in events if e['event'].startswith(('n28_rbf','n28_parent_renoise'))]
    if profile!='N28':
        require(profile in ARMS and not own,'N28 evidence on wrong profile')
        return old.audit_events(profile,metrics,events,compute,backend)
    require(not any(e['event'].startswith(('n25_rbf','n26_rbf','n27_rbf')) for e in events),'N28 cross-profile witness')
    rows=[x for m in metrics for x in call_rows(m)]
    require(type(compute.get('guided_chunks')) is int and compute['guided_chunks']==len(metrics)
        and compute.get('rbf_gradient_calls')==len(rows) and compute.get('rbf_gradient_batch_rows')==16*len(rows),
        'N28 whole-episode gradient costs differ')
    contexts=[e for e in events if e['event']=='decision_context' and e['values'].get('use_guidance') is True]
    require(len(contexts)==len(metrics),'N28 guided context count differs')
    for metric,ctx in zip(metrics,contexts):
        require(metric.get('global_step')==ctx['global_step'] and all(x['stage']==ctx['values']['stage'] for x in call_rows(metric)),
                'N28 all-call context association differs')
    witnesses=[e for e in own if e['event']=='n28_rbf_witness'];coverage=[e for e in own if e['event']=='n28_rbf_witness_coverage']
    boundaries=[e for e in own if e['event']=='n28_parent_renoise_input'];checks=[];numeric=0
    if not metrics:require(not own,'N28 zero-guided evidence present')
    else:
        ctx=contexts[0];expected=[call_rows(metrics[0])[0]]+[g[0] for g in metrics[0]['rollout_direction_rbf_evidence_by_iter']]
        require(len(witnesses)==11 and len(boundaries)==10 and len(coverage)==1,'N28 bounded coverage differs')
        for e in own:
            require(all(e[k]==ctx[k] for k in ('episode','decision_id','global_step','reset_sequence')),'N28 witness cross-decision/reset')
        seq={e['sequence']:e for e in events};require(len(seq)==len(events),'N28 duplicate native event sequence')
        for slot,(event,row) in enumerate(zip(witnesses,expected)):
            tensors=event['values']['tensors'];meta=event['values']['metadata'];fields=old.FIELDS if slot==0 else PARENT_FIELDS
            require(set(tensors)==fields and meta.get('schema')=='n28-bounded-rbf-witness-v1' and meta.get('source')==SOURCE
                and meta.get('exact_cuda_replay_claim') is False and meta.get('call')=={k:v for k,v in row.items() if k not in {'stage','global_step'}},
                'N28 witness/scalar identity differs')
            for key,t in tensors.items():
                shape=(16,3) if key in {'source_origins','cast_origins'} else (16,8,3)
                require(torch.is_tensor(t) and tuple(t.shape)==shape and bool(torch.isfinite(t).all()),'N28 bounded tensor differs')
                info=meta.get('tensors',{}).get(key,{})
                require(info.get('dtype')==str(t.dtype) and info.get('shape')==list(t.shape),'N28 tensor metadata differs')
            pos=events.index(event);origins=events[pos-16:pos]
            require(len(origins)==16 and all(e['event']=='projection_origin' and e['decision_id']==ctx['decision_id'] for e in origins),
                    'N28 same-call origin sequence missing')
            for j,e in enumerate(origins):
                require(exact(e['values']['source_eef_position'],tensors['source_origins'][j])
                    and exact(e['values']['cast_eef_start'],tensors['cast_origins'][j]),'N28 origin bytes differ')
            size=sum(t.numel()*t.element_size() for t in tensors.values());require(size==meta.get('numeric_bytes'),'N28 byte count differs')
            meta_bytes=len(json.dumps(meta,allow_nan=False).encode())
            if slot==0:checks.append(old.audit_witness(tensors,meta,backend))
            else:
                i=slot-1;allocation=seq.get(row['parent_allocation_sequence']);boundary=boundaries[i]
                require(allocation is not None and allocation['event']=='parent_allocation'
                    and all(allocation[k]==ctx[k] for k in ('episode','decision_id','global_step','reset_sequence'))
                    and allocation['values'].get('iter_idx')==i and allocation['values'].get('elite_count')==0
                    and allocation['sequence']<event['sequence']<boundary['sequence'],'N28 allocation/witness/boundary identity differs')
                values=allocation['values'];selected=values['source_population'].index_select(0,values['parent_indices'])
                require(selected.shape==(16,64,128) and exact(selected[:,:8,[39,40,41]],tensors['input_xyz']),
                        'N28 allocation actual parent bytes differ')
                b=boundary['values'];prefix=b['prefix'];bs=prefix.numel()*prefix.element_size()
                require(b['metadata']=={'schema':'n28-parent-renoise-boundary-v1','iteration':i,
                    'parent_allocation_sequence':allocation['sequence'],'parent_witness_sequence':event['sequence'],
                    'n_trunc_steps':(3,2,2,2,2,1,1,1,1,1)[i],'same_tensor_object_verified':True,'numeric_bytes':bs,
                    'observation':'actual _eds_renoise_reference entry before noise draw'}
                    and exact(prefix,tensors['parent_offspring_after']), 'N28 actual renoise input binding differs')
                require(boundary['sequence']==event['sequence']+1,'N28 intervening event before actual renoise entry')
                size+=bs;meta_bytes+=len(json.dumps(b['metadata']).encode());checks.append(audit_witness(tensors,meta,backend))
            numeric+=size;require(size<=20480 and numeric<=225280 and meta_bytes<=16384,'N28 combined witness cap exceeded')
        require(coverage[0]['values']=={'selected_slots':[list(x) for x in SLOTS],'missing_slots':[],
            'numeric_bytes':numeric,'max_calls':11,'numeric_cap_bytes':225280},'N28 coverage mismatch')
    return {'schema':'n28-native-parent-rbf-audit-v1','accepted':True,'guided_decisions':len(metrics),
       'all_call_summaries_verified':len(rows),'witness_calls_verified':len(checks),'parent_boundaries_verified':len(boundaries),
       'witness_numeric_bytes':numeric,'witness_checks':checks,'zero_gradient_calls':sum(x['zero_gradient'] for x in rows),
       'clipped_components':sum(x['clipped_components'] for x in rows),'limited_rows':sum(x['limited_rows'] for x in rows),
       'realized_nonzero_delta_components':sum(x['realized_nonzero_delta_components'] for x in rows),
       'arithmetic_scope':'Exact assigned-backend first-guided witnesses; later scalar consistency only. Denoiser causal transfer Unknown.'}


def audit_output(profile,output,report,backend):
    if profile!='N28':return old.audit_output(profile,output,report,backend)
    from scripts import audit_decision_evidence as base
    output=Path(output);root=output/'eds_eval/decision_evidence/episode_000'
    require(report.get('accepted') is True and report.get('evidence_complete') is True,'N28 generic audit missing')
    events=base.load_events(root,json.loads((root/'status.json').read_text()))
    compute=[json.loads(x) for x in (output/'eds_eval/episode_compute.jsonl').read_text().splitlines() if x.strip()]
    require(len(compute)==1,'N28 compute denominator differs')
    report[GATE]=audit_events(profile,metric_rows(output),events,compute[0],backend)
    report['n23_arithmetic_backend']=backend.report();from_output(profile,output,report,compute[0]['guided_chunks']);return report
