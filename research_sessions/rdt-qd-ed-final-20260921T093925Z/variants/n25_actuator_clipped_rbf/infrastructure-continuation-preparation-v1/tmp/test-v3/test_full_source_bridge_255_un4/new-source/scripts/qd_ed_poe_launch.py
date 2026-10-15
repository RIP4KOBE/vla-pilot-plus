#!/usr/bin/env python3
"""Bind the authorized local Poe credentials, then exec the owned QD/ED runner.

Credentials stay in memory and the child environment. No shell, interpolation,
credential logging, credential fingerprint, or credential artifact is produced.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path('/home/hynx/miniconda3/envs/vla-pilot/bin/python')
RUNNER = ROOT / 'scripts/qd_ed_final_runner.py'
DEFAULT_CREDENTIALS = Path('/home/hynx/VLA-Pilot++/.env')
POE_ENDPOINT = 'https://api.poe.com/v1'
STAGE_MODEL = 'gemini-2.5-flash'
PROVIDER_VARIABLES = {'OPENAI_BASE_URL', 'OPENAI_API_KEY', 'GOOGLE_API_KEY'}
POE_FILE_VARIABLES = {'OPENAI_BASE_URL', 'OPENAI_API_KEY'}
ASSIGNMENT = re.compile(r'(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)')


class BindingError(RuntimeError):
    """Only fixed, non-secret messages may be supplied to this exception."""


def dotenv_value(raw):
    """Parse one static, single-line dotenv value without evaluating anything."""
    raw = raw.strip()
    if raw[:1] in {'"', "'"}:
        quote = raw[0]
        value = []
        index = 1
        while index < len(raw):
            char = raw[index]
            if char == quote:
                suffix = raw[index + 1:].strip()
                if suffix and not suffix.startswith('#'):
                    raise BindingError('Malformed quoted provider value in credential file')
                result = ''.join(value)
                break
            if char == '\\' and index + 1 < len(raw) and raw[index + 1] in {quote, '\\'}:
                index += 1
                char = raw[index]
            value.append(char)
            index += 1
        else:
            raise BindingError('Unclosed quoted provider value in credential file')
    else:
        # As with dotenv, an unquoted # starts a comment only after whitespace.
        result = '' if raw.startswith('#') else re.split(r'\s+#', raw, maxsplit=1)[0].rstrip()
    if any(char in result for char in ('\x00', '\r', '\n')):
        raise BindingError('Provider values must be single-line strings')
    return result


def read_provider_variables(path):
    try:
        source = Path(path).read_text(encoding='utf-8')
    except (OSError, UnicodeError):
        raise BindingError('Cannot read authorized credential file') from None
    values = {}
    for line in source.splitlines():
        match = ASSIGNMENT.fullmatch(line.strip())
        if not match or match[1] not in POE_FILE_VARIABLES:
            continue
        name, raw = match.groups()
        if name in values:
            raise BindingError('Duplicate provider variable in credential file')
        values[name] = dotenv_value(raw)
    return values


def read_public_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BindingError('Duplicate key in public runtime binding')
            result[key] = value
        return result
    try:
        result = json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)
    except (OSError, UnicodeError, ValueError):
        raise BindingError('Cannot read public runtime binding') from None
    if not isinstance(result, dict):
        raise BindingError('Public runtime binding must be a JSON object')
    return result


def bind_environment(credentials_file, manifest, inherited=None):
    values = read_provider_variables(credentials_file)
    if values.get('OPENAI_BASE_URL') != POE_ENDPOINT:
        raise BindingError('Authorized credential file must bind the frozen Poe HTTPS endpoint')
    frozen = manifest.get('frozen_stage_provider')
    if manifest.get('provider_ready') is not True or not isinstance(frozen, dict):
        raise BindingError('Public runtime manifest has not verified provider readiness')
    if frozen.get('base_url') != POE_ENDPOINT or frozen.get('model') != STAGE_MODEL:
        raise BindingError('Public runtime manifest differs from frozen Poe endpoint or Stage model')
    # Select OPENAI_API_KEY by the frozen Poe environment convention, leaving
    # the Stage client unchanged. This selection does not establish validity.
    source = 'OPENAI_API_KEY'
    if not values.get(source) or not values[source].strip():
        raise BindingError('Authorized credential file contains no effective Stage credential')
    if frozen.get('credential_env_name') != source:
        raise BindingError('Public runtime binding must select the Poe OpenAI credential')
    env = dict(os.environ if inherited is None else inherited)
    # Clear every inherited provider value before injecting the file's binding.
    # Neither the file's Google field nor an inherited one may take precedence
    # over the explicitly selected OPENAI_API_KEY in the unchanged client.
    for name in PROVIDER_VARIABLES:
        env.pop(name, None)
    env.update({name: value for name, value in values.items() if value})
    return env


def parser():
    result = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    result.add_argument('--credentials-file', type=Path, default=DEFAULT_CREDENTIALS)
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
    command = [str(PYTHON), str(RUNNER), args.command, '--plan', str(args.plan.resolve())]
    if args.command in {'run', 'print-command'}:
        command.extend(['--split', args.split, '--iteration', args.iteration])
    if args.command == 'run':
        for key in args.episode_key or []:
            command.extend(['--episode-key', key])
    if args.command in {'validate-plan', 'print-command'} and args.allow_unfrozen:
        command.append('--allow-unfrozen')
    if args.command == 'reconcile-ledger':
        command.extend(['--attempt-id', args.attempt_id])
    return command


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        plan = read_public_json(args.plan)
        if not isinstance(plan.get('runtime_manifest_path'), str):
            raise BindingError('Plan has no public runtime manifest binding')
        if Path(plan['runtime_manifest_path']).resolve() != args.runtime_manifest.resolve():
            raise BindingError('Selected manifest differs from the runner plan binding')
        manifest = read_public_json(args.runtime_manifest)
        env = bind_environment(args.credentials_file, manifest)
        os.execve(str(PYTHON), runner_argv(args), env)
    except BindingError as exc:
        print(f'Poe launch refused: {exc}', file=sys.stderr)
        return 2
    except OSError:
        # Never render an exception containing arbitrary environment values.
        print('Poe launch refused: could not exec the fixed research interpreter', file=sys.stderr)
        return 2
    return 0  # Reachable only when execve is mocked by a CPU test.


if __name__ == '__main__':
    raise SystemExit(main())
