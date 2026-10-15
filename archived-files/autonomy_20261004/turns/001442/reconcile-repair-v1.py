import pathlib,json,hashlib,datetime,os,sys,subprocess,yaml
root=pathlib.Path.cwd();base=root.parent/'autonomy_20261004';out=base/'turns/001442'; prior=json.loads((base/'turns/001441/operational-summary-v1.json').read_text());repair=base/'turns/001440/lexical-reference-repair'
report=json.loads((repair/'report-v1.json').read_text());source=pathlib.Path(report['worktree']);sys.path.insert(0,str(source))
from scripts import qd_ed_final_runner as r

def ref(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def write(p,d):
 q=p.with_suffix('.tmp');q.write_text(json.dumps(d,indent=2)+'\n');os.replace(q,p)
assert json.loads((repair/'executor-exit-v1.json').read_text())['exit']==0
proc=json.loads((repair/'executor-process-v1.json').read_text())
assert all(not pathlib.Path('/proc',str(proc[k]['pid'])).exists() for k in ['wrapper','executor'])
for key in ['authority','diagnosis']:
 v=report[key];assert ref(pathlib.Path(v['path']))['sha256']==v['sha256']
assert subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()==report['source_after']
assert not subprocess.check_output(['git','-C',str(source),'status','--porcelain','--untracked-files=no'],text=True).strip()
changed=subprocess.check_output(['git','-C',str(source),'diff','--name-only',report['source_before'],report['source_after']],text=True).splitlines();assert set(changed)=={'scripts/qd_ed_n36_runner.py','tests/test_n36_cli_references.py'}
subprocess.run(['git','-C',str(source),'diff','--check',report['source_before'],report['source_after']],check=True)
contract=json.loads((base/'handoff-v2.json').read_text())['completion_contract'];assert ref(pathlib.Path(contract['path']))['sha256']==contract['sha256']
nextstep='Prepare CPU-only prospective bindings for e36f8b945f6b2fde9e81010b3d16987b8c771dd0 using existing accepted binding tooling (turn 001429), without source edits or historical evidence rewrite. Then root controller review, exact manifest/B5 review and source/runtime adoption; source-bound health readiness and first-C0 release require separate valid prospective records. No automatic replay; mandatory first-C0 G3 and development promotion remain pending.'
with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
 with r.locked(root/'data/qd-ed-state.lock'):
  anchors={}
  for n,v in prior['ledger_prefixes'].items():
   actual=ref(pathlib.Path(v['path']));assert actual['sha256']==v['sha256'] and actual['bytes']==v['bytes'];anchors[n]={**actual,'prior_prefix_preserved':True}
  now=datetime.datetime.now(datetime.timezone.utc).isoformat();status='N36R3_LEXICAL_REFERENCE_REPAIR_ACCEPTED_PENDING_BINDINGS'
  rec={'schema':'n36r3-lexical-reference-terminal-root-review-v1','at':now,'status':status,'report':ref(repair/'report-v1.json'),'exit':ref(repair/'executor-exit-v1.json'),'process_record':ref(repair/'executor-process-v1.json'),'handles_terminal':True,'source_before':report['source_before'],'source_after':report['source_after'],'changed_files':changed,'root_review':'Accepted bounded engineering repair: exact CLI string forwarding preserves frozen reference identity; absolute path rejection occurs before launch; downstream hash/release/runtime consumers unchanged. Reviewed all 12 focused tests and retained reported pass evidence; broad reruns unnecessary. Does not constitute production release or scientific acceptance.','ledger_prefixes':anchors,'source_adopted':False,'gpu_release_enabled':False,'new_dispatches':0,'next_action':nextstep,'goal_complete':False};write(out/'terminal-reconciliation-v1.json',rec)
  for p,isyaml in [(root/'research-state.yaml',True),(root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/checkpoint.json',False)]:
   d=yaml.safe_load(p.read_text()) if isyaml else json.loads(p.read_text());d.update(status=status,phase=status,next_action=nextstep,updated_at=now,n36r3_lexical_reference_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'))
   d['n36r3_lexical_reference_repair'].update(status='TERMINAL_SCOPED_CPU_REPAIR_ACCEPTED_PENDING_BINDINGS',source_after=report['source_after'],report=ref(repair/'report-v1.json'),exit=ref(repair/'executor-exit-v1.json'),live_handles=[])
   if isyaml:
    q=p.with_suffix('.tmp');q.write_text(yaml.safe_dump(d,sort_keys=False,allow_unicode=True));os.replace(q,p)
   else:write(p,d)
  p=root/'.arbor/sessions/rdt-qd-ed-final-20260921T093925Z/.coordinator/idea_tree.json';d=json.loads(p.read_text());d['nodes']['15.6'].update(result=status,insight=nextstep,n36r3_lexical_reference_terminal_reconciliation=ref(out/'terminal-reconciliation-v1.json'));write(p,d)
  summary={'schema':'arbor-operational-summary-v1','at':now,'turn':1442,'owning_source':prior['owning_source'],'candidate_source':report['source_after'],'candidate_source_adopted':False,'live_handles':{},'live_executor_handles':[],'driver':json.loads((base/'driver-status.json').read_text()),'current_controller_status':'NO_GPU_CONTROLLER_OR_CPU_EXECUTOR','ledger_prefixes':anchors,'retained_attempts':505,'retained_gpu_hours':75.53335346582918,'completed_work':['Verified bound handoff/authorization/completion contract, prior normal turn and current driver identity.','Reconciled CPU executor exit 0 and absent original handles.','Reviewed minimal production diff and focused regression tests; accepted bounded repair without adopting source or release.','Verified private ledgers unchanged and updated owning state/checkpoint/tree.'],'terminal_reconciliation':ref(out/'terminal-reconciliation-v1.json'),'next_bounded_step':nextstep,'unresolved_evidence':['Exact new-source bindings, manifest/B5 and runtime/health readiness','First-C0 native G3','Development promotion','Original validation/formal/required ablations'],'driver_stop_exists':(base/'STOP').exists(),'deadline':'2026-10-11T11:13:13Z','goal_complete':False};write(out/'operational-summary-v1.json',summary);(out/'operational-summary-v1.sha256').write_text(ref(out/'operational-summary-v1.json')['sha256']+'  operational-summary-v1.json\n')
print(json.dumps({'status':status,'summary':ref(out/'operational-summary-v1.json')}))
