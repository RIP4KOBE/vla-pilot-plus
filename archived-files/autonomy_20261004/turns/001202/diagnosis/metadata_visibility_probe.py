import json,pathlib,os,difflib,hashlib
import torch
out=pathlib.Path(__file__).parent
plan=json.loads((out.parents[1]/'001199/plan.frozen-v2.json').read_text());p=pathlib.Path(plan['native_build']['path']);assert hashlib.sha256(p.read_bytes()).hexdigest()==plan['native_build']['sha256'];expected=json.loads(p.read_text())
actual={'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show()}
result={'visibility':os.environ.get('CUDA_VISIBLE_DEVICES'),'matches':{k:actual[k]==expected[k] for k in actual},'actual':actual,'diff':list(difflib.unified_diff(expected['torch_build'].splitlines(),actual['torch_build'].splitlines())),'cuda_initialized':torch.cuda.is_initialized(),'torch_file':torch.__file__}
label='hidden' if result['visibility']=='' else 'assigned7'
(out/('metadata-'+label+'.json')).write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps({k:v for k,v in result.items() if k not in ['actual','diff']}))
