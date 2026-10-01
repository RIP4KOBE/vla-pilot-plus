"""Exact current-source reversal and immutable historical byte-boundary tests."""
import hashlib,json
from pathlib import Path
import pytest
from scripts import qd_ed_n29_bridge as bridge

ROOT=Path(__file__).resolve().parents[1]

def test_real_three_file_reverse_and_frozen_pure_helper():
    doc=json.loads((ROOT/bridge.DOC/'reverse-source-v1.json').read_text())
    base=json.loads((ROOT/bridge.DOC/'base-source-v1.json').read_text())
    old={x['path']:x['sha256'] for x in base['files']}
    assert set(doc['files'])==bridge.CHANGED and doc['base_commit']==base['commit']==bridge.BASE
    for path,item in doc['files'].items():
        data=(ROOT/path).read_bytes();assert hashlib.sha256(data).hexdigest()==item['new_sha256']
        lines=data.decode().splitlines(keepends=True)
        for h in reversed(item['hunks']):
            assert lines[h['start']:h['end']]==h['new'];lines[h['start']:h['end']]=h['old']
        assert hashlib.sha256(''.join(lines).encode()).hexdigest()==item['old_sha256']==old[path]
    assert hashlib.sha256((ROOT/'core/qd_population_relative_trust.py').read_bytes()).hexdigest()=='84d629a7d224c51dabe2d8bd962d887debbdc8a7468d72c20e0255134d08150b'

@pytest.mark.parametrize('fault',[None,'unchanged_drift','false_reverse'])
def test_reverse_enforces_unchanged_and_original_bytes(tmp_path,monkeypatch,fault):
    d=tmp_path/bridge.DOC;d.mkdir(parents=True)
    a=tmp_path/'changed';a.write_text('new\n');b=tmp_path/'unchanged';b.write_text('same\n')
    sha=lambda x:hashlib.sha256(x).hexdigest()
    original={'commit':bridge.BASE,'files':[{'path':'changed','sha256':sha(b'old\n')},{'path':'unchanged','sha256':sha(b'same\n')}]}
    patch={'base_commit':bridge.BASE,'files':{'changed':{'old_sha256':sha(b'old\n'),'new_sha256':sha(b'new\n'),'hunks':[{'start':0,'end':1,'old':['old\n'],'new':['new\n']}]}}}
    if fault=='unchanged_drift':b.write_text('drift\n')
    if fault=='false_reverse':patch['files']['changed']['hunks'][0]['old']=['fake\n']
    for name,value in [('base-source-v1.json',original),('reverse-source-v1.json',patch)]: (d/name).write_text(json.dumps(value))
    monkeypatch.setattr(bridge,'CHANGED',{'changed'});monkeypatch.setattr(bridge,'source_paths',lambda p:{'changed','unchanged'})
    source={'files':[{'path':p,'sha256':sha((tmp_path/p).read_bytes())} for p in ('changed','unchanged')]}
    if fault:
        with pytest.raises(ValueError):bridge.reverse_source(tmp_path,source)
    else:assert bridge.reverse_source(tmp_path,source)==original
