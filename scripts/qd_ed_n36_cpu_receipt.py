"""CPU-only source-bootstrap diagnostic; no episode, Main, device or release.

Receipts exercise the production attestors and parent-consumed formats. Both
snapshots use after=False: full post-episode coverage remains a release gate.
"""
import datetime as dt
import json
import os
from pathlib import Path
import sys


def main():
    from scripts import qd_ed_n23_worker as w
    context_ref = {'path': sys.argv[1], 'sha256': sys.argv[2]}
    context = w.read_ref(context_ref)

    def guard():
        w.require(os.environ.get('CUDA_VISIBLE_DEVICES') == ''
                  and len(os.sched_getaffinity(0)) <= 2, 'bounded CPU diagnostic only')
        w.require(context['release_enabled'] is False, 'diagnostic has no release')
        w.require(len(context['stop_paths']) == 2
                  and all(not os.path.lexists(p) for p in context['stop_paths']), 'STOP diagnostic')
        w.require(dt.datetime.now(dt.timezone.utc) < dt.datetime.fromisoformat(
            context['deadline'].replace('Z', '+00:00')), 'diagnostic deadline')

    guard()
    from scripts import qd_ed_n36_worker as worker, qd_ed_n36_source as execution
    from scripts import qd_ed_n34_source as closure
    import pandas
    import scipy.linalg
    import sklearn
    guard()
    # Only native CPU package imports. No simulator construction or model call.
    process = {'pid': os.getpid(),
               'proc_start_ticks': int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]),
               'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    frozen = w.read_ref(context['runtime_closure'])
    source = w.read_ref(context['source'])
    result = {'schema': 'n36-cpu-bootstrap-diagnostic-v1', 'context': context_ref,
              'process': process, 'release_enabled': False, 'full_after_coverage': False}
    for phase in ('runtime_before', 'runtime_after'):
        guard()
        binding = worker.runtime_receipt_binding(context_ref, context, process, phase)
        result[phase] = closure.attest_runtime_receipt(frozen, frozen['runtime'],
                                                      binding=binding, after=False)
        result['loaded_' + phase] = worker.attest_worker_loaded(context['worktree'], source)
        result['execution_' + phase] = execution.attest(context['worktree'], source, frozen)
    guard()
    destination = Path(context['output'])
    w.require(not destination.exists(), 'immutable CPU diagnostic output')
    destination.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
