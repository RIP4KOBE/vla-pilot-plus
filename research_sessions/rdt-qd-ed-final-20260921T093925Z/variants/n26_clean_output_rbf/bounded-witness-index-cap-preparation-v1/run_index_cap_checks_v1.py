"""No tensors/imported Torch; original CPU boundary, synthetic-only inputs."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import time
import traceback
import unittest
import unittest.mock

HERE=Path(__file__).resolve().parent
START=time.monotonic()
sys.dont_write_bytecode=True


def load(name):
    path=HERE/(name+'.py')
    spec=importlib.util.spec_from_loader(name,loader=None)
    module=importlib.util.module_from_spec(spec)
    module.__file__=str(path)
    sys.modules[name]=module
    exec(compile(path.read_bytes(),str(path),'exec'),module.__dict__)
    return module


def main():
    summary_path=HERE/'cpu-results-v1.json'
    prior=json.loads(summary_path.read_text()) if summary_path.exists() else []
    consumed=sum(row['wall_seconds'] for row in prior)
    if consumed>=60:raise RuntimeError('cumulative CPU budget exhausted')
    fixture=HERE/'synthetic-index.bin'
    if not fixture.exists():fixture.write_bytes(b'abcd')
    log=HERE/'cpu-checks-v1.log'
    boundary=load('cpu_boundary_v1')
    boundary.establish(60-consumed)
    allowed=[HERE/(n+'.py') for n in ('cpu_boundary_v1','witness_reader_v1','test_index_cap_v1','run_index_cap_checks_v1')]+[fixture]
    boundary.guard(inputs=allowed,writes=[log,summary_path])
    success=False;count=0;error=None
    with log.open('a') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        print('RUN',len(prior)+1)
        try:
            load('witness_reader_v1')
            tests=load('test_index_cap_v1')
            result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
            success=result.wasSuccessful() and not boundary.DENIED
            count=result.testsRun
        except BaseException as exc:
            error=type(exc).__name__+': '+str(exc);traceback.print_exc()
        finally:signal.setitimer(signal.ITIMER_REAL,0)
    elapsed=time.monotonic()-START
    observation=boundary.observation()
    files=[p for p in HERE.iterdir() if p.is_file()]
    total=sum(p.stat().st_size for p in files)
    if len(files)>12 or total>4*1024**2:raise RuntimeError('file/byte scope exceeded')
    row={'passed':success,'tests':count,'wall_seconds':elapsed,'cumulative_seconds':consumed+elapsed,
         'error':error,'boundary':observation,'torch_imported':'torch' in sys.modules,'actual_evidence_reads':False,
         'physical_fixture_bytes':4,'large_payloads':'synthetic in-memory streams through unchanged physical Reader.blob branch',
         'regular_files_before_summary':len(files),'bytes_before_summary':total}
    prior.append(row);summary_path.write_text(json.dumps(prior,indent=2)+'\n')
    print(json.dumps({k:row[k] for k in ('passed','tests','wall_seconds','cumulative_seconds','error','torch_imported')}))
    return 0 if success else 1


if __name__=='__main__':raise SystemExit(main())
