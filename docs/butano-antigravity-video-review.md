# 用 Antigravity 的 Gemini 3.8 Flash (High) 做录屏理解

本项目在核对木叶战记复刻差异时，把「看录屏」这一步交给本机 Antigravity CLI
里的 `gemini-3.8-flash-high`。本文记录已验证可用的通信方式、参数边界和失败关闭
规则，改动任何一项都要重跑 `tests/test_ask_antigravity_gemini.py`。

## 1. 入口与模型

| 项目 | 值 | 来源 |
| --- | --- | --- |
| CLI | `~/.local/bin/agy`（`~/.gemini/antigravity-cli/bin/agentapi` 的实际实现） | 本机已安装 |
| 模型 | `gemini-3.8-flash-high`（显示名 `Gemini 3.8 Flash (High)`） | `agy models` |
| 备选 | `gemini-3.8-flash-medium` / `-low`、`gemini-4-argon-high` | 同上 |
| 默认档 | `~/.gemini/antigravity-cli/settings.json` 里的 `model` | 用户全局配置 |
| 注意 | `/Applications` 下**没有** Antigravity.app，只有 CLI；不要按 IDE 假设去找 | 本机实测 |

`agy models` 是判断模型名是否存在的唯一权威来源。当前列表：

```
gemini-4-argon-medium / -high / -low
gemini-3.8-flash-high / -medium / -low
claude-opus-5-5-low / -medium / -high
claude-sonnet-5-5-low / -medium / -high
gpt-oss-120b-medium
```

## 2. 为什么必须放行工具权限

Antigravity 的视频理解不是把 mp4 原样喂给模型：代理会先 `ffprobe` 拿分辨率／帧
数／时长，再用 `ffmpeg`（`signalstats`、抽帧、rawvideo）做像素级检查，然后才描述
画面。`--print`（`-p`）无头模式无法弹窗授权，缺授权时它会**自动拒绝并返回空
response**：

```
jetski: no output produced — a tool required the "command" permission that
headless mode cannot prompt for, so it was auto-denied.
```

所以无头调用必须成对带上：

- `--sandbox`：把终端能力限制在沙箱内，保持「只读 sidecar」的定位；
- `--dangerously-skip-permissions`：跳过无法弹窗的授权询问。

两者同时使用时已实测 `ffprobe` / `ffmpeg` 仍可正常运行。不要单独用
`--dangerously-skip-permissions` 而不带 `--sandbox`；也不要改成
`--mode plan`，它与 `--disable-slash-commands` 同时使用会失效并打印警告。

## 3. 视频从哪来

`~/.gemini/antigravity-cli/bin/webm_encoder` **不能用**：它在 macOS 上只是
Chrome DevTools 截屏编码器，对目录或图片序列一律回
`Screencast recording is not supported on macOS without a running editor/browser instance.`。

正确做法是本机 `ffmpeg`（8.1，Homebrew）把帧序列编码成 mp4，由
`tools/butano/ask_antigravity_gemini.py` 封装。要点：

- 帧目录必须是从 `frame-000.png` 起连续、无 `step-*` 混入的完整帧集；
- 先用 PIL 把每帧按最近邻放大并在左上角烧入帧号，**原图不动**（模型引用的帧号
  才能回到原始 PNG 复核）；
- 编码必须带 `-fps_mode passthrough`。libx264 默认会丢重复帧：一次 30 帧
  （15 红 + 15 蓝）的合成测试被压成 17 帧，模型据此报告「切换发生在第 9 帧」，
  真实切换点是第 15 帧。`-crf 12 -preset veryslow` 保证 UI 文字可读。

## 4. 项目封装

```bash
python3 -m tools.butano.ask_antigravity_gemini FRAMES_DIR QUESTION \
    --work-dir RUN_DIR [--context TEXT] [--fps 60] [--scale 2]
```

产出 `RUN_DIR/`：

| 文件 | 作用 |
| --- | --- |
| `staged/frame-NNN.png` | 放大并烧帧号的副本，原帧不变 |
| `capture.mp4` | passthrough 编码的视频 |
| `prompt.txt` / `prompt_sha256` | 实际提问，逐字可复核 |
| `response.md` | 模型原话，不做润色 |
| `receipt.json` | 模型、agy 路径、视频哈希、帧数、fps、token 用量、conversation_id |

提示词固定写清：帧总数、0 基帧号、最后一帧号、`t = n/fps`、帧号已烧在左上角，
并要求「引用确切帧号」「不要凭单帧推断运动」「看不到就直说」。

## 5. 失败关闭

以下情况一律 `ReviewError`（CLI 退出码 2），不允许返回半截结论：

- 帧目录不存在、为空、帧号不连续，或混入 `step-*.png` 等非帧图片；
- 工作目录／暂存目录／视频已存在（保护既有证据，不覆盖）；
- `ffmpeg` 缺失或产出空文件；
- agy 缺失、退出码非 0、stdout 不是 JSON；
- `denied_actions` 非空（工具被拒 = 分析不完整，即使 status 是 SUCCESS）；
- `status != SUCCESS` 或 response 为空。

已验证的真实调用：24 帧（前 12 帧纯红、后 12 帧纯蓝）合成片段，模型用
`ffprobe`+`ffmpeg` 报出「前 12 帧红、后 12 帧蓝、在第 12 帧切换」，与构造一致
（`tests/test_ask_antigravity_gemini.py::RealAntigravityTest`，该测试会真的调用
模型，约 40 秒）。

## 6. 边界

- 模型只能说明「画面上看起来怎样」，不能作为像素等价证明；等价结论仍以
  `tools/butano/compare_frame_sequences.py` 的同索引全屏比对为准。
- 帧号引用必须回到原始 PNG 复核后才写进 notes，避免把模型的近似读数当证据。
- 本通道是只读 sidecar：不启动模拟器、不改 ROM、不写业务代码。
