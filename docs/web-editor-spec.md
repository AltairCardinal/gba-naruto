# 网页编辑器技术规格书

> 创建日期：2026-04-01  
> 项目：木叶战记 GBA 续作网页编辑器  
> 技术栈：FastAPI + Vue 3 + SQLite (WAL) + WebSocket + Docker Compose  
> 服务器：14.103.49.74:443（Debian 12，2核/4GB）

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Vue 3 SPA)                     │
│   WebSocket ←→ FastAPI Server ←→ SQLite DB                   │
│                        ↓                                     │
│              ROM Build Pipeline                              │
│         tools/build_mod.py (existing)                        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + TypeScript | Composition API, Pinia 状态管理 |
| 后端 | FastAPI (Python 3.11) | 异步 REST + WebSocket |
| 数据库 | SQLite (WAL 模式) | 文件存储在 `/root/gba-naruto/sequel/` |
| 实时通信 | WebSocket | 多人协作编辑、构建日志流 |
| 部署 | Docker Compose | 容器化部署 |
| 反向代理 | nginx (已有) | 端口 443 HTTPS，代理到 FastAPI |
| 构建 | tools/build_mod.py | 现有 ROM 构建入口 |

### 1.3 项目结构

```
web-editor/
├── backend/
│   ├── main.py              # FastAPI 入口
│   ├── database.py          # SQLite WAL 连接管理
│   ├── models/              # Pydantic 模型
│   │   ├── dialogue.py
│   │   ├── map.py
│   │   ├── character.py
│   │   └── chapter.py
│   ├── routers/             # API 路由
│   │   ├── dialogues.py
│   │   ├── maps.py
│   │   ├── characters.py
│   │   ├── chapters.py
│   │   ├── build.py
│   │   └── websocket.py
│   ├── services/            # 业务逻辑
│   │   ├── dialogue_service.py
│   │   ├── map_service.py
│   │   ├── build_service.py
│   │   └── collaboration.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # Vue 组件
│   │   ├── views/           # 页面视图
│   │   ├── stores/          # Pinia stores
│   │   ├── composables/     # 组合式函数
│   │   └── types/           # TypeScript 类型
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── Dockerfile
```

---

## 2. 数据库设计（12 张表）

### 2.1 对话相关表

```sql
-- 对话条目表
CREATE TABLE dialogues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT UNIQUE NOT NULL,        -- 对话唯一标识，如 "EP01_NARU_001"
    speaker TEXT,                     -- 说话者
    text_ja TEXT,                     -- 日文原文
    text_zh TEXT,                     -- 中文翻译
    chapter_id INTEGER,               -- 所属章节
    byte_count INTEGER,               -- 编码后字节数
    max_bytes INTEGER DEFAULT 255,    -- 最大允许字节数
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 对话变量引用表
CREATE TABLE dialogue_vars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dialogue_id INTEGER REFERENCES dialogues(id),
    var_name TEXT,                    -- 变量名如 "PLAYER_NAME"
    var_type TEXT DEFAULT 'str'      -- str/int/flag
);
```

### 2.2 地图相关表

```sql
-- 地图元数据表
CREATE TABLE maps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_key TEXT UNIQUE NOT NULL,    -- 如 "MAP_01_01"
    name TEXT,                        -- 地图名称
    tilemap_ptr_hex TEXT,            -- ROM 指针如 "0x195000"
    tile_width INTEGER DEFAULT 32,
    tile_height INTEGER DEFAULT 32,
    tileset_ids TEXT,                -- JSON: [0, 1, 2] 引用的 tileset
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 瓦片编辑快照（undo/redo）
CREATE TABLE map_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    map_id INTEGER REFERENCES maps(id),
    snapshot_data BLOB,              -- 完整 tilemap 二进制快照
    operation TEXT,                  -- 'edit'/'paste'/'fill'
    created_by TEXT,                 -- 用户名
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 2.3 角色/战斗相关表

```sql
-- 角色基础信息表
CREATE TABLE characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slot_id INTEGER UNIQUE,         -- ROM 槽位 ID (0-63)
    name_ja TEXT,
    name_zh TEXT,
    hp_base INTEGER DEFAULT 100,
    attack_base INTEGER DEFAULT 10,
    speed_base INTEGER DEFAULT 5,
    sprite_idx INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 技能配置表
CREATE TABLE skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id INTEGER REFERENCES characters(id),
    skill_slot INTEGER,              -- 技能槽位 0-3
    skill_name TEXT,
    power INTEGER DEFAULT 0,
    effect TEXT,                     -- 效果描述
    animation_id INTEGER
);

-- 战斗场景配置表
CREATE TABLE battle_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scene_key TEXT UNIQUE,           -- 如 "BATTLE_CHAPTER_01"
    chapter_id INTEGER,
    tilemap_ptr_hex TEXT,
    palette_ptr_hex TEXT,
    enemyFormation TEXT,             -- JSON: 敌人阵型配置
    flags INTEGER DEFAULT 0,
    raw_bytes BLOB                   -- 原始 32 字节（用于直接 patch）
);
```

### 2.4 章节/剧情相关表

```sql
-- 章节配置表
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_num INTEGER UNIQUE,      -- 章节号 1-8
    title TEXT,
    tilemap_entry_ptr TEXT,          -- ROM 入口指针
    start_map_key TEXT,
    start_x INTEGER,
    start_y INTEGER,
    episode_id INTEGER               -- 所属季/篇
);

-- 剧情事件表
CREATE TABLE story_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER REFERENCES chapters(id),
    sequence_order INTEGER,           -- 事件顺序
    event_type TEXT,                 -- 'dialogue'/'battle'/'move'/'item'
    event_key TEXT,                   -- 引用 key
    condition TEXT,                   -- 触发条件 JSON
    raw_script BLOB                   -- 原始脚本数据
);

-- 剧情节拍线表
CREATE TABLE story_beats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chapter_id INTEGER REFERENCES chapters(id),
    beat_type TEXT,                  -- 'setup'/'confrontation'/'resolution'
    description TEXT,
    related_dialogue_keys TEXT       -- JSON: 相关对话 key 列表
);
```

### 2.5 构建相关表

```sql
-- 构建历史表
CREATE TABLE build_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    build_hash TEXT,                -- ROM SHA-1
    status TEXT,                     -- 'success'/'error'/'warning'
    output_path TEXT,
    log_text TEXT,
    built_by TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- patch manifest 追踪表
CREATE TABLE patch_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patch_key TEXT UNIQUE,          -- 如 "dialogue_EP01_NARU_001"
    patch_type TEXT,                -- 'bytes'/'pointer_redirect'/'dialogue_var'
    target_address TEXT,            -- ROM 地址
    patch_data BLOB,
    applied BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. REST API 端点（60+）

### 3.1 对话 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/dialogues` | 列出所有对话（分页 + 搜索） |
| GET | `/api/dialogues/{key}` | 获取单个对话 |
| POST | `/api/dialogues` | 创建对话 |
| PUT | `/api/dialogues/{key}` | 更新对话 |
| DELETE | `/api/dialogues/{key}` | 删除对话 |
| POST | `/api/dialogues/batch` | 批量创建/更新 |
| GET | `/api/dialogues/chapter/{chapter_id}` | 获取章节所有对话 |
| GET | `/api/dialogues/{key}/byte-count` | 实时字节计数 |
| GET | `/api/dialogues/export` | 导出 JSON |
| POST | `/api/dialogues/import` | 导入 JSON |

### 3.2 地图 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/maps` | 列出所有地图 |
| GET | `/api/maps/{key}` | 获取地图元数据 |
| POST | `/api/maps` | 创建地图 |
| PUT | `/api/maps/{key}` | 更新地图元数据 |
| DELETE | `/api/maps/{key}` | 删除地图 |
| GET | `/api/maps/{key}/tilemap` | 获取 tilemap 数据（原始字节） |
| PUT | `/api/maps/{key}/tilemap` | 保存 tilemap 编辑 |
| POST | `/api/maps/{key}/snapshot` | 保存快照（undo） |
| GET | `/api/maps/{key}/snapshots` | 获取快照历史 |
| POST | `/api/maps/{key}/undo` | 撤销 |
| POST | `/api/maps/{key}/redo` | 重做 |
| GET | `/api/tilesets` | 列出 tileset 元数据 |
| GET | `/api/tilesets/{id}/tiles.png` | 导出 tileset 图像 |

### 3.3 角色 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/characters` | 列出所有角色 |
| GET | `/api/characters/{slot_id}` | 按槽位获取角色 |
| POST | `/api/characters` | 创建角色 |
| PUT | `/api/characters/{slot_id}` | 更新角色 |
| GET | `/api/characters/{slot_id}/skills` | 获取角色技能 |
| PUT | `/api/characters/{slot_id}/skills` | 更新角色技能 |

### 3.4 战斗 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/battles` | 列出所有战斗配置 |
| GET | `/api/battles/{key}` | 获取战斗配置 |
| POST | `/api/battles` | 创建战斗配置 |
| PUT | `/api/battles/{key}` | 更新战斗配置 |
| GET | `/api/battles/{key}/raw-bytes` | 获取原始字节用于验证 |

### 3.5 章节/剧情 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/chapters` | 列出所有章节 |
| GET | `/api/chapters/{num}` | 获取章节详情 |
| POST | `/api/chapters` | 创建章节 |
| PUT | `/api/chapters/{num}` | 更新章节 |
| GET | `/api/chapters/{num}/events` | 获取章节事件序列 |
| POST | `/api/chapters/{num}/events` | 添加事件 |
| GET | `/api/chapters/{num}/beats` | 获取剧情节拍线 |
| PUT | `/api/chapters/{num}/beats` | 更新节拍线 |

### 3.6 构建 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/build/run` | 触发 ROM 构建（异步） |
| GET | `/api/build/status/{job_id}` | 获取构建状态 |
| GET | `/api/build/history` | 构建历史 |
| GET | `/api/build/output/{hash}` | 下载构建产物 |
| GET | `/api/build/log/{job_id}` | 获取构建日志流 |
| POST | `/api/build/validate` | 验证当前 manifest |
| GET | `/api/patches` | 列出所有 patch 记录 |
| POST | `/api/patches/apply` | 手动应用 patch |

### 3.7 管理 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/stats` | 统计数据（对话数/地图数等） |
| GET | `/api/rom/basInfo` | 基础 ROM 信息（SHA-1/大小） |
| POST | `/api/admin/reset-db` | 重置数据库（慎用） |

---

## 4. WebSocket 协议

### 4.1 连接

```
WebSocket: wss://14.103.49.74/ws?room={room_id}&user={username}
```

### 4.2 消息格式

```typescript
// 基础消息 envelope
interface WsMessage {
    type: string;
    room_id: string;
    user: string;
    payload: any;
    timestamp: number;
}

// 房间加入
{ "type": "join", "room_id": "ep01", "user": "alice" }

// 编辑锁定（协作光标）
{ "type": "lock", "room_id": "ep01", "user": "alice", "payload": { "resource": "dialogue:EP01_NARU_001", "range": [0, 50] } }
{ "type": "unlock", "room_id": "ep01", "user": "alice", "payload": { "resource": "dialogue:EP01_NARU_001" } }

// 实时编辑广播
{ "type": "edit", "room_id": "ep01", "user": "alice", "payload": { "resource": "dialogue:EP01_NARU_001", "delta": {...} } }

// 构建日志流
{ "type": "build_log", "room_id": "ep01", "payload": { "line": "...", "level": "info|error" } }
{ "type": "build_complete", "room_id": "ep01", "payload": { "success": true, "hash": "abc123" } }

// 用户列表
{ "type": "room_users", "room_id": "ep01", "payload": { "users": ["alice", "bob"] } }
```

### 4.3 房间隔离

- 每个资源（对话/key/地图）有独立 room
- 用户加入 room 后接收该 room 所有编辑事件
- 构建日志统一 room：`room=__build__`

---

## 5. Vue 组件树

### 5.1 页面视图

```
App.vue
├── LoginView.vue              # 简单用户名输入（无密码）
├── EditorLayout.vue           # 主布局（侧边栏 + 内容区）
│   ├── SidebarNav.vue         # 导航栏
│   ├── TopBar.vue             # 顶部栏（用户名 + 房间 + 构建按钮）
│   └── RouterView
│       ├── DialogueListView.vue    # 对话列表
│       ├── DialogueEditorView.vue  # 对话编辑器
│       ├── MapListView.vue         # 地图列表
│       ├── MapEditorView.vue       # 地图编辑器（Canvas）
│       ├── CharacterListView.vue   # 角色列表
│       ├── CharacterEditorView.vue # 角色编辑器
│       ├── BattleListView.vue      # 战斗配置列表
│       ├── BattleEditorView.vue    # 战斗编辑器
│       ├── ChapterListView.vue     # 章节列表
│       ├── StoryTimelineView.vue   # 剧情节拍线
│       └── BuildView.vue           # 构建控制台
```

### 5.2 核心组件

| 组件 | 说明 |
|------|------|
| `DialogueEditor.vue` | 双栏编辑（日文/中文）+ 实时字节计数 |
| `MapCanvas.vue` | Canvas 瓦片编辑器，支持笔刷/填充/撤销 |
| `TilePalette.vue` | 瓦片调色板（从 tileset 图像切片） |
| `CharacterForm.vue` | 角色属性表单（HP/ATK/SPD/技能） |
| `BattleConfigForm.vue` | 战斗配置（tilemap/调色板/敌人） |
| `StoryBeatLine.vue` | 可视化剧情节拍线（时间轴组件） |
| `BuildConsole.vue` | 构建日志终端（ANSI 彩色 + 实时流） |
| `CollaborativeCursor.vue` | 其他用户光标/锁定指示器 |
| `ByteCounter.vue` | 实时字节计数（绿/黄/红三色警告） |

### 5.3 Pinia Stores

```typescript
// stores/dialogue.ts — 对话状态
// stores/map.ts — 当前地图 + tilemap 数据 + 快照栈
// stores/character.ts — 角色数据
// stores/battle.ts — 战斗配置
// stores/collaboration.ts — WebSocket 房间 + 用户列表 + 锁定状态
// stores/build.ts — 构建任务状态 + 日志缓冲
// stores/ui.ts — 侧边栏折叠状态 + 主题
```

---

## 6. 构建流水线

### 6.1 流程

```
用户点击"构建 ROM"
    ↓
POST /api/build/run
    ↓
后端：创建 job_id，fork 进程执行 build_mod.py
    ↓
WebSocket 推送构建日志（实时流）
    ↓
build_mod.py 执行完毕 → ROM 输出到 build/output/
    ↓
POST /api/build/status/{job_id} 返回 { success, hash, output_path }
    ↓
前端：提供下载链接
```

### 6.2 与现有工具的集成

```python
# build_service.py
import subprocess
import sys
sys.path.insert(0, '/root/gba-naruto/tools')

from build_mod import build_rom

def run_build(job_id: str, project_path: str):
    result = build_rom(
        project_path='/root/gba-naruto/sequel',
        base_rom_path='/root/gba-naruto/base_rom.gba',
        output_path=f'/root/gba-naruto/build/output/{job_id}.gba'
    )
    return result
```

---

## 7. Docker 部署

### 7.1 Dockerfile (Backend)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ ./backend/
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.2 docker-compose.yml

```yaml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - /root/gba-naruto/sequel:/data/sequel
      - /root/gba-naruto/tools:/app/tools
      - /root/gba-naruto/build:/app/build
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

### 7.3 nginx 配置更新

```nginx
# /root/gba-emu-www/nginx.conf 新增
location /api/ {
    proxy_pass http://127.0.0.1:8000/api/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

location /ws {
    proxy_pass http://127.0.0.1:8000/ws;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location /editor/ {
    proxy_pass http://127.0.0.1:5173/;
    # SPA fallback
    try_files $uri /index.html;
}
```

---

## 8. 错误处理

### 8.1 API 错误响应

```json
{
    "error": {
        "code": "DIALOGUE_EXCEEDS_MAX_BYTES",
        "message": "对话 'EP01_NARU_001' 编码后 312 字节，超过限制 255 字节",
        "details": {
            "current_bytes": 312,
            "max_bytes": 255,
            "dialogue_key": "EP01_NARU_001"
        }
    }
}
```

### 8.2 错误码

| 错误码 | HTTP 状态 | 说明 |
|--------|-----------|------|
| DIALOGUE_NOT_FOUND | 404 | 对话不存在 |
| DIALOGUE_EXCEEDS_MAX_BYTES | 422 | 超过最大字节数 |
| MAP_NOT_FOUND | 404 | 地图不存在 |
| BUILD_FAILED | 500 | ROM 构建失败 |
| ROM_HASH_MISMATCH | 422 | 基础 ROM SHA-1 不匹配 |
| PATCH_APPLY_FAILED | 500 | Patch 应用失败 |
| INVALID_POINTER | 422 | 无效的 ROM 指针 |

---

## 9. 测试策略

### 9.1 后端测试

```python
# tests/test_dialogues.py
def test_dialogue_byte_count():
    # 验证字节计数准确性

def test_dialogue_crud():
    # 验证完整 CRUD 流程

def test_map_undo_redo():
    # 验证 undo/redo 栈

def test_build_pipeline():
    # 验证构建流程（mock build_mod.py）

def test_websocket_join():
    # 验证 WebSocket 房间加入
```

### 9.2 前端测试

- Vitest 单元测试（composables, stores）
- Playwright E2E 测试（关键流程）

---

## 10. 开发阶段优先级

**Phase 1 — 基础 + 对话编辑器（2 周）**
1. 项目脚手架（FastAPI + Vue 3 + SQLite）
2. 对话 CRUD API + SQLite 表
3. 对话列表视图 + 编辑器组件
4. 实时字节计数 UI
5. 基础用户认证（仅用户名，无密码）

**Phase 2 — 构建流水线 + WebSocket（2 周）**
1. build_mod.py 集成
2. 构建触发 API + 日志流
3. WebSocket 协作（房间 + 锁定）
4. 构建历史 + 下载

**Phase 3 — 地图编辑器（3 周）**
1. 地图 CRUD + tilemap 原始数据 API
2. Canvas 瓦片编辑器
3. tileset 图像加载 + TilePalette
4. Undo/Redo 栈（map_snapshots 表）
5. 多用户协作光标

**Phase 4 — 战斗/角色 + 剧情编辑器（2 周）**
1. 角色 CRUD + 技能配置
2. 战斗配置编辑器
3. 章节管理
4. 剧情节拍线时间轴

**Phase 5 — 音频 + 打磨 + 国际化（1 周）**
1. 音频预览（使用现有 tools/extract_audio.py）
2. 中文 UI 完善
3. 管理面板
4. 错误处理加固
