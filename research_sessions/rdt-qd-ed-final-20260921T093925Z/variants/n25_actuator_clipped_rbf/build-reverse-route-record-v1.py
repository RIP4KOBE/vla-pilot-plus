from pathlib import Path
import difflib,hashlib,json,subprocess
root=Path(__file__).resolve().parent/'implementation'
records=[]
for path in ('scripts/qd_ed_final_runner.py','scripts/qd_ed_n23_worker.py'):
 old=subprocess.check_output(['git','show','aadec3f7435f31c60b74f709efb61427c3b829c7:'+path],cwd=root).decode()
 new=(root/path).read_text();a=old.splitlines(keepends=True);b=new.splitlines(keepends=True)
 edits=[{'old_start':i,'old_end':j,'new_start':k,'new_end':l,'old':''.join(a[i:j]),'new':''.join(b[k:l])}
       for tag,i,j,k,l in difflib.SequenceMatcher(a=a,b=b,autojunk=False).get_opcodes() if tag!='equal']
 restored=b.copy()
 for e in reversed(edits):assert ''.join(restored[e['new_start']:e['new_end']])==e['new'];restored[e['new_start']:e['new_end']]=e['old'].splitlines(keepends=True)
 assert ''.join(restored)==old
 records.append({'path':path,'old_sha256':hashlib.sha256(old.encode()).hexdigest(),'new_sha256':hashlib.sha256(new.encode()).hexdigest(),'edits':edits})
(root/'docs/03_evidence/qd_ed_final/n25/shared-route-insertions-v1.json').write_text(json.dumps({'schema':'n25-reversible-shared-routes-v1','base_commit':'aadec3f7435f31c60b74f709efb61427c3b829c7','files':records},indent=2)+'\n')
