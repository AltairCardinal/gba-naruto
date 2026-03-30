# 构建流水线

## 目标

把续作内容文件、ROM 补丁定义和最终开发 ROM 构建串成一个可重复执行的最小流水线。

## 当前入口

- 项目元数据：`sequel/project.json`
- 补丁清单：`sequel/patches/manifest.json`
- 主构建脚本：`tools/build_mod.py`

## 已支持的补丁类型

### `bytes`

直接按偏移写入固定字节。

```json
{
  "id": "my_patch",
  "type": "bytes",
  "offset": 1901,
  "before_hex": "89df95d1",
  "after_hex": "8e8e8cb1"
}
```

### `dialogue`

从高层对白内容文件导入。同长度替换：直接将编码后的文本（含 null 填充）写入 ROM 偏移。

**格式**：`import_dialogue.py` 读取 `bank`（定义 ROM 源位置）和 `content`（定义新文本），生成补丁。

```json
{
  "id": "my_dialogue",
  "type": "dialogue",
  "bank": "sequel/content/text/dialogue-bank.json",
  "content": "sequel/content/text/dialogue-patches.json",
  "entry_id": "group0.main"
}
```

支持变长文本（需在 bank 中配置 `redirect_offset` 指向已验证的空闲 ROM 区域）。

### `pointer_redirect`

更新指针表条目，指向新的文本位置。用于变长对话导入。

```json
{
  "id": "ptr_redirect.group0.main",
  "type": "pointer_redirect",
  "pointer_table_offset": 4594920,
  "expected_pointer_hex": "14944508",
  "new_pointer_hex": "148C6628"
}
```

### `map`

从地图规格文件生成 ROM 补丁。当 `patch_ready: true` 且包含 `patches` 数组时触发。

```json
{
  "id": "map.episode01.mountain_pass",
  "type": "map",
  "spec": "sequel/content/maps/episode-01-mountain-pass.json"
}
```

**当前状态**：仅在 `patch_ready: true` 时生效，否则静默跳过。地图格式逆向完成后填充 `patches` 数组。

### `battle_config`

从单位/剧情规格生成 ROM 补丁。当 `patch_ready: true` 时触发。

```json
{
  "id": "battle.episode01.slice",
  "type": "battle_config",
  "units": "sequel/content/units/sequel-units.json",
  "story": "sequel/content/story/episode-01.json"
}
```

**当前状态**：同上，战斗配置格式逆向完成后填充 `patches` 数组。

## 当前内容文件

| 文件 | 用途 |
|------|------|
| `sequel/content/text/dialogue-bank.json` | ROM 对话文本源位置定义 |
| `sequel/content/text/dialogue-patches.json` | 新对话内容 |
| `sequel/content/story/episode-01.json` | 第一章剧情骨架 |
| `sequel/content/maps/episode-01-mountain-pass.json` | 地图规格（draft） |
| `sequel/content/units/sequel-units.json` | 角色/敌方单位规格 |

## 已验证补丁

当前开发 ROM 包含以下已验证补丁：

| Entry ID | 替换前 | 替换后 | 策略 |
|----------|--------|--------|------|
| `proof.menu.same_length_00076d` | 過篇 | 試験 | 同长度 |
| `group0.main` | 委渉留夘笹戟嗚妣著畔問潰誼↵米休七机誌噐？ | 木葉村国境に異変あり小隊が調査に向かう。 | 同长度（null 填充） |
| `group1.main` | 繁岔妣文嚶奉誼憤搾↵儡參誼壷壘熟扮坦丁悛？ | 忍刀の残党が附近に潜伏警戒せよ。 | 同长度（null 填充） |
| `group2.main` | 著畔立駒愧丈掘猪誼↵囹汲肘誼奉熟扮坦丁悛？ | 輸送巻物守るべし。敵の狙いは明白だ。 | 同长度（null 填充） |

## 常用命令

```bash
python3 tools/build_mod.py
python3 tools/import_dialogue.py
python3 tools/import_dialogue.py --bank sequel/content/text/dialogue-bank.json --content sequel/content/text/dialogue-patches.json
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
python3 tools/import_battle_config.py
```

## 当前状态

已完成：

- `bytes` 补丁构建
- `dialogue` 高层导入补丁构建（同长度 + 变长 redirect 框架）
- `pointer_redirect` 补丁类型
- `map` / `battle_config` 补丁类型入口（待格式逆向后填充）
- 构建报告生成（`build/naruto-sequel-build-report.json`）

未完成：

- 地图格式逆向 + `import_map.py` patch 生成
- 战斗配置格式逆向 + `import_battle_config.py` patch 生成
- 变长文本 redirect 需要已验证的空闲 ROM 区域
