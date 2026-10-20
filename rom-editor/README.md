# 木叶战记 ROM 编辑器

离线网页版 ROM 编辑器。纯 HTML + 原生 ES Module，**没有构建步骤**，也没有后端、
数据库或账号体系——起一个静态服务器就能用。

完整说明（六个域分别覆盖哪些表、文本的长度策略、已知边界、与仓库既有写回路径的
对应关系）见 [`docs/rom-editor.md`](../../docs/rom-editor.md)。
本轮的方法与结论见 [`notes/rom-editor-20261021.md`](../../notes/rom-editor-20261021.md)。

## 跑起来

```powershell
# 1) 导出内容包（改了导出器或换了 ROM 才需要重跑）
python tools\export_content_pack.py

# 2) 起静态服务器
node rom-editor\tools\serve.mjs 8765
#   → http://localhost:8765/rom-editor/

# 3) 打开编辑器，先用顶栏「载入 ROM」选一个原版 ROM（构建基底）
```

## 自检

```powershell
node rom-editor\tools\verify_pack.mjs
#   → 19 项全 PASS，含「未改动的内容包重建 ROM 与原版逐字节相同」
```

浏览器内自检（38 项：所有模块视图渲染、关键面板打开、逐域落点、原始字节补丁、剧情 VM 操作数）：

```
http://localhost:8765/rom-editor/tools/selftest.html
```

## 目录

```
index.html            应用外壳
styles.css
js/                   核心（bytes / textcodec / pack / rom / ui / editors / romsource）
js/modules/           六个域 + 概览 + 原始字节
content/              pack.json(.min) / text-index.json / base-rom/
tools/                serve.mjs / verify_pack.mjs / selftest.html
```

`content/` 下都是**生成物**，不要手改；要改内容就改 `tools/export_content_pack.py`
再重新导出。
