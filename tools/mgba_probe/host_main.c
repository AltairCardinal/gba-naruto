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
#include <mgba/internal/gba/extra/cli.h>
#include <mgba-util/vfs.h>

#include <fcntl.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if !defined(USE_DEBUGGERS) || !defined(M_CORE_GBA)
#error "the host must be compiled with mGBA's own defines (USE_DEBUGGERS, M_CORE_GBA); see tools/mgba_probe/build.py"
#endif

/* ABI fingerprint of the structures the host shares with the mGBA library.
 * Values come from a build against mGBA 0.10.5 with USE_DEBUGGERS=ON,
 * M_CORE_GBA=ON and no MINIMAL_CORE (see notes/mgba-probe-build-20261020.md). */
_Static_assert(sizeof(struct mCore) == 1648, "mCore ABI mismatch: recompile with mGBA's defines");
_Static_assert(offsetof(struct mCore, init) == 1016, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, loadROM) == 1168, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, stateSize) == 1272, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, runFrame) == 1248, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, setKeys) == 1296, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, clearKeys) == 1312, "mCore ABI mismatch");
_Static_assert(offsetof(struct mCore, busRead8) == 1376, "mCore ABI mismatch");
_Static_assert(sizeof(struct CLIDebugger) == 192, "CLIDebugger ABI mismatch");
_Static_assert(offsetof(struct CLIDebugger, system) == 152, "CLIDebugger ABI mismatch");
_Static_assert(offsetof(struct CLIDebugger, backend) == 160, "CLIDebugger ABI mismatch");
_Static_assert(sizeof(struct CLIDebuggerSystem) == 96, "CLIDebuggerSystem ABI mismatch");
_Static_assert(sizeof(struct CLIDebuggerBackend) == 72, "CLIDebuggerBackend ABI mismatch");

#define VIDEO_WIDTH 240
#define VIDEO_HEIGHT 160

static struct mCore* g_core = NULL;
static struct CLIDebugger* g_cli = NULL;
static color_t* g_video = NULL;

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
	struct mDebugger* d = &g_cli->d;
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


static struct CLIDebuggerCommandSummary _extraCommands[] = {
	{ "key", _cmdKey, "I", "Set the key state (GBA bit mask)" },
	{ "keyoff", _cmdKeyOff, "", "Release all keys" },
	{ "frames", _cmdFrames, "Ii", "Set keys, run N frames, release keys" },
	{ "run", _cmdRun, "I", "Run N frames, keeping the current key state" },
	{ "cont", _cmdCont, "I", "Run until a breakpoint hits (default 600 frames)" },
	{ "dump", _cmdDump, "Ii", "Hex dump an arbitrary region" },
	{ "save", _cmdSave, "S", "Save a savestate to a file" },
	{ "load", _cmdLoad, "S", "Load a savestate from a file" },
	{ "shot", _cmdShot, "S", "Save a PNG screenshot of the current frame" },
	{ "rawshot", _cmdRawShot, "S", "Dump the rendered frame as raw RGBA" },
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
	if (argc < 2) {
		fprintf(stderr, "usage: %s <rom> [savestate]\n", argv[0]);
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
	struct VFile* rom = VFileOpen(argv[1], O_RDONLY);
	if (!rom) {
		fprintf(stderr, "ERR cannot open %s\n", argv[1]);
		return 4;
	}
	/* mCoreFind() takes a ROM *path* and sniffs the core type from the file;
	 * "gba" is not a core name. */
	STEP("find core");
	g_core = mCoreFindVF(rom);
	if (!g_core) {
		fprintf(stderr, "ERR no core for %s\n", argv[1]);
		return 3;
	}
	STEP("core init");
	if (!g_core->init(g_core)) {
		fprintf(stderr, "ERR core init failed\n");
		return 3;
	}
	STEP("config");
	mCoreInitConfig(g_core, "konoha-probe");
	mCoreLoadConfig(g_core);
	STEP("load rom");
	if (!g_core->loadROM(g_core, rom)) {
		fprintf(stderr, "ERR cannot load %s\n", argv[1]);
		return 4;
	}
	/* The video buffer has to be installed BEFORE the reset: mGBA's GBA core
	 * only associates its software renderer with the board inside
	 * _GBACoreReset(), and only if `renderer.outputBuffer` is already set
	 * (src/gba/core.c).  With the buffer installed afterwards the core keeps
	 * the dummy renderer and the video buffer stays a blank white frame. */
	STEP("video buffer");
	color_t* video = calloc(VIDEO_WIDTH * VIDEO_HEIGHT, sizeof(color_t));
	g_video = video;
	g_core->setVideoBuffer(g_core, video, VIDEO_WIDTH);

	/* mGBA's own frontends reset the core after loading a ROM; without it
	 * the CPU has no valid memory map and the first ARMRunLoop() crashes
	 * (see src/platform/example/client-server/server.c: "Reset the core.
	 * This is needed before it can run."). */
	STEP("reset core");
	g_core->reset(g_core);

	if (argc > 2) {
		STEP("load savestate");
		struct VFile* state = VFileOpen(argv[2], O_RDONLY);
		if (state) {
			bool ok = mCoreLoadStateNamed(g_core, state, SAVESTATE_RTC);
			state->close(state);
			fprintf(stderr, "[probe] savestate %s: %s\n", argv[2],
				ok ? "loaded" : "FAILED");
		}
	}

	STEP("create debugger");
	struct mDebugger* debugger = mDebuggerCreate(DEBUGGER_CLI, g_core);
	if (!debugger) {
		fprintf(stderr, "ERR cannot create debugger\n");
		return 5;
	}
	g_cli = (struct CLIDebugger*) debugger;
	/* mDebuggerCreate() already attached the GBA CLI system via
	 * core->cliDebuggerSystem(); do not create a second one. */
	if (!g_cli->system) {
		fprintf(stderr, "ERR no CLI debugger system\n");
		return 5;
	}
	STEP("merge commands");
	_mergeCommands(g_cli->system);
	/* The backend has to exist before mDebuggerAttach(): mGBA's
	 * _cliDebuggerInit() dereferences it unconditionally. */
	CLIDebuggerAttachBackend(g_cli, &g_backend);

	STEP("attach debugger");
	mDebuggerAttach(debugger, g_core);
	STEP("enter debugger");
	mDebuggerEnter(debugger, DEBUGGER_ENTER_MANUAL, NULL);
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
