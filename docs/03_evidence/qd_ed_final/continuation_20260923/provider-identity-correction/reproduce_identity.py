#!/usr/bin/env python3
"""CPU provenance experiment; define providers via frozen loader, never call them.

Writes a new supplement, never edits the frozen map or any episode. The map's
original-code identities are derived exclusively from source + actual loader.
Completed-episode identity comparison is appended only after deriving the map.
"""
import argparse
import ast
import builtins
import copy
import hashlib
import json
import marshal
from pathlib import Path
import sys
import types
import warnings
import __future__


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    if isinstance(value, types.CodeType):
        return {"type": "code", "fields": field_values(value)}
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [canonical(item) for item in value]}
    if isinstance(value, bytes):
        return {"type": "bytes", "hex": value.hex()}
    if isinstance(value, float):
        return {"type": "float", "hex": value.hex()}
    if value is None or type(value) in (str, int, bool):
        return {"type": type(value).__name__, "value": value}
    raise TypeError(type(value).__name__)


def field_values(code):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return {name: canonical(getattr(code, name)) for name in dir(code)
                if name.startswith("co_") and not callable(getattr(code, name))}


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def describe(code, raw):
    values = field_values(code)
    return {"marshal_sha256": sha(raw), "marshal_length": len(raw),
            "value_structure_sha256": sha(encoded(values)),
            "fields": {name: {"value": value, "value_sha256": sha(encoded(value))}
                       for name, value in values.items()}}


class ForbiddenModule(types.ModuleType):
    def __getattr__(self, name):
        raise RuntimeError(f"forbidden native/tensor API: {self.__name__}.{name}")


def definition_only_source(text):
    tree = ast.parse(text)
    assert len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef)
    node = tree.body[0]
    assert not node.decorator_list and node.returns is None
    assert not node.args.defaults and not node.args.kw_defaults
    assert all(arg.annotation is None for arg in node.args.args)
    return node.name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-worktree", required=True, type=Path)
    parser.add_argument("--old-map", required=True, type=Path)
    parser.add_argument("--old-review", required=True, type=Path)
    parser.add_argument("--completed-identity-summary", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    assert sys.version_info[:2] == (3, 12) and sys.flags.optimize == 0
    assert "torch" not in sys.modules and "numpy" not in sys.modules
    old_map_raw, old_review_raw = args.old_map.read_bytes(), args.old_review.read_bytes()
    old_map, old_review = json.loads(old_map_raw), json.loads(old_review_raw)
    assert old_map["schema"] == "qd-ed-provider-target-map-v2"
    assert len(old_review["reviews"]) == 4
    loader_path = args.production_worktree.resolve() / "utils/guidance_utils.py"
    collector_path = args.production_worktree.resolve() / "core/decision_evidence.py"
    loader_raw, collector_raw = loader_path.read_bytes(), collector_path.read_bytes()
    assert sha(loader_raw) == old_review["reviewed_file_sha256"][str(loader_path)]
    for entry in old_map["entries"]:
        assert entry["loader_source_sha256"] == sha(loader_raw)

    # These stubs forbid all tensor/GPU APIs. Full original module definitions run,
    # including its exec_safe/string transformations/wrapper attachment unchanged.
    torch_stub, numpy_stub = ForbiddenModule("torch"), ForbiddenModule("numpy")
    sys.modules["torch"], sys.modules["numpy"] = torch_stub, numpy_stub
    loader_ns, collector_ns = {}, {}
    counters = {"provider_function_calls": 0, "validation_calls": 0}

    def profile(frame, event, arg):
        if event == "call":
            if frame.f_code.co_filename == "<string>" and frame.f_code.co_name.startswith("stage"):
                counters["provider_function_calls"] += 1
                raise RuntimeError("provider call prohibited")
            if frame.f_code.co_name == "_validate_guidance_functions":
                counters["validation_calls"] += 1
                raise RuntimeError("provider validation prohibited")

    sys.setprofile(profile)
    try:
        exec(compile(loader_raw, str(loader_path), "exec", flags=0, dont_inherit=True, optimize=0), loader_ns)
        exec(compile(collector_raw, str(collector_path), "exec", flags=0, dont_inherit=True, optimize=0), collector_ns)
        future_mask = 0
        for name in __future__.all_feature_names:
            future_mask |= getattr(__future__, name).compiler_flag
        loader_future = loader_ns["exec_safe"].__code__.co_flags & future_mask
        assert loader_future == 0
        cases, replacements = [], {}
        for reviewed in old_review["reviews"]:
            path = Path(reviewed["source_path"])
            raw, text = path.read_bytes(), path.read_text(encoding="utf-8")
            assert sha(raw) == reviewed["source_sha256"]
            function_name = definition_only_source(text)
            assert function_name == reviewed["original_function_name"]
            compiled = compile(text, "<string>", "exec", flags=0, dont_inherit=True, optimize=0)
            static = next(c for c in compiled.co_consts if isinstance(c, types.CodeType))
            static_raw = marshal.dumps(static)
            assert sha(static_raw) == reviewed["original_code_sha256"]
            functions = loader_ns["load_functions_from_txt"](str(path), validate=False)
            assert len(functions) == 1
            identity = collector_ns["_provider_identity"](functions[0], 0)
            actual = functions[0]._guidance_original_func.__code__
            actual_raw = marshal.dumps(actual)
            assert sha(actual_raw) == identity["original_code_sha256"]
            assert identity["source_text_sha256"] == sha(text.encode("utf-8")) == reviewed["source_text_sha256"]
            assert functions[0]._guidance_source_text == text
            assert identity["source_path"] == str(path)
            assert len(static_raw) == len(actual_raw)
            changes = [{"offset": i, "static_byte": a, "loader_byte": b,
                        "static_context_hex": static_raw[max(0, i-8):i+20].hex(),
                        "loader_context_hex": actual_raw[max(0, i-8):i+20].hex()}
                       for i, (a, b) in enumerate(zip(static_raw, actual_raw)) if a != b]
            assert len(changes) == 1
            assert (changes[0]["static_byte"], changes[0]["loader_byte"]) == (0xFA, 0xDA)
            assert static_raw[changes[0]["offset"]+1:changes[0]["offset"]+10] == b"\x08<string>"
            assert field_values(static) == field_values(actual)
            # Isolate string-interning without exec/provider call. This creates a
            # different filename object from the static literal, preserving its state.
            interned_filename = sys.intern("".join(("<", "string>")))
            interned_module = compile(text, interned_filename, "exec", flags=0, dont_inherit=True, optimize=0)
            interned = next(c for c in interned_module.co_consts if isinstance(c, types.CodeType))
            interned_raw = marshal.dumps(interned)
            assert interned_raw == actual_raw
            future_module = compile(text, "<string>", "exec", flags=__future__.annotations.compiler_flag,
                                    dont_inherit=True, optimize=0)
            future = next(c for c in future_module.co_consts if isinstance(c, types.CodeType))
            future_raw = marshal.dumps(future)
            assert future.co_flags != actual.co_flags
            case = {"task_id_for_review_only": reviewed["task_id"], "stage_for_review_only": reviewed["stage"],
                    "source_path": str(path), "source_sha256": sha(raw),
                    "source_text_sha256": identity["source_text_sha256"], "source_text_transform": "identity",
                    "loader_identity": identity, "static": describe(static, static_raw),
                    "actual_loader_definition": describe(actual, actual_raw),
                    "interned_filename_compile": describe(interned, interned_raw),
                    "future_annotations_control": describe(future, future_raw),
                    "all_public_code_field_values_equal": True, "marshal_byte_differences": changes,
                    "same_filename_value": static.co_filename == actual.co_filename,
                    "same_filename_object": static.co_filename is actual.co_filename,
                    "target_kind": reviewed["target_kind"]}
            cases.append(case)
            replacements[(reviewed["original_code_sha256"], reviewed["source_text_sha256"], str(path))] = identity["original_code_sha256"]
        assert counters == {"provider_function_calls": 0, "validation_calls": 0}
    finally:
        sys.setprofile(None)
        del sys.modules["torch"], sys.modules["numpy"]

    supplement = copy.deepcopy(old_map)
    supplement.update({"supplement_version": 3, "role": "post_data_identity_correction",
                       "schema_note": "v2 payload schema preserved for the unchanged frozen analyzer; supplement artifact version is 3",
                       "old_map_path": str(args.old_map.resolve()), "old_map_sha256": sha(old_map_raw),
                       "old_review_path": str(args.old_review.resolve()), "old_review_sha256": sha(old_review_raw),
                       "identity_derivation": "frozen actual load_functions_from_txt(validate=False) + original collector _provider_identity; tensor/GPU APIs forbidden",
                       "changed_entry_fields": ["original_code_sha256"],
                       "hypothesis_formula_threshold_or_promotion_changes": False,
                       "frozen_analysis_replaced": False, "requires_root_review_before_supplemental_analysis": True,
                       "provider_calls": 0, "native_gpu_initialization": False,
                       "constant_reward_provider_policy": "stage2 verified, no target mapping added"})
    for entry in supplement["entries"]:
        key = (entry["original_code_sha256"], entry["source_text_sha256"], entry["source_path"])
        entry["original_code_sha256"] = replacements[key]
    for before, after in zip(old_map["entries"], supplement["entries"]):
        assert {k: v for k, v in before.items() if k != "original_code_sha256"} == {
            k: v for k, v in after.items() if k != "original_code_sha256"}

    # Post-derivation comparison, never an input to replacements or the new map.
    completed_raw = args.completed_identity_summary.read_bytes()
    completed = json.loads(completed_raw)["target_identity"]
    observed_comparisons = []
    for observed in completed["unique_original_source_path_tuples"]:
        corresponding = [case for case in cases if case["source_path"] == observed["source_path"]
                         and case["source_text_sha256"] == observed["source_text_sha256"]]
        assert len(corresponding) == 1
        derived = corresponding[0]["loader_identity"]["original_code_sha256"]
        observed_comparisons.append({"source_path": observed["source_path"],
                                     "observed_original_code_sha256": observed["original_code_sha256"],
                                     "derived_original_code_sha256": derived,
                                     "exact_match": observed["original_code_sha256"] == derived,
                                     "observed_count": observed["count"]})
    report = {"schema": "qd-ed-provider-identity-correction-reproduction-v1", "python": sys.version,
              "marshal_version": marshal.version, "optimize": sys.flags.optimize,
              "loader_future_flags": loader_future, "compile": {"flags": 0, "dont_inherit": True, "optimize": 0},
              "loader_path": str(loader_path), "loader_sha256": sha(loader_raw),
              "collector_path": str(collector_path), "collector_sha256": sha(collector_raw),
              "old_map_sha256": sha(old_map_raw), "old_review_sha256": sha(old_review_raw),
              "generator_sha256": sha(Path(__file__).read_bytes()), "cases": cases,
              "counts": {**counters, "reviewed_provider_definitions": len(cases), "target_entries": len(supplement["entries"])},
              "real_torch_or_numpy_imported": False, "cuda_initialized": False,
              "completed_summary_path": str(args.completed_identity_summary.resolve()),
              "completed_summary_sha256": sha(completed_raw), "completed_identity_comparisons": observed_comparisons,
              "frozen_exact_target_matches_preserved": completed["exact_map_matches"],
              "wrapper_variation_cause": "Unknown; not used for supplemental target identity",
              "runtime_code_fields_available": False,
              "limitation": "code-field equivalence is CPU reconstruction; runtime recorded only raw code/source/path identities"}
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name, value in (("reproduction.json", report), ("supplemental-map-v3.json", supplement)):
        with (args.output_dir / name).open("x") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print(json.dumps({"output": str(args.output_dir), "cases": len(cases),
                      "provider_calls": 0, "target_entries": len(supplement["entries"]),
                      "completed_identity_matches": all(x["exact_match"] for x in observed_comparisons),
                      "old_map_unchanged": sha(args.old_map.read_bytes()) == sha(old_map_raw)}))


if __name__ == "__main__":
    main()
