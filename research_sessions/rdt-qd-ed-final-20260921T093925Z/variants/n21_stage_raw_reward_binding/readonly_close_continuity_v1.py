"""Bounded saved-Dev audit, no GPU, simulator, provider or alternative outcome."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent
SESSION=HERE.parents[1]
sys.path.insert(0,str(SESSION/'study_worktree'))
from core.rdt_libero_action_converter import rdt_action_to_libero_raw
from core.qd_lift_quality import close_then_lift_bonus

torch.set_num_threads(1)
PATTERNS={'n20_task0':'*n20_dev_t00_n20_*','n17_n7_task0':'*n17_physics_t00_n7_*','n17_n7_task9':'*n17_physics_t09_n7_*'}

def analyze(label,pattern):
    attempts=list((SESSION/'artifacts/attempts').glob(pattern))
    if len(attempts)!=1: raise ValueError((label,len(attempts)))
    attempt=attempts[0]; ep=attempt/'eds_eval/decision_evidence/episode_000'
    result=json.loads((attempt/'attempt-result.json').read_text())
    audit_path=attempt/'eds_eval/decision-evidence-audit.json'
    audit=json.loads(audit_path.read_text())
    counts=Counter(); selected=[]; refs=[]
    for line in (ep/'events.jsonl').open():
        ref=json.loads(line)
        if not any(e['event']=='qd_descriptor_assignment' for e in ref['events']): continue
        f=ep/ref['bundle']; digest=hashlib.sha256(f.read_bytes()).hexdigest()
        if digest!=ref['sha256']: raise ValueError('bundle digest mismatch')
        refs.append({'path':str(f),'sha256':digest})
        ev=torch.load(f,map_location='cpu',weights_only=True)['events']; by={e['sequence']:e for e in ev}
        final=next(e for e in ev if e['event']=='final_selection');fv=final['values']; final_batch=fv['terminal_population']['scoring_batch_id']
        batches=[e for e in ev if e['event']=='qd_descriptor_assignment']
        assert len(batches)==11
        counts['guided_decisions']+=1
        for e in batches:
            sid=e['values']['scoring_batch_id'];score=by[sid]['values']; xyz=score['projected_xyz']; k=score['keypoints'];actions=rdt_action_to_libero_raw(score['samples'][:,:8,:]);grip=actions[:,:,6]
            bonus=close_then_lift_bonus(xyz,k,actions,target_index=0)
            distance=torch.linalg.vector_norm(xyz[:,1:].float()-k[0].float(),dim=2)
            eligible=(distance<=.04)&(grip>0); first=eligible.int().argmax(dim=1)
            after=torch.arange(8).view(1,8)>=first.view(16,1)
            releases=((grip<0)&after).any(dim=1)
            pos=bonus>0
            counts['canonical_candidates']+=16;counts['positive_bonus_candidates']+=int(pos.sum())
            counts['positive_bonus_with_later_open']+=int((pos&releases).sum())
            counts['positive_bonus_ends_open']+=int((pos&(grip[:,-1]<0)).sum())
            if sid==final_batch:
                idx=int(fv['selected_index']);counts['selected_positive_bonus']+=int(pos[idx]);counts['selected_positive_bonus_with_later_open']+=int(pos[idx]&releases[idx])
                selected.append({'step':final['global_step'],'selected_index':idx,'bonus':float(bonus[idx]),'gripper_commands':grip[idx].tolist(),'first_near_close_action_index':int(first[idx]) if bool(eligible[idx].any()) else None,'later_open_after_first_near_close':bool(releases[idx]) if bool(eligible[idx].any()) else None,'selected_min_projected_target_distance_m':float(distance[idx].min()),'projected_z_at_start':float(xyz[idx,0,2]),'projected_z_at_end':float(xyz[idx,8,2]),'positive_pool_count':int(pos.sum()),'positive_release_pool_count':int((pos&releases).sum())})
    return {'label':label,'attempt_id':attempt.name,'source_outcome_valid':result['outcome_valid'],'source_success':result['success'],'native_audit_accepted':audit['accepted'],'native_evidence_complete':audit['evidence_complete'],'native_audit_sha256':hashlib.sha256(audit_path.read_bytes()).hexdigest(),'counts':dict(counts),'selected':selected,'native_bundle_refs':refs}

if __name__=='__main__':
    out={'schema':'close-continuity-readonly-v1','scope':'existing exposed Dev only; compute already-declared bonus on saved candidates, no changed policy or counterfactual success estimate','paths':[analyze(k,v) for k,v in PATTERNS.items()],'limitation':'N20 episode is audit-rejected due Stage binding; its pools are diagnostic-only. N7 saved-pool bonus is offline and does not predict a changed closed-loop path.'}
    path=HERE/'readonly-close-continuity-v1.json'
    if path.exists(): raise ValueError('do not overwrite prior analysis')
    path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    for p in out['paths']: print(p['label'],p['counts'],flush=True)
