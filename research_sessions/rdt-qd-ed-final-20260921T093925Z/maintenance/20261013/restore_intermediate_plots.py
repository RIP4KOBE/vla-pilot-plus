"""Restore deleted 3D plots for one historical chunk using its retained trace.

Run with the vla-pilot Python environment; no GPU is required.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ['CUDA_VISIBLE_DEVICES']=''
os.environ.setdefault('OMP_NUM_THREADS','1')
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
H=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/historical_variants/eds_init_pg_diverse_sampling')
sys.path.insert(0,str(H))
from core.eds_mechanism_trace import load_mechanism_trace
from utils.eds_mechanism_pretest_vis import _plot_stage,_stage_title,_best_particle_stage

parser=argparse.ArgumentParser()
parser.add_argument('--chunk',type=Path,required=True,help='Absolute chunk directory containing tensors/mechanism_trace.pt')
parser.add_argument('--output-dir',type=Path,help='Optional separate output directory; default restores original paths')
parser.add_argument('--limit',type=int,default=0,help='Optional limit for a regeneration check')
args=parser.parse_args()
chunk=args.chunk.resolve()
assert chunk.is_relative_to((H/'outputs').resolve())
rows=[]
with gzip.open(Path(__file__).parent/'deleted-files.jsonl.gz','rt') as f:
    for line in f:
        row=json.loads(line)
        if row.get('regeneration_trace') and Path(row['regeneration_trace']).parent.parent.resolve()==chunk:rows.append(row)
assert rows,'No deleted plots recorded for this chunk'
trace=load_mechanism_trace(chunk)
stages={int(s.iter_idx):s for s in trace.stages if s.stage in {'full_process_after_rollout','after_rollout'}}
for row in rows[:args.limit or len(rows)]:
    original=Path(row['path']);target=(args.output_dir/original.name) if args.output_dir else original
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256'],f'Refusing to overwrite {target}'
        continue
    stage=stages[int(original.name.split('_')[1])]
    if '_best_trajectory_' in original.name:
        _plot_stage(target,trace,_best_particle_stage(stage),title=f'best {_stage_title(trace,stage)}')
    else:_plot_stage(target,trace,stage,title=_stage_title(trace,stage))
    actual=hashlib.sha256(target.read_bytes()).hexdigest()
    print(json.dumps({'path':str(target),'original_sha256':row['sha256'],'regenerated_sha256':actual,'byte_identical':actual==row['sha256']}))
