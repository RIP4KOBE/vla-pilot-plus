from pathlib import Path
p=Path('scripts/qd_ed_n25_contract.py');s=p.read_text();old="""    w.require(dev.get('source_commit')==record['source_commit'] and review.get('result')==record['dev_result']
        and review.get('accepted') is True and review.get('source_commit')==record['source_commit'],
        'N25 predecessor source/result review differs')""";new="""    source=w.read_ref(review['source'])
    w.require(dev.get('source_commit')==record['source_commit'] and review.get('result')==record['dev_result']
        and review.get('schema')=='n24-root-terminal-review-v2'
        and review.get('decision')=='ACCEPT_TERMINAL_RECONSTRUCTION'
        and source.get('commit')==record['source_commit'] and len(source.get('files',[]))==230
        and source.get('sha256')==w.canonical_sha(source['files']) and review.get('source_files_verified')==230
        and review.get('cohort_disposition')==dev.get('decision')
        and review.get('accepted_cells')==dev.get('audited_cells')
        and review.get('counts')==dev.get('counts') and review.get('native')==dev.get('native')
        and review.get('plan')==dev.get('plan') and review.get('ledger')==dev.get('ledger_snapshot')
        and dev.get('controller_evidence',{}).get('consistent') is True,
        'N25 predecessor source/result root reconstruction differs')"""
assert old in s;s=s.replace(old,new);p.write_text(s)
p=Path('tests/test_qd_ed_n25_controller.py');s=p.read_text();s=s.replace("dr=write(tmp_path/'dev.json',dev)\n    review={'result':dr,'accepted':fault!='missing_review','source_commit':dev['source_commit']}\n    if fault=='source':review['source_commit']='other'", """dev.update(counts={'synthetic':'aggregate'},native={'synthetic':'counts'},plan=write(tmp_path/'old-plan.json',{}),
        ledger_snapshot=write(tmp_path/'old-ledger.json',[]),controller_evidence={'consistent':True})
    dr=write(tmp_path/'dev.json',dev)
    files=[{'path':f'synthetic{i}.py','sha256':'a'*64} for i in range(230)]
    source={'commit':'other' if fault=='source' else dev['source_commit'],'files':files,'sha256':w.canonical_sha(files)}
    review={'schema':'n24-root-terminal-review-v2','result':dr,'decision':'WRONG' if fault=='missing_review' else 'ACCEPT_TERMINAL_RECONSTRUCTION',
        'source':write(tmp_path/'source.json',source),'source_files_verified':230,'cohort_disposition':dev['decision'],
        'accepted_cells':dev['audited_cells'],'counts':dev['counts'],'native':dev['native'],'plan':dev['plan'],'ledger':dev['ledger_snapshot']}""")
p.write_text(s)
p=Path('scripts/qd_ed_n25_preflight.py');s=p.read_text().replace("def child(plan_path):\n    from scripts", "def child(plan_path):\n    started=time.perf_counter()\n    from scripts").replace("    started=time.perf_counter();identity=w.process_identity()", "    identity=w.process_identity()");p.write_text(s)
p=Path('docs/03_evidence/qd_ed_final/n25/controller-contract-v1.md');s=p.read_text().replace("original result/ref and aggregate root review (accepted/source_commit/result)","original result/ref and the real n24-root-terminal-review-v2 schema (decision=ACCEPT_TERMINAL_RECONSTRUCTION, source manifest commit/files/sha256, accepted_cells/counts/native/plan/ledger bindings)");p.write_text(s)
