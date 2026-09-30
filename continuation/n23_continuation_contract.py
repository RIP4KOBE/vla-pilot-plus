"""Separately authorized external continuation; the owning 214 files are immutable."""
from __future__ import annotations
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

HERE=Path(__file__).resolve().parents[2]
ROOT=HERE.parents[1]/'study_worktree'
EXTERNAL=Path(__file__).resolve().parents[1]
SOURCE='51104470983cdbafd08feb87f2f39b7553779405'
PLAN=HERE/'plan.frozen.v2.gpu7.json'
PLAN_SHA='acd2b2c639f7756cdc353b6a7eea8c93a4d735a8ce6ee25838d9502c938d07f0'
EXCEPTION=HERE/'legacy-metric-continuation-engineering-exception-v1.md'
EXCEPTION_SHA='ee6750ae41cad78d9e4cbf1fa471267c53cd8fee690d526f1029dc545c56f606'
FAILURE=HERE/'legacy-metric-reader-failure-review-v1.json'
FAILURE_SHA='72621d9a0ae1104da46b769fee0edf5b782197e34b5b301b61b51c7f8912127e'
WRITER=HERE/'summarize_cohort_cpu_v2.py'
WRITER_SHA='d9918d9f52e4bb37c9f71e7be09af880a7b6f4723ed9a68566bfda38b363224c'
REVIEW=HERE/'continuation-source-review-v1.json'
AUTHORITY=HERE/'continuation-adoption-v1/authority.json'
STATUS=HERE/'execution/supervisor-status-continuation-v1.json'
SEAL=HERE/'execution/continuation-launch-seal-v1.json'
RESULT=HERE/'result-continuation-v1.json'
SNAPSHOT=HERE/'dev-terminal-ledger-snapshot-continuation-v1.jsonl'
KEY='n23_legacy_metric_continuation_authority'
PREFIX_IDS=tuple('rdt-qd-ed-final-20260921T093925Z__n23v2_dev_t00_'+x+'_20260930__'+y
    for x,y in [('c0','c58546de418d'),('q0','b05b3fbad53f'),('n7','37d30d11e25a')])
FILES={'continuation/n23_n7_metrics_adapter.py','continuation/n23_continuation_contract.py',
    'continuation/n23_continuation_supervise.py','continuation/n23_continuation_report.py',
    'continuation/activation-v1.md','continuation/legacy-metric-continuation-engineering-exception-v1.md',
    'tests/test_n23_n7_metrics_adapter.py','tests/test_n23_continuation.py'}


def require(condition,message):
    if not condition:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}


def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def source_record(root=EXTERNAL):
    root=Path(root).resolve();commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    records=[]
    for relative in sorted(FILES):
        path=root/relative
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(root),'external source path unsafe')
        committed=subprocess.check_output(['git','show',commit+':'+relative],cwd=root)
        require(path.read_bytes()==committed,'external executable/source bytes uncommitted')
        records.append({'path':relative,'sha256':sha(path)})
    require(sha(WRITER)==WRITER_SHA,'imported original terminal writer changed')
    return {'root':str(root),'commit':commit,'files':records,'sha256':canonical(records),'imported_writer':ref(WRITER)}


def module_origins(root,modules=None):
    root=Path(root).resolve();modules=sys.modules if modules is None else modules
    records={}
    for name,module in list(modules.items()):
        if name in {'scripts','core'} or name.startswith(('scripts.','core.','qd_ed_')):
            filename=getattr(module,'__file__',None)
            if filename is not None:
                path=Path(filename).resolve()
                require(path.is_relative_to(root),'frozen owning import shadowed: '+name)
                records[name]=str(path)
            for location in getattr(module,'__path__',[]):
                require(Path(location).resolve().is_relative_to(root),'frozen owning namespace shadowed: '+name)
    return records


def load_owned(root=ROOT):
    root=Path(root).resolve();module_origins(root)
    # The executable's directory contains only external helpers. Scientific packages
    # must come from this explicit owning root, never the adjacent checkout.
    sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
    names={'r':'qd_ed_final_runner','c':'qd_ed_n23_v2_contract','w':'qd_ed_n23_worker',
        'sup':'qd_ed_n23_v2_supervise','recovery':'qd_ed_n23_v2_recovery'}
    values={k:importlib.import_module('scripts.'+name) for k,name in names.items()}
    importlib.import_module('core.eds_eval_metrics')
    values['queue']=values['sup'].queue
    module_origins(root)
    require(all(Path(values[k].ROOT).resolve()==root for k in ('r','c','w','sup')),'owning module ROOT differs')
    return SimpleNamespace(root=root,**values)


def load_writer(owned):
    require(sha(WRITER)==WRITER_SHA,'frozen imported report writer differs')
    spec=importlib.util.spec_from_file_location('n23_frozen_original_terminal_writer',WRITER)
    writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
    module_origins(owned.root)
    require(writer.r is owned.r and writer.c is owned.c and writer.w is owned.w and writer.sup is owned.sup,
        'terminal writer imported different owning modules')
    return writer


def owning_source(plan,owned):
    require(plan['source_commit']==SOURCE and len(plan['code_files'])==214,'original owning source/count differs')
    record={'commit':SOURCE,'files':plan['code_files'],'sha256':canonical(plan['code_files'])}
    owned.w.verify_source(owned.root,record)
    module_origins(owned.root)
    return record


def immutable_inputs(owned):
    require(sha(PLAN)==PLAN_SHA and sha(EXCEPTION)==EXCEPTION_SHA and sha(FAILURE)==FAILURE_SHA
        and sha(WRITER)==WRITER_SHA,'continuation immutable input differs')
    failure=owned.w.read_ref(ref(FAILURE))
    require(failure.get('schema')=='n23-dev-legacy-metric-reader-failure-v1'
        and failure['original_source_commit']==SOURCE and failure['original_plan']==ref(PLAN),
        'wrong named legacy-metric failure')
    # Bind all frozen refs; text logs are hashed only, never interpreted as authority.
    for key in ('original_failed_status','original_failed_result','original_dev_snapshot',
                'original_supervisor_log','source_serializer','source_checker'):
        require(ref(failure[key]['path'])==failure[key],'original failure evidence changed: '+key)
    old=owned.w.read_ref(failure['original_failed_status']);result=owned.w.read_ref(failure['original_failed_result'])
    require(old.get('status')=='failed' and len(old.get('completed_keys',[]))==2
        and len(old.get('attempts',[]))==3 and result.get('decision')=='INVALID_OR_INTERRUPTED'
        and result.get('audited_cells')==2 and result.get('dispatched')==3,
        'old failed disposition must remain unchanged')
    return failure


def acceptor(plan,manifest,owned):
    from n23_n7_metrics_adapter import native_counts
    def accept(plan,row,events):
        final=owned.c.accepted_cell(plan,row,events,owned.root,vars(owned.r))
        output=Path(final['output_dir']);report=owned.c.read_worker_report(output,vars(owned.r))
        counts,aux=native_counts(final,row,report,plan=plan,manifest=manifest,root=owned.root,
            r=vars(owned.r),w=owned.w,original=owned.sup)
        refs={k:ref(output/p) for k,p in (
            ('audit','eds_eval/decision-evidence-audit.json'),('worker_context','n23-worker-context.json'),
            ('worker_receipt','eds_eval/in-worker-audit-receipt.json'),('attempt_result','attempt-result.json'))}
        require(owned.w.read_ref(refs['attempt_result'])==final,'attempt result differs from private journal')
        return final,refs,counts,aux
    return accept


def prefix_gate(plan,failure,events,owned,accept,*,initial):
    local=[e for e in events if e.get('identity',{}).get('iteration')==owned.c.COHORT]
    groups=list(owned.r.event_groups(local).values())
    require(len(groups)>=3 and (not initial or len(groups)==3),'continuation requires exact three prior attempts at launch')
    require([g[0]['attempt_id'] for g in groups[:3]]==list(PREFIX_IDS),'named three-prefix attempt order differs')
    require([v['episode_key'] for v in failure['prefix']]==[v['episode_key'] for v in plan['episodes'][:3]],
        'failure review names different first cells')
    prefix_events=[e for e in local if e['attempt_id'] in PREFIX_IDS]
    require(owned.r.read_events(failure['original_dev_snapshot']['path'])==prefix_events,'original prefix journal snapshot differs')
    accepted=[]
    for row,prior,group in zip(plan['episodes'][:3],failure['prefix'],groups[:3]):
        require([e['event'] for e in group]==['reserved','dispatched','valid']
            and all(not e.get('retry_of') for e in group),'original prefix is not one valid primary per cell')
        final,refs,counts,aux=accept(plan,row,events)
        require(final==group[-1] and final['attempt_id']==prior['attempt_id'] and final['success'] is False
            and final['outcome_valid'] is True and prior['success'] is False and prior['outcome_valid'] is True
            and final['gpu_process_wall_seconds']==prior['gpu_process_wall_seconds'],
            'original valid prefix outcome/cost changed')
        for key,target in [('terminal','attempt_result'),('native_report','audit'),('native_receipt','worker_receipt')]:
            require(refs[target]==prior[key], 'original prefix evidence binding differs: '+key)
        require(ref(Path(final['output_dir'])/'eds_eval/eds_metrics.jsonl')==prior['metrics'],
            'original prefix metrics changed')
        accepted.append((final,refs,counts,aux))
    return accepted


def review_payload(plan,source,owning,owned):
    return {'schema':'n23-continuation-source-review-v1','decision':'PASS_PREPARATION',
        'exception':ref(EXCEPTION),'failure_review':ref(FAILURE),'plan':ref(PLAN),
        'external_source':source,'owning_source':owning,'runtime':ref(plan['runtime_manifest_path']),
        'backend_proof':plan['n23_cohort']['backend_proof'],'cohort_id':owned.c.COHORT,
        'prefix_attempt_ids':list(PREFIX_IDS),'pending_keys':[v['episode_key'] for v in plan['episodes'][3:]],
        'limits':owned.c.LIMITS,'validation_authorized':False,'formal_authorized':False}


def authority_payload(review,plan,owned):
    return {'schema':'n23-legacy-metric-continuation-authority-v1','source_review':review,
        'exception':ref(EXCEPTION),'failure_review':ref(FAILURE),'plan':ref(PLAN),
        'status_path':str(STATUS),'launch_seal_path':str(SEAL),'result_path':str(RESULT),
        'cohort_id':owned.c.COHORT,'initial_prefix_attempt_ids':list(PREFIX_IDS),
        'pending_keys':[v['episode_key'] for v in plan['episodes'][3:]],'limits':owned.c.LIMITS,
        'initial_launches':1,'scientific_source_unchanged':True,'backend_preflight_authorized':False,
        'validation_authorized':False,'formal_authorized':False,
        'authority_interpretation':'prospective bounded coordinator engineering exception under continuing autonomous user instruction',
        'user_message':'继续完成满足目标且无需我介入的autoresearch'}


def authorization(plan,owned,*,state=None):
    source=source_record();owning=owning_source(plan,owned)
    require(owned.w.read_ref(ref(REVIEW))==review_payload(plan,source,owning,owned),'external source review differs')
    authority=owned.w.read_ref(ref(AUTHORITY))
    require(authority==authority_payload(ref(REVIEW),plan,owned),'closed continuation authority differs')
    if state is not None:
        require(state.get(KEY)==ref(AUTHORITY),'continuation authority not adopted in private state')
    return ref(AUTHORITY)


def no_owned_worker(root,*,proc=Path('/proc')):
    root=Path(root).resolve()
    for item in proc.iterdir():
        if not item.name.isdigit():continue
        try:
            args=(item/'cmdline').read_bytes().split(b'\0');cwd=(item/'cwd').resolve(strict=True)
        except (FileNotFoundError,PermissionError,ProcessLookupError):continue
        tokens=[x.decode(errors='replace') for x in args]
        worker=any(Path(x).name in {'main.py','qd_ed_n23_worker.py'} for x in tokens)
        require(not (worker and (cwd==root or any(str(root) in x for x in tokens))),
            'an owning main/native-audit worker is still active')


def quiescent(plan,owned,state,events,resources):
    owned.c.full_capacity(state,events,resources,vars(owned.r))
    no_owned_worker(owned.root)
    devices=owned.queue.inventory()
    require(7 in devices and devices[7]['uuid']==owned.c.GPU7_UUID,'continuation GPU7 UUID differs')
    owned.queue.reservation_admission(devices[7]);owned.r.gpu_admission(physical_gpu=7,expected_uuid=owned.c.GPU7_UUID)


def check_boundary(plan,manifest,owned,*,initial):
    # Caller holds existing private runner/state locks; source and external docs
    # are checked again before every normal original-supervisor dispatch.
    require(sha(PLAN)==PLAN_SHA,'original plan changed')
    failure=immutable_inputs(owned)
    state=owned.r.read_state(owned.root/'research-state.yaml')
    authority=authorization(plan,owned,state=state)
    events=owned.r.read_events(owned.root/'data/attempt-ledger.jsonl')
    resources=owned.r.read_events(owned.root/'data/gpu-healthcheck-ledger.jsonl')
    accepted=prefix_gate(plan,failure,events,owned,acceptor(plan,manifest,owned),initial=initial)
    quiescent(plan,owned,state,events,resources)
    if initial:require(not STATUS.exists() and not SEAL.exists(),'one continuation launch already consumed')
    else:
        seal=owned.w.read_ref(ref(SEAL))
        require(seal.get('authority')==authority and seal.get('process')==owned.w.process_identity(),
            'continuation cannot resume under a different process')
    return authority,accepted
