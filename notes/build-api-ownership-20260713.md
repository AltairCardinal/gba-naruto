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

## 尚未闭合

`/ws/build` 当前没有鉴权，且缺 build ID 时会跨用户选择全局 build；修复需要前端把
JWT 通过 WebSocket 可验证的握手参数传入并增加 UI wiring 测试。私有 download 的
前端仍用裸 `<a>` 导航，无法附带 Bearer header，也需在建立前端测试能力后改为
带 auth header 的 fetch/blob 下载。真实 subprocess 仍需让 `DB_PATH` 进入
`build_mod.py`，并让 automated checks 验证当前 build-ID 产物。这些边界不能被当前
HTTP 所有权修复掩盖。
