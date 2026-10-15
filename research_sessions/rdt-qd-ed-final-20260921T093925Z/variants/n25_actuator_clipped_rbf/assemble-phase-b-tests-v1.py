from pathlib import Path
import ast
src=Path('tests/test_qd_ed_n24_controller.py').read_text();tree=ast.parse(src)
keep={'write','rows','state','triplet','metric','native_report','draft',
 'test_draft_exact_frozen_identity_mapping_is_nonexecutable','test_full_controller_terminal_reader_and_costs',
 'test_unknown_tokens_independent_of_eligibility','test_terminal_report_retains_cost_when_controller_prefix_lags',
 'test_runtime_alias_strict_ownership_and_provider','test_source_bridge_consumes_settled_strict_backend_json',
 'test_admission_exact_prefix_and_only_complete_quad_futility','test_accepted_terminal_uses_real_runner_base_schema',
 'test_closed_contract_source_profile_matrix'}
lines=src.splitlines(keepends=True);header=src[:src.index('\ndef write')];parts=[header]
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name in keep:
  first=min([node.lineno]+[v.lineno for v in node.decorator_list])-1
  parts.append(''.join(lines[first:node.end_lineno])+'\n\n')
s=''.join(parts).replace('N24','N25').replace('n24','n25').replace('c.CAPS','c.BASE_CAPS')
s=s.replace("m.qd_gripper_rescue_mode=n.MODE;", "m.qd_gripper_rescue_mode='UNUSED';")
s=s.replace("if arm=='N25':\n        m.qd_gripper", "if False:\n        m.qd_gripper")
s=s.replace("if arm=='N25':x['n25_gripper_parent_rescue_audit']", "if False:x['n25_gripper_parent_rescue_audit']")
s=s.replace("['qd_gripper_rescue_mode']='none'", "['initial_diversity_descriptor_mode']='absolute_eef'")
Path('tests/test_qd_ed_n25_controller.py').write_text(s)
s=Path('tests/test_qd_ed_n24_recovery.py').read_text().replace('n24','n25').replace('N24','N25')
s=s.replace("monkeypatch.setattr(c,'require_state',lambda *a:None);", "monkeypatch.setattr(c,'require_state',lambda *a:None);monkeypatch.setattr(c,'budget_authority',lambda:{'caps':c.BASE_CAPS});")
Path('tests/test_qd_ed_n25_recovery.py').write_text(s)
