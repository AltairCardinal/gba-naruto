# Group 15 自然 action 64 运行时闭环（2026-08-02）

## 结论

桃地再不斩（character 20）在原 battle 8 的 AI 回合自然选择 action 64
“水遁・水龙弹术”。唯一显式输入是结束回合确认页上的一次 A（frame 60..68）；没有
自动输入或恢复输入。运行时链为：

`0x0807A222 → 0x0807F064 → 0x0807F09E → 0x0807F0FC →
0x0807F10C → 0x0807C5E8`。

分类比较结果为 0，没有进入固定 sequence 6；binder call 和 binder entry 均为
`side=1, sequence=17`。三份相位存档又独立读出
`0x02026CB8+0x770 = 0x02027428` 的 action byte 为 `0x40`，因此链路不是只靠静态
表或动作名称推断。

## 路线与快照

原 primary scenario 39 的 `SetBattle(40,2)` 仅把 file `0x31071` 从 40 改为 8；
16 MiB route ROM SHA-256 为
`6325192e28774efdb30014b87fe7a3e17f2c1bd1f7c34b2484815c156c081b4e`，相对基准 ROM
只有这一字节不同。该诊断入口保留原剧情、战前菜单、编成和战斗启动链，但不代表原版
剧情本来会在 scenario 39 进入 battle 8。

复用的“结束回合，可以吗？是”快照 SHA-256 为
`c775d4b5ea952f95bdac11993979ad62e11a9418456afc99a54d484b202ce1e1`。因此后续调试
不再重做标题、剧情、任务选择、战前菜单和部署导航。

## 三相全局提交

自然 action 64 在 frame 1546 绑定 group 15，下一帧生成 slot 124 task：

| 相位 | PC | frame | pending | task | dispatcher ordinal |
|---|---|---:|---:|---|---:|
| renderer-post | `0x08063328` | 1547 | 0 | slot 124 / `0x030058C8` | 3 |
| submit-post | `0x08061126` | 1547 | 1 | 同上 | 3 |
| ack-post | `0x080612AA` | 1548 | 0 | 同上 | 3 |

task 的 definition/animation 为 `0x0834711C/0x08347168`。三个相位均有 6 个 active
task，group 15 稳定处于 ordinal 3。renderer 与 submit 阶段的全局 shadow/hardware
OAM 不同，ack 后完整相等，形成 `0→1→0` 的全局提交事务。它证明该事务包含稳定的
group 15 task，但没有建立该 task 对某个 OAM entry 的排他写入归因。画面可见
“水遁・水龙弹术”标题和卡卡西/再不斩战斗场景。

## Artifact 与验证

`artifacts/battle-effect-group15-natural-runtime-v1/` 只有三个文件：manifest、
evidence 和约 1 MiB 的确定性 `raw-runtime.tar`。归档固定 48 个成员，包含原始
1,092-event observer audit、输入/最终快照、最终 PNG、完成标记、两份 guard、
profile/audit 及三相完整 dump；
不会把几十个小文件散落进 Git。

独立 verifier 不导入 exporter，并重新执行以下检查：

- 从基准 ROM 重建唯一 battle-ID 字节差异和 route SHA；
- 从原始 observer audit 选择唯一动态分支链并验证 side 1 / sequence 17，同时重算
  route ROM、输入状态、脚本、guard、run ID、最终 state/PNG 与完成标记绑定；
- 从三份 `.ss9` 读取 action 64；
- 从 task pool、active dispatcher、shadow/hardware OAM 重算 group 15 身份与包含它的
  全局三相提交，并明确拒绝排他 task→OAM 归因；
- 固定当前桌面 mGBA profile、observer/capture 脚本、归档分母及全部成员哈希。
- 在读取 tar payload 前限制每个成员、固定二进制及总归档大小，拒绝同名超大成员。

验证命令：

```bash
python3 tools/verify_battle_effect_group15_natural_runtime.py \
  --artifact artifacts/battle-effect-group15-natural-runtime-v1
```

结果为 `verified=true, errors=[]`。branch/phase 两次 guarded run 的峰值 tree RSS 分别
为 `66.359375 MiB` 和 `66.0234375 MiB`；两次运行都明确记录 PGID 与 mGBA listener
均无残留。

## 边界

本成果签发 natural action 64 的动态 binder 和一次包含稳定 group 15 task 的全局
renderer/submit/ack 事务，不签发：

- action 65；
- 原剧情自然抵达 battle 8；
- group 15 修改后的最终像素 A/B；
- group 15 task 对某个 OAM entry 的排他写入归因；
- 所有动画帧、RNG、blend/window、音频或实体 GBA 等价。

因此 production 自然最终像素 A/B 分母仍为 `4/18`，下一步从同一确认页快照对
group 15 relocation baseline/candidate 做单像素最终画面对照。
