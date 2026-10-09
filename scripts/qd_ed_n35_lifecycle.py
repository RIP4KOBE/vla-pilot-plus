"""Independent event replay for N35; does not invoke the policy memory helper."""
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


def jaw(packet):
    q=packet.get('gripper_qpos')
    if q is None:return None
    require(torch.is_tensor(q) and q.shape==(2,) and q.is_floating_point(),'jaw native field')
    d=float(q[0])-float(q[1])
    return d if bool(torch.isfinite(q).all()) and math.isfinite(d) else None


def replay(events):
    contexts={e['decision_id']:e for e in events if e['event']=='decision_context'}
    grouped={d:[e for e in events if e['decision_id']==d] for d in contexts}
    def one(d,k):
        found=[e for e in grouped[d] if e['event']==k]
        require(len(found)==1,'N35 mandatory '+k);return found[0]
    pending=None;active=None;latch=False;eligible={};ack_count=0;complete_due=False
    counts={'eligible_boundaries':0,'exclusions':{},'consumptions':0,'expiries':0,'resets':[],
            'created_tokens':0,'direct_close_selections':0,'memory_selections':0,'acknowledgements':0}
    for event in events:
        kind=event['event'];v=event['values'];d=event['decision_id']
        if not kind.startswith('n35_'):continue
        if kind=='n35_memory_reset':
            reason=v['reason']
            require(reason in {'episode_reset','stage_change','unguided_or_mode_off','terminal','guidance_change'},'exception or unknown reset invalidates execution')
            if reason=='terminal':
                returns=[e for e in grouped[d] if e['event']=='step_returned' and e['sequence']<event['sequence']]
                require(pending is not None and returns and (terminal_bool(returns[-1]['values']['terminated'])
                    or terminal_bool(returns[-1]['values']['truncated'])),'terminal reset needs actual terminal return')
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
        elif kind=='n35_boundary_entry':
            require(active is None and d not in eligible,'single boundary entry')
            require(equal(v['prior'],pending),'prior token must come from verified execution')
            identity=v['identity'];packet=one(d,'n35_observation_context')['values']['packet']
            require(v['guided'] is True and contexts[d]['values']['use_guidance'] is True,'guided boundary')
            separation=jaw(packet);require(v['jaw']==separation,'measured boundary jaw')
            reason='no_prior_chunk'
            if pending is not None:
                p=pending
                keys=('episode','stage','provider','target_index','tracker_instance','tracker_generation','target_status')
                if any(k not in identity or k not in p['identity'] or identity[k]!=p['identity'][k] for k in keys):reason='identity_or_tracking_change'
                elif identity['step']!=p['identity']['step']+8:reason='not_immediate_prior_chunk'
                elif p['origin']!='observed_close_dwell':reason='non_direct_close_origin'
                elif p['ambiguous']:reason='ambiguous_equal_content_origins'
                elif p['completed'] is not True or p['committed'] is not True or p['acknowledged']!=8:reason='incomplete_execution'
                elif p['positive'] is not True:reason='nonpositive_executed_commands'
                elif separation is None or p['jaw'] is None:reason='jaw_unavailable'
                elif not separation<p['jaw']:reason='jaw_not_strictly_decreasing'
                else:reason='executed_close_consumed'
            latch=reason=='executed_close_consumed'
            require(type(v['eligible']) is bool and v['eligible']==latch and v['reason']==reason,'independent trigger')
            eligible[d]=latch;pending=None;active=d
            counts['eligible_boundaries']+=latch;counts['consumptions']+=latch
            if not latch:counts['exclusions'][reason]=counts['exclusions'].get(reason,0)+1
        elif kind=='n35_selected_occurrence':
            require(active==d and pending is None,'selection lifecycle')
            caches=[e for e in grouped[d] if e['event']=='canonical_candidate_batch']
            ops=[e for e in grouped[d] if e['event']=='n35_capture_dwell_opportunity']
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
                and v['positive'] is None and v['committed'] is False and v['acknowledged']==0,'new selection state')
            packet=one(d,'n35_observation_context')['values']['packet']
            require(v['jaw']==jaw(packet),'selection jaw')
            # Cross-check occurrence transport through archive deduplication; full
            # independent archive replay in qd_ed_n35_native verifies this snapshot.
            archive=[e for e in grouped[d] if e['event']=='n35_archive_update'][-1]['values']['archive']
            best=min(archive,key=lambda x:(-x['reward'],x['fingerprint'],x['cell_id']))
            require(best['occurrence_id']==occurrence,'selected transported archive occurrence')
            require(same(one(d,'final_selection')['values']['selected_latent'],v['native']),'selected latent')
            pending=dict(v);ack_count=0;complete_due=False
            counts['direct_close_selections']+=origin=='observed_close_dwell' and not v['ambiguous']
            counts['memory_selections']+=origin=='closure_intent_memory'
        elif kind=='n35_boundary_expiry':
            require(active==d and v['eligible']==latch and v['selected']==(pending is not None),'boundary expiry')
            require(pending is not None and v['identity']==pending['identity'],'expiry identity')
            active=None;latch=False;counts['expiries']+=1
        elif kind=='n35_decode_binding':
            require(active is None and pending is not None and pending['decoded'] is None,'single decoder')
            p=pending
            decoded=p['native'].float()[:,:8,[39,40,41,42,43,44,10]].clone()
            decoded[:,:,-1]=torch.where(decoded[:,:,-1]<0,-1.,1.)
            require(v['occurrence']==p['occurrence'] and v['native_identity']==p['native_identity']
                and same(v['decoded'],decoded) and v['decoded_identity']==native_id(decoded),'decoder acknowledgement')
            require(same(one(d,'policy_action_decode')['values']['action_chunk'],decoded),'actual decoder link')
            p['decoded']=decoded;p['decoded_identity']=native_id(decoded)
        elif kind=='n35_execution_commit':
            require(pending is not None and pending['committed'] is False and pending['decoded'] is not None,'commit lifecycle')
            require(v=={'occurrence':pending['occurrence'],'step':pending['identity']['step'],'horizon':8,
                'decoded_identity':native_id(pending['decoded'])},'commit identity')
            commit=one(d,'decision_committed')['values']
            require(commit['execution_horizon']==8 and same(commit['action_chunk'],pending['decoded']),'actual committed decoder')
            pending['committed']=True
        elif kind=='n35_step_acknowledged':
            require(pending is not None and pending['committed'] and ack_count<8,'step lifecycle')
            p=pending
            returned=[e for e in grouped[d] if e['event']=='step_returned'][ack_count]
            executed=[e for e in grouped[d] if e['event']=='executed_action'][ack_count]
            end=terminal_bool(returned['values']['terminated']) or terminal_bool(returned['values']['truncated'])
            require(returned['sequence']<event['sequence'] and v['step']==returned['global_step']==p['identity']['step']+ack_count
                and v['index']==ack_count+1 and v['occurrence']==p['occurrence'] and v['native_identity']==p['native_identity']
                and v['ended']==end and same(v['action'],p['decoded'][0,ack_count])
                and same(executed['values']['action_numpy'],v['action']),'actual step-return acknowledgement')
            ack_count+=1;p['acknowledged']=ack_count;counts['acknowledgements']+=1
            complete_due=ack_count==8 and not end
        elif kind=='n35_execution_complete':
            require(complete_due and pending is not None and v=={'occurrence':pending['occurrence'],
                'origin':pending['origin'],'positive':bool((pending['decoded'][0,:,6]>0).all()),
                'ambiguous':pending['ambiguous'],'native_identity':pending['native_identity'],
                'decoded_identity':pending['decoded_identity']},'complete execution token')
            pending['completed']=True;pending['positive']=bool((pending['decoded'][0,:,6]>0).all())
            counts['created_tokens']+=int(pending['origin']=='observed_close_dwell' and pending['positive'] and not pending['ambiguous'])
            pending['native']=None;pending['decoded']=None
            complete_due=False
        elif kind not in {'n35_observation_context','n35_canonical_cache','n35_capture_dwell_opportunity','n35_archive_update'}:
            require(False,'unknown N35 event')
    require(active is None and not complete_due,'unfinished N35 boundary/execution')
    for d,ctx in contexts.items():
        if ctx['values']['use_guidance']:
            require(d in eligible,'missing mandatory boundary')
            for kind in ('n35_selected_occurrence','n35_boundary_expiry','n35_decode_binding','n35_execution_commit'):
                one(d,kind)
            require(len([e for e in grouped[d] if e['event']=='n35_step_acknowledged'])==
                len([e for e in grouped[d] if e['event']=='step_returned']),'mandatory acknowledgements missing')
        else:
            require(d not in eligible and any(e['event']=='n35_memory_reset' for e in grouped[d]),'unguided reset missing')
    return eligible,counts
