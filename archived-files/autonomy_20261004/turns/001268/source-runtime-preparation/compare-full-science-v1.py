import os,sys,json,time,resource,hashlib,datetime as dt
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=Path.cwd().resolve();sys.path.insert(0,str(ROOT));os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);resource.setrlimit(resource.RLIMIT_CPU,(80,80))
START=time.monotonic();a=json.loads((OUT/'authority-v1.json').read_text())
def guard():
 assert not any(os.path.lexists(p) for p in a['STOP_paths']);assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat(a['deadline'].replace('Z','+00:00'));assert os.environ['CUDA_VISIBLE_DEVICES']==''
guard()
from scripts import qd_ed_n36_bridge as b,qd_ed_n23_worker as w
old=json.loads(Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/turns/001250/recovery-preparation/draft/plan.partial.draft-v1.json').read_text());plan=json.loads((OUT/'plan.complete-disabled-v1.json').read_text())
def normalize(x,manifest):
 if isinstance(x,str):return x.replace(manifest['output_dir'],'<prospective-output>').replace(manifest['source']['commit'],'<source-commit>')
 if isinstance(x,list):return [normalize(v,manifest) for v in x]
 if isinstance(x,tuple):return [normalize(v,manifest) for v in x]
 if isinstance(x,dict):return {k:normalize(v,manifest) for k,v in x.items()}
 return x
rows=[]
for row in plan['episodes']:
 guard();key=row['episode_key'];prior=w.read_ref(old['expected_manifests'][key]);current=w.read_ref(plan['expected_manifests'][key]);assert normalize(prior['argv'],prior)==normalize(current['argv'],current)
 before,_=b.compose_launch(prior['argv'],ROOT);after,_=b.compose_launch(current['argv'],ROOT)
 assert w.canonical_sha(before)==prior['composed_config_sha256'];assert w.canonical_sha(after)==current['composed_config_sha256'];assert normalize(before,prior)==normalize(after,current)
 assert prior['row']==current['row'];assert not Path(current['output_dir']).exists()
 rows.append({'episode_key':key,'old_composed_config_sha256':w.canonical_sha(before),'new_composed_config_sha256':w.canonical_sha(after),'normalized_composed_config_sha256':w.canonical_sha(normalize(after,current)),'argv_equal_except_exact_output_prefix_and_source_commit':True,'complete_config_equal_except_exact_output_prefix_and_source_commit':True,'row_exact':True})
report={'status':'PASS','count':len(rows),'normalization_only':['exact per-manifest output_dir prefix','exact per-manifest source.commit'],'rows':rows,'wall_seconds':time.monotonic()-START,'release_enabled':False}
p=OUT/'full-scientific-config-comparison-v1.json';assert not p.exists();p.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':'PASS','rows':len(rows),'seconds':report['wall_seconds']}))
