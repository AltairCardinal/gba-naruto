# Group 3 自然到期生产像素 A/B（2026-08-02）

## 结论

忍具 67“引爆牌”的 C3 对象自然到期入口现已与 production 资源迁移组合：同一个
`expiry-ready` 快照分别加载 preservation baseline 和单像素 candidate ROM，全程不注入
按键，两者都在 frame 67/67/68 命中 group 3 的 renderer/submit/ack 事务。

这使战斗特效 production 修改 ROM 的自然最终像素 A/B 从 **5/18 提升到 6/18**；
精确提交相位仍为 **6/18**。

## 无探针构建

- profile：`sequel/content/battle-effect-natural-pixel-ab/group-03-tool67-expiry.json`；
- builder：`tools/build_natural_delayed_battle_effect_pixel_ab.py`；
- baseline/candidate 都只把 group 3 的共享 graphics 指针 `0x599134` 重定向到
  `0x08B40000`；group 2 的别名 `0x59912C` 保持原值；
- 两个 16 MiB ROM 均保留原始 SoundMain hook 和零填充 stub 区，不包含 controlled
  direct-spawn probe；
- 解压 graphics 仅 offset 207 从 `0x03` 改为 `0x0E`，两次 LZ77 均为 5294 bytes，
  patch topology 相同。

baseline ROM SHA-256 为
`354e43b8f0b366a6b63cf0b9a69fc3d5fd0a0a2429ce86ec2881abda53444c38`，candidate 为
`0965d07ecf7df9126866efc431c217a641175d44ffd48edd8e673d31cbdc6cfe`。

## 自然运行因果链

输入快照为
`artifacts/runtime-checkpoints/scenario-49-battle-14-tool67-expiry-ready.ss9`，其中只有
slot 3/state 1/C3/remaining 0 的延迟对象，输入时没有 group 3 task。两次运行均得到：

| 相位 | PC | frame | pending | task slot |
|---|---|---:|---:|---:|
| renderer-post | `0x08063328` | 67 | 0 | 126 |
| submit-post | `0x08061126` | 67 | 1 | 126 |
| ack-post | `0x080612AA` | 68 | 0 | 126 |

task 的 definition/animation 为 `0x083425D8/0x083426CC`，tile base 288、palette bank
5；完整 32-byte source palette 与运行时 PRAM 相等。EWRAM/IWRAM/IO/PRAM/OAM 均零
差异，VRAM 只有 `0x060124CF` 一字节从 `03→0E`。ack savestate 的独立 Mode 0 合成
只有屏幕 `(70,91)` 从 `[247,115,0]` 变为 `[115,107,99]`。

两次运行峰值 tree RSS 为 75.8515625/68.203125 MiB，guard 均为 completed、非
degraded，PGID 与 mGBA listener 均无残留。

## 持久证据与边界

正式成果在 `artifacts/battle-effect-group03-natural-pixel-ab-v1/`。独立 verifier 不导入
builder/exporter，重新编码 LZ77、重建两份 16 MiB ROM 哈希、验证三相 savestate/dump、
六内存域差异、OAM 提交和最终像素，结果为 `errors=[]`。聚合成果
`artifacts/battle-effect-observed-frame-phases-v1/` 现记录 phase groups
`[1,2,3,5,11,14]`、production pixel groups `[1,3,5,11,14,15]`。

本成果只证明 group 3 当前自然到期时 frame 0/component 0 的一个 graphics 像素；不证明
其余帧、非镜像/仿射分支、blend/window、音频、实体 GBA，亦不外推到其余 12 组。
