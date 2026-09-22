"""Read-only, cursor-bounded kernel evidence for an admitted GPU episode.

No CUDA imports, device reset, process signalling, or retrospective outcome edits.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess


class MonitorError(RuntimeError):
    pass


def pci_device(value):
    match = re.fullmatch(r'(?:0000)?([0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2})(?:\.[0-7])?', value)
    if not match:
        raise MonitorError('invalid frozen PCI identity')
    return match[1].lower()


class KernelXidMonitor:
    def __init__(self, mapping, output, *, run=None):
        self.run = run or subprocess.run
        self.physical_gpu = mapping['physical_gpu']
        self.pci_bus = pci_device(mapping['pci_bus_id'])
        self.output = Path(output)
        self.pid = None
        self.records = []
        baseline = self._query(['-n', '1'])
        if len(baseline) != 1 or not baseline[0].get('__CURSOR') or not baseline[0].get('_BOOT_ID'):
            raise MonitorError('kernel journal baseline unavailable')
        self.cursor = baseline[0]['__CURSOR']
        self.boot_id = baseline[0]['_BOOT_ID']
        self._save()

    def _query(self, extra):
        try:
            result = self.run(['journalctl', '-k', '-b', '--no-pager', '-o', 'json', *extra],
                              capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                raise MonitorError('kernel journal query failed')
            return [json.loads(line) for line in result.stdout.splitlines()
                    if line.strip() and line.strip() != '-- No entries --']
        except (OSError, subprocess.TimeoutExpired, ValueError, TypeError) as exc:
            raise MonitorError('kernel journal query unavailable') from exc

    def _save(self):
        # Save only NVIDIA Xid records, never arbitrary journal messages.
        payload = {'schema': 'qd-ed-kernel-xid-monitor-v1', 'physical_gpu': self.physical_gpu,
                   'pci_bus': self.pci_bus, 'boot_id': self.boot_id, 'after_cursor': self.cursor,
                   'owned_pid': self.pid, 'records': self.records,
                   'stop_on_xids': [31, 109]}
        path = self.output / 'gpu-kernel-xid.json'
        temporary = path.with_suffix('.tmp')
        temporary.write_text(json.dumps(payload, indent=2) + '\n')
        temporary.replace(path)

    def check(self):
        rows = self._query(['--after-cursor', self.cursor])
        for row in rows:
            if row.get('_BOOT_ID') != self.boot_id or not row.get('__CURSOR'):
                raise MonitorError('kernel journal identity changed')
            self.cursor = row['__CURSOR']
            match = re.match(r'NVRM: Xid \(PCI:([0-9a-fA-F:]+)\): ([0-9]+),', row.get('MESSAGE', ''))
            if not match or pci_device(match[1]) != self.pci_bus:
                continue
            message = row['MESSAGE'].strip()
            pid = re.search(r'\bpid=([0-9]+)', message)
            observed_pid = int(pid[1]) if pid else None
            self.records.append({'xid': int(match[2]), 'message': message,
                                 'journal_cursor': row['__CURSOR'],
                                 'time_unix_us': int(row['__REALTIME_TIMESTAMP']),
                                 'pid': observed_pid, 'owned_pid_match': observed_pid == self.pid})
        self._save()
        faults = [record for record in self.records if record['xid'] in {31, 109}]
        if faults:
            codes = ','.join(str(code) for code in sorted({record['xid'] for record in faults}))
            raise MonitorError(f'new kernel Xid {codes} on admitted GPU')
