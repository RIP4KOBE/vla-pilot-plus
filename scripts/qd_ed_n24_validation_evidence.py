"""CPU-only historical Dev receipt/proof verification across the exact source bridge."""
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_arithmetic_repair as repair
from scripts import qd_ed_n24_bridge as dev_bridge

def finite(v):return type(v) in (int,float) and math.isfinite(v)

def historical_backend(reference,parent,events,r):
    from scripts import qd_ed_n24_validation_contract as c
    record=w.read_ref(reference)
    source={'commit':parent['source_commit'],'files':parent['code_files'],'sha256':w.canonical_sha(parent['code_files'])}
    runtime={'path':parent['runtime_manifest_path'],'sha256':parent['runtime_manifest_sha256']}
    review=w.read_ref(parent['n24_cohort']['final_review'])
    authority=w.read_ref(parent['n24_cohort']['authority'])
    w.require(record.get('schema')=='n24-source-equivalence-bridge-v1' and record.get('new_source')==source
        and record.get('from_source')==c.dev.BASE and record.get('phase_a_source')==c.dev.PHASE_A
        and record.get('runtime')==runtime and record.get('new_gpu_preflight') is False,
        'validation reviewed Dev arithmetic bridge differs')
    w.require(review=={'schema':'n24-source-runtime-review-v1','disposition':'accepted','source':source,'runtime':runtime,
        'protocol':c.ref(c.dev.PROTOCOL),'source_plan':c.ref(c.dev.SOURCE_PLAN),'source_bridge':reference,
        'native_preflight':{'required':False,'proof':None},'no_gpu_release':True},'validation old root source review differs')
    w.require(authority.get('schema')=='n24-dev-authority-v1' and authority.get('cohort_id')==c.dev.COHORT
        and authority.get('source')==source and authority.get('runtime')==runtime
        and authority.get('final_review')==parent['n24_cohort']['final_review']
        and authority.get('limits')==c.dev.LIMITS and authority.get('caps')==c.dev.CAPS
        and authority.get('validation_authorized') is False and authority.get('formal_authorized') is False,
        'validation Dev authority provenance differs')
    return dev_bridge.settled_backend(record,events,r)


def historical_receipt(final,row,parent,plan_ref,r):
    """Verify original Dev evidence under its original source, without claiming new HEAD."""
    from scripts import qd_ed_n24_validation_contract as c
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
    kind='cuda' if row['profile'] in {'N23','N24'} else 'cpu';arithmetic=receipt.get('audit_backend',{})
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
    from scripts import qd_ed_n24_native as native
    metric=output/'eds_eval/eds_metrics.jsonl'
    w.require(receipt.get('n24_metrics')=={'path':str(metric),'present':metric.is_file(),'sha256':w.sha(metric) if metric.is_file() else None},
        'validation historical serialized metric binding differs')
    w.require(type(final.get('guided_chunks')) is int,'validation historical guided count absent')
    counts,aux=native.from_output(row['profile'],output,report,final['guided_chunks'])
    w.require(receipt.get('n24_native_counts')==counts and receipt.get('n24_auxiliary')==aux,
        'validation historical N24 profile native gate/counters differ')
    return report
