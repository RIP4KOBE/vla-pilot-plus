"""Fixed-pool prospective N22 feasibility; no model/provider/simulator calls."""
from collections import Counter
import hashlib,json,sys
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent;SESSION=HERE.parents[1]
sys.path.insert(0,str(SESSION/'study_worktree'))
from core.rdt_libero_action_converter import rdt_action_to_libero_raw
from core.qd_lift_quality import close_then_lift_bonus

def main():
 torch.set_num_threads(1)
 source=SESSION/'variants/n21_stage_raw_reward_binding/readonly-close-continuity-v1.json'
 original=json.loads(source.read_text());report={'schema':'n22-fixed-pool-hold-ranking-v1','source_audit':str(source),'source_audit_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'scope':'Known exposed Dev saved candidate pools only; after frozen N22 CPU protocol; no coefficient tuning or success prediction.','paths':[]}
 for path in original['paths']:
  count=Counter();changes=[]
  for ref in path['native_bundle_refs']:
   p=Path(ref['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256']
   ev=torch.load(p,map_location='cpu',weights_only=True)['events'];by={e['sequence']:e for e in ev}; ag={e['values']['scoring_batch_id']:e['values']['aggregate_before_reward_mode'] for e in ev if e['event']=='scoring_aggregate'}
   fe=next(e for e in ev if e['event']=='final_selection');f=fe['values'];terminal_id=f['terminal_population']['scoring_batch_id']
   for e in ev:
    if e['event']!='qd_descriptor_assignment':continue
    sid=e['values']['scoring_batch_id'];v=by[sid]['values'];actions=rdt_action_to_libero_raw(v['samples'][:,:8,:]);grip=actions[:,:,6];xyz=v['projected_xyz'];key=v['keypoints'];raw=ag[sid]
    bonus=close_then_lift_bonus(xyz,key,actions,target_index=0).to(raw.dtype)
    distance=torch.linalg.vector_norm(xyz[:,1:].float()-key[0].float(),dim=2)
    eligible=(distance<=.04)&(grip>0);first=eligible.int().argmax(dim=1)
    hold=(~((torch.arange(8).view(1,8)>=first.view(16,1))&(grip<0)).any(dim=1))&eligible.any(dim=1)
    held_bonus=torch.where(hold,bonus,torch.zeros_like(bonus));old=raw if not bool((bonus!=0).any()) else raw+bonus;new=raw if not bool((held_bonus!=0).any()) else raw+held_bonus
    count['canonical_batches']+=1;count['positive_before']+=int((bonus>0).sum());count['positive_after']+=int((held_bonus>0).sum());count['changed_top_candidate']+=int(int(torch.argmax(old))!=int(torch.argmax(new)))
    if sid==terminal_id:
     mask=torch.zeros(16,dtype=torch.bool);indices=f['terminal_population']['grasp_selection']['eligible_indices'];mask[indices]=True
     oldidx=int(torch.argmax(old.masked_fill(~mask,float('-inf')))) if indices else int(torch.argmax(old))
     newidx=int(torch.argmax(new.masked_fill(~mask,float('-inf')))) if indices else int(torch.argmax(new))
     if path['label']=='n20_task0':assert oldidx==int(f['selected_index'])
     count['terminal_selection_changes']+=int(oldidx!=newidx)
     if oldidx!=newidx:
      changes.append({'step':fe['global_step'],'old_index':oldidx,'new_index':newidx,'old_gripper':grip[oldidx].tolist(),'new_gripper':grip[newidx].tolist(),'old_positive_bonus':float(bonus[oldidx]),'new_held_bonus':float(held_bonus[newidx]),'old_raw_reward':float(raw[oldidx]),'new_raw_reward':float(raw[newidx])})
  report['paths'].append({'label':path['label'],'source_native_audit_accepted':path['native_audit_accepted'],'counts':dict(count),'terminal_selection_changes':changes})
 report['limitation']='Fixed states/pools cannot establish modified archive/search trajectories or physical outcomes; N20 audit rejection is preserved. N7 comparisons apply both hypothetical scoring rules on its saved pools, not measured N21/N22 policies.'
 out=HERE/'offline-fixed-pool-rank-v1.json';assert not out.exists();out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 for p in report['paths']:print(p['label'],p['counts'],flush=True)
if __name__=='__main__':main()
