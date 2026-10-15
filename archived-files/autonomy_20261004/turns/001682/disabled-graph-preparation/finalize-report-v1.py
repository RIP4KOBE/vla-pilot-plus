import json,hashlib,datetime,subprocess,os
from pathlib import Path
O=Path(__file__).absolute().parent
A=json.loads((O/'authority-v1.json').read_text())
def rec(p):
 p=Path(p);d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def write(n,v):
 with (O/n).open('x') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n')
 return rec(O/n)
g=json.loads((O/'generation-results-v1.json').read_text());extra=json.loads((O/'input-checks-v1.json').read_text())
checks=g['checks']+extra['checks'];failures=[c for c in checks if c['status']!='PASS']
commands=[];source_states={}
for name,root in [('accepted',A['source']['worktree']),('deployment',A['deployment_worktree'])]:
 rows=[]
 for args in [['rev-parse','HEAD','HEAD^{tree}'],['status','--porcelain','--untracked-files=no']]:
  argv=['git','-C',root,*args];p=subprocess.run(argv,text=True,capture_output=True,check=True);commands.append(dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr));rows.append(p.stdout)
 source_states[name]=dict(worktree=root,commit=rows[0].splitlines()[0],tree=rows[0].splitlines()[1],tracked_clean=rows[1]=='')
 assert source_states[name]['commit']==A['source']['commit'] and source_states[name]['tree']==A['source']['tree'] and source_states[name]['tracked_clean']
ledgers={}
for name,r in A['ledger_prefixes'].items():
 after=rec(r['path']);before={k:r[k] for k in ('path','bytes','sha256')};assert after==before
 ledgers[name]=dict(before=before,after=after,whole_file_unchanged=True,retained_prefix_preserved=True)
inputs=[]
for r in g['inputs']:
 after=rec(r['path']);assert after==r;inputs.append(dict(before=r,after=after,unchanged=True))
stops=[str(O.parents[2]/'STOP'),'/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP']
now=datetime.datetime.now(datetime.timezone.utc)
preservation=write('preservation-v1.json',dict(schema='n36-disabled-graph-preservation-v1',at=now.isoformat(),source_states=source_states,ledgers=ledgers,inputs=inputs,stop_paths={p:os.path.lexists(p) for p in stops},commands=commands))
invocations=[dict(argv=['/home/hynx/miniconda3/envs/vla-pilot/bin/python',str(O/name)],environment={'PYTHONDONTWRITEBYTECODE':'1','CUDA_VISIBLE_DEVICES':''},stdout_stderr=str(O/log)) for name,log in [('prepare-graph-v1.py','prepare-graph-v1.log'),('verify-inputs-v1.py','verify-inputs-v1.log')]]
invocations.append(dict(argv=['python',str(O/'finalize-report-v1.py')]))
command_ref=write('commands-v1.json',dict(schema='n36-disabled-graph-command-receipt-v1',source_placement=rec(O/'source-placement-v1.json'),invocations=invocations,builder_internal_commands=g['commands'],final_checks=commands))
paths=[Path(r['path']) for r in g['outputs']]
paths += [O/n for n in ['source-placement-v1.json','prepare-graph-v1.py','prepare-graph-v1.log','verify-inputs-v1.py','verify-inputs-v1.log','input-checks-v1.json','generation-results-v1.json','preservation-v1.json','commands-v1.json','finalize-report-v1.py']]
manifest=write('outputs-manifest-v1.json',dict(schema='n36-disabled-graph-output-manifest-v1',artifacts=[rec(p) for p in sorted(set(paths))],release_enabled=False,report_binding='report-v1.json binds this manifest; report-v1.sha256 binds the report to avoid a self-hash cycle'))
plan=json.loads((O/'engineering-plan.draft-disabled-v1.json').read_text());audit=json.loads(Path(plan['audit_plan']['path']).read_text());runtime=json.loads(Path(plan['runtime']['path']).read_text())
assert len(audit['expected_manifests'])==40 and len(plan['expected_manifests'])==1
report=dict(schema='n36-disabled-graph-preparation-report-v1',node_id='15.6',at=now.isoformat(),role='bounded CPU preparation executor; not coordinator',status='PREPARED_DISABLED_GRAPH_BLOCKED_PENDING_EXTERNAL_REVIEW' if failures else 'PREPARED_DISABLED_GRAPH_REQUIRES_INDEPENDENT_REVIEW',verdict='NOT_ACCEPTED',authority=rec(O/'authority-v1.json'),specification=rec(A['specification']['path']),source=source_states,source_placement=rec(O/'source-placement-v1.json'),outputs_manifest=manifest,commands=command_ref,preservation=preservation,graph=dict(plan=rec(O/'engineering-plan.draft-disabled-v1.json'),audit_plan=rec(plan['audit_plan']['path']),audit_manifests=40,engineering_manifests=1,generation='Accepted production b.manifest and b.engineering_manifest; no reference-only or fabricated substitutes',runtime=rec(plan['runtime']['path']),source_record=rec(runtime['preparation']['source_record']['path']),runtime_file_records_preserved=len(runtime['files']),native_build=rec(plan['native_build']['path']),controller_semantics=rec(plan['controller_semantics']['path'])),focused_validation=dict(checks=checks,passed=sum(c['status']=='PASS' for c in checks),failed=len(failures),measurement_entrypoints_invoked=0,broad_test_suites_run=0),blockers=failures,smallest_next_step='Independent review of these exact source/runtime/native/all41 bindings and the refreshed pending controller semantics evidence; owning root may then separately attest the controller proposal and accept the disabled graph. Re-run the unchanged read-only complete graph validator only after that exact external review binding exists. No measurement is authorized by this report.',remaining_gates=['Independent/root controller semantics and disabled graph acceptance; current controller status remains PENDING_INDEPENDENT_AND_ROOT_REVIEW.','A separate finite source-bound preparation measurement release before genuine local GPU/current-login official gpt-6-astra evidence; preserve and reconcile actual charges and unknown handles.','Independent acceptance of exact measured proof/runtime, final ready graph/B5, source/accounting adoption, separately released fresh health and episode gates, and durable one-use exhaustion.','STOP and deadline veto all new work.'],execution_constraints=dict(source_edits=False,commits=False,exact_fast_forward_only=True,owning_state_tree_checkpoint_ledger_writes=False,gpu_work=False,simulation=False,native_builds=False,provider_probes=False,measurement_invocations=0,agents_spawned=0,credentials_opened=False,poe_files_used=False,protected_validation_formal_reads=False,prohibited_design_reads=False,deadline=A['deadline'],maximum_executor_seconds=A['maximum_executor_seconds'],elapsed_since_authority_seconds=(now-datetime.datetime.fromisoformat(A['at'])).total_seconds(),stop_paths={p:os.path.lexists(p) for p in stops}),score=None,target_met=False,production_ready=False,scientific_success_claim=False,root_adopted=False,release_enabled=False,gpu_authorized=False,provider_measurement_authorized=False)
r=write('report-v1.json',report)
with (O/'report-v1.sha256').open('x') as f:f.write(r['sha256']+'  report-v1.json\n')
print(json.dumps(dict(report=r,status=report['status'],passed=report['focused_validation']['passed'],failed=len(failures),blockers=[c.get('message') for c in failures]),indent=2))
