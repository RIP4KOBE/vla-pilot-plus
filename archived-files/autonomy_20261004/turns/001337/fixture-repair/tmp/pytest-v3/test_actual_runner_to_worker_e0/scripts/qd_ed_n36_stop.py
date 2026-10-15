"""Canonical leaf-15.6 STOP authority. This is a veto, never execution authority.

Lexical owner and relocated entries are pinned by the explicit repair contract;
checkout resolution and caller input cannot replace either entry. Source review
and a new detached release are still required before any production use.
"""
import datetime as dt
import os

OWNER_STOP = '/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP'
DATA_STOP = '/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z/autonomy_20261004/STOP'
STOP_PATHS = (OWNER_STOP, DATA_STOP)
DEADLINE = '2026-10-11T11:13:13Z'


def binding():
    return {'schema': 'n36-canonical-stop-v1', 'owner_source':
            'ca4e6a96d049c7ebb1f302d755883388ddbfdbd8',
            'paths': list(STOP_PATHS), 'deadline': DEADLINE}


def check(*, now=None, ends_at=DEADLINE, need=0):
    """Fail closed; ENOENT alone means absent. Never signal or settle a child."""
    for path in STOP_PATHS:
        try:
            os.lstat(path)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise ValueError('STOP inaccessible: ' + path) from exc
        raise ValueError('STOP present: ' + path)
    now = now or dt.datetime.now(dt.timezone.utc)
    end = min(dt.datetime.fromisoformat(x.replace('Z', '+00:00'))
              for x in (DEADLINE, ends_at))
    if now.tzinfo is None or need < 0 or (end-now).total_seconds() < need or now >= end:
        raise ValueError('deadline: full work headroom unavailable')
