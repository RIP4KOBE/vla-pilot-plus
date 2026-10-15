#!/usr/bin/env python3
"""Separate post-release-checker CPU re-audit of immutable online cohorts."""
import ast
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];BASE=ROOT/'.worktrees/exp/steering-integration';OUT=BASE/'checks'
MODES=('eds','vls','eds_qd');PYTHON='/home/hynx/miniconda3/envs/vla-pilot/bin/python'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_bytes())
def semantic(r):
 return {k:r.get(k) for k in ('method','valid','scope','full_audit_performed','checks','errors','completed','planned','successes','success_task_ids','stage_queries','infrastructure_error_episodes','invalid_jsonl','evaluation_directory')}|{
 'tasks':[{k:t.get(k) for k in ('task_id','episode','seed','valid','success','reward_contract_valid','videos')}|{'extended_contract':{k:t.get('extended_contract',{}).get(k) for k in ('valid','summary')}} for t in r.get('tasks',[])],
 'method_audit':{k:r.get('method_audit',{}).get(k) for k in ('valid','chunks','failed_chunks')}}
def main():
 sealpath=OUT/'three-mode-final-seal.json';seal=read(sealpath);sealed={r:sha(BASE/r) for r in seal['files_sha256']}
 if sealed!=seal['files_sha256']:raise ValueError('Original seal already mismatched')
 m=read(BASE/'runs/eds-common-20261013/manifest.json');source=BASE/'runs/eds-common-20261013/source'
 differences=[];same=[]
 for rel,old in m['source_sha256'].items():
  current=ROOT/rel;new=sha(current)
  if new==old:same.append(rel);continue
  row={'path':rel,'online_sha256':old,'release_sha256':new}
  if rel.endswith('.py'):
   row['ast_equal_ignoring_locations']=ast.dump(ast.parse((source/rel).read_text()),include_attributes=False)==ast.dump(ast.parse(current.read_text()),include_attributes=False)
  differences.append(row)
 science=lambda r:r=='main.py' or r.startswith(('core/','envs/','utils/','configs/'))
 science_rows=[r for r in m['source_sha256'] if science(r)]
 science_diffs=[r for r in differences if science(r['path'])]
 checker_paths=['scripts/audit_steering.py','scripts/audit_steering_contract.py','scripts/audit_qd_mechanism.py','scripts/steering_transport_audit.py','scripts/steering_archive.py','scripts/steering_runtime.py','scripts/codex_only_runtime.py','core/stage_fused_carry_hold.py','core/stage_failed_contact_recheck.py']
 checker_before={p:sha(ROOT/p) for p in checker_paths}
 env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',PYTHON_DOTENV_DISABLED='1')
 def one(mode):
  run=BASE/'runs'/f'{mode}-common-20261013';dest=OUT/f'release-reaudit-{mode}.json';log=OUT/f'release-reaudit-{mode}.log'
  if dest.exists() or log.exists():raise ValueError('Refuse overwrite: '+str(dest))
  argv=[PYTHON,str(ROOT/'scripts/audit_steering.py'),str(run),'--no-write']
  began=datetime.now(timezone.utc)
  with dest.open('w') as stdout,log.open('w') as stderr:
   result=subprocess.run(argv,stdout=stdout,stderr=stderr,env=env,stdin=subprocess.DEVNULL,cwd=ROOT,timeout=600)
  audited=read(dest);old=read(run/'audit.json')
  return {'method':mode,'argv':argv,'exit_code':result.returncode,'cpu_wall_seconds':(datetime.now(timezone.utc)-began).total_seconds(),
   'valid':audited.get('valid'),'full_audit_performed':audited.get('full_audit_performed'),'successes':audited.get('successes'),
   'success_task_ids':audited.get('success_task_ids'),'completed':audited.get('completed'),'method_chunks':audited.get('method_audit',{}).get('chunks'),
   'semantic_result_matches_original':semantic(audited)==semantic(old),'failed_checks':[k for k,v in audited.get('checks',{}).items() if v is not True],
   'stdout_path':str(dest),'stdout_sha256':sha(dest),'stderr_path':str(log),'stderr_sha256':sha(log),'stderr_nonempty':log.stat().st_size>0}
 with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(one,MODES))
 checker_after={p:sha(ROOT/p) for p in checker_paths}
 after={r:sha(BASE/r) for r in seal['files_sha256']}
 report={'schema':'steering_release_checker_reaudit_v1','generated_at':datetime.now(timezone.utc).isoformat(),'online_tested_commit':seal['tested_commit'],'original_seal_sha256':sha(sealpath),
 'original_integration_acceptance':seal['integration_acceptance'],'original_scores':seal['scores'],'original_receipts_unchanged':after==sealed==seal['files_sha256'],
 'current_checker_hashes':checker_before,'checker_files_unchanged_during_reaudit':checker_after==checker_before,
 'manifest_source_files':len(m['source_sha256']),'byte_unchanged_paths':same,'release_differences':differences,
 'scientific_source_paths':science_rows,'scientific_source_byte_differences':science_diffs,
 'scientific_python_ast_unchanged':all(r.get('ast_equal_ignoring_locations') is True for r in science_diffs),
 'reaudits':results,'all_pass':all(r['exit_code']==0 and r['valid'] is True and r['full_audit_performed'] is True and r['semantic_result_matches_original'] for r in results) and after==sealed and checker_after==checker_before,
 'scope':'Separate release-auditor compatibility evidence. Original online source commit, receipts, outcomes, and acceptance are not replaced or relabeled.',
 'limitations':['AST equality excludes comments and source locations; a changed byte hash is explicitly retained even for comment-only changes.','CPU --no-write auditing reads captured evidence, not simulator/model execution; no GPU or provider calls are made.']}
 (OUT/'release-reaudit-summary.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
 return 0 if report['all_pass'] else 1
if __name__=='__main__':raise SystemExit(main())
