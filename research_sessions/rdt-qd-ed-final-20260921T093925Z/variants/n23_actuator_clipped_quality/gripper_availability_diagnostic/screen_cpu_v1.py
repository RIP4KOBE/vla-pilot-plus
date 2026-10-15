"""Bounded observation of recorded canonical gripper commands; no rescoring."""
from __future__ import annotations
import collections,csv,hashlib,importlib.util,io,json,os,subprocess,sys,time
from pathlib import Path
import torch

torch.set_num_threads(2)
HERE=Path(__file__).resolve().parent
SCOPE=HERE/'read-scope-v1.json'
SCOPE_SHA='5b569b01eb84cd5b51139cfd9ce175f94f695306cb977b5a3875ebc17fc8c34b'

def check(ok,message):
    if not ok: raise ValueError(message)

def digest(data):return hashlib.sha256(data).hexdigest()
def sha(p):return digest(Path(p).read_bytes())
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def native(t):
    t=t.detach().cpu().contiguous()
    return {'dtype':str(t.dtype),'shape':list(t.shape),'sha256':digest(f'{t.dtype}:{tuple(t.shape)}:'.encode()+t.reshape(-1).view(torch.uint8).numpy().tobytes()),'values':t.tolist()}
def same(a,b):return native(a)==native(b)
def hist(counts):return torch.bincount(counts,minlength=9).tolist()
def summary(counts,costs):
    yes=counts>0;ix=torch.nonzero(yes).reshape(-1).tolist()
    return {'histogram_0_to_8':hist(counts),'positive_candidates':int(yes.sum()),'positive_commands':int(counts.sum()),
        'positive_indices':ix,'min_positive_native_cost':float(costs[yes].min()) if bool(yes.any()) else None,
        'min_zero_positive_native_cost':float(costs[~yes].min()) if bool((~yes).any()) else None}

def run():
    start=time.monotonic();check(not torch.cuda.is_initialized(),'CUDA initialized')
    check(sha(SCOPE)==SCOPE_SHA,'frozen read scope drift')
    scope=json.loads(SCOPE.read_text());W=HERE.parents[2]/'study_worktree'
    check(subprocess.check_output(['git','rev-parse','HEAD'],cwd=W,text=True).strip()==scope['source_commit'],'source commit drift')
    for f in [scope['scope'],scope['prior_screen'],*scope['source_files'].values()]:check(sha(f['path'])==f['sha256'],'static input changed')
    decoder_path=Path(scope['source_files']['core/rdt_libero_action_converter.py']['path'])
    spec=importlib.util.spec_from_file_location('bounded_gripper_decoder',decoder_path);decoder=importlib.util.module_from_spec(spec);spec.loader.exec_module(decoder)
    allowed={str(Path(f['path']).resolve()) for f in scope['data_files']}
    allowed.update(str(Path(f['path']).resolve()) for f in scope['source_files'].values())
    forbidden_roots=[str(HERE.parents[2].resolve()),'/mnt/data/shared2/hynx/VLA-Pilot++']
    denied=[]
    def guard(event,args):
        if event!='open':return
        filename,mode,flags=args
        if isinstance(filename,int):return
        p=str(Path(os.fsdecode(filename)).resolve())
        write=bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write:
            if any(p.startswith(r+'/') for r in forbidden_roots) and not p.startswith(str(HERE)+'/'):raise RuntimeError('write outside diagnostic')
        elif any(p.startswith(r+'/') for r in forbidden_roots) and p not in allowed and not p.startswith(str(HERE)+'/'):
            denied.append(p);raise RuntimeError('read outside exact frozen scope')
    sys.addaudithook(guard)
    data={}
    for f in scope['data_files'][:4]:
        b=Path(f['path']).read_bytes();check(digest(b)==f['sha256'],'metadata changed');data[Path(f['path']).name]=b
    receipt=json.loads(data['in-worker-audit-receipt.json']);audit=json.loads(data['decision-evidence-audit.json'])
    check(receipt['accepted'] is True and audit['accepted'] is True and audit['evidence_complete'] is True
          and receipt['attempt_id']==scope['attempt_id'] and receipt['source']['commit']==scope['source_commit'],'native receipt invalid')
    check(receipt['audit_report']==scope['data_files'][1],'receipt audit binding')
    decisions=audit['n5_grasp_timing_audit']['decisions'];check(len(decisions)==15,'decision count')
    expected={d['decision_id']:d for d in decisions}
    index=[json.loads(x) for x in data['events.jsonl'].decode().splitlines()]
    by_bundle={x['bundle']:x for x in index}
    metrics={x['global_step']:x for x in map(json.loads,data['eds_metrics.jsonl'].decode().splitlines())}
    receipt_files=receipt['evidence']['files'];metered={Path(x['path']).name:x['sha256'] for x in receipt_files}
    for f in scope['data_files']:
        if Path(f['path']).suffix=='.pt' or Path(f['path']).name=='events.jsonl':check(metered[Path(f['path']).name]==f['sha256'],'metered input hash')
    rows=[];batches=[];seen=set();total_links=0
    for f in scope['data_files'][4:]:
        b=Path(f['path']).read_bytes();check(digest(b)==f['sha256'],'bundle changed')
        payload=torch.load(io.BytesIO(b),map_location='cpu',weights_only=True);check(payload['schema']=='qd-ed-decision-evidence-v1','bundle schema')
        events=payload['events'];idx=by_bundle[Path(f['path']).name]
        check([{k:e[k] for k in ('sequence','event','decision_id','global_step','reset_sequence')} for e in events]==idx['events'],'index event identity')
        kinds=collections.defaultdict(list);seq={}
        for e in events:kinds[e['event']].append(e);seq[e['sequence']]=e
        def one(kind):check(len(kinds[kind])==1,'one '+kind);return kinds[kind][0]
        final=one('final_selection');did=final['decision_id'];step=final['global_step'];d=expected[did]
        check(did not in seen and step==d['global_step'],'decision duplicate or step');seen.add(did)
        canonical=kinds['canonical_candidate_batch'];check([e['values']['iter_idx'] for e in canonical]==list(range(-1,10)),'canonical 11 coverage')
        check(len(d['canonical_sources'])==11 and len(d['parent_associations'])==10,'native association coverage')
        known={};batch_rows=[];round_rows=[]
        parents={e['values']['iter_idx']:e for e in kinds['parent_allocation']}
        allocations={e['values']['iter_idx']:e for e in kinds['archive_parent_allocation']}
        check(set(parents)==set(allocations)==set(range(10)),'parent rounds')
        assoc={p['iter_idx']:p for p in d['parent_associations']}
        for ce,cs in zip(canonical,d['canonical_sources']):
            v=ce['values'];i=v['iter_idx'];actions=v['candidates'];score=seq[cs['scoring_batch_id']]
            check(cs['iter_idx']==i and cs['canonical_sequence']==ce['sequence'] and score['decision_id']==did
                  and tuple(actions.shape)==(16,64,128) and actions.dtype==torch.bfloat16
                  and same(actions,score['values']['samples']),'canonical scoring binding')
            eff=[e for e in kinds['effective_quality'] if e['values']['scoring_batch_id']==score['sequence']]
            check(len(eff)==1,'effective quality binding');ev=eff[0]['values'];costs=ev['costs']
            check(ev['quality_mode']=='actuator_clipped_provider_v1' and same(ev['quality'],v['effective_quality'])
                  and same(costs,-v['effective_quality']),'native cost binding')
            decoded=decoder.rdt_action_to_libero_raw(actions[:,:8,:]);counts=(decoded[:,:,6]>0).sum(1)
            check(torch.equal(decoded[:,:,6]>0,actions[:,:8,10]>=0) and bool(torch.isfinite(actions[:,:8,10]).all()),'decoder sign')
            if i>=0:
                pa=parents[i];al=allocations[i];pv=pa['values'];av=al['values'];pr=assoc[i]
                check(pr['parent_sequence']==pa['sequence'] and pr['allocation_sequence']==al['sequence']
                      and al['sequence']<pa['sequence']<score['sequence']<ce['sequence'],'parent association order')
                pop=pv['source_population'];pc=pv['source_costs'];pq=pv['source_quality']
                check(same(pc,av['parent_costs']) and same(pq,av['parent_rewards']) and pv['elite_count']==0
                      and torch.equal(pv['parent_indices'],torch.arange(16)) and same(pv['parent_cell_ids'],av['parent_cell_ids'])
                      and pv['source_fingerprints']==av['parent_fingerprints'],'native parent allocation values')
                pn=(decoder.rdt_action_to_libero_raw(pop[:,:8,:])[:,:,6]>0).sum(1);slots=[]
                for slot,action in enumerate(pop):
                    matches=pr['slots'][slot]['matching_occurrence_ids'];check(matches and pr['slots'][slot]['slot']==slot,'parent slot ids')
                    aid=native(action)['sha256']
                    for oid in matches:
                        old=known[oid];check(old['native_action_sha256']==aid and old['native_cost']==float(pc[slot])
                            and old['native_quality']==float(pq[slot]) and old['positive_count']==int(pn[slot]),'parent exact prior native association')
                    slots.append({'slot':slot,'cell':int(av['parent_cell_ids'][slot]),'positive_count':int(pn[slot]),'native_action_sha256':aid,
                        'native_cost':float(pc[slot]),'matching_prior_occurrence_ids':matches})
                previous=batch_rows[-1]['positive_candidates'];parentyes=int((pn>0).sum());offspringyes=int((counts>0).sum())
                round_rows.append({'iter_idx':i,'allocation_sequence':al['sequence'],'parent_sequence':pa['sequence'],
                    'parent_costs':native(pc),'parent_positive_counts':pn.tolist(),**summary(pn,pc),
                    'offspring_canonical_sequence':ce['sequence'],'offspring_positive_candidates':offspringyes,
                    'previous_canonical_positive_candidates':previous,
                    'observed_transition':('previous_pool_positive_but_allocated_pool_all_nonpositive' if previous and not parentyes else
                        'allocated_pool_positive_but_offspring_pool_all_nonpositive' if parentyes and not offspringyes else
                        'allocated_pool_all_nonpositive_but_offspring_positive' if not parentyes and offspringyes else 'no_pool_level_loss_or_emergence'),
                    'parent_to_offspring_count_changes':{'positive_to_zero':int(((pn>0)&(counts==0)).sum()),
                        'zero_to_positive':int(((pn==0)&(counts>0)).sum())},'slots':slots,
                    'unique_archive_insertion_cause':'Unknown; original insertion occurrences were not recorded'})
                total_links+=16
            nr=[]
            for j,action in enumerate(actions):
                oid=v['occurrence_ids'][j];rec={'row':j,'occurrence_id':oid,'native_action_sha256':native(action)['sha256'],
                    'positive_count':int(counts[j]),'native_cost':float(costs[j]),'native_quality':float(v['effective_quality'][j])}
                check(oid not in known,'duplicate occurrence');known[oid]=rec;nr.append(rec)
            br={'decision_id':did,'global_step':step,'iter_idx':i,'canonical_sequence':ce['sequence'],'scoring_sequence':score['sequence'],
                'positive_counts':counts.tolist(),'native_costs':native(costs),**summary(counts,costs),'rows':nr}
            batch_rows.append(br);batches.append(br)
        fv=final['values'];tv=fv['terminal_population'];pop=fv['population'];costs=tv['native_costs'];selected=fv['selected_index']
        check(same(pop,canonical[-1]['values']['candidates']) and native(costs)==d['terminal_native_costs']
              and selected==d['selected_index']==metrics[step]['selected_idx'] and tv['selected_occurrence_id']==batch_rows[-1]['rows'][selected]['occurrence_id'],
              'terminal binding')
        pos=pop[:,:8,10]>=0;check(torch.equal(tv['grasp_selection']['positive_commands'],pos),'saved decoded terminal positive mask')
        pd=one('policy_action_decode')['values'];committed=one('decision_committed')['values']
        actual=decoder.decode_rdt_libero_action_chunk(pop[selected:selected+1].float(),8)
        check(same(actual,pd['action_chunk']) and same(actual,committed['action_chunk'])
              and same(pd['selected_latent'],pop[selected:selected+1].float()),'saved selected decoded commands')
        archive=fv['archive_reference'];ap=archive['population'];ac=archive['costs'];an=(decoder.rdt_action_to_libero_raw(ap[:,:8,:])[:,:,6]>0).sum(1)
        ar=[];check(len(d['archive_associations'])==len(ap),'archive association count')
        for j,action in enumerate(ap):
            matches=d['archive_associations'][j]['matching_occurrence_ids'];aid=native(action)['sha256'];check(matches,'archive association missing')
            for oid in matches:
                old=known[oid];check(old['native_action_sha256']==aid and old['native_cost']==float(ac[j]) and old['positive_count']==int(an[j]),'archive native association')
            ar.append({'slot':j,'cell':int(archive['cell_ids'][j]),'positive_count':int(an[j]),'native_cost':float(ac[j]),
                'matching_prior_occurrence_ids':matches,'native_action_sha256':aid})
        initial=batch_rows[0]['positive_candidates'];terminal=batch_rows[-1]['positive_candidates'];allpos=[r['positive_candidates'] for r in batch_rows]
        selected_count=int((actual[0,:,6]>0).sum())
        category=('absent_in_every_observed_canonical_pool' if not any(allpos) else
                  'initially_absent_later_appears_then_terminal_absent' if not initial and not terminal else
                  'initially_present_terminal_absent' if initial and not terminal else
                  'terminal_available_but_selected_nonpositive' if not selected_count else 'terminal_available_and_selected_positive')
        rows.append({'decision_id':did,'global_step':step,'bundle':f,'initial_positive_candidates':initial,
            'canonical_positive_candidate_sequence':allpos,'canonical_histograms_0_to_8':[r['histogram_0_to_8'] for r in batch_rows],
            'allocated_parent_positive_candidate_sequence':[r['positive_candidates'] for r in round_rows],
            'final_archive_positive_candidates':int((an>0).sum()),'terminal_positive_candidates':terminal,
            'selected_index':selected,'selected_positive_commands':selected_count,'selected_native_cost':float(costs[selected]),
            'selected_occurrence_id':tv['selected_occurrence_id'],'native_final_eligible_indices':tv['grasp_selection']['eligible_indices'],
            'recorded_selected_command_count':int((actual[0,:d['actual_prefix_length'],6]>0).sum()),
            'actual_prefix_length_confirmed_by_native_audit':d['actual_prefix_length'],
            'selected_decoded_commands':actual[0,:,6].tolist(),'category':category,
            'rounds':round_rows,'archive':{'costs':native(ac),'positive_counts':an.tolist(),**summary(an,ac),'slots':ar},
            'terminal':batch_rows[-1],'initial':batch_rows[0],
            'raw_gripper_zero_values':sum(int((ce['values']['candidates'][:,:8,10]==0).sum()) for ce in canonical)})
    rows.sort(key=lambda x:x['global_step']);batches.sort(key=lambda x:(x['global_step'],x['iter_idx']))
    check(len(rows)==15 and len(batches)==165 and len(seen)==15 and total_links==2400,'bounded coverage totals')
    check(not torch.cuda.is_initialized() and not denied,'CPU/scope guard')
    totals={'decisions':15,'canonical_batches':165,'canonical_candidates':2640,'decoded_canonical_commands':2640*8,
        'parent_rounds':150,'parent_slots_bound_to_native_prior_occurrences':total_links,
        'canonical_histogram_0_to_8':[sum(r['histogram_0_to_8'][i] for r in batches) for i in range(9)],
        'categories':dict(collections.Counter(r['category'] for r in rows)),
        'terminal_absent_steps':[r['global_step'] for r in rows if not r['terminal_positive_candidates']],
        'initial_absent_steps':[r['global_step'] for r in rows if not r['initial_positive_candidates']],
        'terminal_positive_unselected_steps':[r['global_step'] for r in rows if r['terminal_positive_candidates'] and not r['selected_positive_commands']],
        'all_canonical_absent_steps':[r['global_step'] for r in rows if not any(r['canonical_positive_candidate_sequence'])]}
    result={'schema':'n23-gripper-availability-readonly-screen-v1','attempt_id':scope['attempt_id'],'source_commit':scope['source_commit'],
        'scope':ref(SCOPE),'script':ref(__file__),'input_refs':scope['data_files'],'source_refs':scope['source_files'],
        'cpu_threads':2,'cuda_initialized':False,'blocked_reads':denied,'elapsed_cpu_process_wall_seconds':time.monotonic()-start,
        'semantics':{'positive':'native latent index10 >=0 -> unchanged decoder command +1; first8 commands only',
            'costs':'stored native effective costs, unchanged; comparisons only, no quality or trajectory recomputation',
            'association':'exact recorded parent/terminal-archive tensor matches with all accepted-audit occurrence aliases; unique insertion lineage Unknown',
            'temporal':'initial batch iter_idx=-1; ten actual allocations then ten recorded offspring batches iter_idx0..9'},
        'totals':totals,'decisions':rows,'batches':batches,
        'limitations':['Positive is command sign only, not closure feedback, contact, grasp usefulness, or success.',
            'No new geometry or quality was computed, and no action was executed.',
            'Allocated parent pools are observed; intermediate complete archive snapshots/replacement events are absent. Unique insertion/replacement causality is Unknown.',
            'Same native action with multiple prior occurrence matches is retained as multiple aliases, never unique ancestry.',
            'Parent slot versus offspring row is the recorded ordered source/offspring association, not isolation of a particular ED update cause.',
            'Selected full eight-command chunk matches stored decode/commit; actual dispatched prefix length is inherited from accepted native audit, without expanding bundle scope.',
            'One already exposed failed task0 path, no control comparison or generalization evidence.']}
    out=HERE/'screen-result-v1.json';check(not out.exists(),'do not overwrite closed result');out.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    with (HERE/'decisions-v1.csv').open('w',newline='') as fp:
        writer=csv.writer(fp);writer.writerow(['step','initial_positive_candidates','canonical_positive_candidates_by_batch','allocated_parent_positive_candidates','final_archive_positive_candidates','terminal_positive_candidates','selected_index','selected_positive_commands','category'])
        for r in rows:writer.writerow([r['global_step'],r['initial_positive_candidates'],json.dumps(r['canonical_positive_candidate_sequence']),json.dumps(r['allocated_parent_positive_candidate_sequence']),r['final_archive_positive_candidates'],r['terminal_positive_candidates'],r['selected_index'],r['selected_positive_commands'],r['category']])
    with (HERE/'batches-v1.csv').open('w',newline='') as fp:
        writer=csv.writer(fp);writer.writerow(['step','iteration',*[f'positive_count_{i}' for i in range(9)],'positive_candidates','positive_commands','min_positive_native_cost','min_zero_positive_native_cost'])
        for r in batches:writer.writerow([r['global_step'],r['iter_idx'],*r['histogram_0_to_8'],r['positive_candidates'],r['positive_commands'],r['min_positive_native_cost'],r['min_zero_positive_native_cost']])
    print(json.dumps({'result':ref(out),'totals':totals,'cuda_initialized':False,'blocked_reads':denied},indent=2))

if __name__=='__main__':run()
