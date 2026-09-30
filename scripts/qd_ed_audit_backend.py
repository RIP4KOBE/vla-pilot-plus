"""Explicit native audit device selection; importing this module never touches CUDA."""
from dataclasses import dataclass, field
import os
import re
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


def canonical_cuda_uuid(value):
    """Strict physical GPU UUID spelling, independent of PyTorch's prefix choice."""
    if not isinstance(value,str) or re.fullmatch(
            r"(?:GPU-)?[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            value,flags=re.IGNORECASE) is None:
        raise ValueError("physical CUDA UUID missing or malformed")
    bare=value[4:] if value[:4].lower()=="gpu-" else value
    return "GPU-"+bare.lower()


def serialize_cuda_uuid(value):
    """Serialize only str or the installed native CUuuid, never arbitrary objects."""
    native_type=getattr(torch._C,"_CUuuid",None)
    if isinstance(value,str):
        return {"actual_uuid":value,"actual_uuid_type":"builtins.str","actual_uuid_bytes_hex":None,
            "physical_uuid":canonical_cuda_uuid(value)}
    if native_type is None or type(value) is not native_type:
        raise ValueError("unsupported public CUDA UUID type")
    raw=str(value)
    physical=canonical_cuda_uuid(raw)
    data=value.bytes
    if type(data) not in (list,tuple,bytes) or len(data)!=16 or any(type(v) is not int or not 0<=v<=255 for v in data):
        raise ValueError("native CUDA UUID bytes malformed")
    native_hex=bytes(data).hex()
    expected=physical[4:].replace("-","")
    if native_hex!=expected:
        raise ValueError("native CUDA UUID string and bytes differ")
    return {"actual_uuid":raw,"actual_uuid_type":"torch._C._CUuuid","actual_uuid_bytes_hex":native_hex,
        "physical_uuid":physical}


def assigned_cuda_identity(binding):
    """Only called inside an explicitly released, metered worker; never guesses."""
    diagnostic={"schema":"n23-public-cuda-identity-diagnostic-v1","expected_physical_gpu":7,
        "expected_uuid":None,"cuda_visible_devices":None,"visible_device_count":None,"current_device":None,
        "uuid_public_type":None,"serialized_raw_uuid":None,"canonical_uuid":None,"status":"not_observed"}
    def fail(message,status,kind=RuntimeError):
        diagnostic["status"]=status
        error=kind(message);error.identity_diagnostic=dict(diagnostic)
        raise error
    try:
        if (not isinstance(binding, dict) or set(binding) != {"physical_gpu", "uuid", "logical_device"}
                or type(binding["physical_gpu"]) is not int or binding["physical_gpu"] != 7
                or binding["logical_device"] != "cuda:0" or not isinstance(binding["uuid"], str)):
            fail("audit assigned CUDA binding invalid","invalid_binding",ValueError)
        expected_uuid=canonical_cuda_uuid(binding["uuid"]);diagnostic["expected_uuid"]=expected_uuid
        visible=os.environ.get("CUDA_VISIBLE_DEVICES")
        # Retain only a public numeric mask/UUID; arbitrary environment text is not diagnostic output.
        if visible is None:public_visible=None
        elif re.fullmatch(r"[0-9]+(?:,[0-9]+)*",visible):public_visible=visible
        else:
            try:canonical_cuda_uuid(visible);public_visible=visible
            except ValueError:public_visible="<malformed CUDA mask>"
        diagnostic["cuda_visible_devices"]=public_visible
        visible_matches=visible==str(binding["physical_gpu"])
        if not visible_matches:
            try:visible_matches=canonical_cuda_uuid(visible)==expected_uuid
            except ValueError:pass
        if not visible_matches:fail("audit CUDA_VISIBLE_DEVICES differs from frozen binding","mask_mismatch")
        if not torch.cuda.is_available():fail("audit requires exactly one assigned CUDA device","cuda_unavailable")
        count=torch.cuda.device_count();diagnostic["visible_device_count"]=count
        if count!=1:fail("audit requires exactly one assigned CUDA device","count_mismatch")
        current=torch.cuda.current_device();diagnostic["current_device"]=current
        if current!=0:fail("audit current logical CUDA device differs","logical_device_mismatch")
        props=torch.cuda.get_device_properties(0);observed=getattr(props,"uuid",None)
        diagnostic["uuid_public_type"]=type(observed).__module__+"."+type(observed).__name__
        native_type=getattr(torch._C,"_CUuuid",None)
        if native_type is not None and type(observed) is native_type:diagnostic["uuid_public_type"]="torch._C._CUuuid"
        try:
            serialized=serialize_cuda_uuid(observed)
        except (ValueError,TypeError,AttributeError,RuntimeError):
            diagnostic["serialized_raw_uuid"]="<malformed or unsupported UUID>"
            fail("audit physical CUDA UUID differs or unavailable","uuid_serialization_rejected")
        diagnostic.update(serialized_raw_uuid=serialized["actual_uuid"],canonical_uuid=serialized["physical_uuid"])
        if serialized["physical_uuid"]!=expected_uuid:
            fail("audit physical CUDA UUID differs or unavailable","physical_uuid_mismatch")
        diagnostic["status"]="matched"
        return {**binding,**serialized,"device_name":props.name,"cuda_visible_devices":visible,
            "torch_version":str(torch.__version__),"cuda_version":torch.version.cuda,
            "identity_diagnostic":diagnostic}
    except Exception as error:
        if not hasattr(error,"identity_diagnostic"):
            diagnostic["status"]="identity_observation_error";error.identity_diagnostic=dict(diagnostic)
        raise


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
        **actual})
