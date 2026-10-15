import pathlib,json,hashlib,sys,datetime
W=pathlib.Path.cwd();A=W.parent/'autonomy_20261004';T=A/'turns/001611'
def read(p):return json.loads(pathlib.Path(p).read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def save(n,d):(T/n).write_text(json.dumps(d,indent=2)+'\n')
s=read(A/'turns/001610/operational-summary-v1.json');boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def live(h):
 p=pathlib.Path('/proc')/str(h['pid'])/'stat';v=p.read_text().rsplit(')',1)[1].split() if p.exists() else [];return bool(v and v[0]!='Z' and int(v[19])==h['start_ticks'] and h['boot_id']==boot)
d=read(A/'driver-status.json');assert d['turn']==1611 and live(d['driver']) and live(d['process'])
assert not any(live(h) for h in list(s['live_handles'].values()))
for r in s['ledger_prefixes'].values():assert ref(pathlib.Path(r['path']))['sha256']==r['sha256']
assert not (A/'STOP').exists()
pr=read(A/'turns/001608/operational-summary-v1.json')['production_plan'];assert ref(pathlib.Path(pr['path']))==pr
p=read(pr['path']);sys.path.insert(0,p['worktree'])
from scripts import qd_ed_n36_engineering as e
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
x={'schema':'n36-engineering-episode-release-v1','approved':True,'plan':pr,'authority':p['authority'],'b5_review':p['b5_review'],**e.review_bindings(p),'limits':e.LIMITS,'purpose':e.PURPOSE,'issued_at':now}
x['readiness']={'health_release':ref(A/'turns/001609/health-release-v1.json'),'terminal':ref(pathlib.Path(p['artifact_root'])/'healthchecks'/e.HEALTH_ID/'healthcheck-result.json')}
save('root-episode-review-v1.json',{**x,'schema':'n36-engineering-root-episode-review-v1','decision':'APPROVED'})
x['root_review']=ref(T/'root-episode-review-v1.json');save('episode-release-v1.json',x)
e.validate_release(pr,ref(T/'episode-release-v1.json'))
save('episode-release-consumer-v1.json',{'status':'PASS','plan':pr,'release':ref(T/'episode-release-v1.json'),'at':now})
print('Detached episode release production validation PASS')
