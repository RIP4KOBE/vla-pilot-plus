import json,hashlib,os,sys,datetime
from pathlib import Path
O=Path(__file__).absolute().parent; C=O/'composition-v3'; H=O.parent.parent/'001748/disabled-graph-composition/composition-v3'
def read(p):return json.loads(p.read_text())
def ref(p):
 d=p.read_bytes();return dict(path=str(p),bytes=len(d),sha256=hashlib.sha256(d).hexdigest())
def save(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2,sort_keys=True)
 return ref(p)
a=read(O/'authority-v1.json');p=read(C/'engineering-plan.disabled-v1.json');audit=read(C/'all40-audit.immutable-disabled-v1.json');old=read(H/'engineering-plan.disabled-v1.json');olda=read(H/'all40-audit.immutable-disabled-v1.json');checks=[]
def passed(name,condition):
 assert condition,name
 checks.append(dict(check=name,status='PASS'))
passed('original canonical plan/audit STOP bindings preserved exactly',p['stop_authority']==old['stop_authority']==audit['stop_authority']==olda['stop_authority'])
passed('authority deadline agrees and all authority STOP paths remain included',p['stop_authority']['deadline']==a['stop_authority']['deadline'] and set(a['stop_authority']['paths']) <= set(p['stop_authority']['paths']))
passed('no STOP present',all(not os.path.lexists(x) for x in p['stop_authority']['paths']))
passed('all40 frozen scientific fields preserved',all(audit[k]==olda[k] for k in ('episodes','limits','worker_contract','deadline','protocol','protocol_review','accounting')))
passed('separate engineering frozen scientific fields preserved',all(p[k]==old[k] for k in ('episodes','limits','worker_contract','deadline','purpose','cohort')))
passed('all phases and release disabled',not p['release_enabled'] and not audit['release_enabled'] and not p['frozen'] and p['authority'] is None and p['b5_review'] is None and not any(p['phase_authorization'].values()) and not any(audit['phase_authorization'].values()))
runtime=read(Path(p['runtime']['path']))
passed('runtime readiness flags remain false',all(x is False for x in [runtime['preparation']['runtime_ready'],runtime['provider_ready'],runtime['cuda_egl_verified'],runtime['gpu_mapping']['cuda_egl_verified']]))
passed('physical GPU parameter remains 7',audit['limits']['physical_gpu']==7)
for f in read(C/'inputs-manifest-v1.json')['files']:
 passed('unchanged input '+f['path'],ref(Path(f['path']))==f)
passed('40 plus 1 manifests exist',len(audit['expected_manifests'])==40 and len(p['expected_manifests'])==1)
for key,mr in audit['expected_manifests'].items():
 m=read(Path(mr['path']));om=read(Path(olda['expected_manifests'][key]['path']))
 projected=json.loads(json.dumps(m['resolved_config']).replace(p['source']['commit'],old['source']['commit']))
 passed('unchanged resolved scientific configuration '+key,projected==om['resolved_config'])
em=read(Path(p['engineering_manifest']['path']));oem=read(Path(old['engineering_manifest']['path']))
passed('unchanged engineering resolved configuration and argv',em['resolved_config']==oem['resolved_config'] and em['argv']==oem['argv'])
supp=save(O/'preservation-evidence-v1.json',dict(schema='n36-disabled-composition-preservation-v1',checks=checks,explanation='The composition-v3 template preservation check compared complete canonical STOP schema against the smaller executor authority descriptor. Exact original plan/audit bindings, both original STOP paths, and inclusion of all executor STOP paths are verified here. The executor authority duplicates its home STOP path; the original plan additionally retains the shared-data STOP path. This resolves only that executor assertion; production canonical-runtime-path failures remain blocked.'))
report=read(C/'report-v1.json');report['composition_attempt_report']=ref(C/'report-v1.json');report['preservation_evidence']=supp
report['checks']=[x for x in report['checks'] if x['check']!='science budget reserves original offsets journals and disabled authorization preservation']+[dict(check='preservation including STOP bindings; see hash-bound supplemental evidence',status='PASS')]
report['blockers']=[x for x in report['blockers'] if x.get('check')!='science budget reserves original offsets journals and disabled authorization preservation']
report['graph_complete']=True;report['graph_verified']=False;report['composition_method']='Historical templates structurally rebound, production Hydra recomposed; no production admission claimed.'
report['runtime_path_diagnosis']=dict(supplied=p['runtime']['path'],resolved=str(Path(p['runtime']['path']).resolve()),production_condition='reference path must equal its resolved path AND the pinned policy disabled_runtime_path',unchanged_policy_precludes_local_fix=True)
report['future_gates'].insert(0,report['next_bounded_step'])
report['prior_attempts_preserved']=[ref(O/'report-v1.json'),ref(O/'composition-v2/report-v1.json'),ref(C/'report-v1.json')]
report['at']=datetime.datetime.now(datetime.timezone.utc).isoformat();report['exact_static_command_receipt']=ref(C/'command-receipt-v1.json')
F=O/'final-result';F.mkdir();rr=save(F/'report-v1.json',report)
idx=save(O/'final-composition-index-v1.json',dict(status=report['status'],report=rr,graph=report['graph'],command_evidence=report['command_evidence'],command_receipt=ref(C/'command-receipt-v1.json'),preservation_evidence=supp,release_enabled=False,runtime_ready=False,provider_ready=False,graph_verified=False,independent_review_claimed=False,next_bounded_step=report['next_bounded_step'],old_artifacts_preserved=True))
# Exclude active executor transport logs and self to avoid a moving/self-referential manifest.
files=[]
for root in [C,O/'composition-v2',F]:
 for f in sorted(root.rglob('*')):
  if f.is_file() and 'tmp' not in f.relative_to(root).parts:files.append(ref(f))
for name in ['authority-v1.json','compose-disabled-v1.py','report-v1.json','report-v1.sha256','command-evidence-v1.json','command-receipt-v1.json','inputs-manifest-v1.json','outputs-manifest-v1.json','generated-artifact-manifest-v1.json','specification-selector-v1.json','builder-stdout-v1.log','finalize-evidence-v1.py','finalize-evidence-v2.py','preservation-evidence-v1.json','final-composition-index-v1.json']:
 f=O/name
 if f.is_file():files.append(ref(f))
am=save(O/'artifact-manifest-v1.json',dict(schema='n36-hash-bound-artifact-manifest-v1',final_report=rr,final_index=idx,files=files,excludes=['artifact-manifest-v1.json','active executor transport logs and temporary files'],release_enabled=False,graph_verified=False))
print(json.dumps(dict(report=rr,artifact_manifest=am,status=report['status'],preservation_checks=len(checks))))
