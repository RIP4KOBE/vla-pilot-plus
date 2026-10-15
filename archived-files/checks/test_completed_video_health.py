"""CPU-only media and cache corruption checks; immutable real media is only read."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('completed_video_health',HERE/'audit_completed_videos.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
VIDEO=module.ROOT/'.worktrees/exp/steering-integration/runs/eds-common-20261013/output/episode_4/episode_4_success_agentview.mp4'

class VideoCorruptions(unittest.TestCase):
    def test_wrong_frame_count_is_delivery_failure(self):
        report=module.probe_video(VIDEO,121)
        self.assertFalse(report['delivery_valid'])
        self.assertFalse(report['checks']['frame_counts_match_actions'])
        self.assertTrue(report['checks']['full_cpu_decode_ok'])

    def test_cached_report_identity_mismatch_rejected(self):
        report=module.read(module.OUT/'eds-task3.json')
        report['seed']=999
        with self.assertRaisesRegex(ValueError,'identity/source'):
            module.validate_cached_report(report,method='eds',task=3,episode=3,seed=546,video=VIDEO,source=report['source'])

    def test_unknown_cached_checker_rejected(self):
        report=module.read(module.OUT/'eds-task3.json');report['helper_sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Unknown cached'):
            module.validate_cached_report(report,method='eds',task=3,episode=3,seed=546,video=VIDEO,source=report['source'])

    def test_truncated_mp4_is_delivery_failure(self):
        with tempfile.TemporaryDirectory(prefix='steering-video-check-') as folder:
            path=Path(folder)/'truncated.mp4'
            path.write_bytes(VIDEO.read_bytes()[:512])
            report=module.probe_video(path,120)
        self.assertFalse(report['delivery_valid'])
        self.assertFalse(report['checks']['full_cpu_decode_ok'])
        self.assertFalse(report['checks']['ffprobe_ok'])

if __name__=='__main__':unittest.main()
