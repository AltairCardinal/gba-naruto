# Butano 本地开发参考

## 固定版本

本仓库使用 Butano **21.7.1**，源码固定在提交
`112a1827c9c6d9e6041a7e93e66f04c4561a6415`。Butano 采用 zlib
许可证；许可证原文随源码保存在 `third_party/butano/LICENSE`。固定提交而不是只跟随
tag，可避免 tag 或远端状态变化造成不可复现构建。

devkitARM 通过 Docker 镜像摘要固定，唯一事实源是
`tools/butano/toolchain.lock`。当前摘要为：

```text
devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5
```

## 本地资料入口

克隆仓库并初始化 submodule 后，源码、生成后的 API 文档、示例和完整游戏样例均可离线查看：

| 用途 | 本地路径 |
|---|---|
| Butano 源码 | `third_party/butano/butano/` |
| 离线文档首页 | `third_party/butano/docs/index.html` |
| 教程和模块文档 | `third_party/butano/docs/` |
| 官方示例 | `third_party/butano/examples/` |
| 官方完整游戏 | `third_party/butano/games/` |
| zlib 许可证 | `third_party/butano/LICENSE` |
| WAV→S3M 转换器源码与文档 | `third_party/gba-wav-to-s3m-converter/` |
| 木叶战记最小工程 | `butano-sequel/` |

在 macOS 上可用 `open third_party/butano/docs/index.html` 打开离线 API
文档。首次克隆后的初始化命令是：

```sh
git submodule update --init --recursive third_party/butano
python3 tools/butano/verify_setup.py
```

官方在线入口保留作版本核验：

- [Butano 源码仓库](https://github.com/GValiente/butano)
- [21.7.1 发布页](https://github.com/GValiente/butano/releases/tag/21.7.1)
- [入门指南](https://gvaliente.github.io/butano/getting_started.html)
- [模块、示例与导入说明](https://gvaliente.github.io/butano/modules.html)
- [常见问题](https://gvaliente.github.io/butano/faq.html)

## 构建与验证

前置条件是 Docker Desktop 已安装且 daemon 正在运行。首次构建需要下载约
512 MB 的 devkitARM 镜像；此后使用本地缓存。最小工程通过以下命令构建：

```sh
tools/butano/build.sh
```

产物为 `butano-sequel/butano-sequel.gba`。ROM 冷启动后先以内嵌断言检查行动状态机、
寻路、战斗效果、章节脚本和存档编解码，然后从原作任务准备菜单进入 scenario 41。
黄金路线覆盖四回合、原作行动/术/确认 UI、战斗对白、胜利、`100/50/0=150` 结算、
鸣人 LV2、11 页战后对白和战后世界地图；真实 mGBA 中 38 个稳定边界保持零像素差，
逐帧组合拳为 **264/264** normalized RGB 一致。

音频使用 Maxmod：战前/战斗/组合拳/战后对白/世界地图分别接入 cue 5/14/15/8/2。
BGM 由原 PCM 下混、去直流并重采样为 Maxmod 要求的 unsigned 8-bit、22050 Hz 单声道后封装为 S3M；UI 与战斗事件音效转为 22050 Hz 单声道 WAV。WAV→S3M 转换器固定在提交
`ec956fc951cc637153139cb968721f427c802e51`，源码和 README 保存在
`third_party/gba-wav-to-s3m-converter`。各 cue 的输入、输出哈希和循环误差位于
`artifacts/scenario-41-audio-reference-v1/`。

构建中没有网络版本漂移：脚本只接受 `tools/butano/toolchain.lock` 中按 SHA-256
摘要固定的镜像。

可复现的完整按键路线、38 张关键截图、最终 save-state 和 JSON 审计由
`tools/butano/mgba_scenario_41_golden_route.lua` 生成。必须通过
`tools/run_guarded.py` 和 shared heavy lock 启动，不直接裸跑 mGBA；完整命令、ROM/
模拟器哈希和已验收证据见 `notes/butano-scenario-41-runtime-20260721.md`。

官方图形和音频资产链路可分别复验：

```sh
tools/butano/build.sh third_party/butano/examples/sprites
tools/butano/build.sh third_party/butano/examples/audio
```

非集成测试默认不会重复编译 ROM；需要完整构建时使用：

```sh
RUN_BUTANO_INTEGRATION=1 python3 -m unittest tests.test_butano_build -v
```

## 故障处理

- `Butano setup is incomplete`：按错误清单恢复 submodule、离线文档、最小工程或锁文件，再运行 `python3 tools/butano/verify_setup.py`。
- `Docker daemon is unavailable`：启动 Docker Desktop，确认 `docker info` 成功后重试。构建脚本不会偷偷改用宿主机上的未知 devkitARM。
- 镜像拉取失败：检查网络或 Docker 登录状态；不要把 lock 中的 digest 改成浮动 tag。
- 构建目录权限错误：当前脚本以宿主用户 UID/GID 运行容器。若旧产物由 root 创建，先确认只处理 `butano-sequel/build/` 内的生成物，再清理重建。
- ROM 在模拟器中异常：保留 ROM SHA-256、工具链 lock、Butano 提交和唯一 run ID；通过 `tools/run_guarded.py` 启动 mGBA，避免绕过仓库的资源守卫。
- ROM 有画面但无声音：检查 `butano-sequel/build/bn_audio_manager.bn_noflto.d` 是否包含 `bn_hw_audio_maxmod.h`。`tools/butano/build.sh` 会检测历史 null-backend 对象并执行一次干净重建；不要手工复用该陈旧对象。
- ROM 声音撕裂或进入战斗黑屏：除检查五个 BGM manifest 为 `channels=1`、`sample_rate=22050` 和 ROM 不超过 8 MiB 外，还必须审计输入 PCM 的相邻采样突跳。`build/audio-v2/pcm/` 的离线整曲渲染已被用户听感与原 ROM 实录对比推翻，生产 BGM 必须来自 `butano-sequel/audio-runtime-bgm/` 的运行时实录中间件。mGBA 版本、渲染器和宿主音频后端不是本次故障根因。
- 离线文档缺页：确认 submodule 正好位于固定提交，并检查 `third_party/butano/docs/index.html`，不要临时抓取网页覆盖本地版本。

## 升级流程

1. 阅读目标 Butano release notes，确认 GBA、devkitARM 和资产工具兼容性。
2. 在独立分支把 `third_party/butano` 移到目标提交；源码与该提交自带的 `docs/` 必须一起更新。
3. 选择官方 devkitARM tag，拉取后以 `RepoDigests` 获取不可变摘要，更新 `tools/butano/toolchain.lock`。
4. 先让版本契约测试因旧值失败，再更新 verifier 和测试期望值。
5. 依次编译最小 ROM、`examples/sprites`、`examples/audio`，再通过资源守卫运行 mGBA 冒烟。
6. 记录新版本、提交、镜像摘要、ROM 哈希和兼容性差异；未通过全部验证前不得删除旧的可复现信息。

## 能力边界

Butano 提供 GBA 硬件抽象、精灵/背景、输入、音频、SRAM、固定容量容器、日志和性能分析等基础设施。它不直接提供木叶战记所需的场景栈、战棋地图语义、寻路、单位规则、技能效果链、AI、任务目标、可靠存档 schema 或章节脚本虚拟机；这些属于本项目需要实现和测试的游戏层。
