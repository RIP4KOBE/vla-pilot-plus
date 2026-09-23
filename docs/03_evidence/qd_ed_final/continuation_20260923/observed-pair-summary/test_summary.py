"""Synthetic JSON fixtures only; never reads real episodes or tensor bundles."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('summary', HERE/'summarize_pairs.py')
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = {'schema':'qd-ed-final-plan-v1', 'frozen':True, 'artifact_root':str(self.root), 'worktree':str(self.root/'source'),
            'phase_authorization':{'dev':True, 'validation':False, 'formal':False},
            'observational_overrides':{'main.decision_evidence.enabled':True},
            'source_commit':'synthetic-source', 'profiles_sha256':'p'*64,
            'runtime_inventory_sha256':'i'*64, 'runtime_manifest_sha256':'r'*64,
            'code_files':[{'path':s.ANALYZER,'sha256':'a'*64},{'path':s.AUDITOR,'sha256':'b'*64},
                          {'path':s.TARGET_MAP,'sha256':'c'*64}], 'episodes':[]}
        for key,(task,arm,seed) in zip(s.KEYS,s.ORDER):
            self.plan['episodes'].append({'episode_key':key,'task_id':task,'profile':arm,
                'env_seed':seed,'policy_seed':seed,'split':'dev','seed_block':'dev','init_index':0,
                'budget_bucket':'development','iteration':'OBSERVED_PAIRS_DEV_20260923','timeout_seconds':1800})
        self.plan_ref = self.write(self.root/'synthetic-plan.json',self.plan)
        self.addCleanup(patch.stopall)
        patch.object(s,'EXPECTED_PLAN_SHA',self.plan_ref['sha256']).start()
        self.manifest = {'schema':'qd-ed-observed-pair-summary-input-v1','plan':self.plan_ref,
                         'episodes':{key:None for key in s.KEYS}}

    def write(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value,sort_keys=True)+'\n')
        return {'path':str(path),'sha256':s.digest(path.read_bytes())}

    def complete(self,index,*,eligible=True,a=False,b=False,success=False,provider='same'):
        row=self.plan['episodes'][index]
        output=self.root/'attempts'/('synthetic-'+row['episode_key'])
        episode=output/'eds_eval/decision_evidence/episode_000'
        compute=output/'eds_eval/episode_compute.jsonl'
        terminal={'attempt_id':output.name,'output_dir':str(output),'episode_key':row['episode_key'],
            'identity':{k:row[k] for k in s.IDENTITY_FIELDS},'physical_gpu':3,'budget_bucket':'development',
            'plan_sha256':self.plan_ref['sha256'],'source_commit':self.plan['source_commit'],
            'profile_manifest_sha256':self.plan['profiles_sha256'],
            'runtime_inventory_sha256':self.plan['runtime_inventory_sha256'],
            'runtime_manifest_sha256':self.plan['runtime_manifest_sha256'],
            'event':'valid','outcome_valid':True,'success':success,'task_failure':not success,
            'gpu_process_wall_seconds':10+index,'provider_request_attempts':None}
        audit={'schema':'qd-ed-decision-evidence-audit-v1','accepted':True,'evidence_complete':True,'errors':[],
            'episode_dir':str(episode),'episode_compute_file':str(compute),'original_execution_outcome':'completed'}
        decision={'decision_id':'synthetic-decision','stage':1,'guidance':True,
            'provider_identities':[{'original_code_sha256':provider,'source_text_sha256':'synthetic','source_path':'/synthetic/provider'}],
            'hypothesis_eligible':eligible,'unknown_reasons':[] if eligible else ['target_unknown'],
            'hypothesis_ineligible_reasons':[] if eligible else ['target_unknown'],
            'diagnostics':{'projection_optimism_witness':b,'step7_to8':{'both_regress_robust':a}}}
        stratum={k:decision[k] for k in ('stage','guidance','provider_identities')}
        stratum.update(decisions=1,hypothesis_eligible_decisions=int(eligible),
            projection_optimism_witness_ids=[decision['decision_id']] if eligible and b else [],
            step7_to8_joint_regression_witness_ids=[decision['decision_id']] if eligible and a else [],
            actual_progress_median_m=0.1,projection_rmse_median_m=0.01)
        analysis={'schema':'qd-ed-selected-decision-analysis-v2','input_kind':'audited_runtime_episode',
            'source_sha256':{'analysis':'a'*64,'existing_auditor':'b'*64},'episode_dir':str(episode),
            'task_id':row['task_id'],'episode_seed':row['env_seed'],'episode_id':0,
            'original_execution_outcome':'completed','cuda_initialized_before':False,'cuda_initialized_after':False,
            'audit':copy.deepcopy(audit),'input_sha256':{str(p):'f'*64 for p in (episode/'status.json',episode/'events.jsonl',compute)},
            'decisions':[decision],'strata':[stratum]}
        analysis['input_sha256'][str(Path(self.plan['worktree'])/s.TARGET_MAP)]='c'*64
        audit['wrapper_observation']={'audit_wall_seconds':1.0,'parent_ru_maxrss_before_kib':123,'parent_ru_maxrss_after_kib':456}
        refs={'status':'complete','terminal':self.write(output/'attempt-result.json',terminal),
            'audit':self.write(output/'eds_eval/decision-evidence-audit.json',audit),
            'analysis':self.write(self.root/'continuation_20260923/synthetic-analysis'/f'{index}.json',analysis)}
        self.manifest['episodes'][row['episode_key']]=refs
        return refs

    def test_partial_matrix_does_not_read_raw_or_compare_early_and_accepted_is_not_success(self):
        self.complete(0,a=True,success=False)
        self.complete(1,eligible=False,a=True,b=True,success=True)
        report=s.summarize(self.manifest)  # No raw/status/index/compute files exist.
        self.assertEqual((report['completed_episodes'],report['pending_episodes']),(2,2))
        self.assertTrue(all(pair['status']=='pending_all_four' for pair in report['pairs']))
        self.assertFalse(report['rows'][0]['original_outcome']['success'])
        self.assertTrue(report['rows'][0]['audit']['accepted'])
        self.assertEqual(report['rows'][0]['mechanism']['A_unscored_tail']['episode_presence'],'present')
        self.assertEqual(report['rows'][1]['mechanism']['B_projection_response']['episode_presence'],'Unknown')
        self.assertIsNone(report['rows'][2]['costs'])
        self.assertEqual(report['completed_episode_gpu_wall_seconds'],21)
        self.assertIn('pending_all_four',s.render_markdown(report))

    def test_full_matrix_preserves_provider_strata_and_episode_unit_without_promotion(self):
        self.complete(0,a=True,b=True)
        self.complete(1,a=False,b=False,provider='different')
        self.complete(2,eligible=False)
        self.complete(3,a=False,b=True)
        report=s.summarize(self.manifest)
        self.assertEqual(report['status'],'complete_descriptive_matrix')
        self.assertEqual(report['promotion_status'],'NOT_EVALUATED')
        self.assertEqual(report['completed_episode_gpu_wall_seconds'],46)
        alignment=report['pairs'][0]['stage_provider_alignment']
        self.assertEqual(len(alignment),2)
        self.assertTrue(all(item['match']=='unmatched_retained' for item in alignment))
        self.assertEqual(report['rows'][0]['mechanism']['A_B_overlap_decision_ids'],['synthetic-decision'])
        self.assertIn('not independent samples',report['limitations'])
        self.assertNotIn('success_rate',report)

    def test_rejects_tamper_wrong_source_external_gpu_and_unaccepted_evidence(self):
        refs=self.complete(0)
        source_manifest=copy.deepcopy(self.manifest)
        for document,key,value,expected in [('terminal','physical_gpu',2,'cannot be pooled'),
            ('audit','accepted',False,'accepted complete audit'),
            ('analysis','source_sha256',{'analysis':'x'*64,'existing_auditor':'b'*64},'source differs')]:
            self.manifest=copy.deepcopy(source_manifest)
            path=Path(refs[document]['path']); original=path.read_bytes(); payload=json.loads(original)
            payload[key]=value
            self.manifest['episodes'][s.KEYS[0]][document]=self.write(path,payload)
            with self.assertRaisesRegex(ValueError,expected): s.summarize(self.manifest)
            path.write_bytes(original)
        self.manifest=copy.deepcopy(source_manifest)
        path=Path(refs['analysis']['path']); original=path.read_bytes(); payload=json.loads(original)
        payload['input_sha256'][str(Path(self.plan['worktree'])/s.TARGET_MAP)]='new-supplemental-map'
        self.manifest['episodes'][s.KEYS[0]]['analysis']=self.write(path,payload)
        with self.assertRaisesRegex(ValueError,'supplemental maps cannot be pooled'): s.summarize(self.manifest)
        path.write_bytes(original)
        self.manifest=copy.deepcopy(source_manifest)
        Path(refs['analysis']['path']).write_text('{}')
        with self.assertRaisesRegex(ValueError,'SHA mismatch'): s.summarize(self.manifest)

    def test_unknown_or_partial_rows_cannot_silently_enter_matrix(self):
        self.manifest['episodes'][s.KEYS[0]]={'status':'pending','analysis':{'path':'partial.json','sha256':'0'*64}}
        with self.assertRaisesRegex(ValueError,'partial inputs'): s.summarize(self.manifest)
        self.manifest['episodes'][s.KEYS[0]]=None
        self.manifest['episodes']['external-gpu2-row']=None
        with self.assertRaisesRegex(ValueError,'four predetermined keys'): s.summarize(self.manifest)


if __name__=='__main__': unittest.main()
