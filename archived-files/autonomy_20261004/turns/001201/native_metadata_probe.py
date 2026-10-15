import torch,json,pathlib
out=pathlib.Path(__file__).parent
expected=json.loads((out.parent/'001185/runtime-preparation/native-build-v2.json').read_text())
actual={'torch_version':str(torch.__version__),'cuda_version':torch.version.cuda,'torch_build':torch.__config__.show()}
result={'actual':actual,'matches':{k:actual[k]==expected[k] for k in actual},'cuda_initialized':torch.cuda.is_initialized(),'torch_file':torch.__file__}
(out/'cpu-bootstrap-native-metadata-probe-v1.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='actual'}));print(actual['torch_version'],actual['cuda_version'])
