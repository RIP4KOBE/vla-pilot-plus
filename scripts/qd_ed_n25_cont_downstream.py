#!/usr/bin/env python3
"""Non-authorizing, bounded historical logical-Dev metadata evidence only."""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from scripts import qd_ed_n25_cont_evidence as e,qd_ed_n25_cont_contract as c
from scripts import qd_ed_n25_cont_terminal as terminal,qd_ed_n25_cont_bridge as bridge

HISTORICAL='6f796358aa84d53e9c8a04859f7d19352c9db7fe'
PROTOCOL_SHA='0e4ce396125c07a6105a6f90cb2a52835d331ac91ce31e31746f633b1f500213'
DOC='experiments/qd_ed_n25_continuation_downstream'
DISPOSITIONS={'ELIGIBLE_FOR_SEPARATELY_FROZEN_VALIDATION','REJECT','REJECT_NUMERIC_FUTILITY'}
REFS={'old_source','source','seal','seal_review','source_bridge','source_review','authority','release','plan',
      'status','result','root_review','controller','journal_projection','resource_projection'}


def digest(b):return hashlib.sha256(b).hexdigest()


class MetadataReader(e.Reader):
    def __init__(self,records):
        forbidden={'events.jsonl','stage_events.jsonl','stage_responses.jsonl','attempt-ledger.jsonl','gpu-healthcheck-ledger.jsonl'}
        e.require(all(Path(q['path']).name not in forbidden for q in records),'raw Stage/native index or full private ledger is forbidden')
        super().__init__(records)


class GitObjects:
    """Finite local immutable blob reader. Only root's later CLI invokes Git."""
    def __init__(self,root):self.root=Path(root);self.allowed={(HISTORICAL,bridge.DOC+'/original-source-v1.json')};self.cache={};self.bytes=0
    def authorize(self,objects):
        for commit,path in objects:
            e.require(commit in {e.BASE,HISTORICAL} and not Path(path).is_absolute() and '..' not in Path(path).parts,'unsafe historical Git object')
            self.allowed.add((commit,path))
    def __call__(self,commit,path):
        e.require((commit,path) in self.allowed,'unlisted Git object')
        if (commit,path) not in self.cache:
            name=commit+':'+path
            size=int(subprocess.check_output(['git','cat-file','-s',name],cwd=self.root,text=True,timeout=10))
            e.require(0<=size<=16*1024*1024 and self.bytes+size<=128*1024*1024,'source object size bound')
            b=subprocess.check_output(['git','cat-file','blob',name],cwd=self.root,timeout=10)
            e.require(len(b)==size,'source object size differs');self.cache[commit,path]=b;self.bytes+=size
        return self.cache[commit,path]


def historical_sources(old,new,objects):
    anchored=json.loads(objects(HISTORICAL,bridge.DOC+'/original-source-v1.json'))
    e.require(old==anchored and old['commit']==e.BASE and len(old['files'])==257 and old['sha256']==e.canonical(old['files']), 'historical5a source differs')
    paths={q['path'] for q in old['files']}|bridge.EXTRAS
    e.require(new['commit']==HISTORICAL and len(new['files'])==271 and {q['path'] for q in new['files']}==paths
        and new['files']==sorted(new['files'],key=lambda q:q['path']) and new['sha256']==e.canonical(new['files']), 'historical6f closed source differs')
    objects.authorize((s['commit'],q['path']) for s in (old,new) for q in s['files'])
    for source in (old,new):
        for q in source['files']:e.require(set(q)=={'path','sha256'} and digest(objects(source['commit'],q['path']))==q['sha256'],'historical Git bytes differ')
    reverse=json.loads(objects(HISTORICAL,bridge.DOC+'/reverse-routes-v1.json'))
    e.require(reverse['base_commit']==e.BASE and {v['path'] for v in reverse['files']}==set(bridge.ROUTES),'historical reverse scope differs')
    changes=[];same=[]
    for q in old['files']:
        path=q['path'];before=objects(e.BASE,path);after=objects(HISTORICAL,path)
        if path not in bridge.ROUTES:e.require(before==after,'historical scientific byte drift');same.append(q);continue
        row=next(x for x in reverse['files'] if x['path']==path);lines=after.decode().splitlines(keepends=True)
        e.require(row['old_sha256']==digest(before) and row['new_sha256']==digest(after),'historical route hash differs')
        for edit in reversed(row['edits']):
            a,z=edit['new_start'],edit['new_end'];e.require(''.join(lines[a:z])==edit['new'],'historical reverse segment differs');lines[a:z]=edit['old'].splitlines(keepends=True)
        e.require(''.join(lines).encode()==before,'historical whole-file reverse differs')
        a,z=bridge.functions(before.decode()),bridge.functions(after.decode())
        e.require(set(a)==set(z) and {k for k in a if a[k]!=z[k]}==bridge.ROUTES[path],'historical four-function boundary differs')
        changes.append({'path':path,'original_sha256':digest(before),'new_sha256':digest(after),'functions':sorted(bridge.ROUTES[path]),'reverse_exact':True})
    # Current pure reader/helper modules must still have their exact historical bytes.
    # Current runner/worker HEAD is not required to be historical; their relevant
    # primitive function bodies, rather than administrative routes, are bound below.
    for path in bridge.MODULES|{'scripts/qd_ed_n25_backend.py','scripts/qd_ed_n25_reference.py','scripts/qd_ed_audit_backend.py','scripts/qd_ed_n25_report.py','scripts/qd_ed_n25_contract.py'}:
        e.require((ROOT/path).read_bytes()==objects(HISTORICAL,path),'current continuation helper drift')
    worker='scripts/qd_ed_n23_worker.py'
    oldfunc=bridge.functions(objects(HISTORICAL,worker).decode());current=bridge.functions((ROOT/worker).read_text())
    for name in ('require','sha','canonical_sha','read_ref'):
        e.require(current[name]==oldfunc[name],'current pure worker primitive drift')
    return {'same_files':same,'shared_routes':changes}


def same(a,b):e.require(e.same_ref(a,b),'reference alias/hash differs')


def check_current_matching_events(projection,events,resource_projection,resources):
    """Pure release-time hook: caller supplies ONLY already-filtered matching events."""
    e.require(all(x.get('identity',{}).get('iteration') in {e.OLD,c.COHORT} for x in events),'caller must filter Dev-only events')
    e.require([x for x in events if x['identity']['iteration']==e.OLD]==projection['original_events']
        and [x for x in events if x['identity']['iteration']==c.COHORT]==projection['continuation_events'],'later/changed matching Dev journal')
    rid=resource_projection['resource_id'];kind=resource_projection['resource_kind']
    e.require(all(x.get('resource_id')==rid or x.get('kind')==kind for x in resources),'caller must filter proof-resource events')
    e.require(resources==resource_projection['events'],'later/changed matching resource journal')


def projection(reader,reference,schema,root_review):
    record=reader.json(reference)
    e.require(record['schema']==schema and record['root_terminal_review']==root_review
        and record['all_matching_events_included'] is True and record['protected_events_included'] is False
        and isinstance(record['collected_at'],str) and bool(record['collected_at']),'root projection attestation differs')
    for k in ('source_ledger','collector'):
        q=record[k];e.require(set(q)=={'path','sha256'} and Path(q['path']).is_absolute()
            and isinstance(q['sha256'],str) and len(q['sha256'])==64,'projection source reference malformed')
    # These refs are root-attested extraction provenance, never followed.
    return record


def cost_summary(attempts,fields):
    result={a:{k:{'observed_total':0,'observed_attempts':0,'missing_attempts':[]} for k in fields} for a in c.ARMS}
    unknown=0;missing=[]
    for item in attempts:
        f=item['terminal'];logical=f.get('provider_logical_call_attempts');usage=f.get('provider_usage_complete_calls')
        if type(logical) is int and type(usage) is int and 0<=usage<=logical:unknown+=logical-usage
        else:missing.append(f['attempt_id'])
        for k,slot in result[item['profile']].items():
            value=f.get(k)
            if type(value) in (int,float) and math.isfinite(value) and value>=0:slot['observed_total']+=value;slot['observed_attempts']+=1
            else:slot['missing_attempts'].append(f['attempt_id'])
    return {'all_attempt_costs':result,'known_unknown_token_calls':unknown,'unknown_token_calls':None if missing else unknown,
        'unmeasured_token_call_attempts':missing,'all_attempt_token_usage_complete':not missing and unknown==0}


def settled_resource(reader,reference,source,runtime,resource_projection):
    from scripts import qd_ed_n25_backend as backend,qd_ed_audit_backend as audit_backend,qd_ed_n25_reference as arithmetic_reference
    e.require(backend.c is c.old and backend.w is terminal.w,'historical proof shared helper identity differs')
    for module in (backend,backend.c,audit_backend,arithmetic_reference):
        e.require(Path(module.__file__).resolve()==ROOT/'scripts'/Path(module.__file__).name,'historical proof helper shadowing')
    proof=reader.json(reference)
    e.require(set(proof)=={'schema','accepted','source','runtime','plan','report','process','terminal'}
        and proof['schema']=='n25-metered-tensor-proof-v1' and proof['accepted'] is True
        and proof['source']==source and proof['runtime']==runtime,'historical proof source/scope differs')
    plan,report,process,final=[reader.json(proof[k]) for k in ('plan','report','process','terminal')]
    # Existing validate_report performs JSON identity/case/coverage checks only.
    # Its one fixed plan rehash is explicitly inventoried and path-bound first.
    same(proof['plan'],e.ref_from_inventory(reader,backend.PLAN))
    e.require(plan['source']==source and plan['runtime']==runtime and plan['frozen'] is True,'historical resource plan differs')
    events=resource_projection['events'];rid=plan['resource_id']
    e.require(resource_projection['resource_id']==rid and resource_projection['resource_kind']==backend.KIND
        and resource_projection['event_count']==len(events)==3
        and [x['event'] for x in events]==['reserved','dispatched','completed']
        and all(x['resource_id']==rid and x['kind']==backend.KIND and x['plan']==proof['plan'] for x in events), 'settled proof chronology differs')
    e.require(events[-1]==final and final['report']==proof['report'] and final['process']==proof['process']
        and process['resource_id']==rid and final['cleanup_complete'] is True and final['cost_measurement_complete'] is True
        and 0<=report['worker_wall_seconds']<=final['gpu_process_wall_seconds']<=100,'settled resource cost differs')
    backend.validate_report(report,plan,process)
    return {'reference':reference,'source_commit':e.BASE,'resource_id':rid,'gpu_process_wall_seconds':final['gpu_process_wall_seconds'],
        'episode_attempts':0,'new_proof_executed':False,'reliance':'Historical metered JSON report, root source review and settled resource ledger; no numeric replay.'}


def build(data,*,objects=None,cleanup=e.process_cleanup):
    e.require(data['schema']=='n25-logical-dev-evidence-input-v1' and data['root_authorized'] is True
        and set(data['references'])==REFS,'root-reviewed closed metadata inventory required')
    owner=Path(data['owning_root']).resolve()
    e.require(owner==ROOT.resolve() and owner.name=='study_worktree' and c.SEAL.resolve().parent==c.RUN_DIR.resolve()
        and c.RUN_DIR.resolve()==owner.parent/'variants/n25_actuator_clipped_rbf/infrastructure-continuation-v1', 'same approved owning study path required')
    for module in (c,c.old,e,terminal,bridge,terminal.w,terminal.report,terminal.report.old_report):
        e.require(Path(module.__file__).resolve()==owner/'scripts'/Path(module.__file__).name,'historical helper imports must come from owning study')
    reader=MetadataReader(data['files']);refs=data['references'];get=lambda key:reader.json(refs[key])
    same(refs['seal'],e.ref_from_inventory(reader,c.SEAL));same(refs['plan'],e.ref_from_inventory(reader,c.PLAN))
    e.require(digest((ROOT/DOC/'protocol-v1.md').read_bytes())==PROTOCOL_SHA,'adapter protocol drift')
    e.require(refs['old_source']['sha256']==e.FROZEN['source'],'original source manifest reference differs')
    old,new=get('old_source'),get('source');objects=objects or GitObjects(owner);delta=historical_sources(old,new,objects)
    seal=get('seal');review=get('seal_review');parent=reader.json(seal['original_plan'])
    e.require(seal['original_source']==old and seal['historical_unknowns']==e.UNKNOWN and seal['original_disposition']=='INVALID_OR_INTERRUPTED'
        and seal['old_attempts']==19 and seal['old_recoveries']==0 and seal['old_gpu_seconds']==e.OLD_SECONDS
        and seal['counts']==e.EXPECTED_COUNTS and seal['failed_attempt']==e.FAILED,'original seal/Unknown differs')
    for key,refkey in (('root_terminal_review','review'),('original_result','result'),('original_plan','plan')):
        e.require(seal[key]['sha256']==e.FROZEN[refkey],'original frozen provenance differs')
    for q in seal['metadata_files']:reader.read_bytes(q)
    e.verify_absences(seal['failed_audits_absent']);cleanup(seal['processes'])
    original_result=reader.json(seal['original_result']);original_review=reader.json(seal['root_terminal_review'])
    e.require(original_result['decision']=='INVALID_OR_INTERRUPTED' and original_review['cohort_disposition']=='INVALID_OR_INTERRUPTED'
        and original_review['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION' and original_review['counts']==seal['counts']
        and original_result['attempts']==seal['all_old_attempts'] and original_result['accepted_cells']==[x['cell'] for x in seal['accepted_prefix']], 'original immutable terminal association differs')
    e.require(review=={'schema':'n25-continuation-root-seal-review-v1','accepted':True,'seal':refs['seal'],
        'protocol':{'path':str(c.PROTOCOL.resolve()),'sha256':c.PROTOCOL_SHA},'original_disposition':'INVALID_OR_INTERRUPTED',
        'history_is_metadata_attestation':True,'historical_unknowns':e.UNKNOWN,'gpu_authorized':False},'root seal review differs')
    b=get('source_bridge')
    e.require(b=={'schema':'n25-continuation-source-bridge-v1','old_source':old,'new_source':new,**delta,
        'historical_backend_proof':seal['historical_backend_proof'],'new_numerical_preflight':False,
        'interpretation':'Historical5a proof is not generated by new commit; unchanged science/native arithmetic plus reviewed administrative route bridge.'}, 'historical administrative source bridge differs')
    plan=get('plan');result=get('result');status=get('status');root_review=get('root_review');controller=get('controller')
    e.require(Path(parent['worktree']).resolve()==owner and Path(plan['worktree']).resolve()==owner
        and plan['source_commit']==HISTORICAL and plan['code_files']==new['files']
        and plan['episodes']==c.rows(seal) and plan['frozen'] is True,'historical owning plan/mapping differs')
    allowed={'source_commit','code_files','episodes','n25_cohort','n25_infrastructure_continuation','derived_from','frozen'}
    e.require(set(plan)==set(parent)|{'n25_infrastructure_continuation'} and all(plan[k]==parent[k] for k in parent if k not in allowed)
        and plan['derived_from']==seal['original_plan'] and plan['n25_cohort']=={'schema':'n25-continuation-audit-family-v1','worker_audit':c.WORKER_CONTRACT},'historical science/runtime plan fields changed')
    e.require(plan['n25_infrastructure_continuation']=={'schema':'n25-infrastructure-continuation-v1','cohort_id':c.COHORT,
        'protocol':{'path':str(c.PROTOCOL.resolve()),'sha256':c.PROTOCOL_SHA},'seal':refs['seal'],'final_review':refs['source_review'],
        'authority':refs['authority'],'limits':c.LIMITS,'historical_unknowns':e.UNKNOWN,'imports':18,'dispatchable':22},'historical plan authority chain differs')
    runtime=seal['runtime'];runtime_data=reader.json(runtime)
    e.require(Path(runtime_data['worktree']).resolve()==owner,'historical runtime owning alias differs')
    sr=get('source_review')
    e.require(sr=={'schema':'n25-continuation-source-runtime-review-v1','accepted':True,'source':new,'runtime':runtime,
        'protocol':{'path':str(c.PROTOCOL.resolve()),'sha256':c.PROTOCOL_SHA},'seal':refs['seal'],'root_seal_review':refs['seal_review'],
        'source_bridge':refs['source_bridge'],'historical_backend_proof':seal['historical_backend_proof'],
        'no_new_preflight':True,'gpu_authorized':False},'historical source review differs')
    authority=get('authority');old_authority=reader.json(seal['old_authority']);old_source_review=reader.json(parent['n25_cohort']['final_review'])
    e.require(old_source_review['source']==old and old_source_review['runtime']==seal['runtime'] and old_source_review['disposition']=='accepted'
        and old_source_review['backend_proof']==seal['historical_backend_proof'] and old_authority['source']==old and old_authority['runtime']==seal['runtime']
        and old_authority['local_gpu_hours']==22.,'original source/proof/authority lineage differs')
    budget=reader.json(authority['existing_budget_authority'])
    e.require(set(authority)=={'schema','cohort_id','source','runtime','protocol','seal','final_review','existing_budget_authority','caps','limits',
        'original_local_gpu_hours','old_gpu_seconds','remaining_local_gpu_hours','recorded_at','authority_interpretation','validation_authorized','formal_authorized'}
        and authority['schema']=='n25-continuation-authority-v1' and authority['cohort_id']==c.COHORT
        and authority['source']==new and authority['runtime']==runtime and authority['protocol']==sr['protocol']
        and authority['seal']==refs['seal'] and authority['final_review']==refs['source_review']
        and authority['existing_budget_authority']==old_authority['budget_authority'] and budget['caps']==authority['caps']==c.CAPS
        and authority['limits']==c.LIMITS and authority['old_gpu_seconds']==e.OLD_SECONDS and authority['original_local_gpu_hours']==22.
        and all(isinstance(authority[k],str) and authority[k].strip() for k in ('recorded_at','authority_interpretation'))
        and type(authority['remaining_local_gpu_hours']) in (int,float) and math.isfinite(authority['remaining_local_gpu_hours'])
        and 1840/3600<=authority['remaining_local_gpu_hours']<=22-e.OLD_SECONDS/3600
        and authority['validation_authorized'] is authority['formal_authorized'] is False,'historical finite continuation authority differs')
    release=get('release')
    e.require(release=={'schema':'n25-continuation-execution-release-v1','plan':refs['plan'],'source_commit':HISTORICAL,
        'cohort_id':c.COHORT,'authority':refs['authority'],'seal':refs['seal'],'episode_keys':[x['episode_key'] for x in plan['episodes']],
        'limits':c.LIMITS,'physical_gpu':7,'one_launch':True,'validation_authorized':False,'formal_authorized':False},'historical release differs')
    e.require(controller['schema']=='n25-continuation-controller-process-v1' and controller['plan']==refs['plan']
        and controller['release']==refs['release'] and controller['source_commit']==HISTORICAL,'controller provenance differs')
    cleanup([controller['process']])
    e.require(result['source_commit']==HISTORICAL and result['prefix_seal']==refs['seal'] and result['source_bridge']==refs['source_bridge']
        and result['reader']=={'path':str((ROOT/'scripts/qd_ed_n25_cont_report.py').resolve()),'sha256':dict((q['path'],q['sha256']) for q in new['files'])['scripts/qd_ed_n25_cont_report.py']}
        and result['controller_evidence']['consistent'] is True and result['decision'] in DISPOSITIONS,'only valid logical closure allowed')
    same(result['plan'],refs['plan']);same({k:result['terminal_status'][k] for k in ('path','sha256')},refs['status'])
    newkeys=[x['episode_key'] for x in result['accepted_cells'][18:]]
    e.require(status['schema']=='n25-continuation-supervisor-status-v1' and status['cohort_id']==c.COHORT
        and status['plan']==refs['plan'] and status['source_commit']==HISTORICAL and status['prefix_seal']==refs['seal']
        and status['completed_keys']==newkeys and status['protected_authorized'] is False
        and status['counts_success']=={a:result['counts'][a]['success'] for a in c.ARMS},'actual continuation status association differs')
    jp=projection(reader,refs['journal_projection'],'n25-current-dev-journal-projection-v1',refs['root_review'])
    rp=projection(reader,refs['resource_projection'],'n25-current-resource-projection-v1',refs['root_review'])
    old_events=reader.json(seal['old_ledger']);events=reader.json(result['ledger_snapshot'])
    e.require(jp['original_event_count']==len(jp['original_events']) and jp['continuation_event_count']==len(jp['continuation_events']), 'projection counts differ')
    check_current_matching_events(jp,old_events+events,rp,rp['events'])
    finals=[g[-1] for g in e.groups(events).values()]
    e.require(all([x['event'] for x in g]==['reserved','dispatched','valid'] and g[-1]['outcome_valid'] is True
        and g[-1]['required_cost_telemetry_complete'] is True and g[-1]['provider_token_usage_complete'] is True
        and type(g[-1]['success']) is bool and type(g[-1]['provider_logical_call_attempts']) is int
        and type(g[-1]['provider_usage_complete_calls']) is int and g[-1]['provider_logical_call_attempts']>=0
        and g[-1]['provider_logical_call_attempts']==g[-1]['provider_usage_complete_calls'] for g in e.groups(events).values()),'new invalid/incomplete usage cannot enter downstream')
    e.require(len(finals)==len(newkeys) and result['dispatched']==len(result['accepted_cells'])+1,'logical/cost denominator differs')
    e.require(status['attempts']==finals and status['outcomes']==[{'episode_key':f['episode_key'],'attempt_id':f['attempt_id'],'success':f['success']} for f in finals], 'status attempt/outcome evidence differs')
    for n,(row,final) in enumerate(zip(plan['episodes'],finals)):
        e.require(final['episode_key']==row['episode_key'] and final.get('retry_of')==row.get('retry_of')
            and final['budget_bucket']==row['budget_bucket'],'named retry/order/bucket differs')
        if n==0:e.require(final['retry_of']==e.FAILED,'named first repeat required')
    computed=terminal.review_existing(result,plan,seal,events,reader,new,cleanup=cleanup)
    extra={'result':refs['result'],'plan':refs['plan'],'source':new,'seal':refs['seal'],'ledger':result['ledger_snapshot'],'controller':refs['controller']}
    # Historical cleanup snapshot may differ in checked boot after reboot; its
    # measured identities/no-owned-processes must be accepted, with fresh checks above.
    expected={**computed,**extra};expected['cleanup']=root_review.get('cleanup')
    e.require(root_review==expected and root_review['cleanup']['no_owned_processes'] is True
        and root_review['cleanup']['checked_processes']==computed['cleanup']['checked_processes'], 'independent root terminal review differs')
    fields=terminal.report.old_report.COST_FIELDS
    summaries={k:cost_summary(v,fields) for k,v in (('old',seal['all_old_attempts']),('new',result['new_attempts']),('combined',result['attempts']))}
    e.require(result['new_attempts']==result['attempts'][19:] and len(result['new_attempts'])==len(finals),'new terminal cost list differs')
    for k,key in (('old','old_costs'),('new','new_costs')):
        e.require(all(result[key].get(n)==v for n,v in summaries[k].items()),'claimed old/new costs differ')
    e.require(all(result.get(n)==v for n,v in summaries['combined'].items()) and summaries['old']['unknown_token_calls']==6
        and summaries['new']['unknown_token_calls']==0,'exact combined partial cost coverage differs')
    proof=settled_resource(reader,seal['historical_backend_proof'],old,runtime,rp)
    return {'schema':'n25-logical-dev-evidence-v1','allow_validation':False,'allow_n26':False,'gpu_authorized':False,
        'logical_disposition':computed['cohort_disposition'],'accepted_cells':computed['accepted_cells'],'counts':computed['counts'],
        'accepted_mapping':result['accepted_cells'],'native':result['native'],'auxiliary':result['auxiliary'],'attempt_ids':[x['attempt_id'] for x in result['attempts']],
        'cost_coverage':summaries,'historical_unknowns':e.UNKNOWN,'original_disposition':'INVALID_OR_INTERRUPTED',
        'provenance':refs,'source':{'original':old,'continuation':new},'settled_original_resource':proof,
        'current_matching_event_check_required_at_release':True,'projections_are_root_attestations':True,
        'underlying_full_ledger_refs_followed':False,'tensor_reads':0,'metadata_bytes':reader.bytes,'reader':e.ref(__file__)}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();e.require(args.input.stat().st_size<=16*1024*1024,'input envelope bound')
    with args.input.open('rb') as f:data=json.loads(f.read(16*1024*1024+1))
    record=build(data);record['input']=e.ref(args.input)
    e.require(args.output.resolve().is_relative_to(c.RUN_DIR.resolve()) and not args.output.exists(),'new owned evidence output required')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:json.dump(record,f,indent=2,allow_nan=False);f.write('\n')
if __name__=='__main__':main()
