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

    struct mCore* core = mCoreFind(argv[1]);
    if(! core || ! core->init(core)) {
        fprintf(stderr, "failed to initialize mGBA core\n");
        return 1;
    }
    void* video_buffer = calloc(256 * 256, 4);
    if(! video_buffer) {
        core->deinit(core);
        return 1;
    }
    core->setVideoBuffer(core, video_buffer, 256);
    if(! mCoreLoadFile(core, argv[1])) {
        fprintf(stderr, "failed to load ROM: %s\n", argv[1]);
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
    for(long frame = 0; frame < frame_count; ++frame) {
        if(frame == a_frame) {
            core->setKeys(core, 1);
        } else if(a_frame >= 0 && frame == a_frame + 8) {
            core->setKeys(core, 0);
        }
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
    fprintf(stderr,
            "frames=%ld sample_rate=%u sample_count=%llu sound_x=0x%04X "
            "dma1=0x%04X dma2=0x%04X pc=0x%08X emulated_frames=%u\n",
            frame_count, recorder.sample_rate, (unsigned long long) recorder.sample_count,
            core->busRead16(core, 0x04000084), core->busRead16(core, 0x040000C6),
            core->busRead16(core, 0x040000D2), pc, core->frameCounter(core));
    free(video_buffer);
    core->deinit(core);
    return header_ok && close_ok && recorder.sample_count ? 0 : 1;
}
