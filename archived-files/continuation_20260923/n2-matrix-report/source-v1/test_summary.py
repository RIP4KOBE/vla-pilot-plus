"""Synthetic JSON fixtures only; no live output, tensor, or model is read."""
import copy
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n2_matrix_summary', HERE/'summarize_matrix.py')
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)


def plan_fixture():
    plan = {k:k+'_sha' for k in s.BINDING}
    plan.update(n2_cohort={'cohort_id':s.COHORT,'protocol':{'sha256':'protocol'},'accounting_clarification':{'sha256':'clarification'}},
        candidate_profiles={'N2':{'sha256':'candidate'}}, episodes=[])
    for task in range(10):
        for profile in s.PROFILES:
            plan['episodes'].append({'episode_key':f'n2_dev_t{task:02d}_{profile.lower()}_20260923',
                'task_id':task,'profile':profile,'split':'dev','iteration':s.COHORT,'env_seed':task+10,
                'policy_seed':task+20,'init_index':0,'init_row_sha256':str(task)})
    return plan


def terminal_fixture(plan, row, output, *, valid=True, success=True, number=0):
    binding = {k:plan[k] for k in s.BINDING}
    binding.update(cohort_id=s.COHORT,protocol_sha256='protocol',accounting_clarification_sha256='clarification',
        candidate_sha256='candidate',stage_public_config_sha256='stage')
    t = {'attempt_id':row['episode_key']+f'__{number}', 'episode_key':row['episode_key'],
        'identity':{k:row[k] for k in s.IDENTITY}, 'event':'valid','outcome_valid':valid,'success':success,
        'task_failure':not success,'plan_sha256':'plan','physical_gpu':3,'source_commit':plan['source_commit'],
        'profile_manifest_sha256':plan['profiles_sha256'],'runtime_manifest_sha256':plan['runtime_manifest_sha256'],
        'runtime_inventory_sha256':plan['runtime_inventory_sha256'],'init_row_sha256':row['init_row_sha256'],
        'n2_cohort_id':s.COHORT,'n2_frozen_identity':binding,'retry_of':row.get('retry_of'),
        'output_dir':str(output),'time_unix':100+number,'gpu_process_wall_seconds':100.,
        'metric_chunks':1,'candidate_evaluations':176,'score_batches':11,'compute_outcome':'completed',
        'required_cost_telemetry_complete':True,'stage_backend':'codex_cli','stage_condition':'codex_login_astra_low_v1',
        'provider_token_usage_complete':True,'stage_failed_queries':0,'stage_successful_queries':1,'stage_query_events':1}
    t.update({k:0 for k in s.COSTS if k not in t})
    t.update(guided_chunks=1,model_forward_calls=5,provider_logical_call_attempts=1,provider_completed_turns=1,
        provider_usage_complete_calls=1,provider_input_tokens=200,provider_output_tokens=10,provider_call_latency_s=.5,
        provider_request_attempts=None,provider_sdk_retry_attempts=None,provider_reasoning_output_tokens=None)
    return t


def metric_fixture(profile):
    metric={'episode':0,'task_id':0,'global_step':0,'score_call_count':11,'search_evaluation_count':176,
        'action_mask_violation_max':0., 'qd_archive_active_for_chunk':profile!='C0',
        'select_action_latency_s':2.,'eds_loop_latency_s':1.}
    metric.update({k:0 for k in s.VIOLATIONS})
    if profile == 'N2':
        metric.update(qd_quality_mode='executed_prefix_v1',qd_quality_applicable=True,
            qd_quality_reason='recognized_weighted_distance_template',qd_quality_target_index=1,
            qd_quality_identity={'source_text_sha256':'a'*64,'code_structure_sha256':'b'*64},
            qd_quality_changed_candidates=176,qd_selected_raw_reward=-2.,qd_final_best_raw_reward=-1.,
            qd_selected_raw_gap=-1.,qd_best_observed_raw_reward=-.5,selected_reward=-.125,
            qd_quality_batches=[{'iter_idx':i,'raw_provider_quality':[-2.]*16,'quality':[-.125]*16,'fingerprints':['a'*64]*16} for i in range(-1,10)])
    return metric


def write_fixture(root, profile='N2', *, valid=True, accepted=True):
    plan=plan_fixture();row=next(r for r in plan['episodes'] if r['task_id']==0 and r['profile']==profile)
    output=root/'attempt';output.mkdir()
    terminal=terminal_fixture(plan,row,output,valid=valid)
    def write(path,value,lines=False):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value)+'\n')
        return {'path':str(path),'sha256':s.sha(path)}
    refs={'terminal':write(output/'attempt-result.json',terminal)}
    if valid:
        audit={'accepted':accepted,'evidence_complete':accepted,'errors':[] if accepted else ['incomplete'],
            'episode_dir':str(output/'eds_eval/decision_evidence/episode_000'),
            'episode_compute_file':str(output/'eds_eval/episode_compute.jsonl'),
            'original_execution_outcome':'completed','observed_scoring_roles':{'canonical_initial':1,'canonical_offspring':10,'auxiliary_pretest':2}}
        refs['audit']=write(output/'eds_eval/decision-evidence-audit.json',audit)
        if accepted:
            compute={k:terminal[k] for k in s.COSTS}
            compute.update(episode_id=0,task_id=0,episode_seed=row['env_seed'],outcome='completed',
                decision_evidence={'observer_wall_s':.25,'bytes_written':12345})
            refs['compute']=write(output/'eds_eval/episode_compute.jsonl',compute,True)
            refs['metrics']=write(output/'eds_eval/eds_metrics.jsonl',metric_fixture(profile),True)
    return plan,refs


def fake_loaded(plan,row,success=True):
    terminal=terminal_fixture(plan,row,Path('/synthetic')/row['episode_key'],success=success)
    metric=metric_fixture(row['profile']);metric['task_id']=row['task_id']
    audit={'observed_scoring_roles':{'canonical_initial':1,'canonical_offspring':10}}
    compute={**terminal,'decision_evidence':{'observer_wall_s':.25,'bytes_written':100}}
    return {'terminal':terminal,'status':'complete_valid','references':{},'metrics':s.summarize_metrics([metric],terminal,audit,compute)}


class Tests(unittest.TestCase):
    def test_full_synthetic_manifest_cli_writes_new_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);plan,refs=write_fixture(root)
            plan['artifact_root']=str(root/'artifacts')
            def save(name,data):
                p=root/name;p.write_text(json.dumps(data)+'\n')
                return {'path':str(p),'sha256':s.sha(p)}
            planref=save('plan.json',plan)
            terminal_path=Path(refs['terminal']['path']);terminal=json.loads(terminal_path.read_text())
            terminal['plan_sha256']=planref['sha256'];terminal_path.write_text(json.dumps(terminal)+'\n')
            refs['terminal']['sha256']=s.sha(terminal_path)
            script=HERE/'summarize_matrix.py';protocol_sha=s.sha(HERE/'protocol.md')
            auth=save('auth.json',{'script':{'path':str(script),'sha256':s.sha(script)},
                'protocol_sha256':protocol_sha,'base_plan_sha256':planref['sha256']})
            manifest=save('manifest.json',{'schema':'qd-ed-n2-report-input-v1','script_sha256':s.sha(script),
                'protocol_sha256':protocol_sha,'authorization':auth,'base_plan':planref,'attempts':[refs],
                'input_scope_complete':True})
            destination=Path(plan['artifact_root'])/'continuation_20260923/report.json'
            with patch.object(s,'BASE_PLAN_SHA',planref['sha256']),patch.dict(os.environ,{'CUDA_VISIBLE_DEVICES':''}),patch.object(sys,'argv',[
                str(script),'--manifest',manifest['path'],'--output',str(destination),'--execute-reviewed']),contextlib.redirect_stdout(io.StringIO()):
                s.main()
            result=json.loads(destination.read_text())
            self.assertEqual(result['cell_status_counts'],{'missing':29,'complete_valid':1})
            self.assertTrue(result['input_scope_complete'])
            self.assertEqual(result['profiles']['N2']['n2_quality_summary']['quality_changed_candidates'],176)

    def test_real_loader_order_accepts_only_SHA_bound_accepted_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,refs=write_fixture(Path(tmp))
            loaded=s.load_attempt(refs,{'plan':plan})
            self.assertEqual(loaded['status'],'complete_valid')
            self.assertEqual(loaded['metrics']['n2']['quality_changed_candidates'],176)
            self.assertFalse(loaded['metrics']['n2']['normalized_stage_input_directly_observed'])
            self.assertEqual(loaded['metrics']['n2']['raw_selected_minus_final_best']['min'],-1.)
            self.assertEqual(loaded['metrics']['observed_scoring_roles']['auxiliary_pretest'],2)

    def test_valid_event_outcome_false_is_terminal_invalid_without_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,refs=write_fixture(Path(tmp),valid=False)
            row=s.load_attempt(refs,{'plan':plan})
            result=s.summarize(plan,[row])
            self.assertEqual(result['cell_status_counts'],{'missing':29,'terminal_invalid':1})
            self.assertIsNone(result['cells'][2]['success'])
            self.assertEqual(result['profiles']['N2']['failures_observed'],0)
            self.assertEqual(result['profiles']['N2']['all_attempt_gpu_seconds']['complete_total'],100.)
            self.assertIsNone(result['paired_comparisons']['N2_vs_C0']['gained_tasks'])

    def test_rejected_audit_never_reads_metrics_and_raw_success_survives(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan,refs=write_fixture(Path(tmp),accepted=False)
            row=s.load_attempt(refs,{'plan':plan})
            self.assertEqual(row['status'],'pending_or_rejected_audit')
            self.assertTrue(row['terminal']['success'])
            self.assertNotIn('metrics',row)
            refs['metrics']={'path':'/must/not/open.jsonl','sha256':'bad'}
            with self.assertRaisesRegex(ValueError,'rejected audit'):
                s.load_attempt(refs,{'plan':plan})

    def test_missing_optional_counts_remain_unknown_not_zero(self):
        self.assertEqual(s.observed([1,None])['observed_subtotal'],1)
        self.assertIsNone(s.observed([1,None])['complete_total'])
        self.assertIsNone(s.observed([])['observed_subtotal'])
        with tempfile.TemporaryDirectory() as tmp:
            plan,refs=write_fixture(Path(tmp))
            row=s.load_attempt(refs,{'plan':plan})
            result=s.summarize(plan,[row])
            self.assertIsNone(result['profiles']['N2']['all_attempt_cost_fields']['provider_reasoning_output_tokens']['complete_total'])
            self.assertIsNone(result['stage_http_requests'])

    def test_complete_30_pairs_have_honest_gains_losses_and_numeric_only_gate(self):
        plan=plan_fixture(); attempts=[]
        wins={'C0':{0,1,2,3,4},'Q0':{0,1,2,3,5},'N2':{0,1,2,3,6}}
        for row in plan['episodes']:
            attempts.append(fake_loaded(plan,row,row['task_id'] in wins[row['profile']]))
        report=s.summarize(plan,attempts)
        self.assertEqual(report['matrix'],'complete_valid_30')
        self.assertEqual(report['paired_comparisons']['N2_vs_C0']['gained_tasks'],[6])
        self.assertEqual(report['paired_comparisons']['N2_vs_C0']['lost_tasks'],[4])
        self.assertEqual(report['paired_comparisons']['N2_vs_Q0']['lost_tasks'],[5])
        self.assertTrue(report['protocol_numeric_dev_criterion'])
        self.assertFalse(report['phase_authorized'])
        self.assertEqual(report['profiles']['N2']['n2_quality_summary']['quality_changed_candidates'],1760)
        report=s.summarize(plan,attempts[:-1])
        self.assertIsNone(report['protocol_numeric_dev_criterion'])
        self.assertIsNone(report['paired_comparisons']['N2_vs_C0']['gained_tasks'])

    def test_recovery_counts_one_valid_cell_keeps_both_costs(self):
        plan=plan_fixture();row=plan['episodes'][2]
        valid=fake_loaded(plan,row)
        old=copy.deepcopy(valid);old['status']='terminal_invalid';old.pop('metrics')
        t=old['terminal'];t.update(outcome_valid=False,success=False,event='aborted',retryable_infrastructure=True)
        valid['terminal'].update(attempt_id='recovery',retry_of=t['attempt_id'],time_unix=200.)
        result=s.summarize(plan,[old,valid])
        self.assertEqual(result['profiles']['N2']['complete_valid'],1)
        self.assertEqual(result['profiles']['N2']['terminal_attempts'],2)
        self.assertEqual(result['profiles']['N2']['all_attempt_gpu_seconds']['complete_total'],200.)
        self.assertEqual(result['profiles']['N2']['valid_cell_cost_fields']['model_forward_calls']['complete_total'],5)
        old['status']='complete_valid';old['terminal']['outcome_valid']=True
        with self.assertRaisesRegex(ValueError,'invalid replacement'):
            s.summarize(plan,[old,valid])

    def test_inapplicable_N2_has_no_invented_raw_gap(self):
        plan=plan_fixture();row=plan['episodes'][2];t=terminal_fixture(plan,row,Path('/synthetic'))
        metric=metric_fixture('N2')
        metric.update(qd_quality_applicable=False,qd_quality_reason='not_weighted_distance_template',
            qd_quality_batches=[],qd_quality_changed_candidates=0,qd_selected_raw_reward=None,
            qd_final_best_raw_reward=None,qd_selected_raw_gap=None,qd_best_observed_raw_reward=None)
        result=s.summarize_metrics([metric],t,{},t)
        self.assertEqual(result['n2']['inapplicable_chunks'],1)
        self.assertIsNone(result['n2']['raw_selected_minus_final_best']['min'])
        self.assertEqual(result['n2']['raw_selected_minus_final_best']['count'],0)

    def test_raw_gap_changed_count_or_finite_failure_is_not_silently_repaired(self):
        plan=plan_fixture();row=plan['episodes'][2];t=terminal_fixture(plan,row,Path('/synthetic'))
        for key,value in [('qd_selected_raw_gap',0),('qd_quality_changed_candidates',1),('nonfinite_count',1)]:
            metric=metric_fixture('N2');metric[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                s.summarize_metrics([metric],t,{},t)

    def test_wrong_source_or_plan_cannot_pool_external_observation(self):
        plan=plan_fixture();row=plan['episodes'][0];t=terminal_fixture(plan,row,Path('/synthetic'))
        s.validate_terminal(t,plan,'plan')
        t['source_commit']='old-observation-source'
        with self.assertRaisesRegex(ValueError,'frozen condition'):
            s.validate_terminal(t,plan,'plan')
        plan['episodes'][0]['env_seed']=999
        with self.assertRaisesRegex(ValueError,'matched task'):
            s.plan_contract(plan)

    def test_no_authorization_no_reads_and_nonfinite_JSON_rejected(self):
        result=subprocess.run([sys.executable,str(HERE/'summarize_matrix.py'),'--manifest','/nonexistent',
            '--output','/nonexistent'],capture_output=True,text=True,env={**os.environ,'CUDA_VISIBLE_DEVICES':''},timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('explicit review and empty CUDA mask',result.stderr)
        self.assertNotIn('FileNotFoundError',result.stderr)
        with self.assertRaises(ValueError):s.parse('{"value":NaN}')
        with self.assertRaises(ValueError):s.parse('{"value":1,"value":2}')


if __name__=='__main__':
    unittest.main()
