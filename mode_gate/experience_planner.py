"""Bounded evidence exploration by the existing native Codex Planner account task."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .planner_account import CodexPlannerClient
from .experiences import artifact_ref
from .io_utils import sha256_file

ACTION_SCHEMA = {"type": "object", "required": ["action", "arguments"], "additionalProperties": False,
    "properties": {"action": {"enum": ["search", "open_episode", "read_evidence", "annotate", "retrain", "select_remedy", "finish"]},
                   "arguments": {"type": "object"}}}


class ExperiencePlanner:
    def __init__(self, memory, *, client=None):
        self.memory = memory
        self.client = client or CodexPlannerClient()

    def _catalog(self, remedies):
        from .verifier_feedback import publish_verifier_feedback
        feedback = publish_verifier_feedback(self.memory)
        episodes = {}
        for fact in self.memory.experiences.facts.iter_valid():
            episode = episodes.setdefault(fact["episode_id"], {"episode_id": fact["episode_id"], "contexts": []})
            episode.setdefault("event_kinds", [])
            if fact["kind"] not in episode["event_kinds"]:
                episode["event_kinds"].append(fact["kind"])
            if fact["kind"] == "decision_context":
                episode["contexts"].append({"context_id": fact["context_id"],
                    **{k: fact["payload"].get(k) for k in ("task", "policy_id", "route", "remaining_budget")}})
        return {"episodes": list(episodes.values()), "remedies": remedies,
                "verifier_feedback": feedback["observed"],
                "verifier_feedback_unresolved": feedback["unresolved"],
                "training_usage": list(self.memory.experiences.training_usage.iter_valid()),
                "training_requests": list(self.memory.experiences.training_requests.iter_valid()),
                "annotation_heads": list(self.memory.experiences.latest_annotations().values()),
                "decisions": [self._decision_catalog_item(x) for x in self.memory.decisions.iter_valid()]}

    @staticmethod
    def _decision_catalog_item(row):
        item = {k: row.get(k) for k in ("record_id", "context_id", "policy_id", "snapshot_hash", "feature_schema", "provenance")}
        refs = []
        for key in ("round_analysis_path", "multimodal_evidence_path"):
            path = row.get("provenance", {}).get(key)
            if path and Path(path).is_file():
                refs.append(artifact_ref(path, kind="predicted_candidates" if key=="round_analysis_path" else "historical_evidence"))
        item["evidence_refs"] = refs
        item["input_rebuild_required"] = row.get("feature_schema") != "candidate-verifier-input-v3"
        return item

    def run(self, *, purpose, current, remedies=(), max_interactions=64):
        from .campaign import configured_merge_selection
        fixed_merge = configured_merge_selection()
        catalog = self._catalog(list(remedies))
        view = {"current": current, "catalog_counts": {k:len(v) for k,v in catalog.items()}}
        authorized_files = {}
        opened_files = set()
        discovered_remedies = set()
        history = []
        training_request = None

        def expose(value):
            if isinstance(value, dict):
                if value.get("path") and value.get("sha256"):
                    path = Path(value["path"])
                    if path.is_file() and sha256_file(path) == value["sha256"]:
                        authorized_files[str(path.resolve())] = dict(value)
                for item in value.values():
                    expose(item)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    expose(item)
        expose(current)
        for _ in range(max_interactions):
            expose(view)
            images = []
            image_paths = set()
            def attach_images(value):
                if isinstance(value, dict):
                    if value.get("path") and value.get("kind") in {"real_observation", "observed_overlay", "suggested_path_overlay"}:
                        path = Path(value["path"])
                        if (str(path.resolve()) in authorized_files and str(path.resolve()) not in image_paths
                                and path.suffix.lower() in {".png", ".jpg", ".jpeg"}):
                            images.append((path.read_bytes(), "image/png" if path.suffix.lower()==".png" else "image/jpeg"))
                            image_paths.add(str(path.resolve()))
                    for item in value.values():
                        attach_images(item)
                elif isinstance(value, (list, tuple)):
                    for item in value:
                        attach_images(item)
            attach_images(view)
            prompt = (
                "你是现有 LIBERO-PRO 顶层 Planner。负责多模态经验检索、解释/修订标签、选择训练数据和训练时机；"
                "不是运行时二分类 verifier。事实和解释必须分开。提前 EXPANSION 仅说明没有继续尝试，"
                "不能单独证明尝试满 50 次会失败。未来视频/结果可以作为标注证据，但不得修改决策时输入。"
                "verifier_feedback 是对原 head 判断的实测纠错证据：同一 policy 在当时剩余预算对应的实际步数内"
                "原生成功，目标为 RE-STEER；仅实际耗尽全部剩余 RE-STEER chunk 且未成功时，目标才为 EXPANSION。"
                "decision_reward=+1 表示原判断吻合实测结果，-1 表示原判断错误。"
                "它不是负的 loss 权重；采用该证据时使用纠正后的标签和你选择的正有限 weight，和其它标签一起训练。"
                "annotate 另带 feedback_id、decision_reward 并引用该记录的两个原始事实 evidence_refs。"
                "未执行、提前停止、换 policy 后成功或证据不完整不能自动奖惩；未解决记录只供继续审查。"
                "完成首个 rollout 的普通 EXECUTE 续跑不是 RE-STEER 预算消耗，记录会明确区分。"
                "这些反馈无需自动追加 replay，也不能改变唯一的 LIBERO-PRO 成功标准。"
                "不限定数据来源、比例或总量；可以综合实际 retry、示范、历史 replay、扩张前后结果和视频。"
                "训练检查数据必须是独立 episode/decision snapshot，不能与梯度训练或以往训练经历重合。"
                "search 参数 collection=episodes/remedies/annotation_heads/decisions/training_usage/training_requests/"
                "verifier_feedback/verifier_feedback_unresolved, query, offset, limit；"
                "query 可为空以浏览全部，任务文字不同也可能缺失同一能力。open_episode 参数 episode_id, offset, limit。"
                "read_evidence 参数 path；视频可加 frame_indices（自行选择关键帧）。"
                "annotate 参数 record_id, episode_id, label_version=fixed_budget_50-v2, label=RE-STEER/EXPANSION/AMBIGUOUS/CENSORED/null,"
                "reason, evidence_refs（event_id 或 path+sha256+kind）, use_for_training, source, weight, supersedes（上一 annotation_id 或 null）。"
                "retrain 参数 train_annotation_ids, independent_annotation_ids, reason, config（可选训练超参数）。"
                "select_remedy 参数 signature_id, alpha_l_values, reason, evidence_refs，每个 alpha 同时用于语言/视觉/动作三个模块，选出的 delta 将在当前 policy 重建，"
                "通过 raw regression 和 trigger recheck 才能使用；语义相似或历史排名不能作为验证通过。"
                "核对操作相通性、场景/对象关系、失败动作和全部预测候选、视频中 remedy 真正改善之处、当时验证 policy。"
                "没有适合的 remedy 则 finish 并说明需要新 ticket。finish 参数 reason。用中文说明理由。\n"
                + json.dumps({"purpose": purpose, "view": view, "tool_history": history}, ensure_ascii=False)
            )
            if current.get('initialization_only'):
                prompt = (
                    '本次是 verifier 初始化的事后审查：仅使用 current.allowed_task_keys 中的两个任务的数据。'
                    '不要参与在线 steering、选择当前执行候选、判断阶段或改变 guidance 开关。'
                    '只根据已发生的真实结果/视频标注、选训练和独立经历、决定新 head 训练与审查；'
                    '可用这两个任务此前有效的经历，不扩展到第三个任务。初始化完成后由 worker 自动恢复正式完整架构。\n'
                    + prompt)
            if fixed_merge is not None:
                prompt = ('本次实验合并系数由用户固定，不再由 Planner 搜索。'
                    f'语言、视觉、动作均为 {fixed_merge["alpha_values"][0]:g}；'
                    'select_remedy 的 alpha_l_values 只填该单一值；你仍负责 remedy 判断和证据分析。'
                    '不改变 SFT 训练数据混合比例。\n' + prompt)
            response = self.client.request(prompt=prompt, schema=ACTION_SCHEMA, images=images,
                                           purpose="experience_" + purpose)
            output = json.loads(response.text)
            action, args = output["action"], dict(output["arguments"])
            provenance = dict(response.planner_metadata)
            history.append({"action": action, "arguments": args, "planner_provenance": provenance})
            if action == "search":
                collection = str(args.get("collection", "episodes"))
                if collection not in catalog:
                    raise ValueError("unknown experience collection")
                query = str(args.get("query", "")).casefold()
                rows = [x for x in catalog[collection] if query in json.dumps(x, ensure_ascii=False).casefold()]
                offset, limit = max(0,int(args.get("offset",0))), min(50,max(1,int(args.get("limit",10))))
                view = {"total": len(rows), "offset": offset, "rows": rows[offset:offset+limit]}
                if collection == "remedies":
                    discovered_remedies.update(x["signature_id"] for x in view["rows"])
            elif action == "open_episode":
                episode = self.memory.experiences.episode(str(args["episode_id"]))
                offset, limit = max(0,int(args.get("offset",0))), min(200,max(1,int(args.get("limit",50))))
                view = {**episode, "facts": episode["facts"][offset:offset+limit], "total_facts": len(episode["facts"])}
            elif action == "read_evidence":
                path = Path(args["path"]).resolve()
                if str(path) not in authorized_files:
                    raise ValueError("evidence must be discovered in the experience library before opening")
                ref = authorized_files[str(path)]
                if sha256_file(path) != ref["sha256"]:
                    raise ValueError("evidence changed during Planner inspection")
                opened_files.add(str(path))
                if path.suffix == ".json":
                    view = json.loads(path.read_text())
                elif path.suffix == ".npz":
                    with np.load(path, allow_pickle=False) as arrays:
                        view = {"artifact": ref, "arrays": {k: arrays[k].tolist() for k in arrays.files}}
                elif path.suffix == ".mp4":
                    import imageio.v2 as imageio
                    from PIL import Image
                    frames = []
                    with imageio.get_reader(path) as video:
                        for index in args.get("frame_indices", [0]):
                            index = int(index)
                            if index < 0:
                                raise ValueError("video frame index must be nonnegative")
                            image_path = path.with_name(f"{path.stem}_review_{index}.png")
                            Image.fromarray(video.get_data(index)).save(image_path)
                            frames.append(artifact_ref(image_path, kind="real_observation", video=ref, frame_index=index))
                    view = {"selected_video_frames": frames}
                elif path.suffix in {".h5", ".hdf5"}:
                    import h5py
                    from PIL import Image
                    frames = []
                    with h5py.File(path, "r") as demo:
                        view = {"artifact":ref, "native_success":bool(demo.attrs.get("simulator_success", False)),
                                "actions":np.asarray(demo["action"]).tolist(),
                                "observed_positions":np.asarray(demo["ee_position"]).tolist()}
                        for index in args.get("frame_indices", [0]):
                            for name in ("image", "image2"):
                                if name not in demo:
                                    continue
                                output = path.with_name(f"{path.stem}_review_{name}_{int(index)}.png")
                                Image.fromarray(np.asarray(demo[name][int(index)], dtype=np.uint8)).save(output)
                                frames.append(artifact_ref(output, kind="real_observation", demonstration=ref, frame_index=int(index)))
                    view["frames"] = frames
                else:
                    view = {"artifact": ref, "note": "use image evidence or cited structured summaries"}
            elif action == "annotate":
                args["planner_provenance"] = provenance
                view = self.memory.annotate(args)
                catalog["annotation_heads"] = list(self.memory.experiences.latest_annotations().values())
            elif action == "retrain":
                training_request = self.memory.experiences.request_training(**args, planner_provenance=provenance)
                view = {"retrain_request": training_request, "next": "finish to dispatch training"}
            elif action == "select_remedy":
                found = [x for x in remedies if x["signature_id"] == args.get("signature_id")]
                if (len(found) != 1 or args.get("signature_id") not in discovered_remedies
                        or not args.get("reason") or not args.get("evidence_refs")):
                    raise ValueError("remedy choice requires a discovered artifact and cited rationale")
                report_path = str(Path(found[0]["metadata"]["policy_gate_report_path"]).resolve())
                if report_path not in opened_files:
                    raise ValueError("Planner must inspect the remedy's measured historical validation")
                facts = {x["event_id"] for x in self.memory.experiences.facts.iter_valid()}
                for ref in args["evidence_refs"]:
                    if ref.get("event_id") in facts:
                        continue
                    cited = str(Path(ref.get("path", "")).resolve())
                    if cited not in authorized_files or ref.get("sha256") != authorized_files[cited]["sha256"]:
                        raise ValueError("remedy rationale cites undiscovered or changed evidence")
                if fixed_merge is not None:
                    # Preserve the raw Planner response in history, but never
                    # let an unsolicited grid override the user's single alpha.
                    args = {**args, "alpha_l_values": fixed_merge["alpha_values"],
                            "merge_coefficient_selection": fixed_merge}
                values = args.get("alpha_l_values", [])
                if not values or any(not 0 <= float(a) <= 1 for a in values):
                    raise ValueError("Planner must specify feasible merge coefficients")
                return {"remedy": found[0], **args, "planner_provenance": provenance,
                        "training_request": training_request, "history": history}
            elif action == "finish":
                return {"remedy": None, "reason": str(args.get("reason", "")),
                        "training_request": training_request, "planner_provenance": provenance, "history": history}
        raise RuntimeError("Planner evidence exploration exceeded interaction guard; state is saved, no automatic reuse")

    def review_head(self, metrics):
        schema = {"type": "object", "required": ["accept", "reason"], "additionalProperties": False,
                  "properties": {"accept": {"type": "boolean"}, "reason": {"type": "string"}}}
        response = self.client.request(purpose="verifier_independent_review", schema=schema, prompt=(
            "基于独立经历检查新 verifier 是否改善。比较新 head、已有 head（如有）和逐条错误。"
            "没有独立样本不能声称验证可用；不要因仅训练拟合好而同意部署。输出 accept 和中文理由。\n"
            + json.dumps(metrics, ensure_ascii=False)))
        return {**json.loads(response.text), "planner_provenance": dict(response.planner_metadata)}

    def choose_merge_coefficients(self, current):
        from .campaign import configured_merge_selection
        fixed = configured_merge_selection()
        if fixed is not None:
            return fixed
        schema = {'type': 'object', 'required': ['alpha_values', 'reason'], 'additionalProperties': False,
                  'properties': {'alpha_values': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                     'items': {'type': 'number', 'minimum': 0, 'maximum': 1}}, 'reason': {'type': 'string'}}}
        response = self.client.request(purpose='uniform_merge_coefficients', schema=schema,
            prompt='选择待验证的合并系数。每个 alpha 对语言、视觉、动作完全一致：parent + alpha*(SFT-parent)。'
                   '没有固定网格。结合当前任务、训练信息与历史实测证据决定，后续按新任务收益减旧任务遗忘实测选择。'
                   '不能把系数建议当成已验证成功。\n' + json.dumps(current, ensure_ascii=False))
        return {**json.loads(response.text), 'planner_provenance': dict(response.planner_metadata)}

    def select_demonstrations(self, current, candidates):
        images, seen = [], set()
        def attach(value):
            if isinstance(value, dict):
                if value.get('kind') == 'real_observation' and value.get('path') and value.get('sha256'):
                    path=Path(value['path'])
                    if str(path) not in seen and path.suffix.lower() in {'.png','.jpg','.jpeg'}:
                        if sha256_file(path) != value['sha256']:
                            raise ValueError('current demonstration-selection observation changed')
                        images.append((path.read_bytes(),'image/png' if path.suffix.lower()=='.png' else 'image/jpeg'))
                        seen.add(str(path))
                for item in value.values():
                    attach(item)
            elif isinstance(value, (list,tuple)):
                for item in value:
                    attach(item)
        attach(current)
        schema = {'type': 'object', 'required': ['ticket_id', 'reason'], 'additionalProperties': False,
                  'properties': {'ticket_id': {'enum': [x['ticket_id'] for x in candidates]}, 'reason': {'type': 'string'}}}
        response = self.client.request(purpose='precollected_demonstration_selection', schema=schema, images=images,
            prompt='为本次 expansion 选择已采集且原生成功的当前任务示范数据用于 SFT。不要重复采集，'
                   '不要把旧示范 ticket 的 parent 当成当前训练 parent。保留当前 ticket 的图像和失败证据。\n'
                   + json.dumps({'current': current, 'datasets': candidates}, ensure_ascii=False))
        return {**json.loads(response.text), 'planner_provenance': dict(response.planner_metadata)}
