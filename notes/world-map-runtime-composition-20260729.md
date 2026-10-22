# 世界地图 page 0 运行时合成（2026-07-29）

## 结论

从已接纳的 `scenario-42-postbattle-world-map.ss9` 直接载入，没有重走剧情；受守卫
mGBA 在首帧完成 IO/VRAM/OAM/PRAM 与截图抓取，并由 success marker 在约一秒内结束
守卫流程。抓取画面是 page 0 世界地图，左上显示地点标签，右侧显示选择菜单，没有发生
mGBA 崩溃。Guard 的 `completed` 结果遵循 owned-tree 停止后才写 summary 的守卫契约，
但本 capture 没有另存独立的退出后 PGID 进程列表，因此不签发 `pgid_clean` 原始字段。

运行时证据闭合了 page 0 的最终背景绑定、标签排布/调色板/坐标和当前选择光标：

- `DISPCNT=0x1940`：启用 BG0、BG3 和 OBJ。
- BG0CNT=`0x0086`：priority 2、charblock 1、screenblock 0、8bpp、scroll `(0,0)`。
  VRAM `0x06004000` 的 32 KiB gfx 与静态 page 0 完全一致；PRAM 前 320 bytes 与其
  160 色 palette 完全一致；screenblock 0 的 20 行各有前 30 entries 与共享
  30×20 tilemap 完全一致。
- BG3CNT=`0x030C`：priority 0、charblock 3、screenblock 3、4bpp。page 0 四条
  字形记录按 runtime base index 8 展开到 tiles 0..7；screenblock 3 在
  `(x=4..7,y=1)` 使用 tiles `0,2,4,6`，下一行使用 `1,3,5,7`。这决定了每个源记录
  的两个 8×8 半块是上下排列，最终标签为 `(32,8)` 处的 32×16、四个 8×16 字形，
  不是首次静态假设的 64×8。
- 标签 tilemap 使用 palette bank 14，tile 内索引 8..11 对应全局 BG palette
  indices 232..235：`0x6BDC`、`0x4ED5`、`0x35EE`、`0x1D07`。
- OAM 只有一个活动对象：ID 0，位置 `(184,8)`，16×8，tile 1014，priority 0，
  palette bank 15；它是当前选择光标/标记的唯一 OBJ 层。

## 输入、守卫与原始证据

- 输入快照：
  `artifacts/runtime-checkpoints/scenario-42-postbattle-world-map.ss9`
- 输入 SHA-256：
  `35fce6be208aa50044bdaa2232eab5986d9ea76340bc08c68b107f34b5a5b5a1`
- 原始 capture：
  `artifacts/world-map-gpu-captures/s42-page0/`
- 派生 manifest：
  `artifacts/world-map-runtime-v1/manifest.json`
- 派生 manifest SHA-256：
  `83a49eb6b8c65e0c29c3b47edf7217313ce34e96fbe40a10efed612b9643cda7`
- Guard：`reason=completed`、`exit_code=0`、`completion_trigger=success-marker`、
  `degraded=false`、`protection_backend=posix-process-group`。

原始 capture 保留 `frame.png`、四个 GPU memory domain、Lua audit 和 guard JSON，
所有文件均由派生 manifest 逐项绑定 SHA-256。

## 可复现命令

抓取命令使用 `tools/run_guarded.py` 的同一 heavy lock、2 GiB 启动内存门槛、512 MiB
owned-tree RSS 上限和 success marker。后续一般不应重复抓 page 0；直接复核已持久化
capture：

```sh
python3 tools/export_world_map_runtime.py \
  --root . \
  --capture-dir artifacts/world-map-gpu-captures/s42-page0 \
  --output-dir artifacts/world-map-runtime-v1
python3 tools/verify_world_map_runtime.py \
  --root . \
  --capture-dir artifacts/world-map-gpu-captures/s42-page0 \
  --artifact-dir artifacts/world-map-runtime-v1
python3 -m unittest tests.test_export_world_map_runtime -v
```

独立 verifier 不导入 exporter 或共享 helper；它重新解析寄存器、screenblock、4bpp
tile 数据、PRAM 和 OAM，并重新从 ROM 字形源生成 runtime tiles。篡改派生 manifest
或任一原始 GPU domain 都会拒绝。

## 边界与下一步

本证据只覆盖 page 0 和捕获帧的当前选择状态，不证明：

- page 1/2 的运行时背景、标签 palette/坐标和光标是否完全共用同一配置；
- 左右选择时 index、标签、背景和 OAM 的切换帧时序；
- 不同章节的 available-count / unlock state 对菜单项和目的地的影响。

离线检查现有 scenario 42/44/45/46/47/48 accepted 世界地图快照后，六个快照均为
`selected_index=0`、`available_count=1`，LEFT/RIGHT 不可能到达 page 1/2。
因此不得对这些快照重复发送无效输入。下一步需要先取得 `available_count>1` 的自然
解锁快照，或建立单字段、可回滚且有零输入对照的状态补丁，再复用同一 GPU 抓取链验证
page 1/2 与选择切换时序；不重新回放场景 42。完成时系统可用内存 65%，本轮没有
mGBA 崩溃。
