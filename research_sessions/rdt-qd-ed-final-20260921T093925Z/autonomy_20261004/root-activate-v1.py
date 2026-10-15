from pathlib import Path
import datetime,fcntl,hashlib,importlib.util,json,os,subprocess,sys,yaml
A=Path(__file__).resolve().parent;R=A.parent;W=R/'study_worktree';P=R/'variants/n31_capture_dwell_proposal'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text())
def module(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
d=module('autonomy_driver',A/'driver_v1.py')
a=module('arbor_state','/home/hynx/.codex/skills/arbor-agent-tools/scripts/arbor_state.py')
run='rdt-qd-ed-final-20260921T093925Z';session=W/'.arbor/sessions'/run;cpfile=session/'.coordinator/checkpoint.json'
unit='arbor-rdt-qd-ed-20261004.service';now=datetime.datetime.now(datetime.timezone.utc).isoformat()
assert sha(A/'delivery-manifest-v2.json')=='7caebac201bb4882fcb7b1026168da35f2abf4f592e67e592446ac502328e0e1'
manifest=read(A/'delivery-manifest-v2.json')
for f in manifest['files']:
 path=Path(f['path']);assert path.parent==A and path.stat().st_size==f['bytes'] and sha(path)==f['sha256']
assert manifest['driver']==ref(A/'driver_v1.py') and manifest['test_final_guard_clean'] is True
assert manifest['distinct_tests']==17 and manifest['test_total_cpu_seconds']<120
for i in (2,3,4):
 test=read(A/f'cpu-test-resource-v{i}.json');assert test['exit']==0 and test['guard_clean'] is True and test['official_cli_calls']==test['gpu_api_model_sim_calls']==0
assert sha(d.CLI)==d.CLI_SHA
assert read(A/'completion-contract-v1.json')['goal_spec']==ref(W/'docs/01_specs/2026-09-21-rdt-qd-ed-autoresearch-execution-prompt.md')
assert (A/'turns').is_symlink() and str((A/'turns').resolve()).startswith('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/')
assert not (A/'release-v1.json').exists() and not (A/'handoff-v1.json').exists()
lease=d.Lease(A/'coordinator.lease');assert lease.acquire(),'another coordinator owns handoff'
try:
 launch=read(P/'execution/root-launch-v1.json')
 handles={}
 for key in ('controller','monitor'):
  h=launch[key];rec={'pid':h['pid'],'start_ticks':int(h['proc_start_ticks']),'boot_id':h['boot_id']}
  assert d.same_alive(rec);handles[key]=rec
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==launch['source_commit']
 review={'schema':'autonomy-root-operational-review-v1','recorded_at':now,'disposition':'ACCEPT','delivery':ref(A/'delivery-manifest-v2.json'),'driver':ref(A/'driver_v1.py'),'implementation_report':ref(A/'implementation-report-v2.md'),'checks':['all36_delivery_file_bytes_and_hashes','reviewed_complete_driver_and_command','real_authorization_schema_and_immutable_ref','official_CLI_fingerprint','17_distinct_synthetic_cases_with_final_changed_function_coverage','exclusive_driver_and_coordinator_leases','preserve_live_scientific_controller_on_timeout_or_stop','bound_original_goal_outcomes_required','systemd_unit_verification_exit0','linger_enabled','large_turn_logs_on_study_data_volume'],'scientific_source_unchanged':launch['source_commit'],'gpu_controller_live':handles,'scope':'Operational continuation under explicit latest user authorization; no scientific result claimed.'}
 review['checks'][0]=f'all{len(manifest["files"])}_delivery_file_bytes_and_hashes'
 d.atomic(A/'root-review-v1.json',review)
 handoff=read(A/'handoff.disabled.v2.json')
 handoff.update(ready=True,recorded_at=now,root_review=ref(A/'root-review-v1.json'),required_continuation_context=ref(A/'research-continuation-v1.md'),source_at_handoff=launch['source_commit'],current_launch=ref(P/'execution/root-launch-v1.json'),current_plan=launch['plan'],current_release=launch['release'],current_handles_observed=handles,authoritative_mutable_paths={'state':str(W/'research-state.yaml'),'checkpoint':str(cpfile),'attempt_ledger':str(W/'data/attempt-ledger.jsonl'),'health_ledger':str(W/'data/gpu-healthcheck-ledger.jsonl'),'controller_status':str(P/'execution/supervisor-status-v1.json')},root_relinquishes_on_lease_release=True,target_met=False,notes='Read required_continuation_context first; reconcile live handles/ledger before action. New driver owns coordination after this root activation releases coordinator.lease; root thereafter observes only.')
 d.atomic(A/'handoff-v1.json',handoff)
 release=read(A/'release.disabled.v3.json');release.update(released=True,handoff=ref(A/'handoff-v1.json'),root_review=ref(A/'root-review-v1.json'),recorded_at=now)
 d.atomic(A/'release-v1.json',release);d.validate_release(A/'release-v1.json')
 service_dir=Path('/home/hynx/.config/systemd/user');service_dir.mkdir(parents=True,exist_ok=True)
 service_link=service_dir/unit;assert not service_link.exists() and not service_link.is_symlink();service_link.symlink_to(A/unit)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=30)
 subprocess.run(['systemctl','--user','enable',unit],check=True,timeout=30)
 subprocess.run(['systemctl','--user','start',unit],check=True,timeout=30)
 props=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','-p','SubState','-p','MainPID','-p','UnitFileState','-p','Restart','-p','KillMode','-p','SendSIGKILL','-p','TimeoutStopUSec'],text=True,timeout=10)
 assert 'ActiveState=active' in props and 'SubState=running' in props
 receipt={'schema':'autonomy-root-service-activation-v1','recorded_at':now,'release':ref(A/'release-v1.json'),'handoff':ref(A/'handoff-v1.json'),'service':ref(A/unit),'service_name':unit,'service_properties':props,'linger':subprocess.check_output(['loginctl','show-user','hynx','-p','Linger'],text=True,timeout=10).strip(),'driver_start_waits_for_root_lease':True,'root_after_activation':'read-only monitoring; coordinator ownership transferred at function exit','target_met':False}
 d.atomic(A/'root-service-activation-v1.json',receipt)
 with (W/'data/qd-ed-state.lock').open('a+') as state_lock:
  fcntl.flock(state_lock,fcntl.LOCK_EX)
  with a.state_lock(W,run):
   state=yaml.safe_load((W/'research-state.yaml').read_text());cp=read(cpfile);tree=a.load_tree(W,run)
   automation={'status':'SERVICE_ACTIVE_HANDOFF_ON_ROOT_LEASE_RELEASE','service':unit,'release':ref(A/'release-v1.json'),'handoff':ref(A/'handoff-v1.json'),'activation':ref(A/'root-service-activation-v1.json'),'until':'2026-10-11T11:13:13Z','future_budget_amendments_preapproved':True,'further_budget_questions':False,'mutable_status_path':str(A/'driver-status.json')}
   state.update(local_autonomous_coordinator=automation,updated_at=now)
   state['study'].update(automatic_continuation=True,interaction='auto')
   cp.update(local_autonomous_coordinator=automation,updated_at=now)
   tree['meta']['local_autonomous_coordinator']=automation
   temp=W/'research-state.yaml.autonomy-tmp'
   with temp.open('x') as f:yaml.safe_dump(state,f,sort_keys=False,allow_unicode=True);f.flush();os.fsync(f.fileno())
   os.replace(temp,W/'research-state.yaml');d.atomic(cpfile,cp);a.save_tree(W,run,tree)
   note=f'\n### {now} — seven-day autonomous coordinator activated\n\nLatest user authorization preapproves future study budgets without additional questions. User service {unit}, official current-login Codex only, one coordinator lease and one GPU worker. Window through2026-10-11T11:13:13Z. Handoff: {A/"handoff-v1.json"}. N31 controller remains live; no duplicate launch. Target still not met. Root now transfers coordination and observes only.\n'
   for path in (session/'REPORT.md',W/'docs/03_evidence/qd_ed_final/iteration-ledger.md'):
    with path.open('a') as f:f.write(note)
 print(json.dumps({'activated':True,'service':unit,'release':ref(A/'release-v1.json'),'until':handoff['until'],'properties':props}))
finally:lease.close()
