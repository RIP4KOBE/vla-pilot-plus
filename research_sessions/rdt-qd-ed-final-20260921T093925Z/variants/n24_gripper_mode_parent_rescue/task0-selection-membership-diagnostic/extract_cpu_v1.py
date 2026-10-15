"""One-pass recorded N24 task0 terminal eligibility membership; no tensor/runtime imports."""
import collections,csv,hashlib,json,os,signal,sys,time,traceback
from pathlib import Path
H=Path(__file__).resolve().parent
SCOPE_SHA='064f5674a25da0e52514d840ca958a1c4ac593b2d8d2ef753d6cf452363cacad'
def check(ok,msg):
    if not ok:raise ValueError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def write(name,record):
    with (H/name).open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
def main():
    check(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and all(os.environ.get(k)=='2' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')),'CPU-only bounds')
    check('torch' not in sys.modules,'torch must not load')
    mp=H/'input-manifest-v1.json';mb=mp.read_bytes();check(sha(mb)==sys.argv[1],'manifest changed');manifest=json.loads(mb)
    allowed={str(Path(x['path']).resolve()) for x in manifest['inputs']}
    allowed|={str(Path(__file__).resolve()),str(mp),str(H/'read-scope-v1.json')}
    immutable=set(allowed);blocked=[];counts=collections.Counter();rows=[];started=time.monotonic()
    metric_path=manifest['metrics']['path']
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','os.spawn','os.exec','socket.connect','socket.bind','socket.getaddrinfo'}:
            blocked.append(event);raise RuntimeError('process/network forbidden')
        if event=='import' and isinstance(args[0],str) and args[0].split('.')[0] in {'torch','core','scripts','numpy','robosuite','mujoco','libero','libero_pro','requests','httpx','transformers'}:
            blocked.append('import:'+args[0]);raise RuntimeError('tensor/CUDA/model/provider/runtime import forbidden')
        if event!='open' or isinstance(args[0],int):return
        p=Path(os.fsdecode(args[0])).resolve();mode=args[1] or '';flags=args[2] if len(args)>2 else 0
        writing=any(x in mode for x in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        bad=(not p.is_relative_to(H) or str(p) in immutable) if writing else (str(p) not in allowed and not p.is_relative_to(H))
        if p.suffix=='.pt':bad=True
        if not writing and str(p)==metric_path:
            counts[str(p)]+=1
            if counts[str(p)]>1:bad=True
        if bad:blocked.append(str(p));raise PermissionError('outside exact membership read/write scope')
    sys.addaudithook(guard)
    def read(reference):
        b=Path(reference['path']).read_bytes();check(sha(b)==reference['sha256'],'input sha '+Path(reference['path']).name);return b
    def timeout(*a):raise TimeoutError('30-second bound; no automatic second metric pass')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(30)
    try:
        check(sha(Path(__file__).read_bytes())==manifest['extractor']['sha256'],'extractor changed')
        sb=(H/'read-scope-v1.json').read_bytes();check(sha(sb)==SCOPE_SHA,'scope changed');scope=json.loads(sb)
        closed=json.loads(read(scope['inputs']['closed_command_diagnostic']))
        read(scope['inputs']['closed_diagnostic_review']) # Hash-bind the accepted identity review only; no additional outcome fields inspected.
        raw=read(scope['inputs']['metrics']);metrics=[json.loads(line) for line in raw.splitlines() if line.strip()]
        check(len(metrics)==len(closed['decisions'])==14,'complete14 denominator')
        decisions={d['global_step']:d for d in closed['decisions']};terminal={b['global_step']:b for b in closed['canonical_batches'] if b['iter_idx']==9}
        check(len(decisions)==len(terminal)==14,'unique closed decision identities')
        seen=set()
        for item in metrics:
            # Project only the exact frozen allowed fields; never access costs/geometry/provider values.
            step=item['global_step'];v=item['qd_terminal_population'];g=v['grasp_selection']
            projected={k:v[k] for k in ('iter_idx','population_size','selected_index','selected_occurrence_id','selected_fingerprint')}
            gs={k:g[k] for k in ('target_index','recognition_reason','eligible_indices','native_argmin_index')}
            check(type(step) is int and step in decisions and step not in seen,'metric step identity');seen.add(step)
            d=decisions[step];b=terminal[step];selected=projected['selected_index']
            check(projected['iter_idx']==9 and projected['population_size']==16 and type(selected) is int and 0<=selected<16,'terminal16/iter9')
            check(selected==d['selected_index'] and projected['selected_fingerprint']==d['selected_fingerprint'] and projected['selected_occurrence_id']==d['selected_occurrence_id'],'selected full identity')
            prefix=b['gripper_prefix'];check(prefix['shape']==[16,8] and len(prefix['values'])==16,'closed gripper shape')
            positive=[]
            for command in prefix['values']:
                check(len(command)==8 and all(type(x) in (int,float) for x in command),'closed gripper values')
                positive.append(sum(x>=0 for x in command))
            check([positive.count(i) for i in range(9)]==b['histogram_0to8'] and positive[selected]==d['selected_positive_commands'],'closed histogram/selected signs')
            full=[i for i,n in enumerate(positive) if n==8];eligible=gs['eligible_indices'];argmin=gs['native_argmin_index']
            check(isinstance(eligible,list) and len(set(eligible))==len(eligible) and all(type(i) is int and 0<=i<16 for i in eligible),'recorded eligible index set')
            check(type(argmin) is int and 0<=argmin<16,'recorded native argmin identity')
            check(gs['target_index'] is None or type(gs['target_index']) is int,'target index type')
            check(isinstance(gs['recognition_reason'],str),'recognition reason type')
            intersection=[i for i in full if i in eligible]
            category=('no_terminal_full8' if not full else 'selected_full8' if selected in full else
                      'full8_all_ineligible' if not intersection else 'eligible_full8_not_selected')
            row={'global_step':step,'decision_id':d['decision_id'],'selected_index':selected,'selected_fingerprint':d['selected_fingerprint'],
                'selected_occurrence_id':d['selected_occurrence_id'],'selected_positive_commands':positive[selected],
                'terminal_full8_indices':full,'eligible_indices':eligible,'eligible_full8_indices':intersection,
                'native_argmin_index':argmin,'native_argmin_full8':argmin in full,'native_argmin_eligible':argmin in eligible,
                'selected_is_eligible':selected in eligible,'selected_is_native_argmin':selected==argmin,
                'target_index':gs['target_index'],'recognition_reason':gs['recognition_reason'],'classification':category,
                'closed_command_category':d['category']}
            rows.append(row)
            write(f'partial-step-{step:06d}-v1.json',row)
        check(seen==set(decisions) and counts[metric_path]==1 and not blocked and 'torch' not in sys.modules,'complete single-pass guard')
        rows.sort(key=lambda x:x['global_step']);elapsed=time.monotonic()-started;check(elapsed<=30,'wall bound')
        result={'schema':'n24-task0-selection-membership-result-v1','scope':{'path':str(H/'read-scope-v1.json'),'sha256':SCOPE_SHA},
            'input_manifest':{'path':str(mp),'sha256':sys.argv[1]},'extractor':manifest['extractor'],'source_commit':manifest['source_commit'],
            'task_id':0,'arm':'N24','decisions':rows,'count':len(rows),'classifications':dict(collections.Counter(x['classification'] for x in rows)),
            'metric_payload_bytes':len(raw),'metric_payload_passes':counts[metric_path],'new_tensor_reads':0,'elapsed_seconds':elapsed,
            'guard':{'blocked':blocked,'max_cpu_threads':2,'numerical_backend':'stdlib-only single thread','cuda_visible_devices':'','torch_imported':False,'runtime_imports':False},
            'inference_limits':'Exact recorded terminal eligibility membership only. No geometry/distance/cost/quality/rank recomputation, threshold change, physical grasp, counterfactual or efficacy claim.'}
        write('result-v1.json',result)
        with (H/'all-decisions-v1.csv').open('x',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        print(json.dumps({'status':'COMPLETE','count':14,'classifications':result['classifications'],'focused_steps':[x for x in rows if x['global_step'] in (304,408)],'elapsed_seconds':elapsed,'blocked':blocked}),flush=True)
    except BaseException as exc:
        write('extraction-error-v1.json',{'error_type':type(exc).__name__,'error':str(exc),'completed_rows':len(rows),'metric_payload_passes':counts[metric_path],'blocked':blocked,'elapsed_seconds':time.monotonic()-started,'automatic_rerun_authorized':False})
        traceback.print_exc();raise
    finally:signal.alarm(0)
if __name__=='__main__':main()
