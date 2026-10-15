import copy,datetime as dt,hashlib,importlib.util,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
A=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('driver',A/'driver_v1.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
class DriverTests(unittest.TestCase):
 def setUp(self):
  self.base=Path(tempfile.mkdtemp(dir=A/'synthetic'));self.root=self.base/'autonomy';self.root.mkdir();self.owner=self.base/'study_worktree';self.owner.mkdir()
  self.patch=patch.object(d,'ROOT',self.root);self.patch.start()
  original_sha=d.sha;self.cli_patch=patch.object(d,'sha',side_effect=lambda path:d.CLI_SHA if Path(path)==d.CLI else original_sha(path));self.cli_patch.start()
  self.goal=self.base/'goal.md';self.goal.write_text('original frozen goal')
  self.contract={'schema':'autonomy-original-goal-completion-contract-v1','goal_spec':d.ref(self.goal),'review_schema':'autonomy-original-goal-review-v1','validation_n':20,'validation_min':10,'formal_n':10,'formal_min':5,'checks':['substantive_qd_ed','matched_ablations','cost','validity','reproducibility']}
  d.atomic(self.root/'completion-contract-v1.json',self.contract)
  (self.root/'coordinator-prompt-v1.md').write_text('synthetic prompt')
  self.auth={'schema':'rdt-qd-ed-user-standing-autonomy-authorization-v1','approved':True,'future_study_budget_amendments_preapproved':True,'user_message_verbatim':'批准预算 继续完成任务 后续所有的预算都批准 不要再问我 我要你七天自己不间断且不需要批准的连续执行','continuous_window':{'end_utc':d.UNTIL}}
  d.atomic(self.root/'authorization.json',self.auth)
  self.hand={'schema':'autonomy-seven-day-handoff-v1','ready':True,'until':d.UNTIL,'authorization':d.ref(self.root/'authorization.json'),'owning_worktree':str(self.owner),'completion_contract':d.ref(self.root/'completion-contract-v1.json')}
  d.atomic(self.root/'handoff.json',self.hand)
  self.release={'schema':'autonomy-seven-day-release-v1','released':True,'until':d.UNTIL,'model':d.MODEL,'cli':str(d.CLI),'cli_sha256':d.CLI_SHA,'coordinator_lease':str(self.root/'coordinator.lease'),'driver':d.ref(A/'driver_v1.py'),'prompt':d.ref(self.root/'coordinator-prompt-v1.md'),'handoff':d.ref(self.root/'handoff.json'),'authorization':d.ref(self.root/'authorization.json'),'completion_contract':d.ref(self.root/'completion-contract-v1.json')}
  d.atomic(self.root/'release.json',self.release)
 def tearDown(self):self.cli_patch.stop();self.patch.stop()
 def test_release_exact_bound_source_and_authority(self):
  self.assertEqual(d.validate_release(self.root/'release.json')[1],self.hand)
  for field,value in [('model','other'),('released',False),('until','later')]:
   bad={**self.release,field:value};d.atomic(self.root/'release.json',bad)
   with self.assertRaises(ValueError):d.validate_release(self.root/'release.json')
 def test_cli_hash_and_actual_authority_flags(self):
  bad={**self.release,'cli_sha256':'0'*64};d.atomic(self.root/'release.json',bad)
  with self.assertRaises(ValueError):d.validate_release(self.root/'release.json')
  d.atomic(self.root/'release.json',self.release)
  self.auth['approved']=False;d.atomic(self.root/'authorization.json',self.auth)
  self.release['authorization']=d.ref(self.root/'authorization.json');self.hand['authorization']=self.release['authorization'];d.atomic(self.root/'handoff.json',self.hand);self.release['handoff']=d.ref(self.root/'handoff.json');d.atomic(self.root/'release.json',self.release)
  with self.assertRaises(ValueError):d.validate_release(self.root/'release.json')
 def test_handoff_change_rejected(self):
  d.atomic(self.root/'handoff.json',{**self.hand,'ready':False})
  with self.assertRaises(ValueError):d.validate_release(self.root/'release.json')
 def test_lease_exclusion(self):
  one=d.Lease(self.root/'coordinator.lease');two=d.Lease(self.root/'coordinator.lease')
  self.assertTrue(one.acquire());self.assertFalse(two.acquire());one.close();self.assertTrue(two.acquire());two.close()
 def test_singleton_prevents_second_driver(self):
  lease=d.Lease(self.root/'driver.lock');self.assertTrue(lease.acquire())
  try:self.assertEqual(d.Driver(self.root/'release.json').run(),3)
  finally:lease.close()
 def test_stop_and_deadline_no_subprocess(self):
  driver=d.Driver(self.root/'release.json',now=lambda:d.parse_time(d.UNTIL))
  self.assertEqual(driver.stop_reason(self.contract),'authorization_deadline')
  (self.root/'STOP').touch();self.assertEqual(driver.stop_reason(self.contract),'manual_stop')
  with patch.object(d.subprocess,'Popen',side_effect=AssertionError('must not launch')):self.assertEqual(driver.run(),0)
 def test_managed_auth_env_no_api_fallback(self):
  with patch.dict(os.environ,{'OPENAI_API_KEY':'synthetic','POE_API_KEY':'synthetic','CODEX_HOME':'/synthetic/saved-login','HOME':'/synthetic/home'}):
   e=d.child_environment();self.assertNotIn('OPENAI_API_KEY',e);self.assertNotIn('POE_API_KEY',e);self.assertEqual(e['CODEX_HOME'],'/synthetic/saved-login');self.assertEqual(e['HOME'],'/synthetic/home')
 def test_exact_official_cli_command(self):
  cmd=d.command(self.owner,self.root);self.assertEqual(cmd[0],str(d.CLI));self.assertIn('--ignore-user-config',cmd);self.assertIn('approval_policy="never"',cmd);self.assertIn(d.MODEL,cmd)
  self.assertFalse(any('bypass' in s for s in cmd));self.assertNotIn('--ignore-rules',cmd)
 def test_actual_subprocess_receipt_session_and_no_timeout_signal(self):
  code='import sys,time,json;sys.stdin.read();print(json.dumps({"type":"thread.started","thread_id":"synthetic-session"}),flush=True);time.sleep(.03)'
  lease=d.Lease(self.root/'coordinator.lease');self.assertTrue(lease.acquire())
  driver=d.Driver(self.root/'release.json',make_command=lambda *_:[sys.executable,'-I','-c',code],poll_seconds=.005)
  driver.stopping=True
  try:
   with patch.object(d,'source_commit',return_value='a'*40):rec=driver.run_turn(self.release,self.hand,1,lease_fd=lease.file.fileno())
  finally:lease.close()
  self.assertEqual(rec['exit'],0);self.assertEqual(rec['session_ids'],['synthetic-session']);self.assertFalse(d.same_alive(rec['process']));self.assertEqual(d.load(self.root/'active-turn.json')['closed'],True)
  self.assertTrue((self.root/'turns/000001/prompt.txt').exists());self.assertIsNotNone(rec['process']['start_ticks'])
 def test_quota_network_backoff_bounded(self):
  folder=self.root/'logs';folder.mkdir()
  for text,kind in [('quota exceeded','official_quota_or_rate_limit'),('stream disconnected network','network_or_transport_failure'),('unknown','coordinator_exit_failure')]:
   (folder/'stderr.log').write_text(text);self.assertEqual(d.classify(folder,1),kind)
  self.assertEqual(d.classify(folder,0),'completed_turn');self.assertEqual(d.BACKOFF,(60,120,300,600,1800,3600))
 def test_pid_identity_reuse_not_same(self):
  me=d.identity(os.getpid());self.assertTrue(d.same_alive(me));self.assertFalse(d.same_alive({**me,'start_ticks':me['start_ticks']+1}))
 def test_root_lease_wait_stop_without_launch(self):
  lease=d.Lease(self.root/'coordinator.lease');self.assertTrue(lease.acquire())
  def pause(_):(self.root/'STOP').touch()
  try:
   driver=d.Driver(self.root/'release.json',sleep=pause)
   with patch.object(d.subprocess,'Popen',side_effect=AssertionError('lease must block')):self.assertEqual(driver.run(),0)
  finally:lease.close()
 def test_stale_live_coordinator_waits_without_restart(self):
  d.atomic(self.root/'active-turn.json',{'process':{'pid':123,'boot_id':'synthetic','start_ticks':4},'closed':False})
  def pause(_):(self.root/'STOP').touch()
  driver=d.Driver(self.root/'release.json',sleep=pause)
  with patch.object(d,'same_alive',side_effect=[True,False]),patch.object(d.subprocess,'Popen',side_effect=AssertionError('must never duplicate')):
   self.assertEqual(driver.run(),0)
 def test_soft_timeout_records_without_terminating_stub(self):
  import itertools
  code='import sys,time;sys.stdin.read();time.sleep(.03)'
  lease=d.Lease(self.root/'coordinator.lease');self.assertTrue(lease.acquire())
  driver=d.Driver(self.root/'release.json',make_command=lambda *_:[sys.executable,'-I','-c',code],poll_seconds=.005)
  try:
   with patch.object(d,'source_commit',return_value='a'*40),patch.object(d.time,'monotonic',side_effect=itertools.count(0,4001)):
    rec=driver.run_turn(self.release,self.hand,1,lease_fd=lease.file.fileno())
  finally:lease.close()
  self.assertTrue(rec['soft_timeout_observed']);self.assertEqual(rec['exit'],0)
 def completion_fixture(self):
  runtime=self.root/'runtime.json';d.atomic(runtime,{'schema':'synthetic-runtime'})
  protocol=self.root/'protocol.md';protocol.write_text('synthetic frozen protocol')
  common={'candidate_source':'a'*40,'runtime':d.ref(runtime),'task_protocol':d.ref(protocol)}
  review={'schema':'autonomy-original-goal-review-v1','decision':'ACCEPT_ORIGINAL_GOAL','goal_spec':self.contract['goal_spec'],'candidate_profile':'N99',**common,'checks':{}}
  for phase,n in [('validation',20),('formal',10)]:
   cells=[];original={'accepted_cells':[]}
   for arm in ['C0','Q0','N99']:
    for idx in range(n):
     aid=f'{phase}-{arm}-{idx}';audit=self.root/(aid+'-audit.json');d.atomic(audit,{'accepted':True})
     receipt=self.root/(aid+'-receipt.json');d.atomic(receipt,{'audit':d.ref(audit)})
     final=self.root/(aid+'-result.json');success=idx<n//2
     d.atomic(final,{'event':'valid','outcome_valid':True,'required_cost_telemetry_complete':True,'success':success,'source_commit':'a'*40,'attempt_id':aid,'identity':{'profile':arm,'split':phase,'task_id':idx,'iteration':phase},'n23_worker_receipt':d.ref(receipt)})
     pos=len(original['accepted_cells']);original['accepted_cells'].append({'attempt_id':aid,'success':success})
     cells.append({'arm':arm,'success':success,'outcome_valid':True,'attempt_result':d.ref(final),'worker_receipt':d.ref(receipt),'receipt_audit_path':['audit'],'audit':d.ref(audit),'original_result_cell_path':['accepted_cells',pos]})
   orig=self.root/(phase+'-original.json');d.atomic(orig,original)
   normalized=self.root/(phase+'.json');d.atomic(normalized,{'schema':'autonomy-normalized-phase-evidence-v1','phase':phase,**common,'original_result':d.ref(orig),'all_outcomes_valid':True,'no_tuning_after_freeze':True,'cells':cells,'counts':{a:{'audited':n,'success':n//2} for a in ['C0','Q0','N99']}})
   review[phase]=d.ref(normalized)
  for name in self.contract['checks']:
   f=self.root/(name+'.json');d.atomic(f,{'schema':'autonomy-goal-component-review-v1','component':name,'decision':'PASS',**common,'evidence':[d.ref(protocol)]});review['checks'][name]=d.ref(f)
  f=self.root/'goal-review.json';d.atomic(f,review);d.atomic(self.root/'completion-v1.json',{'schema':'autonomy-original-goal-completion-v1','goal_contract':d.ref(self.root/'completion-contract-v1.json'),'goal_review':d.ref(f)})
  return review
 def test_completion_requires_actual_all_phases_and_refs(self):
  self.assertFalse(d.completion_ok(self.root/'completion-v1.json',self.contract));self.completion_fixture();self.assertTrue(d.completion_ok(self.root/'completion-v1.json',self.contract))
  (self.root/'validation-N99-0-result.json').write_text('{}');self.assertFalse(d.completion_ok(self.root/'completion-v1.json',self.contract))
 def test_model_prose_never_completion(self):
  d.atomic(self.root/'completion-v1.json',{'goal_met':True,'message':'done'});self.assertFalse(d.completion_ok(self.root/'completion-v1.json',self.contract))
 def test_completion_counts_and_freeze_tamper(self):
  self.completion_fixture();phase=d.load(self.root/'formal.json');phase['counts']['N99']['audited']=True;d.atomic(self.root/'formal.json',phase)
  review=d.load(self.root/'goal-review.json');review['formal']=d.ref(self.root/'formal.json');d.atomic(self.root/'goal-review.json',review)
  completion=d.load(self.root/'completion-v1.json');completion['goal_review']=d.ref(self.root/'goal-review.json');d.atomic(self.root/'completion-v1.json',completion)
  self.assertFalse(d.completion_ok(self.root/'completion-v1.json',self.contract))
if __name__=='__main__':unittest.main(verbosity=2)
