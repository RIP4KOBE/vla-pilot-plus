import ast,json,os,pathlib,sys
sys.path.append('/home/hynx/miniconda3/envs/vla-pilot/lib/python3.12/site-packages')
import torch
assert os.environ['CUDA_VISIBLE_DEVICES']=='7'
assert not torch.cuda.is_initialized()
actual={'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show()}
assert not torch.cuda.is_initialized()
old=json.loads(pathlib.Path(sys.argv[1]).read_text())
result={'actual':actual,'visibility':os.environ['CUDA_VISIBLE_DEVICES'],'cuda_initialized_before':False,'cuda_initialized_after':torch.cuda.is_initialized(),'old_matches':{k:old[k]==v for k,v in actual.items()},'torch_file':torch.__file__}
if len(sys.argv)>3:
 new=json.loads(pathlib.Path(sys.argv[2]).read_text())
 tree=ast.parse(pathlib.Path(sys.argv[3]).read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='attest');expr=fn.body[1].value.args[0]
 predicate=compile(ast.Expression(expr),sys.argv[3],'eval')
 result['existing_exact_metadata_predicate']=ast.unparse(expr)
 result['old_predicate']=eval(predicate,{'expected':old,'torch':torch})
 result['new_predicate']=eval(predicate,{'expected':new,'torch':torch})
 result['new_matches']={k:new[k]==v for k,v in actual.items()}
 assert result['old_predicate'] is False and result['new_predicate'] is True
assert not torch.cuda.is_initialized()
print(json.dumps(result))
