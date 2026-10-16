"""Hash-bound offline archive lookup. Never rewrite scientific run receipts."""
import hashlib
import json
from pathlib import Path
import shutil

import yaml

TASK_MAP = 'libero/libero/benchmark/libero_suite_task_map.py'
SUPPORT_FILES = {'task_map': 'libero_suite_task_map.py', 'rng_manifest': 'fixture-manifest.json'}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_bytes())


def frozen_inputs(folder, manifest=None, config=None):
    folder = Path(folder).resolve()
    actual_manifest = read_json(folder/'manifest.json')
    if manifest is not None and manifest != actual_manifest:
        raise ValueError('Caller manifest differs from saved manifest')
    manifest = actual_manifest
    if digest(folder/'resolved-config.yaml') != manifest['config_sha256']:
        raise ValueError('Frozen config hash mismatch')
    actual_config = yaml.safe_load((folder/'resolved-config.yaml').read_bytes())
    if config is not None and config != actual_config:
        raise ValueError('Caller config differs from saved frozen config')
    if digest(folder/'environment.json') != manifest['environment_sha256']:
        raise ValueError('Frozen environment hash mismatch')
    return manifest, actual_config, read_json(folder/'environment.json')


def execution_identity(folder, manifest=None, config=None):
    """Execution paths are hash-bound metadata, not paths to trust for archive I/O."""
    manifest, config, _ = frozen_inputs(folder, manifest, config)
    output = Path(config['hydra']['run']['dir'])
    if not output.is_absolute() or output.name != 'output' or '..' in output.parts:
        raise ValueError('Unsupported original output directory')
    original = output.parent
    job_id = config['main']['eds_eval']['job_id']
    # The recorded v1 launcher used the output-folder name; v2 uses run name.
    # Keep both explicit protocols strict rather than accepting arbitrary IDs.
    schema = manifest.get('schema')
    if schema == 'steering_cohort_v1':
        expected_job_id = output.name
    elif schema in ('steering_cohort_v2', 'pi05_vls_cohort_v1'):
        expected_job_id = original.name
    else:
        raise ValueError('Unsupported original cohort schema')
    if job_id != expected_job_id:
        raise ValueError('Original job id/output directory mismatch')
    status = read_json(Path(folder)/'status.json')
    if status.get('run_dir') is not None and status['run_dir'] != str(original):
        raise ValueError('Original status/config run directory mismatch')
    return {'original_run_dir': str(original), 'original_output_dir': str(output), 'job_id': job_id}


def expected_assets(folder, manifest=None, config=None):
    manifest, config, environment = frozen_inputs(folder, manifest, config)
    rel = 'scripts/steering_assets_manifest.json'
    asset_file = Path(folder)/'source'/rel
    if digest(asset_file) != manifest['source_sha256'][rel]:
        raise ValueError('Frozen asset manifest hash mismatch')
    task_hash = read_json(asset_file)['files'][TASK_MAP]
    if isinstance(task_hash, dict): task_hash = task_hash['sha256']
    if manifest.get('schema') == 'pi05_vls_cohort_v1':
        if config['main'].get('episode_rng_fixture_manifest') is not None:
            raise ValueError('PI05 protocol does not restore RDT RNG fixtures')
        return {'task_map': task_hash}, {'task_map': Path(environment['libero']['root'])/TASK_MAP}
    rng_hash = config['main']['episode_rng_fixture_manifest_sha256']
    if environment['rng']['sha256'] != rng_hash:
        raise ValueError('Recorded RNG/config hash mismatch')
    return {'task_map': task_hash, 'rng_manifest': rng_hash}, {
        'task_map': Path(environment['libero']['root'])/TASK_MAP,
        'rng_manifest': Path(config['main']['episode_rng_fixture_manifest'])}


def support_asset(folder, kind, *, archive_support=None, manifest=None, config=None):
    """Prefer an exact verified support bundle; otherwise verify original asset bytes.

    A present-but-invalid bundle is an error, never permission to fall back.
    No arbitrary path map, basename search, current-checkout substitution or gate
    relaxation is accepted. The expected hashes come from frozen run evidence.
    """
    folder = Path(folder).resolve()
    hashes, originals = expected_assets(folder, manifest, config)
    if kind not in SUPPORT_FILES: raise ValueError('Unknown support asset')
    support = Path(archive_support).resolve() if archive_support is not None else folder/'archive-support'
    if archive_support is not None or support.exists():
        receipt = read_json(support/'manifest.json')
        expected = dict(schema='steering_archive_support_v1',
            original_manifest_sha256=digest(folder/'manifest.json'),
            original_config_sha256=digest(folder/'resolved-config.yaml'),
            original_environment_sha256=digest(folder/'environment.json'),
            execution=execution_identity(folder, manifest, config),
            files={SUPPORT_FILES[k]: hashes[k] for k in SUPPORT_FILES})
        if receipt != expected:
            raise ValueError('Archive support binding mismatch')
        for key, name in SUPPORT_FILES.items():
            path = (support/name).resolve()
            if not path.is_relative_to(support.resolve()) or not path.is_file() or digest(path) != hashes[key]:
                raise ValueError('Archive support asset hash/path mismatch: '+key)
        return support/SUPPORT_FILES[kind]
    path = originals[kind]
    if not path.is_absolute() or digest(path) != hashes[kind]:
        raise ValueError('Original support asset hash/path mismatch: '+kind)
    return path


def prepare_support(folder, support_dir, *, task_map=None, rng_manifest=None):
    """Create a new separate sidecar directory after the source run is terminal."""
    folder = Path(folder).resolve(); destination = Path(support_dir).resolve()
    if destination.is_relative_to(folder):
        raise ValueError('Create support outside the preserved source run')
    state = read_json(folder/'status.json').get('state')
    if state not in ('finished', 'exited', 'interrupted', 'launcher_failed', 'preflight_failed'):
        raise ValueError('Do not archive support for a running cohort')
    manifest, config, _ = frozen_inputs(folder)
    hashes, originals = expected_assets(folder, manifest, config)
    sources = {'task_map': Path(task_map) if task_map is not None else originals['task_map'],
               'rng_manifest': Path(rng_manifest) if rng_manifest is not None else originals['rng_manifest']}
    for key, source in sources.items():
        if digest(source) != hashes[key]:
            raise ValueError('Supplied support asset hash mismatch: '+key)
    receipt = dict(schema='steering_archive_support_v1',
        original_manifest_sha256=digest(folder/'manifest.json'),
        original_config_sha256=digest(folder/'resolved-config.yaml'),
        original_environment_sha256=digest(folder/'environment.json'),
        execution=execution_identity(folder, manifest, config),
        files={SUPPORT_FILES[k]: hashes[k] for k in SUPPORT_FILES})
    destination.mkdir(parents=True, exist_ok=False)
    for key, source in sources.items():
        shutil.copyfile(source, destination/SUPPORT_FILES[key])
        if digest(destination/SUPPORT_FILES[key]) != hashes[key]:
            raise ValueError('Support source changed while copying: '+key)
    (destination/'manifest.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    return receipt


def marker_frame(evaluation, episode_index, global_step, marker):
    """Read only the run-relative raw frame; original absolute path is provenance."""
    if any(type(x) is not int or x < 0 for x in (episode_index, global_step)):
        raise ValueError('Invalid raw frame episode/step identity')
    evaluation = Path(evaluation).resolve()
    path = evaluation/'stage_unmarked_frames'/f'episode_{episode_index:03d}'/f'step_{global_step:06d}.png'
    resolved = path.resolve()
    if not resolved.is_relative_to(evaluation) or not resolved.is_file():
        raise ValueError('Raw frame missing or outside archive')
    if digest(resolved) != marker['raw_png_sha256']:
        raise ValueError('Archived raw frame hash mismatch')
    return resolved
