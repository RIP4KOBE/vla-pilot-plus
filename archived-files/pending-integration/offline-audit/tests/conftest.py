"""Test only local offline evidence; copied scripts import no runtime/model modules."""
import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]))

@pytest.fixture(autouse=True)
def forbid_original_run_reads(monkeypatch):
    """Even on the author's workstation, retained evidence must be self-contained."""
    import builtins
    import io
    import json
    from steering_audit_fixture import FIXTURE,read_fixture_file
    source_run=json.loads((FIXTURE/'provenance.json').read_bytes())['source_run']
    source_asset_root=json.loads(read_fixture_file('environment.json'))['libero']['root']
    prohibited=[source_run,source_asset_root]
    def guard(original):
        def opened(file,*args,**kwargs):
            if isinstance(file,(str,bytes,Path)):
                text=str(file)
                if any(text==p or text.startswith(p+'/') for p in prohibited):
                    raise AssertionError('Test attempted an original run/asset dependency: '+text)
            return original(file,*args,**kwargs)
        return opened
    monkeypatch.setattr(builtins,'open',guard(builtins.open))
    monkeypatch.setattr(io,'open',guard(io.open))
