"""Synthetic JSON tests; no runtime imports or real evidence reads."""
import copy, json, math, os, unittest
from pathlib import Path
import summarize_v1 as s

HERE=Path(__file__).resolve().parent
FIX=HERE/'synthetic-fixtures'

def fixture(task=0, dtype='torch.bfloat16', zero=False, guided=True):
    meta=dict(task_id=task,attempt_id=f'synthetic_attempt_{task}',episode_key=f'n25_t{task}',
              accepted_by_root=True,profile='N25')
    def call(phase,iteration,step):
        norm={'finite':True,'zero':zero,'norm':0. if zero else 20.,'norm_dtype':dtype}
        return dict(schema='n25-rbf-call-summary-v1',descriptor_mode=s.MODE,source=s.SOURCE,
            summary_only_not_exact_replay=True,absolute_fallback_used=False,input_shape=[16,64,128],
            input_dtype=dtype,input_stride=[8192,128,1],horizon=8,translation_indices=[39,40,41],
            translation_components=384,clipped_components=80,boundary_components=4,interior_components=300,
            zero_gradient=zero,nonfinite_count=0,phase=phase,iteration=iteration,denoising_step=step,
            timestep=100-step,global_step=24,stage=1,update_operand_is_measured_output_delta=False,
            **{k:copy.deepcopy(norm) for k in s.FIELDS})
    initial=[call('initial',-1,i) for i in range(3)]
    lengths=(3,2,2,2,2,1,1,1,1,1)
    rollout=[[call('rollout',i,j) for j in range(math.ceil(n*.6))] for i,n in enumerate(lengths)]
    metrics=[dict(global_step=24,initial_diversity_descriptor_mode=s.MODE,rollout_diversity_descriptor_mode=s.MODE,
        initial_direction_rbf_evidence_by_step=initial,rollout_direction_rbf_evidence_by_iter=rollout,
        initial_diversity_steps=3,rollout_diversity_steps_applied=15,
        rollout_rbf_steps_by_iter=[dict(iter_idx=i,n_trunc_steps=n,step_indices=list(range(math.ceil(n*.6))),
            step_flags=[j<math.ceil(n*.6) for j in range(n)],step_count=math.ceil(n*.6),fallback_used=False)
            for i,n in enumerate(lengths)],
        score_call_count=11,search_evaluation_count=176,resample_count=10,renoise_count=10,rollout_count=10)] if guided else []
    n=18 if guided else 0;g=int(guided)
    counts=dict(guided_decisions=g,all_call_summaries_verified=n,witness_calls_verified=11*g,
                zero_gradient_calls=n if zero else 0,clipped_components=80*n)
    gate=dict(schema='n25-native-rbf-audit-v1',accepted=True,**counts,
              witness_numeric_bytes=210000*g,witness_checks=[
                  dict(accepted=True,dtype=dtype,comparison='native contiguous uint8; zero tolerance',
                       candidate_rows=16,zero_gradient=zero) for _ in range(11*g)])
    audit={'accepted':True,'evidence_complete':True,'observed_counts':{'canonical_candidate_batch':11} if guided else {},
           s.GATE:gate,'n23_arithmetic_backend':{'kind':'cuda'}}
    compute=dict(guided_chunks=g,unguided_chunks=90-g,rbf_gradient_calls=n,rbf_gradient_batch_rows=16*n)
    receipt=dict(schema='n23-in-worker-audit-receipt-v1',attempt_id=meta['attempt_id'],episode_key=meta['episode_key'],
        profile='N25',accepted=True,main_exit_code=0,process_unchanged=True,source={'commit':s.COMMIT},
        plan={'sha256':s.PLAN_SHA},n25_native_counts=counts,worker_wall_seconds=500.,audit_seconds=3.)
    return meta,metrics,compute,receipt,audit

def wire(cells, namespace=None):
    manifest=dict(schema='n25-measurement-input-manifest-v1',executable=True,
                  source_commit=s.COMMIT,plan_sha256=s.PLAN_SHA,cells=[],
                  root_attestation=dict(all_listed_cells_accepted_and_terminal=True,no_listed_cell_inflight=True,expected_cell_count=len(cells)))
    blobs={}
    for args in cells:
        meta,metrics,compute,receipt,audit=copy.deepcopy(args);base=(FIX/namespace if namespace else FIX)/str(meta['task_id'])
        def add(role,value,jsonl=False):
            path=base/s.ROLES[role]
            data=(''.join(json.dumps(v)+'\n' for v in value) if jsonl else json.dumps(value)).encode()
            blobs[str(path)]=data
            return dict(path=str(path),present=True,sha256=s.sha(data))
        refs={'metrics':add('metrics',metrics,True),'compute':add('compute',[compute],True),'audit':add('audit',audit)}
        receipt['n25_metrics']=refs['metrics']
        receipt['audit_report']={k:refs['audit'][k] for k in ('path','sha256')}
        receipt['evidence']={'files':[dict(path='eds_eval/episode_compute.jsonl',sha256=refs['compute']['sha256']),
                                     dict(path='eds_eval/decision_evidence/episode_000/never-read.pt',sha256='0'*64)]}
        refs['receipt']=add('receipt',receipt);meta['files']=refs;manifest['cells'].append(meta)
    counts={}
    def read(path,limit):
        p=str(path);counts[p]=counts.get(p,0)+1
        return blobs[p]
    return manifest,blobs,counts,read

class SummaryTests(unittest.TestCase):
    def test_fixed_groups_denominators_and_native_dtypes(self):
        result=s.summarize([fixture(),fixture(1,'torch.float32')])
        g=result['aggregate']['all_calls']
        self.assertEqual((g['observed_call_rows'],g['observed_component_denominator']),(36,36*384))
        self.assertEqual(g['clipped_components']+g['boundary_components']+g['interior_components'],36*384)
        self.assertEqual(len(result['aggregate']['groups']),11)
        self.assertEqual(result['aggregate']['phase_totals']['initial']['observed_call_rows'],6)
        for d in s.DTYPES:self.assertEqual(g['native_norms']['update_operand']['by_native_dtype'][d]['observed'],18)
        self.assertEqual(result['cells'][0]['cost_consistency']['status'],'consistent')
        self.assertFalse(result['efficacy_or_promotion_gate'])
    def test_zero_gradient_valid_and_norm_zero_is_not_zero_flag(self):
        args=fixture(zero=True);r=s.summarize([args])
        self.assertEqual(r['cells'][0]['cost_consistency']['status'],'consistent')
        self.assertEqual(r['aggregate']['all_calls']['zero_gradient']['ratio'],1)
        args=fixture();args[1][0]['initial_direction_rbf_evidence_by_step'][0]['gradient_after_normalization']['norm']=0
        self.assertEqual(s.summarize([args])['aggregate']['all_calls']['zero_gradient']['true'],0)
    def test_missing_norm_component_and_group_stay_unknown(self):
        args=fixture();row=args[1][0]['initial_direction_rbf_evidence_by_step'][0]
        del row['update_operand'];del row['clipped_components']
        args[1][0]['rollout_direction_rbf_evidence_by_iter'][3]=None
        g=s.summarize([args])['aggregate']['all_calls']
        self.assertEqual(g['component_unknown_calls'],1)
        self.assertEqual(g['native_norms']['update_operand']['unknown_calls'],1)
        self.assertEqual(g['missing_decision_groups'],1)
    def test_no_guided_no_division_by_zero(self):
        r=s.summarize([fixture(guided=False)])
        c=r['cells'][0]
        self.assertEqual(c['cost_consistency']['status'],'consistent')
        self.assertIsNone(c['all_calls']['zero_gradient']['ratio'])
        self.assertEqual(c['bounded_witness']['recorded_verified_calls'],0)
        self.assertIsNone(c['bounded_witness']['exact_audit_call_coverage'])
    def test_cost_drift_and_mode_missing_explicit(self):
        args=fixture();args[2]['rbf_gradient_calls']=19
        del args[1][0]['initial_diversity_descriptor_mode']
        r=s.summarize([args]);issues=r['cells'][0]['cost_consistency']['issues']
        self.assertTrue(any(x['field']=='compute.rbf_gradient_calls' for x in issues))
        self.assertTrue(any(x['status']=='Unknown' for x in issues))
    def test_witness_coverage_bounded_not_all_calls(self):
        c=s.summarize([fixture()])['cells'][0]['bounded_witness']
        self.assertEqual(c['expected_calls'],11);self.assertEqual(c['exact_audit_call_coverage'],11/18)
        self.assertFalse(c['slot_identity_independently_verified'])
    def test_nearest_rank_quantile(self):
        d=s.distribution(list(range(10)));self.assertEqual(d['p90'],8);self.assertEqual(d['median'],4.5)
    def test_missing_counter_record_not_zero(self):
        args=fixture(guided=False);del args[4]['observed_counts']
        c=s.summarize([args])['cells'][0]
        self.assertIsNone(c['cost_consistency']['recorded_native_canonical_batches'])
        self.assertNotEqual(c['cost_consistency']['status'],'consistent')
    def test_single_read_hash_and_link_binding(self):
        manifest,blobs,counts,read=wire([fixture(),fixture(1)])
        cells,cov=s.load_cells(manifest,read)
        self.assertEqual(cov['file_count'],8);self.assertEqual(set(counts.values()),{1})
        self.assertEqual(cov['tensor_reads'],0)
        self.assertEqual(s.summarize(cells)['accepted_cells_in_frozen_input'],2)
    def test_disabled_manifest_rejects_before_any_read(self):
        manifest,_,counts,read=wire([fixture()]);manifest['executable']=False
        with self.assertRaisesRegex(ValueError,'disabled'):s.load_cells(manifest,read)
        self.assertEqual(counts,{})
    def test_absent_terminal_attestation_blocks_reads(self):
        m,_,counts,read=wire([fixture()]);m['root_attestation']['all_listed_cells_accepted_and_terminal']=False
        with self.assertRaisesRegex(ValueError,'attestation'):s.load_cells(m,read)
        self.assertEqual(counts,{})
    def test_hash_mismatch_rejected(self):
        manifest,blobs,_,read=wire([fixture()])
        blobs[manifest['cells'][0]['files']['metrics']['path']]+=b' '
        with self.assertRaisesRegex(ValueError,'hash'):s.load_cells(manifest,read)
    def test_wrong_source_and_unaccepted_receipt_rejected(self):
        for field,value in [('accepted',False),('source',{'commit':'wrong'})]:
            args=fixture();args[3][field]=value
            m,_,_,r=wire([args])
            with self.assertRaises(ValueError):s.load_cells(m,r)
    def test_duplicate_and_more_than_ten_cells(self):
        m,_,_,r=wire([fixture(),fixture()])
        with self.assertRaisesRegex(ValueError,'duplicate'):s.load_cells(m,r)
        m,_,_,r=wire([fixture(i) for i in range(11)])
        with self.assertRaisesRegex(ValueError,'cap'):s.load_cells(m,r)
    def test_zero_guided_absent_metrics_requires_three_json_witnesses(self):
        for guided,expected in [(0,True),(1,False)]:
            args=fixture(guided=False);args[2]['guided_chunks']=guided
            m,b,_,r=wire([args],namespace='absent-metric-case');cell=m['cells'][0]
            cell['files']['metrics'].update(present=False,sha256=None)
            rp=cell['files']['receipt']['path'];receipt=json.loads(b[rp])
            receipt['n25_metrics']=cell['files']['metrics']
            b[rp]=json.dumps(receipt).encode();cell['files']['receipt']['sha256']=s.sha(b[rp])
            if expected:
                _,cov=s.load_cells(m,r);self.assertEqual(cov['file_count'],3)
            else:
                with self.assertRaisesRegex(ValueError,'absent guided'):s.load_cells(m,r)
    def test_nonnative_nonfinite_norm_unknown(self):
        args=fixture();row=args[1][0]['initial_direction_rbf_evidence_by_step'][0]
        row['update_operand']['norm']=float('nan')
        g=s.summarize([args])['aggregate']['all_calls']
        self.assertEqual(g['native_norms']['update_operand']['unknown_calls'],1)
        json.dumps(s.summarize([args]),allow_nan=False)

if __name__=='__main__':
    import guard_v1
    guard=guard_v1.install(synthetic_root=FIX,write_paths=[str(HERE/'cpu-guard-v1.json')])
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SummaryTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (HERE/'cpu-guard-v1.json').write_text(json.dumps(guard,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
