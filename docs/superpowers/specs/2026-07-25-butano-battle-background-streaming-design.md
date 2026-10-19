# Butano 战斗背景分块流送设计

## 目标

用原作 ROM row 11 的 544×480 地图证明：超过 GBA regular background 512px 上限的
战场仍能由同一可见战斗运行时显示、滚动和战斗，不需要裁掉地图、缩放逻辑格或复用其他
关卡背景。

本里程碑建立后续关卡可复用的分块协议和运行时切换器。它不把 battle 11 的通用角色 sprite
误报为最终角色美术，也不补写尚未证实的章节对白。

## 样本与约束

- 47 张地图中，battle 0 为 23×32 但三个 variant 都为空；battle 11 是唯一非空且宽度
  超过 16 格的样本。
- battle 11 的逻辑尺寸是 17×30，视觉尺寸是 544×480；variant 0 为角色 1/2/3 对
  角色 34/35。
- GBA regular background 单张最大 512×512；当前 renderer 又以 512px 地图中心建立
  世界坐标。
- battle 11 的 palette 和像素必须来自 `rom/base.gba:map-row-11`，并保存 tile graphics、
  palette、layout 和 metatile attribute 哈希。
- 分块切换不能改变领域位置、cursor、camera、单位 sprite 或碰撞坐标。
- VRAM 不能同时常驻两份大背景；切换使用 Butano `regular_bg_ptr::set_item()`，它先释放
  旧资源再建立新资源。

## 资源协议

生成器提供 `generate_map_chunks()`：

1. 从 `reconstruct_map(rom, battle_id)` 得到完整 indexed 像素和平面 palette；
2. 每个分块固定输出 512×512 indexed BMP；
3. 第一块 origin 为 0，最后一块右对齐地图末端；相邻 origin 步长最多
   `512 - viewport_width`，保证 240px 可视窗始终能完全落在某一块内；
4. 不足 512 的右侧/底部只用 palette index 0 填充；
5. 每块 JSON 记录 battle row、全图 active size、chunk index/count、world origin 和
   collision source；
6. 独立 manifest 记录全图尺寸、chunk size、viewport width、全部 origin 与 ROM source
   hashes。

battle 11 因此生成：

```text
battle_11_map_chunk_0: origin 0, covers [0, 512)
battle_11_map_chunk_1: origin 32, covers [32, 544)
```

两个分块有 480px 重叠。大重叠是地图仅超宽 32px 的自然结果，不是重复的逻辑地图。

## 运行时流送器

`battle_background_stream` 是无 Butano 依赖的固定容量状态机：

- `prepare(map_width, viewport_width, origins, count)` 校验首块为 0、origin 递增、
  无可视窗缺口且末块覆盖地图右端；
- 输入是相机在地图像素坐标中的中心点；
- 当前块右边不能覆盖 viewport 时向右切换；
- 当前块左边不能覆盖 viewport 时向左切换；
- 重叠区形成自然 hysteresis，避免边界来回抖动；
- 返回当前 chunk index 和是否变化，不拥有 BG、camera 或领域状态。

renderer 持有分块 item 指针和 origin：

```text
controller snapshot cursor/presentation origin
        |
        v
camera world x
        |
        + 256 -> map pixel center
        |
        v
battle_background_stream
        |
        v
regular_bg_ptr.set_item(chunk) + set_x(origin)
```

背景 origin 只改变 BG 在世界空间中的位置；`world_x(point)`、单位位置和逻辑网格仍以全图
左上角为原点。

## 可见入口

- scenario 43 的 SELECT 继续进入 battle 9；
- battle 9 开放 SELECT 进入 battle 11；
- battle 11 先走共享部署确认，再进入同一 `battle_runtime_controller`；
- 玩家可把移动 cursor 推到最右列，摄像机越过 512px 边界时切换到 chunk 1；
- 遥测追加当前 chunk index/count，验收脚本必须同时看到 chunk 0、chunk 1，并返回 chunk 0，
  证明双向切换而非静态裁图。

## 错误与边界

- 地图尺寸、origin、chunk 数或 viewport 覆盖非法：进入战斗前失败关闭。
- 配置声明的 chunk item 为空：返回上一层，不显示黑屏或错误背景。
- VRAM 资源创建失败：Butano 开发构建断言；ARM 构建与 mGBA 是必需验收。
- 分块切换只发生在帧更新前，不创建等待输入的黑帧。
- 自动路线静音，只验视觉、状态和流程，不验音频听感。
- 纵向最大高度当前为 512px；未来出现更高内容时沿同一协议扩展二维 origin，不在本次提前
  增加未使用复杂度。

## 验收

- 生成器 RED/GREEN 覆盖 battle 11 两块的尺寸、origin、重叠像素一致性、哈希与非法参数。
- C++ RED/GREEN 覆盖 prepare、左右切换、hysteresis、缺口/越界失败。
- source wiring 证明 renderer 使用 stream 结果切换 item，battle 11 没有独立 FSM。
- ARM 构建证明两份资源可编译且 section/ROM 未超预算。
- 静音 mGBA 路线完成部署、观察 chunk `0→1→0`、进入共享战斗状态，并保存三处截图和
  telemetry audit。
- battle 9、scenario 43、scenario 41 既有路线继续通过。

