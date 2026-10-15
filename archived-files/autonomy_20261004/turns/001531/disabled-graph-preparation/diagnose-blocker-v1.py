"""Bounded read-only diagnosis of failed G2. Does not resume graph preparation."""
import ast, json, hashlib, os, subprocess, sys, types, time, datetime as dt
from pathlib import Path
OUT=Path(__file__).resolve().parent
prior=json.loads((OUT/'report-v1.json').read_text())
prep=OUT/'prepare-disabled-v1.py'
# Reuse only the artifact tool's definitions/setup, not its main invocation.
tree=ast.parse(prep.read_text()); nodes=[n for n in tree.body if not isinstance(n,ast.Try)]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(prep),'exec'),globals())
INPUTS.update({r['path']:r for r in prior['inputs']}); OUTPUTS.update(prior['outputs']); CHECKS.update(prior['checks']); ERRORS.extend(prior['errors'])
track(Path(__file__)); track(prep)
wn={'Path':Path,'hashlib':hashlib,'json':json,'subprocess':subprocess,'os':os,'require':require}
extract(ROOT/'scripts/qd_ed_n23_worker.py',{'_source_git','_source_entry','canonical_sha'},wn)
wn.update(sha=sha,read_ref=read); w=types.SimpleNamespace(**wn)
sp=ROOT/'scripts/qd_ed_n34_source.py'; track(sp)
sn={'__file__':str(sp),'__name__':'passive_source','w':w}
tree=ast.parse(sp.read_text()); nodes=[n for n in tree.body if not(isinstance(n,ast.ImportFrom) and n.module=='scripts')]
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(sp),'exec'),sn); s=types.SimpleNamespace(**sn)
required=constant(ROOT/'scripts/qd_ed_final_runner.py','REQUIRED_CODE')
required.update(str(p.relative_to(ROOT)) for folder in ('core','utils','vlm_query') for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in {'.py','.txt'})
bn={'ROOT':ROOT,'Path':Path,'runner':types.SimpleNamespace(REQUIRED_CODE=required),'closure':s}
extract(ROOT/'scripts/qd_ed_n36_bridge.py',{'source_paths'},bn)
paths=bn['source_paths'](ROOT); missing=[]; available=[]; skipped=[]; pins={}
for sub in s.PINNED_SUBMODULES:
 pin,db=s.submodule_pin(ROOT,sub,HEAD); pins[sub]={'commit':pin,'object_database':str(db),'source_entrypoint':s.PINNED_SUBMODULES[sub]}
for name in sorted(paths):
 p=ROOT/name; links=[str(ROOT/Path(*Path(name).parts[:i])) for i in range(1,len(Path(name).parts)+1) if (ROOT/Path(*Path(name).parts[:i])).is_symlink()]
 if not p.is_file() or links:
  sub=next((x for x in pins if name.startswith(x+'/')),None)
  missing.append({'path':name,'is_file':p.is_file(),'exists':p.exists(),'symlink_components':links,'resolved_path':str(p.resolve()),'pinned_dependency':sub,'dependency_commit':pins[sub]['commit'] if sub else None})
 elif any(x in ('/'+name.lower()) for x in ('2026-08-10-eds-qd-stage-guidance-transition-design.md','credential','/poe','poe_','/validation/','/formal/')): skipped.append(name)
 else: available.append(name)
require(missing,'original source-path blocker not reproducible')
# Record only existing source bytes verified against committed objects; explicitly not a complete production source record.
partial=s.source_record(ROOT,available,commit=HEAD)
partial_ref=write('source-inventory.partial-v1.json',{'schema':'n36-partial-source-inventory-diagnostic-v1','production_usable':False,'source_and_scientific_paths_identical':True,'source_record_for_available_subset':partial,'required_paths':sorted(paths),'missing_or_linked_paths':missing,'required_count':len(paths),'available_verified_count':len(available),'missing_count':len(missing),'policy_excluded_paths':skipped,'policy_excluded_count':len(skipped),'dependency_pins':pins,'reason':'Unmodified source_record rejects full candidate: source path missing or linked. No full source record or scientific-equivalence artifact emitted.'})
eroot=ROOT/'scripts/qd_ed_n36_engineering.py'; base=constant(eroot,'BASE'); operational=constant(eroot,'OPERATIONAL_FILES')
changed=git('diff','--name-only',base,HEAD,'--').splitlines(); git('merge-base','--is-ancestor',base,HEAD)
require(set(changed)==operational,'changed paths differ from OPERATIONAL_FILES')
CHECKS['policy_excluded_paths']={'status':'EXCLUDED_FROM_PARTIAL_INVENTORY','paths':skipped,'production_inventory_not_accepted':True}
CHECKS['G2_BASE_ancestry']={'status':'PASS','base':base,'candidate':HEAD}
CHECKS['G2_exact_changed_paths_OPERATIONAL_FILES']={'status':'PASS','changed_paths':sorted(changed),'operational_files':sorted(operational),'set_equality':True}
CHECKS['G2_available_source_bytes_match_pinned_git_objects']={'status':'PASS_PARTIAL_ONLY','verified_files':len(available),'required_files':len(paths)}
CHECKS['G2_full_production_source_record']={'status':'BLOCKED','message':'source path missing or linked','missing_count':len(missing),'required_count':len(paths)}
en={}; extract(eroot,{'require_dispatch_implementation'},en)
try: en['require_dispatch_implementation']()
except RuntimeError as exc: CHECKS['unconditional_dispatch_veto']={'status':'PASS','message':str(exc)}
else: raise ValueError('dispatch veto absent')
oldruntime_path=TURNS/'001467/recovery-preparation/runtime.isolated.disabled-v1.json'; oldruntime=load(oldruntime_path)
oldroot=oldruntime['worktree']; affected=[]
for rec in oldruntime['files']:
 if rec['path'].startswith(oldroot+'/'):
  candidate=ROOT/rec['path'][len(oldroot)+1:]
  if not candidate.is_file(): affected.append({'retained_path':rec['path'],'candidate_path':str(candidate),'retained_sha256':rec['sha256']})
counts={sub:sum(x['pinned_dependency']==sub for x in missing) for sub in pins}
blocker={'schema':'n36-disabled-graph-exact-blocker-v1','status':'BLOCKED_G2_MISSING_PINNED_DEPENDENCY_FILES','source':HEAD,'production_helper':'scripts/qd_ed_n34_source.py:348','error':'source path missing or linked','required_source_paths':len(paths),'available_source_paths_verified':len(available),'missing_source_paths':len(missing),'policy_excluded_paths':skipped,'missing_by_dependency':counts,'first_missing_path':missing[0]['path'],'required_entrypoints':{sub:{'path':str(ROOT/sub/info['source_entrypoint']),'is_file':(ROOT/sub/info['source_entrypoint']).is_file()} for sub,info in pins.items()},'dependency_pins':pins,'partial_inventory':partial_ref,'runtime_rebind_missing_paths':affected,'runtime_rebind_missing_count':len(affected),'no_remediation_performed':True,'contract_not_weakened':True,'next_bounded_step':'Separately authorize materializing the exact pinned third_party/rdt and third_party/lerobot files in the fixed candidate SOURCE route, from local Git object databases, preserving candidate HEAD and all existing bytes. This task forbids checkout writes, so no dependency materialization was attempted. Then rerun G2 before G3/G4; do not redirect source to a different checkout or shrink the inventory.'}
blocker_ref=write('blocker-v1.json',blocker)
write('source-delta.diagnostic-v1.json',{'schema':'n36-source-delta-diagnostic-v1','base_commit':base,'source_commit':HEAD,'base_ancestor':True,'changed_paths':sorted(changed),'operational_files':sorted(operational),'exact_set_equality':True,'scientific_source_equivalence_status':'BLOCKED_FULL_INVENTORY_ABSENT','partial_inventory':partial_ref,'blocker':blocker_ref})
require(git('rev-parse','HEAD')==HEAD and not git('diff','--name-only',HEAD,'--'),'candidate changed')
CHECKS['candidate_HEAD_and_tracked_bytes_unchanged']={'status':'PASS','head':HEAD}
CHECKS['prohibited_native_model_imports']={'status':'PASS','loaded':sorted(n for n in sys.modules if n.split('.')[0] in {'torch','numpy','mujoco','robosuite','transformers','libero'})}
require(not CHECKS['prohibited_native_model_imports']['loaded'],'unexpected import')
ERRORS.append({'stage':'G2_partial_diagnostic_initial_attempt','type':'ValueError','message':'Audit hook blocked direct read of scripts/qd_ed_poe_launch.py. Revised partial inventory excludes prohibited Poe-named paths before Git/source verification; no file content was printed. The initial partial helper had already batch-read committed Git blobs, so this report does not claim those objects were uninspected.'})
STAGE='STOPPED_AT_G2_CONTRACT_MISMATCH'; report('BLOCKED_G2_MISSING_PINNED_DEPENDENCY_FILES')
p=OUT/'report-v1.json'; report_value=json.loads(p.read_text())
report_value.update(blocker=blocker_ref,partial_artifacts=list(OUTPUTS.values()),next_bounded_step=blocker['next_bounded_step'],unresolved_gaps=['G2 full source/scientific inventory blocked by 537 missing pinned dependency files; BASE ancestry and exact 10-path operational delta pass.','G3 runtime rebind not attempted after G2 failure; 697 retained source-dependent runtime paths are absent in the candidate checkout.' if len(affected)==697 else 'G3 runtime rebind not attempted after G2 failure; '+str(len(affected))+' candidate paths absent.','G4 closure rebind and generated/lazy/required-after verification not attempted after G2 failure.','G5 optional audit view and 40+1 manifests not attempted.','G6/G7 remain unresolved; no B5, readiness, adoption, enabling or dispatch.'],commands=['PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(prep),'PYTHONDONTWRITEBYTECODE=1 /home/hynx/miniconda3/envs/vla-pilot/bin/python -B '+str(OUT/'diagnose-blocker-v1.py'),'git --no-replace-objects -C '+str(ROOT)+' merge-base --is-ancestor '+base+' '+HEAD,'git --no-replace-objects -C '+str(ROOT)+' diff --name-only '+base+' '+HEAD+' --'],reproduction_note='Preparation exits 1 at the unmodified full source_record check before any full source/runtime/closure artifact is emitted. The diagnostic script is retained with immutable outputs; inspect existing hashes rather than overwriting artifacts.',score=None,result='CPU preparation stopped at a genuine G2 filesystem contract mismatch; no scientific evaluation or promotion.',insight='Commit ancestry and exact operational path equivalence do not establish a runnable source closure: both pinned dependency trees are absent from this immutable candidate checkout.',code_ref=HEAD)
p.write_text(json.dumps(report_value,indent=2,allow_nan=False)+'\n')
print(json.dumps({'status':report_value['status'],'required':len(paths),'available_verified':len(available),'missing':len(missing),'by_dependency':counts,'runtime_missing':len(affected),'report':str(p)},indent=2))
