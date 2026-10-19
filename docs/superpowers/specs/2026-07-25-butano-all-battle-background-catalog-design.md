# Butano 全战斗背景目录设计

## 目标

把 47 张原作战斗地图全部从 ROM 生成到本地，并建立 battle ID 到像素尺寸、分块资源和
world origin 的唯一目录。后续接入关卡时只提供 battle ID、variant 与章节入口，不再修改
renderer、复制背景配置或借用其他关卡 BMP。

## 审计结论

- 47 张地图共有 23 种像素尺寸，原始 indexed 像素总量 6,221,312。
- 按 512×512 chunk、240px viewport 规划后共 49 块。
- 仅 battle 0 需要 origins `[0,224]`，battle 11 需要 `[0,32]`；其余均为 origin 0 单块。
- 最大高度 512px，不需要纵向分块。
- 当前 ROM 为 5.3MB，GBA ROM 上限 32MB；最终仍必须由 ARM 链接结果而非估算签发容量。

## 生成产物

`generate_all_map_chunks()` 遍历 battle 0..46：

```text
graphics/battle_00_map_chunk_0.bmp/.json
graphics/battle_00_map_chunk_1.bmp/.json
...
graphics/battle_46_map_chunk_0.bmp/.json
graphics/battle_00_map_chunks.json
...
graphics/battle_46_map_chunks.json
graphics/battle_background_catalog.json
game/include/konoha/generated_battle_background_content.h
```

每关 manifest 复用已验收的 chunk 协议。总目录保存：

- battle ID；
- 全图 active size；
- chunk origins/count；
- 对应每关 manifest 文件名；
- 四类 ROM source SHA-256。

C++ 生成表包含 47 个 `battle_background_content_entry`。每条持有固定容量的
`bn::regular_bg_item*`、origins、像素宽高与 chunk count，并提供失败关闭的
`generated_battle_background_entry(battle_id)`。

## 运行时数据流

```text
battle_runtime_scene_config(battle_id, variant, title, flags)
        |
        +--> generated_battle_content_entry
        |       scenario / logical map / conditions
        |
        +--> generated_battle_background_entry
                pixel size / BG items / origins
                        |
                        v
                battle_background_stream
```

wrapper 不保存背景 item、像素尺寸或 origins。逻辑内容和视觉内容分别查询，但必须满足：

- background battle ID 等于 content battle ID；
- `pixel_width == scenario.grid_width * 32`；
- `pixel_height == scenario.grid_height * 16`；
- chunk 配置通过 stream `prepare()`。

任一不匹配都在部署画面前返回，不显示错误地图。

## 复用与边界

1. 直接复用 ROM map reconstruction、chunk planner、per-map manifest 和 background stream。
2. 总目录是新旧关卡共用能力，不另建 battle 11 专用表。
3. 旧 `scenario_41_clean_map`、`battle_09_clean_map` 暂保留给 legacy/custom scene 与历史
   证据；通用 renderer 改用统一 `battle_XX_map_chunk_0`。
4. 47 张背景可查询不等于 47 场都已提供章节入口、部署队伍或特殊脚本。
5. battle 0 三个 variant 为空，资源仍生成以证明最大 736px 地图可被目录描述，但不会伪造
   可玩编队。

## 错误与资源策略

- 生成期间任一 battle row 重建、尺寸、palette 或输出失败：整个命令失败，不写“完整目录”
  完成标记。
- 总目录/生成头必须确定性；连续生成 hash 不变。
- 49 张 BG 若使 converter、VRAM、ROM 32MB 或链接失败，记录精确资源并调整压缩/按章节
  分组，不能删地图或改用截图。
- 运行时一次只载入当前 chunk；目录中的其他资源在 ROM，不同时占 VRAM。
- 自动路线静音，不签发音频听感。

## 验收

- Python RED/GREEN 验证 47 entries、49 chunks、battle 0/11 origins、尺寸、hash 和生成头。
- source wiring RED/GREEN 禁止 wrapper 引用具体 `bn::regular_bg_items::*map*`。
- ARM 构建检查 49 项 converter、最终 ROM 大小、section 和 warning/error。
- battle 11 `0→1→0`、battle 9、43、41 mGBA 路线全部回归。
- 文档明确“背景目录完成”与“47 关完整可玩”之间的边界。

## 实施结果

2026-07-25 已按本设计落地：

- 47 份 per-map manifest、49 组 BMP/JSON 和唯一总目录均由 ROM 确定性生成；
- 通用 renderer 不再直接 include 或选择任何 `battle_XX_map_chunk_*`，而是按 battle ID
  查询 `generated_battle_background_entry()`；
- 49 项 Butano regular BG 全部通过转换和 ARM 链接，ROM 为 6,921,928 字节，未接近
  32MB 上限；一次只把当前分块装入 VRAM；
- battle 11 遥测确认分块序列 `[0,1,0]`，battle 9、43 和 legacy scenario 41 均完成
  既有运行路线；
- 最终 section 为 `.iwram` 8,840、IWRAM `.bss` 2,168、EWRAM `.ewram` 224、
  `.sbss` 129,620，总计 16,233,173 字节。

该结果把“视觉地图内容”从场景代码中抽成了可查询内容层，仍不把空 variant、动态部署、
章节脚本、对象行为、角色专属 sprite 或逐技能演出伪装成已实现关卡。
