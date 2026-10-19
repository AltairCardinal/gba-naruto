local function required_env(name)
	local value = os.getenv(name)
	assert(value and value ~= "", "missing environment variable " .. name)
	return value
end

local function parse_number(value)
	return tonumber(value) or tonumber(value:gsub("^0[xX]", ""), 16)
end

local function env_number_or(name, fallback)
	local value = os.getenv(name)
	if value and value ~= "" then
		return assert(parse_number(value))
	end
	return fallback
end

local function write_file(path, payload)
	local output = assert(io.open(path, "w"))
	output:write(payload)
	output:close()
end

local output_dir = required_env(
	"MGBA_BATTLE_PREPARATION_INPUT_OUTPUT_DIR"
)
local done_marker_path = required_env(
	"MGBA_BATTLE_PREPARATION_INPUT_DONE_MARKER"
)
local battle_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_PREPARATION_INPUT_BATTLE_TELEMETRY_ADDRESS"
)))
local campaign_telemetry_address = assert(parse_number(required_env(
	"MGBA_BATTLE_PREPARATION_INPUT_CAMPAIGN_TELEMETRY_ADDRESS"
)))
local keypad_buffer_address = assert(parse_number(required_env(
	"MGBA_BATTLE_PREPARATION_INPUT_KEYPAD_BUFFER_ADDRESS"
)))
local capture_frame = env_number_or(
	"MGBA_BATTLE_PREPARATION_INPUT_CAPTURE_FRAME",
	240
)

local BATTLE_TELEMETRY_MAGIC = 0x4B42544C
local CAMPAIGN_TELEMETRY_MAGIC = 0x4B43414D
local KEY_INPUT_ADDRESS = 0x04000130
local MAXMOD_LAYER_MAIN_ADDRESS = env_number_or(
	"MGBA_MAXMOD_LAYER_MAIN_ADDRESS",
	0x030028D4
)
local MAXMOD_LAYER_MAIN_SONG_ADDRESS_OFFSET = 0x14
local MAXMOD_LAYER_MAIN_PATTERN_READ_OFFSET = 0x24
local MAXMOD_LAYER_MAIN_VALID_OFFSET = 0x29
local MAXMOD_INITIALIZED_ADDRESS = env_number_or(
	"MGBA_MAXMOD_INITIALIZED_ADDRESS",
	0x030029BC
)
local MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS = env_number_or(
	"MGBA_MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS",
	0x030029AC
)
local MAXMOD_WAVE_BUFFER_POINTER_ADDRESS = env_number_or(
	"MGBA_MAXMOD_WAVE_BUFFER_POINTER_ADDRESS",
	0x030029DC
)
local MAXMOD_MIX_LENGTH_ADDRESS = env_number_or(
	"MGBA_MAXMOD_MIX_LENGTH_ADDRESS",
	0x030029E8
)
local MAXMOD_MIX_CHANNELS_POINTER_ADDRESS = env_number_or(
	"MGBA_MAXMOD_MIX_CHANNELS_POINTER_ADDRESS",
	0x030029F0
)
local MAXMOD_CHANNEL_MASK_ADDRESS = 0x03002870
local MAXMOD_CURRENT_LAYER_CHANNEL_COUNT_ADDRESS = 0x03002879
local MAXMOD_MODULE_CHANNEL_COUNT_ADDRESS = 0x030029B0
local MAXMOD_MODULE_CHANNELS_POINTER_ADDRESS = 0x030029B4
local MAXMOD_ACTIVE_CHANNELS_POINTER_ADDRESS = 0x030029B8
local MAXMOD_MODULE_CHANNEL_SIZE = 40
local MAXMOD_ACTIVE_CHANNEL_SIZE = 28
local MAXMOD_ACTIVE_CHANNEL_TYPE_OFFSET = 17
local SOUNDCNT_H_ADDRESS = 0x04000082

local function detect_maxmod_layer_main_address()
	local ranges = {
		{ 0x03000000, 0x03007FC0 },
		{ 0x02000000, 0x0203FFC0 },
	}
	for _, range in ipairs(ranges) do
		for address = range[1], range[2], 4 do
			local song_address = emu:read32(
				address +
					MAXMOD_LAYER_MAIN_SONG_ADDRESS_OFFSET
			)
			if emu:read8(address + 6) == 1 and
					emu:read16(address + 52) == 1024 and
					song_address >= 0x08000000 and
					song_address < 0x0A000000 then
				return address
			end
		end
	end
	return MAXMOD_LAYER_MAIN_ADDRESS
end

local frame = 0
local complete = false
local key_input_before = 0
local key_input_b_held = 0
local key_input_b_released = 0
local key_input_a_held = 0
local key_input_a_released = 0
local keypad_held_after_b = 0
local keypad_pressed_after_b = 0
local keypad_held_after_a = 0
local keypad_pressed_after_a = 0

callbacks:add("frame", function()
	if complete then
		return
	end
	frame = frame + 1

	if frame == 120 then
		emu:screenshot(output_dir .. "/before-input.png")
		key_input_before = emu:read16(KEY_INPUT_ADDRESS)
		emu:addKey(C.GBA_KEY.B)
	elseif frame == 121 then
		key_input_b_held = emu:read16(KEY_INPUT_ADDRESS)
	elseif frame == 122 then
		keypad_held_after_b =
			emu:read32(keypad_buffer_address + 8)
		keypad_pressed_after_b =
			emu:read32(keypad_buffer_address + 12)
	elseif frame == 126 then
		emu:clearKey(C.GBA_KEY.B)
	elseif frame == 127 then
		key_input_b_released = emu:read16(KEY_INPUT_ADDRESS)
	elseif frame == 140 then
		emu:addKey(C.GBA_KEY.A)
	elseif frame == 141 then
		key_input_a_held = emu:read16(KEY_INPUT_ADDRESS)
	elseif frame == 142 then
		keypad_held_after_a =
			emu:read32(keypad_buffer_address + 8)
		keypad_pressed_after_a =
			emu:read32(keypad_buffer_address + 12)
	elseif frame == 146 then
		emu:clearKey(C.GBA_KEY.A)
	elseif frame == 147 then
		key_input_a_released = emu:read16(KEY_INPUT_ADDRESS)
	elseif frame == capture_frame then
		emu:screenshot(output_dir .. "/after-input.png")
		local battle_magic =
			emu:read32(battle_telemetry_address)
		local campaign_magic =
			emu:read32(campaign_telemetry_address)
		local maxmod_layer_main_address =
			detect_maxmod_layer_main_address()
		local maxmod_address_delta =
			maxmod_layer_main_address -
				MAXMOD_LAYER_MAIN_ADDRESS
		local maxmod_num_active_channels =
			emu:read32(
				MAXMOD_NUM_ACTIVE_CHANNELS_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_wave_buffer_address =
			emu:read32(
				MAXMOD_WAVE_BUFFER_POINTER_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_mix_length =
			emu:read32(
				MAXMOD_MIX_LENGTH_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_mix_channels_address =
			emu:read32(
				MAXMOD_MIX_CHANNELS_POINTER_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_channel_mask =
			emu:read32(
				MAXMOD_CHANNEL_MASK_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_module_channel_count =
			emu:read32(
				MAXMOD_MODULE_CHANNEL_COUNT_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_current_layer_channel_count =
			emu:read8(
				MAXMOD_CURRENT_LAYER_CHANNEL_COUNT_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_module_channels_address =
			emu:read32(
				MAXMOD_MODULE_CHANNELS_POINTER_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_active_channels_address =
			emu:read32(
				MAXMOD_ACTIVE_CHANNELS_POINTER_ADDRESS +
					maxmod_address_delta
			)
		local maxmod_allocated_module_channels = 0
		local maxmod_module_channels_with_flags = 0
		local maxmod_module_channels_with_instrument = 0
		local maxmod_first_allocated_module_index = -1
		local maxmod_first_allocated_mix_index = -1
		for index = 0, maxmod_module_channel_count - 1 do
			local module_channel_address =
				maxmod_module_channels_address +
					index * MAXMOD_MODULE_CHANNEL_SIZE
			local allocated_mix_index =
				emu:read8(module_channel_address)
			if allocated_mix_index ~= 255 then
				maxmod_allocated_module_channels =
					maxmod_allocated_module_channels + 1
				if maxmod_first_allocated_module_index < 0 then
					maxmod_first_allocated_module_index =
						index
					maxmod_first_allocated_mix_index =
						allocated_mix_index
				end
			end
			if emu:read8(module_channel_address + 1) ~= 0 then
				maxmod_module_channels_with_flags =
					maxmod_module_channels_with_flags + 1
			end
			if emu:read8(module_channel_address + 9) ~= 0 then
				maxmod_module_channels_with_instrument =
					maxmod_module_channels_with_instrument + 1
			end
		end
		local maxmod_disabled_active_channels = 0
		local maxmod_reserved_active_channels = 0
		local maxmod_background_active_channels = 0
		local maxmod_foreground_active_channels = 0
		local maxmod_custom_active_channels = 0
		for index = 0, maxmod_num_active_channels - 1 do
			local channel_type = emu:read8(
				maxmod_active_channels_address +
					index * MAXMOD_ACTIVE_CHANNEL_SIZE +
					MAXMOD_ACTIVE_CHANNEL_TYPE_OFFSET
			)
			if channel_type == 0 then
				maxmod_disabled_active_channels =
					maxmod_disabled_active_channels + 1
			elseif channel_type == 1 then
				maxmod_reserved_active_channels =
					maxmod_reserved_active_channels + 1
			elseif channel_type == 2 then
				maxmod_background_active_channels =
					maxmod_background_active_channels + 1
			elseif channel_type == 3 then
				maxmod_foreground_active_channels =
					maxmod_foreground_active_channels + 1
			elseif channel_type == 4 then
				maxmod_custom_active_channels =
					maxmod_custom_active_channels + 1
			end
		end
		local maxmod_wave_nonzero_bytes = 0
		for offset = 0, maxmod_mix_length * 4 - 1 do
			if emu:read8(
					maxmod_wave_buffer_address + offset
			) ~= 0 then
				maxmod_wave_nonzero_bytes =
					maxmod_wave_nonzero_bytes + 1
			end
		end
		local maxmod_active_mix_channels = 0
		local maxmod_mix_volume_sum = 0
		for index = 0, maxmod_num_active_channels - 1 do
			local channel_address =
				maxmod_mix_channels_address + index * 16
			if emu:read32(channel_address) < 0x80000000 then
				maxmod_active_mix_channels =
					maxmod_active_mix_channels + 1
				maxmod_mix_volume_sum =
					maxmod_mix_volume_sum +
						emu:read8(channel_address + 8)
			end
		end
		local payload = string.format(
			'{"capture_frame":%d,"key_input_before":"0x%04X","key_input_b_held":"0x%04X","key_input_b_released":"0x%04X","key_input_a_held":"0x%04X","key_input_a_released":"0x%04X","keypad_held_after_b":"0x%08X","keypad_pressed_after_b":"0x%08X","keypad_held_after_a":"0x%08X","keypad_pressed_after_a":"0x%08X","battle_magic":"0x%08X","battle_id":%d,"battle_phase":%d,"campaign_magic":"0x%08X","campaign_scenario_id":%d,"maxmod_layer_main_address":"0x%08X","maxmod_initialized":%d,"maxmod_tick":%d,"maxmod_row":%d,"maxmod_position":%d,"maxmod_isplaying":%d,"maxmod_song_address":"0x%08X","maxmod_pattern_read_address":"0x%08X","maxmod_valid":%d,"maxmod_global_volume":%d,"maxmod_layer_volume":%d,"maxmod_num_active_channels":%d,"maxmod_channel_mask":"0x%08X","maxmod_module_channel_count":%d,"maxmod_current_layer_channel_count":%d,"maxmod_module_channels_address":"0x%08X","maxmod_allocated_module_channels":%d,"maxmod_module_channels_with_flags":%d,"maxmod_module_channels_with_instrument":%d,"maxmod_first_allocated_module_index":%d,"maxmod_first_allocated_mix_index":%d,"maxmod_active_channels_address":"0x%08X","maxmod_disabled_active_channels":%d,"maxmod_reserved_active_channels":%d,"maxmod_background_active_channels":%d,"maxmod_foreground_active_channels":%d,"maxmod_custom_active_channels":%d,"maxmod_mix_length":%d,"maxmod_wave_buffer_address":"0x%08X","maxmod_wave_nonzero_bytes":%d,"maxmod_mix_channels_address":"0x%08X","maxmod_active_mix_channels":%d,"maxmod_mix_volume_sum":%d,"soundcnt_h":"0x%04X","pc":"0x%08X","lr":"0x%08X","sp":"0x%08X","status":"preparation-input-diagnostic"}',
			frame,
			key_input_before,
			key_input_b_held,
			key_input_b_released,
			key_input_a_held,
			key_input_a_released,
			keypad_held_after_b,
			keypad_pressed_after_b,
			keypad_held_after_a,
			keypad_pressed_after_a,
			battle_magic,
			battle_magic == BATTLE_TELEMETRY_MAGIC and
				emu:read32(battle_telemetry_address + 4) or 0,
			battle_magic == BATTLE_TELEMETRY_MAGIC and
				emu:read32(battle_telemetry_address + 8) or 0,
			campaign_magic,
			campaign_magic == CAMPAIGN_TELEMETRY_MAGIC and
				emu:read32(campaign_telemetry_address + 76) or 0,
			maxmod_layer_main_address,
			emu:read8(
				MAXMOD_INITIALIZED_ADDRESS +
					maxmod_address_delta
			),
			emu:read8(maxmod_layer_main_address),
			emu:read8(maxmod_layer_main_address + 1),
			emu:read8(maxmod_layer_main_address + 2),
			emu:read8(maxmod_layer_main_address + 6),
			emu:read32(
				maxmod_layer_main_address +
					MAXMOD_LAYER_MAIN_SONG_ADDRESS_OFFSET
			),
			emu:read32(
				maxmod_layer_main_address +
					MAXMOD_LAYER_MAIN_PATTERN_READ_OFFSET
			),
			emu:read8(
				maxmod_layer_main_address +
					MAXMOD_LAYER_MAIN_VALID_OFFSET
			),
			emu:read8(maxmod_layer_main_address + 4),
			emu:read16(maxmod_layer_main_address + 52),
			maxmod_num_active_channels,
			maxmod_channel_mask,
			maxmod_module_channel_count,
			maxmod_current_layer_channel_count,
			maxmod_module_channels_address,
			maxmod_allocated_module_channels,
			maxmod_module_channels_with_flags,
			maxmod_module_channels_with_instrument,
			maxmod_first_allocated_module_index,
			maxmod_first_allocated_mix_index,
			maxmod_active_channels_address,
			maxmod_disabled_active_channels,
			maxmod_reserved_active_channels,
			maxmod_background_active_channels,
			maxmod_foreground_active_channels,
			maxmod_custom_active_channels,
			maxmod_mix_length,
			maxmod_wave_buffer_address,
			maxmod_wave_nonzero_bytes,
			maxmod_mix_channels_address,
			maxmod_active_mix_channels,
			maxmod_mix_volume_sum,
			emu:read16(SOUNDCNT_H_ADDRESS),
			emu:readRegister("pc"),
			emu:readRegister("lr"),
			emu:readRegister("sp")
		)
		write_file(output_dir .. "/diagnostic.json", payload)
		write_file(done_marker_path, payload)
		complete = true
	end
end)
