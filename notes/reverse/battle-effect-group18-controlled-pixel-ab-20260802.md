# 战斗特效 group 18 受控单像素 A/B（2026-08-02）

## 结论

group 18 / sequence 7 已从受控直接 selector→spawn 的资源、task 与 OAM 身份，推进到
生产 relocation 后的最终屏幕单像素写回。baseline 与 candidate 使用相同的直接入口
探针、分配窗口和 2,002-byte LZ77 拓扑；candidate 仅把解压 graphics offset
`0xCA` 从 `0x44` 改为 `0x41`。

两次零输入运行都从已验收的 scenario 50 战斗快照恢复，并在 ack 相位捕获。EWRAM、
IWRAM、IO、PRAM 与 OAM 完全相同，VRAM 仅
`0x060160CA:0x44→0x41`。OAM entry 17 为
`0x0021/0x8068/0xCB00`，把 component 0 源像素 `(20,10)` 映射到屏幕
`(124,43)`；从两份 mGBA ack 存档离线重建的 Mode-0 图只有该像素从
`(181,181,181)` 变为 `(231,231,231)`。

三相捕获脚本生成的原始 mGBA `capture.png` 在两变体中逐字节相同，不能作为最终
像素 A/B 证据。artifact 因而把 `mgba_capture_pixel_ab` 固定为 false，并将顶层两张
PNG 明确标记为 `offline-mode0-from-ack-savestate`。本成果的运行时部分证明真实 mGBA
存档中的 task、OAM、VRAM 与三相提交，像素部分则是对该 ack 状态的独立离线合成；
不声称原始 mGBA 截图已经观察到差异。

该结果签发的是“受控直接入口 + 生产资源迁移”的最终像素写回，不是自然玩法路线，
因此 production 自然最终像素 A/B 仍为 `5/18`。18 组资源/task 身份的技术子分母也
保持 `18/18`，不能把二者相加或互相替代。

## 构建与运行合同

配置文件为
`sequel/content/battle-effect-controlled-pixel-ab/group-18-sequence-07-direct-spawn.json`。
构建器先验证父 direct-spawn artifact、18 组资源目录、原 graphics/palette 哈希和
exclusive pointer，再在 `0xB40000` 进行既有生产 relocation；两份 ROM 最后安装完全
相同的受控直接入口探针。它们均为 16 MiB，只有 relocation payload 的一个解压字节
不同，pointer、编码长度和探针字节均相同。

baseline/candidate ROM SHA-256 分别为
`12d14514f29097e520743c9a94fa8ef07c8f4b1a42d7322af245826493a51d9f` 和
`b10f1bec8ee15f1c79a3858ebd6c383f1f566f16f5af2a177d7a4f331d1f609f`。
目标 task 均为 slot 109、anchor `(120,80)`、tile base 768、palette bank 12，
definition/animation 为 `0x0834819C/0x083481DC`。

两次运行都经统一 heavy lock 完成，success marker、非 degraded、PGID 与 mGBA
listener 清理均通过。baseline 的峰值 tree RSS 样本为 `78.08203125 MiB`；candidate
只有 `0.171875 MiB`，属于采样不足，artifact 明确标记为不得用于峰值或均值统计，
不能据此宣称候选运行更省内存。

## Artifact 与复验

正式成果位于 `artifacts/battle-effect-group18-controlled-pixel-ab-v1/`，约 1.6 MiB，
包含 manifest、evidence、两张最终 PNG 和不含 ROM 的确定性 `raw.tar`。归档保存
102 个构建与运行来源成员，避免把临时实验目录和大量小文件留在 Git 工作树。

独立 verifier 不导入本成果的 builder 或 exporter。它重新执行父 direct-spawn
verifier、独立 LZ77 编码、两份 16 MiB ROM 重建、tar 安全与全集检查，并从两变体的
renderer/submit/ack 三份存档独立复算 PC、cycle、pending `0→1→0`、稳定 task、
资源与 shadow/hardware OAM 提交；最后比较六个内存域和离线 Mode-0 像素。它还固定
原始 mGBA 截图相同且不参与像素 A/B，拒绝把受控范围或截图范围重新签大。

复验命令：

```text
python3 tools/verify_controlled_battle_effect_pixel_ab.py \
  --root . \
  --artifact artifacts/battle-effect-group18-controlled-pixel-ab-v1
```

结果为 `verified=true, errors=[]`。

## 边界与下一步

本成果不签发 group 18 的自然玩法入口、sequence 18 的独立像素链、完整动画帧、
blend/window、音频、RNG 或实体 GBA 等价。sequence 7 与 18 使用同一 group 18
资源，当前没有必要为静态资源写回重复做第二份受控像素 A/B。

下一项高价值缺口是 group 3：其 304-tile graphics 需要自然 allocator 上游提供足够
容量并形成 exclusive pointer relocation，再从自然或可清晰标注的受控路线闭合最终
像素；不得用 group 18 的窄分配窗口或本成果外推。
