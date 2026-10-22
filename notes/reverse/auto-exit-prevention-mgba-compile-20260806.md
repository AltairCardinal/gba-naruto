# mGBA 工具链编译尝试记录（2026-08-06）

## 背景

profile.json 与 tools/run_macos_mgba_replay.py 引用不一致：

| 字段 | profile.json | run_macos_mgba_replay.py |
|---|---|---|
| mgba_source_commit | d8bad14b4540f9114246c0281d74985cf81adc68 | 26b7884bc25a5933960f3cdcd98bac1ae14d42e2 |
| backport_commit | (未指定) | 7cacae126207de5499857439b9c7919bf8e882c2 |
| expected_sha256 | c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8 | (间接，EXPECTED_PATCH_SHA256=e76c8fc4...) |

profile.json 期望 `c1135d28...`，但没指定 backport patch。

## 编译尝试 1：d8bad14b commit + Qt5 + Release

```bash
cd /tmp/mgba-build
git clone https://github.com/mgba-emu/mgba.git
cd mgba
git checkout d8bad14b4540f9114246c0281d74985cf81adc68
git submodule update --init --recursive
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_QT=ON \
      -DBUILD_SDL=OFF -DCMAKE_PREFIX_PATH=/usr/local/opt/qt@5
make -j8 -C build
```

结果：
- size: 3.7 MiB
- sha256: `953572b3575b5e3eee9e30ccd0ba62a78dd4628d1034c24bc6356358e4ba2667`
- 期望: `c1135d28ec17def50c6cea0ef635bf1c4902290a4d2e9ba4a5376c300da642c8`
- **不匹配**

副作用：本编译产物支持 `--script` 选项（因为 d8bad14b 已包含此功能）。

## 编译尝试 2：26b7884bc + 7cacae126 backport

```bash
cd /tmp/mgba-build-correct
git clone https://github.com/mgba-emu/mgba.git
git checkout 26b7884bc25a5933960f3cdcd98bac1ae14d42e2
git checkout 7cacae126207de5499857439b9c7919bf8e882c2 -- \
    src/platform/qt/ConfigController.cpp src/platform/qt/Window.cpp
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_QT=ON \
      -DBUILD_SDL=OFF -DCMAKE_PREFIX_PATH=/usr/local/opt/qt@5 \
      -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DENABLE_SCRIPTING=ON
make -j8 -C build
```

结果：**编译失败**，ConfigController.cpp 中 QGBA::ConfigOption::addValue 返回
类型不兼容 Qt5 旧头文件：

```
error: return type of out-of-line definition of 'QGBA::ConfigOption::addValue'
       differs from that in the declaration
error: no viable overloaded '='
```

backport 7cacae126 假设了较新 Qt5 API（shared_ptr<Action>），与
homebrew Qt5 5.15.18 的 Action* 不兼容。

## 真正的 mGBA 工具链来源

profile.json 中的 `c1135d28...` binary 是 mGBA 0.10.5 (d8bad14b commit)
**带有 Qt script backport patch 7cacae126207**——但需在 Qt 编译器环境
配套升级（Qt 5.15.x newer patches 或 Qt 6.x）。

需要的 binary 来源：
- mGBA-emu/mgba CI artifacts（d8bad14b + backport 7cacae126 的 prebuilt）
- 或自行 forward-port backport patch 到兼容的 mGBA commit

按当前 macOS 环境 Qt 5.15.18 + Xcode CLT，无法直接编译出
profile.json 期望的 binary。

## 推荐后续修复

1. 升级 macOS Qt 到 Qt6，或用 LLVM Qt 14+
2. forward-port 7cacae126 backport 到兼容 API
3. 或使用 mGBA 0.11+ 已包含 --script 选项的版本（但需 profile.json 重签）
4. 或用 mGBA-emu/mgba 提供的 CI artifact（如果有）

profile.json 的 mgba_binary_sha256 可能来自一次特定的 CI 构建，
不一定能本地复现。

## 数据完整性 + 工具链双重 blocker

> **2026-08-09 更正：以下 blocker 判断均不再成立。** `.ss9` 是包含 `gbAs`
> 状态 chunk 的合法 PNG 容器；profile 指定的 mGBA binary 也已在
> `/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA` 找回并核对
> SHA-256。forward-port 编译是一次可保留的历史调查，但不是继续逆向的前置条件。

- **blocker 1**: artifacts/runtime-checkpoints/*.ss9 实际是 PNG（d8bad14b
  commit 中 emu:saveStateFile 行为变更，或某次具体 save bug）
- **blocker 2**: profile.json 期望的 mGBA binary SHA 在当前 macOS Qt5
  环境下不可重现编译
- **blocker 3**: 26b7884bc + 7cacae126 backport 在 Qt5 5.15.18 不兼容

三个 blocker 都需要先解决才能继续推进 mGBA 工作。当前会话**不**继续
mGBA 编译尝试（避免浪费更多时间在工具链问题上）。

## 不属于本 notes 的内容

- 不修改 profile.json（已签 manifest）
- 不 monkey-patch verifier SHA 检查（debug-only 操作可能掩盖数据完整性问题）
- 不重签 verifier manifest（依赖 .ss9 数据完整性，.ss9 修复后才能重签）
