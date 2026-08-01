# 战斗特效 group 3 受控最终像素写回（2026-08-02）

## 结论

group 3 / sequence 3 / side 0 已从受控资源、task 与 OAM 身份推进到 production
relocation 下的最终单像素写回。该入口仍是零输入直接 selector→spawn 探针，不是
自然玩法路线，因此 production 自然最终像素 A/B 保持 `5/18`，技术资源/task 身份
保持 `18/18`。

group 2 与 group 3 的 graphics 表项 `0x59912C/0x599134` 原本都指向
`0x08340AF8`。本次构建只把 group 3 的 `0x599134` 重定向到 `0x08B40000`，group 2
继续指向原资源；两份 ROM 使用完全相同的 5,294-byte 安全 LZ77 拓扑和完全相同的
直接入口探针。candidate 只把解压 graphics offset `0xCF` 从 `0x03` 改为 `0x0E`。

## 运行时与像素证据

baseline/candidate 均从同一已验收直接入口状态零输入恢复，依次捕获
`renderer 0x08063328 → submit 0x08061126 → ack 0x080612AA`。pending 为
`0→1→0`，ack 后完整 1 KiB hardware OAM 等于 renderer shadow。目标 task 均为
slot 109、definition/animation `0x083425D8/0x083426CC`、tile base 256、palette
bank 4。

OAM entry 22 为 `0x0028/0x9078/0x4900`。水平翻转把 frame 0/component 0 的源像素
`(22,11)`映射到屏幕 `(129,51)`。六个完整内存域中仅 VRAM
`0x060120CF` 一字节不同；从两份 mGBA ack savestate 独立离线重建的 Mode 0 图也只
改变该像素，RGB 从 `(247,115,0)` 变为 `(115,107,99)`。

两份原始 mGBA ack capture PNG 的 SHA-256 均为
`c289e4d9b0969333c14372ecb8edfc34e5ca77f9b77505499da06b8a4657200d`，逐字节相同，
所以不作为像素 A/B。artifact 固定 `mgba_capture_pixel_ab=false`，最终像素结论只来自
ack savestate 的独立 Mode 0 合成。

## Palette 与共享资源边界

baseline/candidate 的完整 PRAM 相同。运行时 palette 与 ROM 源 palette 只有前 30
字节一致，offset 30/31 为运行时 `01 00`、源 `6C 2D`。本次修改使用的索引 3 与 14
都落在已匹配范围内；成果明确记录 `source_palette_matched_prefix_bytes=30`、
`source_palette_mismatch_offsets=[30,31]` 和 `full_source_palette_equal=false`，不把
所选像素可解释性扩大为完整 32-byte palette 等价。

独立 verifier 还从基准 ROM 重建 group 2/3 的共享指针，并只对 `0x599134` 应用
redirect。把 `0x59912C` 一并重定向或把 palette 声明扩大为 32/32，即使重新签名
manifest，也会被拒绝。

## Artifact、资源安全与复验

正式成果位于 `artifacts/battle-effect-group03-controlled-pixel-ab-v1/`，包含两张离线
最终 PNG、evidence、manifest 和一个不含 ROM 的 102-member 确定性 `raw.tar`。运行
来源、三相 savestate、audit、guard、构建 ledger 与实现依赖均进入哈希分母。

baseline 的有效峰值 tree RSS 样本为 `77.73046875 MiB`；candidate 的
`0.171875 MiB` 属于短运行欠采样，只保留原样记录，不参与统计。两次运行的 PGID 与
mGBA listener 均清理完成。本轮复用既有运行目录，没有再次启动 mGBA；group 18 也只
从已归档 raw 证据重建，以适配通用化后的严格实现哈希。

复验命令：

```text
python3 tools/verify_controlled_battle_effect_pixel_ab.py \
  --root . \
  --artifact artifacts/battle-effect-group03-controlled-pixel-ab-v1
```

结果为 `verified=true, errors=[]`。

## 未完成边界

本成果不签发 group 3 的自然 allocator 上游、间接回调表消费者、自然 side 镜像分支、
palette 尾字生命周期、完整动画/音频、自然最终像素 A/B 或实体 GBA 等价。下一步仍应先
定位 `0x0807F208` 的自然间接消费者及其之前最近的 wide allocator reset，不能把本次
受控容量重建冒充自然调用链。
