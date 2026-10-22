# Dialogue Byte-Pair Mapping - 关键障碍（2026-07-02 15:32）

## 背景

BREAKTHROUGH commit (`473a737`) 声称："IWRAM 0x03000078 = 当前 dialogue ROM 偏移"。
基于此，捕获了 chapter 1 intro 30 个 dialogue 状态，期望能从 30 个 (ROM bytes, OCR text) 对
中构建 byte→char 映射表，扩展 `sjis-to-tile-mapping.json`（目前只有 20 条映射，来自 group0）。

## 关键发现（correction）

**BREAKTHROUGH 的 IWRAM 0x78 解读错误：**

- 字节序问题：commit 把 0x78 当作 BIG-endian 读了
- 实际 GBA 是 LITTLE-endian，所以 30 个状态的正确 LE 16-bit 值是：
  - State 0: 0x8DF0 (commit 写的 0xF08D 是 BE 解读)
  - State 1: 0x8F6F
  - State 2: 0x90E5
  - ...
  - State 29: 0xB8EB

**用正确的 LE 值指向 ROM，data 不能解出 OCR text：**

例如 state 0：
- 正确 LE 指针: 0x8DF0
- ROM[0x8DF0:0x8DF0+12] = `5a 8a ef 88 da 91 69 81 63 81 63 00 00 00...`
- OCR: "能不能再来一碗啊……" (9 chars)
- 即使假设 5 字节 header，剩下的 7 字节按 SJIS 解也只出 3.5 个 char
- 加上后续零填充，结构看起来像 metadata 而非 dialogue 文本

## 多种假设尝试均失败

1. **2-byte SJIS 解码（标准）：** 不匹配
2. **反字节序 SJIS：** 81 40 / 40 81、81 63 / 63 81 双向都高频出现，但没产生一致 mapping
3. **跳过 N 字节 header：** 各种 header 长度都凑不齐 OCR 字符数
4. **找 tile table（0xA0000 是空区，不是）：** 0xA0000-0xA4000 几乎全 0，无 tile index 表

## State 0 vs Group0 对比

- Group0 dialogue at ROM 0x459414 (per `notes/dialogue-format.md`):
  - 解码完美："什么！？……真拿你没办法\n最后一次哦！！"
  - 用现有 20 条 mapping 完全 ok
- Chapter 1 intro at ROM 0x8DF0-0xB8EB (IWRAM 0x78):
  - 解码失败
  - 假设 IWRAM 0x78 不是 dialogue 文本指针，而是其他 metadata

## IWRAM 0x78 实际语义（推测）

- LE 值随 dialogue state 单调递增（每次 A 按 +0x17F 左右）
- 可能是 "当前 entry 在某张表中的索引"
- 0x0300007C-0x7F = 常量 0xE3A03301（ARM `MOV r3, #0xCC00` 指令）
  - 这看起来像内嵌的 ARM 代码，不是数据
  - 0x03000078 可能是指向 VM/code pointer，不是 dialogue 文本

## 下一步候选方向

**Option A - 换思路找 dialogue 文本：**
1. 在 ROM 里扫描 chapter 1 intro dialogue 的真实文本区
   - 已知：text bank 在 0x459414-0x461CE0，35KB
   - 但 30 个 OCR text 里只有 "伊鲁卡老师真是好啊！" 这类短对话
   - 跟 text bank 不重合
2. 用 mGBA debugger 追 dialogue renderer 的读取路径
   - 之前 32 structures 已经定位到 `0x0808947C` (renderer)、`0x08065EB8` (glyph expansion)
   - 在这些函数上设断点，看实际从哪个地址读 dialogue bytes
3. 用 VRAM tilemap 反推（已有 vram-state0.json）
   - Tilemap entry → tile index → 对比 vram 里的 glyph → 映射回 SJIS

**Option B - 暂停 dialogue mapping，回到 editor / battle / 其他任务：**
- 编辑器已经端到端可用（`43b4398`）
- battle config / 地图 / 战斗脚本 还有 10+ 个未完成
- puppeteer 视觉验证也可以扩展到其他 dialogue

**Option C - 完全不同的方向：**
- 开始做 chapter 2/3 的 dialogue 捕获（但有同样的 mapping 问题）
- 开始做 tile 替换研究（如何自己替换 tile 而不依赖熊组汉化版）

## 当前文件状态

- pi-goal-editor tmux session 还在（PID 3056055），goal complete，等新指令
- Working tree 脏：`build/naruto-sequel-build-report.json` + `naruto-sequel-dev.gba` 是 T7 puppeteer 验证产物（memory 里有提到但没 commit）
- node_modules 噪音（1323 个 tracked 文件不该进 git，但 .gitignore 加了之后已经有的没移除）
