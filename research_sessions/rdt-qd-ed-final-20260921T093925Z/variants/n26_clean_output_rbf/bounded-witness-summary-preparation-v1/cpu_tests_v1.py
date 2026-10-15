"""One bounded synthetic invocation; child argv registrations are exact and owned."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time
import types

START=time.monotonic();HERE=Path(__file__).resolve().parent
from cpu_boundary_v1 import establish,guard,observation
establish(float(os.environ.get('WITNESS_TEST_SECONDS','160')))
os.chdir(HERE)
fixture=HERE/'fixture';episode=fixture/'attempt-N25/eds_eval/decision_evidence/episode_000'
names=[fixture/n for n in ('source.json','plan.json','result.json','terminal-input.json','review.json')]
names += [fixture/'attempt-N25/eds_eval'/n for n in ('in-worker-audit-receipt.json','decision-evidence-audit.json')]
names += [episode/'events.jsonl',episode/'bundle_000000.pt']
names += [HERE/'synthetic-input-v1.json',HERE/'synthetic-output-v1.json',HERE/'synthetic-output-v2.json']
children=set()
guard(inputs=[HERE/n for n in ('cpu_boundary_v1.py','witness_reader_v1.py','test_witness_reader_v1.py','cpu_tests_v1.py','input-disabled-v1.json')]+names,
      writes=names,test_children=children)

def load(name):
    p=HERE/(name+'.py');m=types.ModuleType(name);m.__file__=str(p);sys.modules[name]=m
    exec(compile(p.read_bytes(),str(p),'exec'),m.__dict__);return m


def child(argv,limit=25):
    children.add(tuple(argv));start=time.monotonic()
    p=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,cwd=HERE,env=dict(os.environ))
    sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ);data=bytearray()
    try:
        while sel.get_map():
            if time.monotonic()-start>limit:raise TimeoutError('owned child deadline')
            for key,_ in sel.select(.1):
                chunk=os.read(key.fd,4096)
                if not chunk:sel.unregister(key.fileobj);continue
                data.extend(chunk)
                if len(data)>65536:raise RuntimeError('owned child output cap')
        rc=p.wait(timeout=2)
    except BaseException:
        p.kill();p.wait(timeout=2);raise
    finally:sel.close();p.stdout.close()
    text=bytes(data).decode(errors='replace');print(json.dumps({'child':argv,'returncode':rc,'seconds':time.monotonic()-start,'output':text}),flush=True)
    return rc,text

status=1
try:
    rc,raw=child([sys.executable,'-B',str(HERE/'cpu_boundary_v1.py'),'--allocation-probe'])
    assert rc==0 and json.loads(raw)['allocation_refused'] and not json.loads(raw)['guard_denials']
    w=load('witness_reader_v1');cli_only=sys.argv[1:]==['--cli-only'];tests_only=sys.argv[1:]==['--tests-only']
    assert cli_only or tests_only or sys.argv[1:]==[]
    if cli_only:status=0
    else:
        # Initialize the permitted dependency while the search path is still
        # narrow; pytest's default collection temporarily prepends this directory.
        w.torch_cpu()
        tests=load('test_witness_reader_v1');import pytest
        options=['-q','-s','--assert=plain','-p','no:cacheprovider','-p','no:logging','--noconftest','--confcutdir='+str(HERE),'-c','/dev/null',str(HERE/'test_witness_reader_v1.py')]
        if os.environ.get('WITNESS_TEST_SELECT'):options+=['-k',os.environ['WITNESS_TEST_SELECT']]
        status=pytest.main(options)
    if status==0 and not tests_only:
        if cli_only:inp=(HERE/'synthetic-input-v1.json').read_bytes()
        else:
            f=tests.Fixture(slots=w.SLOTS)
            for path,b in f.store.items():
                with Path(path).open('xb') as h:h.write(b)
            inp=tests.encoded(f.data)
            with (HERE/'synthetic-input-v1.json').open('xb') as h:h.write(inp)
        output=HERE/('synthetic-output-v2.json' if cli_only else 'synthetic-output-v1.json')
        command=[sys.executable,'-B',str(HERE/'witness_reader_v1.py'),'--input',str(HERE/'synthetic-input-v1.json'),'--input-sha256',w.digest(inp),'--output',str(output)]
        rc,raw=child(command,30);assert rc==0
        out=json.loads(output.read_bytes())
        assert out['extraction_status']=='COMPLETE' and out['read_progress']['containers_loaded']==1
        assert out['boundary']['rlimit_as_bytes']==[8*1024**3]*2 and not out['boundary']['guard_denials'] and not out['boundary']['cuda_initialized']
        rc,raw=child(command);assert rc!=0 and 'output must be a new' in raw
except BaseException as exc:
    status=1;print(json.dumps({'harness_error':type(exc).__name__,'message':str(exc)}),flush=True)
    import traceback;traceback.print_exc()
finally:
    obs=observation();elapsed=time.monotonic()-START
    if obs['guard_denials'] or obs['cuda_initialized']:status=1
    print(json.dumps({'invocation_wall_seconds':elapsed,'status':status,'boundary':obs,'actual_inputs_read':False}),flush=True)
raise SystemExit(status)
