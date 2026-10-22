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

**必须用 HTTP 打开**（`file://` 会被同源策略拦住）。用别的静态服务器也行
（`python -m http.server` 从仓库根目录起，然后访问 `/rom-editor/`），
但自带的那个服务器会额外做两件事：关闭缓存，以及在目录路径上回落到
`index.html`。

启动时顶栏会显示进度条与阶段（下载 → 解压 → 解析）；
每个来源都有 20 秒超时与降级，不会永远停在「正在载入内容包…」。

**构建 ROM 还需要原版 ROM**（6,291,456 字节）：用顶栏「载入 ROM」选一个文件
（不走网络，最稳），或点「载入内置 ROM」从编辑器自带的压缩副本取
（部分浏览器有单页下载量限制，可能取不到）。

编辑功能**不需要** ROM —— 内容包自带全部可编辑内容。

## 自检

```powershell
node rom-editor\tools\verify_pack.mjs
#   → 30 项全 PASS，含「未改动的内容包重建 ROM 与原版逐字节相同」

node rom-editor\tools\verify_views.mjs
#   → 30 项全 PASS：九个模块的视图渲染 + 战斗视图的说明文字/条件语义/出生点就地编辑 + 剧情路线视图
#     （无头跑，不需要浏览器，可进 CI）
```

浏览器内自检（45 项：所有模块视图渲染、关键面板打开、逐域落点、原始字节补丁、剧情 VM 操作数、控制码保留、战斗目标说明文字）：

```
http://localhost:8765/rom-editor/tools/selftest.html
```

自检每检查一项就把结果发到服务器的 `POST /__report`，落到
`build/selftest-report.jsonl`（`GET /__report` 可取回）——
这样即使页面被刷新，结果也留得住。

## 目录

```
index.html            应用外壳
styles.css
js/                   核心（bytes / textcodec / pack / rom / ui / editors / loader / textindex / romsource）
js/modules/           六个域 + 概览 + 原始字节
content/              pack.json(.min) / text-index.json / base-rom/
tools/                serve.mjs / verify_pack.mjs / verify_views.mjs / selftest.html
```

`content/` 下都是**生成物**，不要手改；要改内容就改 `tools/export_content_pack.py`
再重新导出。
