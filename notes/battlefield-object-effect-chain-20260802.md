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
- 有效单位在 `unit+0xB0` 声明范围内实际装备的忍具 67–72。

2026-08-02 经 `tools/run_guarded.py` 扫描 `artifacts/` 的 183 份和 `build/` 的 981 份
存档，共 1,164 份，全部解析成功但命中 0；修正输入 fail-closed 后的复跑 guard 峰值
tree RSS 为 20.16015625 MiB。
因此当前没有可直接恢复的自然种子，本轮未启动 mGBA，也不把静态链或既有受控
single-pixel 证据计入 production 自然最终像素分母。下一步需要从原版内容中定位忍具
67–72 的取得/装备路径，或建立明确标为受控的装备前置后，再以一次自然 UI 选择和到期
命中闭合运行时链。
