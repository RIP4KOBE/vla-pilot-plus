"""Observed physical endpoints joined to exact selected detour occurrences.

Missing terminal/next target identity is Unknown, never simulated or interpolated.
These are descriptive repeated observations, not independent task outcomes.
"""
import math
import torch
from scripts.qd_ed_n36_reference import reconstruct
from scripts.qd_ed_n36_lifecycle import predicate


def geometry(packet,index):
    if packet is None or packet.get('keypoints') is None:return None
    if not 0<=index<len(packet['keypoints']):return None
    _,arrival,reason,path=reconstruct(torch.zeros(64,128),packet['keypoints'][index],
        packet.get('observed_eef'),packet.get('hand_quaternion_xyzw'),packet.get('gripper_qpos'),eligible=True)
    if arrival!=0 and path is None:return None
    q=packet['hand_quaternion_xyzw'].double().tolist()
    norm=math.sqrt(math.fsum(x*x for x in q));x,y,z,w=[v/norm for v in q]
    rotation=((1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)),
        (2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)),
        (2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)))
    jaw=packet['gripper_qpos'].double().tolist()
    center=(0.,((jaw[1]+.0005)+(jaw[0]-.0005))/2,-.0036)
    delta=(packet['keypoints'][index].double()-packet['observed_eef'].double()).tolist()
    error=[delta[k]-math.fsum(rotation[k][j]*center[j] for j in range(3)) for k in range(3)]
    return {'inside':arrival==0,'distance_to_center':math.hypot(*error)}


def summarize(events):
    contexts=[e for e in events if e['event']=='decision_context']
    groups={e['decision_id']:[x for x in events if x['decision_id']==e['decision_id']] for e in contexts}
    responses=[]
    for i,ctx in enumerate(contexts):
        rows=groups[ctx['decision_id']]
        selections=[e['values'] for e in rows if e['event']=='n36_selected_occurrence']
        if not selections or selections[0]['origin']!='nonprogress_tangent':continue
        selected=selections[0];identity=selected['identity']
        complete=[e['values'] for e in rows if e['event']=='n36_execution_complete']
        response={'decision_id':ctx['decision_id'],'occurrence':selected['occurrence'],
            'full8_nonterminal':bool(complete),'response':'Unknown','entry':'Unknown',
            'displacement':None,'predicted_dot_observed':None}
        response['per_step_eef']=[]
        for event in rows:
            if event['event']!='pre_reset_outcome':continue
            raw=event['values']['observation'].get('robot0_eef_pos')
            position=None
            if torch.is_tensor(raw) and raw.numel()==3 and bool(torch.isfinite(raw).all()):
                position=raw.reshape(3).double().tolist()
            response['per_step_eef'].append({'step':event['global_step'],'eef':position})
        if complete and i+1<len(contexts):
            nxt=contexts[i+1];following=groups[nxt['decision_id']]
            boundaries=[e['values'] for e in following if e['event']=='n36_boundary_entry']
            packets=[e['values']['packet'] for e in following if e['event']=='n36_observation_context']
            prior_packets=[e['values']['packet'] for e in rows if e['event']=='n36_observation_context']
            keys=('episode','stage','provider','target_index','tracker_instance','tracker_generation','target_status','task_id','run_id','source_commit')
            if boundaries and packets and prior_packets and nxt['global_step']==identity['step']+8 and all(
                    k in identity and boundaries[0]['identity'].get(k)==identity[k] for k in keys):
                b=geometry(prior_packets[0],identity['target_index']);a=geometry(packets[0],identity['target_index'])
                end=boundaries[0]['eef'];start=selected['eef']
                d,dot,_=predicate(complete[0]['p'],start,end)
                if b is not None and a is not None and d is not None and dot is not None:
                    response.update(response='observed_adjacent',entry=not b['inside'] and a['inside'],
                        before=b,after=a,displacement=d,predicted_dot_observed=dot)
        responses.append(response)
    known=sum(x['response']=='observed_adjacent' for x in responses)
    return {'selected_detours':len(responses),'full8_nonterminal_detours':sum(x['full8_nonterminal'] for x in responses),
        'observed_responses':known,'unknown_responses':len(responses)-known,
        'observed_box_entries':sum(x['entry'] is True for x in responses),'responses':responses,
        'contact_inference':False,'task_success_claim':False}
