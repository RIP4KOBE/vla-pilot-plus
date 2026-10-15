"""N25 envelope around the unchanged exact Codex-timeout classifier."""
from pathlib import Path
import types
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n25_contract as c
from scripts import qd_ed_n25_native as native


def classifier():
    from scripts import qd_ed_n23_v2_recovery
    return qd_ed_n23_v2_recovery


def terminal_binding(final,row,plan,reference,r):
    classifier().terminal_binding(final,row,plan,reference,r)


def check_cell_history(events,row,primary_id,r):
    local=[e for e in events if e.get('identity',{}).get('iteration')==c.COHORT]
    groups=r['event_groups'](local)
    own=[g for g in groups.values() if g[0].get('episode_key')==row['episode_key']]
    w.require(len(own)==1 and own[0][0]['attempt_id']==primary_id
        and [e['event'] for e in own[0]]==['reserved','dispatched','valid']
        and own[0][-1].get('outcome_valid') is False and all(e.get('retry_of') is None for e in own[0])
        and own[0][0]['identity']==r['episode_identity'](row), 'N25 recovery requires one completed invalid primary')
    w.require(len({e['attempt_id'] for e in local if e.get('retry_of')})<2,'N25 recovery slots exhausted')
    return own[0][-1]



def diagnose(final,row,profile,runtime,r,report):
    """Private evidence-reader substitution only; all original timeout gates stay exact."""
    original=classifier()
    path=Path(final['output_dir'])/'eds_eval/eds_metrics.jsonl'
    if path.is_file():return original.diagnose(final,row,profile,runtime,r,native_report=report)
    w.require(type(final.get('guided_chunks')) is int and final['guided_chunks']==0,
        'N25 absent metric recovery needs explicit terminal guided zero')
    counts,_=native.from_output(row['profile'],final['output_dir'],report,0)
    w.require(counts['guided_decisions']==0,'N25 absent metric recovery native count differs')
    def evidence_files(output):
        output=Path(output)
        mapping={'stage_events':'eds_eval/stage_events.jsonl','episode_compute':'eds_eval/episode_compute.jsonl',
            'episode_metadata':'eds_eval/episode_metadata.jsonl','safety_events':'eds_eval/safety_events.jsonl',
            'metrics':'eds_eval/eds_metrics.jsonl','resolved_config':'.hydra/config.yaml','results':'results.txt'}
        result={}
        for key,name in mapping.items():
            item=output/name
            if key in {'safety_events','metrics'}:
                w.require(not item.is_symlink() and (item.is_file() or not item.exists()),'N25 optional evidence unsafe')
                if key=='metrics':w.require(not item.exists(),'N25 absent metrics changed during classification')
                result[key]={'path':str(item.resolve()),'present':item.is_file(),'sha256':w.sha(item) if item.is_file() else None}
            else:result[key]=c.ref(item)
        return result
    fn=original.diagnose
    private=types.FunctionType(fn.__code__,{**fn.__globals__,'evidence_files':evidence_files},fn.__name__,fn.__defaults__,fn.__closure__)
    private.__kwdefaults__=fn.__kwdefaults__
    return private(final,row,profile,runtime,r,native_report=report)

def create_eligibility(plan_path,plan,row,final,profile,runtime,events,root,r):
    w.require(row in plan['episodes'] and row['iteration']==c.COHORT,'N25 recovery primary identity differs')
    w.require(check_cell_history(events,row,final['attempt_id'],r)==final,'N25 primary terminal journal differs')
    terminal_binding(final,row,plan,c.ref(plan_path),r)
    output=Path(final['output_dir']);terminal=c.ref(output/'attempt-result.json')
    w.require(w.read_ref(terminal)==final and final.get('n23_worker_receipt')==c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'N25 primary terminal/metered audit differs')
    report=c.read_worker_report(output,r)
    w.require(type(final.get('guided_chunks')) is int,'N25 terminal guided count missing')
    native.from_output(row['profile'],output,report,final['guided_chunks'])
    diagnostic=diagnose(final,row,profile,runtime,r,report)
    return {'schema':'n25-typed-timeout-eligibility-v1','cohort_id':c.COHORT,'primary_attempt_id':final['attempt_id'],
        'episode_key':row['episode_key'],'scientific_row':row,'plan':c.ref(plan_path),'source_commit':plan['source_commit'],
        'protocol':c.ref(c.PROTOCOL),'timeout_observability':c.ref(c.OBSERVABILITY),'terminal':terminal,
        'native_receipt':c.ref(output/'eds_eval/in-worker-audit-receipt.json'),
        'native_report':c.ref(output/'eds_eval/decision-evidence-audit.json'),'process':c.ref(output/'process.json'),
        'evidence_files':diagnostic['evidence_files'],'diagnostic':diagnostic,
        'evidence_packaging_reader':c.ref(__file__),
        'evidence_packaging_mode':('n25_absent_zero_guided_private_reader' if not (output/'eds_eval/eds_metrics.jsonl').exists() else 'unchanged_original_reader'),
        'primary_outcome_valid':False,'unknown_token_calls':1,'retry_budget_bucket':'recovery','same_cell_max_recoveries':1}


def verify_eligibility(reference,plan,row,events,root,r):
    record=w.read_ref(reference)
    w.require(record.get('schema')=='n25-typed-timeout-eligibility-v1' and record.get('cohort_id')==c.COHORT
        and record.get('episode_key')==row['episode_key'] and record.get('scientific_row')==row
        and record.get('source_commit')==plan['source_commit'] and w.read_ref(record['plan'])==plan,
        'N25 eligibility plan/source differs')
    final=check_cell_history(events,row,record['primary_attempt_id'],r)
    manifest=r['read_json'](plan['profiles_path'])
    for arm,profile in plan['candidate_profiles'].items():
        manifest['profiles'][arm]=r['expand_candidate'](arm,w.read_ref(profile),manifest['profiles']['Q0'])
    runtime=w.read_ref({'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']})
    rebuilt=create_eligibility(record['plan']['path'],plan,row,final,manifest['profiles'][row['profile']],runtime,events,root,r)
    w.require(record==rebuilt,'N25 eligibility changed or widened')
    return record


def check_retry(events,row,r):
    reference=row['n25_recovery_eligibility'];record=w.read_ref(reference);plan=w.read_ref(record['plan'])
    primary=c.primary_row(plan,row)
    w.require(row.get('retry_of')==record['primary_attempt_id'] and row['budget_bucket']=='recovery','N25 retry lineage/bucket differs')
    verify_eligibility(reference,plan,primary,events,Path(plan['worktree']),r)
