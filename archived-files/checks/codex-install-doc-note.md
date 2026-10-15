# Codex CLI installation note for final documentation

Verified 2026-10-13. Codex CLI is an external prerequisite, not installed by the Python requirements. The actual online cohorts use `codex-cli 0.156.1`, resolved locally to the standalone package. This task did not perform a fresh Codex CLI installation or a new account login.

Suggested documentation text:

在创建 Python 环境之外，还需按 [官方 Codex CLI 安装说明](https://learn.chatgpt.com/docs/codex/cli) 安装独立 CLI 并加入 PATH。本文验收记录的 CLI 是 **0.156.1**；官方默认安装命令可能安装更新版本，不应将更新版本自动视为相同实验环境。请记录实际版本，使用不同版本时先单独完成预检与对照验收。当前环境未验证从零安装 CLI 的过程。

```bash
command -v codex
codex --version
# 已有有效会话无需重新登录；新环境执行并完成自己的浏览器登录。
codex login
codex login status
```

CLI 支持浏览器 ChatGPT 登录；无浏览器服务器可按 [官方鉴权说明](https://learn.chatgpt.com/docs/auth#login-on-headless-devices) 使用 `codex login --device-auth`，需要账户或工作区允许设备码登录。不要复制其他合作者的凭据，凭据不放进项目配置或 Git。随后运行项目的 `check_steering.py --gpu --api`，实际验证本次指定模型的视觉请求是否可用。

The two official pages were fetched. Official installation currently shows a standalone shell installer, but it was not executed. No model, account, CLI binary, or experiment setting was changed.
