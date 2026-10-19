local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or tonumber(value:gsub("^0[xX]", ""), 16)
end

local function write_file(path, payload, mode)
	local output = assert(io.open(path, mode or "w"))
	output:write(payload)
	output:close()
end

local output_dir =
	required_env("MGBA_MANUAL_BATTLE_OBSERVER_OUTPUT_DIR")
local battle_telemetry_address = assert(parse_number(required_env(
	"MGBA_MANUAL_BATTLE_OBSERVER_BATTLE_TELEMETRY_ADDRESS"
)))
local campaign_telemetry_address = assert(parse_number(required_env(
	"MGBA_MANUAL_BATTLE_OBSERVER_CAMPAIGN_TELEMETRY_ADDRESS"
)))
local assert_address = assert(parse_number(required_env(
	"MGBA_MANUAL_BATTLE_OBSERVER_ASSERT_ADDRESS"
)))
local trace_path = output_dir .. "/manual-battle-trace.jsonl"
local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local PHASE_TARGET_SELECTION = 8
local ACTION_TAIJUTSU = 5
local SASUKE_CHARACTER_ID = 2
local stall_threshold_frames = tonumber(
	os.getenv("MGBA_MANUAL_BATTLE_OBSERVER_STALL_FRAMES") or "180"
)
assert(stall_threshold_frames and stall_threshold_frames >= 60)

write_file(trace_path, "")

local frame = 0
local ready = false
local focus_armed = false
local focus_capture_written = false
local last_signature = ""
local last_change_frame = 0
local last_heartbeat_frame = 0
local last_combat_stage = -1
local last_presentation_busy = 0
local last_control_error = 0
local last_player_error = 0
local stall_latched = false
local stall_index = 0
local assert_hit = false

local function u32(offset)
	return emu:read32(battle_telemetry_address + offset)
end

local function campaign_u32(offset)
	return emu:read32(campaign_telemetry_address + offset)
end

local function read_battle()
	if u32(0) ~= BATTLE_TELEMETRY_MAGIC then
		return nil
	end
	return {
		battle_id = u32(4),
		phase = u32(8),
		round = u32(12),
		current_side = u32(16),
		selected_unit = u32(20),
		active_unit_count = u32(24),
		selected_command = u32(32),
		scene_frame = u32(44),
		cursor_x = u32(48),
		cursor_y = u32(52),
		last_control_error = u32(56),
		last_player_error = u32(60),
		render_stage = u32(64),
		presentation_busy = u32(68),
		selected_character_id = u32(72),
		action_index = u32(80),
		selected_action_id = u32(84),
		selected_action_error = u32(88),
		last_resolved_action_id = u32(92),
		selected_action_kind = u32(104),
		cursor_unit_id = u32(304),
		cursor_unit_active = u32(324),
		cursor_unit_hp = u32(328),
		presentation_combat_stage = u32(364),
		presentation_combat_stage_frame = u32(368),
		presentation_combat_impact_index = u32(372),
		presentation_combat_tracks = u32(376),
		presentation_combat_resource = u32(380),
		selected_unit_x = u32(384),
		selected_unit_y = u32(388),
		first_active_enemy_x = u32(392),
		first_active_enemy_y = u32(396),
		selected_action_effect_code = u32(400),
		selected_action_target_kind = u32(404),
		selected_unit_chakra = u32(408),
		move_preview_x = u32(412),
		move_preview_y = u32(416),
		selected_unit_hp = u32(612),
		selected_unit_max_hp = u32(616),
		sasuke_character_id = u32(424),
		sasuke_active = u32(472),
		sasuke_x = u32(520),
		sasuke_y = u32(568),
		sasuke_hp = u32(624),
		sasuke_chakra = u32(672),
		condition_outcome = u32(820),
	}
end

local function signature(battle, keys)
	return string.format(
		"%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d:%d",
		battle.phase,
		battle.round,
		battle.selected_unit,
		battle.selected_command,
		battle.cursor_x,
		battle.cursor_y,
		battle.selected_character_id,
		battle.selected_action_id,
		battle.selected_action_error,
		battle.last_resolved_action_id,
		battle.presentation_busy,
		battle.presentation_combat_stage,
		battle.presentation_combat_stage_frame,
		battle.last_control_error,
		battle.last_player_error,
		battle.render_stage,
		battle.cursor_unit_id,
		battle.cursor_unit_hp,
		keys
	)
end

local function trace_record(kind, battle, keys)
	local campaign_valid =
		campaign_u32(0) == CAMPAIGN_TELEMETRY_MAGIC
	write_file(
		trace_path,
		string.format(
			'{"observer_frame":%d,"emulator_frame":%d,"kind":"%s","keys":%u,"campaign_valid":%d,"scenario_id":%d,"campaign_error":%d,"battle_id":%d,"phase":%d,"round":%d,"current_side":%d,"scene_frame":%d,"selected_unit":%d,"selected_character_id":%d,"selected_command":%d,"cursor_x":%d,"cursor_y":%d,"cursor_unit_id":%d,"cursor_unit_active":%d,"cursor_unit_hp":%d,"action_index":%d,"selected_action_id":%d,"selected_action_kind":%d,"selected_action_error":%d,"selected_action_effect_code":%d,"selected_action_target_kind":%d,"last_resolved_action_id":%d,"presentation_busy":%d,"presentation_combat_stage":%d,"presentation_combat_stage_frame":%d,"presentation_combat_impact_index":%u,"presentation_combat_tracks":%d,"presentation_combat_resource":%d,"render_stage":%d,"last_control_error":%d,"last_player_error":%d,"selected_unit_x":%u,"selected_unit_y":%u,"selected_unit_hp":%u,"selected_unit_max_hp":%u,"selected_unit_chakra":%u,"move_preview_x":%u,"move_preview_y":%u,"first_active_enemy_x":%u,"first_active_enemy_y":%u,"sasuke_character_id":%d,"sasuke_active":%d,"sasuke_x":%u,"sasuke_y":%u,"sasuke_hp":%d,"sasuke_chakra":%d,"condition_outcome":%d,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X"}\n',
			frame,
			emu:currentFrame(),
			kind,
			keys,
			campaign_valid and 1 or 0,
			campaign_valid and campaign_u32(76) or 0,
			campaign_valid and campaign_u32(68) or 0,
			battle.battle_id,
			battle.phase,
			battle.round,
			battle.current_side,
			battle.scene_frame,
			battle.selected_unit,
			battle.selected_character_id,
			battle.selected_command,
			battle.cursor_x,
			battle.cursor_y,
			battle.cursor_unit_id,
			battle.cursor_unit_active,
			battle.cursor_unit_hp,
			battle.action_index,
			battle.selected_action_id,
			battle.selected_action_kind,
			battle.selected_action_error,
			battle.selected_action_effect_code,
			battle.selected_action_target_kind,
			battle.last_resolved_action_id,
			battle.presentation_busy,
			battle.presentation_combat_stage,
			battle.presentation_combat_stage_frame,
			battle.presentation_combat_impact_index,
			battle.presentation_combat_tracks,
			battle.presentation_combat_resource,
			battle.render_stage,
			battle.last_control_error,
			battle.last_player_error,
			battle.selected_unit_x,
			battle.selected_unit_y,
			battle.selected_unit_hp,
			battle.selected_unit_max_hp,
			battle.selected_unit_chakra,
			battle.move_preview_x,
			battle.move_preview_y,
			battle.first_active_enemy_x,
			battle.first_active_enemy_y,
			battle.sasuke_character_id,
			battle.sasuke_active,
			battle.sasuke_x,
			battle.sasuke_y,
			battle.sasuke_hp,
			battle.sasuke_chakra,
			battle.condition_outcome,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		),
		"a"
	)
end

local function write_stall_snapshot(battle, keys)
	stall_index = stall_index + 1
	local tag = string.format("stall-snapshot-%02d", stall_index)
	trace_record("stall", battle, keys)
	emu:screenshot(output_dir .. "/" .. tag .. ".png")
	assert(emu:saveStateFile(output_dir .. "/" .. tag .. ".ss9"))
	write_file(
		output_dir .. "/" .. tag .. ".json",
		string.format(
			'{"observer_frame":%d,"phase":%d,"selected_character_id":%d,"selected_action_id":%d,"last_resolved_action_id":%d,"presentation_busy":%d,"presentation_combat_stage":%d,"presentation_combat_stage_frame":%d,"render_stage":%d,"last_control_error":%d,"last_player_error":%d,"keys":%u,"status":"stall-candidate"}',
			frame,
			battle.phase,
			battle.selected_character_id,
			battle.selected_action_id,
			battle.last_resolved_action_id,
			battle.presentation_busy,
			battle.presentation_combat_stage,
			battle.presentation_combat_stage_frame,
			battle.render_stage,
			battle.last_control_error,
			battle.last_player_error,
			keys
		)
	)
end

local function on_assert()
	if assert_hit then
		return
	end
	assert_hit = true

	local battle = read_battle()
	if battle then
		trace_record("assert-hit", battle, emu:getKeys())
	else
		write_file(
			trace_path,
			string.format(
				'{"observer_frame":%d,"emulator_frame":%d,"kind":"assert-hit","battle_valid":0,"pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","r0":"0x%08X","r1":"0x%08X","r2":"0x%08X","r3":"0x%08X"}\n',
				frame,
				emu:currentFrame(),
				emu:readRegister("pc"),
				emu:readRegister("lr"),
				emu:readRegister("sp"),
				emu:readRegister("r0"),
				emu:readRegister("r1"),
				emu:readRegister("r2"),
				emu:readRegister("r3")
			),
			"a"
		)
	end

	write_file(
		output_dir .. "/assert-hit.json",
		string.format(
			'{"observer_frame":%d,"emulator_frame":%d,"assert_address":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","r0":"0x%08X","r1":"0x%08X","r2":"0x%08X","r3":"0x%08X","status":"assert-hit"}',
			frame,
			emu:currentFrame(),
			assert_address,
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp"),
			emu:readRegister("r0"),
			emu:readRegister("r1"),
			emu:readRegister("r2"),
			emu:readRegister("r3")
		)
	)
	emu:screenshot(output_dir .. "/assert-hit.png")
	assert(emu:saveStateFile(output_dir .. "/assert-hit.ss9"))
end

emu:setBreakpoint(on_assert, assert_address)

callbacks:add("frame", function()
	frame = frame + 1
	local battle = read_battle()
	if not battle then
		if frame - last_heartbeat_frame >= 60 then
			last_heartbeat_frame = frame
			write_file(
				trace_path,
				string.format(
					'{"observer_frame":%d,"emulator_frame":%d,"kind":"waiting-for-telemetry","keys":%u,"battle_magic":"0x%08X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X"}\n',
					frame,
					emu:currentFrame(),
					emu:getKeys(),
					u32(0),
					emu:readRegister("pc"),
					emu:readRegister("lr"),
					emu:readRegister("sp")
				),
				"a"
			)
		end
		return
	end

	local keys = emu:getKeys()
	if not ready then
		ready = true
		write_file(
			output_dir .. "/observer-ready.json",
			string.format(
				'{"observer_frame":%d,"battle_telemetry_address":"0x%08X","campaign_telemetry_address":"0x%08X","battle_id":%d,"phase":%d,"scenario_id":%d,"status":"observer-ready"}',
				frame,
				battle_telemetry_address,
				campaign_telemetry_address,
				battle.battle_id,
				battle.phase,
				campaign_u32(0) == CAMPAIGN_TELEMETRY_MAGIC and
					campaign_u32(76) or 0
			)
		)
		trace_record("ready", battle, keys)
	end

	if battle.selected_character_id == SASUKE_CHARACTER_ID and
			battle.selected_action_id == ACTION_TAIJUTSU and
			battle.phase == PHASE_TARGET_SELECTION then
		focus_armed = true
	end
	if focus_armed and not focus_capture_written then
		focus_capture_written = true
		trace_record("sasuke-taijutsu-focus-armed", battle, keys)
		emu:screenshot(output_dir .. "/sasuke-taijutsu-focus-armed.png")
	end

	if focus_armed and
			battle.presentation_busy == 1 and
			last_presentation_busy == 0 then
		trace_record("presentation-start", battle, keys)
		emu:screenshot(output_dir .. "/presentation-start.png")
	end
	if focus_armed and
			battle.presentation_busy == 1 and
			battle.presentation_combat_stage ~= last_combat_stage then
		last_combat_stage = battle.presentation_combat_stage
		trace_record("presentation-stage", battle, keys)
		emu:screenshot(
			output_dir .. string.format(
				"/presentation-stage-%d.png",
				battle.presentation_combat_stage
			)
		)
	end
	if battle.last_control_error ~= last_control_error or
			battle.last_player_error ~= last_player_error then
		trace_record("error-change", battle, keys)
		emu:screenshot(output_dir .. "/error-change.png")
	end

	local current_signature = signature(battle, keys)
	if current_signature ~= last_signature then
		last_signature = current_signature
		last_change_frame = frame
		stall_latched = false
		trace_record("state-change", battle, keys)
	elseif frame - last_heartbeat_frame >= 60 then
		last_heartbeat_frame = frame
		trace_record("heartbeat", battle, keys)
	end

	if focus_armed and not stall_latched and
			frame - last_change_frame >= stall_threshold_frames then
		stall_latched = true
		write_stall_snapshot(battle, keys)
	end

	last_presentation_busy = battle.presentation_busy
	last_control_error = battle.last_control_error
	last_player_error = battle.last_player_error
end)
