import pathlib,json,sys,os,time,traceback,datetime
root=pathlib.Path.cwd();out=root.parent/'autonomy_20261004/turns/000709';record=json.loads((out/'release-preparation-v1.json').read_text());plan=json.loads(pathlib.Path(record['plan']['path']).read_text());rt=json.loads(pathlib.Path(plan['runtime']['path']).read_text());os.environ.update(rt['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+rt['environment']['PYTHONPATH'].split(':')
from scripts.qd_ed_n34_release import validate_release
start=time.monotonic();result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan':record['plan'],'release':record['release'],'gpu_dispatched':False}
try:
 p,r,a=validate_release(record['plan'],record['release']);result.update(status='PASS',manifest_count=len(p['expected_manifests']))
except Exception as e:
 result.update(status='FAIL',error=repr(e),traceback=traceback.format_exc())
result['elapsed_seconds']=time.monotonic()-start;(out/'full-public-release-validation-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));sys.exit(0 if result['status']=='PASS' else 1)
