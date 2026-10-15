"""Profile-bound N26 scalar and bounded independent same-backend witness audit."""
import json
import math
from pathlib import Path
import torch
from scripts import qd_ed_n24_native as prior
from scripts import qd_ed_n25_native as control
from scripts.qd_ed_n26_reference import audit_witness,require,exact

ARMS=('C0','Q0','N25','N26')
MODE='actuator_clipped_eef_v1'
SOURCE='core.qd_clean_output_rbf:model_output_sample_v1'
GATE='n26_clean_output_rbf_audit'
SLOTS=(('initial',-1),)+tuple(('rollout',i) for i in range(10))
FIELDS={'input_xyz','source_origins','cast_origins','projected_xyz','gradient_before','gradient_after',
        'update_operand','model_output_before','model_output_after'}


def metric_rows(output):
    path=Path(output)/'eds_eval/eds_metrics.jsonl'
    require(not path.is_symlink() and (path.is_file() or not path.exists()),'metric file unsafe')
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.is_file() else []


def scalar(row):
    require(row.get('descriptor_mode')==MODE and row.get('source')==SOURCE
        and row.get('schema')=='n26-rbf-call-summary-v1'
        and row.get('input_source')=='model_output_sample_v1' and row.get('prediction_type')=='sample'
        and row.get('input_binding')=='same_forward_unmodified_model_output' and row.get('model_jacobian_used') is False and row.get('absolute_fallback_used') is False
        and row.get('summary_only_not_exact_replay') is True and row.get('input_shape')==[16,64,128]
        and row.get('input_dtype') in {'torch.float32','torch.bfloat16'} and row.get('horizon')==8
        and row.get('translation_indices')==[39,40,41] and row.get('translation_components')==384
        and row.get('update_operand_is_measured_output_delta') is False,'call mode/source/shape differs')
    from scripts.qd_ed_n26_reference import layout_name
    layout_name(row.get('input_stride'))
    names=('clipped_components','boundary_components','interior_components')
    require(all(type(row.get(k)) is int and row[k]>=0 for k in names)
        and sum(row[k] for k in names)==384,'clipping denominator differs')
    require(row.get('nonfinite_count')==0 and type(row.get('zero_gradient')) is bool,'gradient status differs')
    for key in ('gradient_before_normalization','gradient_after_normalization','masked_gradient','update_operand'):
        v=row.get(key,{})
        require(v.get('finite') is True and type(v.get('zero')) is bool
            and type(v.get('norm')) in (int,float) and math.isfinite(v['norm']) and v['norm']>=0
            and v.get('norm_dtype') in {'torch.float32','torch.bfloat16'}
            and (not v['zero'] or v['norm']==0),'gradient summary differs')
    require(row['zero_gradient']==row['gradient_after_normalization']['zero'],'zero summary differs')
    require(all(type(row.get(k)) is int for k in ('iteration','denoising_step','timestep','global_step','stage')),
        'call identity incomplete')
    require(row['denoising_step']>=0 and row['timestep']>=0,'call step invalid')


def call_rows(metric):
    require(metric.get('initial_diversity_descriptor_mode')==metric.get('rollout_diversity_descriptor_mode')==MODE,
            'required N26 mode absent/downgraded')
    initial=metric.get('initial_direction_rbf_evidence_by_step');rollout=metric.get('rollout_direction_rbf_evidence_by_iter')
    rounds=metric.get('rollout_rbf_steps_by_iter')
    require(isinstance(initial,list) and isinstance(rollout,list) and len(rollout)==10
        and isinstance(rounds,list) and len(rounds)==10,'call groups missing')
    require(len(initial)==4 and len(initial)==metric.get('initial_diversity_steps')
        and sum(map(len,rollout))==metric.get('rollout_diversity_steps_applied'),'step counters differ')
    require([v.get('denoising_step') for v in initial]==list(range(len(initial))),'initial non-prefix calls')
    require(all(v.get('phase')=='initial' and v.get('iteration')==-1 for v in initial),'initial scope differs')
    for i,(rows,info) in enumerate(zip(rollout,rounds)):
        length=info.get('n_trunc_steps')
        require(type(length) is int and length==(3,2,2,2,2,1,1,1,1,1)[i] and info.get('iter_idx')==i,'rollout schedule differs')
        flags=[j<math.ceil(length*.6) for j in range(length)]
        indices=[j for j,v in enumerate(flags) if v]
        require(info.get('step_indices')==indices and info.get('step_flags')==flags
            and info.get('step_count')==len(rows)==len(indices) and info.get('fallback_used') is False
            and [v.get('denoising_step') for v in rows]==indices,'rollout active-call schedule differs')
        require(all(v.get('phase')=='rollout' and v.get('iteration')==i for v in rows),'rollout scope differs')
    allrows=initial+[v for rows in rollout for v in rows]
    for row in allrows:scalar(row)
    require(all(v['global_step']==metric.get('global_step') for v in allrows),'metric decision binding differs')
    for rows in [initial,*rollout]:
        require(all(a['timestep']>b['timestep'] for a,b in zip(rows,rows[1:])),'nondecreasing denoising time')
    return allrows


def counts(profile,metrics,report,guided_count=None):
    require(profile in ARMS,'unknown arm')
    if profile!='N26':
        require(not report.get(GATE),'control has N26 audit gate')
        return control.counts(profile,metrics,report,guided_count)
    counts,aux=prior.counts('N23',metrics,report,guided_count)
    require(not report.get(control.GATE),'N26 downgraded/cross-profile audit gate')
    gate=report.get(GATE)
    require(isinstance(gate,dict) and gate.get('schema')=='n26-native-rbf-audit-v1'
        and gate.get('accepted') is True and gate.get('guided_decisions')==len(metrics),'N26 profile gate missing')
    rows=[r for m in metrics for r in call_rows(m)]
    require(gate.get('all_call_summaries_verified')==len(rows)
        and type(gate.get('witness_calls_verified')) is int and gate['witness_calls_verified']==(11 if metrics else 0)
        and gate.get('zero_gradient_calls')==sum(v['zero_gradient'] for v in rows)
        and gate.get('clipped_components')==sum(v['clipped_components'] for v in rows),'N26 audit counts differ')
    counts.update({k:gate[k] for k in ('all_call_summaries_verified','witness_calls_verified','zero_gradient_calls','clipped_components')})
    return counts,aux


def from_output(profile,output,report,guided_count=None):
    # Preserve strict episode/native/metric zero-guided omission compatibility.
    require(profile in ARMS,'unknown arm')
    if profile!='N26':
        require(not report.get(GATE),'control has N26 audit gate')
        return control.from_output(profile,output,report,guided_count)
    prior.from_output('N23',output,report,guided_count)
    return counts(profile,metric_rows(output),report,guided_count)


def audit_events(profile,metrics,events,compute,backend):
    require(profile in ARMS,'unknown arm')
    witness=[e for e in events if e['event']=='n26_rbf_witness']
    coverage=[e for e in events if e['event']=='n26_rbf_witness_coverage']
    if profile!='N26':
        require(not witness and not coverage,'control has N26 witness')
        return control.audit_events(profile,metrics,events,compute,backend)
    require(not any(e['event'].startswith('n25_rbf') for e in events),'N26 has cross-profile witness')
    rows=[row for m in metrics for row in call_rows(m)]
    require(type(compute.get('guided_chunks')) is int and compute['guided_chunks']==len(metrics)
        and compute.get('rbf_gradient_calls')==len(rows) and compute.get('rbf_gradient_batch_rows')==16*len(rows),
        'whole-episode RBF costs differ')
    contexts=[e for e in events if e['event']=='decision_context' and e['values'].get('use_guidance') is True]
    require(len(contexts)==len(metrics),'guided context denominator differs')
    for metric,ctx in zip(metrics,contexts):
        require(metric.get('global_step')==ctx['global_step'] and all(row['stage']==ctx['values']['stage'] for row in call_rows(metric)),
                'all-call context/stage association differs')
    checks=[];numeric=0
    if not metrics:require(not witness and not coverage,'zero-guided witness present')
    else:
        context=contexts[0]
        require(all(e['decision_id']==context['decision_id'] and e['global_step']==context['global_step']
            and e['reset_sequence']==context['reset_sequence'] and e['episode']==context['episode'] for e in witness+coverage),
            'witness moved across decision/reset')
        first=call_rows(metrics[0]);expected=[]
        for slot in SLOTS:
            group=[r for r in first if (r['phase'],r['iteration'])==slot]
            if group:expected.append(group[0])
        require(len(witness)==len(expected)<=11 and len(coverage)==1,'witness missing/duplicate/extra')
        for event,row in zip(witness,expected):
            value=event['values'];tensors=value.get('tensors',{});meta=value.get('metadata',{})
            require(set(tensors)==FIELDS and meta.get('schema')=='n26-bounded-rbf-witness-v1'
                and meta.get('source')==SOURCE and meta.get('exact_cuda_replay_claim') is False,'witness schema differs')
            # Capture is before loop closure attaches these two scalar identities.
            expected_call={k:v for k,v in row.items() if k not in {'global_step','stage'}}
            require(meta.get('call')==expected_call and row['stage']==context['values']['stage'],'call/scalar association differs')
            for name,tensor in tensors.items():
                shape=(16,3) if name in {'source_origins','cast_origins'} else (16,8,3)
                require(torch.is_tensor(tensor) and tuple(tensor.shape)==shape and bool(torch.isfinite(tensor).all()),
                        'witness tensor shape/nonfinite')
            position=next(i for i,e in enumerate(events) if e['sequence']==event['sequence'])
            origin_rows=events[position-16:position]
            require(position>=16 and len(origin_rows)==16
                and all(e['event']=='projection_origin' and e['decision_id']==context['decision_id'] for e in origin_rows),
                'same-call origin acquisition sequence missing')
            for j,origin in enumerate(origin_rows):
                require(exact(origin['values']['source_eef_position'],tensors['source_origins'][j])
                    and exact(origin['values']['cast_eef_start'],tensors['cast_origins'][j]),'origin witness association differs')
            size=sum(t.numel()*t.element_size() for t in tensors.values());numeric+=size
            require(size==meta.get('numeric_bytes') and size<=20480 and numeric<=225280
                and len(json.dumps(meta,allow_nan=False).encode())<=16384,'witness cap differs')
            require(set(meta.get('tensors',{}))==FIELDS,'witness tensor metadata missing')
            for name,t in tensors.items():
                info=meta['tensors'][name]
                require(info.get('dtype')==str(t.dtype) and info.get('shape')==list(t.shape)
                    and isinstance(info.get('capture_stride_before_serialization'),list),'witness metadata differs')
            checks.append(audit_witness(tensors,meta,backend))
        covered=[list((r['phase'],r['iteration'])) for r in expected]
        require(coverage[0]['values']=={'selected_slots':covered,'missing_slots':[list(s) for s in SLOTS if list(s) not in covered],
            'numeric_bytes':numeric,'max_calls':11,'numeric_cap_bytes':225280},'witness coverage differs')
    return {'schema':'n26-native-rbf-audit-v1','accepted':True,'guided_decisions':len(metrics),
        'all_call_summaries_verified':len(rows),'witness_calls_verified':len(checks),'witness_numeric_bytes':numeric,
        'zero_gradient_calls':sum(v['zero_gradient'] for v in rows),
        'clipped_components':sum(v['clipped_components'] for v in rows),'witness_checks':checks,
        'arithmetic_scope':'Exact same-backend reconstruction only of bounded first-guided witnesses; later calls scalar consistency only'}


def audit_output(profile,output,report,backend):
    from scripts import audit_decision_evidence as base
    output=Path(output);root=output/'eds_eval/decision_evidence/episode_000'
    require(report.get('accepted') is True and report.get('evidence_complete') is True,'base audit not accepted')
    status=json.loads((root/'status.json').read_text());events=base.load_events(root,status)
    compute=[json.loads(x) for x in (output/'eds_eval/episode_compute.jsonl').read_text().splitlines() if x.strip()]
    require(len(compute)==1,'compute record ambiguous')
    gate=audit_events(profile,metric_rows(output),events,compute[0],backend)
    if gate is not None:report[GATE if profile=='N26' else control.GATE]=gate
    report['n23_arithmetic_backend']=backend.report()
    from_output(profile,output,report,compute[0]['guided_chunks'])
    return report
