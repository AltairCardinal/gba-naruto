# 木叶战记续作 Roadmap

## 目标

把当前仓库从“已建立续作工作区和逆向基础”推进到“可以持续生产续作内容并稳定回写 ROM”的状态。

这份 roadmap 只写接下来真正应该做的事，不重复已经完成的工作。

## 当前基线

已具备：

- 项目记忆规则和工作区结构
- 续作内容目录 `sequel/content/`
- ROM 构建入口 `tools/build_mod.py`
- 可重复生成开发 ROM
- 高层 `dialogue` 导入补丁已接入构建流程
- 地图/战斗配置已进入统一内容校验接口
- 无头 `mGBA` 自动导航、截图、OCR
- 对白渲染链路的关键结论：
  - `BG3` 是对白层
  - `WRAM 0x00A900-0x00AA4A` 是对白 tilemap 工作缓冲候选
  - `VRAM 0x1800+` 是对应 screen block
  - `VRAM 0x2000+` 更像字形上传区
  - `WRAM` 稳定写入点已定位到 `0x08066D74`
  - `VRAM glyph` 稳定写入点已定位到 `0x08065F50`
  - `VRAM tilemap` 刷新更像 DMA/system copy 到 `0x06001B00+`
  - `0x08065EB8` 已识别为强字形展开候选函数
  - `0x08065F84` / `0x080894DE` 已识别为更高价值的上层文本渲染入口

未具备：

- 可变长真实对白导入格式
- 章节脚本导入格式
- 地图导入格式
- 角色/技能高层配置格式
- `0x080894DE` 所在上层流程的状态结构与数据来源

## 总体路线

按四条线并行推进：

1. 渲染与脚本逆向
2. 内容源稿生产
3. ROM 补丁流水线扩展
4. 垂直切片集成验证

其中优先级最高的是第 1 条和第 3 条，因为它们决定“续作内容能不能真正进 ROM”。

---

## Phase 1: 拿下对白写入路径

当前状态：已完成。

已完成内容：

- 无头静音 watchpoint 流程已稳定复跑
- `WRAM 0x0200A900-0x0200AA4A` 写入者已稳定命中 `0x08066D74`
- `VRAM 0x06002000-0x06002800` 字形上传写入者已稳定命中 `0x08065F50`
- `VRAM 0x06001B00+` 已确认更像 `BG3` tilemap 的 DMA/system copy 目标区
- 相关结果、脚本和汇总都已落盘

详见：

- `notes/dialogue-write-path.md`
- `notes/dialogue-writer-addresses.md`
- `notes/dialogue-function-analysis.md`

### 目标

确认是谁在写：

- `WRAM 0x00A900-0x00AA4A`
- `VRAM 0x1800+`
- `VRAM 0x2000+`

### 原因

对白系统是目前最接近“真正可扩展内容开发”的入口。只要拿到这条链路，就有机会做：

- 新对白回写
- 新剧情事件
- 章节前后演出

### 任务

1. 稳定化脚本级 watchpoint 或等效调试方案
2. 分别针对 `WRAM 0xA900+` 和 `VRAM 0x2000+` 捕获写入 PC
3. 记录命中函数附近的调用链
4. 判断写入前的数据来源是：
   - ROM 直接文本块
   - 自定义编码缓冲
   - 压缩块解码结果

### 交付物

- `notes/dialogue-write-path.md`
- `notes/dialogue-writer-addresses.md`
- 至少一个可重复命中的调试脚本

### 完成标准

- 至少拿到一个稳定的写入者地址
- 能解释“tilemap 更新”和“glyph 上传”分别由哪段逻辑负责

---

## Phase 2: 拿下对白数据入口

当前状态：进行中。

已完成内容：

- `0x08066D14` 已确认是 `WRAM` tilemap 半字写函数
- `0x08065EB8` 已确认是字形展开候选函数
- `0x08065F84` 已确认是连接字形生成与 tilemap 放置的包装层
- `0x080894DE` 已确认是非局部上层调用点，值得继续上追
- `0x0808947C-0x080894F8` 已确认是更高层的多项渲染循环
- `sb` 已收敛到 `0x02002880` 这块 RAM 工作结构
- `0x080886E8` / `0x08088718` 已显示出对 `0x02022E30` 一带 RAM 记录的查询关系
- `0x02002880` / `0x02022E30` 的快照观察已表明它们更像页级渲染状态和记录区，而不像直接文本源
- `0x02002880` / `0x02002E30` 的运行时写入已确认共享同一上游调用链，锚点落在 `0x08096176-0x08096212`
- 静态调用与局部反汇编资产已建立
- 高层 `dialogue` 导入补丁已通过固定入口位点打通构建闭环
- `0x08096168` caller family 已做第一轮静态分层：
  - `0x08077D0E` / `0x08089B36` / `0x0809159C` / `0x08093842` 更像大块 panel/window builder
  - `0x0809678A` / `0x080968A0` / `0x0809698E` 更像紧凑 record-state transition helper
- 运行时 caller trace 已确认：开场新游戏流程在这组 caller 中实际命中的是 `0x080968A0`
- `0x080968A0` 两次命中都带有相同上游 `lr=0x08096633`

当前缺口：

- `0x080894DE` 所在上层函数的边界、状态结构、数据来源
- `0x02002880` 结构及其 `+0x16` / `+0x82` / `+0x96` 区域含义
- `0x02022E30` 记录区与对白/角色/槽位的关系
- 谁负责把更上游的脚本/文本数据写进这两块 RAM 结构
- `0x08096176-0x08096212` 如何从更上游状态组装这两块 RAM
- 哪条脚本/UI 路径实际驱动了开场对白使用的那一支调用链
- `0x080968A0` 上游 `0x08096633` 所在函数的真实边界和来源

详见：

- `notes/dialogue-function-analysis.md`
- `notes/disasm-080894DE.txt`
- `notes/calls-08065EB8.txt`

### 目标

从“知道怎么显示”推进到“知道从哪里取文本”。

### 任务

1. 从写入者反推对白源数据结构
2. 判断文本是否：
   - 直接块存储
   - 指针表存储
   - 脚本命令流内嵌
3. 做最小对白替换实验
4. 把对白改动接入构建流水线

### 交付物

- `notes/dialogue-format.md`
- `tools/import_dialogue.py` 或同类工具
- `sequel/patches/manifest.json` 中出现第一类“高层对白导入”条目

当前已交付：

- `tools/import_dialogue.py`
- `sequel/content/text/dialogue-bank.json`
- `sequel/content/text/dialogue-patches.json`
- `sequel/patches/manifest.json` 中的 `dialogue` 条目

### 完成标准

- 能从项目内容文件生成至少 1 段实际对白改动
- 不再只依赖同长度字节补丁

当前进度：

- 已达到“能从项目内容文件生成至少 1 段实际对白改动”
- 尚未达到“摆脱固定已知入口位点”
- 开场对白的上层 live branch 已进一步收敛到 `0x080968A0`

---

## Phase 3: 拿下章节流程入口

### 目标

确认 1 章完整流程的入口、结束和跳转逻辑。

### 任务

1. 找出章节开始点
2. 找出胜利条件、失败条件、战后跳转
3. 识别章节编号或流程脚本入口
4. 做一次最小流程改动：
   - 改一句战后对白
   - 改一次跳转目标
   - 或改一条胜利判定

### 交付物

- `notes/chapter-flow-format.md`
- `notes/chapter-entry-points.md`
- 最小流程改动实验记录

### 完成标准

- 能完整描述一章从进入到结束的控制路径

---

## Phase 4: 拿下地图格式

当前状态：已建立内容接口，ROM 写回未完成。

### 目标

确定战斗地图的导入导出闭环。

### 任务

1. 定位地图 tilemap 数据
2. 定位出生点、事件区、障碍、目标点
3. 判断地图和战斗配置是合并还是分离
4. 做一张地图最小改动实验

### 交付物

- `notes/map-format.md`
- `notes/map-addresses.md`
- `tools/extract_map.py`
- `tools/import_map.py`

当前已交付：

- `tools/import_map.py`
- `notes/map-import-report.json`

### 完成标准

- 能对一张战斗地图做稳定修改并在模拟器中验证

---

## Phase 5: 拿下战斗配置格式

当前状态：已建立内容接口，ROM 写回未完成。

### 目标

确定角色、敌人、技能、阵营、出生配置的主要表结构。

### 任务

1. 定位角色基础数值
2. 定位敌方战斗配置
3. 定位技能 ID、消耗、范围或效果索引
4. 做最小战斗配置改动实验

### 交付物

- `notes/battle-config-format.md`
- `notes/unit-skill-addresses.md`
- `tools/import_battle_config.py`

当前已交付：

- `tools/import_battle_config.py`
- `notes/battle-config-report.json`

### 完成标准

- 能稳定修改一场战斗中的单位、敌人或技能配置

---

## Phase 6: 扩展构建流水线

当前状态：已部分完成。

### 目标

把已经拿下的高层格式全部接入统一构建入口。

### 任务

1. 扩展 `tools/build_mod.py`
2. 支持补丁类型从 `bytes` 扩展到：
   - `dialogue`
   - `map`
   - `battle_config`
   - `pointer_redirect`
3. 增加构建前校验
4. 增加构建后报告

### 交付物

- `tools/build_mod.py` 扩展版
- `docs/build-pipeline.md`
- 更完整的 `build/naruto-sequel-build-report.json`

当前已交付：

- `tools/build_mod.py` 已支持 `dialogue`
- `docs/build-pipeline.md`
- `build/naruto-sequel-build-report.json` 已记录高层 `dialogue` 补丁

### 完成标准

- 不再需要手工做十六进制试验来集成新内容

当前进度：

- 对 `dialogue` 已基本达到
- 对 `map` / `battle_config` / `pointer_redirect` 尚未达到

---

## Phase 7: 续作第一章垂直切片

当前状态：内容源稿已具备基础骨架，ROM 集成未完成。

### 目标

把 `episode-01` 真正变成一章可玩切片。

### 任务

1. 完成 `episode-01` 的剧情源稿
2. 完成地图草案
3. 完成战斗配置草案
4. 至少导入：
   - 1 段新对白
   - 1 处战斗配置改动
   - 1 个地图或流程改动
5. 生成一版可测试 ROM

### 交付物

- `sequel/content/story/episode-01.json` 完整版
- `sequel/content/text/episode-01-dialogue.md` 扩展版
- 切片测试 ROM
- 切片测试记录

### 完成标准

- 新内容不再只是源稿，而是实际进入 ROM 并可验证

---

## Phase 8: 工具链化与规模化内容生产

### 目标

进入真正的续作开发阶段，而不是单次试验阶段。

### 任务

1. 固定内容编写规范
2. 固定补丁清单结构
3. 固定构建流程
4. 增加更多章节模板
5. 增加测试 checklist

### 交付物

- `docs/content-pipeline.md`
- `docs/testing-checklist.md`
- 更多 `sequel/content/` 章节草案

### 完成标准

- 新章节开发不再依赖重新探索整个 ROM

---

## 当前推荐顺序

按投入产出比，建议严格按下面顺序继续：

1. `Phase 1` 对白写入路径
2. `Phase 2` 对白数据入口
3. `Phase 6` 构建流水线扩展的对白部分
4. `Phase 3` 章节流程入口
5. `Phase 4` 地图格式
6. `Phase 5` 战斗配置格式
7. `Phase 7` 第一章垂直切片

## 不该现在做的事

1. 不要现在就写大量长篇剧情，因为还没拿到真实导入格式
2. 不要现在就做多章地图生产，因为地图格式还没拿下
3. 不要把大规模十六进制手改当正式开发流程
4. 不要把不落盘的聊天结论当项目记忆

## 本周最具体的下一步

最该优先完成的是这 3 件事：

1. 稳定一个能抓 `WRAM 0xA900+` 写入者的调试方案
2. 把对白导入格式拿到最小闭环
3. 把 `episode-01` 的剧情源稿扩成可导入结构
