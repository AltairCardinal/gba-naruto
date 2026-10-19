#include <mgba/core/config.h>
#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba-util/vfs.h>

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>


struct Recorder {
    struct mAVStream stream;
    FILE* output;
    uint32_t sample_rate;
    uint64_t sample_count;
};

struct InputEvent {
    long frame;
    uint32_t key;
    int pressed;
};


static uint32_t key_mask(const char* name) {
    if(strcmp(name, "A") == 0) {
        return 1;
    }
    if(strcmp(name, "B") == 0) {
        return 2;
    }
    if(strcmp(name, "Select") == 0) {
        return 4;
    }
    if(strcmp(name, "Start") == 0) {
        return 8;
    }
    if(strcmp(name, "Right") == 0) {
        return 16;
    }
    if(strcmp(name, "Left") == 0) {
        return 32;
    }
    if(strcmp(name, "Up") == 0) {
        return 64;
    }
    if(strcmp(name, "Down") == 0) {
        return 128;
    }
    if(strcmp(name, "R") == 0) {
        return 256;
    }
    if(strcmp(name, "L") == 0) {
        return 512;
    }
    return 0;
}


static long parse_input_events(
        const char* path,
        struct InputEvent* events,
        long capacity) {
    FILE* input = fopen(path, "r");
    if(! input) {
        fprintf(stderr, "failed to open input events: %s\n", strerror(errno));
        return -1;
    }
    char line[512];
    long count = 0;
    long previous_frame = -1;
    while(fgets(line, sizeof(line), input)) {
        long frame = -1;
        char event[16] = {0};
        char key[16] = {0};
        if(sscanf(
                   line,
                   "{\"frame\":%ld,\"event\":\"%15[^\"]\",\"key\":\"%15[^\"]\"",
                   &frame,
                   event,
                   key) != 3) {
            fprintf(stderr, "invalid input event line: %s", line);
            fclose(input);
            return -1;
        }
        const uint32_t mask = key_mask(key);
        if(frame < previous_frame || ! mask ||
                (strcmp(event, "press") != 0 &&
                 strcmp(event, "release") != 0)) {
            fprintf(stderr, "invalid input event: %s", line);
            fclose(input);
            return -1;
        }
        if(count == capacity) {
            fprintf(stderr, "too many input events\n");
            fclose(input);
            return -1;
        }
        events[count].frame = frame;
        events[count].key = mask;
        events[count].pressed = strcmp(event, "press") == 0;
        previous_frame = frame;
        ++count;
    }
    if(ferror(input) || fclose(input) != 0) {
        fprintf(stderr, "failed to read input events\n");
        return -1;
    }
    return count;
}


static void write_u16(FILE* output, uint16_t value) {
    const uint8_t bytes[] = { (uint8_t) value, (uint8_t) (value >> 8) };
    fwrite(bytes, 1, sizeof(bytes), output);
}


static void write_u32(FILE* output, uint32_t value) {
    const uint8_t bytes[] = {
        (uint8_t) value,
        (uint8_t) (value >> 8),
        (uint8_t) (value >> 16),
        (uint8_t) (value >> 24),
    };
    fwrite(bytes, 1, sizeof(bytes), output);
}


static void audioRateChanged(struct mAVStream* stream, unsigned rate) {
    struct Recorder* recorder = (struct Recorder*) stream;
    recorder->sample_rate = rate;
}


static void postAudioFrame(struct mAVStream* stream, int16_t left, int16_t right) {
    struct Recorder* recorder = (struct Recorder*) stream;
    write_u16(recorder->output, (uint16_t) left);
    write_u16(recorder->output, (uint16_t) right);
    ++recorder->sample_count;
}


static int write_header(struct Recorder* recorder) {
    if(recorder->sample_rate == 0 || recorder->sample_count > UINT32_MAX / 4) {
        return 0;
    }
    const uint32_t data_size = (uint32_t) recorder->sample_count * 4;
    if(fseek(recorder->output, 0, SEEK_SET) != 0) {
        return 0;
    }
    fwrite("RIFF", 1, 4, recorder->output);
    write_u32(recorder->output, 36 + data_size);
    fwrite("WAVE", 1, 4, recorder->output);
    fwrite("fmt ", 1, 4, recorder->output);
    write_u32(recorder->output, 16);
    write_u16(recorder->output, 1);
    write_u16(recorder->output, 2);
    write_u32(recorder->output, recorder->sample_rate);
    write_u32(recorder->output, recorder->sample_rate * 4);
    write_u16(recorder->output, 4);
    write_u16(recorder->output, 16);
    fwrite("data", 1, 4, recorder->output);
    write_u32(recorder->output, data_size);
    return ferror(recorder->output) == 0;
}


int main(int argc, char** argv) {
    if(argc != 4 && argc != 5) {
        fprintf(stderr, "usage: %s ROM OUTPUT.wav FRAMES [STATE.ss9]\n", argv[0]);
        return 2;
    }
    char* end = NULL;
    errno = 0;
    const long frame_count = strtol(argv[3], &end, 10);
    if(errno || ! end || *end || frame_count <= 0) {
        fprintf(stderr, "invalid frame count: %s\n", argv[3]);
        return 2;
    }
    long a_frame = -1;
    const char* a_frame_text = getenv("MGBA_AUDIO_A_FRAME");
    if(a_frame_text) {
        errno = 0;
        end = NULL;
        a_frame = strtol(a_frame_text, &end, 10);
        if(errno || ! end || *end || a_frame < 0 || a_frame >= frame_count) {
            fprintf(stderr, "invalid MGBA_AUDIO_A_FRAME: %s\n", a_frame_text);
            return 2;
        }
    }
    enum { input_event_capacity = 4096 };
    struct InputEvent* input_events = calloc(
            input_event_capacity, sizeof(*input_events));
    if(! input_events) {
        return 1;
    }
    long input_event_count = 0;
    const char* input_events_path =
            getenv("MGBA_AUDIO_INPUT_EVENTS");
    if(input_events_path) {
        input_event_count = parse_input_events(
                input_events_path,
                input_events,
                input_event_capacity);
        if(input_event_count < 0) {
            free(input_events);
            return 2;
        }
    }
    uint32_t telemetry_address = 0;
    const char* telemetry_address_text =
            getenv("MGBA_AUDIO_TELEMETRY_ADDRESS");
    if(telemetry_address_text) {
        errno = 0;
        end = NULL;
        const unsigned long parsed =
                strtoul(telemetry_address_text, &end, 0);
        if(errno || ! end || *end || parsed > UINT32_MAX) {
            fprintf(
                    stderr,
                    "invalid MGBA_AUDIO_TELEMETRY_ADDRESS: %s\n",
                    telemetry_address_text);
            free(input_events);
            return 2;
        }
        telemetry_address = (uint32_t) parsed;
    }
    const char* report_path = getenv("MGBA_AUDIO_REPORT");

    struct mCore* core = mCoreFind(argv[1]);
    if(! core || ! core->init(core)) {
        fprintf(stderr, "failed to initialize mGBA core\n");
        free(input_events);
        return 1;
    }
    void* video_buffer = calloc(256 * 256, 4);
    if(! video_buffer) {
        free(input_events);
        core->deinit(core);
        return 1;
    }
    core->setVideoBuffer(core, video_buffer, 256);
    if(! mCoreLoadFile(core, argv[1])) {
        fprintf(stderr, "failed to load ROM: %s\n", argv[1]);
        free(input_events);
        free(video_buffer);
        core->deinit(core);
        return 1;
    }
    mCoreConfigInit(&core->config, "s41-audio-recorder");
    mCoreConfigLoad(&core->config);
    struct mCoreOptions options = {
        .skipBios = true,
        .useBios = true,
        .audioBuffers = 1024,
        .fpsTarget = 60,
        .sampleRate = 32768,
        .volume = 0x100,
    };
    options.audioSync = false;
    options.videoSync = false;
    mCoreConfigLoadDefaults(&core->config, &options);
    mCoreLoadConfig(core);
    core->opts.skipBios = true;
    core->opts.useBios = false;

    FILE* output = fopen(argv[2], "wb+");
    if(! output) {
        fprintf(stderr, "failed to open output: %s\n", strerror(errno));
        free(input_events);
        free(video_buffer);
        core->deinit(core);
        return 1;
    }
    fwrite((uint8_t[44]){0}, 1, 44, output);
    struct Recorder recorder = {0};
    recorder.output = output;
    recorder.stream.audioRateChanged = audioRateChanged;
    recorder.stream.postAudioFrame = postAudioFrame;
    core->reset(core);
    if(argc == 5) {
        struct VFile* state = VFileOpen(argv[4], O_RDONLY);
        if(! state || ! mCoreLoadStateNamed(core, state, 0)) {
            fprintf(stderr, "failed to load state: %s\n", argv[4]);
            if(state) {
                state->close(state);
            }
            fclose(output);
            free(input_events);
            free(video_buffer);
            core->deinit(core);
            return 1;
        }
        state->close(state);
    }
    core->setAVStream(core, &recorder.stream);
    const uint32_t player_addresses[] = {
        0x030076B0, 0x030076F0, 0x03007730, 0x03007780,
    };
    uint32_t player_descriptors[] = {
        core->busRead32(core, 0x030076B0),
        core->busRead32(core, 0x030076F0),
        core->busRead32(core, 0x03007730),
        core->busRead32(core, 0x03007780),
    };
    uint32_t key_state = 0;
    long input_event_index = 0;
    for(long frame = 0; frame < frame_count; ++frame) {
        if(frame == a_frame) {
            key_state |= 1;
        }
        if(a_frame >= 0 && frame == a_frame + 8) {
            key_state &= ~UINT32_C(1);
        }
        while(input_event_index < input_event_count &&
                input_events[input_event_index].frame == frame) {
            const struct InputEvent* event =
                    &input_events[input_event_index];
            if(event->pressed) {
                key_state |= event->key;
            } else {
                key_state &= ~event->key;
            }
            ++input_event_index;
        }
        core->setKeys(core, key_state);
        core->runFrame(core);
        for(int slot = 0; slot < 4; ++slot) {
            const uint32_t descriptor = core->busRead32(core, player_addresses[slot]);
            if(descriptor != player_descriptors[slot]) {
                fprintf(stderr, "frame=%ld player_slot=%d descriptor=0x%08X\n",
                        frame, slot, descriptor);
                player_descriptors[slot] = descriptor;
            }
        }
    }
    core->setAVStream(core, NULL);

    const int header_ok = write_header(&recorder);
    const int close_ok = fclose(output) == 0;
    uint32_t pc = 0;
    core->readRegister(core, "pc", &pc);
    const uint16_t sound_x =
            core->busRead16(core, 0x04000084);
    const uint16_t dma1 =
            core->busRead16(core, 0x040000C6);
    const uint16_t dma2 =
            core->busRead16(core, 0x040000D2);
    const unsigned emulated_frames =
            core->frameCounter(core);
    fprintf(stderr,
            "frames=%ld sample_rate=%u sample_count=%llu sound_x=0x%04X "
            "dma1=0x%04X dma2=0x%04X pc=0x%08X emulated_frames=%u\n",
            frame_count, recorder.sample_rate, (unsigned long long) recorder.sample_count,
            sound_x, dma1, dma2, pc, emulated_frames);
    int report_ok = 1;
    if(report_path) {
        FILE* report = fopen(report_path, "w");
        if(! report) {
            fprintf(stderr, "failed to open audio report: %s\n", strerror(errno));
            report_ok = 0;
        } else {
            const uint32_t telemetry_magic = telemetry_address ?
                    core->busRead32(core, telemetry_address) : 0;
            const uint32_t battle_id = telemetry_address ?
                    core->busRead32(core, telemetry_address + 4) : 0;
            const uint32_t phase = telemetry_address ?
                    core->busRead32(core, telemetry_address + 8) : 0;
            const uint32_t round = telemetry_address ?
                    core->busRead32(core, telemetry_address + 12) : 0;
            const uint32_t active_units = telemetry_address ?
                    core->busRead32(core, telemetry_address + 24) : 0;
            const uint32_t last_action = telemetry_address ?
                    core->busRead32(core, telemetry_address + 92) : 0;
            fprintf(
                    report,
                    "{\"frames\":%ld,\"emulated_frames\":%u,"
                    "\"sample_rate\":%u,\"sample_count\":%llu,"
                    "\"input_event_count\":%ld,"
                    "\"input_events_consumed\":%ld,"
                    "\"sound_x\":%u,\"dma1\":%u,\"dma2\":%u,"
                    "\"pc\":%u,\"telemetry_address\":%u,"
                    "\"telemetry_magic\":%u,\"battle_id\":%u,"
                    "\"phase\":%u,\"round\":%u,"
                    "\"active_units\":%u,\"last_action\":%u}\n",
                    frame_count,
                    emulated_frames,
                    recorder.sample_rate,
                    (unsigned long long) recorder.sample_count,
                    input_event_count,
                    input_event_index,
                    sound_x,
                    dma1,
                    dma2,
                    pc,
                    telemetry_address,
                    telemetry_magic,
                    battle_id,
                    phase,
                    round,
                    active_units,
                    last_action);
            report_ok = fclose(report) == 0;
        }
    }
    free(input_events);
    free(video_buffer);
    core->deinit(core);
    return header_ok && close_ok && report_ok &&
            recorder.sample_count ? 0 : 1;
}
