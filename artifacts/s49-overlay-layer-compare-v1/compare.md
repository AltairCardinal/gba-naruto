# S49 覆盖层逐单元比对（自动生成）

本文件由 `tools/butano/compare_s49_overlay_layers.py` 生成，不要手工编辑。

| 项 | 值 |
| --- | ---: |
| 16x16 单元总数 | 150 |
| **族不同（覆盖/状态差异）** | **85** |
| 族相同（画法/描边差异） | 65 |

## 面积对照（8x8 px 格）

| 项 | 值 |
| --- | ---: |
| 原版移动透镜覆盖 | 192 |
| 重制侧移动透镜覆盖 | 232 |
| **重制侧覆盖层实际画出的格数** | **899** |
| **重制 / 原版 画出面积比** | **4.68** |
| 减去 8× 绘制展开后的**状态面积比** | **2.33** |

## 逐单元

| 单元 (col,row) | 原版 | 重制 | 同族 |
| --- | --- | --- | --- |
| (2,3) | grid|transparent | blocked | ❌ |
| (3,3) | grid|transparent | blocked | ❌ |
| (4,3) | grid|transparent | blocked | ❌ |
| (5,3) | grid|transparent | blocked | ❌ |
| (6,3) | move | blocked | ❌ |
| (7,3) | move | blocked | ❌ |
| (8,3) | grid|transparent | blocked | ❌ |
| (9,3) | grid|transparent | blocked | ❌ |
| (14,3) | blocked|grid|transparent | blocked | ❌ |
| (0,4) | blocked | blocked|grid | ❌ |
| (1,4) | blocked | blocked|grid | ❌ |
| (2,4) | grid|transparent | blocked|grid | ❌ |
| (3,4) | grid|transparent | blocked|grid | ❌ |
| (4,4) | move | blocked|grid | ❌ |
| (5,4) | move | blocked|grid | ❌ |
| (6,4) | move | blocked|grid | ❌ |
| (7,4) | move | blocked|grid|move | ❌ |
| (8,4) | move | blocked|move | ❌ |
| (9,4) | move | blocked|grid|move | ❌ |
| (10,4) | grid|transparent | blocked|grid | ❌ |
| (11,4) | grid|transparent | blocked|grid | ❌ |
| (14,4) | blocked|grid|transparent | blocked | ❌ |
| (0,5) | grid|transparent | grid | ❌ |
| (1,5) | grid|transparent | grid | ❌ |
| (2,5) | move | grid | ❌ |
| (3,5) | move | grid | ❌ |
| (4,5) | move | grid | ❌ |
| (5,5) | move | grid|move | ❌ |
| (6,5) | move | grid|move | ❌ |
| (7,5) | move | grid|move | ❌ |
| (9,5) | move | grid|move | ❌ |
| (10,5) | move | grid|move | ❌ |
| (11,5) | move | blocked|grid|move | ❌ |
| (12,5) | blocked | blocked|grid | ❌ |
| (13,5) | blocked | blocked|grid | ❌ |
| (14,5) | blocked|grid|transparent | blocked | ❌ |
| (0,6) | move | grid | ❌ |
| (1,6) | move | grid | ❌ |
| (2,6) | move | grid | ❌ |
| (3,6) | move | grid|move | ❌ |
| (4,6) | move | grid|move | ❌ |
| (5,6) | move | grid|move | ❌ |
| (11,6) | move | grid|move | ❌ |
| (12,6) | blocked | grid|move | ❌ |
| (13,6) | blocked | blocked|grid|move | ❌ |
| (14,6) | blocked|cursor | blocked | ❌ |
| (0,7) | grid|transparent | grid | ❌ |
| (1,7) | grid|transparent | grid|move | ❌ |
| (2,7) | move | grid|move | ❌ |
| (3,7) | move | grid|move | ❌ |
| (7,7) | move | attack|move | ❌ |
| (8,7) | blocked | attack|move | ❌ |
| (9,7) | blocked | attack|move | ❌ |
| (12,7) | blocked | move | ❌ |
| (13,7) | blocked | blocked|move | ❌ |
| (14,7) | blocked|move | blocked | ❌ |
| (0,8) | grid|transparent | grid | ❌ |
| (1,8) | grid|transparent | grid|move | ❌ |
| (2,8) | blocked | grid|move | ❌ |
| (3,8) | blocked | grid|move | ❌ |
| (5,8) | move | blocked|move | ❌ |
| (6,8) | move | blocked|move | ❌ |
| (7,8) | move | attack|blocked|move | ❌ |
| (8,8) | move | attack|move | ❌ |
| (9,8) | move | attack|grid|move | ❌ |
| (10,8) | grid|transparent | grid|move | ❌ |
| (11,8) | grid|transparent | grid|move | ❌ |
| (12,8) | blocked | move | ❌ |
| (13,8) | blocked | blocked|move | ❌ |
| (14,8) | blocked|move | blocked | ❌ |
| (0,9) | grid|transparent | grid | ❌ |
| (1,9) | grid|transparent | grid | ❌ |
| (2,9) | blocked | grid | ❌ |
| (3,9) | blocked | grid|move | ❌ |
| (4,9) | grid|transparent | grid|move | ❌ |
| (5,9) | grid|transparent | blocked|grid|move | ❌ |
| (6,9) | move | blocked|move | ❌ |
| (7,9) | move | blocked|move | ❌ |
| (8,9) | grid|transparent | move | ❌ |
| (9,9) | grid|transparent | grid|move | ❌ |
| (10,9) | grid|transparent | grid|move | ❌ |
| (11,9) | grid|transparent | grid|move | ❌ |
| (12,9) | blocked | grid|move | ❌ |
| (13,9) | blocked | blocked|grid|move | ❌ |
| (14,9) | blocked|grid|transparent | blocked | ❌ |
