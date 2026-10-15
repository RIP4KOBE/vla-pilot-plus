"""Summarize Stage/guidance activity on five completed, exposed Dev paths only."""
from collections import Counter
import importlib.util
import json
from pathlib import Path
import torch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('parity_reader', HERE/'n21_control_parity_cpu_v1.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
reader.FIELDS = {'decision_context': ('stage', 'use_guidance')}
IDS = (
    'rdt-qd-ed-final-20260921T093925Z__n22_dev_t00_n21_20260930__31c7a7b0fb11',
    'rdt-qd-ed-final-20260921T093925Z__n22_dev_t00_n22_20260930__151029753fc6',
    'rdt-qd-ed-final-20260921T093925Z__n22_dev_t01_n21_20260930__e120fd199382',
    'rdt-qd-ed-final-20260921T093925Z__n22_dev_t01_n22_20260930__08ebc428b0b3',
    'rdt-qd-ed-final-20260921T093925Z__n22_dev_t02_n21_20260930__ea104f7b95bd',
)

def main():
    torch.set_num_threads(1)
    out = HERE/'stage-activity-readonly-result-v1.json'
    assert not out.exists()
    rows = []
    for attempt in IDS:
        events, ref = reader.read(attempt)
        contexts = events['decision_context']
        assert [step for step, _ in contexts] == list(range(0,720,8))
        counts = Counter((int(v['stage']), bool(v['use_guidance'])) for _, v in contexts)
        rows.append({'source': ref, 'decisions': len(contexts),
                     'counts': [{'stage': s, 'guidance': g, 'decisions': n}
                                for (s,g),n in sorted(counts.items())],
                     'guided_stage2_steps': [step for step,v in contexts
                                             if v['stage']==2 and v['use_guidance']]})
    result = {'schema':'completed-dev-stage-activity-v1', 'rows':rows,
              'reader_sha256':reader.sha(__file__),
              'dependency_reader_sha256':reader.sha(reader.__file__),
              'cuda_initialized':torch.cuda.is_initialized(),
              'limitation':'Describes only the listed completed exposed Dev paths. Does not prove absence of guided Stage2 on future or modified trajectories. No provider, Stage, source, protocol or release change follows from this count.'}
    assert not result['cuda_initialized']
    with out.open('x') as f:
        f.write(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'report':str(out),'sha256':reader.sha(out),
                      'rows':[{'attempt':v['source']['attempt_id'],'counts':v['counts'],
                               'guided_stage2_steps':v['guided_stage2_steps']} for v in rows]}))

if __name__=='__main__':
    main()
