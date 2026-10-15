#!/usr/bin/env python3
"""Build a local video index from existing fresh C0 evidence; never edit videos."""
import html
import json
import os

from c0_poe_fresh_retest import STUDY, ROOT, OUTPUT

if (ROOT / "active-cohort.json").exists():
    selection = json.loads((ROOT / "active-cohort.json").read_text())
    OUTPUT = ROOT / selection["relative_output"]

NAMES = ["alphabet soup", "cream cheese", "salad dressing", "bbq sauce", "ketchup", "tomato sauce", "butter", "milk", "chocolate pudding", "orange juice"]
DEST = STUDY / "docs/03_evidence/c0_poe_fresh/videos.html"
CACHED = STUDY / "artifacts/c0_poe_online_20260929/outputs/c0_poe_gemini3_flash_attempt1"
REPLAY = STUDY / "artifacts/c0_trace_replay_20260925/outputs/current"


def player(path, label):
    url = html.escape(os.path.relpath(path, DEST.parent), quote=True)
    return f'<figure><figcaption>{label}</figcaption><video controls preload="none" playsinline src="{url}"></video><a href="{url}">打开原始 MP4</a></figure>'


def build():
    status = json.loads((OUTPUT / "status.json").read_text())
    cards = []
    for task, name in enumerate(NAMES):
        episode = task + 1
        found = list((OUTPUT / f"episode_{episode}").glob("*agentview.mp4"))
        if found:
            outcome = "成功" if "success" in found[0].name else "失败"
            fresh = player(found[0], "本轮：每任务新生成 reward + 在线 Stage · " + outcome)
        else:
            fresh = "<p>本轮尚无完整视频，任务运行中或待执行。</p>"
        cached = list((CACHED / f"episode_{episode}").glob("*agentview.mp4"))
        other = player(cached[0], "上一轮：历史 reward 缓存 + 在线 Stage · 失败") if cached else ""
        replay = list((REPLAY / f"episode_{episode}").glob("*success*agentview.mp4"))
        comparison = '<details><summary>查看历史 Stage 回放成功对照</summary>' + player(replay[0], "历史回复回放成功；不是新的在线结果") + '</details>' if replay else ""
        cards.append(f'<article id="task-{task}"><h2>Task {task} · {name}</h2><div class="grid">{fresh}{other}</div>{comparison}</article>')
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新生成 C0 十任务视频</title>
<style>body{font:16px/1.65 system-ui,sans-serif;background:#f4f6fa;color:#192334;margin:0}main{max-width:1200px;margin:auto;padding:24px}article{padding:20px;margin:24px 0;background:white;border:1px solid #dde3ec;border-radius:10px}a{color:#135baa}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:20px}figure{margin:0}figcaption{font-weight:600;margin:8px 0}video{display:block;width:100%;max-width:640px;background:#111;aspect-ratio:1}nav{display:flex;flex-wrap:wrap;gap:12px}summary{cursor:pointer;margin:18px 0}</style></head><body><main><h1>新生成 reward + 在线 Stage：C0 十任务视频</h1>'''
    page += f'<p>已完成 {status["completed"]}/10；已完成任务中成功 {status["successes"]}。状态记录：{status["utc"]}。最终计分须以完整审计报告为准。</p>'
    page += '<p>本轮每个任务都重新生成 reward 函数与阶段描述；两条调用路径均为 Poe Gemini-3-Flash。对照保留历史 reward。两轮 C0 参数与原控制规则一致。视频按 10 fps 播放，不包含在线 API 等待时间。</p><nav>'
    page += ''.join(f'<a href="#task-{i}">{i} · {name}</a>' for i, name in enumerate(NAMES)) + '</nav>'
    page += '\n'.join(cards) + '</main></body></html>\n'
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(page)
    print(str(DEST))


if __name__ == "__main__":
    build()
