"""Metadata-only historical attestation. Never follows evidence tensor references."""
import hashlib
import json
import math
from pathlib import Path

BASE='5a65ef15968cc68c82314e8c0773b3365ad45fa0'
OLD='N25_ACTUATOR_CLIPPED_RBF_DEV_20260930'
COHORT='N25_ACTUATOR_CLIPPED_RBF_DEV_INFRA_CONTINUATION_V1_20260930'
FAILED='rdt-qd-ed-final-20260921T093925Z__n25_dev_t04_n23_20260930__8b236af507d8'
OLD_SECONDS=8201.788167113322
FAILED_SECONDS=1801.4751812220784
EXPECTED_COUNTS={'C0':{'audited':5,'success':0},'Q0':{'audited':5,'success':0},'N23':{'audited':4,'success':0},'N25':{'audited':4,'success':1}}
FROZEN={'review':'a0b225efd8e35c17b5c6e801c3188a63b178079b7d31274f8b189a5641c59052',
 'result':'8005d67dc8cc04c764838d703c06dd8e14aeeae6b2312ba5bfe9b483228ac3b1',
 'plan':'1f0c94ccd3458a3a786acb9525728a1b64e3df439e4f920731f6566dd3a95eb3',
 'source':'fafcb0d881c95d567cb14a6690145d4ad933abc84a5e0175dfbe1512efd836ee'}
ARMS=('C0','Q0','N23','N25')
UNKNOWN={'native_audit_status':'UNKNOWN_MISSING','all_non_transport_gates_verified':False,
 'api_only_causal_attribution':'UNPROVEN','accept_original_as_scientific_result':False,
 'retroactive_native_repair_authorized':False,'unknown_token_calls':6}

def require(ok,msg):
    if not ok:raise ValueError(msg)

def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}
def same_ref(a,b):return a['sha256']==b['sha256'] and Path(a['path']).resolve()==Path(b['path']).resolve()
def identity(row):return {k:row[k] for k in ('split','iteration','profile','task_id','env_seed','policy_seed','init_index')}

class Reader:
    """One explicitly inventoried metadata universe, bounded total bytes, no payload follow."""
    def __init__(self,records):
        require(isinstance(records,list) and 0<len(records)<=512,'metadata inventory bound')
        self.records={str(Path(r['path']).resolve()):r for r in records};self.cache={};self.bytes=0
        require(len(self.records)==len(records),'duplicate metadata path')
        for p,r in self.records.items():
            require(set(r)=={'path','sha256'} and Path(p).suffix in {'.json','.jsonl','.txt'},'metadata file type')
            require(not any(x in Path(p).parts for x in ('decision_evidence','images','videos')),'payload directory forbidden')
    def read_bytes(self,reference):
        p=Path(reference['path']);key=str(p.resolve())
        require(set(reference)=={'path','sha256'} and p.is_absolute() and key in self.records
            and same_ref(reference,self.records[key]),'uninventoried metadata reference')
        if key not in self.cache:
            require(p.is_file() and not p.is_symlink(),'metadata missing/symlink')
            size=p.stat().st_size;require(0<=size<=16*1024*1024 and self.bytes+size<=128*1024*1024,'metadata byte bound before read')
            with p.open('rb') as stream:b=stream.read(size+1)
            require(len(b)==size,'metadata changed while reading');self.bytes+=len(b)
            require(hashlib.sha256(b).hexdigest()==reference['sha256'],'metadata hash changed');self.cache[key]=b
        return self.cache[key]
    def json(self,r):return json.loads(self.read_bytes(r))
    def lines(self,r):return [json.loads(s) for s in self.read_bytes(r).splitlines() if s.strip()]

def absence(path):
    p=Path(path);require(not p.exists() and not p.is_symlink(),'delayed audit writer or linked absence')
    return {'path':str(p.resolve()),'present':False,'sha256':None}

def verify_absences(rows):
    require(len(rows)==2 and {Path(r['path']).name for r in rows}=={'in-worker-audit-receipt.json','decision-evidence-audit.json'},'two named absent audits required')
    for row in rows:require(row==absence(row['path']),'absence record changed')

def process_cleanup(processes,*,proc=Path('/proc')):
    """Public boot/stat/cmdline only; no signalling or child creation."""
    boot=(proc/'sys/kernel/random/boot_id').read_text().strip();checked=[];owned=set()
    for p in processes:
        require(set(p)=={'pid','proc_start_ticks','boot_id'} and type(p['pid']) is int and p['pid']>1
            and isinstance(p['proc_start_ticks'],str) and p['proc_start_ticks'].isdigit(),'process identity malformed')
        owned.add(p['pid']);stat=proc/str(p['pid'])/'stat'
        if p['boot_id']==boot and stat.exists():
            fields=stat.read_text().rsplit(')',1)[1].split()
            require(fields[19]!=p['proc_start_ticks'],'original owned process still present (including zombie)')
        checked.append(p)
    # Original workers use start_new_session=True. Detect surviving process groups
    # and explicit original attempt/supervisor command identities, including reparented children.
    for entry in proc.iterdir():
        if not entry.name.isdigit():continue
        try:
            fields=(entry/'stat').read_text().rsplit(')',1)[1].split()
            cmd=(entry/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        except (FileNotFoundError,ProcessLookupError):continue
        require(not (any(p['boot_id']==boot for p in processes) and (int(fields[2]) in owned or int(fields[3]) in owned)), 'owned process group/session remains')
        require(FAILED not in cmd and 'qd_ed_n25_supervise.py' not in cmd,'original owned command remains')
    return {'boot_id':boot,'checked_processes':checked,'no_owned_processes':True}

def groups(events):
    d={}
    for e in events:d.setdefault(e['attempt_id'],[]).append(e)
    return d

def failed_signature(final,stage):
    require(final['attempt_id']==FAILED and final.get('event')=='valid' and final.get('outcome_valid') is False
        and final.get('reason')=='TimeoutExpired' and final.get('compute_outcome')=='completed'
        and final.get('gpu_process_wall_seconds')==FAILED_SECONDS and final.get('retry_of') is None,'named terminal signature differs')
    for k,v in {'provider_logical_call_attempts':43,'provider_completed_turns':37,'provider_failed_calls':6,'provider_usage_complete_calls':37}.items():
        require(type(final.get(k)) is int and final[k]==v,'named provider counter differs: '+k)
    require(stage['schema']=='n25-public-stage-metadata-v1' and stage['attempt_id']==FAILED
        and stage.get('response_payloads_included') is False,'public Stage projection differs')
    att=stage['attestation'];require(att['root_terminal_review']['sha256']==FROZEN['review'] and att['source_stage_events']==stage['source_stage_events']
        and att['public_fields_only'] is True and att['all_logical_calls_included'] is True,'root projection attestation differs')
    calls=stage['calls'];require(len(calls)==43,'public logical call count differs')
    positions=[x['event_position'] for x in calls];require(all(type(n) is int and n>=0 for n in positions) and positions==sorted(set(positions)), 'public event positions differ')
    fails=[x for x in calls if x['query_ok'] is not True]
    require([x['global_step'] for x in fails]==[96,120,128,136,168,176],'six named failed steps differ')
    for x in calls:
        require(not any(k in x for k in ('raw_response','prompt','image','images','response')),'public projection contains excluded content')
        tr=x['transport'];require(tr['backend']=='codex_cli' and tr['auth_mode']=='chatgpt' and tr['model']=='gpt-6-astra'
            and tr['reasoning_effort']=='low' and tr['timeout_seconds']==180.,'provider semantics changed')
        require(x['codex_logical_call_attempts']==1,'logical call multiplicity')
        if x['query_ok'] is True:
            require(x['codex_completed_turns']==x['codex_usage_complete_calls']==1 and x['codex_failed_calls']==0,'successful usage incomplete')
        else:
            life=tr['lifecycle'];events=life['events'];kinds=[e['kind'] for e in events]
            require(x['query_status']=='error' and x['error']=='codex_timeout' and x['codex_completed_turns']==0
                and x['codex_usage_complete_calls']==0 and x['codex_failed_calls']==1,'failed call changed')
            require(life['schema']=='codex-stage-lifecycle-v1' and life['observation_complete'] is True
                and life['observer_error_category'] is None and life['timeout_observed_at'] is not None
                and life['first_completed_observed_at'] is None and life['first_complete_usage_observed_at'] is None
                and life['complete_usage_observed'] is False,'timeout lifecycle incomplete/different')
            timeline=[life[k] for k in ('request_started_at','spawn_started_at','spawn_returned_at','communicate_started_at','timeout_observed_at','cleanup_started_at','cleanup_returned_at','process_exit_observed_at','observer_finished_at')]
            require(all(type(v) in (int,float) and math.isfinite(v) for v in timeline) and timeline==sorted(timeline)
                and life['timeout_observed_at']-life['communicate_started_at']>=180.
                and type(x.get('codex_call_latency_s')) in (int,float) and math.isfinite(x['codex_call_latency_s']) and x['codex_call_latency_s']>=180.,'timeout interval/cleanup ordering differs')
            require(tr['event_types']==kinds and tr['item_types']==[v['item_kind'] for v in events if 'item_kind' in v]
                and all(type(v.get('observed_at')) in (int,float) and math.isfinite(v['observed_at']) for v in events)
                and [v['observed_at'] for v in events]==sorted(v['observed_at'] for v in events)
                and all(timeline[0]<=v['observed_at']<=timeline[-1] for v in events),'transport/lifecycle association differs')
            require(kinds[:2]==['thread.started','turn.started'] and all(e['kind'] in {'thread.started','turn.started','error','item.completed'} for e in events)
                and {e.get('error_category') for e in events[2:]}=={'stream_error','item_error'}
                and all(e.get('item_kind')=='error' for e in events if e['kind']=='item.completed'),'unexpected lifecycle fault')
    return {'failed_calls':fails,'failed_calls_sha256':canonical(fails),'public_projection_source':stage['source_stage_events'],**UNKNOWN}

def terminal_binding(final,row,plan,plan_ref,commit=BASE):
    require(final['identity']==identity(row) and final['episode_key']==row['episode_key']
        and final['plan_sha256']==plan_ref['sha256'] and final['source_commit']==commit
        and final['runtime_manifest_sha256']==plan['runtime_manifest_sha256']
        and final['profile_manifest_sha256']==plan['profiles_sha256']
        and final['runtime_inventory_sha256']==plan['runtime_inventory_sha256']
        and final['init_row_sha256']==row['init_row_sha256'] and final['physical_gpu']==7,'historical terminal binding differs')

def accepted_metadata(cell,final,row,plan,plan_ref,source,runtime,reader,*,historical=True):
    require(final.get('event')=='valid' and final.get('outcome_valid') is True
        and final.get('required_cost_telemetry_complete') is True and final.get('retry_of')==row.get('retry_of'),'import must be fully accepted primary')
    terminal_binding(final,row,plan,plan_ref,BASE if historical else source['commit'])
    require(cell['attempt_id']==final['attempt_id'] and cell['episode_key']==row['episode_key']
        and cell['task_id']==row['task_id'] and cell['profile']==row['profile'] and cell['success'] is final['success'],'accepted prefix association')
    require(reader.json(cell['attempt_result'])==final,'accepted terminal record differs')
    context=reader.json(cell['worker_context']);receipt=reader.json(cell['worker_receipt']);audit=reader.json(cell['audit'])
    require(context['source']==source and context['plan']==plan_ref and context['runtime']==runtime
        and context['attempt_id']==cell['attempt_id'] and context['episode_key']==cell['episode_key']
        and context['profile']==cell['profile'] and context['output_dir']==final['output_dir'],'historical context identity')
    require(receipt['accepted'] is True and audit['accepted'] is True and audit.get('evidence_complete') is True
        and receipt['main_exit_code']==0 and receipt['process_unchanged'] is True
        and receipt['context']==cell['worker_context'] and receipt['audit_report']==cell['audit']
        and receipt['source']==source and receipt['plan']==plan_ref and receipt['runtime']==runtime
        and receipt['attempt_id']==cell['attempt_id'] and receipt['profile']==cell['profile']
        and receipt['episode_key']==cell['episode_key'] and final['n23_worker_receipt']==cell['worker_receipt']
        and receipt['main_argv_sha256']==canonical(context['main_argv']),'historical receipt metadata binding')
    process=reader.json(ref_from_inventory(reader,Path(final['output_dir'])/'process.json'))
    proc={k:process[k] for k in ('pid','proc_start_ticks','boot_id')}
    require(process['attempt_id']==cell['attempt_id'] and receipt['process']==proc,'historical PID binding')
    start=reader.json(ref_from_inventory(reader,Path(final['output_dir'])/'eds_eval/in-worker-audit-start.json'))
    require(start=={'schema':'n23-worker-start-v1','process':proc,'context':cell['worker_context']},'historical audit start')
    evidence=receipt['evidence'];require(evidence['sha256']==canonical(evidence['files']),'recorded evidence digest changed')
    require(all(set(q)=={'path','sha256'} and not Path(q['path']).is_absolute() and '..' not in Path(q['path']).parts for q in evidence['files']), 'unsafe recorded evidence index')
    kind='cuda' if row['profile'] in {'N23','N25'} else 'cpu'
    require(receipt['audit_backend']['kind']==kind and audit['n23_arithmetic_backend']==receipt['audit_backend']
        and receipt['worker_cuda']['physical_gpu']==7 and receipt['worker_cuda']['physical_uuid']=='GPU-48473162-9548-1a19-04aa-ea86c5349187','historical audit backend')
    require(0<=receipt['audit_seconds']<=receipt['worker_wall_seconds'] and receipt['worker_wall_seconds']<=final['gpu_process_wall_seconds'],'historical audit wall association')
    return {'cell':cell,'process':proc,'native':receipt['n25_native_counts'],'auxiliary':receipt['n25_auxiliary'],
        'evidence_index':evidence,'reliance':'Original metered audit + frozen root terminal review; no tensor reread or native re-audit.'}

def ref_from_inventory(reader,path):
    key=str(Path(path).resolve());require(key in reader.records,'missing required metadata inventory: '+key);return reader.records[key]


def measured_native_metadata(final,receipt,audit):
    """Public result/receipt gates only. No numerical replay and no tensor reads."""
    counts=receipt['n25_native_counts'];arm=final['identity']['profile'];g=counts['guided_decisions']
    require(type(g) is int and g>=0,'guided count missing')
    require(not audit.get('errors') and audit.get('evidence_complete') is True,'native report completeness')
    if arm in ('N23','N25'):
        require(counts['parent_rounds_verified']==10*g and counts['score_batches_verified']==11*g and counts['candidate_scores_verified']==176*g,'fixed QD/ED canonical counts')
    gate=audit.get('n25_actuator_clipped_rbf_audit')
    if arm=='N25':
        require(gate is not None and gate['schema']=='n25-native-rbf-audit-v1' and gate['accepted'] is True and gate['guided_decisions']==g,'N25 cannot downgrade missing native markers')
        for k in ('all_call_summaries_verified','witness_calls_verified','zero_gradient_calls','clipped_components'):
            require(type(gate[k]) is int and gate[k]>=0 and gate[k]==counts[k],'N25 scalar native gate differs')
        require(gate['all_call_summaries_verified']==final['rbf_gradient_calls']
            and gate['zero_gradient_calls']<=gate['all_call_summaries_verified'] and gate['clipped_components']<=384*gate['all_call_summaries_verified']
            and gate['witness_calls_verified']<=11 and gate['witness_numeric_bytes']<=225280
            and len(gate['witness_checks'])==gate['witness_calls_verified'] and all(q['accepted'] is True for q in gate['witness_checks']), 'bounded native witness gate differs')
    else:require(not gate,'control has unexpected N25 gate')
    transport=final['stage_transport']
    require((transport['backend'],transport['auth_mode'],transport['model'],transport['reasoning_effort'],transport['timeout_seconds'])
        ==('codex_cli','chatgpt','gpt-6-astra','low',180.) and final['guidance_api_request_attempts']==final['grounding_api_request_attempts']==0,
        'Codex-only frozen transport differs')
    return counts,receipt['n25_auxiliary']
