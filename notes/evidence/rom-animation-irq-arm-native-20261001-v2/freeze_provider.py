import hashlib,json,shlex,subprocess
from pathlib import Path
here=Path(__file__).resolve().parent
build=Path('/Users/altair/.cache/codex-tools/mgba/0.11-dev-c16c3ff-20260730-build')
source=Path('/Users/altair/.cache/codex-tools/mgba/0.11-dev-c16c3ff-20260730-source')
cmd=json.loads((here/'compile-contract.json').read_text())
index=next(i for i,x in enumerate(cmd) if x.endswith('/mgba_arm_probe.c'))
headers=subprocess.check_output([*cmd[:index],'-MM',str(here/'mgba_arm_probe.c')],text=True)
paths=set(shlex.split(headers.replace('\\\n',' ').split(':',1)[1]));paths.discard(str(here/'mgba_arm_probe.c'))
paths.update(str(source/x) for x in ('src/gba/hle-bios.c','src/gba/hle-bios.s','src/gba/bios.c','src/gba/core.c','src/gba/memory.c','src/arm/arm.c','src/arm/isa-arm.c','src/arm/isa-thumb.c','src/util/sha1.c'))
paths.add(str(build/'build.ninja'));paths.add(str(build/'include/mgba/flags.h'))
pending=[str(build/'libmgba.0.11.0.dylib')];seen=set();links={}
while pending:
 name=pending.pop();path=Path(name).resolve();name=str(path)
 if name in seen:continue
 seen.add(name);paths.add(name)
 output=subprocess.check_output(['otool','-L',name],text=True)
 deps=[line.strip().split(' (',1)[0] for line in output.splitlines()[1:]]
 links[name]=deps
 for dep in deps:
  if dep.startswith('/usr/local/') or dep.startswith('/opt/homebrew/'):pending.append(dep)
files={}
for name in sorted(paths):
 raw=Path(name).read_bytes();files[name]={'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
contract={'source_commit':'c16c3ff55585e71bee83c95539c2ecde15d728c8','files':files,'library_links':links,
 'native_binary_sha256':hashlib.sha256((here/'mgba-arm-probe').read_bytes()).hexdigest(),
 'compiler':subprocess.check_output(['clang','--version'],text=True),
 'build_defines':[x for x in cmd if x.startswith('-D')],
 'system':subprocess.check_output(['sw_vers'],text=True),'architecture':subprocess.check_output(['uname','-m'],text=True).strip(),
 'policy':'fixed local native provider, event processing suppressed, artificial RAM/register/IO fixtures; no hardware or natural reachability claim'}
(here/'provider-contract.json').write_text(json.dumps(contract,sort_keys=True,indent=2)+'\n');print('provider files',len(files))
