Environment and asset preparation (2026-10-13)

The current working interpreter is /home/hynx/miniconda3/envs/vla-pilot/bin/python,
Python 3.12.12, Torch runtime 2.7.1+cu126. requirements-steering.txt captures 53
observed core packages; environment-steering.yml is a proposed fresh-environment
recipe, not a clean-install success report or a complete transitive lock.
The shared environment was not changed. See pip-check.json for existing missing
robomimic extras/etils and the pyrender/PyOpenGL version conflict.

For a fresh environment, from the repository root:
  conda env create -f environment-steering.yml
  conda activate vla-steering
  git submodule update --init third_party/rdt third_party/lerobot
  python scripts/prepare_steering_assets.py install-libero
  python -m pip install --no-deps -e third_party/libero_pro -e third_party/lerobot
  python -m pip check
  python scripts/prepare_steering_assets.py verify-rng
  python scripts/prepare_steering_assets.py configure --help
Do not blindly run submodule update for the stale LIBERO entry in .gitmodules.
LIBERO is retrieved over public HTTPS at eafdb809426b13153aa1e4c42d6601844217dfec,
whose public HEAD was verified. The preparer normalizes eight CRLF source files,
repairs the malformed empty key in libero_ood/ood_object.yaml to wooden_cabinet,
and installs the frozen ten-task BDDL/init overlay. It verifies all 2308 files.
The production normalization/patch/overlay path is checked on a tree extracted
from the exact upstream Git commit; this is not a fresh network installation.
An initial partial-clone diagnostic was interrupted after checkout stalled; the
installer now fetches the exact commit with full blobs to avoid lazy fetches. assets/ contains large upstream mesh
and texture files and is intentionally not added to the parent Git repository.

The new machine file is .worktrees/exp/steering-integration/local.yaml and uses
explicit encoder snapshot paths. Its LIBERO_CONFIG_PATH is the root .libero_config
whose paths reference the new independent third_party/libero_pro tree. The old
P2 paths and donor Python packages are not required at runtime. Environment
metadata still records legacy editable installs; the worker must prefer target
checkout package paths (or use the clean environment with the editable commands
above). The demonstration datasets directory is not required for online eval.

GPU2/EGL1 is copied from the accepted worker environment, not inferred from CUDA
numbering. The preparer is CPU-only and cannot validate current GPU/EGL mapping.
All 20 RNG files and original audit are byte-identical, with relative manifest
paths; fixture identity/hash validation passes without Torch. No RNG restoration
or simulator execution was performed by this asset preparation task.

model-assets.json records the read-only hashes of the external weights/configs,
all encoder snapshot files, DINO code/weights and embedded normalization source.
No model weights were downloaded or rewritten. The model loader uses 5 denoising
steps from the checkpoint config when num_inference_steps is null.
