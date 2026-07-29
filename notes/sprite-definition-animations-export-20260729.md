# 通用 Sprite 动画序列导出

日期：2026-07-29

## 结论

`0x0853F140` 的 43 组通用 Sprite definition/animation 指针对应 43 条自然加载器
使用的 animation 0。每个 animation table 的首个 `u32` 都指向
`definition_pointer + 4`，即 definition 内嵌的两条 4-byte 记录：

```text
s16 frame_index  s16 duration_ticks
0                1
-1               0
```

因此 43/43 项均为“显示 frame 0 一个 tick，然后停止”的单帧序列；没有循环、跳转、
空序列或越界 frame。frame 0 直接绑定
`artifacts/sprite-definition-assets-v2/` 中对应 ID 的 component 和 PNG，不再把
animation 指针误当作像素地址。

批量成果：

- `artifacts/sprite-definition-animations-v1/`
- `tools/export_sprite_definition_animations.py`
- `tools/verify_sprite_definition_animations.py`
- `tests/test_export_sprite_definition_animations.py`

产物共 87 个文件：1 份 manifest、43 份 timeline JSON、43 张编辑器 contact sheet；
总计 43 条 sequence、43 个 keyframe、43 个停止哨兵。

## Consumer 语义

- `0x0806298C..0x080629A0`：
  `animation_table[animation_id] + frame_cursor * 4` 选择当前记录；
- `0x08063256..0x0806327A`：每 tick 增加 task timer，与记录 `+2` 的
  `duration_ticks` 比较；到期后检查下一条记录的 `frame_index`；
- `0x08063284..0x080632D8`：下一条 `frame_index=-1` 时根据 task flags
  `0x30` 位选择停止、循环或 callback；
- `0x08080B08..0x08080B7C`：自然通用加载链传入 `0x48`，allocator 加入活动位后
  task flags 为 `0x49`；`0x49 & 0x30 == 0`，因此选择停止路径。

导出器和 verifier 都绑定上述四段 Thumb 切片的精确 SHA-256。verifier 不导入
导出器，直接从 ROM 重读 43 组 pair、animation table pointer、两条记录和现有
静态 Sprite manifest，并重建 43 张 contact sheet。更新 manifest 文件哈希后再篡改
duration 的测试仍会被语义检查拒绝。

## 边界

本成果闭合自然通用加载链的 animation 0、帧号、时长、哨兵和终止策略。它不证明：

- 其他调用者手工替换 task animation table 后的场景专用流；
- 加载后是否有场景系统覆盖规范 OBJ tile/palette；
- 业务语义名称或屏幕空间坐标。

这些边界不影响 43 组规范静态 Sprite 的编辑器播放。全过程仅离线读取 ROM 和现有
artifact，没有启动 mGBA 或 Butano。

## 验证

```bash
python3 tools/export_sprite_definition_animations.py
python3 tools/verify_sprite_definition_animations.py
python3 -m unittest \
  tests.test_export_sprite_definition_animations \
  tests.test_export_sprite_definition_runtime_chain
```

结果：43/43 entry、43/43 sequence、43/43 keyframe，`errors=[]`；相关 12 项测试通过。
