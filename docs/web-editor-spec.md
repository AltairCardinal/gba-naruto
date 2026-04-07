# 木叶战记 网页编辑器技术规格书

## 概述

P0 逆向工程全部 7 步已完成（2026-04-01）。项目已具备 6 种 patch 类型的构建流水线、17 项自动化测试、完整的 ROM 地址文档。现在需要建立网页编辑器，让内容创作者无需接触命令行即可编辑对话、地图、战斗配置，触发构建并下载 ROM。

本规格书覆盖：系统架构、数据库设计、REST API、WebSocket 协议、前端组件树、构建队列、部署方案、开发阶段、错误处理、测试策略。


---

## 1. System Architecture

```
                         Internet
                            |
                        [nginx:443]
                       TLS termination
                            |
                    +-------+-------+
                    |               |
              /api/* (HTTP)   /ws/* (WebSocket upgrade)
                    |               |
              [FastAPI:8000] -------+
              (uvicorn, 2 workers)
                    |
         +----------+----------+----------+
         |          |          |          |
    [SQLAlchemy] [ROM Ops]  [Build Q]  [WS Hub]
         |          |          |          |
      SQLite     ROM file   subprocess  broadcast
    (WAL mode)  (read-only   (serial)   (per-room)
                 + build/)
```

### Server File System Layout

```
/opt/naruto-editor/
  app/                     # FastAPI application
    main.py                # application entry, mount routers
    config.py              # settings (paths, secrets, limits)
    models.py              # SQLAlchemy ORM models
    schemas.py             # Pydantic request/response models
    auth.py                # token verification middleware
    routers/
      dialogue.py          # /api/dialogue/*
      maps.py              # /api/maps/*
      battle.py            # /api/battle/*
      story.py             # /api/story/*
      audio.py             # /api/audio/*
      build.py             # /api/build/*
      project.py           # /api/project/*
      users.py             # /api/users/*
    services/
      dialogue_svc.py      # encoding logic, byte counting
      map_svc.py           # tilemap serialization
      battle_svc.py        # unit/scenario patch generation
      build_svc.py         # build queue manager
      ws_hub.py            # WebSocket connection manager
      rom_reader.py        # read-only ROM data extraction
      content_io.py        # JSON file read/write bridging
    websocket/
      handler.py           # WebSocket endpoint, message dispatch
      rooms.py             # room/channel management
      protocol.py          # message type definitions
  tools/                   # symlink or copy of repo tools/
  rom/                     # base ROM (read-only mount)
  data/                    # SQLite database + build artifacts
    editor.db
    builds/                # timestamped build outputs
    tiles/                 # extracted tileset PNGs (pre-generated)
    audio/                 # extracted WAV files (pre-generated)
  frontend/                # Vue 3 + Vite project
    src/
      main.ts
      App.vue
      router/index.ts
      stores/              # Pinia stores
      composables/         # shared composition functions
      components/
      views/
      api/                 # HTTP + WS client wrappers
      i18n/                # zh-CN locale files
```

### Key Design Decisions

- **ROM never leaves the server.** All ROM reads (tileset extraction, map reading, current hex values) happen server-side. The client receives only derived data: tile PNGs as base64 or URLs, dialogue text as decoded strings, map grids as JSON arrays.
- **Existing Python tools are invoked as library calls, not subprocess.** `build_mod.py`, `import_dialogue.py`, `import_dialogue_var.py`, `import_map.py`, and `import_battle_config.py` are imported directly by FastAPI service modules. The only subprocess call is for `automated_test.py` which is run as an isolated process.
- **SQLite in WAL mode** allows concurrent reads from multiple uvicorn workers while a single writer handles mutations. All content edits are persisted to SQLite immediately, then projected onto the JSON content files on disk only at build time.

---

## 2. Database Schema (SQLite, WAL mode)

```sql
-- ============================================================
-- Authentication
-- ============================================================

CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    display_name TEXT   NOT NULL,
    token_hash  TEXT    NOT NULL,           -- SHA-256 of bearer token
    role        TEXT    NOT NULL DEFAULT 'editor',  -- 'admin' | 'editor' | 'viewer'
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_seen   TEXT
);

-- ============================================================
-- Dialogue
-- ============================================================

CREATE TABLE dialogue_bank_entries (
    id              TEXT    PRIMARY KEY,     -- e.g. 'group0.main'
    rom_offset      INTEGER NOT NULL,
    max_bytes       INTEGER NOT NULL,
    encoding        TEXT    NOT NULL DEFAULT 'cp932',
    table_index     INTEGER,
    table_offset    INTEGER,
    text_rom_offset INTEGER,
    expected_hex    TEXT    NOT NULL,
    notes           TEXT,
    group_id        INTEGER,
    group_slot      INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE dialogue_content (
    id              TEXT    PRIMARY KEY,     -- matches dialogue_bank_entries.id
    text            TEXT    NOT NULL,
    notes           TEXT,
    encoded_bytes   INTEGER,
    strategy        TEXT    NOT NULL DEFAULT 'auto',  -- 'same_length' | 'variable' | 'auto'
    updated_by      INTEGER REFERENCES users(id),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    version         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE dialogue_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    entry_id        TEXT    NOT NULL REFERENCES dialogue_content(id),
    text_before     TEXT    NOT NULL,
    text_after      TEXT    NOT NULL,
    changed_by      INTEGER REFERENCES users(id),
    changed_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- Maps
-- ============================================================

CREATE TABLE map_definitions (
    id              TEXT    PRIMARY KEY,
    display_name    TEXT    NOT NULL,
    rom_region      TEXT,
    rom_offset      INTEGER,
    status          TEXT    NOT NULL DEFAULT 'draft',
    notes           TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE map_tile_grids (
    map_id          TEXT    PRIMARY KEY REFERENCES map_definitions(id),
    grid_json       TEXT    NOT NULL,        -- JSON: 32x32 array of {tile_id, hflip, vflip, palette_bank}
    updated_by      INTEGER REFERENCES users(id),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    version         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE map_edit_ops (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    map_id          TEXT    NOT NULL REFERENCES map_definitions(id),
    op_type         TEXT    NOT NULL,        -- 'paint' | 'fill' | 'rect' | 'paste'
    op_data         TEXT    NOT NULL,        -- JSON: {cells: [{row, col, before, after}]}
    user_id         INTEGER REFERENCES users(id),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    seq             INTEGER NOT NULL
);

CREATE INDEX idx_map_edit_ops_map ON map_edit_ops(map_id, seq);

-- ============================================================
-- Battle / Units
-- ============================================================

CREATE TABLE battle_scenarios (
    id              INTEGER PRIMARY KEY,     -- 0-7
    height          INTEGER NOT NULL,
    width           INTEGER NOT NULL,
    tile_gfx_ptr    INTEGER NOT NULL,
    tilemap_ptr     INTEGER NOT NULL,
    tilemap_alt_ptr INTEGER NOT NULL,
    extra_ptr       INTEGER,
    palette_ptr     INTEGER NOT NULL,
    palette2_ptr    INTEGER NOT NULL,
    flags           INTEGER NOT NULL,
    notes           TEXT,
    loaded_from_rom INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE unit_definitions (
    id              TEXT    PRIMARY KEY,
    unit_id         INTEGER NOT NULL,
    display_name    TEXT    NOT NULL,
    role            TEXT,                    -- 'ally' | 'enemy' | 'npc'
    level           INTEGER DEFAULT 1,
    attack          INTEGER DEFAULT 10,
    defense         INTEGER DEFAULT 10,
    agility         INTEGER DEFAULT 10,
    movement        INTEGER DEFAULT 3,
    chakra          INTEGER DEFAULT 100,
    experience      INTEGER DEFAULT 0,
    skills_json     TEXT,                    -- JSON: [{slot, skill_id, skill_level}]
    notes           TEXT,
    updated_by      INTEGER REFERENCES users(id),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE battle_placements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id      TEXT    NOT NULL,
    unit_id         TEXT    NOT NULL REFERENCES unit_definitions(id),
    team            INTEGER NOT NULL DEFAULT 0,
    grid_x          INTEGER NOT NULL,
    grid_y          INTEGER NOT NULL,
    scenario_index  INTEGER NOT NULL DEFAULT 0 REFERENCES battle_scenarios(id)
);

-- ============================================================
-- Story / Episodes
-- ============================================================

CREATE TABLE episodes (
    id              TEXT    PRIMARY KEY,
    title           TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'draft',
    design_goal     TEXT,
    battle_map_id   TEXT    REFERENCES map_definitions(id),
    battle_scenario INTEGER REFERENCES battle_scenarios(id),
    win_condition   TEXT,
    lose_condition  TEXT,
    updated_by      INTEGER REFERENCES users(id),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE episode_beats (
    id              TEXT    NOT NULL,
    episode_id      TEXT    NOT NULL REFERENCES episodes(id),
    seq             INTEGER NOT NULL,
    beat_type       TEXT    NOT NULL,         -- 'dialogue' | 'battle' | 'cutscene'
    summary         TEXT,
    dialogue_ids    TEXT,                     -- JSON array
    config_json     TEXT,
    PRIMARY KEY (episode_id, id)
);

-- ============================================================
-- Build Pipeline
-- ============================================================

CREATE TABLE builds (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    status          TEXT    NOT NULL DEFAULT 'queued',
    triggered_by    INTEGER REFERENCES users(id),
    queued_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    started_at      TEXT,
    finished_at     TEXT,
    rom_sha1        TEXT,
    rom_size        INTEGER,
    report_json     TEXT,
    test_json       TEXT,
    test_passed     INTEGER,
    test_total      INTEGER,
    log             TEXT,
    error           TEXT
);

CREATE TABLE patches_applied (
    build_id        INTEGER NOT NULL REFERENCES builds(id),
    patch_id        TEXT    NOT NULL,
    patch_type      TEXT    NOT NULL,
    offset          INTEGER,
    length          INTEGER,
    strategy        TEXT,
    PRIMARY KEY (build_id, patch_id)
);

-- ============================================================
-- Collaboration / Locking
-- ============================================================

CREATE TABLE edit_locks (
    resource_type   TEXT    NOT NULL,
    resource_id     TEXT    NOT NULL,
    locked_by       INTEGER NOT NULL REFERENCES users(id),
    locked_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at      TEXT    NOT NULL,        -- auto-expire after 5 minutes
    PRIMARY KEY (resource_type, resource_id)
);
```

---

## 3. REST API Specification

All endpoints prefixed with `/api/v1`. Authentication via `Authorization: Bearer <token>`.

### 3.1 Authentication

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/login` | Exchange username + password for bearer token |
| `POST` | `/auth/logout` | Invalidate current token |
| `GET` | `/auth/me` | Return current user profile |

### 3.2 Project

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/project` | Return project metadata |
| `GET` | `/project/stats` | Dashboard statistics |

### 3.3 Dialogue Editor

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/dialogue/bank` | List all bank entries |
| `GET` | `/dialogue/bank/{id}` | Get single bank entry |
| `GET` | `/dialogue/groups` | List grouped entries (305 groups) |
| `GET` | `/dialogue/content` | List all content entries |
| `GET` | `/dialogue/content/{id}` | Get single content entry |
| `PUT` | `/dialogue/content/{id}` | Create or update dialogue text |
| `DELETE` | `/dialogue/content/{id}` | Revert to ROM original |
| `POST` | `/dialogue/validate` | Validate encoding + byte count |
| `GET` | `/dialogue/history/{id}` | Edit history |
| `POST` | `/dialogue/bulk-import` | Import dialogue-patches.json |
| `GET` | `/dialogue/export` | Export as dialogue-patches.json |
| `GET` | `/dialogue/free-space` | Free space usage report |

**PUT /dialogue/content/{id}** example:
```json
Request:  {"text": "木葉村国境に異変あり小隊が調査に向かう。", "notes": "Episode-01 opening"}
Response: {"id": "group0.main", "text": "...", "encoded_bytes": 40, "max_bytes": 41,
           "fits_in_place": true, "strategy": "same_length", "version": 2}
```

**POST /dialogue/validate** example:
```json
Request:  {"bank_id": "group0.main", "text": "テスト文字列"}
Response: {"valid": true, "encoded_bytes": 12, "max_bytes": 41, "fits_in_place": true,
           "strategy": "same_length", "hex_preview": "8365834883678e9a97f1", "warnings": []}
```

### 3.4 Map Editor

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/maps` | List all map definitions |
| `GET` | `/maps/{id}` | Get map definition |
| `GET` | `/maps/{id}/grid` | Get full 32x32 tile grid |
| `PUT` | `/maps/{id}/grid` | Replace entire tile grid |
| `PATCH` | `/maps/{id}/cells` | Update specific cells (batch) |
| `POST` | `/maps/{id}/fill` | Flood fill |
| `GET` | `/maps/{id}/ops` | Edit operation history |
| `POST` | `/maps/{id}/undo` | Undo last operation |
| `POST` | `/maps/{id}/redo` | Redo |
| `GET` | `/maps/tileset` | Tileset atlas metadata |
| `GET` | `/maps/tileset/image/{chapter_id}` | Tileset PNG |
| `GET` | `/maps/rom/{region}` | Read current map from ROM |
| `POST` | `/maps/{id}/import-rom` | Import map grid from ROM region |

### 3.5 Battle / Character Editor

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/battle/scenarios` | List all 8 battle scenarios |
| `GET` | `/battle/scenarios/{id}` | Get scenario detail |
| `PUT` | `/battle/scenarios/{id}` | Update scenario fields |
| `GET` | `/battle/units` | List all unit definitions |
| `GET` | `/battle/units/{id}` | Get unit detail with skills |
| `PUT` | `/battle/units/{id}` | Create or update unit |
| `DELETE` | `/battle/units/{id}` | Delete unit |
| `GET` | `/battle/unit-id-map` | ROM unit ID mapping (64 entries) |
| `GET` | `/battle/placements/{episode_id}` | Get placements |
| `PUT` | `/battle/placements/{episode_id}` | Set placements |
| `POST` | `/battle/validate/{episode_id}` | Validate battle config |

### 3.6 Story / Chapter Editor

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/story/episodes` | List all episodes |
| `GET` | `/story/episodes/{id}` | Get episode with beats |
| `PUT` | `/story/episodes/{id}` | Create or update episode |
| `DELETE` | `/story/episodes/{id}` | Delete episode |
| `GET` | `/story/episodes/{id}/beats` | Get ordered beat list |
| `PUT` | `/story/episodes/{id}/beats` | Replace beat list |
| `PATCH` | `/story/episodes/{id}/beats/{beat_id}` | Update single beat |
| `POST` | `/story/episodes/{id}/reorder` | Reorder beats |

### 3.7 Audio Preview

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/audio/samples` | List all extracted audio samples |
| `GET` | `/audio/samples/{index}` | Get sample metadata |
| `GET` | `/audio/samples/{index}/wav` | Download WAV file |

### 3.8 Build Pipeline

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/build/trigger` | Queue a new build |
| `GET` | `/build/queue` | Current queue status |
| `GET` | `/build/{id}` | Build detail + report |
| `GET` | `/build/{id}/log` | Build log (streamed) |
| `GET` | `/build/{id}/rom` | Download built ROM |
| `GET` | `/build/{id}/test-report` | Automated test results |
| `GET` | `/build/history` | All builds (paginated) |
| `POST` | `/build/{id}/rerun-tests` | Re-run tests on existing build |

### 3.9 User Management (Admin only)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/users` | List all users |
| `POST` | `/users` | Create user (returns generated token) |
| `PUT` | `/users/{id}` | Update user profile/role |
| `DELETE` | `/users/{id}` | Deactivate user |
| `POST` | `/users/{id}/reset-token` | Generate new token |

---

## 4. WebSocket Protocol

### Connection

```
wss://14.103.49.74/ws?token=<bearer_token>
```

### Message Format

```typescript
// Client -> Server
interface ClientMessage {
  type: string;
  room?: string;
  payload: any;
  request_id?: string;
}

// Server -> Client
interface ServerMessage {
  type: string;
  room?: string;
  payload: any;
  request_id?: string;
  sender?: {id: number, display_name: string};
  timestamp: string;    // ISO 8601
}
```

### Room Management

| Type | Direction | Payload | Description |
|------|-----------|---------|-------------|
| `join_room` | C->S | `{room: "dialogue"}` | Join a resource channel |
| `leave_room` | C->S | `{room: "dialogue"}` | Leave |
| `room_joined` | S->C | `{room, users: [...]}` | Confirmation + current users |
| `user_joined` | S->C (broadcast) | `{room, user}` | Another user joined |
| `user_left` | S->C (broadcast) | `{room, user}` | Another user left |

Valid rooms: `dialogue`, `map:{map_id}`, `battle`, `story:{episode_id}`, `build`

### Dialogue Editing Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `dialogue:edit` | C->S | User edits dialogue text |
| `dialogue:edited` | S->C (broadcast) | Broadcast edit |
| `dialogue:cursor` | C->S | User is viewing this entry |
| `dialogue:cursors` | S->C (broadcast) | Current cursors |
| `dialogue:lock` | C->S | Request edit lock |
| `dialogue:locked` | S->C | Lock granted/denied |
| `dialogue:unlock` | C->S | Release edit lock |

### Map Editing Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `map:paint` | C->S | Paint cells |
| `map:painted` | S->C (broadcast) | Broadcast paint |
| `map:fill` | C->S | Flood fill |
| `map:filled` | S->C (broadcast) | Broadcast fill result |
| `map:undo` | C->S | Undo last own operation |
| `map:undone` | S->C (broadcast) | Broadcast undo |
| `map:cursor` | C->S | User cursor position |
| `map:cursors` | S->C (broadcast) | All cursors |

### Build Pipeline Messages

| Type | Direction | Description |
|------|-----------|-------------|
| `build:triggered` | S->C (broadcast) | New build queued |
| `build:started` | S->C (broadcast) | Build started |
| `build:log` | S->C (broadcast) | Streaming log line |
| `build:finished` | S->C (broadcast) | Build complete |

### Conflict Resolution

Last-writer-wins with advisory locks:
1. Client sends `dialogue:lock` when editing begins
2. Server grants lock for 5 minutes (renewable)
3. Other clients see lock indicator but are **not blocked** -- UI shows warning
4. Simultaneous edits: later write wins, earlier user receives `conflict` message
5. Map editing: cell-level granularity means conflicts are rare; different-cell edits merge automatically

### Heartbeat

Client sends `ping` every 30 seconds. Server disconnects after 3 missed pings (90s timeout).

---

## 5. Frontend Component Tree

```
App.vue
  AppLayout.vue
    HeaderBar.vue                    -- logo, user menu, language switch
    SideNav.vue                      -- module navigation
    NotificationToast.vue            -- global notifications

  router-view:

    DashboardView.vue
      ProjectStatsCard.vue
      RecentBuildsCard.vue
      ActiveUsersCard.vue

    DialogueEditorView.vue
      DialogueGroupList.vue          -- 305 groups sidebar (virtual scrolled)
      DialogueEntryEditor.vue
        TextInputField.vue           -- textarea with live byte counter
        EncodingInfo.vue             -- encoding, bytes used/max, strategy
        ByteHexPreview.vue           -- hex preview of encoded text
        WarningBanner.vue            -- overflow / encoding errors
      DialogueBulkImport.vue
      DialogueHistoryPanel.vue

    MapEditorView.vue
      MapToolbar.vue                 -- tool selection, flip toggles
      MapCanvas.vue                  -- HTML5 Canvas, 32x32 grid
        CanvasRenderer.ts
        GridOverlay.ts
        CursorOverlay.ts             -- other users' cursors
      TilePalette.vue               -- 312 tile thumbnails
      MapPropertiesPanel.vue
      UndoRedoBar.vue

    BattleEditorView.vue
      ScenarioSelector.vue           -- 8 scenario tabs
      ScenarioDetailPanel.vue
      UnitListPanel.vue
      UnitDetailEditor.vue           -- stats form + skill slots
      BattleGridPreview.vue          -- unit placement preview (canvas)
      UnitPlacementEditor.vue

    StoryEditorView.vue
      EpisodeList.vue
      EpisodeEditor.vue
      BeatTimeline.vue               -- ordered beat list (drag to reorder)
      BranchingEditor.vue            -- win/lose condition editor

    AudioPreviewView.vue
      SampleList.vue                 -- 10 sample cards
      AudioPlayer.vue

    BuildView.vue
      BuildTriggerPanel.vue
      BuildQueueStatus.vue
      BuildLogViewer.vue             -- streaming log
      BuildHistoryTable.vue
      TestResultPanel.vue            -- 17 tests, pass/fail
      RomDownloadButton.vue

    AdminView.vue (admin only)
      UserManagementTable.vue
      CreateUserDialog.vue
      TokenResetDialog.vue
```

### Pinia Stores

```
stores/
  useAuthStore.ts        -- token, user, login/logout
  useDialogueStore.ts    -- bank entries, content, groups, encoding cache
  useMapStore.ts         -- map definitions, current grid, undo stack
  useBattleStore.ts      -- scenarios, units, placements
  useStoryStore.ts       -- episodes, beats
  useBuildStore.ts       -- build queue, history, current build
  useWebSocketStore.ts   -- connection state, room management, message dispatch
  useNotificationStore.ts -- toast queue
```

### Composables

```
composables/
  useEncoding.ts         -- cp932 byte counting via precomputed lookup table (~80 KB)
  useUndoRedo.ts         -- generic undo/redo stack
  useCanvasTools.ts      -- paint, fill, select for map canvas
  useWebSocket.ts        -- WS connection, auto-reconnect, room join/leave
  useEditLock.ts         -- advisory lock acquisition/release
  useI18n.ts             -- Vue i18n integration
```

---

## 6. Build Queue Design

### Architecture

Single-threaded async task runner. ROM is a single file so only one build can run at a time.

```python
class BuildQueue:
    def __init__(self, db, rom_dir, tools_dir):
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[int] = asyncio.Queue(maxsize=10)

    async def enqueue(self, user_id, run_tests, note) -> int:
        # 1. Write content files from SQLite to disk
        # 2. Create builds row (status='queued')
        # 3. Put build_id into queue
        # 4. Broadcast 'build:triggered' via WS

    async def run_worker(self):
        while True:
            build_id = await self._queue.get()
            async with self._lock:
                await self._execute_build(build_id)

    async def _execute_build(self, build_id):
        # 1. Update status to 'running', broadcast 'build:started'
        # 2. Flush SQLite content to JSON files on disk
        # 3. Call build_mod.build() -- imported as library
        # 4. Parse build report
        # 5. If run_tests: run automated_test.py via subprocess
        # 6. Copy output ROM to data/builds/{build_id}/
        # 7. Update builds row, broadcast 'build:finished'
```

### Content Flush Strategy

Before each build, convert SQLite state to JSON files that existing tools expect:

1. `dialogue_bank_entries` -> `sequel/content/text/dialogue-bank.json`
2. `dialogue_content` -> `sequel/content/text/dialogue-patches.json`
3. episodes + beats -> `sequel/content/story/episode-*.json`
4. map grid -> map spec JSON
5. unit definitions + placements -> `sequel/content/units/sequel-units.json`
6. Reconstruct `sequel/patches/manifest.json` from enabled content

**SQLite is the source of truth.** JSON files on disk are transient build artifacts. Existing tools work unchanged.

### Queue Limits

- Maximum queue depth: 10 (reject with 429 if full)
- Build timeout: 120 seconds
- ROM file lock: `flock` during build
- Cooldown: minimum 5 seconds between builds by the same user

---

## 7. File Storage Strategy

```
/opt/naruto-editor/
  rom/
    base.gba                               # immutable (read-only mount)
    base.gba.sha1
  data/
    editor.db                              # SQLite (WAL mode)
    builds/{build_id}/
      naruto-sequel-dev.gba
      build-report.json
      test-report.json
      manifest-snapshot.json
    tiles/battle_tileset_00..07.png         # pre-extracted
    audio/*.wav                             # pre-extracted
    content/                                # transient JSON (flushed before build)
```

### Storage Budget

| Item | Size | Notes |
|------|------|-------|
| Base ROM | 6 MB | read-only |
| SQLite DB | ~5 MB | all content + history |
| Per build | ~7 MB | ROM + reports |
| 100 builds | 700 MB | retention: keep last 50 |
| Tile PNGs | ~200 KB | 8 files |
| Audio WAVs | ~4 MB | 10 files |
| Frontend dist | ~2 MB | gzipped |

Retention: auto-delete builds older than 30 days, keep 50 most recent.

---

## 8. Authentication Design

### Token-Based (Small Team, 3-5 Users)

1. Admin creates users via CLI or admin panel, generating random 32-byte token
2. Token hashed (SHA-256) before storage; plaintext shown once at creation
3. All API: `Authorization: Bearer <token>`
4. WebSocket: `wss://host/ws?token=<token>`
5. Tokens do not expire but can be rotated by admin

### Roles

| Role | Permissions |
|------|------------|
| `admin` | All operations + user management |
| `editor` | All content operations + build trigger |
| `viewer` | Read-only access |

### Rate Limiting

60 requests/minute per user (API), 120 messages/minute per user (WebSocket).

---

## 9. Deployment Plan

### Docker Compose

```yaml
version: "3.9"
services:
  backend:
    build: {context: ., dockerfile: Dockerfile.backend}
    volumes:
      - ./rom:/opt/naruto-editor/rom:ro
      - editor-data:/opt/naruto-editor/data
    environment:
      - DATABASE_URL=sqlite:///opt/naruto-editor/data/editor.db
      - SECRET_KEY=${SECRET_KEY}
      - ROM_PATH=/opt/naruto-editor/rom/base.gba
    expose: ["8000"]
    deploy: {resources: {limits: {memory: 2G}}}

  frontend:
    build: {context: ./frontend, dockerfile: Dockerfile.frontend}
    expose: ["80"]
    deploy: {resources: {limits: {memory: 256M}}}

  nginx:
    image: nginx:1.25-alpine
    ports: ["443:443", "80:80"]
    volumes:
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - certs:/etc/letsencrypt:ro
    depends_on: [backend, frontend]

volumes:
  editor-data:
  certs:
```

### nginx Configuration

```nginx
upstream backend { server backend:8000; }
upstream frontend { server frontend:80; }

server {
    listen 443 ssl http2;
    server_name 14.103.49.74;

    ssl_certificate     /etc/letsencrypt/live/naruto-editor/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/naruto-editor/privkey.pem;

    client_max_body_size 10M;

    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }

    location /static/tiles/ {
        alias /opt/naruto-editor/data/tiles/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }

    location /static/audio/ {
        alias /opt/naruto-editor/data/audio/;
        expires 1h;
    }

    location / { proxy_pass http://frontend; }
}
```

Note: IP-only access (14.103.49.74) requires self-signed certificate. Switch to certbot when a domain is added.

---

## 10. Development Phases

### Phase 1: Foundation (2 weeks)

**Goal: Running backend with auth, database, and dialogue editor API + UI.**

1. FastAPI scaffold, SQLAlchemy models, Pydantic schemas
2. Auth middleware
3. Dialogue router + service (full CRUD + validate)
4. Seed script: import existing `dialogue-bank.json` and `dialogue-patches.json` into SQLite
5. Vue 3 + Vite project, router, Pinia
6. `DialogueEditorView` with `TextInputField`, `EncodingInfo`, `ByteHexPreview`
7. Client-side cp932 byte counter
8. API integration tests (pytest)

**Deliverable:** Browse dialogue groups, edit text, see real-time byte counts, save to SQLite.

### Phase 2: Build Pipeline + WebSocket (2 weeks)

**Goal: Trigger builds from UI, see streaming logs, download ROM.**

1. `BuildQueue` service with async worker
2. Content flush (SQLite -> JSON)
3. Integrate `build_mod.build()` as library call
4. Integrate `automated_test.py` as subprocess
5. Build router endpoints
6. WebSocket handler + hub
7. `build:*` WS messages
8. `BuildView` UI components
9. Docker deployment on target server
10. Build pipeline integration tests

**Deliverable:** Full build-test-download cycle from browser.

### Phase 3: Map Editor (3 weeks)

**Goal: Canvas-based tile map editor with undo/redo.**

1. Map router + service
2. ROM map reading via `import_map.read_map_from_rom()`
3. Tileset PNG serving
4. Cell PATCH + flood fill endpoints
5. Undo/redo via `map_edit_ops` table
6. `MapCanvas.vue` with HTML5 Canvas rendering
7. `TilePalette.vue` with 312 tiles
8. Paint, fill, select tools
9. Map WebSocket messages + collaborative cursors
10. E2E tests (Playwright)

**Deliverable:** Multi-user map editing with tile palette, tools, and undo/redo.

### Phase 4: Battle/Character + Story Editors (2 weeks)

**Goal: Unit/scenario editing and story beat management.**

1. Seed `battle_scenarios` from `BATTLE_SCENARIOS` constant
2. Seed `unit_definitions` from `UNIT_ID_NAMES`
3. Battle/unit CRUD endpoints
4. `BattleEditorView` with stats form and skill slots
5. Placement grid preview
6. Story/episode CRUD endpoints
7. `StoryEditorView` with beat timeline
8. Dialogue collaboration WebSocket + edit locking

**Deliverable:** Complete battle configuration and story structure editing.

### Phase 5: Audio + Polish + i18n (1 week)

**Goal: Audio preview, Chinese localization, UX polish.**

1. Audio preview with HTML5 player
2. zh-CN i18n for all UI strings
3. Dashboard view
4. Admin user management panel
5. Performance: virtual scrolling, canvas optimization
6. Build history retention
7. Security: CSP headers, rate limiting

**Deliverable:** Production-ready editor.

---

## 11. Error Handling

### Backend Error Model

```json
{
  "error": {
    "code": "DIALOGUE_ENCODING_ERROR",
    "message": "文本包含无法编码为cp932的字符: '😀'",
    "details": {"entry_id": "group0.main", "character": "😀", "position": 15}
  }
}
```

### Error Categories

| HTTP | Code Prefix | Description |
|------|-------------|-------------|
| 400 | `VALIDATION_*` | Invalid data |
| 401 | `AUTH_*` | Missing/invalid token |
| 403 | `FORBIDDEN_*` | Insufficient permissions |
| 404 | `NOT_FOUND_*` | Resource not found |
| 409 | `CONFLICT_*` | Edit conflict |
| 422 | `ENCODING_*` | cp932 encoding failure |
| 429 | `RATE_LIMIT_*` | Too many requests |
| 500 | `INTERNAL_*` | Server error |
| 503 | `BUILD_QUEUE_*` | Queue full |

### Logging

Python `logging` with structured JSON output. 10 MB per file, 5 backups, `/opt/naruto-editor/data/logs/`.

---

## 12. Testing Strategy

### Backend (pytest)

**Unit tests:**
- `test_dialogue_svc.py` (15+): cp932 encoding, overflow, strategy selection
- `test_map_svc.py` (10+): tile grid serialization, flood fill, validation
- `test_battle_svc.py` (8+): unit ID mapping, patch generation
- `test_build_svc.py` (5+): content flush, manifest generation
- `test_auth.py` (5+): token hashing, roles, rate limiting

**Integration tests:**
- `test_dialogue_api.py`: Full CRUD cycle
- `test_map_api.py`: Create map, PATCH cells, undo
- `test_build_api.py`: Trigger build, poll status, verify ROM
- `test_ws_protocol.py`: WS connect, join room, verify broadcast
- `test_full_pipeline.py`: Seed DB -> trigger build -> verify 17/17 tests pass

### Frontend (Vitest + Playwright)

**Unit:** `useEncoding`, `useUndoRedo`, `useCanvasTools`, Pinia stores
**Component:** `TextInputField`, `TilePalette`, `BuildTriggerPanel`
**E2E:** dialogue-edit, map-paint, build-cycle, multi-user collaboration

### Existing Tests

`tools/automated_test.py` (17 tests) runs unchanged as subprocess during each build. JSON output stored in `builds.test_json`.

---

## Appendix A: ROM Constants

| Constant | Value | Source |
|----------|-------|--------|
| ROM size | 6,291,456 bytes | `project.json` |
| ROM SHA-1 | `26f60795...` | `project.json` |
| Dialogue pointer table | `0x461CE8`-`0x4634B8` (1,524 entries) | `import_dialogue_var.py` |
| Free space | `0x5DFBEC`-`0x5FFFFF` (128 KB) | `import_dialogue_var.py` |
| Tile descriptor table | `0x596D5C` (312 x 16B) | `import_map.py` |
| Tilemap format | 32x32, 2B/entry, bits[9:0]=tile_id | `import_map.py` |
| Tilemap regions | 0x14D000, 0x195000, 0x1CB000, 0x1C2000, 0x1F1000 | `import_map.py` |
| Battle config | `0x53D910`, +4 header, 8 x 32B | `import_battle_config.py` |
| Unit ID table | `0x53F298`, u16[64] | `import_battle_config.py` |
| Audio sample rate | 13,379 Hz | `extract_audio.py` |
| GBA ROM base | `0x08000000` | multiple tools |

## Appendix B: Data Flow Diagrams

### Dialogue Edit Flow
```
User types text -> [Client] useEncoding.countBytes() -> display
    -> (on save) PUT /api/v1/dialogue/content/{id}
    -> [Server] dialogue_svc.validate_and_save()
        -> text.encode('cp932'), compare vs max_bytes, determine strategy
        -> save to dialogue_content, insert dialogue_history
    -> ws_hub.broadcast('dialogue:edited')
    -> [All Clients] useDialogueStore.applyRemoteEdit()
```

### Build Flow
```
User clicks "构建" -> POST /api/v1/build/trigger
    -> build_svc.enqueue() -> builds row (queued) -> broadcast 'build:triggered'
    -> [BuildWorker] content_io.flush_sqlite_to_json()
        -> write dialogue-bank.json, dialogue-patches.json, manifest.json
    -> build_mod.build(project_path) -> apply patches -> output ROM
    -> subprocess: automated_test.py --json-output
    -> copy ROM to data/builds/{id}/
    -> broadcast 'build:finished'
```

---

## Critical Files for Implementation

| File | Role |
|------|------|
| `tools/build_mod.py` | Core build pipeline, `build()` function, all patch application logic |
| `tools/import_dialogue.py` | Dialogue encoding (`build_patch()`, `import_dialogue()`) |
| `tools/import_dialogue_var.py` | Variable-length dialogue redirect pipeline |
| `tools/import_map.py` | Map format constants (`TILEMAP_REGIONS`), `read_map_from_rom()`, `generate_map_patch()` |
| `tools/import_battle_config.py` | `UNIT_ID_NAMES`, `BATTLE_SCENARIOS`, `resolve_battle_config_patches()` |
| `tools/extract_tileset.py` | Tileset PNG extraction (pre-generate for serving) |
| `tools/extract_audio.py` | Audio WAV extraction (pre-generate for serving) |
| `tools/automated_test.py` | 17 tests, run as subprocess during builds |

---

## Verification Plan

1. **Phase 1 验证:** 启动 FastAPI 服务，通过 pytest 运行对话 CRUD 集成测试，打开浏览器访问对话编辑器 UI，编辑一条对话，验证字节计数与服务端一致
2. **Phase 2 验证:** 在 UI 点击"构建"按钮，观察 WebSocket 推送的构建日志流，下载构建后的 ROM，用 mGBA 打开验证对话修改生效
3. **Phase 3 验证:** 打开地图编辑器，绘制瓦片，执行 undo/redo，触发构建并验证 ROM 中地图数据已更新
4. **Phase 4 验证:** 配置战斗角色属性和放置位置，修改剧情结构，构建后验证
5. **Phase 5 验证:** 试听音频，验证中文 UI 完整，测试多用户同时编辑场景
6. **全流程:** 从零开始：登录 -> 编辑对话 -> 编辑地图 -> 配置战斗 -> 构建 -> 下载 ROM -> mGBA 验证

---

# 附录 C：实现状态（2026-04-07 更新）

## 整体评估：约 35% 实现

| 模块 | 实现度 | 状态 | 说明 |
|------|--------|------|------|
| 对话 CRUD | ✅ 85% | 基本完成 | 缺 validate / bulk-import / export / free-space |
| 地图编辑器 | ⚠️ 40% | 基础CRUD | 缺 undo/redo / fill / ops历史 |
| 战斗配置 | ✅ 80% | 基本完成 | unit_positions 完整，battles/characters 齐全 |
| 技能列表 | ✅ 90% | 基本完成 | 仅列表，无 tree view |
| 剧情编辑 | ✅ 70% | 基本完成 | story_beats CRUD，有 episode 概念 |
| 音频预览 | ⚠️ 30% | 读取已有文件 | 需实现上传 + extract 联动 |
| 用户管理 | ⚠️ 50% | CRUD 存在 | 无 auth middleware，role 字段未强制 |
| 构建流水线 | ⚠️ 50% | 可触发 | 缺 queue 列表、build 记录表 |
| WebSocket | ⚠️ 20% | 仅 build WS | 缺协作编辑房间、用户感知、冲突解决 |
| 认证系统 | ❌ 0% | 未实现 | 无 JWT / login / middleware |
| 地图 undo/redo | ❌ 0% | 未实现 | map_edit_ops 表不存在 |
| 对话 undo/redo | ❌ 0% | 未实现 | dialogue_edit_ops 表不存在 |
| 项目统计 | ❌ 0% | 未实现 | /project/stats 不存在 |

## 实际数据库表（8张）

```
dialogues          — 对话条目（简化为单表，无 bank/content 分离）
units              — 战斗单位
skills             — 技能列表
story_beats        — 剧情节点
audio_files        — 音频文件索引
settings           — 键值设置
battle_configs     — 战斗配置
users              — 用户（含 role 字段，但无权限校验）
```

**SPEC 描述但未实现的表**：dialogue_bank_entries / dialogue_edit_ops / map_definitions / map_edit_ops / battle_scenarios / unit_definitions / episodes / episode_scenes / builds / build_patches / edit_locks

## 实际 API 路由

### 对话 `/api/dialogues`
- ✅ GET `/api/dialogues`
- ✅ GET `/api/dialogues/{key}`
- ✅ POST `/api/dialogues`
- ✅ PUT `/api/dialogues/{key}`
- ✅ DELETE `/api/dialogues/{key}`
- ✅ GET `/api/dialogues/{key}/byte-count`
- ❌ GET `/dialogue/bank` · POST `/dialogue/validate` · POST `/dialogue/bulk-import` · GET `/dialogue/export` · GET `/dialogue/free-space`

### 地图 `/api/maps`
- ✅ GET `/api/maps` · GET `/api/maps/{id}` · PUT `/api/maps/{id}`
- ❌ GET `/maps/{id}/grid`（实际内嵌在返回中）· POST `/maps/{id}/fill` · GET `/maps/{id}/ops` · POST `/maps/{id}/undo` · POST `/maps/{id}/redo`

### 战斗 `/api/battles`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

### 单位 `/api/units`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

### 角色 `/api/characters`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

### 技能 `/api/skills`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

### 剧情 `/api/story-beats`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

### 章节 `/api/chapters`
- ✅ GET/POST 存在

### 音频 `/api/audio-files`
- ✅ GET 存在（读取 build/audio/ 目录）

### 构建 `/api/build`
- ✅ POST `/api/build/trigger` · GET `/api/build/status` · GET `/api/build/download` · WS `/ws/build`
- ❌ GET `/build/queue`

### 用户 `/api/users`
- ✅ GET/POST/PUT/DELETE 完整 CRUD（但无权限校验）
- ❌ POST `/auth/login` · POST `/auth/logout` · GET `/auth/me`

### 单位位置 `/api/unit-positions`
- ✅ GET/POST/PUT/DELETE 完整 CRUD

## 未实现的 API（按优先级）

### P0 — 必须实现
1. **JWT 认证**：`POST /auth/login` · `POST /auth/logout` · `GET /auth/me` + 所有路由 auth middleware
2. **地图 undo/redo**：新增 `map_edit_ops` 表 + `POST /maps/{id}/undo` · `POST /maps/{id}/redo`
3. **构建队列状态**：`GET /api/build/queue` + `builds` 表

### P1 — 重要功能
4. **对话批量导入/导出**：`POST /dialogue/bulk-import` · `GET /dialogue/export`
5. **对话验证**：`POST /dialogue/validate`
6. **空闲空间报告**：`GET /dialogue/free-space`
7. **对话操作历史**：`dialogue_edit_ops` 表 + `GET /dialogue/history/{id}`
8. **地图操作历史**：`map_edit_ops` 表（现有 `operations` 字段存在，但未实现 undo/redo 逻辑）

### P2 — 协作功能
9. **WebSocket 协作房间**：`/ws/collaborate` · 房间感知 · 用户列表
10. **冲突解决**：last-write-wins 或 OT

### P3 — 锦上添花
11. **项目统计**：`GET /project/stats`
12. **地图 flood fill**：`POST /maps/{id}/fill`
13. **音频文件上传** + 触发 `extract_audio.py` 联动

