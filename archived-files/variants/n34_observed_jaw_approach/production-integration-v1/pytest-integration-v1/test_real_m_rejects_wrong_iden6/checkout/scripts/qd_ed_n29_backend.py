"""Exactly one metered tensor resource; all release authority is external."""
import argparse,json,math,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n29_contract as c
KIND='n29_tensor_arithmetic_v1'
LIMITS={'resource_processes':1,'episode_attempts':0,'model_calls':0,'api_calls':0,'simulation_steps':0,
        'timeout_seconds':80,'cleanup_seconds':40,'physical_gpu':7,'health_gpu_hours_bucket':'recovery'}
REVIEW=c.RUN_DIR/'arithmetic-preflight-source-review-v1.json'
AUTHORITY=c.RUN_DIR/'arithmetic-preflight-adoption-v1/authority.json'
PLAN=c.RUN_DIR/'arithmetic-preflight/plan.frozen.v1.json'
RELEASE=c.RUN_DIR/'arithmetic-preflight-release-v1.json'


def source_review(source,runtime,root):
    from scripts import qd_ed_n29_bridge as bridge
    c.require_protocols(root);bridge.verify(c.ref(c.BRIDGE),source,runtime,root)
    expected={'schema':'n29-arithmetic-source-review-v1','accepted':True,'source':source,'runtime':runtime,
        'source_bridge':c.ref(c.BRIDGE),'phase_b_protocol':c.ref(c.PROTOCOL),
        'arithmetic_protocol':c.ref(c.ARITHMETIC_PROTOCOL),'predecessor':c.predecessor(),
        'budget_reuse':c.budget_reuse(),
        'limits':LIMITS,'gpu_release':False}
    w.require(w.read_ref(c.ref(REVIEW))==expected,'N29 arithmetic source review missing/different')
    return c.ref(REVIEW)


def authority(source,runtime,root,state=None):
    record=w.read_ref(c.ref(AUTHORITY))
    w.require(record=={'schema':'n29-arithmetic-resource-authority-v1','source':source,'runtime':runtime,
        'source_review':source_review(source,runtime,root),'budget_reuse':c.budget_reuse(),
        'limits':LIMITS,'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'automatic_retry':False,'dev_authorized':False,'validation_authorized':False,'formal_authorized':False},
        'N29 one-resource authority differs')
    if state is not None:w.require(state.get('n29_arithmetic_authority')==c.ref(AUTHORITY),'N29 resource authority not adopted')
    return c.ref(AUTHORITY)


def build_plan(source,runtime,root,resource_id,*,authority_ref=None):
    w.require(resource_id.endswith('__n29_tensor_arithmetic_v1'),'N29 fixed resource identity differs')
    return {'schema':'n29-tensor-resource-plan-v1','frozen':False,'resource_id':resource_id,'kind':KIND,
        'worktree':str(Path(root).resolve()),'source':source,'runtime':runtime,'limits':LIMITS,
        'authority':authority_ref,'output_dir':str((c.RUN_DIR/'arithmetic-preflight/worker').resolve())}


def validate_plan(plan,root,*,check_authority=True):
    expected=build_plan(plan['source'],plan['runtime'],root,plan['resource_id'],authority_ref=plan['authority']);expected['frozen']=True
    w.require(plan==expected and plan['runtime']==c.runtime_ref(),'N29 tensor resource plan differs')
    w.verify_source(root,plan['source'])
    if check_authority:w.require(plan['authority']==authority(plan['source'],plan['runtime'],root),'N29 resource authority differs')


def admission(state,events,resources,r,source,runtime,root,*,reservation_events=()):
    c.require_budget_state(state,r);authority(source,runtime,root,state)
    w.require(bool(reservation_events) and reservation_events[-1].get('event')=='gpu_hour_reservations_changed'
        and reservation_events[-1].get('gpu_hour_reservations')==c.BASE_CAPS['protected_gpu_hours'],
        'N29 authoritative protected hour reservations missing')
    c.validate_runtime(w.read_ref(runtime),root,r)
    w.require(not any(e.get('kind')==KIND or str(e.get('resource_id','')).endswith('__n29_tensor_arithmetic_v1') for e in resources),
        'N29 arithmetic opportunity already consumed, no retry')
    w.require(not any(e.get('identity',{}).get('iteration')==c.COHORT for e in events),'N29 Dev already reserved')
    snap=r['budget_snapshot'](events,resources);caps=c.budget_authority()['caps']
    w.require(snap['running']==snap['gpu_healthcheck_inflight']==0
        and all(v[-1]['event'] in r['TERMINAL'] for v in r['event_groups'](events).values()),'N29 unsettled episode/resource')
    w.require(state['budget']['dispatched']==snap['dispatched']
        and abs(state['budget']['gpu_hours_consumed']-snap['gpu_hours_consumed'])<1e-8,'N29 state/ledger cost mismatch')
    protected=sum(max(0,h-snap['gpu_hours_by_bucket'][b]) for b,h in caps['protected_gpu_hours'].items())
    protected_attempts=sum(max(0,caps['buckets'][b]-snap['by_bucket'][b]) for b in ('validation','formal'))
    w.require(all(caps['buckets'][b]-snap['by_bucket'][b]>=n for b,n in {'baseline':10,'development':30}.items())
        and snap['dispatched']+40+protected_attempts<=caps['attempts']
        and snap['gpu_hours_consumed']+120/3600+protected<=caps['gpu_hours'],'N29 no finite unprotected capacity')
    return snap


def validate_report(report,plan,process):
    from scripts.qd_ed_audit_backend import canonical_cuda_uuid
    from scripts.qd_ed_n29_reference import CASES,LAYOUTS
    w.require(report.get('schema')=='n29-tensor-arithmetic-report-v1' and report.get('accepted') is True
        and report.get('resource_id')==plan['resource_id'] and report.get('source')==plan['source']
        and report.get('runtime')==plan['runtime'] and report.get('plan')==c.ref(PLAN)
        and report.get('process')=={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
        and report.get('process_unchanged') is True and report.get('errors')==[]
        and all(type(report.get(k)) is int and report[k]==0 for k in ('model_calls','api_calls','simulation_steps','episodes')),
        'N29 arithmetic report identity/outcome differs')
    backend=report.get('backend',{});diag=backend.get('identity_diagnostic',{})
    w.require(backend.get('kind')=='cuda' and backend.get('logical_device')=='cuda:0'
        and backend.get('physical_gpu')==7 and backend.get('physical_uuid')==c.GPU7_UUID
        and canonical_cuda_uuid(backend.get('actual_uuid'))==c.GPU7_UUID
        and backend.get('actual_uuid_type') in {'builtins.str','torch._C._CUuuid'}
        and diag.get('status')=='matched' and diag.get('visible_device_count')==1 and diag.get('current_device')==0
        and diag.get('cuda_visible_devices') in {'7',c.GPU7_UUID}
        and {'torch.float32','torch.bfloat16'}<=set(backend.get('dtype_coverage',[])), 'N29 actual native CUDA identity missing')
    w.require((backend['actual_uuid_type']=='builtins.str' and backend.get('actual_uuid_bytes_hex') is None)
        or (backend['actual_uuid_type']=='torch._C._CUuuid' and backend.get('actual_uuid_bytes_hex')==c.GPU7_UUID[4:].replace('-','')),
        'N29 native UUID bytes differ')
    cases=report.get('cases',[])
    w.require([(x.get('dtype'),x.get('case'),x.get('layout')) for x in cases]==[(d,k,l) for d in ('torch.float32','torch.bfloat16') for k in CASES for l in LAYOUTS],
        'N29 fixed-case coverage differs')
    for row in cases:
        w.require(row.get('accepted') is True and row.get('candidate_rows')==16
            and row.get('comparison')=='native contiguous uint8; zero tolerance'
            and row.get('custom_boundary_derivative_verified') is True
            and row.get('production_projection_calls')==16 and row.get('production_origin_reads')==16
            and row.get('invalid_inputs_rejected')==['nonfinite','wrong_horizon'] and type(row.get('zero_gradient')) is bool
            and row.get('input_stride')==list(LAYOUTS[row['layout']][0]) and row.get('synthetic_storage_offset')==LAYOUTS[row['layout']][1]
            and row.get('population_trust_verified') is True and row.get('helper_semantic_case_verified') is True
            and row.get('feasible_ray_verified') is True and row.get('tail_mask_rng_verified') is True and row.get('rng_scope')=='cpu_and_assigned_cuda'
            and row.get('parent_object_selection_verified') is True and row.get('parent_input_binding_verified') is True
            and row.get('sample_only_negative_controls')==[None,'epsilon','v_prediction']
            and row.get('wrong_source_rejected') is True and row.get('signed_zero_rejected') is True and row.get('boundary_observer_binding_verified') is True
            and row.get('interior_original_parity')==(True if row['case']=='strict_interior' else None)
            and row.get('negative_controls_rejected')==['input_xyz','projected_xyz','gradient_before','gradient_after','update_operand','parent_offspring_before','parent_offspring_after','scaled_operand','beta','radius','operand_norms'],
            'N29 strict arithmetic/negative coverage missing')
    w.require(type(report.get('worker_wall_seconds')) in (int,float) and math.isfinite(report['worker_wall_seconds'])
        and 0<=report['worker_wall_seconds']<=80,'N29 arithmetic process exceeds active bound')


def settled_proof(proof,resources,r):
    plan=w.read_ref(proof['plan']);report=w.read_ref(proof['report']);process=w.read_ref(proof['process'])
    group=[e for e in resources if e.get('resource_id')==plan['resource_id']]
    w.require([e['event'] for e in group]==['reserved','dispatched','completed']
        and sum(e['event']=='reserved' for e in resources if e.get('kind')==KIND)==1,'N29 single settled resource missing')
    final=group[-1]
    w.require(w.read_ref(proof['terminal'])==final and proof['plan']==c.ref(PLAN)
        and all(e.get('plan')==proof['plan'] and e.get('kind')==KIND for e in group)
        and final.get('report')==proof['report'] and final.get('process')==proof['process']
        and final.get('resource_id')==process.get('resource_id')==plan['resource_id']
        and final.get('cleanup_complete') is True and final.get('cost_measurement_complete') is True
        and 0<=report['worker_wall_seconds']<=final['gpu_process_wall_seconds']<=120,
        'N29 resource proof cost/process/plan differs')
    validate_report(report,plan,process)
    return proof


def verify_proof(reference,source,runtime,root):
    proof=w.read_ref(reference)
    w.require(reference==c.ref(c.BACKEND_PROOF) and set(proof)=={'schema','accepted','source','runtime','plan','report','process','terminal'}
        and proof['schema']=='n29-metered-tensor-proof-v1' and proof['accepted'] is True
        and proof['source']==source and proof['runtime']==runtime,'N29 arithmetic proof absent/different')
    plan=w.read_ref(proof['plan']);validate_plan(plan,root)
    w.require(plan['source']==source and plan['runtime']==runtime,'N29 preflight/Dev source drift')
    report=w.read_ref(proof['report']);process=w.read_ref(proof['process']);validate_report(report,plan,process)
    # Terminal JSON is checked now, append-only ledger is rechecked under admission lock.
    terminal=w.read_ref(proof['terminal'])
    w.require(terminal.get('event')=='completed' and terminal.get('cleanup_complete') is True
        and terminal.get('cost_measurement_complete') is True and terminal.get('report')==proof['report']
        and terminal.get('process')==proof['process'] and terminal.get('plan')==proof['plan']
        and report['worker_wall_seconds']<=terminal['gpu_process_wall_seconds']<=120,'N29 terminal proof differs')
    return proof


def run(*,root=c.ROOT):
    """Root-only activation; even a reserved failure permanently consumes this scope."""
    from scripts import qd_ed_final_runner as r
    root=Path(root).resolve()
    with r.locked(root/'data/qd-ed-runner.lock',nonblocking=True):
        source=w.source_record(root,c.source_paths(vars(r)));runtime_ref=c.runtime_ref();runtime=w.read_ref(runtime_ref)
        state=r.read_state(root/'research-state.yaml');events=r.read_events(root/'data/attempt-ledger.jsonl');resources=r.read_events(root/'data/gpu-healthcheck-ledger.jsonl')
        admission(state,events,resources,vars(r),source,runtime_ref,root,
            reservation_events=r.read_events(root/'data/gpu-hour-reservation-ledger.jsonl'))
        w.require(w.read_ref(c.ref(RELEASE))=={'schema':'n29-tensor-resource-release-v1','source':source,'runtime':runtime_ref,
            'authority':c.ref(AUTHORITY),'limits':LIMITS,'one_shot':True},'N29 tensor execution release missing')
        admission_record=r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
        resource_id=state['run_name']+'__n29_tensor_arithmetic_v1'
        plan=build_plan(source,runtime_ref,root,resource_id,authority_ref=c.ref(AUTHORITY));plan['frozen']=True
        w.atomic_json(PLAN,plan);validate_plan(plan,root)
        output=Path(plan['output_dir']);output.mkdir(parents=True,exist_ok=False)
        base={'resource_id':resource_id,'kind':KIND,'physical_gpu':7,'output_dir':str(output),
            'plan':c.ref(PLAN),'source_commit':source['commit'],'budget_bucket':'recovery','episode_attempts':0}
        process=None;started=None;event='aborted';reason=None;report_ref=None;process_ref=None
        r.append_healthcheck_event(root,{**base,'event':'reserved','time_unix':time.time(),'admission':admission_record})
        try:
            r.gpu_admission(physical_gpu=7,expected_uuid=c.GPU7_UUID)
            env=r.child_environment(runtime);env.update(N29_PREFLIGHT_PARENT_PID=str(os.getpid()),N29_PREFLIGHT_RESOURCE_ID=resource_id)
            command=[str(r.PYTHON),str(root/'scripts/qd_ed_n29_preflight.py'),'--plan',str(PLAN)]
            w.atomic_json(output/'command.json',{'argv':command,'limits':LIMITS})
            r.append_healthcheck_event(root,{**base,'event':'dispatched','time_unix':time.time(),'timeout_seconds':80})
            started=time.monotonic()
            with (output/'worker.log').open('x') as log:
                process=subprocess.Popen(command,cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                identity={'pid':process.pid,'resource_id':resource_id,
                    'proc_start_ticks':Path(f'/proc/{process.pid}/stat').read_text().rsplit(')',1)[1].split()[19],
                    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
                w.atomic_json(output/'process.json',identity);process_ref=c.ref(output/'process.json')
                code=r.wait_exclusively(process,80,physical_gpu=7)
            w.require(code==0,'N29 arithmetic child failed')
            report_ref=c.ref(output/'report.json');validate_report(w.read_ref(report_ref),plan,identity)
            event='completed'
        except BaseException as exc:reason={'type':type(exc).__name__,'message':str(exc)}
        finally:
            cleanup_complete=True
            try:r.terminate_owned(process)
            except BaseException as exc:
                cleanup_complete=False;event='aborted';reason={'type':type(exc).__name__,'message':'Owned cleanup failed; root reconciliation required'}
            elapsed=time.monotonic()-started if started is not None else 0.
            if elapsed>120:event='aborted';reason={'type':'TimeoutError','message':'N29 complete resource wall exceeded120s'}
            terminal={**base,'event':event,'time_unix':time.time(),'gpu_process_wall_seconds':elapsed,
                'report':report_ref,'process':process_ref,'failure':reason,'cleanup_complete':cleanup_complete,
                'cost_measurement_complete':cleanup_complete,'measurement':'whole exclusive process wall including cleanup'}
            r.append_healthcheck_event(root,terminal);w.atomic_json(output/'healthcheck-result.json',terminal)
        w.require(event=='completed','N29 resource failed; no retry authorized')
        proof={'schema':'n29-metered-tensor-proof-v1','accepted':True,'source':source,'runtime':runtime_ref,
            'plan':c.ref(PLAN),'report':report_ref,'process':process_ref,'terminal':c.ref(output/'healthcheck-result.json')}
        settled_proof(proof,r.read_events(root/'data/gpu-healthcheck-ledger.jsonl'),vars(r));w.atomic_json(c.BACKEND_PROOF,proof)
        return proof


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',action='store_true',required=True);parser.parse_args()
    run()
