#!/usr/bin/env python3
"""Relocate this session's Git worktrees without altering their history or evidence."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import time

EXP=Path('/home/hynx/VLA-Pilot++/.worktrees/exp')
HERE=Path(__file__).resolve().parent
MAPPING={
    'rdt-qd-ed-decision-evidence-20260923':'variants/support/decision_evidence',
    'rdt-qd-ed-executed-quality-20260923':'variants/n2_executed_quality/implementation',
    'rdt-qd-ed-n2-runner-20260923':'variants/n2_executed_quality/runner',
    'rdt-qd-ed-n3-runner-20260924':'variants/n3_executed_feedback/runner',
    'rdt-qd-ed-n4-terminal-20260924':'variants/n4_terminal_population/implementation',
    'rdt-qd-ed-n4-audit-20260924':'variants/n4_terminal_population/audit',
    'rdt-qd-ed-n4-runner-20260924':'variants/n4_terminal_population/runner',
    'rdt-qd-ed-n4-evaluation-audit-20260924':'variants/n4_terminal_population/evaluation_audit',
    'rdt-qd-ed-n4-evaluation-runner-20260924':'variants/n4_terminal_population/evaluation_runner',
    'rdt-qd-ed-n4-e1-runner-20260924':'variants/n4_terminal_population/e1_transport_runner',
    'rdt-qd-ed-stage-lifecycle-20260924':'variants/n4_terminal_population/stage_lifecycle',
    'rdt-qd-ed-final-20260921T093925Z':'study_worktree',
}
ARTIFACTS=Path('/mnt/data/shared2/hynx/VLA-Pilot++/rdt-qd-ed-final-20260921T093925Z')

def git(*args,cwd=EXP):
    return subprocess.check_output(('git',*args),cwd=cwd,text=True).strip()

def main():
    assert HERE == (EXP/'eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z').resolve()
    assert ARTIFACTS.is_dir() and not ARTIFACTS.is_symlink()
    entries=[]
    for oldname,newrel in MAPPING.items():
        old=EXP/oldname;new=HERE/newrel
        assert old != new and new.is_relative_to(HERE)
        new.parent.mkdir(parents=True,exist_ok=True)
        if old.is_symlink():
            assert old.resolve()==new.resolve() and new.is_dir(),f'incompatible alias {old}'
        else:
            assert old.is_dir() and not new.exists(),f'not movable {old}'
            head=git('-C',str(old),'rev-parse','HEAD')
            git('worktree','move',str(old),str(new))
            old.symlink_to(new,target_is_directory=True)
            assert git('-C',str(old),'rev-parse','HEAD')==head
        entries.append({'old_path':str(old),'archive_path':str(new),
                        'head':git('-C',str(new),'rev-parse','HEAD'),
                        'old_path_is_compatibility_symlink':old.is_symlink()})
        print(json.dumps({'archived':oldname,'at':str(new)}),flush=True)
    link=HERE/'artifacts'
    if link.is_symlink():
        assert link.resolve()==ARTIFACTS.resolve()
    else:
        assert not link.exists()
        link.symlink_to(ARTIFACTS,target_is_directory=True)
    record={'schema':'rdt-qd-ed-current-session-archive-v1',
            'created_unix':time.time(),'study_id':'rdt-qd-ed-final-20260921T093925Z',
            'algorithm_variants':entries,
            'artifact_entry':str(link),'artifact_storage':str(ARTIFACTS),
            'artifact_strategy':'symlink; original frozen absolute paths remain canonical',
            'excluded_active_or_other_session':['rdt-qd-ed-gpu6-20260922T063626Z'],
            'excluded_historical':['eds-init-fps','eds-init-pg-diverse-sampling',
              'eds-qd-stage-guidance-transition','eds-quality-diversity'],
            'protected_historical_file_touched':False}
    out=HERE/'archive-layout-v1.json'
    temporary=out.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    os.replace(temporary,out)
    print(json.dumps({'manifest':str(out),'entries':len(entries)}),flush=True)

if __name__=='__main__':main()
