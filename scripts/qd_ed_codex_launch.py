#!/usr/bin/env python3
"""Launch the frozen GPU7 study using Codex's existing managed ChatGPT login.

No credential file is read or changed. Alternate API credentials are removed
only from the child environment; the caller's Poe/account files are untouched.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import qd_ed_final_runner as runner

ROOT = Path(__file__).resolve().parents[1]
PYTHON = runner.PYTHON
RUNNER = ROOT / 'scripts/qd_ed_final_runner.py'


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument('--runtime-manifest', type=Path, required=True)
    sub = result.add_subparsers(dest='command', required=True)
    for name in ('run', 'validate-plan', 'print-command', 'reconcile-ledger'):
        child = sub.add_parser(name, allow_abbrev=False)
        child.add_argument('--plan', type=Path, default=ROOT / 'data/qd-ed-final-plan.json')
        if name in {'run', 'print-command'}:
            child.add_argument('--split', choices=('dev', 'validation', 'formal'), required=True)
            child.add_argument('--iteration', required=True)
        if name == 'run':
            child.add_argument('--episode-key', action='append')
        if name in {'validate-plan', 'print-command'}:
            child.add_argument('--allow-unfrozen', action='store_true')
        if name == 'reconcile-ledger':
            child.add_argument('--attempt-id', required=True)
    return result


def runner_argv(args):
    argv = [str(PYTHON), str(RUNNER), args.command, '--plan', str(args.plan.resolve())]
    if args.command in {'run', 'print-command'}:
        argv.extend(['--split', args.split, '--iteration', args.iteration])
    if args.command == 'run':
        for key in args.episode_key or []:
            argv.extend(['--episode-key', key])
    if args.command in {'validate-plan', 'print-command'} and args.allow_unfrozen:
        argv.append('--allow-unfrozen')
    if args.command == 'reconcile-ledger':
        argv.extend(['--attempt-id', args.attempt_id])
    return argv


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        # Validate source, runtime and scientific inputs before touching the CLI.
        # The runner repeats these checks immediately before every GPU dispatch.
        plan, _, runtime = runner.validate_plan(
            args.plan, root=ROOT,
            require_frozen=not (getattr(args, 'allow_unfrozen', False)
                                or args.command == 'reconcile-ledger'))
        runner.require(Path(plan['runtime_manifest_path']).resolve() == args.runtime_manifest.resolve(),
                       'Selected manifest differs from the frozen plan binding')
        runner.require(runtime.get('frozen_stage_provider', {}).get('backend') == 'codex_cli',
                       'Selected manifest is not a Codex managed login contract')
        env = runner.child_environment(runtime)
        runner.verify_provider(runtime, env, root=ROOT)
        os.execve(str(PYTHON), runner_argv(args), env)
    except (runner.GateError, OSError, ValueError, KeyError):
        # Never print arbitrary exceptions, subprocess output or account values.
        print('Codex launch refused: frozen inputs, managed login, or executable binding failed verification.',
              file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
