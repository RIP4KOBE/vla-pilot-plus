"""Replay old/new archive consumers of fixed saved Dev pools, without rollout."""
import hashlib,json,sys
from collections import Counter
from pathlib import Path
import torch
HERE=Path(__file__).resolve().parent; SESSION=HERE.parents[1]
sys.path.insert(0,str(SESSION/'study_worktree'))
from core.qd_ed import QDArchive
from core.rdt_libero_action_converter import rdt_action_to_libero_raw
from core.qd_lift_quality import close_then_lift_bonus

def main():
 torch.set_num_threads(1);src=SESSION/'variants/n21_stage_raw_reward_binding/readonly-close-continuity-v1.json';refs=json.loads(src.read_text());report={'schema':'n22-fixed-pool-archive-replay-v1','source':str(src),'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'paths':[]}
 for path in refs['paths']:
  counts=Counter();decisions=[]
  for ref in path['native_bundle_refs']:
   p=Path(ref['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==ref['sha256'];ev=torch.load(p,map_location='cpu',weights_only=True)['events'];by={e['sequence']:e for e in ev}
   ag={e['values']['scoring_batch_id']:e['values']['aggregate_before_reward_mode'] for e in ev if e['event']=='scoring_aggregate'}
   pars={int(e['values']['iter_idx']):e['values'] for e in ev if e['event']=='archive_parent_allocation'}
   final=next(e for e in ev if e['event']=='final_selection');step=final['global_step'];archives=[QDArchive(grid_shape=(4,4),descriptor_mode='target_xy_quadrant_signed_height_v1') for _ in range(2)];changes=[]
   for e in (e for e in ev if e['event']=='qd_descriptor_assignment'):
    d=e['values'];sid=d['scoring_batch_id'];sc=by[sid]['values'];raw=ag[sid];act=rdt_action_to_libero_raw(sc['samples'][:,:8,:]);g=act[:,:,6];xyz=sc['projected_xyz'];key=sc['keypoints'];b=close_then_lift_bonus(xyz,key,act,target_index=0).to(raw.dtype)
    near=(torch.linalg.vector_norm(xyz[:,1:].float()-key[0].float(),dim=2)<=.04)&(g>0);first=near.int().argmax(dim=1);hold=near.any(dim=1)&~((torch.arange(8).view(1,8)>=first.view(16,1))&(g<0)).any(dim=1);h=torch.where(hold,b,torch.zeros_like(b));qualities=[raw if not bool((z!=0).any()) else raw+z for z in (b,h)]
    i=int(d['iter_idx'])
    for archive,q in zip(archives,qualities): archive.update(actions=sc['samples'],rewards=q,costs=-q,descriptors=d['descriptors'],cell_ids=d['cell_ids'],source_iter=i,raw_rewards=raw)
    assert set(archives[0].entries)==set(archives[1].entries)
    counts['batches']+=1;different=[cell for cell in archives[0].entries if archives[0].entries[cell].fingerprint!=archives[1].entries[cell].fingerprint]
    counts['different_archive_cells']+=len(different)
    if i+1 in pars:
     parent=pars[i+1];cells=[int(x) for x in parent['parent_cell_ids'].tolist()];before=[archives[0].entries[cell].fingerprint for cell in cells];after=[archives[1].entries[cell].fingerprint for cell in cells]
     if path['label']=='n20_task0':
      assert before==list(parent['parent_fingerprints']),('native parent mismatch',step,i)
      counts['native_original_parent_rows_verified']+=16
     changed=[j for j,(a,b) in enumerate(zip(before,after)) if a!=b];counts['changed_parent_slots']+=len(changed)
     if changed:changes.append({'after_canonical_iter':i,'next_parent_iter':i+1,'different_cells':different,'changed_parent_slots':changed})
   counts['decisions']+=1
   if changes: counts['decisions_with_parent_change']+=1;decisions.append({'step':step,'first_divergence':changes[0],'fixed_pool_later_changes':changes[1:]})
  report['paths'].append({'label':path['label'],'counts':dict(counts),'changed_decisions':decisions})
 report['limitation']='These archives see fixed saved pools. Only the first parent divergence per decision is a locally causal consumer difference; all later pools would change online. N7 lift and hold scores are hypothetical. Native N20 parent rows are checked, but its original Stage audit remains rejected. No model, simulator or counterfactual success.'
 out=HERE/'offline-archive-replay-v1.json';assert not out.exists();out.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 for p in report['paths']:print(p['label'],p['counts'],flush=True)
if __name__=='__main__':main()
