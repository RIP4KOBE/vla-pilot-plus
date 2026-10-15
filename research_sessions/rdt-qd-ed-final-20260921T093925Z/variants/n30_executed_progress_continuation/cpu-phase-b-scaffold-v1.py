from pathlib import Path
p=Path('/home/hynx/lizhuo/VLA-Pilot++/.worktrees/exp/eds-qd-autoresearch-libero-swap-ood/research_sessions/rdt-qd-ed-final-20260921T093925Z/variants/n30_executed_progress_continuation/implementation')
for name in ['contract','prepare','supervise','report','bridge']:
 s=(p/f'scripts/qd_ed_n29_{name}.py').read_text().replace('n29','n30').replace('N29','N30').replace('population_relative_trust','executed_progress_continuation').replace('13.5','6.0').replace('20261001','20261003')
 (p/f'scripts/qd_ed_n30_{name}.py').write_text(s)
