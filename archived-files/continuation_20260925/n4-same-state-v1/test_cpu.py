#!/usr/bin/env python3
"""CPU gates for bounded branch execution and diagnostic-only accounting."""
from __future__ import annotations
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import torch

D=pathlib.Path(__file__).resolve().parent
W=pathlib.Path('/home/hynx/VLA-Pilot++/.worktrees/exp/rdt-qd-ed-final-20260921T093925Z')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
c=load('diagnostic_child',D/'child.py')
r=load('diagnostic_runner',W/'scripts/qd_ed_final_runner.py')

class FakeAdapter:
    def env_postprocessor(self,value): return value

class FakeControl:
    def __init__(self): self.steps=0
    def step(self,action): self.steps+=1

class FakeEnv:
    def __init__(self): self._env=FakeControl();self.num_steps_wait=5
    def reset(self,seed=None): pass

def snap(env): return {'success':False,'steps':env._env.steps}

class DiagnosticCPU(unittest.TestCase):
    def test_command_contrast_and_gripper(self):
        selected=torch.zeros((1,8,7)); archive=selected.clone()
        archive[0,4,0]=.125
        a=c.command_prefix(FakeAdapter(),selected)
        b=c.command_prefix(FakeAdapter(),archive)
        self.assertEqual([i for i in range(8) if not np.array_equal(a[i],b[i])],[4])
        self.assertEqual([i for i in range(8) if not np.array_equal(a[i],a[i])],[])
        self.assertTrue(all(x.dtype==np.float32 and x[-1]==-1 for x in a))

    def test_transition_ceiling_before_step(self):
        env=FakeEnv();lim={'transitions':32}
        with patch.object(c,'snapshot',snap):
            with self.assertRaises(AssertionError): c.run_prefix(env,[np.zeros(7)],lim)
        self.assertEqual(env._env.steps,0)

    def test_state_mismatch_refuses_branch(self):
        env=FakeEnv();lim={'resets':1,'settling_steps':5}
        with patch.object(c,'snapshot',return_value={'not':'initial'}), patch.object(c,'exact',return_value=False):
            with self.assertRaises(c.StateMismatch):
                c.reset_to_initial(env,1045350852,{'initial':True},lim)
        self.assertEqual(lim,{'resets':2,'settling_steps':10})
        self.assertEqual(env._env.steps,0)

    def test_null_official_rate_and_development_cost(self):
        with tempfile.TemporaryDirectory() as directory:
            path=pathlib.Path(directory)/'result.json'
            c.write_result(path,{'diagnostic_only':True,'official_task_success_rate':None})
            self.assertIsNone(r.read_json(path)['official_task_success_rate'])
        ident={'split':'dev','iteration':'diagnostic','profile':'N4_DIAGNOSTIC',
               'task_id':9,'env_seed':1045350852,'policy_seed':1045350852,'init_index':0}
        events=[{'event':'reserved','attempt_id':'x','identity':ident},
                {'event':'dispatched','attempt_id':'x','identity':ident,'budget_bucket':'development'},
                {'event':'valid','attempt_id':'x','identity':ident,'budget_bucket':'development',
                 'outcome_valid':False,'gpu_process_wall_seconds':3600,'diagnostic_only':True}]
        cost=r.budget_snapshot(events)
        self.assertEqual((cost['dispatched'],cost['invalid'],cost['by_bucket']['development']), (1,1,1))
        self.assertEqual(cost['gpu_hours_consumed'],1.)

if __name__=='__main__':unittest.main()
