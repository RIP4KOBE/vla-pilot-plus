# N23 UUID repair failed before arithmetic

The second backend attempt rdt-qd-ed-final-20260921T093925Z__n23_backend_uuid_repair__41eab61a8079 aborted before arithmetic, costing 6.601666689035483 GPU-process seconds. Both backend failures remain charged. No N23 Dev cell ran; no task or arithmetic result exists. The first engineering exception is exhausted and does not authorize another attempt.

The first fix incorrectly required the observed property to be a Python string. Installed torch exposes a non-string torch._C._CUuuid class. The [PyTorch2.7.1 binding source](https://raw.githubusercontent.com/pytorch/pytorch/v2.7.1/torch/csrc/cuda/Module.cpp) binds device.uuid to this native type and provides __str__. The earlier probe serialized it with str; string-only CPU fixtures omitted that conversion boundary. This identifies a real implementation defect, while neither failed worker retained its actual UUID value. There is no hardware-fault evidence.

The isolated executor will implement native-type conversion and faithful CPU tests, preserve failure diagnostics, and leave admission closed. Original sources/proofs/protocols remain immutable. No protected outcome access, provider switch or scientific change is authorized by this diagnosis.
