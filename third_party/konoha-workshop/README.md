# 木叶工房 剧情编辑器与后续 DEMO — 第三方源码（vendored）

> 本目录是**第三方作品**的源码快照，用于本仓库的逆向工程参考。
> 它不是本仓库自己写的代码，**不要在本地直接改这里**；
> 要改动请在本仓库自己的 `tools/` `notes/` `web-editor/` 下另起实现。

---

## 1. 来源

| 项 | 值 |
|---|---|
| 原包名 | 木叶工房_剧情编辑器与后续DEMO_v0.4.4_无ROM |
| 版本 | v0.4.4 |
| 原始位置 | `D:\Downloads\火影忍者_木叶\木叶工房_剧情编辑器与后续DEMO_v0.4.4_无ROM` |
| 引入日期 | 2026-10-20 |
| 引入方式 | 按原目录结构整体复制，**不含 ROM、SAV、即时状态** |
| 文件数 | 155（全部 SHA-256 与原包逐一核对一致） |
| 体积 | 1,282,546 字节 |

原作者在包内 `00_先看这里.txt` 署名"你是谁怎么傻乎乎修改 免费分享"，并声明
"自编代码以 MIT 完全开源，可用 AI 自由修改；未来理论上不再更新"。

## 2. 许可状态

原包 `LICENSE` 为 MIT，`素材与许可说明.txt` 划清了边界：

- **MIT 授权**：本包自编的编辑器、扩展程序、补丁应用器与随附工具代码
- **不在 MIT 范围**：游戏原有程序、图像、音乐、汉化底稿、角色及原作故事
  （原作相关归属含 TOMY 及相关原权利方；简体中文底稿为 BEARTEAM）
- 补丁、字形缓存、示例素材含对既有资源的引用或差异数据，
  **不因此把原作资产变成 MIT 授权**

本目录只收录 MIT 授权的自编代码与其必需的工程配置；原作素材一律排除（见 §4）。
上游 MIT 许可全文保留在本目录 `LICENSE`。

## 3. 为什么引入

本仓库的 ROM 与该包基线**完全同一份**：

```
SHA-256 : 1198ece781aaf629db1f0c6628b4f9f1849ecc4a2eac6a55d32748c2a459d05b
SHA-1   : 26f60795fa5e63b4f0264b84e453beffd56b9f7d
大小    : 6291456 (0x600000)
```

因此该包源码里固化的逆向结论（地址、字段偏移、脚本指令编号、hook 前像字节）
**对本仓库直接可用**，无需重新定位。本仓库已完成逐条实测复核，
见 `notes/external-konoha-workshop-gap-20261020.md`。

复核脚本：`tools/probe_external_re_claims.py`（本仓库自写，不属于第三方）。

## 4. 已排除的文件（54 个）及理由

| 排除项 | 数量 | 理由 |
|---|---|---|
| `editor/music/track_*.wav`、`源码/editor/music/track_*.wav` | 36 | **原作音乐**，明确不在 MIT 范围 |
| `editor/sample_glyphs.json`、`源码/editor/sample_glyphs.json` | 2 | **原作字体字形位图缓存**（"字形缓存"不因随包开源而变为 MIT） |
| `源码/asset_import/generated/**` | 12 | 此前改版制作的**参考美术素材**（凯头像/战斗人物 PNG、素材包 JSON、生成记录），含角色形象 |
| `DEMO/补丁/*.bps`、`源码/基础引擎_v0.1.5.bps` | 3 | 针对原作 ROM 的**二进制补丁**（含原作差异数据） |
| `demo_data.js` | 1 | base64 内嵌上述 BPS 补丁 |

排除项**均可自行重建**，方法见各目录内脚本：

- 音乐：`源码/continuation/tools/gba_music_preview.c` +
  `源码/continuation/tools/build_music_previews.py`（从自有 ROM 导出）
- 字形缓存：`editor/make_sample_glyphs.py`（从自有 ROM 字库生成）
- 凯素材：`源码/asset_import/build_guy_demo.js`（需自备素材/图片生成）
- 补丁：`源码/bps.py` + `源码/continuation/tools/build_campaign.js`
  → 需自备匹配基线的 ROM（`python 源码/准备自有基底.py "<你的原版.gba>"`）

本仓库 ROM 与该基线 SHA-256 相同，因此上述重建脚本在本仓库可直接跑通。

## 5. 目录结构（保持上游原样）

上游构建脚本依赖固定相对路径，因此**原样保留**目录布局：

```
editor/                     离线可视化编辑器（core/features/asset_imports/music…）
源码/editor/                同版构建副本（与包根 editor/ 内容相同）
源码/continuation/          剧情扩展工程
  ├─ project/               战役工程 JSON（campaign / campaign_continuation / 模板）
  ├─ source/                运行时扩展 C/ASM（runtime*.c、runtime.S、escape_rules.c）
  └─ tools/                 战役构建器与验证脚本（build_campaign.js 等）
源码/source/                早期"三人替代"工程（v0.1.2，另一套代码，勿与 v0.4.4 混用）
源码/tools/                 构建与探针（build.py、gba_probe.c、validate_*.py）
源码/build/symbols.txt      链接符号表（供 build_campaign.js 解析 hook 目标）
DEMO/工程/                  两版初始工程 JSON
DEMO/剧情原稿/              26 场剧情原稿与战斗编排 TSV
```

顶层另有 `00_先看这里.txt`、`给AI的修改入口.md`、`素材与许可说明.txt`、
`交付核对.json`、`补丁核对.json`、`文件清单.json`、`patcher.js`、
`生成DEMO.html`、`启动编辑器.cmd`、`生成DEMO.cmd`。

## 6. 使用方式

1. **只读参考**：绝大多数情况下，正确的用法是把它当**逆向知识库**读，
   然后在本仓库 `notes/` 记录结论、在 `tools/` 写自己的实现。
2. **跑通它自己的构建**（需要工具链）：
   - Node.js、Python 3 + Pillow、ARM GCC (`arm-none-eabi-`)，Windows 下源码构建未实测
   - `python 源码/准备自有基底.py "<你的原版.gba>"`
   - `NARUTO_CAMPAIGN_EDITION=restart node 源码/continuation/tools/build_campaign.js`
   - Windows 命令提示符请用 `set` 设置变量后执行 `node`
3. **不要**用它的 `源码/tools/build.py` 覆盖本仓库的固定基底；
   上游自己也提醒"不要运行历史 tools/build.py 覆盖固定基底"。

## 7. 上游自陈的局限（引用时注意）

- DEMO 只是**功能演示**，数值/剧情/素材都不完善，不是成熟成品
- 验证范围：两版均以正常按键完成第一关和第二关撤离、进入第三关；
  **本次没有重新完整打通两版各 26 场**，硬件、全部换人组合及所有路线未测
- 条件类型 10（"到达指定位置并结束行动"的撤离规则）是**上游新增的运行时扩展**，
  不是原版能力；原版类型 0..9 的逐条精确语义上游未公开
- 他们的做法是"搬迁整表 + 批量改指针 + 追加代码段"，会大量占用 ROM 尾部空间

## 8. 相关文档

- `notes/external-konoha-workshop-gap-20261020.md` — 完整差集清单与实测复核记录
- `tools/probe_external_re_claims.py` — 复核脚本（本仓库自写）
- `docs/sequel-roadmap.md` — P0-Step 3.5「吸收第三方剧情编辑器的逆向成果」
