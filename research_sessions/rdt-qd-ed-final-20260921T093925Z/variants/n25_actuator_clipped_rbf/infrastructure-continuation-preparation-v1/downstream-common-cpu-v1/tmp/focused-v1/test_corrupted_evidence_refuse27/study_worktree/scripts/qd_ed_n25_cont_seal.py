#!/usr/bin/env python3
"""Root-only future metadata seal; CPU preparation never invokes main on real inputs."""
import argparse
import json
import subprocess
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n25_cont_evidence as e


def build(input_record,old_root,*,cleanup=e.process_cleanup):
    e.require(input_record['schema']=='n25-continuation-sealing-input-v1' and input_record['root_authorized'] is True,
        'explicit root metadata input review required')
    r=e.Reader(input_record['files']);refs=input_record['references']
    for k,expected in e.FROZEN.items():e.require(refs[k]['sha256']==expected,'frozen parent reference differs: '+k)
    review=r.json(refs['review']);result=r.json(refs['result']);plan=r.json(refs['plan']);source=r.json(refs['source'])
    e.require(review['schema']=='n25-root-terminal-review-v1' and review['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
        and review['cohort_disposition']=='INVALID_OR_INTERRUPTED' and review['source_files_verified']==257
        and review['accepted_cells']==18 and review['counts']==e.EXPECTED_COUNTS
        and review['all_attempts']==19 and review['all_attempt_gpu_process_seconds']==e.OLD_SECONDS,'root terminal attestation differs')
    for k in ('result','plan','source'):e.require(e.same_ref(review[k],refs[k]),'root reference binding differs')
    e.require(source['commit']==e.BASE and len(source['files'])==257 and source['sha256']==e.canonical(source['files']), 'old source manifest closure')
    old_root=Path(old_root).resolve()
    e.require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=old_root,text=True).strip()==e.BASE,'sealing requires intact old HEAD')
    for q in source['files']:
        p=old_root/q['path'];e.require(not p.is_symlink() and p.resolve().is_relative_to(old_root) and e.sha(p)==q['sha256'],'old source byte drift')
    e.require(plan['source_commit']==e.BASE and plan['code_files']==source['files'] and Path(plan['worktree']).resolve()==old_root,'original plan/source root differs')
    rows=plan['episodes'];e.require(len(rows)==40 and [(x['task_id'],x['profile']) for x in rows]==[(t,a) for t in range(10) for a in e.ARMS]
        and all(x['iteration']==e.OLD and x['split']==x['seed_block']=='dev' and x['timeout_seconds']==1800 for x in rows),'old matrix changed')
    runtime={'path':plan['runtime_manifest_path'],'sha256':plan['runtime_manifest_sha256']}
    runtime_data=r.json(runtime)  # JSON only: never follows runtime.files/weights.
    e.require(Path(runtime_data['worktree']).resolve()==old_root and runtime_data['gpu_mapping']['physical_gpu']==7
        and runtime_data['gpu_mapping']['uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187','old runtime identity')
    e.require(result['schema']=='n25-dev-cohort-result-v1' and result['decision']=='INVALID_OR_INTERRUPTED'
        and result['cohort_id']==e.OLD and result['source_commit']==e.BASE and result['audited_cells']==18
        and result['planned']==40 and result['dispatched']==19 and result['counts']==e.EXPECTED_COUNTS
        and result['dev_gate_promoted'] is False and result['controller_evidence']['consistent'] is True,'old INVALID result differs')
    e.require(e.same_ref(result['plan'],refs['plan']) and e.same_ref(result['ledger_snapshot'],review['ledger']),'old result ledger/plan differs')
    sr={k:result['terminal_status'][k] for k in ('path','sha256')};status=r.json(sr)
    e.require(status==result['terminal_status']['content'] and status['status']=='failed'
        and status['completed_keys']==[x['episode_key'] for x in rows[:18]],'old status differs')
    ledger=r.json(result['ledger_snapshot']);gg=e.groups(ledger)
    e.require(len(gg)==19 and list(gg)==[x['attempt_id'] for x in result['attempts']], 'old attempt order differs')
    all_attempts=[]
    for n,(aid,g) in enumerate(gg.items()):
        e.require([q['event'] for q in g]==['reserved','dispatched','valid'] and all(q.get('retry_of') is None for q in g),'old attempt chronology/recovery differs')
        final=g[-1];e.terminal_binding(final,rows[n],plan,refs['plan'])
        e.require(all(q['identity']==final['identity'] and q['attempt_id']==aid for q in g),'old event identity differs')
        item={'attempt_id':aid,'episode_key':rows[n]['episode_key'],'profile':rows[n]['profile'],'terminal':final}
        e.require(item==result['attempts'][n],'old result attempt differs from ledger');all_attempts.append(item)
    e.require(sum(v['terminal']['gpu_process_wall_seconds'] for v in all_attempts)==e.OLD_SECONDS,'old all-attempt wall differs')
    accepted=[];processes=[];native={a:{} for a in e.ARMS};aux={a:{} for a in e.ARMS}
    for n,cell in enumerate(result['accepted_cells']):
        rec=e.accepted_metadata(cell,all_attempts[n]['terminal'],rows[n],plan,refs['plan'],source,runtime,r)
        accepted.append({'logical_index':n,**rec});processes.append(rec['process'])
        for dest,key in ((native,'native'),(aux,'auxiliary')):
            for k,v in rec[key].items():dest[rows[n]['profile']][k]=dest[rows[n]['profile']].get(k,0)+v
    e.require(len(accepted)==18 and native==result['native'] and aux==result['auxiliary'],'old native totals/root attestation mismatch')
    failed=all_attempts[-1]['terminal'];e.require(failed['attempt_id']==e.FAILED,'wrong exceptional attempt')
    out=Path(failed['output_dir']);e.require(out.name==e.FAILED,'failed output identity')
    failed_terminal=r.json(e.ref_from_inventory(r,out/'attempt-result.json'));e.require(failed_terminal==failed,'failed terminal file differs')
    process=r.json(e.ref_from_inventory(r,out/'process.json'));e.require(process['attempt_id']==e.FAILED,'failed process binding')
    processes.append({k:process[k] for k in ('pid','proc_start_ticks','boot_id')})
    context=r.json(e.ref_from_inventory(r,out/'n23-worker-context.json'))
    e.require(context['source']==source and context['plan']==refs['plan'] and context['runtime']==runtime
        and context['attempt_id']==e.FAILED and context['profile']=='N23','failed context/source binding')
    absent=[e.absence(out/'eds_eval'/n) for n in ('in-worker-audit-receipt.json','decision-evidence-audit.json')]
    present=[e.ref_from_inventory(r,out/n) for n in ('results.txt','eds_eval/episode_compute.jsonl')]
    for q in present:r.read_bytes(q)  # presence and immutable hash, never acceptance.
    signature=e.failed_signature(failed,r.json(refs['stage_public']))
    controller=r.json(refs['controller']);e.require(controller['schema']=='n25-root-controller-process-v1'
        and e.same_ref(controller['plan'],refs['plan']),'original supervisor identity')
    processes.append({'pid':controller['controller_pid'],'proc_start_ticks':controller['controller_start_ticks'],'boot_id':controller['boot_id']})
    final_review=r.json(plan['n25_cohort']['final_review']);authority=r.json(plan['n25_cohort']['authority'])
    e.require(final_review['source']==source and final_review['runtime']==runtime and final_review['disposition']=='accepted'
        and authority['source']==source and authority['runtime']==runtime and authority['local_gpu_hours']==22.,'old reviewed source/authority differs')
    proof=r.json(final_review['backend_proof'])
    e.require(proof['schema']=='n25-metered-tensor-proof-v1' and proof['accepted'] is True and proof['source']==source
        and proof['runtime']==runtime,'historical backend source proof differs')
    # Hash proof closure only. It is historical root-reviewed evidence, not a new run.
    for k in ('plan','report','process','terminal'):r.json(proof[k])
    cleanup_record=cleanup(processes)
    return {'schema':'n25-continuation-metadata-seal-v1','original_disposition':'INVALID_OR_INTERRUPTED',
        'original_source':source,'original_plan':refs['plan'],'runtime':runtime,'root_terminal_review':refs['review'],
        'original_result':refs['result'],'old_ledger':result['ledger_snapshot'],'old_status':sr,'old_authority':plan['n25_cohort']['authority'],
        'historical_backend_proof':final_review['backend_proof'],'metadata_files':list(r.records.values()),
        'all_old_attempts':all_attempts,'original_rows':rows,'accepted_prefix':accepted,'native':native,'auxiliary':aux,
        'counts':e.EXPECTED_COUNTS,'old_gpu_seconds':e.OLD_SECONDS,'old_attempts':19,'old_recoveries':0,
        'failed_attempt':e.FAILED,'failed_signature':signature,'failed_audits_absent':absent,'failed_present_only':present,
        'processes':processes,'cleanup':cleanup_record,'reader':e.ref(__file__),
        'metadata_reader':e.ref(Path(__file__).with_name('qd_ed_n25_cont_evidence.py')),
        'reliance':'Root terminal review + original metered receipts/evidence-index digests; no tensor files opened or native gates recomputed.',
        'historical_unknowns':e.UNKNOWN,'metadata_bytes':r.bytes,'validation_authorized':False,'formal_authorized':False}


def verify(seal,*,check_cleanup=False,cleanup=e.process_cleanup):
    e.require(seal['schema']=='n25-continuation-metadata-seal-v1' and seal['historical_unknowns']==e.UNKNOWN
        and seal['original_disposition']=='INVALID_OR_INTERRUPTED' and seal['failed_attempt']==e.FAILED
        and seal['old_attempts']==19 and seal['old_recoveries']==0 and seal['old_gpu_seconds']==e.OLD_SECONDS
        and seal['counts']==e.EXPECTED_COUNTS and [x['logical_index'] for x in seal['accepted_prefix']]==list(range(18)), 'seal limits/Unknown changed')
    r=e.Reader(seal['metadata_files'])
    for q in seal['metadata_files']:r.read_bytes(q)
    e.verify_absences(seal['failed_audits_absent'])
    if check_cleanup:cleanup(seal['processes'])
    return seal


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--old-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=json.loads(a.input.read_text());seal=build(data,a.old_root);seal['sealing_input']=e.ref(a.input)
    e.require(not a.output.exists(),'seal is immutable');a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(seal,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps({'path':str(a.output.resolve()),'sha256':e.sha(a.output),'metadata_only':True,'gpu_authorized':False}))
if __name__=='__main__':main()
