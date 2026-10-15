import json,pathlib,hashlib,sys,importlib.util
T=pathlib.Path.cwd().parent/'autonomy_20261004/turns/001792';P=T.parent/'001779/canonical-path-rebinding'
r=json.loads((P/'proof.measurement/runtime-receipt.json').read_text());c=json.loads((P/'runtime-closure.prospective-disabled-v1.json').read_text());out={}
for name,x in r['generated_modules'].items():
 rule=c['generated_modules'][name];origins={}
 for key in ['origin','generator_origin','template_origin']:
  v=x[key];expect=importlib.util.cache_from_source(v['file']);origins[key]=dict(recorded_cached=v['cached'],verifier_cached=expect,spec_cached=v['spec']['cached'],matches=v['cached']==v['spec']['cached']==expect)
 out[name]=dict(rule_matches=x['rule']==rule,record_hash_matches=x['record']['sha256']==rule['sha256'],content_hash_matches=hashlib.sha256(x['source_utf8'].encode()).hexdigest()==rule['sha256'],origins=origins)
result=dict(schema='n36-readiness-parent-invocation-diagnosis-v1',sys_pycache_prefix=sys.pycache_prefix,generated=out,explanation='Initial CPU validator omitted frozen worker pycache prefix. Historical measurement launch explicitly binds -X pycache_prefix=/dev/null. Repeat only CPU validation using matching cache prefix; receipts, source, and rules unchanged.',prior_failure_preserved=True,new_gpu_or_provider_call=False)
(T/'generated-receipt-diagnosis-v1.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
