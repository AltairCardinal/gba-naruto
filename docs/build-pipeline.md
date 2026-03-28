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

### `dialogue`

从高层对白内容文件导入。

当前实现：

- 文本银行：`sequel/content/text/dialogue-bank.json`
- 内容文件：`sequel/content/text/dialogue-patches.json`
- 导入器：`tools/import_dialogue.py`

当前能力：

- 支持 `cp932`
- 支持固定偏移、固定字节长度的对白入口
- 已复现 `0x00076D` 的 `試験` proof-of-write 补丁

当前限制：

- 仍依赖已知固定入口位点
- 还不支持指针重定向和变长扩容

## 内容校验接口

这些接口当前先负责“内容验证 + 摘要输出”，还未做真实 ROM 写回：

- 地图：`tools/import_map.py`
- 战斗配置：`tools/import_battle_config.py`

## 常用命令

```bash
python3 tools/build_mod.py
python3 tools/import_dialogue.py
python3 tools/import_map.py sequel/content/maps/episode-01-mountain-pass.json
python3 tools/import_battle_config.py
```

## 当前状态

已完成：

- `bytes` 补丁构建
- `dialogue` 高层导入补丁构建
- 构建报告生成

未完成：

- `map` 真正写回 ROM
- `battle_config` 真正写回 ROM
- `pointer_redirect`
- 自动从章节脚本生成流程补丁
