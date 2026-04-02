# Web Editor Phase 1 Specification

## Project Overview
- **Project**: Naruto GBA Sequel Web Editor
- **Phase**: 1 - Basic + Dialogue Editor
- **Stack**: FastAPI + Vue 3 + SQLite (WAL)

## Database Schema

### dialogues table
| Column | Type | Constraints |
|--------|------|-------------|
| id | INTEGER | PRIMARY KEY |
| key | TEXT | UNIQUE NOT NULL |
| speaker | TEXT | |
| text_ja | TEXT | |
| text_zh | TEXT | |
| chapter_id | INTEGER | |
| byte_count | INTEGER | |
| max_bytes | INTEGER | DEFAULT 255 |
| created_at | TEXT | DEFAULT CURRENT_TIMESTAMP |
| updated_at | TEXT | DEFAULT CURRENT_TIMESTAMP |

## API Endpoints

### GET /api/dialogues
- Query params: page, limit, search, chapter_id
- Returns: List of dialogues with byte_count calculated

### GET /api/dialogues/{key}
- Returns: Single dialogue

### POST /api/dialogues
- Body: key, speaker, text_ja, text_zh, chapter_id, max_bytes

### PUT /api/dialogues/{key}
- Body: speaker, text_ja, text_zh, chapter_id, max_bytes

### DELETE /api/dialogues/{key}

### GET /api/dialogues/{key}/byte-count
- Returns: { key, byte_count, max_bytes, remaining }

## Frontend Components

### DialogueListView.vue
- Search bar with enter key trigger
- Table listing all dialogues
- Create/Delete/Edit actions
- Modal for new dialogue creation

### DialogueEditorView.vue
- Two-column text input (Japanese/Chinese)
- Real-time byte count display
- Over-limit warning
- Save/Cancel actions

## Byte Count Logic
- UTF-8 encoding
- Total = len(text_ja) + len(text_zh)