import json,pathlib,hashlib,time,stat,collections
start=time.process_time();d=pathlib.Path(__file__).resolve().parent;p=d.parent
local=json.loads((d/'index-metadata-local-v1.json').read_text());out=[];reads=[]
for ep in local['episodes']:
 ip=pathlib.Path(ep['index_ref']['path']);raw=ip.read_bytes();assert hashlib.sha256(raw).hexdigest()==ep['index_ref']['sha256'];reads.append(dict(ep['index_ref'],bytes=len(raw)))
 previous=[]
 for line in raw.splitlines():
  x=json.loads(line)
  if any(e['event']=='pre_reset_outcome' and e['global_step']==15 for e in x['events']):previous.append(x)
 assert len(previous)==1
 main=[r for r in ep['decision_records'] if any(e['event']=='final_selection' for e in r['events'])];assert len(main)==1
 containers=[]
 for role,rec in [('pre_action_state',previous[0]),('terminal_pool',main[0])]:
  q=ip.parent/rec['bundle'];st=q.lstat();assert stat.S_ISREG(st.st_mode) and not q.is_symlink();attemptroot=ip.parents[3]
  matches=[z for z in ep['receipt_files'] if attemptroot/pathlib.Path(z['path'])==q];assert len(matches)==1 and matches[0]['sha256']==rec['sha256']
  containers.append({'role':role,'path':str(q),'stat_bytes':st.st_size,'stat_identity':{'device':st.st_dev,'inode':st.st_ino,'mtime_ns':st.st_mtime_ns},'sha256':rec['sha256'],'receipt_relative_path':matches[0]['path'],'first_sequence':rec['first_sequence'],'last_sequence':rec['last_sequence'],'events':rec['events']})
  print(ep['cell']['task_id'],role,q.name,st.st_size,dict(collections.Counter(e['event'] for e in rec['events'])))
 out.append({'cell':ep['cell'],'index':ep['index_ref'],'receipt':ep['cell']['worker_receipt'],'receipt_identity':{k:ep['receipt_identity'][k] for k in ('schema','accepted','attempt_id','source')},'containers':containers})
result={'schema':'n30-jaw-pool-input-v1','source_commit':'6292fc8cffad2eec0f789e023d835ad3c1df146a','decision_id':'e0:d3:s16','episodes':out,'payload_reads_so_far':0,'limits':{'containers':4,'encoded_bytes':sum(b['stat_bytes'] for e in out for b in e['containers']),'encoded_cap':64*1024**2,'zip_and_storage_cap_each':128*1024**2},'prior_executed_commands':{'path':str(p/'approach-handoff-review-v1/decode-v1/result-v1.json'),'sha256':'fd63df833c0839efd87ddea5d3ffcb75eebfe493730aef018f809d9937324f46'}}
with (d/'input-manifest.frozen.v1.json').open('x') as f:json.dump(result,f,indent=2)
(d/'scope-addendum-v1.md').write_text('Root explicitly permits immediately preceding step15 pre_reset_outcome as decision16 pre-action quaternion/qpos. Require same episode/reset, no termination/truncation, sequential step-return before context, and raw dtype/byte equality of prior EEF with packet.start_eef. Four whole containers are weights_only CPU decoded; co-resident fields are not analyzed/exported beyond hand pose/qpos, candidates, original scores and selection identities. No object pose/contact/future values are used. Raw canonical projection is retained without clipping. Administrative metadata failures are preserved separately.\n')
(d/'tmp').mkdir(exist_ok=True)
(d/'preparation-step07-resource.json').write_text(json.dumps({'cpu_seconds':time.process_time()-start,'metadata_reads':reads,'payload_reads':0,'affinity':[0,1],'threads':2},indent=2))
print('TOTAL',result['limits'])
