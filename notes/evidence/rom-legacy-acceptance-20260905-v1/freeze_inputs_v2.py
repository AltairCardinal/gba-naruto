"""Freeze corrected candidate inputs; private index only, no production index mutation."""
import collections, hashlib, json, os, pathlib, shutil, subprocess
ROOT=pathlib.Path('/Users/altair/github/gba-naruto-reverse')
RUN=ROOT/'build/experiments/active/legacy-artifact-acceptance/post-story-v1-20260905'
OLD=ROOT/'build/experiments/active/direct-root-overlap-cfg/root-063400-tier1-20260905/resume-20260905T052627Z'
def git(*args,env=None): return subprocess.check_output(['git',*args],cwd=ROOT,env=env)
def sha(raw): return hashlib.sha256(raw).hexdigest()
old=json.loads((OLD/'commit-closure-candidate-v2.json').read_bytes())
old_stage=json.loads((OLD/'candidate-staged-policy-v3.json').read_bytes())
paths={r['path']:r for r in old['files']}
roots=sorted({'/'.join(p.split('/')[:2]) for p in old_stage['changed_paths'] if p.startswith('artifacts/')})
added=[]
for root in roots:
 for p in sorted((ROOT/root).rglob('*')):
  if p.is_symlink():raise ValueError(f'nonregular artifact member {p}')
  if p.is_file() and p.relative_to(ROOT).as_posix() not in paths:
   name=p.relative_to(ROOT).as_posix(); raw=p.read_bytes()
   paths[name]={'path':name,'tracked':False,'sha256':sha(raw),'size_bytes':len(raw),'reasons':[root+'/manifest.json:independently-reviewed-exact-member-domain']};added.append(paths[name])
assert len(added)==8,added
tracked=set(git('ls-files','-z').decode().split('\0'))
for name,row in paths.items():
 raw=(ROOT/name).read_bytes();row.update(sha256=sha(raw),size_bytes=len(raw),tracked=name in tracked)
old.update(files=[paths[p] for p in sorted(paths)],correction={'previous_snapshot_sha256':sha((OLD/'commit-closure-candidate-v2.json').read_bytes()),'added_members':added,'reviewed_artifact_roots':roots,'scope':'All actual regular members of the 113 changed artifact roots; all eight additions independently justified by manifest and verifier exact inventory.'})
for name in ('commit-closure-candidate-v3.json','candidate-index-v4','input-inventory-v2.json'):
 assert not (RUN/name).exists(),name
(RUN/'commit-closure-candidate-v3.json').write_text(json.dumps(old,indent=2)+'\n')
index=RUN/'candidate-index-v4';shutil.copyfile(OLD/'candidate-index-v3',index)
env=dict(os.environ,GIT_INDEX_FILE=str(index))
# Refresh only actual changes. Clean tracked ignored dependencies are not restaged.
changed=sorted(set(old_stage['changed_paths'])|{r['path'] for r in added})
pathspec=RUN/'candidate-changed-pathspec-v4.nul';pathspec.write_bytes(b'\0'.join(x.encode() for x in changed)+b'\0')
git('add','--pathspec-from-file='+str(pathspec),'--pathspec-file-nul',env=env)
tree=git('write-tree',env=env).decode().strip()
inv=json.loads((RUN/'input-inventory-v1.json').read_bytes());inv.update(source_tree=tree,member_count=0)
for row in inv['roots']:
 root=row['root'];members={}
 for entry in git('ls-tree','-r','-z',tree,'--',root).split(b'\0'):
  if not entry:continue
  metadata,path=entry.split(b'\t');mode,kind,oid=metadata.split();assert kind==b'blob' and mode in (b'100644',b'100755')
  name=path.decode();raw=git('cat-file','blob',oid.decode());assert raw==(ROOT/name).read_bytes()
  members[name[len(root)+1:]]={'mode':mode.decode(),'size':len(raw),'sha256':sha(raw)}
 row['members']=members;inv['member_count']+=len(members)
 if any(n.endswith('.gz') for n in members):
  assert row['coverage_claim_count']==0 and not row['proof_verifier_indices'];row['bridge_kind']='immutable_precoverage_binding'
 assert set(members)=={p.relative_to(ROOT/root).as_posix() for p in (ROOT/root).rglob('*') if p.is_file()}
for path,expected in inv['identities'].items():assert sha((ROOT/path).read_bytes())==expected,path
(RUN/'input-inventory-v2.json').write_text(json.dumps(inv,indent=2)+'\n')
report={'status':'corrected_private_tree_inputs_only_not_accepted','tree':tree,'head':git('rev-parse','HEAD').decode().strip(),'changed_paths':changed,'added_members':added,'legacy_roots':len(inv['roots']),'legacy_members':inv['member_count'],'legacy_bytes':sum(m['size'] for r in inv['roots'] for m in r['members'].values()),'bridge_counts':dict(collections.Counter(r['bridge_kind'] for r in inv['roots']))}
(RUN/'input-correction-v2.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('changed_paths','added_members')},indent=2))
assert not git('diff','--cached','--name-only').strip()
