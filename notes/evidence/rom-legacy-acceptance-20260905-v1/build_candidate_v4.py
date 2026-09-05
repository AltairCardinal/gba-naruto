"""Construct a candidate archive/catalog independently of the acceptance verifier."""
import base64,gzip,hashlib,json,pathlib,subprocess
ROOT=pathlib.Path('/Users/altair/github/gba-naruto-reverse')
RUN=ROOT/'build/experiments/active/legacy-artifact-acceptance/post-story-v1-20260905'
inv=json.loads((RUN/'input-inventory-v4.json').read_bytes());tree=inv['source_tree'];out=RUN/'candidate-v4';out.mkdir()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def encode(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()
proof=json.loads((ROOT/'sequel/reverse-engineering-proof.json').read_bytes());coverage=json.loads((ROOT/'sequel/rom-byte-coverage.json').read_bytes());formal=json.loads((ROOT/'notes/evidence/rom-evidence-selector-repair-20260905/formal-report.json').read_bytes())
names=set(inv['identities'])
for row in inv['roots']:
 names.update(row['root']+'/'+name for name in row['members'])
 for c in coverage['claims']:
  if c['id'] in row['coverage_claim_ids'] and c.get('independent_verifier_path'):names.add(c['independent_verifier_path'])
names.update(next(arg for arg in v['command'][1:] if arg.startswith('tools/')) for v in proof['gates']['rom_byte_coverage']['verifiers'])
records={};identities={}
for name in sorted(names):
 info=git('ls-tree',tree,'--',name).split(b'\t')[0].split();assert len(info)==3 and info[0] in (b'100644',b'100755') and info[1]==b'blob',name
 raw=git('cat-file','blob',info[2].decode());assert raw==(ROOT/name).read_bytes(),name
 records[name]={'mode':info[0].decode(),'data_base64':base64.b64encode(raw).decode()}
 identities[name]={'mode':info[0].decode(),'size':len(raw),'sha256':sha(raw)}
for name,expected in inv['identities'].items():assert identities[name]['sha256']==expected,name
roots={}
for row in inv['roots']:
 root=row['root'];baseline=None;verifiers={}
 if row['bridge_kind']=='immutable_precoverage_binding':
  m=json.loads((ROOT/root/'manifest.json').read_bytes())
  if 'coverage' in m:a=m['coverage']['archive'];b=m['coverage']['raw'];name=a['file']
  else:
   name=next(n for n in m['files'] if n.endswith('.gz'));a=m['files'][name];b={'sha256':a['uncompressed_sha256'],'size':a['uncompressed_size']}
  baseline={'archive_path':root+'/'+name,'archive_sha256':a['sha256'],'archive_size':a['size'],'raw_sha256':b['sha256'],'raw_size':b['size'],'per_root_semantic_verifier':False}
 for c in coverage['claims']:
  if c['id'] in row['coverage_claim_ids'] and c.get('independent_verifier_path'):
   v={'path':c['independent_verifier_path'],'sha256':c['independent_verifier_sha256'],'report_sha256':c.get('independent_verifier_report_sha256')};verifiers[json.dumps(v,sort_keys=True)]=v
 roots[root]={'members':row['members'],'bridge_kind':row['bridge_kind'],'proof_verifier_indices':row['proof_verifier_indices'],'coverage_claim_ids':row['coverage_claim_ids'],'claim_verifiers':[verifiers[k] for k in sorted(verifiers)],'baseline_binding':baseline}
summary={'root_count':64,'member_count':160,'bridge_counts':{'direct_proof_verifier':32,'aggregate_coverage_verifier':21,'immutable_precoverage_binding':11},'formal_contracts':106,'rom_contracts':96,'classified_bytes':6203707,'unknown_bytes':87749,'newly_classified_bytes':0,'semantic_verifiers_reexecuted':False,'global_complete':False,'global_blockers':len(formal['blockers']),'external_trust_anchor_verified':False}
catalog={'schema':'legacy-artifact-acceptance-catalog-v1','input_files':identities,'roots':roots,'summary':summary}
(out/'catalog.json').write_bytes(encode(catalog));(out/'snapshot.json.gz').write_bytes(gzip.compress(encode({'schema':'legacy-artifact-snapshot-v1','files':records}),compresslevel=9,mtime=0))
print(json.dumps({'source_tree':tree,'inputs':len(records),'raw_input_bytes':sum(r['size'] for r in identities.values()),'members':{p.name:{'sha256':sha(p.read_bytes()),'size':p.stat().st_size} for p in out.iterdir()}},indent=2))
