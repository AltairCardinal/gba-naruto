/**
 * Mirrors of the FastAPI OpenAPI schema at /openapi.json.
 *
 * If the backend changes a response shape, regenerate from
 *   curl -s http://127.0.0.1:8000/openapi.json | jq '.components.schemas'
 * and update the type below. (We hand-write instead of using
 * openapi-typescript to keep the dependency surface small — these types
 * are the single source of truth for store response shapes.)
 */

export interface DialogueResponse {
  id: number
  key: string
  speaker: string | null
  text_ja: string | null
  text_zh: string | null
  chapter_id: number | null
  byte_count: number
  max_bytes: number
  created_at: string
  updated_at: string
}

export interface DialogueCreate {
  key: string
  speaker?: string | null
  text_ja?: string | null
  text_zh?: string | null
  chapter_id?: number | null
  max_bytes?: number | null
}

export interface DialogueUpdate {
  speaker?: string | null
  text_ja?: string | null
  text_zh?: string | null
  chapter_id?: number | null
  max_bytes?: number | null
}

export interface SkillResponse {
  id: number
  unit_id: number
  name: string
  name_ja: string | null
  name_zh: string | null
  description: string | null
  description_ja: string | null
  description_zh: string | null
  damage: number
  heal: number
  range_min: number
  range_max: number
  cost_hp: number
  cost_chakra: number
  effect_type: string | null
  created_at: string
  updated_at: string
}

export interface SkillCreate {
  unit_id: number
  name: string
  name_ja?: string | null
  name_zh?: string | null
  description?: string | null
  description_ja?: string | null
  description_zh?: string | null
  damage?: number | null
  heal?: number | null
  range_min?: number | null
  range_max?: number | null
  cost_hp?: number | null
  cost_chakra?: number | null
  effect_type?: string | null
}

export interface SkillUpdate {
  name?: string | null
  name_ja?: string | null
  name_zh?: string | null
  description?: string | null
  description_ja?: string | null
  description_zh?: string | null
  damage?: number | null
  heal?: number | null
  range_min?: number | null
  range_max?: number | null
  cost_hp?: number | null
  cost_chakra?: number | null
  effect_type?: string | null
}

export interface UnitResponse {
  id: number
  char_id: number
  name: string
  name_ja: string | null
  name_zh: string | null
  hp: number
  attack: number
  defense: number
  speed: number
  chapter_id: number | null
  map_id: string | null
  position_x: number | null
  position_y: number | null
  team: number
  created_at: string
  updated_at: string
}

export interface UnitCreate {
  char_id: number
  name: string
  name_ja?: string | null
  name_zh?: string | null
  hp?: number | null
  attack?: number | null
  defense?: number | null
  speed?: number | null
  chapter_id?: number | null
  map_id?: string | null
  position_x?: number | null
  position_y?: number | null
  team?: number | null
}

export interface UnitUpdate {
  char_id?: number | null
  name?: string | null
  name_ja?: string | null
  name_zh?: string | null
  hp?: number | null
  attack?: number | null
  defense?: number | null
  speed?: number | null
  chapter_id?: number | null
  map_id?: string | null
  position_x?: number | null
  position_y?: number | null
  team?: number | null
}

export interface StoryBeatResponse {
  id: number
  chapter_id: number
  beat_index: number
  beat_type: string
  title: string | null
  title_ja: string | null
  title_zh: string | null
  description: string | null
  description_ja: string | null
  description_zh: string | null
  trigger_type: string | null
  trigger_param: string | null
  dialogue_key: string | null
  battle_config_id: number | null
  map_id: string | null
  position_x: number | null
  position_y: number | null
  next_beat_id: number | null
  created_at: string
  updated_at: string
}

export interface StoryBeatCreate {
  chapter_id: number
  beat_index: number
  beat_type: string
  title?: string | null
  title_ja?: string | null
  title_zh?: string | null
  description?: string | null
  description_ja?: string | null
  description_zh?: string | null
  trigger_type?: string | null
  trigger_param?: string | null
  dialogue_key?: string | null
  battle_config_id?: number | null
  map_id?: string | null
  position_x?: number | null
  position_y?: number | null
  next_beat_id?: number | null
}

export interface StoryBeatUpdate {
  beat_index?: number | null
  beat_type?: string | null
  title?: string | null
  title_ja?: string | null
  title_zh?: string | null
  description?: string | null
  description_ja?: string | null
  description_zh?: string | null
  trigger_type?: string | null
  trigger_param?: string | null
  dialogue_key?: string | null
  battle_config_id?: number | null
  map_id?: string | null
  position_x?: number | null
  position_y?: number | null
  next_beat_id?: number | null
}

export interface BattleConfigResponse {
  id: number
  chapter_id: number | null
  scenario_id: number | null
  config_json: string | null
  created_at: string
  updated_at: string
}

export interface BattleConfigCreate {
  chapter_id?: number | null
  scenario_id?: number | null
  config_json?: string | null
}

export interface BattleConfigUpdate {
  chapter_id?: number | null
  scenario_id?: number | null
  config_json?: string | null
}

export interface LoginResponse {
  access_token: string
  token_type: string
  username: string
  role: string
}

export interface MeResponse {
  username: string
  role: string
  permissions: string[]
}

export interface BuildStatusResponse {
  build_id: string
  status: 'idle' | 'running' | 'done' | 'error' | string
  logs: string[]
  progress: number
  rom_path: string | null
  error?: string | null
}