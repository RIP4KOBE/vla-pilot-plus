"""N2's bounded semantic recognizer and pure native-arithmetic quality.

No provider execution, projection, observation access, or persistent cache.
The recognizer deliberately accepts only the preregistered expression template.
"""
from __future__ import annotations

import ast
import builtins
import copy
import hashlib
import types
from dataclasses import dataclass, field

import torch
from torch import Tensor


TEMPLATE = '''def approach(keypoints, action_sequence):
    T = action_sequence.shape[1]
    timesteps = torch.arange(T, device=action_sequence.device)
    final_start = int(0.7 * T)
    weights = torch.where(timesteps >= final_start,
        torch.tensor(3.0, device=action_sequence.device),
        torch.tensor(1.0, device=action_sequence.device))
    weights = weights / weights.sum()
    target_idx = torch.tensor([0], dtype=torch.long, device=keypoints.device)
    target_pos = keypoints[target_idx][0]
    all_dists = torch.norm(action_sequence - target_pos, dim=-1)
    reward = -(all_dists ** 2 * weights).sum(dim=1)
    return reward.mean()
'''


def _code_signature(code):
    """Compare executable structure without marshal's string-interning markers."""
    if isinstance(code, types.CodeType):
        names = ("co_argcount", "co_posonlyargcount", "co_kwonlyargcount",
                 "co_nlocals", "co_stacksize", "co_flags", "co_code", "co_names",
                 "co_varnames", "co_filename", "co_name", "co_qualname",
                 "co_firstlineno", "co_linetable", "co_exceptiontable",
                 "co_freevars", "co_cellvars")
        return tuple((n, getattr(code, n, None)) for n in names) + (
            ("co_consts", tuple(_code_signature(c) for c in code.co_consts)),)
    return (type(code).__name__, code)


def _canonical_function(node):
    node = copy.deepcopy(node)
    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
        node.body.pop(0)
    local_names = [arg.arg for arg in node.args.args]
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id not in local_names:
                    local_names.append(target.id)
    if {"torch", "int"}.intersection(local_names):
        raise ValueError("reserved_name_shadowed")
    mapping = {name: f"local_{i}" for i, name in enumerate(local_names)}
    class Rename(ast.NodeTransformer):
        def visit_Name(self, item):
            item.id = mapping.get(item.id, item.id)
            return item
        def visit_arg(self, item):
            item.arg = mapping.get(item.arg, item.arg)
            return item
    node = Rename().visit(node)
    node.name = "recognized_approach"
    return node


def _template_index(source):
    tree = ast.parse(source)
    body = list(tree.body)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
        body.pop(0)
    if len(body) != 1 or not isinstance(body[0], ast.FunctionDef):
        raise ValueError("not_single_function_template")
    fn = _canonical_function(body[0])
    expected = _canonical_function(ast.parse(TEMPLATE).body[0])
    # Match the complete AST, with exactly one free integer at the target index.
    try:
        literal = fn.body[5].value.args[0].elts[0]
        index = literal.value
        if not isinstance(literal, ast.Constant) or type(index) is not int or index < 0:
            raise ValueError("target_index_not_nonnegative_integer")
        literal.value = 0
    except (AttributeError, IndexError):
        raise ValueError("not_weighted_distance_template") from None
    if ast.dump(fn, include_attributes=False) != ast.dump(expected, include_attributes=False):
        raise ValueError("not_weighted_distance_template")
    return tree, body[0].name, index


def _bound_identity(fn):
    # Importing this existing module neither loads a provider nor runs validation.
    from utils.guidance_utils import wrap_guidance_function_with_device_fix
    source = getattr(fn, "_guidance_source_text", None)
    original = getattr(fn, "_guidance_original_func", None)
    if not isinstance(source, str) or not isinstance(original, types.FunctionType):
        raise ValueError("missing_loader_source_or_original")
    if not isinstance(fn, types.FunctionType):
        raise ValueError("not_loader_function")
    wrapper_code = next(c for c in wrap_guidance_function_with_device_fix.__code__.co_consts
                        if isinstance(c, types.CodeType) and c.co_name == "wrapped")
    if _code_signature(fn.__code__) != _code_signature(wrapper_code):
        raise ValueError("unrecognized_wrapper")
    closure = dict(zip(fn.__code__.co_freevars, fn.__closure__ or ()))
    if set(closure) != {"func"} or closure["func"].cell_contents is not original:
        raise ValueError("wrapper_original_mismatch")
    if fn.__globals__ is not wrap_guidance_function_with_device_fix.__globals__:
        raise ValueError("wrapper_globals_mismatch")
    if original.__closure__ or original.__defaults__ or original.__kwdefaults__:
        raise ValueError("unsupported_original_bindings")
    tree, name, index = _template_index(source)
    compiled = compile(tree, original.__code__.co_filename, "exec", dont_inherit=True)
    definitions = [c for c in compiled.co_consts if isinstance(c, types.CodeType) and c.co_name == name]
    if len(definitions) != 1 or _code_signature(definitions[0]) != _code_signature(original.__code__):
        raise ValueError("source_original_code_mismatch")
    if original.__globals__.get("torch") is not torch:
        raise ValueError("original_torch_binding_mismatch")
    bindings = original.__globals__
    default_builtins = bindings.get("__builtins__", builtins)
    int_binding = bindings.get("int", default_builtins.get("int") if isinstance(default_builtins, dict) else getattr(default_builtins, "int", None))
    if int_binding is not int:
        raise ValueError("original_int_binding_mismatch")
    return index, {
        "source_text_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "code_structure_sha256": hashlib.sha256(repr(_code_signature(original.__code__)).encode("utf-8")).hexdigest(),
        "binding": "loader_wrapper_original_and_complete_template_ast",
    }


@dataclass(frozen=True)
class ExecutedPrefixContract:
    target_index: int
    identity: dict
    provider: object = field(repr=False, compare=False)

    def validate(self, providers):
        if not providers or len(providers) != 1 or providers[0] is not self.provider:
            raise RuntimeError("N2 provider occurrence changed after recognition")
        try:
            index, identity = _bound_identity(self.provider)
        except (ValueError, SyntaxError, TypeError) as exc:
            raise RuntimeError(f"N2 provider identity changed: {exc}") from exc
        if index != self.target_index or identity != self.identity:
            raise RuntimeError("N2 provider identity changed after recognition")


def recognize_executed_prefix_provider(providers, keypoints):
    """Return (contract, reason); unsupported semantics fall back before search."""
    if not providers or len(providers) != 1:
        return None, "requires_single_provider"
    try:
        index, identity = _bound_identity(providers[0])
    except (ValueError, SyntaxError, TypeError) as exc:
        return None, str(exc)
    _validate_keypoints(keypoints, index)
    return ExecutedPrefixContract(index, identity, providers[0]), "recognized_weighted_distance_template"


def _validate_keypoints(keypoints, index):
    if not isinstance(keypoints, Tensor) or keypoints.ndim != 2 or keypoints.shape[1] != 3:
        raise ValueError("N2 keypoints must have shape (K,3)")
    if type(index) is not int or not 0 <= index < keypoints.shape[0]:
        raise ValueError("N2 target index is outside current keypoints")
    if not keypoints.is_floating_point() or not bool(torch.isfinite(keypoints).all()):
        raise FloatingPointError("N2 keypoints must be finite floating point values")


def executed_prefix_quality(projected_xyz: Tensor, keypoints: Tensor, *, target_index: int) -> Tensor:
    """Q8 from native (B,9,3) projection; native stored dtype, no selection.

    Norm and square retain input dtype. Scalar float weights use the provider's
    FP32 default arithmetic; each candidate is evaluated with B=1 then cast to
    the native quality storage dtype. Exact output equality defines ties.
    """
    _validate_keypoints(keypoints, target_index)
    if not isinstance(projected_xyz, Tensor) or projected_xyz.ndim != 3 or tuple(projected_xyz.shape[1:]) != (9, 3) or projected_xyz.shape[0] == 0:
        raise ValueError("N2 projection must have shape (B,9,3), B > 0")
    if projected_xyz.dtype != keypoints.dtype or projected_xyz.device != keypoints.device:
        raise ValueError("N2 projection/keypoints must preserve matching native dtype/device")
    if not projected_xyz.is_floating_point() or not bool(torch.isfinite(projected_xyz).all()):
        raise FloatingPointError("N2 projection must be finite floating point values")
    if torch.get_default_dtype() != torch.float32:
        raise RuntimeError("N2 requires the frozen provider FP32 scalar default")
    points = projected_xyz[:, 1:9]
    timesteps = torch.arange(8, device=points.device)
    weights = torch.where(timesteps >= int(0.7 * 8),
                          torch.tensor(3.0, device=points.device),
                          torch.tensor(1.0, device=points.device))
    weights = weights / weights.sum()
    target_idx = torch.tensor([target_index], dtype=torch.long, device=keypoints.device)
    target = keypoints[target_idx][0]
    rewards = []
    for candidate in points:
        distances = torch.norm(candidate.unsqueeze(0) - target, dim=-1)
        reward = -(distances ** 2 * weights).sum(dim=1)
        rewards.append(reward.mean().detach().to(dtype=projected_xyz.dtype).reshape(()))
    result = torch.stack(rewards)
    if not bool(torch.isfinite(result).all()):
        raise FloatingPointError("N2 quality is nonfinite")
    return result
