"""Frozen N24 task0, one-pass gripper-only recorded-identity diagnostic."""
import collections,csv,hashlib,io,json,os,re,signal,sys,time,traceback
from pathlib import Path
import torch
H=Path(__file__).resolve().parent
SCOPE_SHA='d309ef966b8f18f8d66dbdbc2e670b8d70369ed23ec2b0d6552d6323ed64548b'

def check(ok,message):
    if not ok:raise ValueError(message)
def sha(data):return hashlib.sha256(data).hexdigest()
def dump(name,value):
    with (H/name).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def ref(path):
    p=Path(path);return {'path':str(p.resolve()),'sha256':sha(p.read_bytes())}
def native(value):return {'dtype':str(value.dtype),'shape':list(value.shape),'values':value.tolist()}
def grip(value):
    check(torch.is_tensor(value) and value.device.type=='cpu' and value.ndim==3 and tuple(value.shape[1:])==(64,128),'native action shape/device')
    g=value[:,:8,10].contiguous();check(g.dtype in (torch.float32,torch.bfloat16) and bool(torch.isfinite(g).all()),'gripper dtype/finite')
    return g,(g>=0).sum(dim=1)
def same(a,b):return a.dtype==b.dtype and a.shape==b.shape and torch.equal(a.view(torch.uint8),b.view(torch.uint8))
def hist(counts):return torch.bincount(counts,minlength=9).tolist()
def cache_identity(record):
    return None if record is None else {k:record[k] for k in ('iteration','row','fingerprint','canonical_sequence','scoring_batch_id','occurrence_id')}
def classify(counts,selected):
    return ('never_full8_positive' if not any(counts) else 'lost_before_terminal' if counts[-1]==0
            else 'available_terminal_not_selected' if selected!=8 else 'selected_full8_positive')

def main():
    torch.set_num_threads(2);torch.set_num_interop_threads(2)
    check(os.environ.get('CUDA_VISIBLE_DEVICES')=='' and not torch.cuda.is_initialized(),'CPU-only environment')
    manifest_path=H/'input-manifest-v1.json';mb=manifest_path.read_bytes();check(sha(mb)==sys.argv[1],'manifest hash')
    manifest=json.loads(mb);allowed={str(Path(x['path']).resolve()) for x in manifest['inputs']+manifest['source_files']}
    allowed|={str(Path(__file__).resolve()),str(manifest_path.resolve()),str((H/'read-scope-v1.json').resolve())}
    blocked=[];read_counts=collections.Counter();loaded=[];bytes_read=0;decisions=[];batches=[];rounds=[];substitutions=[]
    repo=H.parents[3];native_paths={x['path'] for x in manifest['bundles']}
    def guard(event,args):
        if event in {'subprocess.Popen','os.system','os.fork','os.posix_spawn','os.spawn','os.exec','socket.connect','socket.bind','socket.getaddrinfo'}:
            blocked.append(event);raise RuntimeError('dispatch/network forbidden')
        if event=='import' and isinstance(args[0],str) and args[0].split('.')[0] in {'core','scripts','robosuite','mujoco','libero','libero_pro','requests','httpx','transformers'}:
            blocked.append('import:'+args[0]);raise RuntimeError('runtime import forbidden')
        if event!='open' or isinstance(args[0],int):return
        path=Path(os.fsdecode(args[0])).resolve();mode=args[1] or '';flags=args[2] if len(args)>2 else 0
        writing=any(x in mode for x in 'wax+') or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writing:bad=not path.is_relative_to(H) and str(path)!='/dev/null'
        else:
            sensitive=path.is_relative_to(repo) or path.is_relative_to(Path('/mnt')) or path.is_relative_to(Path('/home/hynx/.codex'))
            bad=sensitive and str(path) not in allowed and not path.is_relative_to(H)
            if not bad and str(path) in native_paths:
                read_counts[str(path)]+=1
                if read_counts[str(path)]>1:bad=True
        if bad:blocked.append(str(path));raise PermissionError('outside exact diagnostic scope or repeated native read')
    sys.addaudithook(guard)
    def no_cuda(*a,**k):blocked.append('CUDA');raise RuntimeError('CUDA forbidden')
    torch.cuda._lazy_init=no_cuda
    def read_bound(reference):
        data=Path(reference['path']).read_bytes();check(sha(data)==reference['sha256'],'input changed: '+Path(reference['path']).name);return data
    check(sha(Path(__file__).read_bytes())==manifest['extractor']['sha256'],'extractor changed')
    for source in manifest['source_files']:read_bound(source)
    scope_data=(H/'read-scope-v1.json').read_bytes();check(sha(scope_data)==SCOPE_SHA,'scope changed');scope=json.loads(scope_data)
    started=time.monotonic()
    def timeout(*a):raise TimeoutError('native extraction exceeded120 seconds; no automatic reread')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(120)
    try:
        # These four refs are explicitly authorized. Other scope refs are provenance only.
        terminal=json.loads(read_bound(scope['terminal']));receipt=json.loads(read_bound(scope['native_receipt']));audit=json.loads(read_bound(scope['native_audit']))
        read_bound(scope['metered_bundle_index']) # hash only; per-bundle index associations already frozen in scope.
        check(terminal['identity']['task_id']==0 and terminal['identity']['profile']=='N24' and terminal['outcome_valid'] is True,'completed task0/N24 identity')
        check(terminal['source_commit']==scope['source_commit'] and terminal.get('n23_worker_receipt')==scope['native_receipt'],'terminal source/receipt')
        check(receipt['accepted'] is True and receipt['audit_report']==scope['native_audit'] and audit['accepted'] is True and audit['evidence_complete'] is True,'accepted native refs')
        gate=audit['n24_gripper_parent_rescue_audit'];linked={x['decision_id']:x for x in audit['n5_grasp_timing_audit']['decisions']}
        check(len(linked)==14 and gate['checked_decisions']==14 and gate['canonical_batches_verified']==154 and gate['canonical_candidates_verified']==2464 and gate['parent_rounds_verified']==140,'native audit coverage')
        for bref in manifest['bundles']:
            path=bref['path'];check(path not in loaded,'duplicate bundle');loaded.append(path)
            data=read_bound(bref);bytes_read+=len(data)
            payload=torch.load(io.BytesIO(data),map_location='cpu',weights_only=True);del data
            check(payload['schema']=='qd-ed-decision-evidence-v1','bundle schema')
            index=next(x for x in scope['bundles'] if x['path']==path)
            check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in payload['events']]==index['events'],'frozen metered bundle event association')
            wanted={'decision_context','canonical_candidate_batch','gripper_rescue_begin','gripper_rescue_cache','gripper_rescue_parents','archive_parent_allocation','parent_allocation','final_selection','policy_action_decode','decision_committed'}
            kinds=collections.defaultdict(list)
            for e in payload['events']:
                if e['event'] in wanted:kinds[e['event']].append(e)
            def one(kind):check(len(kinds[kind])==1,'singleton '+kind);return kinds[kind][0]
            context=one('decision_context');did=context['decision_id'];step=context['global_step'];reset=context['reset_sequence'];na=linked[did]
            check(did==bref['decision_id'] and step==bref['global_step']==na['global_step'] and context['values']['use_guidance'] is True,'guided identity')
            check(all(x['decision_id']==did and x['global_step']==step and x['reset_sequence']==reset for values in kinds.values() for x in values),'decision context association')
            def indexed(kind,expected):
                es=kinds[kind];check([e['values']['iter_idx'] for e in es]==expected,'ordered coverage '+kind);return {e['values']['iter_idx']:e for e in es}
            canonical=indexed('canonical_candidate_batch',list(range(-1,10)));updates=indexed('gripper_rescue_cache',list(range(-1,10)))
            parents=indexed('parent_allocation',list(range(10)));original=indexed('archive_parent_allocation',list(range(10)));rescues=indexed('gripper_rescue_parents',list(range(10)))
            source_audit={x['iter_idx']:x for x in na['canonical_sources']};parent_audit={x['iter_idx']:x for x in na['parent_associations']}
            check(set(source_audit)==set(canonical) and set(parent_audit)==set(parents),'native association coverage')
            known={};prior_by_fp=collections.defaultdict(list);own_batches=[];own_rounds=[];own_subs=[];update_sum=0;updated_batches=0
            for iteration in range(-1,10):
                event=canonical[iteration];v=event['values'];g,n=grip(v['candidates']);ids=v['occurrence_ids'];fps=v['canonical_fingerprints'];sa=source_audit[iteration]
                check(g.shape==(16,8) and len(fps)==16 and all(re.fullmatch('[0-9a-f]{64}',fp) for fp in fps),'canonical gripper/fingerprints')
                check(ids==[f'{did}:q{event["sequence"]}:r{j}' for j in range(16)] and sa['canonical_sequence']==event['sequence'],'canonical occurrence/native audit binding')
                # Actual ED row link is from ordered recorded parent_indices, never inferred from similarity.
                if iteration>=0:
                    ae=original[iteration];av=ae['values'];re_=rescues[iteration];rv=re_['values'];pe=parents[iteration];pv=pe['values'];pa=parent_audit[iteration]
                    og,on=grip(rv['original_actions']);ag,an=grip(rv['actual_actions']);pg,pn=grip(pv['source_population']);indices=pv['parent_indices'].tolist();slot=rv['replacement_slot']
                    check(pa['allocation_sequence']==ae['sequence'] and pa['parent_sequence']==pe['sequence'] and ae['sequence']<re_['sequence']<pe['sequence']<sa['scoring_batch_id']<event['sequence'],'original→actual→ED order')
                    check(indices==list(range(16)) and pv['elite_count']==0 and same(ag,pg),'exact ordered ED actual parents')
                    check(rv['original_full_close_mask'].tolist()==(on==8).tolist(),'original full8 witness')
                    check(rv['exact_survivor'] is False and rv['original_is_archive_allocation'] is True and rv['actual_is_archive_allocation']==(slot is None),'no survivor/archive claims')
                    check(pv['gripper_rescue_mode']=='canonical_full_close_v1' and pv['parent_fingerprints']==[pv['source_fingerprints'][i] for i in indices],'actual fingerprints')
                    original_links=[];actual_links=[]
                    for j in range(16):
                        originals=prior_by_fp[av['parent_fingerprints'][j]]
                        check(originals and all(same(known[oid]['gripper'],og[j]) for oid in originals),'original witness prior gripper association')
                        original_links.append({'slot':j,'fingerprint':av['parent_fingerprints'][j],'matching_prior_occurrence_ids':list(originals),'positive_commands':int(on[j])})
                        ap=pa['slots'][j];check(ap['slot']==j and ap['matching_occurrence_ids'],'native actual parent slot')
                        for oid in ap['matching_occurrence_ids']:
                            check(oid in known and known[oid]['fingerprint']==pv['source_fingerprints'][j] and same(known[oid]['gripper'],pg[j]),'accepted native full identity plus authorized gripper')
                        actual_links.append({'slot':j,'fingerprint':pv['source_fingerprints'][j],'matching_prior_occurrence_ids':ap['matching_occurrence_ids'],'positive_commands':int(pn[j])})
                    expected_sources=['qd_archive_offspring']*16
                    if slot is not None:
                        check(type(slot) is int and 0<=slot<16 and int((on==8).sum())==0 and int((an==8).sum())==1 and an[slot].item()==8,'conditional rescue full8 restoration')
                        ci=cache_identity(rv['cache']);old=known[ci['occurrence_id']]
                        check(ci['iteration']<iteration and ci['fingerprint']==pv['source_fingerprints'][slot]==old['fingerprint'] and same(old['gripper'],ag[slot]),'cache exact prior identity')
                        check(all(same(og[j],ag[j]) and av['parent_fingerprints'][j]==pv['source_fingerprints'][j] for j in range(16) if j!=slot),'other15 unchanged authorized slice and recorded fingerprint')
                        expected_sources[slot]='qd_gripper_rescue_offspring'
                        sub={'decision_id':did,'global_step':step,'iter_idx':iteration,'replacement_slot':slot,'cache':ci,
                             'original_full8':0,'actual_full8':int((an==8).sum()),'child_row':indices.index(slot),
                             'child_occurrence_id':ids[indices.index(slot)],'child_fingerprint':fps[indices.index(slot)],'child_positive_commands':int(n[indices.index(slot)]),
                             'original_allocation_sequence':ae['sequence'],'rescue_sequence':re_['sequence'],'actual_parent_sequence':pe['sequence'],'child_canonical_sequence':event['sequence'],
                             'later_exact_child_identity_observations':[],'genealogy_beyond_recorded_links':'Unknown; no unique archive insertion ancestry claim'}
                        own_subs.append(sub);substitutions.append(sub)
                    else:check(same(og,ag) and av['parent_fingerprints']==pv['source_fingerprints'],'unmodified allocation')
                    check(pv['offspring_sources']==expected_sources,'recorded ED source labels')
                    for sub in own_subs:
                        if sub['iter_idx']<iteration:
                            matches=[{'slot':j,'matching_occurrence_ids':ap['matching_prior_occurrence_ids']} for j,ap in enumerate(actual_links) if sub['child_occurrence_id'] in ap['matching_prior_occurrence_ids']]
                            if matches:sub['later_exact_child_identity_observations'].append({'round':iteration,'actual_parent_slots':matches})
                    rr={'decision_id':did,'global_step':step,'iter_idx':iteration,'original_histogram_0to8':hist(on),'actual_histogram_0to8':hist(an),
                        'offspring_histogram_0to8':hist(n),'replacement_slot':slot,'original_parents':original_links,'actual_parents':actual_links,
                        'parent_indices':indices,'offspring_sources':pv['offspring_sources'],
                        'row_links':[{'parent_slot':i,'child_row':j,'child_occurrence_id':ids[j],'parent_positive_commands':int(pn[i]),'child_positive_commands':int(n[j])} for j,i in enumerate(indices)]}
                    own_rounds.append(rr);rounds.append(rr)
                for j in range(16):known[ids[j]]={'fingerprint':fps[j],'gripper':g[j].clone(),'positive_commands':int(n[j])};prior_by_fp[fps[j]].append(ids[j])
                uv=updates[iteration]['values'];ci=cache_identity(uv['cache']);updated=uv['updated'];count=uv['update_count']
                check(type(updated) is bool and type(count) is int and count>=0 and updated==(count>0),'native cache count semantics')
                check(uv['full_close_rows'].tolist()==torch.nonzero(n==8).flatten().tolist(),'cache full8 witness')
                if ci is not None:
                    check(ci['occurrence_id'] in known and known[ci['occurrence_id']]['positive_commands']==8 and ci['fingerprint']==known[ci['occurrence_id']]['fingerprint'],'cache birth identity/full8')
                update_sum+=count;updated_batches+=int(updated)
                br={'decision_id':did,'global_step':step,'iter_idx':iteration,'canonical_sequence':event['sequence'],'scoring_batch_id':sa['scoring_batch_id'],
                    'histogram_0to8':hist(n),'full8':int((n==8).sum()),'exact_zero_values':int((g==0).sum()),'cache_updated':updated,'native_cache_update_count':count,
                    'cache':ci,'row_occurrence_ids':ids,'row_fingerprints':fps,'gripper_prefix':native(g)}
                own_batches.append(br);batches.append(br)
            fv=one('final_selection')['values'];fg,fn=grip(fv['population']);tv=fv['terminal_population'];selected=fv['selected_index'];last=canonical[9]['values'];lastg,lastn=grip(last['candidates'])
            check(same(fg,lastg) and type(selected) is int and 0<=selected<16 and selected==na['selected_index'],'terminal gripper/source/native selection')
            selected_fp=fv['selected_canonical_fingerprint'];selected_id=tv['selected_occurrence_id']
            check(selected_fp==last['canonical_fingerprints'][selected]==na['selected_fingerprint'] and selected_id==last['occurrence_ids'][selected]==na['selected_occurrence_id'],'selected canonical binding')
            dv=one('policy_action_decode')['values'];commit=one('decision_committed')['values'];dg=dv['action_chunk'][0,:,6].contiguous();cg=commit['action_chunk'][0,:,6].contiguous()
            check(dv['selected_canonical_fingerprint']==selected_fp and tuple(dg.shape)==(8,) and same(dg,cg) and torch.equal(dg>0,fg[selected]>=0),'native decoded committed gripper binding')
            for sub in own_subs:
                match=[j for j,fp in enumerate(last['canonical_fingerprints']) if fp==sub['child_fingerprint']]
                sub['terminal_same_recorded_fingerprint_rows']=match
                sub['selected_same_recorded_child_fingerprint']=selected_fp==sub['child_fingerprint']
                sub['later_fingerprint_identity_caveat']='Native audit binds full identities; duplicate birth occurrences remain aliases. Same fingerprint is not unique causal ancestry.'
            counts=[x['full8'] for x in own_batches]
            decision={'decision_id':did,'global_step':step,'reset_sequence':reset,'stage':context['values']['stage'],
                'bundle':{k:bref[k] for k in ('path','sha256')},'canonical_full8_counts':counts,'canonical_any_positive_counts':[16-b['histogram_0to8'][0] for b in own_batches],
                'original_parent_full8_counts':[rr['original_histogram_0to8'][8] for rr in own_rounds],
                'actual_parent_full8_counts':[rr['actual_histogram_0to8'][8] for rr in own_rounds],
                'initial_full8':counts[0],'terminal_full8':counts[-1],'selected_positive_commands':int(fn[selected]),'selected_index':selected,
                'selected_fingerprint':selected_fp,'selected_occurrence_id':selected_id,'decoded_gripper':native(dg),'category':classify(counts,int(fn[selected])),
                'native_cache_updates':update_sum,'cache_changed_batches':updated_batches,'substitutions':len(own_subs)}
            decisions.append(decision)
            dump(f'partial-decision-{step:06d}-v1.json',{'decision':decision,'batches':own_batches,'rounds':own_rounds,'substitutions':own_subs})
            print(json.dumps({'completed_decisions':len(decisions),'step':step,'elapsed_seconds':time.monotonic()-started}),flush=True)
            del payload
        totals={'guided_decisions':len(decisions),'canonical_batches':len(batches),'canonical_candidates':len(batches)*16,'parent_rounds':len(rounds),
                'cache_updates':sum(x['native_cache_update_count'] for x in batches),'substitutions':len(substitutions)}
        check(all(totals[k]==scope['expected'][k] for k in totals),'frozen expected totals')
        check(totals['cache_updates']==gate['cache_updates'] and totals['substitutions']==gate['substitutions'],'metered native mechanism audit totals')
        check(len(loaded)==14 and bytes_read==243123318 and max(read_counts.values())==1,'exact native read coverage')
        elapsed=time.monotonic()-started;check(elapsed<=120 and not blocked and not torch.cuda.is_initialized(),'time/guards')
        result={'schema':'n24-task0-rescue-survival-result-v1','scope':{'path':str(H/'read-scope-v1.json'),'sha256':SCOPE_SHA},
            'input_manifest':{'path':str(manifest_path),'sha256':sys.argv[1]},'extractor':manifest['extractor'],'source_commit':scope['source_commit'],
            'native_audit':scope['native_audit'],'native_receipt':scope['native_receipt'],'terminal':scope['terminal'],'totals':totals,
            'cache_changed_batches':sum(x['cache_updated'] for x in batches),'categories':dict(collections.Counter(x['category'] for x in decisions)),
            'rescue_child_histogram_0to8':[sum(x['child_positive_commands']==i for x in substitutions) for i in range(9)],
            'decisions':decisions,'canonical_batches':batches,'parent_rounds':rounds,'substitutions':substitutions,
            'native_bytes_read':bytes_read,'native_loads':loaded,'native_read_counts':dict(read_counts),'elapsed_seconds':elapsed,
            'guard':{'blocked':blocked,'cuda_initialized':False,'cpu_threads':2,'cuda_visible_devices':''},
            'interpretation':'Recorded command-sign availability and actual slot links only; no new geometry/quality/score/ranking, contact, grasp, efficacy or counterfactual inference.'}
        dump('result-v1.json',result)
        for name,rows,cols in [('all-decisions-v1.csv',decisions,['global_step','stage','initial_full8','canonical_full8_counts','original_parent_full8_counts','actual_parent_full8_counts','terminal_full8','selected_positive_commands','category','native_cache_updates','cache_changed_batches','substitutions']),
            ('all-substitutions-v1.csv',substitutions,['global_step','iter_idx','replacement_slot','original_full8','actual_full8','child_row','child_positive_commands','child_occurrence_id','selected_same_recorded_child_fingerprint','terminal_same_recorded_fingerprint_rows'])]:
            with (H/name).open('x',newline='') as f:writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)
        print(json.dumps({'status':'COMPLETE','totals':totals,'cache_changed_batches':result['cache_changed_batches'],'categories':result['categories'],'rescue_child_histogram':result['rescue_child_histogram_0to8'],'elapsed_seconds':elapsed,'blocked':blocked}),flush=True)
    except BaseException as exc:
        dump('extraction-error-v1.json',{'schema':'n24-bounded-extraction-error-v1','error_type':type(exc).__name__,'error':str(exc),
            'native_loads':loaded,'native_read_counts':dict(read_counts),'native_bytes_read':bytes_read,'completed_decisions':len(decisions),
            'elapsed_seconds':time.monotonic()-started,'blocked':blocked,'cuda_initialized':torch.cuda.is_initialized(),'automatic_rerun_authorized':False})
        traceback.print_exc();raise
    finally:signal.alarm(0)
if __name__=='__main__':main()
