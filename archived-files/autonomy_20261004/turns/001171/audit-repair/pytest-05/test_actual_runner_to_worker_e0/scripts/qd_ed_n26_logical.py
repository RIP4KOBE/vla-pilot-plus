"""Strict logical-rejection evidence and additive historical composition; no dispatch."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
from scripts import qd_ed_n23_worker as w
from scripts import qd_ed_n25_cont_downstream as common
from scripts import qd_ed_n26_contract as c

ACCEPTED='c09dffe956c391d85ecc02e3288b9fa982e86ce7'
COMMON='ff285373cc69a898cb1f5e6ed9cbbfe370a2972a'
DOC='experiments/qd_ed_n26_logical'
PROTOCOL_SHA='87ff4abf54ebeed75a9551db309bb82472d752f0b9f13b818f1509b6de183dc6'
SOURCE_FILES={'scripts/qd_ed_n26_logical.py','tests/test_qd_ed_n26_logical.py','tests/n26_logical_fixtures.py'}|{DOC+'/'+n for n in
 ('protocol-v1.md','admission-addendum-v1.md','controller-contract-v1.md','accepted-n26-source-v1.json','common-source-v1.json','shared-reverse-v1.json','provenance-reverse-v1.json')}
PROVENANCE_FUNCTIONS={'scripts/qd_ed_n26_contract.py':{'source_paths','final_review','authority','metadata','require_protocols','predecessor'},
 'scripts/qd_ed_n26_bridge.py':{'build','verify_reverse','settled_control_proofs'},
 'scripts/qd_ed_n26_prepare.py':{'build_plan'},'scripts/qd_ed_n26_backend.py':{'source_review'}}
SHARED={'scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'}


def bounded_ref(reference):
    w.require(set(reference)=={'path','sha256'},'logical metadata ref shape')
    p=Path(reference['path']);w.require(p.is_absolute() and p.stat().st_size<=16*1024*1024,'logical metadata size/path bound')
    with p.open('rb') as f:b=f.read(16*1024*1024+1)
    w.require(len(b)<=16*1024*1024 and hashlib.sha256(b).hexdigest()==reference['sha256'],'logical metadata hash/bound')
    return json.loads(b)


def protocol(root):
    root=Path(root)
    w.require(w.sha(c.LOGICAL_PROTOCOL)==PROTOCOL_SHA
        and (root/DOC/'protocol-v1.md').read_bytes()==Path(c.LOGICAL_PROTOCOL).read_bytes(), 'logical composition protocol differs')
    w.require(Path(common.__file__).resolve()==root/'scripts/qd_ed_n25_cont_downstream.py','common import must be owning source')
    frozen=w.read_ref(c.ref(root/DOC/'common-source-v1.json'))
    q=next(x for x in frozen['files'] if x['path']=='scripts/qd_ed_n25_cont_downstream.py')
    w.require(frozen['commit']==COMMON and w.sha(common.__file__)==q['sha256'],'common ff reader bytes differ')


def read_gate(*,root=None):
    root=Path(root or c.ROOT).resolve();protocol(root)
    record=bounded_ref(c.ref(c.PREDECESSOR))
    keys={'schema','disposition','allow_n26','allow_validation','logical_disposition','common_evidence','continuation_root_review',
          'common_reader','runtime','historical_backend_proof','composition_protocol','admission_addendum'}
    w.require(set(record)==keys and record['schema']=='n26-logical-predecessor-review-v1'
        and record['disposition']=='VALID_LOGICAL_DEV_REJECTION' and record['allow_n26'] is True
        and record['allow_validation'] is False and record['logical_disposition'] in {'REJECT','REJECT_NUMERIC_FUTILITY'}
        and record['composition_protocol']==c.ref(c.LOGICAL_PROTOCOL)
        and record['admission_addendum']==c.ref(root/DOC/'admission-addendum-v1.md'),'strict logical rejection gate required')
    evidence_ref=record['common_evidence']
    w.require(Path(evidence_ref['path']).resolve()==(common.c.RUN_DIR/'logical-dev-evidence-v1.json').resolve(),'exact common evidence path required')
    evidence=bounded_ref(evidence_ref)
    w.require(Path(evidence['input']['path']).resolve().is_relative_to(common.c.RUN_DIR.parent.resolve()),'common input must be root-owned N25 metadata')
    data=bounded_ref(evidence['input'])
    rebuilt=common.build(data)
    w.require(evidence=={**rebuilt,'input':evidence['input']},'common evidence reconstruction differs')
    w.require(evidence['logical_disposition']==record['logical_disposition']
        and evidence['allow_validation'] is evidence['allow_n26'] is evidence['gpu_authorized'] is False
        and evidence['original_disposition']=='INVALID_OR_INTERRUPTED'
        and evidence['historical_unknowns']==common.e.UNKNOWN
        and record['common_reader']==evidence['reader']==c.ref(common.__file__)
        and record['continuation_root_review']==evidence['provenance']['root_review']
        and record['runtime']==c.runtime_ref()
        and record['historical_backend_proof']==evidence['settled_original_resource']['reference'], 'logical rejection lineage differs')
    review=bounded_ref(record['continuation_root_review'])
    w.require(review['schema']=='n25-continuation-root-terminal-review-v1'
        and review['decision']=='ACCEPT_TERMINAL_RECONSTRUCTION'
        and review['cohort_disposition']==evidence['logical_disposition']
        and review['source']==evidence['source']['continuation']
        and review['accepted_cells']==evidence['accepted_cells'] and review['counts']==evidence['counts'], 'independent continuation rejection review differs')
    return record,evidence,data


def current_matching(events,resources):
    record,evidence,data=read_gate()
    reader=common.MetadataReader(data['files']);refs=evidence['provenance']
    jp=common.projection(reader,refs['journal_projection'],'n25-current-dev-journal-projection-v1',refs['root_review'])
    rp=common.projection(reader,refs['resource_projection'],'n25-current-resource-projection-v1',refs['root_review'])
    selected=[x for x in events if x.get('identity',{}).get('iteration') in {common.e.OLD,common.c.COHORT}]
    health=[x for x in resources if x.get('resource_id')==rp['resource_id'] or x.get('kind')==rp['resource_kind']]
    common.check_current_matching_events(jp,selected,rp,health)
    return c.ref(c.PREDECESSOR)


def manifests(root):
    values=[w.read_ref(c.ref(Path(root)/DOC/name)) for name in ('accepted-n26-source-v1.json','common-source-v1.json')]
    for v,commit,count in zip(values,(ACCEPTED,COMMON),(286,276)):
        w.require(v['commit']==commit and len(v['files'])==count and v['sha256']==w.canonical_sha(v['files'])
            and len({q['path'] for q in v['files']})==count,'accepted historical closure differs')
    return values


def source_paths(root):
    accepted,shared=manifests(root)
    return {q['path'] for q in accepted['files']+shared['files']}|SOURCE_FILES


def restore_shared(root,path):
    record=w.read_ref(c.ref(Path(root)/DOC/'shared-reverse-v1.json'))
    w.require(record['schema']=='n26-logical-to-accepted-shared-reverse-v1' and record['base_commit']==ACCEPTED
        and {x['path'] for x in record['files']}==SHARED,'logical shared reverse scope')
    row=next(x for x in record['files'] if x['path']==path);current=(Path(root)/path).read_bytes()
    w.require(hashlib.sha256(current).hexdigest()==row['new_sha256'],'composed shared byte drift')
    lines=current.decode().splitlines(True)
    for edit in reversed(row['edits']):
        a,z=edit['new_start'],edit['new_end'];w.require(''.join(lines[a:z])==edit['new'],'composed reverse segment differs')
        lines[a:z]=edit['old'].splitlines(True)
    restored=''.join(lines).encode()
    w.require(hashlib.sha256(restored).hexdigest()==row['old_sha256'],'composed reverse bytes differ')
    return restored


def restore_provenance(root,path):
    record=w.read_ref(c.ref(Path(root)/DOC/'provenance-reverse-v1.json'))
    w.require(record['schema']=='n26-logical-provenance-reverse-v1' and record['base_commit']==ACCEPTED
        and {x['path'] for x in record['files']}==set(PROVENANCE_FUNCTIONS),'logical provenance reverse scope')
    row=next(x for x in record['files'] if x['path']==path);current=(Path(root)/path).read_bytes()
    w.require(hashlib.sha256(current).hexdigest()==row['new_sha256'],'logical provenance byte drift')
    lines=current.decode().splitlines(True)
    for edit in reversed(row['edits']):
        a,z=edit['new_start'],edit['new_end'];w.require(''.join(lines[a:z])==edit['new'],'provenance reverse segment differs')
        lines[a:z]=edit['old'].splitlines(True)
    restored=''.join(lines).encode()
    w.require(hashlib.sha256(restored).hexdigest()==row['old_sha256'],'provenance reverse bytes differ')
    return restored


def verify_composition(root,source):
    root=Path(root);accepted,shared=manifests(root)
    w.require({q['path'] for q in source['files']}==source_paths(root),'logical full source closure differs')
    fs=lambda text:{n.name:ast.get_source_segment(text,n) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}
    unchanged=[];provenance={};historic={};accepted_paths={q['path'] for q in accepted['files']}
    for manifest in (accepted,shared):
        for q in manifest['files']:
            # Common overlapping science belongs to accepted N26, not ff science;
            # the unchanged common gate separately verifies original5a/6f history.
            if manifest['commit']==COMMON and q['path'] in accepted_paths:continue
            b=subprocess.check_output(['git','show',manifest['commit']+':'+q['path']],cwd=root)
            w.require(hashlib.sha256(b).hexdigest()==q['sha256'],'accepted historical Git bytes differ')
            historic[manifest['commit'],q['path']]=b
    for q in accepted['files']:
        path=q['path'];before=historic[ACCEPTED,path];after=(root/path).read_bytes()
        if path in SHARED:w.require(restore_shared(root,path)==before,'accepted shared source differs');continue
        if path in PROVENANCE_FUNCTIONS:
            w.require(restore_provenance(root,path)==before,'accepted provenance reverse differs')
            a,z=fs(before.decode()),fs(after.decode());changed={k for k in a if a[k]!=z.get(k)}
            w.require(set(a)==set(z) and changed<=PROVENANCE_FUNCTIONS[path],'new behavior outside provenance functions')
            provenance[path]=sorted(changed)
        else:w.require(after==before,'accepted N26 science/controller drift: '+path);unchanged.append(q)
    common_exact=[]
    for q in shared['files']:
        if q['path'] not in accepted_paths:
            w.require((root/q['path']).read_bytes()==historic[COMMON,q['path']],'6f/common administrative source drift');common_exact.append(q)
    return {'schema':'n26-logical-source-composition-v1','accepted_n26_source':accepted,'historical_common_source':shared,
        'accepted_unchanged':unchanged,'common_administrative_unchanged':common_exact,'provenance_functions':provenance,
        'shared_reverse':c.ref(root/DOC/'shared-reverse-v1.json'),'provenance_reverse':c.ref(root/DOC/'provenance-reverse-v1.json'),
        'historical_proof_relabelled':False}
