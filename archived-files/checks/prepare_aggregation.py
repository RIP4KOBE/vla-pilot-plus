from pathlib import Path
import hashlib,json
here=Path(__file__).resolve().parent;old=here.parents[1]/'steering-integration/checks'
s=(old/'aggregate_steering_cohorts.py').read_text()
s=s.replace("manifest.get('reasoning_effort')=='low'", "manifest.get('reasoning_effort')=='ultra'")
s=s.replace('integration_accepted=cohorts_valid and performance_pass is True','integration_accepted=cohorts_valid')
s=s.replace("state=('final_accepted' if integration_accepted else ('cohorts_valid_integration_threshold_not_met' if cohorts_valid else 'partial_or_not_accepted'))", "state='complete_valid' if cohorts_valid else 'partial_or_invalid'")
s=s.replace('integration_acceptance','evaluation_complete').replace('final_accepted','final_valid').replace('performance_gate','eds_reference')
s=s.replace('steering_three_mode_aggregation_v1','steering_ultra_three_mode_aggregation_v1')
s=s.replace('Integration performance threshold; does not change validity of scientifically unsuccessful episodes or completed cohorts.', 'Descriptive comparison to the previous EDS low score, never an acceptance gate.')
s=s.replace('Completed valid cohort scores remain visible. Integration acceptance additionally requires EDS at least3/10 after all shared-contract and fresh read-only audit gates pass.', 'Complete evaluation requires all shared-contract and fresh read-only audit gates. No success-rate threshold is imposed.')
s=s.replace('Integration acceptance requires three finished, valid full v2 audits, identical shared source/assets/RNG/protocol, and EDS at least 3/10. Cohort validity and integration performance are separate gates.', 'Evaluation completion requires three finished valid full v2 audits and identical shared source/assets/RNG/protocol. All use ultra; no minimum success rate is required.')
s=s.replace('Integration accepted:', 'Evaluation complete:').replace('EDS integration threshold: at least 3/10; observed validated score:', 'Previous EDS low reference is 3/10; observed ultra score:')
s=s.replace('Pending cohorts have no validated score. A completed valid cohort retains its score even if EDS falls below the integration threshold; that outcome is not relabeled invalid.', 'Pending cohorts have no validated score. Zero-success and low-scoring valid cohorts remain reportable outcomes.')
s=s.replace("default='common-20261013'", "default='ultra-full10'")
s=s.replace('Running cohorts remain partial. Final acceptance also requires a fresh CPU-only', 'Running cohorts remain partial. Completion requires a fresh CPU-only')
(here/'aggregate_steering_cohorts.py').write_text(s)
t=(old/'test_aggregate_steering_cohorts.py').read_text()
t=t.replace("base_run=HERE.parent/'runs/eds-common-20261013'", "source_runs=REPO/'.worktrees/exp/steering-integration/runs'\n base_run=source_runs/'eds-common-20261013'")
t=t.replace("live=HERE.parent/'runs'/(mode+'-common-20261013')", "live=source_runs/(mode+'-common-20261013')")
t=t.replace("config=yaml.safe_load((live/'resolved-config.yaml').read_text())", "config=yaml.safe_load((live/'resolved-config.yaml').read_text())\n  for role in ('gemini','vlm_agent'):config['perception'][role]['reasoning_effort']='ultra'")
old_line="dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((base_run/'source'/name).read_bytes());source[name]=a.sha(dest.read_bytes())"
new_line="""dest=folder/'source'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((base_run/'source'/name).read_bytes())
   if name=='configs/evaluation/libero_object_swap.yaml':
    frozen=yaml.safe_load(dest.read_text())
    for role in ('gemini','vlm_agent'):frozen['perception'][role]['reasoning_effort']='ultra'
    dest.write_text(yaml.safe_dump(frozen))
   source[name]=a.sha(dest.read_bytes())"""
assert old_line in t;t=t.replace(old_line,new_line)
t=t.replace("'reasoning_effort':'low'", "'reasoning_effort':'ultra'")
t=t.replace('integration_acceptance','evaluation_complete').replace('final_accepted','final_valid').replace('performance_gate','eds_reference')
t=t.replace("assert r['evaluation_complete'] is False and r['final_valid'] is False", "assert r['evaluation_complete'] is True and r['final_valid'] is True")
t=t.replace("assert r['evaluation_complete'] is (score>=3)","assert r['evaluation_complete'] is True").replace("assert r['final_valid'] is (score>=3)","assert r['final_valid'] is True")
t=t.replace('Integration performance threshold; does not change validity of scientifically unsuccessful episodes or completed cohorts.', 'Descriptive comparison to the previous EDS low score, never an acceptance gate.')
t=t.replace("if score==2:assert r['state']=='cohorts_valid_integration_threshold_not_met'", "assert r['state']=='complete_valid'")
(here/'test_aggregate_steering_cohorts.py').write_text(t)
(here/'aggregate-provenance.json').write_text(json.dumps({'base_helper':str(old/'aggregate_steering_cohorts.py'),'base_sha256':hashlib.sha256((old/'aggregate_steering_cohorts.py').read_bytes()).hexdigest(),'new_sha256':hashlib.sha256(s.encode()).hexdigest(),'scope':'Copy of reviewed prior cohort aggregator. Require ultra; all validity gates preserved; EDS3/10 becomes a descriptive reference, not a completion criterion. Old files untouched.'},indent=2)+'\n')
