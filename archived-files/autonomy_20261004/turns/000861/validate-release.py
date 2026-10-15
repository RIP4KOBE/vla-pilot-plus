import pathlib,json,sys,os,datetime,traceback
root=pathlib.Path.cwd();out=(root.parent/'autonomy_20261004/turns/000861').resolve();refs=json.loads((out/'release-refs-v1.json').read_text());plan=json.loads(pathlib.Path(refs['plan']['path']).read_text());runtime=json.loads(pathlib.Path(plan['runtime']['path']).read_text());os.environ.update(runtime['environment']);os.environ['CUDA_VISIBLE_DEVICES']='';sys.path[:0]=[str(root)]+runtime['environment']['PYTHONPATH'].split(':')
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'plan':refs['plan'],'release':refs['release'],'gpu_dispatched':False}
try:
 from scripts.qd_ed_n34_continuation_release import validate_release
 p,r,a=validate_release(refs['plan'],refs['release']);result.update(status='PASS',missing_cells=len(p['episodes']),retained_cells=len(p['retained_outcomes']))
except BaseException as e:
 result.update(status='FAIL',error=repr(e),traceback=traceback.format_exc())
(out/'public-release-validation-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));sys.exit(0 if result['status']=='PASS' else 1)
