from pathlib import Path
p=Path('scripts/qd_ed_n25_contract.py');s=p.read_text();s=s.replace("    w.require(state.get('n25_budget_authority')==ref(BUDGET_AUTHORITY)","    resource=state.get('resource_isolation',{})\n    w.require(resource.get('status')=='ACTIVE' and resource.get('validation_status')=='PASS'\n        and resource.get('private_budget') is True and state.get('max_concurrent_gpu_workers')==1\n        and not state.get('external_resource_hold',{}).get('do_not_auto_resume',False)\n        and budget.get('gpu_hour_reservations')==caps['protected_gpu_hours']\n        and state.get('n25_budget_authority')==ref(BUDGET_AUTHORITY)")
p.write_text(s)
p=Path('../n25_cpu_guard_v3.py');s=Path('../n25_cpu_guard_v2.py').read_text().replace("PUBLIC={'/dev/null'","PUBLIC={'/proc/cpuinfo','/dev/null'").replace('N25_CPU_GUARD_V2','N25_CPU_GUARD_V3');p.write_text(s)
p=Path('tests/test_qd_ed_n25_recovery.py');s=p.read_text();start=s.index("spec=importlib.util.spec_from_file_location('n25_old_synthetic_builders'");end=s.index('\n\n\n@pytest',start)
s=s[:start]+'''from n25_cpu_synthetic import old_builders,install_classifier
old=old_builders()

@pytest.fixture(autouse=True)
def synthetic_classifier(monkeypatch):
    install_classifier(monkeypatch)
'''+s[end:];p.write_text(s)
p=Path('tests/test_qd_ed_n25_controller.py');s=p.read_text();s+='''\n\n@pytest.fixture(autouse=True)
def synthetic_classifier(monkeypatch):
    from n25_cpu_synthetic import install_classifier
    install_classifier(monkeypatch)
''';p.write_text(s)
