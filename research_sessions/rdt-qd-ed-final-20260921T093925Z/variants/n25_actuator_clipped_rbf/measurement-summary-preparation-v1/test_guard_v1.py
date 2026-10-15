"""Guard negatives use deliberately nonexistent synthetic targets, no real payload."""
import json, socket, subprocess, unittest
from pathlib import Path
import guard_v1

H=Path(__file__).resolve().parent
F=H/'guard-synthetic-fixtures'
F.mkdir(exist_ok=True)
(F/'allowed.json').write_text('{}\n')
guard=guard_v1.install(synthetic_root=F,write_paths=[str(H/'cpu-guard-negative-v1.json')])

class GuardTests(unittest.TestCase):
    def test_allow_owned_synthetic_json(self):
        self.assertEqual(json.loads((F/'allowed.json').read_text()),{})
    def test_read_outside_scope_blocked(self):
        with self.assertRaises(PermissionError):(H/'nonexistent-real-result-placeholder.json').read_text()
    def test_write_outside_scope_blocked(self):
        with self.assertRaises(PermissionError):(H/'nonexistent-authority-placeholder.json').write_text('{}')
    def test_tensor_even_owned_blocked(self):
        with self.assertRaises(PermissionError):(F/'unread.pt').read_bytes()
    def test_network_before_socket_created(self):
        with self.assertRaises(PermissionError):socket.socket()
    def test_subprocess_before_launch(self):
        with self.assertRaises(PermissionError):subprocess.Popen(['/bin/true'])
    def test_torch_before_import(self):
        with self.assertRaises(PermissionError):__import__('torch')

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuardTests))
    guard['expected_negative_denials']=6
    guard['unexpected_denials']=len(guard['denied'])-6
    (H/'cpu-guard-negative-v1.json').write_text(json.dumps(guard,indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
