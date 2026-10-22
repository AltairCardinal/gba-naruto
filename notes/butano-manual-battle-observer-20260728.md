# Butano 人工战斗观察器（2026-07-28）

## 目的

用于捕获“佐助对黄蜂使用忍者组合拳后未进入战斗并卡死”的人工操作现场。
观察器只读取按键、战斗遥测和 CPU 寄存器，不注入按键、不写模拟器内存、
不加载状态，因此人工复现路径不会被自动化脚本改写。

## 启动与收尾

从仓库根目录执行：

```sh
tools/butano/start_manual_battle_observer.sh
```

启动前也可执行只读检查；直接执行和显式使用 `sh` 的行为一致：

```sh
tools/butano/start_manual_battle_observer.sh --check
sh tools/butano/start_manual_battle_observer.sh --check
```

启动器会：

1. 从当前 ELF 符号动态解析战斗遥测、战役遥测和 `bn::assert::show` 地址；
2. 把当前 `butano-sequel/butano-sequel.gba` 复制为本次运行目录中的独立 ROM；
3. 把场景 49 的干净存档复制为与该 ROM 同名的独立 SAV；
4. 经 `tools/run_guarded.py` 和统一 heavy lock 启动签名版 mGBA；
5. 把本次目录写入 `artifacts/manual-battle-observer-latest.txt`。

启动器使用 POSIX `sh` 语法，不依赖 zsh 的路径修饰符。ROM、ELF、
存档、mGBA、观察器或必要符号缺失时，会在创建本次运行目录前输出
明确的中文错误，不再静默退出。每次启动都从当前构建复制 ROM，不再读取
`konoha-battle-acceptance-clean.gba` 等历史验收副本；因此 ELF 符号、ROM 代码和
本次日志属于同一个构建。

卡住后停止输入并等待至少 5 秒，再关闭 mGBA。随后可执行：

```sh
python3 tools/butano/summarize_manual_battle_observer.py
```

## 产物

- `manual-battle-trace.jsonl`：状态变化、每秒心跳、按键位图、PC/LR/SP。
- `sasuke-taijutsu-focus-armed.png`：进入佐助忍者组合拳选目标状态。
- `presentation-start.png`、`presentation-stage-*.png`：演出启动与阶段切换。
- `stall-snapshot-*.json/.png/.ss9`：目标路径连续约 180 帧无状态变化。
- `assert-hit.json/.png/.ss9`：命中 Butano 断言入口时的寄存器和现场。
- `guard.json`：mGBA 进程退出原因、资源峰值和运行时边界。

如果程序在断言前完全停止逐帧回调，断言断点仍可独立留下
`assert-hit` 产物；如果没有命中断言，则 JSONL 最后一条记录中的
阶段、演出状态和 PC/LR/SP 是定位停点的主要依据。

## 当前验证基线

- ROM SHA-256：
  `b3e02cbba75ee3a66357be70fb0c06aeb98330fe4c2c54b5d013e21d7e0576fe`
- ELF SHA-256：
  `31014feab37ab060cd1c0f3146ae2e0b16e0b0a48e6a7e3ea829c6e07382bd32`
- 遥测地址：战斗 `0x020227dc`，战役 `0x0200820c`
- Butano 断言入口：`0x08035724`
- 冒烟证据：
  `artifacts/butano-battle-manual-observer-smoke-20260728-02/`

短时真实 mGBA 冒烟运行持续写出 `waiting-for-telemetry` 心跳，
观察器没有命中断言，也没有生成输入；进程由资源守卫按预设的
8 秒 wall timeout 回收，峰值进程树 RSS 为 132.98 MiB。
