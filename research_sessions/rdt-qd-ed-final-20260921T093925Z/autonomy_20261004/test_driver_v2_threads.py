import importlib.util,os,unittest
from pathlib import Path
from unittest.mock import patch
A=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('driver2',A/'driver_v2.py');d=importlib.util.module_from_spec(s);s.loader.exec_module(d)
THREADS=('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')
class Focused(unittest.TestCase):
 def test_unset_thread_environment_stays_unset(self):
  with patch.dict(os.environ,{'HOME':'/synthetic','CODEX_HOME':'/synthetic/auth'},clear=True):
   env=d.child_environment();self.assertFalse(set(THREADS)&set(env));self.assertEqual(env,dict(os.environ))
 def test_explicit_runtime_threads_and_auth_preserved(self):
  values=dict(zip(THREADS,['11','8','4','6']))
  with patch.dict(os.environ,{**values,'HOME':'/synthetic','CODEX_HOME':'/synthetic/auth','OPENAI_API_KEY':'REDACTED','POE_API_KEY':'REDACTED','HTTPS_PROXY':'http://synthetic-proxy'},clear=True):
   env=d.child_environment();self.assertEqual({k:env[k] for k in THREADS},values);self.assertEqual(env['HOME'],'/synthetic');self.assertEqual(env['CODEX_HOME'],'/synthetic/auth');self.assertEqual(env['HTTPS_PROXY'],'http://synthetic-proxy');self.assertNotIn('OPENAI_API_KEY',env);self.assertNotIn('POE_API_KEY',env)
 def test_official_command_unchanged(self):
  spec=importlib.util.spec_from_file_location('driver1',A/'driver_v1.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
  self.assertEqual(d.command(Path('/synthetic/W'),Path('/synthetic/turn')),old.command(Path('/synthetic/W'),Path('/synthetic/turn')))
  cmd=d.command(Path('/synthetic/W'),Path('/synthetic/turn'));self.assertIn('--ephemeral',cmd);self.assertIn('--ignore-user-config',cmd);self.assertIn('approval_policy="never"',cmd);self.assertEqual(cmd[0],str(d.CLI));self.assertFalse(any('bypass' in x for x in cmd))
if __name__=='__main__':unittest.main(verbosity=2)
