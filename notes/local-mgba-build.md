# Local mGBA Build With Script CLI

Date: `2026-03-28`

## Summary

The Homebrew `mGBA 0.10.5` binary installed at:

- `/usr/local/bin/mGBA`

does **not** accept:

- `--script FILE`

However, upstream source does include this CLI option in the Qt frontend, guarded by `ENABLE_SCRIPTING`.

## Source evidence

Upstream Qt source contains:

- `ConfigController.cpp`: parses `--script FILE`
- `Window.cpp`: auto-loads each script path via `m_scripting->loadFile(scriptPath)`

## Local source/build paths

- Source clone: `/Users/altair/github/mgba-src`
- Qt-capable build: `/Users/altair/github/mgba-build-qt`
- Local built binary: `/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA`

## Verified behavior

This locally built binary accepts:

```bash
/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA \
  --script /Users/altair/github/naruto/tools/mgba_probe_script.lua \
  /Users/altair/github/naruto/rom/experiment-00076d.gba
```

And the script successfully executed, writing:

- `notes/mgba-script-probe.txt`
- `notes/mgba-script-frame.txt`

Observed output:

```text
script_loaded=yes
bytes=00 8E 8E 8C B1 81 40 0A
```

This proves all of the following:

1. the local source build includes scripting CLI support
2. `--script` auto-load works
3. the Lua script can read the patched ROM bytes from the emulator

## Practical recommendation

For all future scripted ROM debugging in this project, use the locally built binary instead of the Homebrew stable package:

```bash
/Users/altair/github/mgba-build-qt/qt/mGBA.app/Contents/MacOS/mGBA
```
