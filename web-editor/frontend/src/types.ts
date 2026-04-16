export interface AppError {
  message: string
  code?: string
  status?: number
}

export interface BattleConfig {
  id: number
  name: string
  chapter_id?: number
  scenario_id?: number
  player_units?: string
  enemy_units?: string
  terrain_mod?: string
  turn_limit?: number
  win_condition?: string
  lose_condition?: string
  created_at?: string
  updated_at?: string
}

export interface Unit {
  id: number
  char_id: number
  name: string
  name_ja?: string
  name_zh?: string
  hp: number
  attack: number
  defense: number
  speed: number
  chapter_id?: number
  map_id?: string
  position_x?: number
  position_y?: number
  team: number
  created_at: string
  updated_at: string
}

export interface Skill {
  id: number
  unit_id: number
  name: string
  name_ja?: string
  name_zh?: string
  description?: string
  description_ja?: string
  description_zh?: string
  damage: number
  heal: number
  range_min: number
  range_max: number
  cost_hp: number
  cost_chakra: number
  effect_type?: string
  created_at: string
  updated_at: string
}

export interface StoryBeat {
  id: number
  chapter_id: number
  beat_index: number
  beat_type: string
  title?: string
  title_ja?: string
  title_zh?: string
  description?: string
  description_ja?: string
  description_zh?: string
  trigger_type?: string
  trigger_param?: string
  dialogue_key?: string
  battle_config_id?: number
  map_id?: string
  position_x?: number
  position_y?: number
  next_beat_id?: number
  created_at: string
  updated_at: string
}

export interface Dialogue {
  id: number
  key: string
  speaker?: string
  text_ja?: string
  text_zh?: string
  chapter_id?: number
  byte_count: number
  max_bytes: number
  created_at: string
  updated_at: string
}

export interface Character {
  id: number
  char_id: number
  name: string
  name_ja?: string
  name_zh?: string
  hp: number
  attack: number
  defense: number
  speed: number
  chapter_id?: number
  map_id?: string
  position_x?: number
  position_y?: number
  team: number
  created_at: string
  updated_at: string
}

export interface MapTile {
  tile_id: number
  hflip: boolean
  vflip: boolean
  palette_bank: number
}

export interface AudioFile {
  id: number
  name: string
  type: string
  rom_offset?: number
  size?: number
  duration_seconds?: number
  format?: string
  created_at: string
  updated_at: string
}
