import json,pathlib,difflib
import torch
out=pathlib.Path(__file__).parent
plan=json.loads((out.parents[1]/'001199/plan.frozen-v2.json').read_text())
expected=json.loads(pathlib.Path(plan['native_build']['path']).read_text())
def snap():
 return {'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show()}
before=snap()
from scripts import qd_ed_n36_worker as worker
after=snap()
result={'before_matches':{k:before[k]==expected[k] for k in before},'after_matches':{k:after[k]==expected[k] for k in after},'diff':list(difflib.unified_diff(expected['torch_build'].splitlines(),after['torch_build'].splitlines())),'cuda_initialized':torch.cuda.is_initialized(),'torch_file':torch.__file__}
(out/'worker-import-result.json').write_text(json.dumps(result,indent=2)+'\n'); print(json.dumps(result,indent=2))
