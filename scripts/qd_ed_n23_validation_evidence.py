"""Hash-only historical readiness/receipts across an explicit source bridge."""
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_v2_backend as backend
from scripts import qd_ed_n23_arithmetic_repair as repair


def finite(v):return type(v) in (int,float) and math.isfinite(v)


def historical_backend(reference,parent,events,r):
    """Never calls validate_plan/current-HEAD verification or executes arithmetic."""
    w.require(set(reference)=={'plan','report','attempt_id'},'validation original backend reference differs')
    plan=w.read_ref(reference['plan']);report=w.read_ref(reference['report'])
    source={'commit':parent['source_commit'],'files':parent['code_files'],'sha256':w.canonical_sha(parent['code_files'])}
    runtime_ref={'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']}
    w.require(plan['source']==source and plan['runtime']==runtime_ref
        and plan.get('uuid_repair',{}).get('schema')=='n23-arithmetic-repair-binding-v3'
        and reference==parent['n23_cohort']['backend_proof']
        and plan['protocol']==dev.ref(dev.BACKEND_PROTOCOL)
        and plan['timeout_observability']==dev.ref(dev.OBSERVABILITY)
        and plan['predecessor_review']==dev.predecessor_review(),'validation original backend source/protocol differs')
    terminal=repair.verify_lineage(plan,reference,events,source,r)
    backend.verify_corpus_files(plan['corpus'])
    w.require(plan['corpus']==backend.corpus_from_index(plan['corpus']['index']),'validation backend corpus index differs')
    output=Path(reference['report']['path']).parent
    expected_plan={'path':str(Path(reference['plan']['path']).resolve()),'sha256':reference['plan']['sha256']}
    w.require(report.get('schema')=='n23-backend-preflight-proof-v2' and report.get('accepted') is True
        and report.get('task_outcome') is False and report.get('source')==source and report.get('plan')==expected_plan
        and report.get('runtime')==runtime_ref and report.get('limits')==backend.LIMITS
        and report.get('attempt_id')==reference['attempt_id']
        and report.get('uuid_repair')==plan['uuid_repair'] and report.get('retry_of')==repair.FAILED_ATTEMPT,
        'validation original arithmetic proof association differs')
    start=r['read_json'](output/backend.artifact_name(plan,'start'))
    w.require(start=={'schema':'n23-backend-preflight-start-v2','process':report['process'],'plan':report['plan'],
        'attempt_id':report['attempt_id'],'source':source},'validation backend start/process differs')
    release=w.read_ref(report['release']);context=w.read_ref(report['attempt_context'])
    w.require(release=={'schema':'n23-backend-preflight-release-v2','plan':report['plan'],'source':source,
        'runtime':runtime_ref,'limits':backend.LIMITS,'attempt_id':report['attempt_id'],
        'predecessor_review':plan['predecessor_review'],'retry_of':repair.FAILED_ATTEMPT}
        and context=={'schema':'n23-recovery-attempt-context-v2','attempt_id':report['attempt_id'],
            'output_dir':str(output.resolve()),'budget_bucket':'recovery','plan':report['plan'],
            'timeout_seconds':120,'cleanup_seconds':40,'retry_of':repair.FAILED_ATTEMPT},
        'validation backend release/context differs')
    w.require(terminal.get('process')==report['process'] and terminal.get('backend_preflight_report')==reference['report']
        and finite(report.get('worker_wall_seconds')) and finite(terminal.get('gpu_process_wall_seconds'))
        and 0<=report['worker_wall_seconds']<=120
        and report['worker_wall_seconds']<=terminal['gpu_process_wall_seconds']<=160,
        'validation original metered arithmetic lifetime differs')
    runtime=w.read_ref(runtime_ref);observed=report.get('backend',{})
    repair.verify_identity(observed,runtime);repair.verify_arithmetic_success(report)
    w.require(observed.get('kind')=='cuda' and observed.get('logical_device')=='cuda:0'
        and isinstance(observed.get('torch_version'),str) and observed['torch_version']
        and isinstance(observed.get('cuda_version'),str) and observed['cuda_version']
        and {'torch.float32','torch.bfloat16'}<=set(observed.get('dtype_coverage',[])),
        'validation original arithmetic dtype/backend incomplete')
    return reference


def historical_receipt(final,row,parent,plan_ref,r):
    """Verify original Dev evidence under its original source, without claiming new HEAD."""
    from scripts import qd_ed_n23_validation_contract as c
    output=Path(final['output_dir'])
    context_ref=c.ref(output/'n23-worker-context.json');context=w.read_ref(context_ref)
    receipt_ref=c.ref(output/'eds_eval/in-worker-audit-receipt.json');receipt=w.read_ref(receipt_ref)
    runtime_ref={'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']}
    runtime=w.read_ref(runtime_ref)
    source={'commit':parent['source_commit'],'files':parent['code_files'],'sha256':w.canonical_sha(parent['code_files'])}
    manifest=c.manifest(parent,r);command,expected_output=r['build_command'](parent,manifest,runtime,row,final['attempt_id'])
    w.require(Path(expected_output).resolve()==output.resolve() and context=={
        'schema':'n23-metered-worker-context-v1','attempt_id':final['attempt_id'],'episode_key':row['episode_key'],
        'profile':row['profile'],'output_dir':str(output.resolve()),'worktree':str(Path(parent['worktree']).resolve()),
        'main_argv':command[1:],'plan':plan_ref,'runtime':runtime_ref,'source':source},
        'validation historical worker context/command differs')
    w.require(w.read_ref(context['plan'])==parent and final.get('n23_worker_receipt')==receipt_ref,
        'validation historical receipt/plan terminal association differs')
    process=r['read_json'](output/'process.json');identity={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
    start=r['read_json'](output/'eds_eval/in-worker-audit-start.json')
    w.require(start=={'schema':'n23-worker-start-v1','process':identity,'context':context_ref}
        and process.get('attempt_id')==final['attempt_id'] and receipt.get('process')==identity
        and final.get('process')==process and receipt.get('process_unchanged') is True,
        'validation historical same-process ownership differs')
    w.require(receipt.get('schema')=='n23-in-worker-audit-receipt-v1' and receipt.get('accepted') is True
        and receipt.get('main_exit_code')==0 and receipt.get('context')==context_ref
        and all(receipt.get(k)==context[k] for k in ('attempt_id','episode_key','profile','plan','runtime','source'))
        and receipt.get('main_argv_sha256')==w.canonical_sha(command[1:])
        and receipt.get('evidence')==w.evidence_record(output),'validation historical native source/evidence differs')
    actual=receipt.get('worker_cuda',{});repair.verify_identity(actual,runtime)
    kind='cuda' if row['profile']=='N23' else 'cpu';arithmetic=receipt.get('audit_backend',{})
    w.require(arithmetic.get('kind')==kind and arithmetic.get('logical_device')==('cuda:0' if kind=='cuda' else 'cpu'),
        'validation historical audit backend differs')
    if kind=='cuda':
        w.require(arithmetic.get('physical_uuid')==actual['physical_uuid']
            and arithmetic.get('torch_version')==actual.get('torch_version')
            and arithmetic.get('cuda_version')==actual.get('cuda_version')
            and isinstance(arithmetic.get('dtype_coverage'),list),'validation historical CUDA identity differs')
    report_ref=c.ref(output/'eds_eval/decision-evidence-audit.json')
    w.require(receipt.get('audit_report')==report_ref,'validation historical native report path/hash differs')
    report=w.read_ref(report_ref)
    w.require(report.get('accepted') is True and report.get('evidence_complete') is True
        and report.get('n23_arithmetic_backend')==arithmetic
        and finite(receipt.get('audit_seconds')) and finite(receipt.get('worker_wall_seconds'))
        and 0<=receipt['audit_seconds']<=receipt['worker_wall_seconds']<=final['gpu_process_wall_seconds'],
        'validation historical native report/metering differs')
    if kind=='cuda':
        gate=report.get('n23_actuator_clipped_quality_audit')
        w.require((gate is None and report.get('observed_counts',{}).get('canonical_candidate_batch',0)==0
            and arithmetic['dtype_coverage']==[]) or (isinstance(gate,dict) and gate.get('candidate_scores_verified',0)>0
            and arithmetic['dtype_coverage']),'validation historical N23 arithmetic coverage missing')
    return report
