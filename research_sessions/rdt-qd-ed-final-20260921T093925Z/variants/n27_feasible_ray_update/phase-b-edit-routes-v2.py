from pathlib import Path
I=Path(__file__).parent/'implementation'
p=I/'scripts/qd_ed_final_runner.py';s=p.read_text()
s=s.replace("    if candidate_id == 'N26':", "    if candidate_id == 'N27':\n        from scripts import qd_ed_n27_contract\n        return qd_ed_n27_contract.expand_candidate(candidate, baseline, globals())\n    if candidate_id == 'N26':",1)
s=s.replace('def is_n26_plan(plan):\n    return ',"def is_n27_plan(plan):\n    return plan.get('n27_cohort') is not None or 'N27' in plan.get('candidate_profiles', {})\n\n\ndef is_n26_plan(plan):\n    return not is_n27_plan(plan) and (")
s=s.replace("return not is_n27_plan(plan) and (plan.get('n26_cohort') is not None or 'N26' in plan.get('candidate_profiles', {})","return not is_n27_plan(plan) and (plan.get('n26_cohort') is not None or 'N26' in plan.get('candidate_profiles', {}))")
s=s.replace('return not is_n26_plan(plan) and','return not is_n27_plan(plan) and not is_n26_plan(plan) and')
s=s.replace('return is_n26_plan(plan) or','return is_n27_plan(plan) or is_n26_plan(plan) or')
s=s.replace('def metered_support(plan):','def metered_support(plan):\n    if is_n27_plan(plan):\n        from scripts import qd_ed_n27_contract\n        return qd_ed_n27_contract')
s=s.replace(' or is_n26_plan(plan)),',' or is_n26_plan(plan) or is_n27_plan(plan)),')
s=s.replace("    if row.get('iteration') == 'N25_ACTUATOR_CLIPPED_RBF_DEV_INFRA_CONTINUATION_V1_20260930':\n        from scripts import qd_ed_n25_cont_contract as n25c\n        n25c.require_state", "    if row.get('iteration') == 'N27_FEASIBLE_RAY_SCREEN_20261001':\n        from scripts import qd_ed_n27_contract as n27\n        n27.require_state(state, globals())\n        bucket_caps = n27.BASE_CAPS['buckets']\n    elif row.get('iteration') == 'N25_ACTUATOR_CLIPPED_RBF_DEV_INFRA_CONTINUATION_V1_20260930':\n        from scripts import qd_ed_n25_cont_contract as n25c\n        n25c.require_state",1)
s=s.replace('def check_retry(events, row):',"def check_retry(events, row):\n    if row.get('n27_recovery_eligibility') is not None:\n        from scripts import qd_ed_n27_recovery as recovery\n        return recovery.check_retry(events, row, globals())")
s=s.replace("terminal['n26_episode_dispatched' if is_n26_plan(plan)","terminal['n27_episode_dispatched' if is_n27_plan(plan) else 'n26_episode_dispatched' if is_n26_plan(plan)")
p.write_text(s)
p=I/'scripts/qd_ed_n23_worker.py';s=p.read_text()
a="    if plan.get('n25_infrastructure_continuation') is not None:"
s=s.replace(a,"    if plan.get('n27_cohort') is not None or 'N27' in plan.get('candidate_profiles', {}):\n        from scripts import qd_ed_n27_contract as n27\n        return n27.validate_worker_context(context, main_argv, root, output, plan, runtime)\n"+a,1)
s=s.replace("{'N23', 'N24', 'N25', 'N26'}","{'N23', 'N24', 'N25', 'N26', 'N27'}")
# Duplicate explicit existing N26 routes, keeping each old route literally unchanged.
lines=s.splitlines(True);out=[];i=0
while i<len(lines):
    line=lines[i]
    if "if read_ref(context['plan']).get('n26_cohort') is not None:" in line:
        indent=len(line)-len(line.lstrip());j=i+1
        while j<len(lines) and (not lines[j].strip() or len(lines[j])-len(lines[j].lstrip())>indent):j+=1
        block=''.join(lines[i:j]);out.append(block.replace('n26','n27').replace('N26','N27'))
        out.append(block);i=j
    else:out.append(line);i+=1
p.write_text(''.join(out))
p=I/'scripts/qd_ed_n27_prepare.py';s=p.read_text().replace("'n25_'))","'n25_','n26_'))").replace("('N25','N27')","('N26','N27')").replace('candidate_n25.json','candidate_n26.json')
start=s.index("    plan['n27_cohort']=");end=s.index('    return plan',start)
s=s[:start]+'''    plan['n27_cohort']={'schema':'n27-feasible-ray-screen-v1','cohort_id':c.COHORT,'limits':c.LIMITS,
        'protocol':c.ref(c.PROTOCOL),'source_plan':c.ref(c.SOURCE_PLAN),'timeout_observability':c.ref(c.OBSERVABILITY),
        'final_review':review,'authority':authority,'predecessor':predecessor_ref,
        'budget_reuse':None if review is None else c.ref(c.BUDGET_REUSE),'worker_audit':c.WORKER_CONTRACT,
        'n26_role':'control_only_no_promotion','early_stop':'none_full_sixteen_required'}
'''+s[end:]
s=s.replace('review=review,authority=authority);','review=review,authority=authority,predecessor_ref=c.predecessor());')
p.write_text(s)
p=I/'scripts/qd_ed_n27_supervise.py';s=p.read_text();start=s.index("            if row['profile']=='N27'");end=s.index('    except BaseException',start)
s=s[:start]+'''        promoted=(successes['N27']>=2 and successes['N27']>=max(successes[a] for a in c.ARMS[:-1])
            and successes['N27']>successes['N26']
            and native_totals['N27'].get('guided_decisions',0)>0 and native_totals['N27'].get('parent_rounds_verified',0)>0)
        write('completed_all_sixteen_audited',dev_gate_promoted=promoted)
'''+s[end:];p.write_text(s)
p=I/'scripts/qd_ed_n27_report.py';s=p.read_text().replace('==40','==16').replace('<40','<16').replace('range(10)','range(4)').replace("'planned':40","'planned':16").replace('wins>=5','wins>=2').replace(' and substantive',' and wins>counts[\'N26\'][\'success\'] and substantive')
start=s.index('    futility=');end=s.index('    return ',start)
s=s[:start]+"    decision=('ELIGIBLE_FOR_SEPARATELY_FROZEN_FULL_DEV' if promoted else 'REJECT_SCREEN' if complete and failure is None else 'INVALID_OR_INTERRUPTED')\n"+s[end:]
s=s.replace("((phase=='rejected_numeric_futility' and result['decision']=='REJECT_NUMERIC_FUTILITY')\n        or (phase=='completed_all_forty_audited'", "((phase=='completed_all_sixteen_audited'")
s=s.replace('clipping and zero-gradient counts are descriptive','feasible alpha, clipping and zero-gradient counts are descriptive')
p.write_text(s)
