# Character growth 运行时消费链（2026-07-11）

## 结论

原 `character-stats@0x54507A` 和 `character-stats-b@0x545200` 不是两张表。
真实结构是 file `0x545068..0x545457` 的 **63×`0x10` 角色成长表**，并已通过
代码引用和受控首战 A/B 闭合到 WRAM 角色模板及战斗单位槽。

- 地址公式：`0x545068 + character_id*0x10`；
- 结束地址：`0x545068 + 63*0x10 = 0x545458`，与下一张已知表严格相接；
- 消费函数：Thumb `0x0806D964`；
- 模板池：`0x02022E34 + slot*0xBC`；
- 战斗单位：`0x020240C0 + slot*0x1D4`；
- 证据等级：`runtime_verified`；
- `0x545200` legacy 回写已禁用。

## 尝试与方法

### 1. 扩大指针扫描范围

直接搜索 `0x0854507A` / `0x08545200` 均无引用。改为扫描整个邻近区域
`0x545000..0x545458`，找到三个对齐 ROM literal：

| literal 位置 | 值 | 用途 |
|---:|---:|---|
| `0x0806D998` | `0x08545068` | 普通 character ID 的成长基址 |
| `0x0806D9AC` | `0x085450E8` | ID 57 复用 physical record 8 |
| `0x0806DB3C` | `0x08545158` | ID 58 复用 physical record 15 |

有效方法是扫描“目标附近的所有 ROM 指针”，而不是只扫已有猜测的精确地址。
这是本次从零引用恢复真实消费者的关键。

### 2. 反汇编工具问题

仓库 `tools/_vendor/capstone/lib/libcapstone.dylib` 是 x86_64，当前 arm64 macOS
无法加载。临时安装 arm64 Capstone 到 `/private/tmp/gba-capstone` 后，用
`CAPSTONE_PYTHON_PATH=/private/tmp/gba-capstone` 运行反汇编工具。两个工具现支持
该环境变量：

```sh
python3 -m pip install --target /private/tmp/gba-capstone capstone==5.0.6
CAPSTONE_PYTHON_PATH=/private/tmp/gba-capstone \
  python3 tools/disasm_thumb.py rom/base.gba 0x0806D964 --before 0 --size 0x180
CAPSTONE_PYTHON_PATH=/private/tmp/gba-capstone \
  python3 tools/find_thumb_calls.py rom/base.gba 0x0806D964
```

这个兼容问题此前会让静态分析脚本直接崩溃；现在失败路径和恢复方式均已固化。

## 静态消费链

`0x0806D964` 输入 `r0=template`。`template +0` 是 character ID，`template +1`
是 level。普通 ID 路径：

```text
0x0806D974  ldrb id, [template]
0x0806D98A  id << 4
0x0806D98C  load 0x08545068
0x0806D98E  growth = base + id*0x10
0x0806D9B8  level = template[1]
0x0806D9BA  level_minus_one = level - 1
```

随后每个字段执行整数运算 `growth * (level-1) / 100`，加到
`0x0854241C + id*0xB4` 角色定义的基础值，再写入模板：

| growth record | 角色定义 base | 模板目标 | 代码范围 |
|---:|---:|---:|---:|
| `+0x04` | `+0x01` u8 | `+0x02` u8 | `0x0806D9C0..D9D2` |
| `+0x06` | `+0x02` u8 | `+0x03` u8 | `0x0806D9D4..D9E6` |
| `+0x08` | `+0x03` u8 | `+0x04` u8 | `0x0806D9E8..D9FA` |
| `+0x0A` | `+0x04` u8 | `+0x05` u8 | `0x0806D9FC..DA0E` |
| `+0x0C` | `+0x05` u8 | `+0x06` u8 | `0x0806DA10..DA22` |
| `+0x02` | `+0x06` u8 | `+0x08` u8 | `0x0806DA24..DA36` |
| `+0x00` | `+0x0A` u16 | `+0x0E` u16 | `0x0806DA38..DA4C` |

`+0x0E` 未被这条路径读取。模板字段随后有上限钳制：普通三项最大 99，移动
最大 5，两项资源最大 9，u16 两项最大 999。调用点至少有 12 处，包括角色模板
创建 `0x0806D5C6` 和 formation→battle 路径 `0x0806AD40`。

## 旧 bank 为什么错

- `0x54507A = 0x545068 + 1*0x10 + 2`，旧 primary 从角色 1 记录 `+2` 开始；
- `0x545200 = 0x545068 + 25*0x10 + 8`，旧 B 从角色 25 记录 `+8` 开始；
- 两者只是对同一连续表的错位窗口，所谓不同字段顺序是错位造成的假象；
- 原 `generate_character_stats_b_patches()` 会跨真实记录边界写 16 字节，已改为
  `db_character_stats_b_disproved` diagnostic，零 bytes patch。

## 动态两因素 A/B

### 难点

首战 character ID 1 的 level 为 1，正常公式 `(level-1)=0`。只改成长值不会产生
运行时差异，属于必然伪阴性。

### 诊断 ROM

`tools/build_character_growth_probe.py` 强制验证基准 ROM SHA-1 和 before bytes。

- C/control：仅把 file `0x06D9BA` 的 Thumb `subs r0,#1` (`01 38`) 改为
  `subs r0,#0` (`00 38`)；SHA-256
  `e973fca0e2b63184bc2e5b0bab9696cb7208b30d21261d34095d5d7f84a8e3e9`；
- D/changed：在 C 基础上，仅把 character ID 1 growth record `+0x04`，即 file
  `0x54507C`，从 u16 100 改为 200；SHA-256
  `4c8161c625296241f115957668a38840955943546b0ff286d6f7cfc96a1fb56d`。

两版走完全相同的 WASM 导航，均得到 battle ID 40、slot 1 character ID 1、坐标
`(4,4)`、map runtime `[36,44,9,22]`，且 template slot 1 与 battle slot 1
前 `0xBC` 字节匹配。

| 结果 | control | growth=200 |
|---|---|---|
| template/battle first16 | `01010f0e0903050505000f005e005e00` | `0101100e0903050505000f005e005e00` |
| 两版唯一 runtime 差异 | `+2 = 15` | `+2 = 16` |
| result SHA-256 | `2efdb73d5f1f9ed2c3cebb4c43045d5afcc173f5592d36c61c1f1f7eb23f38dc` | `e6b9e4adf75fd695cd7829b799f3ae38ea89c6b6a8de8f67e85173deb79f157a` |
| screenshot SHA-256 | `9bc9f1c2a35e890bf59ee5e5e07e4334d05c447d26374c0d8c4b271fccaad3f8` | `cc53b728a83a9883fba226321a9cadc257d2dc8205013d9436dd32e5867fc4a6` |

这证明 physical record 1 `+0x04` 被既有代码读取、参与乘除运算、写入模板 `+2`，
再复制到战斗槽；不是简单的内存值相关性。

## 交付物与下一步

- `tools/extract_character_growth.py`：63 条无损提取；
- `tools/verify_character_stats_records.py`：纠正后的表边界与 ROM fidelity；
- `tools/build_character_growth_probe.py`：可重复诊断 ROM；
- `tests/test_extract_character_growth.py`、`tests/test_build_character_growth_probe.py`；
- `sequel/content/character-stats/bank.json`：迁移到真实表；
- `sequel/content/character-stats-b/bank.json`：disproved tombstone。

人物信息页同边界截图/EWRAM 已命名 growth `+0` 体力、`+4` 攻击、`+6` 防御、
`+8` 敏捷、`+A` 移动。growth `+2/+C` 对应 template `+8/+6`，仍需单字节 UI
A/B 排定查克拉与手里剑容量；`+E` 仍未读。editor DB 仍需迁移到 63 条 lossless
growth records，之后才可恢复字段级安全写回。
