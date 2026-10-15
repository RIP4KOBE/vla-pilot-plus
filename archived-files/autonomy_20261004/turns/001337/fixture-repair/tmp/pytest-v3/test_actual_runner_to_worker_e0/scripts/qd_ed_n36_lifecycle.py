"""Independent event replay for N36; does not invoke the policy memory helper."""
import math
import torch
from scripts.qd_ed_n31_reference import require, same, native_id, terminal_bool


def equal(a, b):
    if torch.is_tensor(a) or torch.is_tensor(b):
        return torch.is_tensor(a) and torch.is_tensor(b) and same(a,b)
    if isinstance(a,dict):
        return isinstance(b,dict) and set(a)==set(b) and all(equal(a[k],b[k]) for k in a)
    if isinstance(a,(tuple,list)):
        return type(a)==type(b) and len(a)==len(b) and all(equal(x,y) for x,y in zip(a,b))
    return a==b


def eef(packet):
    value=packet.get('observed_eef')
    if value is None:return None
    require(torch.is_tensor(value) and value.shape==(3,) and value.is_floating_point(), 'EEF native field')
    coords=value.double().tolist()
    return coords if all(math.isfinite(v) for v in coords) else None


def translation(actions):
    require(actions.dtype==torch.float32 and actions.shape==(1,8,7), 'fp32 committed prefix')
    rows=actions.double().tolist()[0]
    if not all(math.isfinite(v) for row in rows for v in row):return None
    result=[]
    for axis in range(3):
        total=0.
        for row in range(8):total=total+rows[row][axis]
        result.append(0.01*total)
    return result if all(math.isfinite(v) for v in result) else None


def predicate(p, before, after):
    if p is None or before is None or after is None or not all(math.isfinite(v) for v in p+before+after):
        return None,None,'physical_data_unavailable'
    length=math.hypot(*p)
    if not math.isfinite(length) or length==0.:return None,None,'zero_or_nonfinite_prediction'
    displacement=[after[k]-before[k] for k in range(3)]
    dot=0.
    for k in range(3):
        product=p[k]*displacement[k];dot=dot+product
        if not math.isfinite(product) or not math.isfinite(dot):return displacement,None,'nonfinite_displacement_or_dot'
    if not all(math.isfinite(v) for v in displacement):return displacement,None,'nonfinite_displacement_or_dot'
    return displacement,dot,'nonprogress_consumed' if dot<=0. else 'positive_progress'


def recognized(identity):
    keys=('episode','stage','provider','target_index','tracker_instance','tracker_generation','target_status','task_id','source_commit','run_id')
    return (all(k in identity and identity[k] is not None for k in keys)
        and identity['target_status'] in ('tracked','static_background')
        and isinstance(identity['provider'],dict) and bool(identity['provider'])
        and all(type(identity.get(k)) is int and identity[k]>=0 for k in ('episode','stage','target_index','tracker_instance','tracker_generation','task_id','step'))
        and isinstance(identity.get('decision_id'),str) and bool(identity['decision_id'])
        and isinstance(identity['source_commit'],str) and len(identity['source_commit'])==40
        and all(c in '0123456789abcdef' for c in identity['source_commit'])
        and isinstance(identity['run_id'],str) and bool(identity['run_id']))


def verify_reset_epochs(events):
    """Replay recorder epochs, including the transition inside adapter.step.

    The automatic-reset marker belongs to the old epoch; the returned outcome
    and subsequent memory acknowledgement belong to the incremented epoch.
    Truncation alone does not advance the recorder epoch.
    """
    epoch=0;sequence=0;outcome=None;reset_seen=False
    identity=('episode','decision_id','global_step')
    for event in events:
        kind=event['event'];v=event['values']
        require(type(event['sequence']) is int and event['sequence']>sequence,'N36 event order')
        sequence=event['sequence']
        require(type(event['reset_sequence']) is int and event['reset_sequence']==epoch,'N36 reset epoch mismatch')
        if outcome is not None:
            require(all(event[k]==outcome[k] for k in identity),'N36 outcome/reset identity')
            if terminal_bool(outcome['values']['terminated']) and not reset_seen:
                require(kind=='automatic_reset_boundary','N36 missing ordered automatic reset')
            else:
                require(kind=='step_returned','N36 missing ordered returned outcome')
        if kind=='pre_reset_outcome':
            outcome=event;reset_seen=False
        elif kind=='automatic_reset_boundary':
            require(outcome is not None and terminal_bool(outcome['values']['terminated']) and not reset_seen
                and v=={'terminal_episode':event['episode'],'reset_will_follow':True,'reset_completed':None},
                'N36 automatic reset binding')
            reset_seen=True;epoch+=1
        elif kind=='step_returned':
            require(outcome is not None and terminal_bool(v['terminated'])==terminal_bool(outcome['values']['terminated'])
                and terminal_bool(v['success'])==terminal_bool(outcome['values']['success']),
                'N36 returned outcome binding')
            outcome=None;reset_seen=False
    require(outcome is None,'N36 unfinished returned outcome')


def replay(events):
    verify_reset_epochs(events)
    contexts={e['decision_id']:e for e in events if e['event']=='decision_context'}
    grouped={d:[e for e in events if e['decision_id']==d] for d in contexts}
    def one(d,k):
        found=[e for e in grouped[d] if e['event']==k]
        require(len(found)==1,'N36 mandatory '+k);return found[0]
    pending=None;active=None;latch=False;eligible={};ack_count=0;complete_due=False;terminal_due=None;returned_due=None
    counts={'eligible_boundaries':0,'exclusions':{},'consumptions':0,'expiries':0,'resets':[],
            'created_tokens':0,'direct_open_selections':0,'detour_selections':0,'acknowledgements':0}
    for event in events:
        kind=event['event'];v=event['values'];d=event['decision_id']
        if returned_due is not None:
            require(kind=='n36_step_acknowledged'
                and all(event[k]==returned_due[k] for k in ('episode','decision_id','global_step','reset_sequence')),
                'N36 mandatory ordered return acknowledgement')
            returned_due=None
        if terminal_due is not None:
            require(kind=='n36_memory_reset' and v=={'reason':'terminal'}
                and all(event[k]==terminal_due[k] for k in ('episode','decision_id','global_step','reset_sequence')),
                'N36 mandatory identity-linked terminal reset after acknowledgement')
        if kind=='step_returned' and contexts[d]['values']['use_guidance']:
            returned_due=event
        if not kind.startswith('n36_'):continue
        if kind=='n36_memory_reset':
            reason=v['reason']
            require(reason in {'episode_reset','stage_change','unguided_or_mode_off','terminal','guidance_change'},'exception or unknown reset invalidates execution')
            if reason=='terminal':
                require(pending is not None and terminal_due is not None,
                    'terminal reset needs actual terminal acknowledgement')
                terminal_due=None
            elif reason=='unguided_or_mode_off':
                require(contexts[d]['values']['use_guidance'] is False,'unguided reset in guided boundary')
            elif pending is not None:
                following=[e for e in contexts.values() if e['sequence']>event['sequence']]
                require(following,'reset without next context')
                next_context=min(following,key=lambda e:e['sequence'])
                if reason=='stage_change':require(next_context['values']['stage']!=pending['identity']['stage'],'stage reset evidence')
                elif reason=='episode_reset':require(next_context['episode']!=pending['identity']['episode'],'episode reset evidence')
                else:require(next_context['values']['use_guidance'] is False,'guidance reset evidence')
            pending=None;active=None;latch=False;complete_due=False;counts['resets'].append(v['reason'])
        elif kind=='n36_boundary_entry':
            require(active is None and d not in eligible,'single boundary entry')
            require(equal(v['prior'],pending),'prior token must come from verified execution')
            identity=v['identity'];packet=one(d,'n36_observation_context')['values']['packet']
            require(v['guided'] is True and contexts[d]['values']['use_guidance'] is True,'guided boundary')
            position=eef(packet);require(v['eef']==position,'measured boundary EEF')
            displacement=dot=None
            reason='no_prior_chunk'
            if pending is not None:
                p=pending
                keys=('episode','stage','provider','target_index','tracker_instance','tracker_generation','target_status','task_id','source_commit','run_id')
                if not recognized(identity) or not recognized(p['identity']) or any(identity[k]!=p['identity'][k] for k in keys):reason='identity_or_tracking_change'
                elif identity['step']!=p['identity']['step']+8 or identity['decision_id']==p['identity']['decision_id']:reason='not_immediate_prior_chunk'
                elif p['origin']!='observed_open_approach':reason='non_direct_open_origin'
                elif p['ambiguous']:reason='ambiguous_equal_content_origins'
                elif p['completed'] is not True or p['committed'] is not True or p['acknowledged']!=8:reason='incomplete_execution'
                elif p['open_translation'] is not True:reason='non_open_translation_commands'
                else:displacement,dot,reason=predicate(p['p'],p['eef'],position)
            latch=reason=='nonprogress_consumed'
            require(v['displacement']==displacement and v['dot']==dot,'ordered binary64 arithmetic')
            require(type(v['eligible']) is bool and v['eligible']==latch and v['reason']==reason,'independent trigger')
            eligible[d]=latch;pending=None;active=d
            counts['eligible_boundaries']+=latch;counts['consumptions']+=latch
            if not latch:counts['exclusions'][reason]=counts['exclusions'].get(reason,0)+1
        elif kind=='n36_selected_occurrence':
            require(active==d and pending is None,'selection lifecycle')
            caches=[e for e in grouped[d] if e['event']=='canonical_candidate_batch']
            ops=[e for e in grouped[d] if e['event']=='n36_capture_dwell_opportunity']
            plans=torch.cat([e['values']['candidates'] for e in caches])
            origins=['ordinary']*len(plans)
            for op in ops:
                o=op['values']
                if o['candidate'] is not None:origins[(o['iteration']+1)*16+15]=o['reason']
            occurrence=v['occurrence'];require(type(occurrence) is int and 0<=occurrence<len(plans),'occurrence index')
            aliases=[i for i,p in enumerate(plans) if same(p,plans[occurrence])]
            origin=origins[occurrence]
            require(type(v['occurrence']) is int and v['origin']==origin and v['aliases']==aliases and v['ambiguous'] is False,'direct origin/aliases')
            require(same(v['native'],plans[occurrence][None]) and v['native_identity']==native_id(v['native']),'occurrence native bytes')
            require(v['decoded'] is None and v['decoded_identity'] is None and v['completed'] is False
                and v['open_translation'] is None and v['p'] is None and v['committed'] is False and v['acknowledged']==0,'new selection state')
            packet=one(d,'n36_observation_context')['values']['packet']
            require(v['eef']==eef(packet),'selection EEF')
            # Cross-check occurrence transport through archive deduplication; full
            # independent archive replay in qd_ed_n36_native verifies this snapshot.
            archive=[e for e in grouped[d] if e['event']=='n36_archive_update'][-1]['values']['archive']
            best=min(archive,key=lambda x:(-x['reward'],x['fingerprint'],x['cell_id']))
            require(best['occurrence_id']==occurrence,'selected transported archive occurrence')
            require(same(one(d,'final_selection')['values']['selected_latent'],v['native']),'selected latent')
            pending=dict(v);ack_count=0;complete_due=False
            counts['direct_open_selections']+=origin=='observed_open_approach' and not v['ambiguous']
            counts['detour_selections']+=origin=='nonprogress_tangent'
        elif kind=='n36_boundary_expiry':
            require(active==d and v['eligible']==latch and v['selected']==(pending is not None),'boundary expiry')
            require(pending is not None and v['identity']==pending['identity'],'expiry identity')
            active=None;latch=False;counts['expiries']+=1
        elif kind=='n36_decode_binding':
            require(active is None and pending is not None and pending['decoded'] is None,'single decoder')
            p=pending
            decoded=p['native'].float()[:,:8,[39,40,41,42,43,44,10]].clone()
            decoded[:,:,-1]=torch.where(decoded[:,:,-1]<0,-1.,1.)
            require(v['occurrence']==p['occurrence'] and v['native_identity']==p['native_identity']
                and same(v['decoded'],decoded) and v['decoded_identity']==native_id(decoded),'decoder acknowledgement')
            require(same(one(d,'policy_action_decode')['values']['action_chunk'],decoded),'actual decoder link')
            p['decoded']=decoded;p['decoded_identity']=native_id(decoded)
        elif kind=='n36_execution_commit':
            require(pending is not None and pending['committed'] is False and pending['decoded'] is not None,'commit lifecycle')
            require(v=={'occurrence':pending['occurrence'],'step':pending['identity']['step'],'horizon':8,
                'decoded_identity':native_id(pending['decoded'])},'commit identity')
            commit=one(d,'decision_committed')['values']
            require(commit['execution_horizon']==8 and same(commit['action_chunk'],pending['decoded']),'actual committed decoder')
            pending['committed']=True
        elif kind=='n36_step_acknowledged':
            require(pending is not None and pending['committed'] and ack_count<8,'step lifecycle')
            p=pending
            returned=[e for e in grouped[d] if e['event']=='step_returned'][ack_count]
            executed=[e for e in grouped[d] if e['event']=='executed_action'][ack_count]
            end=terminal_bool(returned['values']['terminated']) or terminal_bool(returned['values']['truncated'])
            require(returned['sequence']<event['sequence'] and v['step']==returned['global_step']==p['identity']['step']+ack_count
                and all(event[k]==returned[k] for k in ('episode','decision_id','global_step','reset_sequence'))
                and v['index']==ack_count+1 and v['occurrence']==p['occurrence'] and v['native_identity']==p['native_identity']
                and v['ended']==end and same(v['action'],p['decoded'][0,ack_count])
                and same(executed['values']['action_numpy'],v['action']),'actual step-return acknowledgement')
            ack_count+=1;p['acknowledged']=ack_count;counts['acknowledgements']+=1
            complete_due=ack_count==8 and not end
            terminal_due=event if end else None
        elif kind=='n36_execution_complete':
            require(complete_due and pending is not None and v=={'occurrence':pending['occurrence'],
                'origin':pending['origin'],'open_translation':bool((pending['decoded'][0,:,6]==-1).all() and (pending['decoded'][0,:,3:6]==0).all()),
                'p':translation(pending['decoded']),
                'ambiguous':pending['ambiguous'],'native_identity':pending['native_identity'],
                'decoded_identity':pending['decoded_identity']},'complete execution token')
            pending['completed']=True;pending['open_translation']=bool((pending['decoded'][0,:,6]==-1).all() and (pending['decoded'][0,:,3:6]==0).all());pending['p']=translation(pending['decoded'])
            counts['created_tokens']+=int(pending['origin']=='observed_open_approach' and pending['open_translation'] and not pending['ambiguous'])
            pending['native']=None;pending['decoded']=None
            complete_due=False
        elif kind not in {'n36_native_runtime','n36_observation_context','n36_canonical_cache','n36_capture_dwell_opportunity','n36_archive_update'}:
            require(False,'unknown N36 event')
    require(active is None and not complete_due and terminal_due is None and returned_due is None,
        'unfinished N36 boundary/execution/terminal reset')
    for d,ctx in contexts.items():
        if ctx['values']['use_guidance']:
            require(d in eligible,'missing mandatory boundary')
            for kind in ('n36_selected_occurrence','n36_boundary_expiry','n36_decode_binding','n36_execution_commit'):
                one(d,kind)
            require(len([e for e in grouped[d] if e['event']=='n36_step_acknowledged'])==
                len([e for e in grouped[d] if e['event']=='step_returned']),'mandatory acknowledgements missing')
        else:
            require(d not in eligible and any(e['event']=='n36_memory_reset' for e in grouped[d]),'unguided reset missing')
    return eligible,counts
