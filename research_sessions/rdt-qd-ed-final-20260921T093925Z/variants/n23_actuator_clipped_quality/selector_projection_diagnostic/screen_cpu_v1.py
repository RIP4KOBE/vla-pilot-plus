"""One bounded exposed N23/task0 pool screen; no model, CUDA, API or simulation."""
from __future__ import annotations
import csv,hashlib,io,json,math,subprocess
from pathlib import Path
import torch

torch.set_num_threads(2)
HERE=Path(__file__).resolve().parent
VARIANT=HERE.parent
SESSION=VARIANT.parents[1]
W=SESSION/'study_worktree'
ATTEMPT='rdt-qd-ed-final-20260921T093925Z__n23v2_dev_t00_n23_20260930__2cfd86692394'
OUT=SESSION/'artifacts/attempts'/ATTEMPT
ED=OUT/'eds_eval';EVIDENCE=ED/'decision_evidence/episode_000'
SOURCE='51104470983cdbafd08feb87f2f39b7553779405'
SCOPE=VARIANT/'selector-projection-diagnostic-scope-v1.md'
SCOPE_SHA='1b5bb691fdf58154edf1922b8c042a0f214100ce2d982e9306ff1c534ac843f2'


def check(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}


def read(path):return json.loads(Path(path).read_text())


def native(value):
    t=value.detach().cpu().contiguous()
    digest=hashlib.sha256(f'{t.dtype}:{tuple(t.shape)}:'.encode()+t.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()
    return {'dtype':str(t.dtype),'shape':list(t.shape),'sha256':digest,'values':t.tolist()}


def approx_geometry(commands,origin,target):
    # Exactly the source operation order on CPU native dtype; this is NOT a GPU audit.
    cpu=torch.stack([origin[i]+torch.cumsum(commands[i].clamp(-1,1)*.01,dim=0) for i in range(16)])
    cpu_dist=torch.linalg.vector_norm(cpu.float()-target.float(),dim=-1)
    # A second FP64 diagnostic is centered on exact dequantized recorded inputs.
    increments=commands.double().clamp(-1,1)*.01
    ideal=origin.double()[:,None,:]+torch.cumsum(increments,dim=1)
    ideal_dist=torch.linalg.vector_norm(ideal-target.double(),dim=-1)
    # Conservative ordinary round-to-nearest bound: native multiplication, at
    # most k-1 native additions for cumsum, then native origin addition. Actual
    # higher-precision accumulation has a smaller error. No CUDA parity claimed.
    u=torch.finfo(commands.dtype).eps/2
    k=torch.arange(1,9,dtype=torch.float64)[None,:,None]
    gamma=(k-1)*u/(1-(k-1)*u)
    sumabs=torch.cumsum(increments.abs(),dim=1)
    before=(u+gamma*(1+u))*sumabs
    coordinate_error=before+u*(origin.double().abs()[:,None,:]+sumabs+before)
    # FP32 subtraction and length reduction are bounded separately; 1e-6m
    # floor dominates their ordinary rounding at these meter-scale coordinates.
    fp32_error=1e-6+16*torch.finfo(torch.float32).eps*torch.maximum(ideal.abs(),target.double().abs()).amax(dim=-1)
    distance_error=torch.linalg.vector_norm(coordinate_error,dim=-1)+fp32_error
    lower=(ideal_dist-distance_error).clamp_min(0);upper=ideal_dist+distance_error
    check(bool(((cpu_dist.double()>=lower)&(cpu_dist.double()<=upper)).all()),'CPU diagnostic outside declared conservative envelope')
    return cpu,cpu_dist,ideal_dist,lower,upper,distance_error


def selection(costs,eligible):
    return int(torch.argmin(costs.masked_fill(~eligible,float('inf')) if bool(eligible.any()) else costs))


def indices(mask):return torch.nonzero(mask).reshape(-1).tolist()


def bounded_eligibility(positive,lower,upper,costs,actual):
    best_lower=lower.min();best_upper=upper.min()
    definitely=(positive&(upper<=.06)&(upper<=best_lower+.03)).any(dim=1)
    impossible=(~positive|(lower>.06)|(lower>best_upper+.03)).all(dim=1)
    check(not bool((definitely&impossible).any()),'eligibility interval contradiction')
    uncertain=~definitely&~impossible
    # Every arbitrary uncertainty assignment is included. Correlations may make
    # this set too large; it cannot justify a false robust selection conclusion.
    order=sorted(range(16),key=lambda i:(float(costs[i]),i))
    certain_best=next((i for i in order if bool(definitely[i])),None)
    possible=[i for i in order if bool(uncertain[i]) and (certain_best is None or order.index(i)<order.index(certain_best))]
    if certain_best is not None:possible.append(certain_best)
    else:possible.append(int(torch.argmin(costs)))
    possible=sorted(set(possible))
    verdict='same' if possible==[actual] else 'different' if actual not in possible else 'Unknown'
    return {'definitely_eligible':indices(definitely),'definitely_ineligible':indices(impossible),
        'unknown_eligibility':indices(uncertain),'possible_selected_indices':possible,
        'fixed_pool_selection_verdict_under_rounding_envelope':verdict},definitely,impossible


def min_positive(distances,positive,index):
    values=distances[index][positive[index]]
    return None if not len(values) else float(values.min())


def run():
    check(not torch.cuda.is_initialized(),'CPU-only diagnostic')
    check(sha(SCOPE)==SCOPE_SHA,'scope changed')
    check(subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==SOURCE,'owning scientific source changed')
    audit=read(ED/'decision-evidence-audit.json');receipt=read(ED/'in-worker-audit-receipt.json')
    check(audit['accepted'] is True and audit['evidence_complete'] is True and receipt['accepted'] is True
        and receipt['profile']=='N23' and receipt['attempt_id']==ATTEMPT and receipt['source']['commit']==SOURCE
        and receipt['audit_report']==ref(ED/'decision-evidence-audit.json'),'accepted native receipt/report association differs')
    gate=audit['n5_grasp_timing_audit'];decisions=gate['decisions']
    check(len(decisions)==gate['checked_decisions']==15 and gate['canonical_batches_verified']==165
        and gate['canonical_candidates_verified']==2640,'bounded decision scope differs')
    index=[json.loads(line) for line in (EVIDENCE/'events.jsonl').read_text().splitlines()]
    receipt_files={v['path']:v['sha256'] for v in receipt['evidence']['files']}
    check(receipt_files[str((EVIDENCE/'events.jsonl').relative_to(OUT))]==sha(EVIDENCE/'events.jsonl'),'metered index differs')
    sequence_bundle={e['sequence']:b for b in index for e in b['events']}
    metadata={e['sequence']:e for b in index for e in b['events']}
    by_kind={}
    for value in metadata.values():by_kind.setdefault((value['decision_id'],value['event']),[]).append(value['sequence'])
    metrics=[json.loads(s) for s in (ED/'eds_metrics.jsonl').read_text().splitlines()]
    check(len(metrics)==15 and len({v['global_step'] for v in metrics})==15,'metrics scope differs')
    metrics={v['global_step']:v for v in metrics}
    used_bundles={};rows=[]
    for d in decisions:
        cache={};did=d['decision_id'];step=d['global_step'];last=d['canonical_sources'][-1]
        def event(sequence):
            b=sequence_bundle[sequence];name=b['bundle']
            if name not in cache:
                path=EVIDENCE/name;data=path.read_bytes()
                check(not path.is_symlink() and hashlib.sha256(data).hexdigest()==b['sha256']
                    and receipt_files[str(path.relative_to(OUT))]==b['sha256'],'selected bundle hash differs')
                payload=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True)
                check(payload['schema']=='qd-ed-decision-evidence-v1','bundle schema differs')
                check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in payload['events']]==b['events'],
                    'bundle/index event association differs')
                cache[name]={e['sequence']:e for e in payload['events']}
                used_bundles[name]={'path':str(path.resolve()),'sha256':b['sha256'],'bytes':len(data)}
            e=cache[name][sequence]
            check(e['decision_id']==did and e['global_step']==step,'cross-decision association')
            return e
        score=event(last['scoring_batch_id']);canonical=event(last['canonical_sequence'])
        fs=by_kind[(did,'final_selection')];check(len(fs)==1,'terminal selection association differs')
        final=event(fs[0]);v=score['values'];fv=final['values'];term=fv['terminal_population'];grasp=term['grasp_selection']
        effective=[event(seq) for seq in by_kind[(did,'effective_quality')] if sequence_bundle[seq]['bundle'] in cache]
        # The terminal effective event follows scoring_inputs in the same indexed
        # chunk; select by scoring ID without loading any extra decision pools.
        effective=[e for e in effective if e['values'].get('scoring_batch_id')==score['sequence']]
        if not effective:
            effective=[event(seq) for seq in by_kind[(did,'effective_quality')] if metadata[seq]['sequence']>score['sequence'] and metadata[seq]['sequence']<canonical['sequence']]
            effective=[e for e in effective if e['values'].get('scoring_batch_id')==score['sequence']]
        check(len(effective)==1,'effective terminal quality association differs');effective=effective[0]
        population=v['samples'];projected=v['projected_xyz'];target=v['keypoints'][grasp['target_index']]
        check(population.shape==(16,64,128) and projected.shape==(16,9,3) and grasp['target_index']==0
            and population.dtype==projected.dtype==target.dtype==torch.bfloat16,'native population/projection shape/dtype differs')
        check(torch.equal(population,canonical['values']['candidates']) and torch.equal(population,fv['population'])
            and term['scoring_batch_id']==score['sequence'] and term['canonical_event_sequence']==canonical['sequence'],
            'scoring/final canonical association differs')
        origins=torch.stack([event(seq)['values']['source_eef_position'].to(population.dtype) for seq in v['projection_origin_sequences']])
        commands=population[:,:8,39:42];positive=grasp['positive_commands'];distances=grasp['projected_distances_m']
        check(torch.equal(positive,population[:,:8,10]>=0) and positive.dtype==torch.bool
            and distances.dtype==torch.float32 and distances.shape==(16,8),'recorded gate commands/distances differ')
        check(torch.equal(origins,projected[:,0]),'native origin binding differs')
        raw_cpu=torch.stack([origins[i]+torch.cumsum(commands[i]*.01,dim=0) for i in range(16)])
        raw_projection_equal=torch.equal(raw_cpu,projected[:,1:])
        raw_dist_cpu=torch.linalg.vector_norm(projected[:,1:].float()-target.float(),dim=-1)
        raw_error=float((raw_dist_cpu-distances).abs().max())
        eligible=(positive&(distances<=.06)&(distances<=distances.min()+.03)).any(dim=1)
        costs=term['native_costs'];actual=int(fv['selected_index'])
        check(indices(eligible)==grasp['eligible_indices']==d['n5_grasp_selection']['eligible_indices']
            and selection(costs,eligible)==actual==d['selected_index']==metrics[step]['selected_idx'],
            'actual native eligibility/selection differs')
        check(native(costs)==d['terminal_native_costs'] and torch.equal(costs,-effective['values']['quality'])
            and torch.equal(effective['values']['quality'],canonical['values']['effective_quality'])
            and effective['values']['quality_mode']=='actuator_clipped_provider_v1',
            'held-fixed cost association differs')
        clipped,cd,ideal,lo,hi,err=approx_geometry(commands,origins,target)
        hypo=(positive&(cd<=.06)&(cd<=cd.min()+.03)).any(dim=1);hypo_idx=selection(costs,hypo)
        interval,defyes,defno=bounded_eligibility(positive,lo,hi,costs,actual)
        robust_differences=indices((eligible&defno)|(~eligible&defyes))
        possible_differences=indices((eligible&~defyes)|(~eligible&~defno))
        mismatch=torch.any(raw_cpu!=clipped,dim=(1,2))
        affected=((commands[:,:7]>1)|(commands[:,:7]<-1)).any(dim=(1,2))
        check(torch.equal(affected,effective['values']['clipped_prefix_mask']),'scored-prefix mask differs')
        margin=lambda distance,best: None if distance is None else {'absolute_m':.06-distance,'relative_m':.03-(distance-best)}
        selraw=min_positive(distances,positive,actual);selclip=min_positive(cd,positive,actual)
        rows.append({'decision_id':did,'global_step':step,'dtype':str(population.dtype),
            'event_sequences':{'scoring':score['sequence'],'effective':effective['sequence'],'canonical':canonical['sequence'],'final':final['sequence'],
                'origins':v['projection_origin_sequences']},
            'projection_semantics':'native stored raw/unclipped t0..t8; clipped geometry reconstructed on CPU only',
            'stored_clipped_geometry':False,'raw_cpu_projection_bitwise_equal':raw_projection_equal,
            'raw_distance_cpu_vs_native_max_abs_m':raw_error,'native_eligible_indices':indices(eligible),
            'cpu_clipped_eligible_indices':indices(hypo),'robust_eligibility_changed_indices':robust_differences,
            'possible_eligibility_changed_indices':possible_differences,
            'eligibility_set_verdict_under_rounding_envelope':'different' if robust_differences else 'same' if not possible_differences else 'Unknown',
            'selected_index':actual,'native_argmin_index':int(torch.argmin(costs)),
            'cpu_clipped_selected_index':hypo_idx,'cpu_point_selection_changed':hypo_idx!=actual,**interval,
            'positive_candidates':indices(positive.any(dim=1)),'positive_command_count':int(positive.sum()),
            'terminal_clipped_t1_t7_candidate_count':int(affected.sum()),
            'terminal_translation_clipped_t1_t8_candidate_count':int(((commands>1)|(commands<-1)).any(dim=(1,2)).sum()),
            'raw_vs_cpu_clipped_geometry_different_candidates':indices(mismatch),
            'selected_positive_min_distance_raw_m':selraw,'selected_positive_min_distance_cpu_clipped_m':selclip,
            'native_best_reach_m':float(distances.min()),'cpu_clipped_best_reach_m':float(cd.min()),
            'selected_raw_threshold_margins':margin(selraw,float(distances.min())),
            'selected_cpu_clipped_threshold_margins':margin(selclip,float(cd.min())),
            'distance_envelope_max_half_width_m':float(err.max()),
            'cpu_clipped_t8_is_hypothetical_not_native_score_input':True,
            'native':{'projected_xyz':native(projected),'gate_distances':native(distances),'positive_commands':native(positive),
                'fixed_costs':native(costs),'target':native(target),'translation_commands_t1_t8':native(commands)},
            'approximate_geometry':{'cpu_clipped_distances_m':cd.tolist(),'fp64_ideal_distances_m':ideal.tolist(),
                'distance_lower_m':lo.tolist(),'distance_upper_m':hi.tolist()},
            'candidate_threshold_margins':[{'index':i,'raw_positive_min_m':min_positive(distances,positive,i),
                'cpu_clipped_positive_min_m':min_positive(cd,positive,i),
                'raw_margin':margin(min_positive(distances,positive,i),float(distances.min())),
                'cpu_clipped_margin':margin(min_positive(cd,positive,i),float(cd.min()))} for i in range(16)]})
        del cache
    check(not torch.cuda.is_initialized(),'unexpected CUDA initialization')
    source_files=['core/qd_grasp_timing.py','core/qd_actuator_clipped_quality.py','core/rdt_policy_steer.py',
        'core/rdt_libero_action_converter.py','scripts/audit_decision_evidence.py','configs/qd_ed_final/candidate_n23.json','configs/qd_ed_final/candidate_n7.json']
    sources={name:ref(W/name) for name in source_files}
    recorded={v['path']:v['sha256'] for v in receipt['source']['files']}
    check(all(recorded[name]==v['sha256'] for name,v in sources.items()),'source bytes differ from metered worker')
    result={'schema':'n23-selector-projection-readonly-screen-v1','attempt_id':ATTEMPT,'scope':ref(SCOPE),
        'source_commit':SOURCE,'source_files':sources,'script':ref(__file__),'cuda_initialized':False,
        'receipt':ref(ED/'in-worker-audit-receipt.json'),'native_audit':ref(ED/'decision-evidence-audit.json'),
        'metrics':ref(ED/'eds_metrics.jsonl'),'index':ref(EVIDENCE/'events.jsonl'),'read_bundles':list(used_bundles.values()),
        'row_count':len(rows),'native_audit_totals':audit['n23_actuator_clipped_quality_audit'],
        'rows':rows,'summary':{
            'raw_cpu_projection_bitwise_equal_decisions':sum(v['raw_cpu_projection_bitwise_equal'] for v in rows),
            'decisions_with_terminal_translation_clipping':sum(v['terminal_translation_clipped_t1_t8_candidate_count']>0 for v in rows),
            'cpu_point_eligibility_changed_decisions':sum(v['native_eligible_indices']!=v['cpu_clipped_eligible_indices'] for v in rows),
            'cpu_point_selection_changed_decisions':sum(v['cpu_point_selection_changed'] for v in rows),
            'robust_eligibility_changed_decisions':sum(v['eligibility_set_verdict_under_rounding_envelope']=='different' for v in rows),
            'robust_selection_changed_decisions':sum(v['fixed_pool_selection_verdict_under_rounding_envelope']=='different' for v in rows),
            'unknown_eligibility_decisions':sum(v['eligibility_set_verdict_under_rounding_envelope']=='Unknown' for v in rows),
            'unknown_selection_decisions':sum(v['fixed_pool_selection_verdict_under_rounding_envelope']=='Unknown' for v in rows)},
        'limitations':[
            'No stored clipped XYZ was found in terminal scoring/effective/final records; production returns quality and prefix mask only.',
            'Raw projected XYZ and gate distances/positive masks are native records; CPU clipped XYZ/distances are approximate diagnostic arithmetic.',
            't1..t7 is the original quality scope. Hypothetical selection uses t1..t8 only because unchanged N5 selector uses eight command steps; no eighth native clipped score/projection is asserted.',
            'Robust labels assume ordinary round-to-nearest native operations bounded conservatively at BF16 precision; they are not GPU bitwise validation.',
            'Input clipping plus 0.01 integration is the existing internal scoring geometry, not an exact OSC physics prediction or contact observation.',
            'Population, native N23 costs, gripper commands, target and original raw Stage binding are held fixed. No archive regeneration or rollout/counterfactual task success is inferred.',
            'Single already-exposed unsuccessful task0 trajectory, not independent or generalization evidence. No other attempt or protected/inflight data read.']}
    target=HERE/'screen-result-v1.json';check(not target.exists(),'immutable output exists');target.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    fields=['global_step','native_eligible_indices','cpu_clipped_eligible_indices','robust_eligibility_changed_indices','selected_index',
        'cpu_clipped_selected_index','fixed_pool_selection_verdict_under_rounding_envelope','unknown_eligibility',
        'selected_positive_min_distance_raw_m','selected_positive_min_distance_cpu_clipped_m','distance_envelope_max_half_width_m']
    with (HERE/'decisions-v1.csv').open('x',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for row in rows:writer.writerow({k:json.dumps(row[k]) if isinstance(row[k],list) else row[k] for k in fields})
    print(json.dumps({'result':ref(target),'summary':result['summary'],'rows':15,'bundles_read':len(used_bundles)}))


if __name__=='__main__':run()
