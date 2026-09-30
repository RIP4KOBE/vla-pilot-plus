"""Read-only historical continuation bridge, independent of current owning HEAD."""
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n23_v2_contract as dev
from scripts import qd_ed_n23_historical_n7_metrics_adapter as adapter

RUN_DIR=dev.RUN_DIR
ADDENDUM=RUN_DIR/'validation-continuation-evidence-addendum-v1.md'
ADDENDUM_SHA='536c4508cdf21fdf59a86acdbd83ab2f8fc45b99c9e14e9b1a4bdf35329d484c'
EXTERNAL_ROOT=RUN_DIR/'continuation_implementation'
EXTERNAL_COMMIT='dd27e77edd5e8d67aba998c1d0441c2b8e48713c'
MANIFEST=RUN_DIR/'continuation-source-manifest-v1.json'
MANIFEST_SHA='ced23d5abf8949621ccb5cdbccbb557f75d19e116b85b9deb8461a6a043ac4e4'
SOURCE_REVIEW=RUN_DIR/'continuation-source-review-v1.json'
SOURCE_REVIEW_SHA='88144f06aab2d4ac106f8010b49f469ef3a155c910615c96d0d2400c8ae715e3'
AUTHORITY=RUN_DIR/'continuation-adoption-v1/authority.json'
AUTHORITY_SHA='aadb38d59cc48d95793030dd34f4fe1dc01db8d64e121907a8212b70b85cdb6c'
ROOT_REVIEW=RUN_DIR/'root-continuation-review-v1.json'
ROOT_REVIEW_SHA='520cec3e63fe2c0ff28265f4a0263c32562b6fc6696320f22dc285a31d81500d'
FAILURE=RUN_DIR/'legacy-metric-reader-failure-review-v1.json'
FAILURE_SHA='72621d9a0ae1104da46b769fee0edf5b782197e34b5b301b61b51c7f8912127e'
EXCEPTION=RUN_DIR/'legacy-metric-continuation-engineering-exception-v1.md'
EXCEPTION_SHA='ee6750ae41cad78d9e4cbf1fa471267c53cd8fee690d526f1029dc545c56f606'
ORIGINAL_WRITER=RUN_DIR/'summarize_cohort_cpu_v2.py'
ORIGINAL_WRITER_SHA='d9918d9f52e4bb37c9f71e7be09af880a7b6f4723ed9a68566bfda38b363224c'
ADAPTER_SHA='fc98d401fb6095fb0a4311fa2de5e04d9940b6f5406e96078ba3b350168821c5'
STATUS=RUN_DIR/'execution/supervisor-status-continuation-v1.json'
SEAL=RUN_DIR/'execution/continuation-launch-seal-v1.json'
SNAPSHOT=RUN_DIR/'dev-terminal-ledger-snapshot-continuation-v1.jsonl'
FILES={'continuation/n23_n7_metrics_adapter.py','continuation/n23_continuation_contract.py',
    'continuation/n23_continuation_supervise.py','continuation/n23_continuation_report.py',
    'continuation/activation-v1.md','continuation/legacy-metric-continuation-engineering-exception-v1.md',
    'tests/test_n23_n7_metrics_adapter.py','tests/test_n23_continuation.py'}
PREFIX_IDS=tuple('rdt-qd-ed-final-20260921T093925Z__n23v2_dev_t00_'+a+'_20260930__'+b
    for a,b in [('c0','c58546de418d'),('q0','b05b3fbad53f'),('n7','37d30d11e25a')])
ref=dev.ref


def addendum():
    w.require(w.sha(ADDENDUM)==ADDENDUM_SHA,'validation continuation addendum changed')
    return ref(ADDENDUM)


def external_source():
    for path,digest in ((MANIFEST,MANIFEST_SHA),(SOURCE_REVIEW,SOURCE_REVIEW_SHA),(AUTHORITY,AUTHORITY_SHA),
        (ROOT_REVIEW,ROOT_REVIEW_SHA),(FAILURE,FAILURE_SHA),(EXCEPTION,EXCEPTION_SHA),(ORIGINAL_WRITER,ORIGINAL_WRITER_SHA)):
        w.require(w.sha(path)==digest,'historical continuation frozen authority/source reference differs')
    source=w.read_ref(ref(MANIFEST));records=source.get('files',[])
    w.require(set(source)=={'root','commit','files','sha256','imported_writer'}
        and Path(source['root']).resolve()==EXTERNAL_ROOT.resolve() and source['commit']==EXTERNAL_COMMIT
        and [v['path'] for v in records]==sorted(FILES) and source['sha256']==w.canonical_sha(records)
        and source['imported_writer']==ref(ORIGINAL_WRITER),'historical external source manifest differs')
    for item in records:
        path=EXTERNAL_ROOT/item['path']
        w.require(set(item)=={'path','sha256'} and path.is_file() and not path.is_symlink()
            and path.resolve().is_relative_to(EXTERNAL_ROOT.resolve()) and w.sha(path)==item['sha256'],
            'historical external source byte/link drift')
        before=subprocess.check_output(['git','show',EXTERNAL_COMMIT+':'+item['path']],cwd=EXTERNAL_ROOT)
        w.require(path.read_bytes()==before,'historical external committed byte mismatch')
    w.require(w.sha(adapter.__file__)==ADAPTER_SHA
        and w.sha(EXTERNAL_ROOT/'continuation/n23_n7_metrics_adapter.py')==ADAPTER_SHA,
        'historical N7 adapter is not exact reviewed copy')
    return source


def provenance(parent,review,status,result):
    """Check historical refs without invoking a live HEAD, budget or authority gate."""
    from scripts import qd_ed_n23_validation_contract as c
    addendum();source=external_source();failure=w.read_ref(ref(FAILURE))
    historical={'commit':parent['source_commit'],'files':parent['code_files'],'sha256':w.canonical_sha(parent['code_files'])}
    expected_review={'schema':'n23-continuation-source-review-v1','decision':'PASS_PREPARATION',
        'exception':ref(EXCEPTION),'failure_review':ref(FAILURE),'plan':ref(c.DEV_PLAN),
        'external_source':source,'owning_source':historical,
        'runtime':ref(parent['runtime_manifest_path']),
        'backend_proof':parent['n23_cohort']['backend_proof'],'cohort_id':dev.COHORT,
        'prefix_attempt_ids':list(PREFIX_IDS),'pending_keys':[v['episode_key'] for v in parent['episodes'][3:]],
        'limits':dev.LIMITS,'validation_authorized':False,'formal_authorized':False}
    w.require(w.read_ref(ref(SOURCE_REVIEW))==expected_review,'historical continuation source review content differs')
    authority=w.read_ref(ref(AUTHORITY))
    w.require(authority=={'schema':'n23-legacy-metric-continuation-authority-v1','source_review':ref(SOURCE_REVIEW),
        'exception':ref(EXCEPTION),'failure_review':ref(FAILURE),'plan':ref(c.DEV_PLAN),
        'status_path':str(STATUS),'launch_seal_path':str(SEAL),'result_path':str(c.DEV_RESULT),
        'cohort_id':dev.COHORT,'initial_prefix_attempt_ids':list(PREFIX_IDS),
        'pending_keys':[v['episode_key'] for v in parent['episodes'][3:]],'limits':dev.LIMITS,
        'initial_launches':1,'scientific_source_unchanged':True,'backend_preflight_authorized':False,
        'validation_authorized':False,'formal_authorized':False,
        'authority_interpretation':'prospective bounded coordinator engineering exception under continuing autonomous user instruction',
        'user_message':'继续完成满足目标且无需我介入的autoresearch'},'historical continuation finite authority differs')
    seal=w.read_ref(ref(SEAL));pid=seal.get('process',{})
    w.require(seal=={'schema':'n23-continuation-launch-seal-v1','authority':ref(AUTHORITY),
        'process':pid,'prefix_attempt_ids':list(PREFIX_IDS),'pending_keys':[v['episode_key'] for v in parent['episodes'][3:]]}
        and set(pid)=={'pid','proc_start_ticks','boot_id'} and type(pid['pid']) is int and pid['pid']>0
        and isinstance(pid['proc_start_ticks'],str) and pid['proc_start_ticks'].isdigit()
        and isinstance(pid['boot_id'],str) and bool(pid['boot_id']),'historical continuation launch/process witness differs')
    expected_provenance={'authority':ref(AUTHORITY),'launch_seal':ref(SEAL),'original_failed_review':ref(FAILURE),
        'original_source_commit':c.DEV_COMMIT,'original_plan':ref(c.DEV_PLAN),
        'external_source':source,'imported_writer':ref(ORIGINAL_WRITER)}
    w.require(status.get('continuation')==result.get('continuation')==expected_provenance
        and c.same_ref(review.get('dev_status'),ref(STATUS)) and result.get('ledger_snapshot')==ref(SNAPSHOT)
        and result.get('original_v2_disposition')=='INVALID_OR_INTERRUPTED'
        and result.get('original_v2_record_preserved') is True
        and result.get('original_failed_result')==failure['original_failed_result'],
        'validation does not bind actual continuation/original failed record')
    w.require(failure.get('schema')=='n23-dev-legacy-metric-reader-failure-v1'
        and failure['original_source_commit']==c.DEV_COMMIT and failure['original_plan']==ref(c.DEV_PLAN),
        'wrong named original continuation defect')
    for key in ('original_failed_status','original_failed_result','original_dev_snapshot',
                'original_supervisor_log','source_serializer','source_checker'):
        w.require(ref(failure[key]['path'])==failure[key],'original failed evidence drift: '+key)
    old=w.read_ref(failure['original_failed_status']);old_result=w.read_ref(failure['original_failed_result'])
    w.require(old.get('status')=='failed' and len(old.get('completed_keys',[]))==2 and len(old.get('attempts',[]))==3
        and old_result.get('decision')=='INVALID_OR_INTERRUPTED' and old_result.get('audited_cells')==2
        and old_result.get('dispatched')==3,'old failed result was relabelled')
    return failure


def prefix(parent,failure,events,result,r):
    groups=list(r['event_groups'](events).values());accepted=result['accepted_cells']
    w.require(len(groups)>=3 and [v[0]['attempt_id'] for v in groups[:3]]==list(PREFIX_IDS)
        and [v['episode_key'] for v in failure['prefix']]==[v['episode_key'] for v in parent['episodes'][:3]],
        'historical original three-cell prefix identity differs')
    original=[e for e in events if e['attempt_id'] in PREFIX_IDS]
    w.require(r['read_events'](failure['original_dev_snapshot']['path'])==original,'original prefix ledger changed')
    for row,prior,group,entry in zip(parent['episodes'][:3],failure['prefix'],groups[:3],accepted[:3]):
        final=group[-1];output=Path(final['output_dir'])
        w.require([e['event'] for e in group]==['reserved','dispatched','valid'] and all(not e.get('retry_of') for e in group)
            and final['attempt_id']==prior['attempt_id']==entry['attempt_id'] and final['episode_key']==row['episode_key']
            and final.get('outcome_valid') is True and final['success'] is prior['success'] is entry['success'] is False
            and final['gpu_process_wall_seconds']==prior['gpu_process_wall_seconds'],
            'original three primary failures/outcomes/costs changed')
        for key,target in [('terminal','attempt_result'),('native_report','audit'),('native_receipt','worker_receipt')]:
            w.require(entry[target]==prior[key] and ref(prior[key]['path'])==prior[key],'original prefix evidence changed')
        w.require(ref(output/'eds_eval/eds_metrics.jsonl')==prior['metrics'],'original prefix metrics drift')


def native_counts(final,row,report,*,parent,root,r,manifest):
    from scripts import qd_ed_n23_v2_supervise as supervision
    # The live external controller is deliberately not imported: its HEAD/worker
    # gates belong to active Dev execution, not a later evaluation-only commit.
    return adapter.native_counts(final,row,report,plan=parent,manifest=manifest,
        root=Path(parent['worktree']),r=r,w=w,original=supervision)
