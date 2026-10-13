"""Create hash-bound task/RNG sidecars outside an unchanged, terminal run archive."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.steering_archive import prepare_support


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    parser.add_argument('--support-dir', required=True, help='New separate sidecar directory')
    parser.add_argument('--task-map', help='Optional copy; must match frozen LIBERO asset SHA')
    parser.add_argument('--rng-manifest', help='Optional copy; must match frozen config SHA')
    args=parser.parse_args()
    print(json.dumps(prepare_support(args.run_dir,args.support_dir,
        task_map=args.task_map,rng_manifest=args.rng_manifest),indent=2))
