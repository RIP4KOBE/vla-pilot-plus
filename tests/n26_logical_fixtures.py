"""Synthetic common evidence + logical gate; no actual artifacts or Git process."""
import json
from pathlib import Path
from scripts import qd_ed_n26_logical as logical,qd_ed_n26_contract as c
from n25_downstream_fixtures import complete_fixture,fake_cleanup,put
ACTUAL=Path(__file__).resolve().parents[1]


def gate_fixture(tmp,monkeypatch,kind='reject'):
    data,objects=complete_fixture(tmp,monkeypatch,kind)
    common=logical.common;owner=Path(data['owning_root']);root=owner.parent/'variants/n26_clean_output_rbf';root.mkdir()
    monkeypatch.setattr(c,'ROOT',owner);monkeypatch.setattr(c,'RUN_DIR',root)
    monkeypatch.setattr(c,'PREDECESSOR',root/'predecessor-logical-review-v1.json')
    for name in ('protocol-v1.md','admission-addendum-v1.md','common-source-v1.json'):
        p=owner/logical.DOC/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((ACTUAL/logical.DOC/name).read_bytes())
    monkeypatch.setattr(c,'LOGICAL_PROTOCOL',owner/logical.DOC/'protocol-v1.md')
    cp=owner/'scripts/qd_ed_n25_cont_downstream.py';cp.write_bytes((ACTUAL/'scripts/qd_ed_n25_cont_downstream.py').read_bytes())
    monkeypatch.setattr(common,'__file__',str(cp))
    original=common.build;calls=[]
    def build(d):
        calls.append('bounded_common_build');return original(d,objects=objects,cleanup=fake_cleanup)
    monkeypatch.setattr(common,'build',build)
    evidence=build(data);evidence['input']=put(common.c.RUN_DIR.parent/'common-metadata-input.json',data)
    reference=put(common.c.RUN_DIR/'logical-dev-evidence-v1.json',evidence)
    seal=json.loads(Path(data['references']['seal']['path']).read_text());monkeypatch.setattr(c,'runtime_ref',lambda:seal['runtime'])
    record={'schema':'n26-logical-predecessor-review-v1','disposition':'VALID_LOGICAL_DEV_REJECTION','allow_n26':True,'allow_validation':False,
        'logical_disposition':evidence['logical_disposition'],'common_evidence':reference,
        'continuation_root_review':evidence['provenance']['root_review'],'common_reader':evidence['reader'],
        'runtime':seal['runtime'],'historical_backend_proof':evidence['settled_original_resource']['reference'],
        'composition_protocol':c.ref(c.LOGICAL_PROTOCOL),'admission_addendum':c.ref(owner/logical.DOC/'admission-addendum-v1.md')}
    put(c.PREDECESSOR,record)
    return record,evidence,data,calls
