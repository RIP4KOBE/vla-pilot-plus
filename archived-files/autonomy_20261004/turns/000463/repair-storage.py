import pathlib,json,hashlib,shutil,datetime
from scripts import qd_ed_n32r3_contract as c,qd_ed_n32r3_release as release,qd_ed_n23_worker as w
out=pathlib.Path.cwd().parent/'autonomy_20261004/turns/000463'; previous=json.loads((out/'release-validation.json').read_text());p=w.read_ref(previous['plan']);runtime=w.read_ref(p['runtime']);src=pathlib.Path(p['artifact_root']);dst=pathlib.Path(runtime['artifact_root'])/'variants/n32_archive_eligible_capture/prospective-continuation-v3/prospective-artifacts'
def inventory(base):
 return {str(x.relative_to(base)):hashlib.sha256(x.read_bytes()).hexdigest() for x in base.rglob('*') if x.is_file()}
assert src.is_dir() and not src.is_symlink() and not dst.exists();assert not (src/'attempts').exists();assert not pathlib.Path(p['stop_path']).exists()
old=inventory(src);assert old and all(x.startswith('manifests-v1/') for x in old)
backup=src.with_name('prospective-artifacts.pre-storage-repair-turn463');assert not backup.exists()
w.atomic_json(out/'storage-repair-intent.json',{'source':str(src),'destination':str(dst),'backup':str(backup),'files':old,'authority':'standing local engineering repair; retain logical paths and bytes; own study only','gpu_dispatched':False})
dst.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(src,dst);assert inventory(dst)==old
src.rename(backup);src.symlink_to(dst,target_is_directory=True);assert inventory(src)==old
w.atomic_json(out/'storage-repair-result.json',{'status':'PASS','files_verified':len(old),'intent':c.ref(out/'storage-repair-intent.json'),'logical_paths_and_hashes_unchanged':True})
try:
 release.validate_release(previous['plan'],previous['release']);status={'status':'PASS'}
except Exception as e:
 import traceback
 status={'status':'FAIL','error':str(e),'traceback':traceback.format_exc()}
w.atomic_json(out/'release-validation-after-storage-repair.json',{**status,'plan':previous['plan'],'release':previous['release'],'gpu_dispatched':False});print(json.dumps(status))
