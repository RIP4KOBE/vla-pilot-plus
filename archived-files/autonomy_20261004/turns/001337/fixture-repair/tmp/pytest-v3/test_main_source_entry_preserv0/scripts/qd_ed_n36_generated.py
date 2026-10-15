"""Pre-execution admission for the existing, fixed Torch generated-source rule.

This is not a runtime closure: production attestation still requires the frozen
closure and its process-bound generated receipt. No observed hash grants trust.
"""
from pathlib import Path
import sys
from scripts import qd_ed_n34_source as runtime

CONTENT_SHA = '8205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8'


def admit(directory, compiled):
    site = Path(sys.prefix) / ('lib/python%d.%d/site-packages' % sys.version_info[:2])
    records = {
        runtime.GENERATOR_NAME: {'path': str(site / 'torch/distributed/nn/jit/instantiator.py'),
                                 'sha256': runtime.GENERATOR_SHA},
        runtime.TEMPLATE_NAME: {'path': str(site / 'torch/distributed/nn/jit/templates/remote_module_template.py'),
                                'sha256': runtime.TEMPLATE_SHA},
    }
    rule = {'rule': runtime.GENERATED_RULE, 'generator': records[runtime.GENERATOR_NAME],
            'template': records[runtime.TEMPLATE_NAME], 'sha256': CONTENT_SHA}
    closure = {'schema': 'n34-runtime-source-closure-v2', 'modules': records,
               'generated_modules': {runtime.GENERATED_NAME: rule},
               'required_after': [runtime.GENERATED_NAME]}
    for name, record in records.items():
        runtime.w.require(compiled.get((name, record['path'])) == record['sha256'],
                          'N36 generated owner/template execution differs')
    # Reuse canonical live origin, TemporaryDirectory/finalizer, pinned template
    # derivation and source-byte checks, including during module initialization.
    inventory = runtime._generated_runtime(closure, scan_loaded=False)
    generator = sys.modules[runtime.GENERATOR_NAME]
    path = Path(directory)
    expected = path / (runtime.GENERATED_NAME + '.py')
    runtime.w.require(str(path) == generator.INSTANTIATED_TEMPLATE_DIR_PATH
                      and set(path.iterdir()) == {expected},
                      'N36 generated directory contains foreign source')
    runtime._runtime_file({'path': str(expected), 'sha256': CONTENT_SHA})
    return inventory
