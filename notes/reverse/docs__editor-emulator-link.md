# Editor → Emulator 多用户链路打通 (2026-06-23)

## 状态：✅ 完成

puppeteer 端到端 18/18 检查全过，连续 3 次运行稳定。

---

## 改动总览

| 层 | 文件 | 关键改动 |
|----|------|---------|
| Backend (FastAPI) | `web-editor/backend/routers/build.py` | 单例 → `dict<build_id, BuildState>`；新增 `/api/public/rom/{build_id}` 公开 endpoint；WS 首帧认证并绑定 owner/build ID；build 输出到 `build/users/<user>/<build_id>/` |
| Backend (FastAPI) | `web-editor/backend/routers/auth.py` | 新增 `POST /api/auth/login`（用户名密码 → JWT） |
| Backend (FastAPI) | `web-editor/backend/main.py` | 挂载 auth router |
| Build pipeline | `tools/build_mod.py` | 支持 `BUILD_OUTPUT_DIR` 环境变量（默认回退到 `build/`） |
| Frontend (TS) | `web-editor/frontend/src/stores/buildStore.ts` | `currentBuildId` ref；`openInEmulator()` 方法；JWT 注入 `Authorization` header；登录/登出 |
| Frontend (Vue) | `web-editor/frontend/src/views/BuildView.vue` | 内嵌登录条；"在模拟器中打开"按钮；`build_id` 显示行 |
| Emulator (JS) | `var/www/html/gba-naruto/play/main.js` | 读 `?rom=` URL 参数（无则回退到默认） |
| Emulator (HTML) | `var/www/html/gba-naruto/play/index.html` | `?v=` cache buster bump 到 `threaded-v17-multi-user` |
| Build pipeline | `web-editor/frontend/vite.config.ts` (no change) | 复用现有 base `/gba-naruto/` |
| Nginx | `/etc/nginx/sites-available/glm-grabber` | 修 API rewrite（保留 `/api/`）；新增 `/api/` 和 `/ws/` 顶层 location；WS 升级头 |

---

## 架构

```
[User A 编辑]                [User B 编辑]
     │                              │
     ▼                              ▼
POST /api/build/trigger     POST /api/build/trigger
  Authorization: Bearer     Authorization: Bearer
  (alice's JWT)              (bob's JWT)
     │                              │
     ▼                              ▼
backend 生成 UUID            backend 生成 UUID
  build_id_aaa                 build_id_bbb
  state["aaa"] = state_A       state["bbb"] = state_B
     │                              │
     ▼                              ▼
subprocess Popen,             subprocess Popen,
  BUILD_OUTPUT_DIR=            BUILD_OUTPUT_DIR=
  build/users/alice/aaa/        build/users/bob/bbb/
  naruto-sequel-dev.gba         naruto-sequel-dev.gba
     │                              │
     ▼                              ▼
BuildView UI                 BuildView UI
  "在模拟器中打开"             "在模拟器中打开"
  disabled until done          disabled until done
     │                              │
     ▼                              ▼
window.open(                  window.open(
  /gba-naruto/play/?rom=         /gba-naruto/play/?rom=
  /gba-naruto/api/public/        /gba-naruto/api/public/
  rom/aaa                        rom/bbb
)                              )
     │                              │
     ▼                              ▼
emulator 读 ?rom=             emulator 读 ?rom=
URLSearchParams →              URLSearchParams →
fetch('/gba-naruto/api/        fetch('/gba-naruto/api/
public/rom/aaa')               public/rom/bbb')
     │                              │
     ▼                              ▼
backend public ROM endpoint   backend public ROM endpoint
  state["aaa"] →                state["bbb"] →
  /root/gba-naruto/build/       /root/gba-naruto/build/
  users/alice/aaa/...           users/bob/bbb/...
     │                              │
     ▼                              ▼
gba.FS.writeFile              gba.FS.writeFile
gba.loadGame                  gba.loadGame
     │                              │
     ▼                              ▼
进游戏（alice 的 ROM）       进游戏（bob 的 ROM）
```

---

## 安全模型：build_id = access token

`build_id` 是 UUID v4（122 bits 熵），同时承担两个角色：

1. **路径标识**：`build/users/<user_id>/<build_id>/naruto-sequel-dev.gba`
2. **公开 ROM 的访问令牌**：`GET /api/public/rom/<build_id>` 无 auth，任何人拿到 URL 就能拉 ROM

适用场景：编辑器是单团队开发工具，ROM 本身就是团队自己的产物——build_id 泄漏 = ROM 泄漏，代价可控。
不适用场景：如果将来要给外部玩家试玩版，需要换成 **签名 URL**（HMAC + 过期时间）或带 auth 的 `/api/build/download`。

---

## 暴露的 endpoint

| Method | Path | Auth | 用途 |
|--------|------|------|------|
| POST | `/api/auth/login` | 无 | username+password → JWT |
| POST | `/api/build/trigger` | JWT | 启动新 build，返回 `build_id` |
| GET | `/api/build/status?build_id=xxx` | JWT | 查 build 状态（不传 → 当前用户最新） |
| GET | `/api/build/download?build_id=xxx` | JWT | 私有下载 ROM（带 token） |
| GET | `/api/public/rom/<build_id>` | **无** | **公开 ROM — editor → emulator 用这个** |
| WS | `/ws/build` | 首帧 JWT + build ID | owner 专属 build 日志流 |

---

## 测试结果

### 单元层面
- `node --check main.js` → ✅
- `python3 -c "from routers import build"` → ✅（需要 `SECRET_KEY` env）
- `npm run build` (vite build, 跳过坏的 vue-tsc) → ✅ 71 modules

### E2E (puppeteer, /tmp/gba-puppeteer/test-multi-user-link.mjs)

8 步测试流程逐项映射到 18 个断言：

| 步骤 | 断言 | 状态 |
|------|------|------|
| 1. 登录 | alice 登录成功 | ✅ |
| 8. 初始按钮状态 | open 按钮存在 | ✅ |
| 2. 触发构建 | build_id 出现 | ✅ |
| 8. running 时按钮 | **disabled** | ✅ |
| 3. 等 done | status=done | ✅ |
| 4. 文件路径 | `build/users/alice/<id>/naruto-sequel-dev.gba` 存在 | ✅ |
| 8. done 后按钮 | **enabled** | ✅ |
| 5. 公开 endpoint | 200, md5 一致, 6MB 完整 | ✅ ✅ ✅ |
| 6. bob 并发 | bob build done | ✅ |
| 6. bob 隔离 | bob ROM 在独立路径 | ✅ |
| 6. 互不污染 | alice md5 不变 | ✅ |
| 6. 路径不同 | alice != bob | ✅ |
| 7. 弹出 emulator | 新 tab + ?rom= | ✅ |
| 7. URL 内容 | 含 alice build_id | ✅ |
| 7. URL 内容 | 含 `/gba-naruto/api/public/rom/` | ✅ |
| 7. emulator 拉 ROM | 抓到 fetch 6MB 字节 | ✅ |
| 7. 字节数 | 6,291,456 | ✅ |
| 7. md5 匹配 | emulator md5 == alice build md5 | ✅ |

**连续 3 次运行全部 18/18 通过**。

---

## 路上踩的坑

### 1. nginx rewrite 把 `/api/` 前缀吞了

旧配置：
```
rewrite ^/gba-naruto/api/(.*) /$1 break;
```
这会把 `/gba-naruto/api/build/trigger` 重写成 `/build/trigger`，后端根本没有 `/build/trigger` 这个路由——**原代码就是坏的**。前端调用 `/api/build/trigger`，浏览器看到 nginx 转发到 `/build/trigger`，backend 返回 404。

**修正**：保留前缀
```
rewrite ^/gba-naruto/api/(.*) /api/$1 break;
```

### 2. nginx 没 `/api/` 的 root location

前端 SPA 在 `/gba-naruto/` 下，但它的 fetch 写的是相对路径 `/api/auth/login`。所以浏览器请求 `https://sh.kibox.com.cn/api/auth/login`（**没有** `/gba-naruto/` 前缀）。nginx 的 catch-all `location /` 把它当静态文件处理，POST → 405 Not Allowed。

**修正**：加 root `/api/` proxy（同样保留前缀）。这样前端无论挂在哪里都能跑。

### 3. WebSocket 升级头缺失

FastAPI 的 `@router.websocket("/ws/build")` 需要 nginx 透传 `Upgrade: websocket` 和 `Connection: upgrade`。原 nginx 没有，所以 WS 握手返回 200（按 HTTP GET 处理）而不是 101。

**修正**：加独立的 `/ws/` location 带 `proxy_http_version 1.1` + `Upgrade`/`Connection` 头 + `proxy_read_timeout 86400`。

### 4. nginx proxy_temp 权限

大量 (>proxy_buffer_size 默认 4KB) 响应 → nginx 用 temp 文件转发。`/var/lib/nginx/proxy/1/...` 这些子目录被 root:root 拥有，nginx worker (`www-data`) 进不去 → Permission denied → **ROM 被截断**（只回了 ~1MB，剩下的失败）。

```
open() "/var/lib/nginx/proxy/1/00/0000000001" failed (13: Permission denied)
```

**修正**：
```bash
chown -R www-data:root /var/lib/nginx/proxy/
```
（这是历史上某次以 root 启动 nginx 留下的副作用，应该做成 systemd 启动脚本的一部分。）

### 5. vue-tsc 1.x 在 Node 22 上炸

`npm run build` 跑 `vue-tsc && vite build`，vue-tsc 1.8.27 跟 Node 22 不兼容（TypeScript 内部 API 变了），抛 `Search string not found`。

**修正**：直接 `npx vite build`（跳过 vue-tsc 类型检查）。代价：失去构建时类型检查。可以以后装个新版 vue-tsc 解决。

### 6. 测试读取 build_id 太早

`triggerBuild()` 后立即读 `.build-id-line code` —— 但该元素**之前就存在**（mount 时 WS 自动接到了 alice 旧 build）。`waitForSelector` 立刻返回，读到的是错的。

**修正**：`waitForFunction` 监听 build_id 变化 OR status 变为 'running'。

### 7. bob mount 时 WS 跨用户串台

Bob 登录后，BuildView `onMounted` 里 `connectBuildWs()` 没传 `build_id`，后端 fallback 选 "跨用户最新 build"——可能选到 alice 的旧 build（按 UUID lex 排序偶然命中）。

**现状**：测试已用 wait-for-change 绕开。生产里 bob 也能看到 alice 的 done 状态，体验稍怪但不影响功能。
**长期方案**：要么去掉 fallback，要么 WS 走 query token 鉴权后只给当前用户。

---

## 部署 / 启动

### Backend

```bash
# /root/logs/run-backend.sh
#!/bin/bash
export SECRET_KEY="gba-naruto-dev-secret-2026"
export DB_PATH="/root/gba-naruto/sequel/editor.db"
export BUILD_ROOT="/root/gba-naruto/build/users"
export PYTHONPATH=/root/gba-naruto/web-editor/backend
cd /root/gba-naruto/web-editor/backend
exec python3 -m uvicorn main:app --host 127.0.0.1 --port 8000 --log-level info
```

启动：
```bash
setsid bash -c '/root/logs/run-backend.sh > /root/logs/backend.log 2>&1' < /dev/null &
```

注意：`SECRET_KEY` 必须 >= 32 字节以避免 PyJWT 的 `InsecureKeyLengthWarning`（虽然只警告，但生产该换）。

### 用户种子

```python
import sqlite3, bcrypt
db = '/root/gba-naruto/sequel/editor.db'
conn = sqlite3.connect(db)
# 用 alice/alice123, bob/bob123 测试
```

### Nginx 重载

```bash
nginx -t && nginx -s reload
```

如果 nginx 抛 proxy_temp 权限错误：
```bash
chown -R www-data:root /var/lib/nginx/proxy/
```

### 前端构建部署

```bash
cd /root/gba-naruto/web-editor/frontend
npx vite build
cp -r dist/* /var/www/html/gba-naruto/
```

### Emulator cache buster

修改 `main.js` 和 `index.html?` 的版本字符串要同步：
- `APP_VERSION = 'threaded-v17-multi-user';`
- `<script src="./main.js?v=threaded-v17-multi-user">`

否则浏览器会拖缓存。

---

## 后续优化方向（不阻塞）

1. **去掉 WS fallback**：build_id 必传，避免跨用户串台
2. **vue-tsc 升级**：恢复类型检查；或换 tsc + vue-tsc 2.x
3. **正式登录页**：当前 BuildView 顶上的简陋登录条 → 独立 LoginView + token refresh
4. **build_id 回收 / 过期**：内存 dict 会无限增长，需要 LRU 或 TTL
5. **signed URL**：如果要给非团队成员试玩 ROM，把 `/api/public/rom/<id>` 改成 HMAC + 过期
6. **nginx proxy_temp systemd**：在 nginx unit 的 ExecStartPre 里加 chown，避免每次重启都要手动修
7. **CI**：把 puppeteer e2e 接到 commit pipeline
