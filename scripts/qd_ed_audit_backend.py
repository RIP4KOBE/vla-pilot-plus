"""Explicit native audit device selection; importing this module never touches CUDA."""
from dataclasses import dataclass, field
import os
import torch


@dataclass
class AuditBackend:
    device: torch.device
    metadata: dict
    dtypes: set = field(default_factory=set)

    def native(self, value):
        if not torch.is_tensor(value):
            raise TypeError("audit native transfer requires tensor")
        self.dtypes.add(str(value.dtype))
        return value.to(device=self.device)  # dtype and values stay unchanged

    def synchronize(self):
        if self.device.type == "cuda":
            torch.cuda.synchronize(self.device)

    def report(self):
        return {**self.metadata, "dtype_coverage": sorted(self.dtypes)}


def assigned_cuda_identity(binding):
    """Only called inside an explicitly released, metered worker; never guesses."""
    if (not isinstance(binding, dict) or set(binding) != {"physical_gpu", "uuid", "logical_device"}
            or type(binding["physical_gpu"]) is not int or binding["physical_gpu"] != 7
            or binding["logical_device"] != "cuda:0"
            or not isinstance(binding["uuid"], str) or not binding["uuid"].startswith("GPU-")):
        raise ValueError("audit assigned CUDA binding invalid")
    visible = os.environ.get("CUDA_VISIBLE_DEVICES")
    if visible not in {str(binding["physical_gpu"]), binding["uuid"]}:
        raise RuntimeError("audit CUDA_VISIBLE_DEVICES differs from frozen binding")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("audit requires exactly one assigned CUDA device")
    if torch.cuda.current_device() != 0:
        raise RuntimeError("audit current logical CUDA device differs")
    props = torch.cuda.get_device_properties(0)
    actual_uuid = str(getattr(props, "uuid", ""))
    if actual_uuid != binding["uuid"]:
        raise RuntimeError("audit physical CUDA UUID differs or unavailable")
    return {**binding, "actual_uuid": actual_uuid, "device_name": props.name,
            "cuda_visible_devices": visible, "torch_version": str(torch.__version__),
            "cuda_version": torch.version.cuda}


def create_backend(kind, *, binding=None):
    if kind == "cpu":
        if binding is not None:
            raise ValueError("CPU audit must not request a CUDA binding")
        return AuditBackend(torch.device("cpu"), {"kind": "cpu", "logical_device": "cpu",
            "physical_uuid": None, "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda})
    if kind != "cuda":
        raise ValueError("audit backend must be explicitly cpu or cuda")
    actual = assigned_cuda_identity(binding)
    return AuditBackend(torch.device("cuda:0"), {"kind": "cuda", "logical_device": "cuda:0",
        "physical_uuid": actual["actual_uuid"], **actual})
