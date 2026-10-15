"""Normalize prospective fixed-path bindings to the same physical output directory."""
import pathlib,json,hashlib,difflib,datetime,os
O=pathlib.Path(__file__).absolute().parent; C=O.resolve()
def load(n):return json.loads((O/n).read_text())
def rec(p):
 b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
def save(n,v):
 p=O/n;assert not p.exists()
 with p.open('x') as f:json.dump(v,f,sort_keys=True,separators=(',',':'),allow_nan=False)
 r=rec(p);return {k:r[k] for k in ('path','sha256')}
def canon(r):return dict(path=str(pathlib.Path(r['path']).resolve()),sha256=r['sha256'])
def guard():
 for p in load('authority-v1.json')['stop_authority']['paths']:
  try:os.lstat(p)
  except FileNotFoundError:pass
  else:raise AssertionError('STOP present '+p)
 assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat(load('authority-v1.json')['deadline'].replace('Z','+00:00'))
guard()
m=load('outputs-manifest-v1.json')
for r in m['files']:assert rec(pathlib.Path(r['path']))==r
report=load('report-v1.json'); initial_report=save('report.initial-draft-v1.json',report)
policy=load('preparation-policy.prospective-disabled-v1.json')
for k in policy:
 if k.endswith('_path'):policy[k]=str(pathlib.Path(policy[k]).resolve())
policy['disabled_runtime_path']=str(C/'runtime.canonical-prospective-disabled-v1.json')
pref=save('preparation-policy.canonical-prospective-disabled-v1.json',policy)
spec=load('engineering-r1-spec.prospective-disabled-v1.json');spec['runtime_binding'].update(preparation=pref,runtime_path=str(C/'runtime.measured.pending-v1.json'),source_record_path=str(C/'source-record.prospective-disabled-v1.json'))
sref=save('engineering-r1-spec.canonical-prospective-disabled-v1.json',spec)
runtime=load('runtime.prospective-disabled-v1.json');runtime['preparation']['source_record']=canon(runtime['preparation']['source_record'])
rref=canon(save('runtime.canonical-prospective-disabled-v1.json',runtime))
closure=load('runtime-closure.prospective-disabled-v1.json');closure['runtime']=rref
cref=save('runtime-closure.canonical-prospective-disabled-v1.json',closure)
scope=load('scope.prospective-disabled-v1.json');scope['specification']=sref
scref=save('scope.canonical-prospective-disabled-v1.json',scope)
acc=load('accounting.prospective-disabled-v1.json');acc['specification']=sref
acref=save('accounting.canonical-prospective-disabled-v1.json',acc)
audit=load('audit-view.incomplete-prospective-disabled-v1.json');audit.update(runtime=rref,runtime_closure=cref,scope=scref)
aref=save('audit-view.canonical-incomplete-prospective-disabled-v1.json',audit)
plan=load('engineering-plan.incomplete-prospective-disabled-v1.json');plan.update(runtime=rref,runtime_closure=cref,scope=scref,accounting=acref,audit_plan=aref)
plref=save('engineering-plan.canonical-incomplete-prospective-disabled-v1.json',plan)
graph=load('graph.incomplete-prospective-disabled-v1.json');graph.update(specification=sref,policy=pref,source_record=runtime['preparation']['source_record'],runtime=rref,runtime_closure=cref,plan=plref,audit=aref)
gref=save('graph.canonical-incomplete-prospective-disabled-v1.json',graph)
# This is an exact prospective pin amendment, never applied to source.
old=next(l for l in (pathlib.Path(report['source']['worktree'])/'scripts/qd_ed_n36_engineering_r1.py').read_text().splitlines() if l.startswith('SPECIFICATION = '))
p=O/'minimal-follow-on-canonical-source-pin.diff'
with p.open('x') as f:f.write('--- a/scripts/qd_ed_n36_engineering_r1.py\n+++ b/scripts/qd_ed_n36_engineering_r1.py\n@@ -37 +37 @@\n-'+old+'\n+SPECIFICATION = '+repr(sref)+'\n')
original=json.loads(pathlib.Path(load('inputs-manifest-v1.json')['files'][0]['path']).read_text()) if False else None
active=next(r for r in load('inputs-manifest-v1.json')['files'] if r['path'].endswith('engineering-r1-spec.prospective-disabled-v7.json'))
oldspec=json.loads(pathlib.Path(active['path']).read_text())
with (O/'specification.canonical-final.diff').open('x') as f:f.write(''.join(difflib.unified_diff(json.dumps(oldspec,indent=2,sort_keys=True).splitlines(True),json.dumps(spec,indent=2,sort_keys=True).splitlines(True),fromfile=active['path'],tofile=sref['path'])))
# Check exact final projections, canonical paths and disabled flags without opening any model/Poe payload.
assert pathlib.Path(policy['disabled_runtime_path']).resolve()==pathlib.Path(policy['disabled_runtime_path'])
assert rref['path']==policy['disabled_runtime_path']
assert runtime['preparation']['source_record']['path']==spec['runtime_binding']['source_record_path']
for k,v in policy.items():
 if k.endswith('_path'):
  assert pathlib.Path(v).parent==C and str(pathlib.Path(v).resolve())==v
  if k!='disabled_runtime_path':assert not os.path.lexists(v)
assert all(pathlib.Path(v).parent==C for v in (spec['runtime_binding']['runtime_path'],spec['runtime_binding']['source_record_path']))
assert not os.path.lexists(spec['runtime_binding']['runtime_path'])
rt0=load('runtime.prospective-disabled-v1.json');rt0['preparation']['source_record']=runtime['preparation']['source_record'];assert runtime==rt0
sp0=load('engineering-r1-spec.prospective-disabled-v1.json');sp0['runtime_binding'].update(preparation=pref,runtime_path=spec['runtime_binding']['runtime_path'],source_record_path=spec['runtime_binding']['source_record_path']);assert spec==sp0
for d in (plan,audit,graph):assert d['frozen'] is False and d['release_enabled'] is False
check=dict(check='canonical same-directory path normalization',status='PASS',detail='Final graph uses physical paths only where exact readiness path checks require them; lexical and physical output directories identify the same directory. All prior drafts preserved; pending release/evidence paths absent.',lexical_output=str(O),physical_output=str(C))
checks=load('commands-checks-v1.json');checks['checks'].append(check);checks['finalizer_command']="CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 python -B "+str(pathlib.Path(__file__));checks['checked_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
checksref=save('commands-checks.final-v1.json',checks)
report.update(graph=gref,prospective_specification=sref,prospective_policy=pref,initial_draft_report=initial_report,focused_command_evidence=checksref,canonical_path_check=check,minimal_follow_on_diff=str(p),prospective_specification_diff=str(O/'specification.canonical-final.diff'),at=datetime.datetime.now(datetime.timezone.utc).isoformat())
report['checks'].append(check)
report['remaining_exact_gates'][1]='Separately authorized source amendment: apply the exact one-line SPECIFICATION replacement in minimal-follow-on-canonical-source-pin.diff after review of engineering-r1-spec.canonical-prospective-disabled-v1.json. Preserve AMENDMENT and all runtime audit/admission checks. Commit/review/place that source, then regenerate its source record and downstream hashes. No source change was applied.'
report['limitations'].append('Initial lexical-path drafts are superseded by the canonical-prospective graph named in this report. They remain intact for command evidence; use the final canonical source-pin diff, not the initial illustrative diff.')
report['elapsed_seconds']= (datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(load('authority-v1.json')['at'])).total_seconds()
report['manifest']='outputs-manifest-final-v1.json'
guard()
# Finalize this task report only; historical inputs and draft artifacts remain immutable.
(O/'report-v1.json').write_text(json.dumps(report,sort_keys=True,separators=(',',':'),allow_nan=False))
(O/'report-v1.sha256').write_text(rec(O/'report-v1.json')['sha256']+'  report-v1.json\n')
# Names are explicitly enumerated; no wrapper/event/credential/result files inspected.
names={pathlib.Path(r['path']).name for r in m['files']}
names.update(['outputs-manifest-v1.json','prepare-recovery-v2.log','finalize-recovery-v1.py','report.initial-draft-v1.json','preparation-policy.canonical-prospective-disabled-v1.json','engineering-r1-spec.canonical-prospective-disabled-v1.json','runtime.canonical-prospective-disabled-v1.json','runtime-closure.canonical-prospective-disabled-v1.json','scope.canonical-prospective-disabled-v1.json','accounting.canonical-prospective-disabled-v1.json','audit-view.canonical-incomplete-prospective-disabled-v1.json','engineering-plan.canonical-incomplete-prospective-disabled-v1.json','graph.canonical-incomplete-prospective-disabled-v1.json','minimal-follow-on-canonical-source-pin.diff','specification.canonical-final.diff','commands-checks.final-v1.json'])
manifest=save('outputs-manifest-final-v1.json',dict(schema='generated-files-manifest-v1',files=[rec(O/n) for n in sorted(names)],self_excluded=True,prior_manifest_superseded=True,release_enabled=False))
for r in load('outputs-manifest-final-v1.json')['files']:assert rec(pathlib.Path(r['path']))==r
assert (O/'report-v1.sha256').read_text().split()[0]==rec(O/'report-v1.json')['sha256']
print(json.dumps(dict(report=rec(O/'report-v1.json'),manifest=manifest,files=len(names),stop_rechecked=True,status=report['status'])))
