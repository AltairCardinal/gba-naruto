# 79 项战斗视觉运行时时间线（2026-07-29）

## 结论

`artifacts/battle-visual-runtime-timelines-v1/` 将现有 79 项无损 descriptor/message
目录推进为标准 consumer 的运行时模型：

- 75 项可播放 descriptor 各导出 106 个 linked update tick；
- 13、31、32、46 四项全零 sentinel 明确标为不可播放，不生成伪时间线；
- 75 张 `1440×190` RGBA contact sheet 包含标准 A＋消息 OBJ 布局，以及 linked
  tick 16、32、50、81、106 的 240×160 离线关键帧；
- callback 低字节 0、1、2、3、4、6、7、8 和主 updater 的 `0x0100` 分支在标准
  consumer 实际执行的 tick 1..106 内均已覆盖；
- 独立 verifier 不导入本导出器，从 ROM 和上游目录重算全部语义与 75 张 contact
  sheet 像素，验证结果为 `75 timelines、errors=[]`。
- 逐项 timeline 使用确定性单行紧凑 JSON，避免 75×106 tick 形成约 49.5 万行
  缩进文本，降低 Git、审查和模型上下文成本；顶层 manifest 仍保持可读缩进。

manifest SHA-256：
`7a3fd143f76a72f9f996029cef6aca218aa4bed5e2f2f16e63a6b7a76c55250b`。

## 标准 consumer 时序

`0x08099BFC` 的标准 consumer 先执行 A 层滚动 17 帧，再调用
`0x08098EDC`：

1. 消息 OBJ 前置等待 8 帧；
2. binding 槽按 6 帧节拍处理，slot 0 在前置等待后立即创建，随后精确等待
   `6×count-1` 帧；`0xFF` 槽不创建 OBJ、但仍占用槽时序；
3. OBJ 坐标为 `x = slot×24 - count×12 + 132`、`y = 16`；
4. OBJ palette bank 固定为 13；
5. 全部槽处理后保持 60 帧。

因此 linked installer 前的标准时长为 `84 + 6×binding_count` 帧。随后
`0x080990BC` 内部调用 updater 16 次，`0x08099BFC` 再调用 90 次，总计精确
106 个 linked tick。

## 新闭合的动态分支

### callback mode 2 / descriptor 0

- tick 32 捕获 easing 终点 `origin_x=72` 并进入 phase 1；
- tick 33..89 按 `origin+q`（奇数 q）或 `origin-q-2`（偶数 q）交替；
- tick 90 清零位置和 C scroll，把 D tilemap 与 C graphics 组合写入 C 路径，
  然后进入 `0xFF` 终止 phase；
- descriptor 0 的 D graphics 指针为零不是缺失资源：运行时只消费其 tilemap，
  因此 artifact 显式生成 `C_GFX_D_MAP` 合成层。

### callback mode 3 / descriptor 2

- tick 32..89 与 mode 2 共用横向震荡；
- tick 90 同样把 D tilemap 写入 C 路径，同时播放 cue 119、启用 D、置
  runtime flag bit 0；
- tick 91 起 D scroll 依次为 `+1,-2,+3,-4...` 像素；标准 consumer 在 tick
  106 停止 linked updater，此时为 `-16 px`。

### flags `0x0100` / descriptor 1、3

- 初始化时 C 禁用；
- tick 8 播放 cue 137；
- tick 17 启用 C 并开始 C-over-B alpha，系数为
  `k=trunc((tick-16)/4)`、`EVA=k`、`EVB=16-k`；
- tick 80 达到 `16/0`，tick 81 清除 `BLDCNT`，C 保持普通不混合显示；
- verifier 同时检查原始 `BLDALPHA`，包括 tick 81 的 `0x0010`。

## 证据边界

这是 ROM 代码驱动的确定性离线模型，不冒充 mGBA 像素等价。仍需在内存压力恢复后，
用少量代表性 descriptor 的已验证快照闭合：

- shadow register 的 VBlank 提交顺序；
- window mask 边缘；
- 代表性 mGBA golden frame。

当前 contact sheet 已可供编辑器预览、动作选择和批量回归使用，但上述三项完成前，
`runtime_pixel_equivalence_complete` 保持 `false`。

mode 3 handler 的理论 phase 20/30 在 tick 125 以后仍有定义，但标准 consumer 在
tick 106 后不再调用 linked updater。本成果只签发标准 consumer 的真实 1..106
范围，不把脱离该 consumer 的理论尾段计入运行时完成度。

## 复核

```sh
python3 -m unittest tests.test_export_battle_visual_runtime_timelines
python3 tools/export_battle_visual_runtime_timelines.py --root .
python3 tools/verify_battle_visual_runtime_timelines.py --root .
```

TDD 红阶段首先因导出模块不存在而失败；首次 CLI 集成又捕获直接执行脚本时仓库根目录
未进入模块搜索路径的问题。加入 CLI 集成测试并修复后，10 项测试全部通过；verifier
另有 manifest 来源、summary、关键 tick 和 intro 摘要的语义篡改拒绝覆盖。
