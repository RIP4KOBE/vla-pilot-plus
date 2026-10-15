"""CPU synthetic metadata/layout tests; no video decoding or image viewing."""
import importlib.util
from pathlib import Path
import sys
import unittest
spec=importlib.util.spec_from_file_location('extractor',Path(__file__).with_name('extract_fixed_grid.py'))
x=importlib.util.module_from_spec(spec);spec.loader.exec_module(x)

class MetadataTests(unittest.TestCase):
    def test_exact_approved_grid(self):
        self.assertEqual(len(x.GRID),16)
        self.assertEqual(x.GRID[-1],719)
        self.assertEqual(x.selection_filter(x.GRID).count('eq(n'),16)
        with self.assertRaisesRegex(ValueError,'unapproved'):
            x.selection_filter(x.GRID+[720])

    def test_before_action_caption_boundary(self):
        arm={'decisions':[{'global_step':0,'last_executed_step':7,'decision_id':'a','stage':1,'use_guidance':True},
            {'global_step':8,'last_executed_step':15,'decision_id':'b','stage':2,'use_guidance':False}]}
        self.assertEqual(x.caption_context(arm,7)['decision_id'],'a')
        self.assertEqual(x.caption_context(arm,8)['decision_id'],'b')
        with self.assertRaisesRegex(ValueError,'missing_or_ambiguous'):
            x.caption_context(arm,16)

    def test_overlap_fails(self):
        row={'global_step':0,'last_executed_step':7,'decision_id':'a','stage':1,'use_guidance':True}
        with self.assertRaises(ValueError):x.caption_context({'decisions':[row,row]},0)

    def test_decoded_count_not_selected_count(self):
        log='Input stream #0:0 (video): 720 packets read (10 bytes); 720 frames decoded; 0 decode errors;\nOutput stream #0:0 (video): 16 frames encoded;'
        self.assertEqual(x.decoded_count(log),720)
        with self.assertRaises(ValueError):x.decoded_count('frame=16')

    def test_fixed_nonoverlapping_layout(self):
        cells=[x.cell_position(r,c) for r in range(3) for c in range(4)]
        self.assertEqual(len(set(cells)),12)
        self.assertTrue(all(px+480<=1980 and py+536<=1656 for px,py in cells))
        self.assertEqual(x.cell_position(2,3),(1488,1108))

    def test_no_torch_or_gpu_dependency(self):
        self.assertNotIn('torch',sys.modules)

if __name__=='__main__':unittest.main()
