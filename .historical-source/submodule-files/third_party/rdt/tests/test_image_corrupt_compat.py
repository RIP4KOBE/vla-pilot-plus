import importlib
import sys
from pathlib import Path


RDT_ROOT = Path(__file__).resolve().parents[1]
if str(RDT_ROOT) not in sys.path:
    sys.path.insert(0, str(RDT_ROOT))


def test_image_corrupt_imports_with_numpy_2():
    import numpy as np

    original_sctypes = getattr(np, "sctypes", None)
    if hasattr(np, "sctypes"):
        delattr(np, "sctypes")
    sys.modules.pop("train.image_corrupt", None)
    sys.modules.pop("imgaug", None)
    sys.modules.pop("imgaug.imgaug", None)
    sys.modules.pop("imgaug.augmenters", None)

    try:
        module = importlib.import_module("train.image_corrupt")
        assert callable(module.image_corrupt)
    finally:
        if original_sctypes is not None:
            np.sctypes = original_sctypes
