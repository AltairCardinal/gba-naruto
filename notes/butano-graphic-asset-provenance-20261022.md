# W3 动作 2 的 ③：1819 个图形资产按生成器归组，10 个 sidecar（2026-10-22）

日期：2026-10-22
工作树 `/Users/altair/github/gba-naruto`（分支 `codex/butano-foundation-research`）
配套：`docs/butano-wiring-roadmap.md`（W3 动作 2）、`notes/butano-content-bank-provenance-20261022.md`（②）

## 0. 结论

**图形资产已按生成器归组，每组一个 sidecar；归不进去的 198 个**明列在开放清单里**，
没有被猜进任何一组。

| 项 | 值 |
| --- | ---: |
| 图形资产（去掉 `.DS_Store` 这类点文件） | **1818** |
| **已归组（有逐条证据）** | **1807**（**99.4%**） |
| 生成器组（每组一个 sidecar） | **16** |
| 歧义（两个生成器同样特异） | 11 |
| 无归属（没有任何规则能解释） | **0** |

收据 `artifacts/butano-graphic-asset-provenance-v1/`
工具 `tools/butano/annotate_graphic_asset_provenance.py`（幂等）
门禁 `tests/test_graphic_asset_provenance.py`（**5 项全绿**）

## 1. 归组用四条**可测量**的规则，每条都记下它判定了哪个资产

| 规则 | 判据 | 命中 |
| --- | --- | ---: |
| `literal` | 生成器源码里**直接出现**该资产名 | 218 |
| `pattern` | 生成器源码里的 **f-string / %-格式名**（含**无扩展名的 C++ 符号名**）转成正则后匹配 | 302 |
| `constant` | 资产名以生成器源码里的 **snake_case 常量**开头（`symbol_prefix="battle_ninja_tool_bomb_projectile"`） | 128 |
| `prefix` | 资产名以**生成器自己的名字**（去 `generate_`/`export_`/`butano_` 前缀）开头 | 1260 |

⇒ **消歧按特异度**：多个生成器都命中时，`literal` > `pattern`/`constant` > `prefix`
（**具体规则压过宽泛规则**）⇒ 11 个真歧义留在开放清单里。

⇒ sidecar 里每个资产都带 `attribution_rules`（哪个规则判的它），
**不是「大概是它生成的」**。

## 2. 三条被**否决**的规则（试过，留档）

| 试过的规则 | 结果 | 处置 |
| --- | --- | --- |
| 「资产名里任一 token 出现在某个生成器名里」 | 命中 1818/1819，但**唯一命中 0 个** | 否决：等于没归 |
| 「资产名的固定片段（`_map_chunk_` 之类）出现在生成器源码里」 | 唯一命中从 1621 掉到 106，歧义涨到 1712 | **否决**：`_character_` 这类片段在很多生成器里都有 ⇒ 规则在猜 |
| 「把两个 f-string 拼起来当名字模式」 | 两个片段都带占位符 ⇒ 拼出来的正则**重建不出**名字 | 否决：数学上不成立 |
| 「模式只按扩展名筛」 | 地图块的名字是**无扩展名的 C++ 符号名** ⇒ 被过滤掉，159 个资产无归属 | 修：符号名模式也收 |

⇒ **宁可 89% 逐条有证据 + 11% 明列缺口，也不要 100% 靠猜。**
「猜错的归属」比「明写的缺口」危险：前者会让接线登记表说谎。

## 3. 16 个组（按资产数，前 6）

| 生成器 | 资产数 | 规则 |
| --- | ---: | --- |
| `tools/generate_butano_battle_unit_content.py` | 1192 | prefix |
| `tools/butano/generate_scenario_41_assets.py` | 185 | literal 37 / pattern 148 |
| `tools/generate_butano_battle_runtime_assets.py` | 148 | literal 3 / pattern 145 |
| `tools/butano/generate_battle_effect_sequence.py` | 122 | constant |
| `tools/butano/generate_battle_ui_assets.py` | 109 | literal 95 / pattern 12 / prefix 2 |
| `tools/generate_butano_battle_identity_content.py` | 18 | literal |

⇒ **16 个生成器解释了 99.4% 的图形资产**；其余 50 个候选生成器没有产出落在这里的资产。

## 4. 11 个待逐生成器声明的歧义（开放清单）

**0 个无归属**；剩下的 **11 个歧义**（两个生成器同样特异，如
`battle_action_16_movie_actor.bmp` 同时被 `generate_battle_action_16_movie.py`
和 `generate_butano_battle_action_content.py` 命中）逐条列在
`provenance.json` 的 `ambiguous` 里。

⇒ 收口办法：**让这两个生成器各自声明自己的产物**（像 `GENERATED_PRODUCTS` 那样），
声明后 100% 归组是机械的 ⇒ 属逐生成器改造。
（消歧办法试过两条，都不成立，见 §6。）

## 5. 图形资产的**逆向来源**登记：3 个已声明，13 个缺声明

归组只回答「谁产的」，不回答「消费了哪个逆向族」。后者其实**已经有机器可读的声明**：
消费逆向成果的生成器用树自己的合同声明——

```python
PROVENANCE = provenance_block(
    sources=(("rom-...-v1", "<manifest sha256>"),), roms=(...))
```

⇒ sidecar 改成**读这个声明**（AST 解析），不再 grep 源码：

| 生成器 | 声明的逆向族 |
| --- | --- |
| `generate_butano_battle_identity_content.py` | `rom-fixed-consumer-text-inventory-v1` |
| `generate_butano_battle_presentation_glyphs.py` | `dialogue-font-v2` |
| `generate_butano_movegrid_overlay_assets.py` | `rom-pointer-lz77-inventory-v1` |

⇒ **3 / 16 已声明，13 个未声明**（收据的 `declaration_gap` 逐个列出），
门禁钉住「声明的族必须在索引里」与「缺口清单与已声明集合**恰好互补**」。

⇒⇒ **收口办法与归组一样**：让这 13 个生成器各自补一个 `provenance_block` 声明。

## 6. 11 个歧义：试过的两条消歧办法都不成立

歧义只剩 11 个（8 个 `battle_action_16_movie_*` + `battle_ui_result_panel.bmp` +
`battle_unit_visual_catalog.json` + `scenario_41_map.bmp`）。

| 消歧办法 | 结果 | 处置 |
| --- | --- | --- |
| **mtime 聚簇**（同一轮生成的资产共享分钟） | 电影那一组**两个候选都在同一分钟**跑过（`2026-07-27 01:06`）⇒ 不可分 | 规则保留（对别的情形有效），本组不生效 |
| **定向重跑候选生成器**看谁真产出 | 电影工具需要 `build/original-fire-presentation-trace-20260726-9*`，**已被清理**⇒ 跑不了 | 不可行，留在清单 |

⇒ ⇒ **11 个资产明列在开放清单里**，归它们的生成器自己声明产物后即可机械收口。

## 7. 边界声明

- sidecar 里的 `reverse_family` **几乎都是空的**：只有 2 个生成器在源码里声明了
  `reverse-source`。⇒ **图形资产的逆向来源本身还没有登记**，
  sidecar 如实写「the generator declares no reverse-source family」。
- 本轮**没有改任何生成器、也没有改任何图形资产**；只新增了收据与 sidecar。
- 归组是**按名字**判的，不是按运行记录判的 ⇒ 名字像的资产可能被归错，
  但每条都记了判定规则，可复核。
- W3 动作 2 的 ②（内容库来源）见 `notes/butano-content-bank-provenance-20261022.md`。

## 8. 相关

- `docs/butano-wiring-roadmap.md`（W3 动作 2）
- `tools/butano/annotate_graphic_asset_provenance.py`、
  `tests/test_graphic_asset_provenance.py`、
  `artifacts/butano-graphic-asset-provenance-v1/`
