from pathlib import Path
import hashlib,json,datetime
H=Path(__file__).resolve().parent;V=H.parent
D=lambda b:hashlib.sha256(b).hexdigest()
def read(p,expected=None):
 b=p.read_bytes()
 if expected:assert D(b)==expected
 return b
def ref(p,b):return {'path':str(p.resolve()),'sha256':D(b)}
s=V/'full-close-survival-extension-scope-v1.md';m=V/'planned-gripper-continuity-attempts-v1.json';prior=V/'planned_gripper_continuity_diagnostic/read-scope-v1.json';gr=V/'gripper_availability_diagnostic/screen-result-v1.json';gs=V/'gripper_availability_diagnostic/read-scope-v1.json'
sb=read(s,'97a1c71e8d25654964931dddb55a621d895e2da43d721b440d4e55d7f9df5bf7');mb=read(m,'cca36ad827d720aa7973e808d86db7fb00da961f44ba4203f57123626adc39f4');pb=read(prior,'65e0381d8ad3e1e9321be09b63e5cbf5a11ece46f1950adf76a2aceed640d452');gb=read(gr,'d8ba9b2865479646edfede42e447497dd7b162a4847e3fe5447aa98905c5477c');gsb=read(gs,'5b569b01eb84cd5b51139cfd9ce175f94f695306cb977b5a3875ebc17fc8c34b')
old=json.loads(pb);source=json.loads(gsb)['source_files'];a=json.loads(mb)['attempts'];items=[]
for x in old['attempts'][1:]:
 ds=x['native_audit_guided_decisions'];ids={d['decision_id'] for d in ds};assert x['attempt_id']==a[x['task']]['attempt_id']
 bundles=[b for b in x['bundle_refs'] if any(e['event']=='canonical_candidate_batch' and e['decision_id'] in ids for e in b['events'])]
 assert len(bundles)==len(ds)=={1:54,2:68,3:2}[x['task']]
 assert all(all(e['decision_id'] in ids for e in b['events']) for b in bundles)
 items.append({'task':x['task'],'attempt_id':x['attempt_id'],'metadata_refs':x['metadata_refs'],'bundles':bundles,'native_audit_guided_decisions':ds})
result={'schema':'n23-full-close-survival-frozen-scope-v1','created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':ref(s,sb),'attempt_manifest':ref(m,mb),'prior_metered_index_and_audit_derivation':ref(prior,pb),'task0_closed_result':ref(gr,gb),'earlier_source_binding':ref(gs,gsb),'source_commit':old['source_commit'],'source_files':source,'attempts':items,
 'limits':{'guided_decisions':124,'canonical_batches':1364,'canonical_rows':21824,'parent_rounds':1240,'native_extraction_seconds':240,'engineering_reruns':2,'cpu_threads':2,'cuda_visible_devices':''},
 'native_read_rule':'Only task1..3 listed bundles, each once; task0 only closed JSON. New tensors analyzed only at gripper [:,:8,10], original quality/cost vectors, recorded identity/parent/final metadata; no trajectory or quality recomputation.'}
f=H/'read-scope-v1.json';assert not f.exists();f.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'manifest':ref(f,f.read_bytes()),'decisions':sum(len(x['bundles']) for x in items),'new_index_or_tensor_reads_during_freeze':0},indent=2))
