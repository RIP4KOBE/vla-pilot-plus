"""The queued experiment cannot bypass completion, source or cancellation gates."""
import importlib.util
import json
from pathlib import Path

import pytest


def setup_queue(monkeypatch,tmp_path,*,success=0,valid=True,exit_code=0):
    script=Path(__file__).with_name('continue_after_v13.py')
    spec=importlib.util.spec_from_file_location('continuation_under_test',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for name in ('ROOT','ART','DRAFT','PREVIOUS','QUEUE'):
        value=tmp_path/name;value.mkdir();monkeypatch.setattr(module,name,value)
    (module.ROOT/'data').mkdir()
    (module.ART/'codex-only-provider-authorization-20260930.json').write_text(json.dumps({'poe_allowed':False}))
    (module.QUEUE/'predecessor-identities.json').write_text('{}')
    (module.PREVIOUS/'output').mkdir()
    (module.PREVIOUS/'output/status.json').write_text(json.dumps({'status':'exited','exit_code':exit_code,'completed':10}))
    (module.PREVIOUS/'audit.json').write_text(json.dumps({'valid':valid,'success':success}))
    (module.PREVIOUS/'deep-audit.json').write_text(json.dumps({'valid':True}))
    calls=[]
    monkeypatch.setattr(module,'execute',lambda command,name:calls.append(name))
    monkeypatch.setattr(module,'record_state',lambda **kw:calls.append(kw))
    monkeypatch.setattr(module,'prepend_status',lambda text:calls.append(text))
    monkeypatch.setattr(module,'reserve_own_hours',lambda:calls.append('reserve_own_hours'))
    def forbidden(*args,**kw):
        pytest.fail('No worker may start through these guards')
    monkeypatch.setattr(module.subprocess,'Popen',forbidden)
    return module,calls


@pytest.mark.parametrize('valid,exit_code',[(False,0),(True,-15),(True,1)])
def test_incomplete_or_invalid_predecessor_never_installs_or_dispatches(monkeypatch,tmp_path,valid,exit_code):
    module,calls=setup_queue(monkeypatch,tmp_path,valid=valid,exit_code=exit_code)
    with pytest.raises(AssertionError):module.main()
    assert calls==[]
    assert not (module.QUEUE/'applied-source.json').exists()


def test_score_gate_requires_review_instead_of_scheduling_another_experiment(monkeypatch,tmp_path):
    module,calls=setup_queue(monkeypatch,tmp_path,success=3)
    module.main()
    assert json.loads((module.QUEUE/'status.json').read_text())['phase']=='V13_SCORE_GATE_REACHED_VIDEO_REVIEW_REQUIRED'
    assert 'reserve_own_hours' not in calls
    assert not (module.QUEUE/'applied-source.json').exists()


def test_explicit_queue_cancellation_prevents_all_mutations(monkeypatch,tmp_path):
    module,calls=setup_queue(monkeypatch,tmp_path)
    (module.QUEUE/'cancel.json').write_text('{}')
    module.main()
    assert calls==[]
    assert json.loads((module.QUEUE/'status.json').read_text())['phase']=='CANCELLED_BEFORE_DISPATCH'


def test_changed_frozen_source_is_not_overwritten(monkeypatch,tmp_path):
    module,_=setup_queue(monkeypatch,tmp_path)
    (module.ROOT/'example.py').write_text('user edit')
    (module.PREVIOUS/'manifest.json').write_text(json.dumps({'source_sha256':{'example.py':'wrong hash'}}))
    with pytest.raises(AssertionError):module.main()
    assert (module.ROOT/'example.py').read_text()=='user edit'
    assert not (module.QUEUE/'applied-source.json').exists()
