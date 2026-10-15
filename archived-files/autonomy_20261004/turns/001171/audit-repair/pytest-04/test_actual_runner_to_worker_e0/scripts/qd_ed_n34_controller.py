"""Read-only OSC instance attestation, installed only inside a released worker.

The reviewed proof is external to candidate evidence. This hook observes the
actual constructor result; it neither changes commands nor controller settings.
"""
from contextlib import contextmanager
import importlib
import inspect
import math
from pathlib import Path
from scripts import qd_ed_n23_worker as w

FIELDS = ('control_delta', 'control_ori', 'control_dim', 'impedance_mode',
          'input_min', 'input_max', 'output_min', 'output_max', 'policy_freq',
          'uncouple_pos_ori', 'interpolator_pos', 'interpolator_ori')

# Reviewed robosuite 1.4.0 instance storage. Proof/receipt keys remain canonical;
# this is an exact adapter, not attribute discovery or a compatibility fallback.
INSTANCE_ATTRIBUTES = {
    'control_delta': 'use_delta',
    'control_ori': 'use_ori',
    'control_dim': 'control_dim',
    'impedance_mode': 'impedance_mode',
    'input_min': 'input_min',
    'input_max': 'input_max',
    'output_min': 'output_min',
    'output_max': 'output_max',
    'policy_freq': 'control_freq',
    'uncouple_pos_ori': 'uncoupling',
    'interpolator_pos': 'interpolator_pos',
    'interpolator_ori': 'interpolator_ori',
}


def serial(value):
    if hasattr(value, 'tolist'):
        value = value.tolist()
    w.canonical_sha(value)  # reject non-JSON and nonfinite values
    return value


def verify_semantics(reference, runtime_ref, closure):
    proof = w.read_ref(reference)
    w.require(proof['schema'] == 'n34-deployed-controller-semantics-v1'
              and proof['runtime'] == runtime_ref and proof['status'] == 'ROOT_REVIEWED'
              and proof['physical_gain_certified'] is False, 'reviewed controller semantics required')
    w.require(proof['module'].startswith('robosuite.') and proof['class'] == 'OperationalSpaceController'
              and proof['source'] == closure['modules'][proof['module']]
              and proof['module'] in closure['required_after'], 'controller loaded source binding')
    expected = proof['instance']
    w.require(set(expected) == set(FIELDS) and expected['control_delta'] is True
              and expected['control_ori'] is True and expected['control_dim'] == 6
              and expected['impedance_mode'] == 'fixed' and expected['policy_freq'] == 20
              and expected['interpolator_pos'] is None and expected['interpolator_ori'] is None,
              'OSC normalized delta/fixed/no-interpolation semantics')
    for key in ('input_min', 'input_max', 'output_min', 'output_max'):
        values = expected[key]
        w.require(isinstance(values, list) and len(values) == 6
                  and all(type(v) in (float,int) and math.isfinite(v) for v in values), 'controller scaling shape/finite')
    w.require(expected['input_min'] == [-1]*6 and expected['input_max'] == [1]*6
              and all(a == -b and b > 0 for a,b in zip(expected['output_min'], expected['output_max'])),
              'zero must map to zero delta; normalized inputs required')
    w.require(proof['semantics'] == {'translation': 'scaled_world_delta', 'rotation': 'scaled_axis_angle_delta',
              'zero_rotation': 'zero_increment_not_absolute_pose', 'gripper': 'minus_open_plus_close',
              'projector_0_01': 'convention_not_measured_gain'}, 'controller interpretation differs')
    # Root must supply source review evidence for set_goal, scale_action and
    # wrapper/gripper forwarding, not a fixture assertion or candidate receipt.
    w.require(set(proof['review_evidence']) == {'set_goal', 'scale_action', 'wrapper_and_gripper'}, 'controller proof coverage')
    for ref in proof['review_evidence'].values():
        evidence = w.read_ref(ref)
        w.require(evidence['kind'] == 'deployed_source_review' and evidence['runtime'] == runtime_ref
                  and evidence['fixture_only'] is False, 'fixture cannot attest deployment')
    return proof


def attest_instance(controller, proof):
    cls = type(controller)
    w.require(cls.__module__ == proof['module'] and cls.__name__ == proof['class'], 'controller class differs')
    path = Path(inspect.getfile(cls)).resolve()
    w.require({'path': str(path), 'sha256': w.sha(path)} == proof['source'], 'controller implementation differs')
    values = {key: serial(getattr(controller, INSTANCE_ATTRIBUTES[key])) for key in FIELDS}
    w.require(values == proof['instance'], 'actual controller config/delta semantics differ')
    return {'source': proof['source'], 'module': cls.__module__, 'class': cls.__name__, 'instance': values}


@contextmanager
def observe_instances(proof):
    module = importlib.import_module(proof['module'])
    cls = getattr(module, proof['class'])
    original = cls.__init__
    records = []
    def observed(self, *args, **kwargs):
        original(self, *args, **kwargs)
        records.append(attest_instance(self, proof))
    cls.__init__ = observed
    try:
        yield records
        w.require(records, 'no deployed controller instance observed')
    finally:
        cls.__init__ = original
