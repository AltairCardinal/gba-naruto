"""Stage only the modern authority; retain pre-existing AGENTS edits unstaged."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path('/Users/altair/github/gba-naruto-reverse')
RUN=Path(__file__).parent


def git(*args,input=None):
    return subprocess.check_output(['git',*args],cwd=ROOT,input=input)


assert not git('diff','--cached','--name-only').strip()
assert git('rev-parse','HEAD').decode().strip()=='e4b626462d389027b44908f71082dc83a85ad7f7'
paths={'tools/check_staged_artifact_policy.py','tools/verify_legacy_artifact_acceptance.py',
       'tools/rebuild_legacy_artifact_acceptance.py','tools/legacy_artifact_acceptance_contract.py',
       'tests/test_staged_legacy_artifact_acceptance.py','tests/test_verify_legacy_artifact_acceptance.py',
       'tests/test_rebuild_legacy_artifact_acceptance.py','docs/legacy-artifact-acceptance-contract-v1.md',
       'notes/legacy-artifact-acceptance-20260905.md'}
for folder in ('artifacts/rom-legacy-acceptance-20260905-v1',
               'notes/evidence/rom-legacy-acceptance-20260905-v1'):
    for path in (ROOT/folder).rglob('*'):
        assert not path.is_symlink(),path
        if path.is_file():paths.add(path.relative_to(ROOT).as_posix())
pathspec=RUN/'commit-a-pathspec.nul'
with pathspec.open('xb') as stream:
    stream.write(b'\0'.join(p.encode() for p in sorted(paths))+b'\0')
git('add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul')
before=git('show','HEAD:AGENTS.md')
addition=(RUN/'agents-pattern-added.txt').read_bytes()
marker='## ROM 与资源安全\n'.encode()
assert before.count(marker)==1 and addition not in before
staged_agents=before.replace(marker,addition+marker)
oid=git('hash-object','-w','--stdin',input=staged_agents).decode().strip()
git('update-index','--cacheinfo','100644,'+oid+',AGENTS.md')
paths.add('AGENTS.md')
assert set(git('diff','--cached','--name-only','-z').decode().rstrip('\0').split('\0'))==paths
tree=git('write-tree').decode().strip()
records={}
for path in sorted(paths):
    raw=git('show',tree+':'+path)
    if path!='AGENTS.md':assert raw==(ROOT/path).read_bytes(),path
    records[path]={'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
report={'status':'staged_authority_only_not_committed','baseline':git('rev-parse','HEAD').decode().strip(),
        'tree':tree,'files':records,'agents_preexisting_changes_preserved_unstaged':True}
with (RUN/'commit-a-staged.json').open('x') as stream:
    json.dump(report,stream,sort_keys=True,indent=2);stream.write('\n')
print(json.dumps({'tree':tree,'files':len(paths),'bytes':sum(r['size'] for r in records.values())}))
