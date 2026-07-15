# Build-ID API 所有权隔离（2026-07-13）

## 已复现并修复

`GET /api/build/status` 与 `GET /api/build/download` 原先只要求任意有效登录，传入
他人的 build ID 仍返回 200；隔离 smoke 已实际让无构建权限的 bob 下载到 alice 的
private marker。根因是查到 `BuildState` 后没有比较 `state.user_id` 与当前 username。

`web-editor/backend/tests/test_build_api.py` 现在通过 FastAPI TestClient 固化：

- owner 能查看状态并下载自己的 ROM；
- 其他登录用户对同一私有 status/download 均得到 403；
- `/api/public/rom/{build_id}` 是明确记录的 UUID capability URL，本轮不改变；
- 未指定 build ID 时按 `build_states` 的插入顺序选该用户最新 running/done build，
  不再错误地把随机 UUID v4 字典序当创建时间。

## 浏览器鉴权闭合

前端 token 现统一来自 `authStore`，`apiFetch` 与地图读写不再读取旧的
`access_token` key。私有下载改为携带 Bearer 的 fetch→blob；按钮在请求期间显示
“下载中…”，401 会清理登录态，其他失败把服务端原因展示在构建页。

`/ws/build` 现要求连接后的第一帧携带 JWT 与显式 build ID。缺 ID、无效 token、
跨用户和未知 build 分别以 4400/4401/4403/4404 关闭；缺 ID 时不再选择全局 build。
服务端只向已验证 owner 推送，payload 去除了绝对 `rom_path`。BuildView 先读取当前
用户最新状态，再订阅该 build ID。

后端 TestClient 固化 HTTP/WS owner 隔离，前端 Vitest/jsdom 固化共享 token、认证
下载、WebSocket 首帧和地图 wiring。真实 subprocess 的 `DB_PATH`、外部
`BUILD_OUTPUT_DIR` 与当前 build-ID automated report 仍由
`notes/editor-isolated-writeback-smoke-20260713.md` 覆盖。公开
`/api/public/rom/{build_id}` 的 UUID capability 边界本轮不变。
