"""CPU independent continuation replay; no online history/helper or provider call.

Generic native audit establishes search/source/candidate integrity. This module
reconstructs the additional cross-decision operation from actual recorded events.
The supervisor consumes hashes/scalars; only the metered worker loads tensors.
"""
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import types
import torch

MODE='executed_progress_continuation_v1'
GATE='n30_executed_progress_audit'
ARMS=('C0','Q0','N30')


def require(ok,message):
    if not ok:raise ValueError('N30 native: '+message)


def terminal_bool(value):
    """Decode the two native recorder representations without truthiness coercion."""
    if type(value) is bool:
        return value
    require(type(value) is torch.Tensor and value.device.type=='cpu'
        and value.dtype==torch.bool and value.ndim==0, 'terminal boolean type/shape/device differs')
    return value.item()


def identity(x):
    require(torch.is_tensor(x) and x.device.type=='cpu' and x.is_floating_point() and bool(torch.isfinite(x).all()),'finite CPU native tensor required')
    return hashlib.sha256(str((str(x.dtype),tuple(x.shape))).encode()+x.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def same(a,b):
    return torch.is_tensor(a) and torch.is_tensor(b) and identity(a)==identity(b)


def same_optional(a,b):
    return (a is None and b is None) or same(a,b)


def shaped(x,shape):
    identity(x);require(tuple(x.shape)==tuple(shape),'shape differs');return x


def provider_target(context):
    providers=context['values']['providers']
    if len(providers)!=1:return None
    p=providers[0];path=Path(p.get('source_path') or '')
    require(path.is_file() and not path.is_symlink() and path.stat().st_size<=1024*1024,'provider frozen source missing/oversized')
    source=path.read_text();require(hashlib.sha256(source.encode()).hexdigest()==p['source_text_sha256'],'provider source changed')
    # Reuse only the existing complete-template AST parser; never execute source.
    from core.qd_executed_quality import _template_index
    try:tree,name,index=_template_index(source)
    except (ValueError,SyntaxError,TypeError):return None
    # The frozen loader exec_safe executes a string, hence co_filename '<string>'.
    # Compile only; no provider execution. Canonical structure avoids marshal's
    # interning/reference markers, which are not semantic provider identity.
    def signature(code):
        if isinstance(code,types.CodeType):
            names=('co_argcount','co_posonlyargcount','co_kwonlyargcount','co_nlocals','co_stacksize',
                'co_flags','co_code','co_names','co_varnames','co_filename','co_name','co_qualname',
                'co_firstlineno','co_linetable','co_exceptiontable','co_freevars','co_cellvars')
            return tuple((n,getattr(code,n,None)) for n in names)+(('co_consts',tuple(signature(c) for c in code.co_consts)),)
        return (type(code).__name__,code)
    code=compile(tree,'<string>','exec',dont_inherit=True)
    functions=[x for x in code.co_consts if isinstance(x,types.CodeType) and x.co_name==name]
    require(len(functions)==1,'provider compiled structure differs')
    semantic={'source_text_sha256':p['source_text_sha256'],
        'code_structure_sha256':hashlib.sha256(repr(signature(functions[0])).encode()).hexdigest(),
        'binding':'loader_wrapper_original_and_complete_template_ast'}
    return index,semantic


def audit_events(profile,metrics,events,compute):
    require(profile in ARMS,'unknown profile')
    guided=[e for e in events if e['event']=='decision_context' and e['values']['use_guidance'] and e['values']['providers']]
    require(len(guided)==len(metrics)==compute.get('guided_chunks'),'guided coverage differs')
    counts={'schema':'n30-independent-copy-feedback-v1','profile':profile,'guided_decisions':len(guided),
        'parent_rounds_verified':0,'active_insertions_verified':0,'completed_prefixes_verified':0,
        'actual_acknowledgments_verified':0,'observation_contexts_verified':0,'inactive_decisions_verified':0,
        'canonical_batches_verified':11*len(guided),'canonical_candidates_verified':176*len(guided)}
    if profile!='N30':
        require(not any(e['event'].startswith('n30_') for e in events),'control continuation markers present')
        require(all('executed_progress_continuation' not in m for m in metrics),'control continuation scalar present')
        return counts
    contexts=[e for e in events if e['event']=='decision_context'];groups=defaultdict(list)
    for e in events:groups[e['decision_id']].append(e)
    previous=None;prior_outcome=None;metric_index=0
    for context in contexts:
        rows=groups[context['decision_id']];kinds=defaultdict(list)
        for e in rows:kinds[e['event']].append(e)
        def one(kind):
            require(len(kinds[kind])==1,'missing/duplicate '+kind);return kinds[kind][0]
        def values(kind):return one(kind)['values']
        packet_event=one('n30_observation_context');packet=packet_event['values']['packet']
        require(context['sequence']<packet_event['sequence']<one('policy_action_decode')['sequence'],'raw packet order')
        require(packet['episode']==context['episode'] and same_optional(packet['keypoints'],context['values']['keypoints'])
            and packet['tracker']==context['values'].get('keypoint_tracking_snapshot'),'Main/context association')
        start=shaped(packet['start_eef'],(3,))
        if prior_outcome is not None and not terminal_bool(prior_outcome['values']['terminated']) and context['global_step']>0:
            require(prior_outcome['global_step']==context['global_step']-1
                and same(start,prior_outcome['values']['observation']['robot0_eef_pos'].reshape(3)),'raw EEF previous actual outcome association')
        counts['observation_contexts_verified']+=1
        outcomes=kinds['pre_reset_outcome']
        if outcomes:prior_outcome=outcomes[-1]
        is_guided=bool(context['values']['use_guidance'] and context['values']['providers'])
        if not is_guided:
            require(not kinds['n30_initial_proposal'] and not kinds['n30_selected_native_plan'] and not kinds['n30_actual_ack'],'unguided history did not clear')
            previous=None;continue
        m=metrics[metric_index];metric_index+=1
        proposal=one('n30_initial_proposal');v=proposal['values'];state=v['progress_state']
        require({**state,'control':v.get('control')}==m.get('executed_progress_continuation') and v.get('control')=='none' and state.get('mode')==MODE
            and state.get('invalid_evidence_count')==0 and state.get('status')!='invalid_evidence','invalid/missing scalar feedback evidence')
        require(packet_event['sequence']<proposal['sequence'],'proposal packet order')
        canon=kinds['canonical_candidate_batch'];parents=kinds['parent_allocation']
        require(len(canon)==11 and [e['values']['iter_idx'] for e in canon]==list(range(-1,10)) and len(parents)==10,'canonical/parent coverage')
        counts['parent_rounds_verified']+=10
        require(proposal['sequence']<canon[0]['sequence'],'initial proposal canonical order')
        target=provider_target(context);cur=v['current_context']
        if target is None:
            require(cur is None and state['active'] is False and state['reason']=='unrecognized_single_target_provider','unrecognized provider must be inactive')
            require(values('n30_selected_native_plan')['selected'] is None and not kinds['n30_actual_ack'],'unrecognized provider cannot retain winner')
            previous=None;counts['inactive_decisions_verified']+=1;continue
        target_index,provider_identity=target
        require(isinstance(cur,dict),'recognized provider context missing')
        ci=cur['identity'];tr=packet['tracker'];target_status=tr['targets'][str(target_index)]
        require(target_status['valid'] is True and target_status['status'] in {'tracked','static_background'},'invalid target tracking')
        expected={'episode':packet['episode'],'stage':context['values']['stage'],'target_index':target_index,
            'tracker_instance':tr['instance_id'],'tracker_generation':tr['generation'],'target_status':target_status['status']}
        require(all(ci.get(k)==x for k,x in expected.items()) and type(ci.get('reset_generation')) is int
            and set(ci)==set(expected)|{'provider','reset_generation'},'policy identity differs')
        require(ci['provider']==provider_identity,'independent source/code structure differs')
        require(cur['step']==context['global_step'] and same(cur['start'],start.double())
            and same(cur['target'],packet['keypoints'][target_index].double()),'policy original float64 snapshot differs')
        eligible=(previous is not None and previous['context_identity']==ci
            and previous['reset']==context['reset_sequence']
            and previous['step']+8==context['global_step'] and previous['after']<previous['before'])
        require(state['active'] is eligible,'eligibility independently disagrees')
        if eligible:
            native=previous['native'];fresh=shaped(v['fresh_native_population'],(16,64,128));mask=shaped(v['action_mask'],(1,1,128))
            expected_mask=torch.zeros((1,1,128),dtype=fresh.dtype);expected_mask[:,:,[10,39,40,41,42,43,44]]=1
            require(same(mask,expected_mask),'frozen 128D action mask differs')
            require(fresh.dtype==native.dtype and same(v['previous_native_plan'],native)
                and v['previous_native_identity']==identity(native),'previous native source differs')
            composed=fresh.clone();composed[15]=torch.cat((native[0,8:],fresh[15,56:]),dim=0)
            composed=composed*mask.expand_as(composed).to(dtype=composed.dtype)
            require(same(canon[0]['values']['candidates'],composed) and same(v['inserted_row'],composed[15])
                and same(v['fresh_tail'],fresh[15,56:]),'shift/tail/mask/other15/canonical differs')
            require(v['initial_final_trace_semantics']=='composed_canonical_reuses_its_score'
                and state['previous_start_step']==previous['step'] and state['distance_before_m']==previous['before']
                and state['distance_after_m']==previous['after'],'active diagnostic/feedback association')
            counts['active_insertions_verified']+=1
        else:
            require(all(v[k] is None for k in ('previous_native_plan','previous_native_identity','fresh_native_population','fresh_tail','inserted_row'))
                and v['initial_final_trace_semantics']=='unchanged_fresh','inactive copy evidence differs')
            counts['inactive_decisions_verified']+=1
        selected=one('n30_selected_native_plan');sv=selected['values'];native=shaped(sv['native_plan'],(1,64,128));metadata=sv['selected']
        # Tensor-containing dictionaries require explicit byte comparisons.
        require(isinstance(metadata,dict) and metadata['native_identity']==identity(native) and metadata['identity']==ci
            and metadata['start_step']==cur['step'] and metadata['native_dtype']==str(native.dtype)
            and same(metadata['start_eef'],cur['start']) and same(metadata['target_snapshot'],cur['target'])
            and same(native,values('final_selection')['selected_latent']),'selected native provenance differs')
        decoded=values('policy_action_decode');raw=shaped(decoded['selected_latent'],(1,64,128))
        require(same(raw,native.float()),'native forward FP32 representation differs')
        actions=raw[:,:8,[39,40,41,42,43,44,10]].clone();actions[:,:,-1]=torch.where(actions[:,:,-1]<0,-1.,1.)
        require(same(actions,decoded['action_chunk']) and same(actions,values('n30_decode_binding')['actions'])
            and same(actions,values('decision_committed')['action_chunk']) and same(actions,values('n30_commit_binding')['actions']),
            'decode/commit actual converter differs')
        horizon=values('decision_committed')['execution_horizon'];commit=values('n30_commit_binding')
        require(commit['execution_horizon']==horizon and commit['step']==cur['step'] and commit['committed'] is (horizon==8),'commit horizon association')
        require(selected['sequence']<one('final_selection')['sequence']<one('policy_action_decode')['sequence']
            <one('n30_commit_binding')['sequence']<one('decision_committed')['sequence'],'selected/decode/commit order')
        previous=None;acks=kinds['n30_actual_ack'];executed=kinds['executed_action'];returned=kinds['step_returned']
        if horizon!=8:
            require(not acks,'partial horizon acknowledgments must clear');continue
        require(len(acks)==len(executed)==len(outcomes)==len(returned)<=8 and len(acks)>0,'actual feedback coverage differs')
        terminal=False
        for i,(ack,act,out,ret) in enumerate(zip(acks,executed,outcomes,returned)):
            a=ack['values'];q=out['values'];rv=ret['values'];require(not terminal,'feedback after terminal')
            require(ack['global_step']==act['global_step']==out['global_step']==ret['global_step']==cur['step']+i
                and a['global_step']==cur['step']+i and a['execution_index']==i+1
                and act['sequence']<out['sequence']<ack['sequence']<ret['sequence'],'ordered 1-based actual acknowledgments differ')
            require(same(a['action'],actions[0,i]) and same(act['values']['action_numpy'],actions[0,i]),'actual command differs')
            ack_terminal=terminal_bool(a['terminated']);ack_truncated=terminal_bool(a['truncated'])
            returned_terminal=terminal_bool(rv['terminated']);returned_truncated=terminal_bool(rv['truncated'])
            outcome_terminal=terminal_bool(q['terminated'])
            require(ack_terminal==returned_terminal and ack_truncated==returned_truncated
                and outcome_terminal==returned_terminal,'terminal feedback binding')
            terminal=returned_terminal or returned_truncated;counts['actual_acknowledgments_verified']+=1
            if terminal:require(a['completed'] is None,'terminal cannot certify progress');continue
            endpoint=shaped(q['observation']['robot0_eef_pos'].reshape(3),(3,));require(same(a['endpoint'],endpoint),'actual EEF acknowledgment differs')
            require(a['progress_state']['invalid_evidence_count']==0,'invalid actual feedback')
            if i<7:require(a['completed'] is None,'premature progress certification')
            else:
                before=float(torch.linalg.vector_norm(cur['start']-cur['target']));after=float(torch.linalg.vector_norm(endpoint.double()-cur['target']))
                require(a['completed']=={'selected_native_identity':identity(native),'ack_count':8,'distance_before_m':before,
                    'distance_after_m':after,'progress':before-after,'comparison':'strictly_lower_to_previous_snapshot'},'float64 progress differs')
                previous={'context_identity':ci,'generic_providers':context['values']['providers'],'reset':context['reset_sequence'],
                    'step':cur['step'],'native':native,'before':before,'after':after};counts['completed_prefixes_verified']+=1
        require(terminal or len(acks)==8,'incomplete nonterminal prefix')
    return counts


def compute_check(compute,n):
    u=compute.get('unguided_chunks');require(type(u) is int and u>=0 and compute.get('policy_counters_available') is True,'compute unavailable')
    expected={'guided_chunks':n,'model_forward_calls':21*n+5*u,'model_batch_rows':336*n+5*u,
        'rbf_gradient_calls':19*n,'rbf_gradient_batch_rows':304*n,'reward_scoring_batches':16*n,'reward_evaluations':256*n}
    require(all(compute.get(k)==v for k,v in expected.items()),'Q0 total/canonical cost interpretation differs')
    return expected


def counts(profile,metrics,report,guided_count=None):
    require(profile in ARMS and report.get('accepted') is True and report.get('evidence_complete') is True,'generic audit incomplete')
    n=len(metrics);observed=report['observed_counts'];gate=report.get(GATE)
    require(isinstance(gate,dict) and gate.get('schema')=='n30-independent-copy-feedback-v1' and gate.get('profile')==profile
        and gate.get('guided_decisions')==n and observed.get('canonical_candidate_batch',0)==11*n
        and gate.get('canonical_batches_verified')==11*n and gate.get('canonical_candidates_verified')==176*n,'profile-bound audit missing/downgraded')
    if guided_count is not None:require(type(guided_count) is int and guided_count==n,'terminal guided mismatch')
    require(all(m.get('score_call_count')==11 and m.get('search_evaluation_count')==176
        and all(m.get(k)==10 for k in ('resample_count','renoise_count','rollout_count'))
        and m.get('qd_archive_active_for_chunk') is (profile!='C0') and m.get('qd_quality_mode','provider')=='provider'
        and m.get('qd_gripper_rescue_mode','none')=='none' for m in metrics),'frozen search metrics differ')
    if profile=='N30':
        require(gate.get('parent_rounds_verified')==10*n and all(m.get('executed_progress_continuation',{}).get('mode')==MODE
            and m['executed_progress_continuation']['invalid_evidence_count']==0 for m in metrics),'continuation mode/evidence missing')
        require(sum(m['executed_progress_continuation']['active'] for m in metrics)==gate['active_insertions_verified'],'metric activation differs')
    else:require(all('executed_progress_continuation' not in m for m in metrics),'control continuation metric')
    return {k:v for k,v in gate.items() if type(v) is int},{}


def from_output(profile,output,report,guided_count=None):
    output=Path(output);mp=output/'eds_eval/eds_metrics.jsonl';cp=output/'eds_eval/episode_compute.jsonl'
    require(not mp.is_symlink() and (mp.is_file() or not mp.exists()) and cp.is_file() and not cp.is_symlink(),'metrics/compute path')
    metrics=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()] if mp.is_file() else []
    rows=[json.loads(x) for x in cp.read_text().splitlines() if x.strip()];require(len(rows)==1,'episode compute count')
    compute_check(rows[0],len(metrics))
    return counts(profile,metrics,report,rows[0]['guided_chunks'] if guided_count is None else guided_count)


def audit_output(profile,output,report,backend):
    from scripts import audit_decision_evidence as generic
    require(backend.report()['kind']=='cpu','N30 copy/feedback audit must be CPU')
    output=Path(output);mp=output/'eds_eval/eds_metrics.jsonl';cp=output/'eds_eval/episode_compute.jsonl'
    metrics=[json.loads(x) for x in mp.read_text().splitlines() if x.strip()] if mp.is_file() else []
    compute=[json.loads(x) for x in cp.read_text().splitlines() if x.strip()];require(len(compute)==1,'compute missing')
    compute_check(compute[0],len(metrics))
    root=output/'eds_eval/decision_evidence/episode_000';events=generic.load_events(root,json.loads((root/'status.json').read_text()))
    report=dict(report);report[GATE]=audit_events(profile,metrics,events,compute[0]);counts(profile,metrics,report,compute[0]['guided_chunks'])
    return report
