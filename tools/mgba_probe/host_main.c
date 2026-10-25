/*
 * Headless mGBA host for the Konoha Senki reverse-engineering work.
 *
 * Why this exists
 * ---------------
 * The repository's dynamic verification is blocked on two things that the
 * stock mgba-sdl cannot do:
 *   1. injecting key presses, and
 *   2. producing a *usable* savestate.
 *
 * mGBA's own CLI debugger already provides breakpoints, watchpoints, memory
 * reads/writes, register dumps, frame advance and savestate save/load (the
 * GBA platform adds "frame", "load" and "save").  The only missing piece is
 * key injection - and the core API has had `setKeys()` all along.
 *
 * The clean way to add it is *not* to patch mGBA: `struct CLIDebuggerSystem`
 * exposes `commands`, so a host can mount its own commands.  This file does
 * exactly that, and adds a thin stdin backend so the debugger can be driven
 * from a script.
 *
 * Command surface (all extra to mGBA's own):
 *   key <mask>            set the key state (GBA bit mask)
 *   keyoff                release all keys
 *   frames <count> <mask> set keys, run <count> frames, release keys
 *   run <count>           run <count> frames, keeping the current key state
 *   dump <addr> <len>     hex dump of an arbitrary region
 *   save <path>           write a savestate to <path>
 *   load <path>           read a savestate from <path>
 *   echo <token>          print a token (used as a client-side sentinel)
 *
 * The key mask is the GBA KEYINPUT bit layout, which is also what
 * core->setKeys() expects: A=0x001 B=0x002 SELECT=0x004 START=0x008
 * RIGHT=0x010 LEFT=0x020 UP=0x040 DOWN=0x080 R=0x100 L=0x200.
 * KEYINPUT itself (0x04000130) reads back as 0x3FF ^ mask while held.
 *
 * Everything else (b / c / status / x/4 / w/1 / frame / print / disassemble)
 * is mGBA's own CLI debugger, reached through CLIDebuggerRunCommand().
 *
 * GBA key mask: A=0x001 B=0x002 SELECT=0x004 START=0x008
 *               RIGHT=0x010 LEFT=0x020 UP=0x040 DOWN=0x080 R=0x100 L=0x200
 *
 * ABI WARNING
 * -----------
 * `struct mCore` embeds `#ifdef USE_DEBUGGERS` members, so the host must be
 * compiled with exactly the same preprocessor defines as the mGBA static
 * library it links against.  tools/mgba_probe/build.py reads those defines
 * out of the generated mgba.vcxproj and passes them to cl.exe; the
 * compile-time assertions below turn any future drift into a build error
 * instead of a crash at runtime.
 */
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif

#include <mgba/core/core.h>
#include <mgba/core/interface.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba/debugger/debugger.h>
#include <mgba/internal/debugger/cli-debugger.h>
#include <mgba-util/image.h>
#include <mgba-util/vfs.h>

#include <fcntl.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(M_CORE_GBA)
#error "the host must be compiled with mGBA's own defines (M_CORE_GBA); see tools/mgba_probe/build.py"
#endif

/* ABI fingerprint of the structures the host shares with the mGBA library.
 * Values come from a build against mGBA at the pinned commit
 * d8bad14b4540f9114246c0281d74985cf81adc68 (see tools/mgba_probe/abi_probe.c
 * and notes/mgba-probe-build-20261020.md).
 *
 * From the 0.11 development line onwards the debugger is part of the core, so
 * there is no USE_DEBUGGERS define any more, and `struct CLIDebugger` embeds a
 * `struct mDebuggerModule` instead of a `struct mDebugger`. */
_Static_assert(sizeof(struct mCore) == 1712, "mCore ABI mismatch: recompile with mGBA's defines");
_Static_assert(offsetof(struct mCore, init) == 1024, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, loadROM) == 1216, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, stateSize) == 1320, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, runFrame) == 1296, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, setKeys) == 1360, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, clearKeys) == 1376, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, busRead8) == 1440, "mCore ABI mismatch");
_Static_assert(sizeof(struct CLIDebugger) == 112, "CLIDebugger ABI mismatch");
_Static_assert(offsetof(struct CLIDebugger, system) == 72, "CLIDebugger ABI mismatch");
_Static_assert(offsetof(struct CLIDebugger, backend) == 80, "CLIDebugger ABI mismatch");
_Static_assert(sizeof(struct CLIDebuggerSystem) == 96, "CLIDebuggerSystem ABI mismatch");
_Static_assert(sizeof(struct CLIDebuggerBackend) == 80, "CLIDebuggerBackend ABI mismatch");

#define VIDEO_WIDTH 240
#define VIDEO_HEIGHT 160

static struct mCore* g_core = NULL;
static struct CLIDebugger* g_cli = NULL;
/* The debugger itself.  Since the 0.11 development line the CLI debugger is a
 * *module* of an mDebugger rather than an mDebugger itself, so the host keeps
 * the debugger and lets mDebuggerCreateModule() hand out the CLI module. */
static struct mDebugger g_debugger;
static mColor* g_video = NULL;

/* ---------------------------------------------------------- crash report */

static void _crashReport(EXCEPTION_POINTERS* ep) {
	EXCEPTION_RECORD* record = ep->ExceptionRecord;
	fprintf(stderr, "[probe] CRASH code=%08lX address=%p exe=%p\n",
		(unsigned long) record->ExceptionCode, record->ExceptionAddress,
		(void*) GetModuleHandleA(NULL));
	void* frames[32];
	USHORT count = CaptureStackBackTrace(0, 32, frames, NULL);
	for (USHORT i = 0; i < count; ++i) {
		fprintf(stderr, "[probe]   #%02u %p\n", i, frames[i]);
	}
	fflush(stderr);
}

static LONG WINAPI _unhandledException(EXCEPTION_POINTERS* ep) {
	_crashReport(ep);
	return EXCEPTION_EXECUTE_HANDLER;
}

/* ----------------------------------------------------------- backend */

static void _backendInit(struct CLIDebuggerBackend* be) {
	(void) be;
}

static void _backendDeinit(struct CLIDebuggerBackend* be) {
	(void) be;
}

static void _backendPrintf(struct CLIDebuggerBackend* be, const char* fmt, ...) {
	va_list ap;
	(void) be;
	va_start(ap, fmt);
	vfprintf(stdout, fmt, ap);
	va_end(ap);
	fflush(stdout);
}

static const char* _backendReadline(struct CLIDebuggerBackend* be, size_t* len) {
	static char buffer[8192];
	(void) be;
	if (!fgets(buffer, sizeof(buffer), stdin)) {
		return NULL;
	}
	size_t n = strlen(buffer);
	while (n && (buffer[n - 1] == '\n' || buffer[n - 1] == '\r')) {
		buffer[--n] = '\0';
	}
	if (len) {
		*len = n;
	}
	return buffer;
}

static void _backendLineAppend(struct CLIDebuggerBackend* be, const char* line) {
	(void) be;
	(void) line;
}

static const char* _backendHistoryLast(struct CLIDebuggerBackend* be, size_t* len) {
	(void) be;
	if (len) {
		*len = 0;
	}
	return NULL;
}

static void _backendHistoryAppend(struct CLIDebuggerBackend* be, const char* line) {
	(void) be;
	(void) line;
}

static void _backendInterrupt(struct CLIDebuggerBackend* be) {
	(void) be;
}

static struct CLIDebuggerBackend g_backend = {
	.p = NULL,
	.init = _backendInit,
	.deinit = _backendDeinit,
	.printf = _backendPrintf,
	.readline = _backendReadline,
	.lineAppend = _backendLineAppend,
	.historyLast = _backendHistoryLast,
	.historyAppend = _backendHistoryAppend,
	.interrupt = _backendInterrupt,
};

/* mGBA logs INFO messages (the GBA DMA chatter) to stdout by default, which
 * would drown the debugger protocol.  Keep stdout for debugger output only and
 * send warnings and errors to stderr. */
static void _hostLog(struct mLogger* logger, int category, enum mLogLevel level,
		const char* format, va_list args) {
	(void) logger;
	(void) category;
	if (level > mLOG_WARN) {
		return;
	}
	fputs("[mgba] ", stderr);
	vfprintf(stderr, format, args);
	fputc('\n', stderr);
}

static struct mLogger g_logger = {
	.log = _hostLog,
	.filter = NULL,
};

/* Set when a breakpoint fired during the last frame loop. */
static int g_bp_hit = 0;

/* Forward declaration: the Lua frame callback fires after every completed
 * frame.  Defined with the rest of the scripting block further down. */
#ifdef USE_LUA
static void _scriptFireFrame(void);
#endif

/* Frames actually executed by the last frame loop.  A loop that stops on a
 * breakpoint executes fewer frames than requested, and the caller needs the
 * real number to keep its trace honest. */
static int g_frames_done = 0;



/* Run `count` frames.
 *
 * Fast path: core->runFrame() - full speed, but mGBA never consults the
 * breakpoint table here, so an armed breakpoint cannot fire.
 *
 * Debugger path: mDebuggerRunFrame() steps the core one instruction at a time
 * and consults the breakpoint table - this is the only place breakpoints are
 * ever checked, but it is roughly two orders of magnitude slower.
 *
 * Navigation uses the fast path; a bounded hunt (right after a savestate) uses
 * the debugger path.  Returns 1 if a breakpoint fired. */
static int _runFramesFast(int count) {
	for (int i = 0; i < count; ++i) {
		g_core->runFrame(g_core);
#ifdef USE_LUA
		_scriptFireFrame();
#endif
	}
	return 0;
}

/* Run exactly one frame through the debugger path.
 *
 * mGBA's own mDebuggerRunFrame() is a do/while loop that keeps stepping
 * until the frame counter changes.  When the game is stopped inside an
 * interrupt handler (a breakpoint fires between the VBlank flag being set
 * and the handler running) the frame counter may never advance, and that
 * loop spins forever -- the probe then burns CPU with no output.
 *
 * Stepping manually with a cap keeps the probe responsive: a frame that
 * cannot complete is abandoned instead of hanging the whole session. */
#define FRAME_STEP_CAP 2000000

static int _runOneFrameDbg(struct mDebugger* d) {
	uint32_t frame = d->core->frameCounter(d->core);
	unsigned int steps = 0;
	while (d->core->frameCounter(d->core) == frame) {
		mDebuggerRun(d);
		if (d->state == DEBUGGER_PAUSED) {
			return 1;
		}
		if (++steps > FRAME_STEP_CAP) {
			fprintf(stderr, "[probe] frame step cap reached, abandoning frame\n");
			return 0;
		}
	}
	return 0;
}

static int _runFramesDbg(int count) {
	struct mDebugger* d = &g_debugger;
	bool armed = d->platform && d->platform->hasBreakpoints
		&& d->platform->hasBreakpoints(d->platform);
	g_bp_hit = 0;
	g_frames_done = 0;
	if (!armed) {
		g_frames_done = count;
		return _runFramesFast(count);
	}
	d->state = DEBUGGER_RUNNING;
	for (int i = 0; i < count; ++i) {
		if (_runOneFrameDbg(d)) {
			++g_frames_done;
			g_bp_hit = 1;
			break;
		}
		++g_frames_done;
#ifdef USE_LUA
		/* The frame completed (no breakpoint), so the script sees it. */
		_scriptFireFrame();
#endif
	}
	if (!g_bp_hit) {
		d->state = DEBUGGER_PAUSED;
	}
	return g_bp_hit;
}

/* -------------------------------------------------- our own commands */

static void _cmdKey(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend, "ERR missing key mask\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	g_core->setKeys(g_core, (uint32_t) dv->intValue);
	debugger->backend->printf(debugger->backend, "OK key 0x%08X\n",
		(unsigned) dv->intValue);
}

static void _cmdKeyOff(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	(void) dv;
	if (g_core) {
		/* clearKeys(core, mask) does keysActive &= ~mask, so passing 0
		 * would clear nothing; setKeys(core, 0) is the real "release". */
		g_core->setKeys(g_core, 0);
	}
	debugger->backend->printf(debugger->backend, "OK keyoff\n");
}

static void _cmdFrames(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE || !dv->next
			|| dv->next->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend,
			"ERR frames <count> <keymask>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	int count = dv->intValue;
	uint32_t mask = (uint32_t) dv->next->intValue;
	if (count < 0) {
		count = 0;
	}
	g_core->setKeys(g_core, mask);
	/* The debugger path when breakpoints are armed, the fast path otherwise.
	 * This is what lets a key press and a breakpoint hit happen in the same
	 * window: the fast path never consults the breakpoint table, so a
	 * breakpoint could only ever fire in a separate `cont` window. */
	int hit = _runFramesDbg(count);
	g_core->setKeys(g_core, 0);
	debugger->backend->printf(debugger->backend, "OK frames %d 0x%08X bp=%d done=%d\n",
		count, (unsigned) mask, hit, g_frames_done);
}


/* Run N frames *without* touching the key state, so a held key can be
 * observed in the emulated KEYINPUT register (0x04000130). */
static void _cmdRun(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend, "ERR run <count>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	int count = dv->intValue;
	if (count < 0) {
		count = 0;
	}
	int hit = _runFramesDbg(count);
	debugger->backend->printf(debugger->backend, "OK run %d keys=0x%08X bp=%d done=%d\n",
		count, (unsigned) g_core->getKeys(g_core), hit, g_frames_done);
}


static void _cmdDump(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE || !dv->next
			|| dv->next->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend, "ERR dump <addr> <len>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	uint32_t addr = (uint32_t) dv->intValue;
	int len = dv->next->intValue;
	if (len < 0) {
		len = 0;
	}
	debugger->backend->printf(debugger->backend, "DUMP %08X %d\n", addr, len);
	for (int i = 0; i < len; ++i) {
		if (i && (i % 16) == 0) {
			debugger->backend->printf(debugger->backend, "\n");
		}
		debugger->backend->printf(debugger->backend, "%02X",
			g_core->busRead8(g_core, addr + i));
	}
	debugger->backend->printf(debugger->backend, "\nENDDUMP\n");
}

/* Write one byte / one halfword into the emulated address space.
 *
 * The companion of `dump`: reading uses g_core->busRead8(), so writing uses
 * g_core->busWrite8().  This is what makes an instrumented playthrough
 * possible -- the L4 harness pokes the story "next scene" byte at
 * 0x020311EA (inside the story flag block at 0x020311D4) so the game
 * dispatches a chosen scene, and the scene then plays normally.
 */
static void _cmdPoke(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE || !dv->next
		|| dv->next->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend, "ERR poke <addr> <value>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	uint32_t addr = (uint32_t) dv->intValue;
	uint32_t value = (uint32_t) dv->next->intValue;
	g_core->busWrite8(g_core, addr, (uint8_t) (value & 0xFF));
	debugger->backend->printf(debugger->backend, "OK poke %08X %02X\n",
		addr, value & 0xFF);
}

static void _cmdPoke16(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE || !dv->next
		|| dv->next->type != CLIDV_INT_TYPE) {
		debugger->backend->printf(debugger->backend, "ERR poke16 <addr> <value>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	uint32_t addr = (uint32_t) dv->intValue;
	uint32_t value = (uint32_t) dv->next->intValue;
	g_core->busWrite8(g_core, addr, (uint8_t) (value & 0xFF));
	g_core->busWrite8(g_core, addr + 1, (uint8_t) ((value >> 8) & 0xFF));
	debugger->backend->printf(debugger->backend, "OK poke16 %08X %04X\n",
		addr, value & 0xFFFF);
}

/* mGBA's own "save"/"load" work on numbered state slots, and the "*"
 * argument format mGBA uses for them cannot parse a path (the CLI parser
 * tries an integer first and reports "Parse error" for anything else).
 * We therefore implement path-based savestates ourselves on top of
 * mCoreSaveStateNamed()/mCoreLoadStateNamed(). */
static void _cmdSave(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "ERR save <path>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	/* mCoreSaveStateNamed() memory-maps the file, and on Windows
	 * CreateFileMapping() needs read access, so the file has to be opened
	 * O_RDWR - this is exactly what mGBA's own mCoreGetState() does. */
	struct VFile* vf = VFileOpen(dv->charValue, O_RDWR | O_CREAT | O_TRUNC);
	if (!vf) {
		debugger->backend->printf(debugger->backend, "ERR save %s cannot open\n",
			dv->charValue);
		return;
	}
	bool ok = mCoreSaveStateNamed(g_core, vf,
		SAVESTATE_SAVEDATA | SAVESTATE_RTC | SAVESTATE_METADATA);
	ssize_t size = vf->size(vf);
	vf->close(vf);
	debugger->backend->printf(debugger->backend, "%s save %s %d\n",
		ok ? "OK" : "ERR", dv->charValue, (int) size);
}

static void _cmdLoad(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "ERR load <path>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	struct VFile* vf = VFileOpen(dv->charValue, O_RDONLY);
	if (!vf) {
		debugger->backend->printf(debugger->backend, "ERR load %s cannot open\n",
			dv->charValue);
		return;
	}
	bool ok = mCoreLoadStateNamed(g_core, vf, SAVESTATE_RTC);
	vf->close(vf);
	debugger->backend->printf(debugger->backend, "%s load %s\n",
		ok ? "OK" : "ERR", dv->charValue);
}

/* Dump mGBA's own rendered frame as raw RGBA.
 *
 * The core's video buffer is `VIDEO_WIDTH * VIDEO_HEIGHT` pixels of
 * `color_t`.  With the 32-bit build (no COLOR_16_BIT) one pixel is a
 * uint32 whose bytes are R, G, B, A in that order
 * (mgba/core/interface.h: M_COLOR_RED 0x000000FF, M_COLOR_GREEN
 * 0x0000FF00, M_COLOR_BLUE 0x00FF0000, M_COLOR_ALPHA 0xFF000000).
 *
 * This is the *renderer's* output, i.e. exactly what a player sees, so it
 * needs no PNG support in mGBA and no re-implementation of the PPU on the
 * Python side. */
static void _cmdRawShot(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "ERR rawshot <path>\n");
		return;
	}
	if (!g_video) {
		debugger->backend->printf(debugger->backend, "ERR no video buffer\n");
		return;
	}
	FILE* f = fopen(dv->charValue, "wb");
	if (!f) {
		debugger->backend->printf(debugger->backend, "ERR rawshot %s cannot open\n",
			dv->charValue);
		return;
	}
	size_t written = fwrite(g_video, BYTES_PER_PIXEL,
		VIDEO_WIDTH * VIDEO_HEIGHT, f);
	fclose(f);
	debugger->backend->printf(debugger->backend, "OK rawshot %s %u %dx%d bpp=%d\n",
		dv->charValue, (unsigned) written, VIDEO_WIDTH, VIDEO_HEIGHT,
		BYTES_PER_PIXEL);
}

/* Run N frames and write a memory region to a file after every frame.
 *
 * framedump <count> <addr> <len> <keymask> <prefix>
 *
 * This is the state-differential instrument: it samples the *bus* after each
 * frame, so it can watch VRAM, PRAM, OAM or EWRAM change over time.  A pixel
 * diff can only say "these pixels differ"; a per-frame region dump says
 * "this tilemap entry changed on frame 412".
 *
 * The bus is read with core->busRead8(), which is the same path the
 * `dump` command uses.  mGBA's Lua memory domains are not used here on
 * purpose: on this mGBA revision the Lua "vram" domain raises "Invalid
 * object" as soon as the game starts rendering, while the bus keeps
 * working. */
static void _cmdFrameDump(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_INT_TYPE || !dv->next
			|| dv->next->type != CLIDV_INT_TYPE || !dv->next->next
			|| dv->next->next->type != CLIDV_INT_TYPE || !dv->next->next->next
			|| dv->next->next->next->type != CLIDV_INT_TYPE
			|| !dv->next->next->next->next
			|| dv->next->next->next->next->type != CLIDV_CHAR_TYPE
			|| !dv->next->next->next->next->charValue) {
		debugger->backend->printf(debugger->backend,
			"ERR framedump <count> <addr> <len> <keymask> <prefix>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	int count = dv->intValue;
	uint32_t addr = (uint32_t) dv->next->intValue;
	int len = dv->next->next->intValue;
	uint32_t mask = (uint32_t) dv->next->next->next->intValue;
	const char* prefix = dv->next->next->next->next->charValue;
	if (count < 0) {
		count = 0;
	}
	if (len < 0) {
		len = 0;
	}
	g_core->setKeys(g_core, mask);
	for (int i = 0; i < count; ++i) {
		g_core->runFrame(g_core);
		char path[1024];
		snprintf(path, sizeof(path), "%s-%04d.bin", prefix, i);
		FILE* f = fopen(path, "wb");
		if (!f) {
			debugger->backend->printf(debugger->backend,
				"ERR framedump %s cannot open\n", path);
			g_core->setKeys(g_core, 0);
			return;
		}
		for (int j = 0; j < len; ++j) {
			fputc((int) (g_core->busRead8(g_core, addr + (uint32_t) j) & 0xFF), f);
		}
		fclose(f);
	}
	g_core->setKeys(g_core, 0);
	debugger->backend->printf(debugger->backend,
		"OK framedump %d frames @ %08X len %d prefix %s mask 0x%08X\n",
		count, addr, len, prefix, mask);
}

/* Repeat a press/release pattern while dumping a memory region every frame.
 *
 * keyseq <hold> <gap> <count> <addr> <len> <keymask> <prefix>
 *
 * The recording scripts in the Butano line press a key for `hold` frames and
 * release it for `gap` frames, repeated `count` times.  Holding a key down
 * for the whole run does not work: the game needs the release edge.
 * This command reproduces that pattern *and* samples the region after every
 * frame, which is what a state-level differential needs.
 */
static void _cmdKeySeq(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	int fields[6];
	const char* prefix = NULL;
	struct CLIDebugVector* node = dv;
	for (int i = 0; i < 6; ++i) {
		if (!node || node->type != CLIDV_INT_TYPE) {
			debugger->backend->printf(debugger->backend,
				"ERR keyseq <hold> <gap> <count> <addr> <len> <keymask> <prefix>\n");
			return;
		}
		fields[i] = node->intValue;
		node = node->next;
	}
	if (!node || node->type != CLIDV_CHAR_TYPE || !node->charValue) {
		debugger->backend->printf(debugger->backend,
			"ERR keyseq <hold> <gap> <count> <addr> <len> <keymask> <prefix>\n");
		return;
	}
	prefix = node->charValue;
	uint32_t mask = (uint32_t) fields[5];
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	int hold = fields[0] > 0 ? fields[0] : 1;
	int gap = fields[1] > 0 ? fields[1] : 0;
	int count = fields[2] > 0 ? fields[2] : 0;
	uint32_t addr = (uint32_t) fields[3];
	int len = fields[4] > 0 ? fields[4] : 0;
	int frame = 0;

	for (int round = 0; round < count; ++round) {
		g_core->setKeys(g_core, mask);
		for (int i = 0; i < hold; ++i) {
			g_core->runFrame(g_core);
			char path[1024];
			snprintf(path, sizeof(path), "%s-%04d.bin", prefix, frame++);
			FILE* f = fopen(path, "wb");
			if (f) {
				for (int j = 0; j < len; ++j) {
					fputc((int) (g_core->busRead8(g_core, addr + (uint32_t) j) & 0xFF), f);
				}
				fclose(f);
			}
		}
		g_core->setKeys(g_core, 0);
		for (int i = 0; i < gap; ++i) {
			g_core->runFrame(g_core);
			char path[1024];
			snprintf(path, sizeof(path), "%s-%04d.bin", prefix, frame++);
			FILE* f = fopen(path, "wb");
			if (f) {
				for (int j = 0; j < len; ++j) {
					fputc((int) (g_core->busRead8(g_core, addr + (uint32_t) j) & 0xFF), f);
				}
				fclose(f);
			}
		}
	}
	g_core->setKeys(g_core, 0);
	debugger->backend->printf(debugger->backend,
		"OK keyseq hold=%d gap=%d count=%d addr=%08X len=%d prefix=%s mask=0x%08X frames=%d\n",
		hold, gap, count, addr, len, prefix, mask, frame);
}

/* Echo a single token back.  probe_client.py uses it as a per-command
 * sentinel so it can tell where one command's output ends and the next
 * command's begins. */
static void _cmdEcho(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "\n");
		return;
	}
	debugger->backend->printf(debugger->backend, "%s\n", dv->charValue);
}

/* Save a screenshot with mGBA's own PNG writer.
 *
 * mCoreTakeScreenshotVF() pulls the pixels through core->getPixels(), which
 * is the same path the SDL/Qt frontends use, so this shows exactly what a
 * player would see.  It needs mGBA built with USE_PNG (the build script
 * enables it). */
static void _cmdShot(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "ERR shot <path>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	struct VFile* vf = VFileOpen(dv->charValue, O_WRONLY | O_CREAT | O_TRUNC);
	if (!vf) {
		debugger->backend->printf(debugger->backend, "ERR cannot open %s\n",
			dv->charValue);
		return;
	}
	bool ok = mCoreTakeScreenshotVF(g_core, vf);
	vf->close(vf);
	debugger->backend->printf(debugger->backend, "OK shot %s %d\n",
		dv->charValue, ok ? 1 : 0);
}

/* Continue execution until a breakpoint fires.
 *
 * The frame budget bounds the wait so a breakpoint that never hits cannot hang
 * the probe.  "hit=1" means the debugger reported a break during the run. */
static void _cmdCont(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	int budget = 600;
	if (dv && dv->type == CLIDV_INT_TYPE) {
		budget = dv->intValue;
	}
	if (budget < 1) {
		budget = 1;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	int hit = _runFramesDbg(budget);
	debugger->backend->printf(debugger->backend, "OK cont hit=%d frames=%d done=%d\n",
		hit, budget, g_frames_done);
}


/* --------------------------------------------------------- Lua scripting */

/* The probe hosts mGBA's own script layer so that the `mgba --script` style
 * Lua probes work here too, without mGBA's Qt/SDL frontends.
 *
 * Why this stays headless and silent: the probe links libmgba's *core* only
 * (BUILD_QT=OFF, BUILD_SDL=OFF).  There is no video window and no audio
 * backend in the process at all -- the import table of mgba-probe.exe lists
 * no USER32/winmm/SDL dependency -- so a script cannot open a window and
 * cannot make the machine play a sound.  `emu:screenshot` writes a PNG file
 * through mCoreTakeScreenshotVF(), it does not present anything.
 *
 * The frame callback is driven by the host rather than by mCoreThread: the
 * probe runs frames through core->runFrame() / mDebuggerRun(), so the host
 * fires "frame" itself after every completed frame.  That is the same
 * contract the Qt frontend gets from mCoreThread's ADD_CALLBACK(frame). */

#ifdef USE_LUA
#include <mgba/script/context.h>
#include <mgba/core/scripting.h>

/* Exported by src/script/engines/lua.c. */
extern struct mScriptEngine2* const mSCRIPT_ENGINE_LUA;

static struct mScriptContext g_scriptContext;
static struct mScriptEngineContext* g_scriptEngine = NULL;
static int g_scriptLoaded = 0;

static void _scriptFireFrame(void) {
	if (!g_scriptLoaded || !g_scriptEngine) {
		return;
	}
	mScriptContextTriggerCallback(&g_scriptContext, "frame", NULL);
}

static void _cmdScript(struct CLIDebugger* debugger, struct CLIDebugVector* dv) {
	if (!dv || dv->type != CLIDV_CHAR_TYPE || !dv->charValue) {
		debugger->backend->printf(debugger->backend, "ERR script <path>\n");
		return;
	}
	if (!g_core) {
		debugger->backend->printf(debugger->backend, "ERR no core\n");
		return;
	}
	if (g_scriptLoaded) {
		debugger->backend->printf(debugger->backend, "ERR script already loaded\n");
		return;
	}
	mScriptContextInit(&g_scriptContext);
	mScriptContextRegisterEngines(&g_scriptContext);
	mScriptContextAttachStdlib(&g_scriptContext);
	mScriptContextAttachCore(&g_scriptContext, g_core);
	g_scriptEngine = mScriptContextRegisterEngine(&g_scriptContext, mSCRIPT_ENGINE_LUA);
	if (!g_scriptEngine) {
		debugger->backend->printf(debugger->backend, "ERR no lua engine\n");
		return;
	}
	struct VFile* vf = VFileOpen(dv->charValue, O_RDONLY);
	if (!vf) {
		debugger->backend->printf(debugger->backend, "ERR script %s cannot open\n",
			dv->charValue);
		return;
	}
	bool ok = g_scriptEngine->load(g_scriptEngine, dv->charValue, vf);
	vf->close(vf);
	if (!ok) {
		debugger->backend->printf(debugger->backend, "ERR script %s cannot load\n",
			dv->charValue);
		return;
	}
	ok = g_scriptEngine->run(g_scriptEngine);
	if (!ok) {
		const char* err = g_scriptEngine->getError(g_scriptEngine);
		debugger->backend->printf(debugger->backend, "ERR script %s failed: %s\n",
			dv->charValue, err ? err : "(no message)");
		return;
	}
	g_scriptLoaded = 1;
	debugger->backend->printf(debugger->backend, "OK script %s\n", dv->charValue);
}
#endif /* USE_LUA */


static struct CLIDebuggerCommandSummary _extraCommands[] = {
	{ "key", _cmdKey, "I", "Set the key state (GBA bit mask)" },
	{ "keyoff", _cmdKeyOff, "", "Release all keys" },
	{ "frames", _cmdFrames, "Ii", "Set keys, run N frames, release keys" },
	{ "run", _cmdRun, "I", "Run N frames, keeping the current key state" },
	{ "cont", _cmdCont, "I", "Run until a breakpoint hits (default 600 frames)" },
	{ "dump", _cmdDump, "Ii", "Hex dump an arbitrary region" },
	{ "poke", _cmdPoke, "II", "Write one byte into memory" },
	{ "poke16", _cmdPoke16, "II", "Write one halfword into memory" },
	{ "save", _cmdSave, "S", "Save a savestate to a file" },
	{ "load", _cmdLoad, "S", "Load a savestate from a file" },
	{ "shot", _cmdShot, "S", "Save a PNG screenshot of the current frame" },
	{ "rawshot", _cmdRawShot, "S", "Dump the rendered frame as raw RGBA" },
	{ "framedump", _cmdFrameDump, "IIIIS", "Run N frames, dumping a memory region after each" },
	{ "keyseq", _cmdKeySeq, "IIIIIIS", "Press/release pattern, dumping a region every frame" },
#ifdef USE_LUA
	{ "script", _cmdScript, "S", "Load a Lua script (frame callback runs per frame)" },
#endif
	{ "echo", _cmdEcho, "S", "Echo a token (client sentinel)" },
	{ 0, 0, 0, 0 }
};

/* Merged command table.  It has to live in static storage: the debugger
 * keeps the pointer for the whole session. */
static struct CLIDebuggerCommandSummary _mergedCommands[64];

static void _mergeCommands(struct CLIDebuggerSystem* system) {
	size_t n = 0;
	for (size_t i = 0; _extraCommands[i].name && n < 63; ++i) {
		_mergedCommands[n++] = _extraCommands[i];
	}
	if (system->commands) {
		for (size_t i = 0; system->commands[i].name && n < 63; ++i) {
			_mergedCommands[n++] = system->commands[i];
		}
	}
	memset(&_mergedCommands[n], 0, sizeof(_mergedCommands[n]));
	system->commands = _mergedCommands;
}

/* ------------------------------------------------------------- main */

int main(int argc, char** argv) {
#define STEP(msg) do { fprintf(stderr, "[probe] %s\n", (msg)); fflush(stderr); } while (0)
	/* usage: <rom> [savestate] [--bios <path>]
	 *
	 * --bios matters for fidelity work: mGBA's built-in HLE BIOS and a real
	 * GBA BIOS boot at slightly different times, so every captured frame is
	 * shifted in the boot fade and a pixel comparison reports "everything
	 * differs" even though the content is identical.  The Butano line's
	 * original-side recordings were taken with a real BIOS
	 * (recomp/bios/gba_bios.bin), so reproducing them needs the same BIOS. */
	const char* romPath = NULL;
	const char* statePath = NULL;
	const char* biosPath = NULL;
	for (int i = 1; i < argc; ++i) {
		if (!strcmp(argv[i], "--bios") && i + 1 < argc) {
			biosPath = argv[++i];
		} else if (!romPath) {
			romPath = argv[i];
		} else if (!statePath) {
			statePath = argv[i];
		}
	}
	if (!romPath) {
		fprintf(stderr, "usage: %s <rom> [savestate] [--bios <path>]\n", argv[0]);
		return 2;
	}
	/* NOTE: do NOT call setvbuf(stdout, NULL, _IOLBF, 0) here.  MSVC's
	 * setvbuf() rejects a NULL buffer for every mode except _IONBF and
	 * reports it through the invalid-parameter handler, which in a
	 * non-interactive session terminates the process with a fast-fail
	 * (0xC0000409) *before* main() produces any output.  Every write in
	 * this host is flushed explicitly instead. */
	SetErrorMode(SEM_NOGPFAULTERRORBOX);
	SetUnhandledExceptionFilter(_unhandledException);

	mLogSetDefaultLogger(&g_logger);
	STEP("open rom");
	struct VFile* rom = VFileOpen(romPath, O_RDONLY);
	if (!rom) {
		fprintf(stderr, "ERR cannot open %s\n", romPath);
		return 4;
	}
	/* mCoreFind() takes a ROM *path* and sniffs the core type from the file;
	 * "gba" is not a core name. */
	STEP("find core");
	g_core = mCoreFindVF(rom);
	if (!g_core) {
		fprintf(stderr, "ERR no core for %s\n", romPath);
		return 3;
	}
	STEP("core init");
	if (biosPath) {
		/* The GBA core loads the BIOS itself during init, from
		 * core->opts.bios (src/gba/core.c: "if (!gba->biosVf &&
		 * core->opts.useBios)").  Calling core->loadBIOS() by hand before
		 * loadROM() does not work: the core then runs the BIOS it already
		 * has, and the game ends up executing garbage ("Illegal opcode").
		 * So: hand the path to the core and let it do the loading. */
		g_core->opts.bios = (char*) biosPath;
		g_core->opts.useBios = true;
		g_core->opts.skipBios = false;
	}
	if (!g_core->init(g_core)) {
		fprintf(stderr, "ERR core init failed\n");
		return 3;
	}
	STEP("config");
	mCoreInitConfig(g_core, "konoha-probe");
	mCoreLoadConfig(g_core);
	STEP("load rom");
	if (!g_core->loadROM(g_core, rom)) {
		fprintf(stderr, "ERR cannot load %s\n", romPath);
		return 4;
	}
	/* The video buffer has to be installed BEFORE the reset: mGBA's GBA core
	 * only associates its software renderer with the board inside
	 * _GBACoreReset(), and only if `renderer.outputBuffer` is already set
	 * (src/gba/core.c).  With the buffer installed afterwards the core keeps
	 * the dummy renderer and the video buffer stays a blank white frame. */
	STEP("video buffer");
	mColor* video = calloc(VIDEO_WIDTH * VIDEO_HEIGHT, sizeof(mColor));
	g_video = video;
	g_core->setVideoBuffer(g_core, video, VIDEO_WIDTH);

	/* mGBA's own frontends reset the core after loading a ROM; without it
	 * the CPU has no valid memory map and the first ARMRunLoop() crashes
	 * (see src/platform/example/client-server/server.c: "Reset the core.
	 * This is needed before it can run."). */
	STEP("reset core");
	g_core->reset(g_core);

	if (statePath) {
		STEP("load savestate");
		struct VFile* state = VFileOpen(statePath, O_RDONLY);
		if (state) {
			bool ok = mCoreLoadStateNamed(g_core, state, SAVESTATE_RTC);
			state->close(state);
			fprintf(stderr, "[probe] savestate %s: %s\n", statePath,
				ok ? "loaded" : "FAILED");
		}
	}

	STEP("create debugger");
	mDebuggerInit(&g_debugger);
	mDebuggerAttach(&g_debugger, g_core);
	struct mDebuggerModule* module = mDebuggerCreateModule(DEBUGGER_CLI, g_core);
	if (!module) {
		fprintf(stderr, "ERR cannot create debugger\n");
		return 5;
	}
	g_cli = (struct CLIDebugger*) module;
	/* mDebuggerCreateModule() already attached the GBA CLI system via
	 * core->cliDebuggerSystem(); do not create a second one. */
	if (!g_cli->system) {
		fprintf(stderr, "ERR no CLI debugger system\n");
		return 5;
	}
	STEP("merge commands");
	_mergeCommands(g_cli->system);
	/* The backend has to exist before the module is initialised: mGBA's
	 * _cliDebuggerInit() dereferences it unconditionally. */
	CLIDebuggerAttachBackend(g_cli, &g_backend);

	STEP("attach module");
	mDebuggerAttachModule(&g_debugger, module);
	STEP("enter debugger");
	mDebuggerEnter(&g_debugger, DEBUGGER_ENTER_MANUAL, NULL);
	STEP("ready");

	printf("READY\n");
	fflush(stdout);

	char line[8192];
	while (fgets(line, sizeof(line), stdin)) {
		size_t n = strlen(line);
		while (n && (line[n - 1] == '\n' || line[n - 1] == '\r')) {
			line[--n] = '\0';
		}
		if (!n) {
			continue;
		}
		if (!strcmp(line, "quit")) {
			break;
		}
		CLIDebuggerRunCommand(g_cli, line, n);
	}

	printf("BYE\n");
	fflush(stdout);
	free(video);
	return 0;
}
