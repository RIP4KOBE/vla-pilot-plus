"""Synthetic final-gate tests only; no robot, provider, model or acceptance claim."""
from copy import deepcopy
from datetime import datetime,timezone
import importlib.util
import json
from pathlib import Path
import sys
import pytest
import yaml

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('external_aggregate',HERE/'aggregate_steering_cohorts.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
REPO=HERE.parents[3]

def write(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value)+'\n')
def write_rows(p,values):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(v)+'\n' for v in values))
def good_reaudit(folder,manifest):
 report=deepcopy(a.read_json(folder/'audit.json'))
 report.update(successes=0,success_task_ids=[])
 for row in report['tasks']:row['success']=False
 record=report['method_audit'];detail=a.read_json(Path(record['path']));record.update(sha256=a.identity(detail),path=None,written=False,hash_encoding='canonical_json')
 return {'valid':True,'exit_code':0,'report':report}

@pytest.fixture
def bundle(tmp_path):
 runs=tmp_path/'runs'
 base_run=HERE.parent/'runs/eds-common-20261013'
 for mode in a.MODES:
  live=HERE.parent/'runs'/(mode+'-common-20261013')
  folder=runs/(mode+'-test');folder.mkdir(parents=True)
  config=yaml.safe_load((live/'resolved-config.yaml').read_text())
  config['hydra']['run']['dir']=str(folder/'output');config['main']['eds_eval']['job_id']=folder.name
  (folder/'resolved-config.yaml').write_text(yaml.safe_dump(config))
  source={}
  for name in ['configs/evaluation/libero_object_swap.yaml']+['configs/steering/'+m+'.yaml' for m in a.MODES]:
   dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((base_run/'source'/name).read_bytes());source[name]=a.sha(dest.read_bytes())
  env={'model_assets':{'valid':True,'expected_manifest_sha256':'a'*64,'verifier_sha256':'b'*64,'files_checked':1,'bytes_hashed':1,'files':[{'root':'test','path':'test','bytes':1,'sha256':'c'*64}],'normalization_files':[],'normalization_checked':True},
       'rng':{'valid':True,'sha256':'d'*64,'fixture_count':20},'libero':{'valid':True,'manifest_sha256':'e'*64,'upstream_commit':'f'*40,'files_verified':1},'libero_paths':{'valid':True},'imported_packages':{},'submodules':{},'codex_cli':'synthetic-test'}
  write(folder/'environment.json',env)
  local={'gpu':{'eds':0,'vls':1,'eds_qd':4}[mode],'egl_device_id':2,'allocator_limit_gib':48}
  (folder/'local-config.yaml').write_text(yaml.safe_dump(local))
  manifest={'schema':'steering_cohort_v2','method':mode,'commit':'33954ead452927fc3168efb610487a688f89169e','code_root':str(REPO),
      'tasks':a.TASKS,'seeds':a.SEEDS,'provider':'codex_cli','model':'gpt-6-astra','reasoning_effort':'low','fresh_reward':True,'online_stage':True,'evaluation_directory':'output/evaluation','source_sha256':source,
      'physical_gpu':local['gpu'],'egl_device_id':local['egl_device_id'],'gpu':'synthetic-device',
      'config_sha256':a.sha((folder/'resolved-config.yaml').read_bytes()),'environment_sha256':a.sha((folder/'environment.json').read_bytes()),'local_config_sha256':a.sha((folder/'local-config.yaml').read_bytes())}
  write(folder/'manifest.json',manifest)
  write(folder/'status.json',{'state':'finished','exit_code':0,'source_unchanged':True,'started_at':'2026-10-13T00:00:00+00:00','completed_at':'2026-10-13T00:01:00+00:00'})
  audit={'schema':'steering_cohort_audit_v2','scope':'full_v2_contract_and_recorded_method_evidence','method':mode,'valid':True,'full_audit_performed':True,'checks':{'synthetic':True},'planned':10,'completed':10,'successes':0,'success_task_ids':[],'tasks':[]}
  for episode,(task,seed) in enumerate(zip(a.TASKS,a.SEEDS)):
   cp=folder/f'audit-details/task{task}-contract.json';write(cp,{'task_id':task,'task_contract_valid':True,'task_evidence_complete':True})
   audit['tasks'].append({'task_id':task,'seed':seed,'valid':True,'success':False,'extended_contract':{'path':str(cp),'sha256':a.sha(cp.read_bytes()),'valid':True,'written':True,'hash_encoding':'file_bytes'}})
   video=folder/f'output/episode_{episode+1}/episode_fail_agentview.mp4';video.parent.mkdir(parents=True,exist_ok=True);video.write_bytes(b'synthetic-video')
  detail=folder/'audit-details/method-chunks.json';write(detail,{'method':mode,'chunks':[{'stage_binding_valid':True,'recorded_mechanism_valid':True} for _ in a.TASKS]})
  audit['method_audit']={'path':str(detail),'sha256':a.sha(detail.read_bytes()),'valid':True,'written':True,'hash_encoding':'file_bytes','chunks':10,'failed_chunks':0}
  write(folder/'audit.json',audit)
  write_rows(folder/'output/evaluation/episode_compute.jsonl',[{'episode_id':i,'task_id':i,'episode_seed':seed,'outcome':'completed','model_forward_calls':1,'provider_reasoning_output_tokens':None} for i,seed in enumerate(a.SEEDS)])
 return runs

def change(p,fn):
 x=json.loads(p.read_text());fn(x);write(p,x)


def test_three_completed_valid_zero_success_cohorts_can_be_accepted(bundle):
 r=a.aggregate(bundle,'test',revalidator=good_reaudit)
 assert r['all_cohorts_valid'],r
 assert r['integration_acceptance'] is False and r['final_accepted'] is False
 assert r['comparison']['final_success_counts']==dict.fromkeys(a.MODES,0)
 assert all(v['state']=='accepted' for v in r['runs'].values())

@pytest.mark.parametrize('case',['running','failed_exit','audit_absent','invalid_audit','legacy_scope','missing_task','wrong_seed','detail_hash','method_failed','common_commit','common_source','shared_asset','shared_rng','shared_protocol','source_changed','unknown_check','reaudit_rejected','reaudit_raised','stale_success_count','stale_task_success','stale_success_ids','fresh_method_mismatch'])
def test_final_gate_refuses_incomplete_or_inconsistent_bundle(bundle,case):
 p=bundle/'eds-test';revalidator=good_reaudit
 if case=='running':change(p/'status.json',lambda x:x.update(state='running'))
 elif case=='failed_exit':change(p/'status.json',lambda x:x.update(exit_code=1))
 elif case=='audit_absent':(p/'audit.json').unlink()
 elif case=='invalid_audit':change(p/'audit.json',lambda x:x.update(valid=False))
 elif case=='legacy_scope':change(p/'audit.json',lambda x:x.update(scope='legacy_basic_only'))
 elif case=='missing_task':change(p/'audit.json',lambda x:x['tasks'].pop())
 elif case=='wrong_seed':change(p/'manifest.json',lambda x:x['seeds'].__setitem__(0,999))
 elif case=='detail_hash':change(p/'audit-details/task0-contract.json',lambda x:x.update(task_id=1))
 elif case=='method_failed':change(p/'audit.json',lambda x:x['method_audit'].update(failed_chunks=1))
 elif case=='common_commit':change(p/'manifest.json',lambda x:x.update(commit='different'))
 elif case=='common_source':
  f=p/'source/extra.py';f.write_text('# extra\n');change(p/'manifest.json',lambda x:x['source_sha256'].update({'extra.py':a.sha(f.read_bytes())}))
 elif case in ('shared_asset','shared_rng'):
  change(p/'environment.json',lambda x:(x['model_assets'].update(expected_manifest_sha256='9'*64) if case=='shared_asset' else x['rng'].update(sha256='9'*64)))
  change(p/'manifest.json',lambda x:x.update(environment_sha256=a.sha((p/'environment.json').read_bytes())))
 elif case=='shared_protocol':
  f=p/'resolved-config.yaml';x=yaml.safe_load(f.read_text());x['main']['eds_config']['temperature']=.2;f.write_text(yaml.safe_dump(x));change(p/'manifest.json',lambda x:x.update(config_sha256=a.sha(f.read_bytes())))
 elif case=='source_changed':(p/'source/configs/steering/eds.yaml').write_text('modified: true\n')
 elif case=='unknown_check':change(p/'audit.json',lambda x:x['checks'].update(unknown=None))
 elif case=='stale_success_count':change(p/'audit.json',lambda x:x.update(successes=10))
 elif case=='stale_success_ids':change(p/'audit.json',lambda x:x.update(success_task_ids=list(range(10))))
 elif case=='stale_task_success':change(p/'audit.json',lambda x:x['tasks'][0].update(success=True))
 elif case=='fresh_method_mismatch':
  def revalidator(folder,manifest):
   r=good_reaudit(folder,manifest);r['report']['method_audit']['sha256']='0'*64;return r
 elif case=='reaudit_rejected':revalidator=lambda *args: {'valid':False,'report':{'full_audit_performed':True}}
 elif case=='reaudit_raised':
  def revalidator(*args):raise ValueError('Synthetic stale audit')
 r=a.aggregate(bundle,'test',revalidator=revalidator)
 assert not r['all_cohorts_valid'] and not r['final_accepted'],case
 assert r['comparison']['final_success_counts'] is None
 if case=='running':assert r['runs']['eds']['state']=='partial'


def test_unknown_compute_does_not_become_zero(bundle):
 r=a.aggregate(bundle,'test',revalidator=good_reaudit)
 counter=r['runs']['eds']['compute_completed_episode_totals']['provider_reasoning_output_tokens']
 assert counter==dict(total=None,observed_subtotal=0,known_rows=0,unknown_rows=10)


def test_outputs_refuse_raw_run_directory(bundle,tmp_path):
 r=a.aggregate(bundle,'test',revalidator=good_reaudit)
 with pytest.raises(ValueError,match='outside raw runs'):a.write_outputs(r,bundle/'eds-test/aggregate',bundle)
 p=tmp_path/'external/report';a.write_outputs(r,p,bundle)
 with pytest.raises(FileExistsError):a.write_outputs(r,p,bundle)


def test_running_stale_valid_audit_never_calls_final_revalidator(bundle):
 for mode in a.MODES:change(bundle/(mode+'-test/status.json'),lambda x:x.update(state='running'))
 def forbidden(*args):pytest.fail('Running cohorts must not be reclassified')
 r=a.aggregate(bundle,'test',revalidator=forbidden)
 assert not r['final_accepted'] and all(x['state']=='partial' for x in r['runs'].values())


def test_fresh_audit_refuses_changed_python_helper_before_subprocess(tmp_path,monkeypatch):
 root=tmp_path/'code';(root/'scripts').mkdir(parents=True)
 (root/'scripts/audit_steering.py').write_text('# synthetic wrapper')
 helper=root/'scripts/audit_steering_contract.py';helper.write_text('# original helper')
 source={str(p.relative_to(root)):a.sha(p.read_bytes()) for p in (root/'scripts').glob('*.py')}
 helper.write_text('# changed helper')
 monkeypatch.setattr(a.subprocess,'run',lambda *args,**kwargs:pytest.fail('Must reject before executing any code'))
 with pytest.raises(ValueError,match='dependency differs'):
  a.fresh_audit(tmp_path,{'code_root':str(root),'source_sha256':source})


def test_fresh_audit_refuses_changed_rng_manifest_before_subprocess(tmp_path,monkeypatch):
 root=tmp_path/'code';(root/'scripts').mkdir(parents=True)
 p=root/'scripts/audit_steering.py';p.write_text('# synthetic wrapper')
 rng=tmp_path/'rng.json';rng.write_text('{}')
 (tmp_path/'resolved-config.yaml').write_text(yaml.safe_dump({'main':{'episode_rng_fixture_manifest':str(rng),'episode_rng_fixture_manifest_sha256':'0'*64}}))
 monkeypatch.setattr(a.subprocess,'run',lambda *args,**kwargs:pytest.fail('Must reject before executing any code'))
 with pytest.raises(ValueError,match='RNG fixture manifest'):
  a.fresh_audit(tmp_path,{'code_root':str(root),'source_sha256':{'scripts/audit_steering.py':a.sha(p.read_bytes())}})


@pytest.mark.parametrize('score',[2,3,4])
def test_eds_performance_gate_preserves_valid_cohort_scores(bundle,score):
 p=bundle/'eds-test/audit.json';cached=a.read_json(p)
 cached.update(successes=score,success_task_ids=list(range(score)))
 for row in cached['tasks']:row['success']=row['task_id']<score
 write(p,cached)
 def revalidator(folder,manifest):
  fresh=good_reaudit(folder,manifest)
  if manifest['method']=='eds':
   fresh['report'].update(successes=score,success_task_ids=list(range(score)))
   for row in fresh['report']['tasks']:row['success']=row['task_id']<score
  return fresh
 r=a.aggregate(bundle,'test',revalidator=revalidator)
 assert r['all_cohorts_valid'] is True
 assert r['integration_acceptance'] is (score>=3)
 assert r['final_accepted'] is (score>=3)
 assert r['performance_gate']==dict(method='eds',reference_successes=3,denominator=10,observed_successes=score,passed=score>=3,
  scope='Integration performance threshold; does not change validity of scientifically unsuccessful episodes or completed cohorts.')
 assert r['runs']['eds']['accepted'] is True and r['runs']['eds']['state']=='accepted'
 assert r['comparison']['final_success_counts']=={'eds':score,'vls':0,'eds_qd':0}
 assert f'{score}/10' in a.markdown(r)
 if score==2:assert r['state']=='cohorts_valid_integration_threshold_not_met'


def test_pending_cohort_has_no_validated_score_or_performance_decision(bundle):
 for mode in a.MODES:change(bundle/(mode+'-test/status.json'),lambda x:x.update(state='running'))
 r=a.aggregate(bundle,'test',revalidator=good_reaudit)
 assert r['performance_gate']['observed_successes'] is None and r['performance_gate']['passed'] is None
 assert r['comparison']['validated_cohort_success_counts']==dict.fromkeys(a.MODES,None)
 assert all(x['final_successes'] is None for x in r['runs'].values())
