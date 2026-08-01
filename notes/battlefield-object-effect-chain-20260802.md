# 战场对象延迟特效生产链

## 结论

原 ROM 中忍具 67–72 形成一组完整的延迟战场特效生产链。六个忍具的 effect code
均为 `0x18`，resolver `0x08077514` 把 event `+0x0C` 的高位编码动作写入 type-1
战场对象 `+4`；阵营回合结束时 `0x08081B70` 读取该字段并加 `0x21`，精确生成
`0xE4..0xE9`。演出初始化最终按这六个动作分派到同一原生 handler
`0x0807F209`（Thumb 入口 `0x0807F208`）。

| 忍具 ID | 对象内编码动作 | 到期动作 | effect flags | primary handler |
| ---: | ---: | ---: | ---: | ---: |
| 67 | `0xC3` | `0xE4` | `0x00` | `0x0807F209` |
| 68 | `0xC4` | `0xE5` | `0x00` | `0x0807F209` |
| 69 | `0xC5` | `0xE6` | `0x00` | `0x0807F209` |
| 70 | `0xC6` | `0xE7` | `0x40` | `0x0807F209` |
| 71 | `0xC7` | `0xE8` | `0x40` | `0x0807F209` |
| 72 | `0xC8` | `0xE9` | `0x40` | `0x0807F209` |

六条 secondary handler 均为 0。

## 静态调用链

```text
选择的 encoded ninja-tool action C3..C8
  -> 0x080755FA: 保存到 event +0x0C
  -> 0x08077514 / 0x0807752C: 创建 type-1 战场对象
  -> 0x08081024: event action 复制到 object +4
  -> 0x08073688: 阵营结束调用 0x08081B70
  -> 0x08081D74: object +4 加 0x21，生成 E4..E9
  -> 0x08081F60: 0x0807AB34
  -> 0x0807ABD4: 0x0807F414
  -> action > 0xE3 的特殊路径
  -> 0x0807FD14: reset(0x100, 0x39F, 4, 14)
  -> 0x0807FD28: primary[action]
  -> 0x0809C114: 间接跳转
  -> 0x0807F208: 原生 Group 3 处理器
```

`tools/analyze_battlefield_object_effect_chain.py` 对 ROM SHA、关键代码片段、七个
直接 `BL`、忍具模板、effect dispatch 和六个 handler 表项做 fail-closed 绑定，生成
`battlefield-object-effect-chain-bindings-20260802.json`。独立
`tools/verify_battlefield_object_effect_chain.py` 不导入分析器，会从基准 ROM 重新计算
上述事实；篡改自然完成声明或 handler 映射都会失败。

## 自然运行时边界

`tools/find_battlefield_object_effect_seeds.py` 可批量扫描 mGBA 存档，只接受：

- state 为 1/2 且 `object+4` 为 `0xC3..0xC8` 的活动战场对象；
- 有效单位在 `unit+0xB0` 声明范围内实际装备的忍具 67–72；
- 持久忍具库存 `0x02023FD4..0x02024044` 中 ID 67–72 的非零数量；其中前两字节
  分别是总数和空位，工具 ID `n` 位于偏移 `n+1`；
- 24 槽持久角色模板池 `0x02022E34 + slot*0xBC` 的 `+0xB0/+0xB1...`
  装备计数与工具 ID，不把“尚未进入战斗”误报成未装备。

第一版扫描遗漏了持久库存，只能证明当时没有活动对象或已经装入单位战斗槽的目标忍具，
不能证明没有可恢复种子。补齐库存后，经 `tools/run_guarded.py` 重新扫描 `artifacts/`
的 183 份和 `build/` 的 981 份存档，共 1,164 份，全部解析成功并命中 248 个路径；
第二次自然 UI 复核发现库存偏移曾被直接当成工具 ID：这些命中实际均为库存中的忍具
67、数量 1；旧“忍具 68”结论已取代。原始语料中没有活动 `0xC3..0xC8` 对象，也没有已装备的
忍具 67–72。224 个不同 savestate SHA 中包含已跟踪 checkpoint：

- `artifacts/runtime-checkpoints/scenario-47-battle-13-postbattle-world-map.ss9`
- SHA-256：`e80779dc048fd862d0a8fc1a47f77bcfe1ab06810859f38015c562679958b800`

复跑输出位于忽略的实验目录
`build/experiments/active/20260802-group3-seed-scan/seeds-inventory.json`，SHA-256 为
`226358f776c85b84efcd499e8f19d6db8fe3997679cdb6dab7ae2a33dbd82a28`；guard 摘要 SHA-256
为 `403d2425f64c06395a2566f8c878145d43473ad2cf3baa5bea75a3de21ef9367`，峰值 tree RSS
为 20.28515625 MiB。扫描本身未启动 mGBA。

从该世界地图 checkpoint 经自然 UI 展开 18 件库存，向下 13 次选中画面可见“引爆牌”，
按 A 后鸣人持久模板 `0x02022FA1` 从工具 1 变为工具 67，库存数量保持 1。随后以该状态
重新启动当前桌面 mGBA 并按四次 B 返回世界地图，证明 checkpoint 可恢复且装备仍保持。
正式快照为 `artifacts/runtime-checkpoints/scenario-47-tool67-equipped-world-map.ss9`，SHA-256
为 `ecea4dc669f4e7d8a72d6c6e28fe456ec335c3c113c8c1426ed5e7eba225e601`；证据文件记录六段
输入链、当前 profile/二进制、clean guard 和 `67 → C3 → E4 → group 3` 绑定。下一步从
该快照自然推进到 battle 14，验证战斗槽复制、选择、对象到期和 handler；在此之前静态链
仍不计入 production 自然最终像素分母。
