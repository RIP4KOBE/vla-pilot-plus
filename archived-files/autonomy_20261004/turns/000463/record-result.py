import pathlib,json,hashlib,datetime,os,yaml
from scripts import qd_ed_n32r3_bridge as b,qd_ed_n32r3_contract as c,qd_ed_n23_worker as w,qd_ed_final_runner as r
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000463';v=json.loads((out/'release-validation-after-storage-repair.json').read_text());p=w.read_ref(v['plan']);rt=w.read_ref(p['runtime']);candidates=c.read_ref(p['command_candidates'])['commands'];diffs=[]
for row, candidate in zip(p['episodes'],candidates):
 assert candidate['new_attempt_id']==row['episode_key']
 argv,output=b.old.command({**p,'source':p['scientific_source']},rt,row)
 diffs.append({'episode_key':row['episode_key'],'changes':[{'index':i,'prepared':a,'actual':z} for i,(a,z) in enumerate(zip(candidate['proposed_argv'],argv)) if a!=z],'prepared_output':candidate['proposed_output_dir'],'actual_output':str(output)})
w.atomic_json(out/'command-path-diagnosis.json',{'status':'BLOCKED_FAIL_CLOSED','cells':diffs,'cause':'Prepared commands use lexical home-volume output paths; existing old.command resolves relocated output paths to data volume. Exact candidate contract rejects this mismatch.','source_changes':False,'gpu_dispatched':False})
now=datetime.datetime.now(datetime.timezone.utc).isoformat();next_action='N32R3 detached v1 release failed full validator; DO NOT DISPATCH. Storage migrated with byte-verification and retained backup, but all16 prepared command candidates bind lexical home output while old.command resolves data-volume paths. Review command-path-diagnosis.json in turn463. Prepare separately versioned exact prospective command/map/manifest amendment or scoped executor repair; preserve scientific semantics and hard audits, never weaken exact equality. Retain rejected v1 release and438 charges. Then revalidate and perform fresh admission.'
with r.locked(root/'data/qd-ed-state.lock'):
 sp=root/'research-state.yaml';cp=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json';tp=cp.parent/'idea_tree.json'
 s=yaml.safe_load(sp.read_text());ck=json.loads(cp.read_text());tree=json.loads(tp.read_text());assert s['active_controller'] is None and not s['current_owned_workers']
 assert hashlib.sha256((root/'data/attempt-ledger.jsonl').read_bytes()).hexdigest()=='8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6'
 for path in [sp,cp,tp]:(out/('pre-release-review-'+path.name)).write_bytes(path.read_bytes())
 for obj in [s,ck]:
  obj.update(status='N32R3_RELEASE_VALIDATION_BLOCKED_COMMAND_PATH',next_action=next_action,updated_at=now,n32r3_release_validation=c.ref(out/'release-validation-after-storage-repair.json'),n32r3_command_path_diagnosis=c.ref(out/'command-path-diagnosis.json'))
 tree['nodes']['15.2']['n32r3_release_validation']=c.ref(out/'release-validation-after-storage-repair.json');tree['nodes']['15.2']['result']=next_action
 for path,obj,isy in [(sp,s,True),(cp,ck,False),(tp,tree,False)]:
  temp=path.with_name(path.name+'.turn463.tmp');temp.write_text(yaml.safe_dump(obj,sort_keys=False) if isy else json.dumps(obj,indent=2)+'\n');os.replace(temp,path)
summary=f'''Current source:36aac818c8ea0ec3ce18413e678963818bb5bb5d; scientific source1065f38122379a515b60a9a424f574330405b66f unchanged.
Live handles: driver268073/start97715947; coordinator978880/start132177893; boot2a1fa95f-ab0d-488c-a298-fc488ddd2af7. Historical N31 handles absent; owning active controller null; no GPU cohort dispatched. Prior turn462 exited0. STOP absent; deadline2026-10-10T17:42:00Z, autonomy end2026-10-11T11:13:13Z.
Completed: verified bound authorization/handoff and unchanged5694864-byte ledger prefix8294b4ed47b8f645f2b3ab6511329f548b5788a5f40d0822b54d3c6c8c814da6. Detached plan/review/release v1 created but FAILED full validation and NOT adopted for execution. First failure artifact containment repaired by relocating17 manifest files to own data volume, retaining original directory backup and logical symlink, exact bytes verified. Second failure exact command output path mismatch retained and diagnosed across16 cells. No source, protocol threshold, journal, or protected-result changes. Subagent spawn unavailable (no thread); no child launched. Root review independent of implementation executor.
Next bounded step: {next_action}
Unresolved: exact command/path compatibility, valid production release, fresh GPU admission; validation/formal/required ablation and completion record absent.438 attempts/61.35722319715016GPUh and protected reserves preserved. Driver retains locks and continues; goal unmet.
'''
(out/'operational-summary.md').write_text(summary);print(json.dumps({'diagnosis':c.ref(out/'command-path-diagnosis.json'),'summary':c.ref(out/'operational-summary.md')}))
