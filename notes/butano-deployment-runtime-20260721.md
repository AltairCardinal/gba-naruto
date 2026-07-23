# Butano 部署与 mGBA 冒烟记录（2026-07-21）

## 输入与版本

- Butano：21.7.1
- Butano commit：`112a1827c9c6d9e6041a7e93e66f04c4561a6415`
- devkitARM image：`devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5`
- 最小 ROM：`butano-sequel/butano-sequel.gba`
- ROM SHA-256：`739dfde790e6a1429fd7b291843f1d48ec2e98004e37e649fab87a4fd2999545`
- mGBA：Homebrew 0.10.5_2，实际前端为 Qt/Cocoa

## 构建结果

以下输入都在固定 Docker 镜像中成功完成资产生成、编译、链接和 gbafix：

1. `tools/butano/build.sh`
2. `tools/butano/build.sh third_party/butano/examples/sprites`
3. `tools/butano/build.sh third_party/butano/examples/audio`

最小 ROM 集成测试同时验证了 GBA header：title 为 `KONOHA BASE`，game code
为 `KNBT`。这证明源码、离线文档对应版本、C/C++ 编译器、Butano runtime、图形转换和音频转换链路均能在本机复现。

## 受守卫约束的 mGBA 运行

所有尝试都通过 `tools/run_guarded.py` 和同一 heavy lock 运行，限制为：最低可用内存
4096 MiB、进程树 RSS 1536 MiB、wall timeout 60 秒、idle timeout 30 秒。原始证据未覆盖：

| run ID | 结果 | 结论 |
|---|---|---|
| `butano-smoke-20260721-01` | `launch-error`，exit 125 | 调用多传一个 `--`，守卫把分隔符当作可执行文件；mGBA 未启动。命令已在后续 run 修正。 |
| `butano-smoke-20260721-02` | `child-exit`，exit 1 | 现有启动器把 Homebrew mGBA 误判为需要 Xvfb，但 macOS 无 Xvfb。已用回归测试修正为只对明确的 `mgba-qt` 名称启动 Xvfb。 |
| `butano-smoke-20260721-03` | `idle-timeout`，exit 124 | mGBA 进程树峰值 101.16 MiB；Homebrew Qt/Cocoa 前端没有在无窗口 debugger 管道中消费 `frame` 命令，守卫按策略终止 owned process tree。 |

第三次运行的守卫摘要位于
`build/butano-smoke-20260721-03/guard-summary.json`。没有生成 snapshot，因此当前只能确认
ROM 可构建和头部有效，不能宣称已经在该 macOS frontend 中验证 `PRESS A` →
`INPUT OK` 的运行时交互。

## 后续复验方法

优先在提供 SDL CLI frontend 的环境中设置 `MGBA_BIN`，然后以新的唯一 run ID 重跑同一
snapshot 命令；不得放宽 heavy lock 或删除 timeout 来掩盖 frontend 不兼容。若继续支持
Homebrew Qt/Cocoa，应新增一个能可靠等待 debugger 就绪并传递命令的 macOS runner，先以
失败集成测试固定行为，再替换当前管道。
