import ctypes,hashlib,json,subprocess
from pathlib import Path
lib=Path('/Users/altair/.cache/codex-tools/mgba/0.11-dev-c16c3ff-20260730-build/libmgba.0.11.0.dylib')
source=Path('/Users/altair/.cache/codex-tools/mgba/0.11-dev-c16c3ff-20260730-source')
commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
assert commit=='c16c3ff55585e71bee83c95539c2ecde15d728c8'
assert subprocess.check_output(['git','-C',str(source),'status','--porcelain=v1'],text=True)==''
loaded=ctypes.CDLL(str(lib))
exported=ctypes.c_char_p.in_dll(loaded,'gitCommit').value.decode()
assert exported==commit
result={'library':str(lib),'library_sha256':hashlib.sha256(lib.read_bytes()).hexdigest(),'source_commit':commit,'exported_git_commit':exported,'source_tree_clean':True,'dlopen_verified':True,'repair_scope':'process-local DYLD_LIBRARY_PATH; original binary, manifests and source trees untouched'}
Path('build/experiments/active/cutscene-secondary-ptr-ab/runtime-recovery-20261001-v1/preflight-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps(result))
