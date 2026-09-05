import collections,hashlib,json,pathlib
root=pathlib.Path('/Users/altair/github/gba-naruto-reverse');run=pathlib.Path(__file__).parent
coverage=json.loads((root/'sequel/rom-byte-coverage.json').read_bytes());cache={};issues=[];resolved=0
for c in coverage['claims']:
 selector=c.get('evidence_selector')
 if not selector:continue
 path=c.get('evidence_path')
 if path not in cache:
  try:cache[path]=json.loads((root/path).read_bytes())
  except Exception as e:cache[path]=e
 value=cache[path]
 try:
  if isinstance(value,Exception):raise value
  if not selector.startswith('/'):raise ValueError('not a JSON Pointer')
  for token in selector[1:].split('/'):
   token=token.replace('~1','/').replace('~0','~')
   value=value[int(token)] if isinstance(value,list) else value[token]
  resolved+=1
 except Exception as e:issues.append({'id':c['id'],'evidence_path':path,'selector':selector,'error':str(e),'promotion_batch':c.get('promotion_batch')})
report={'schema':'coverage-selector-inventory-v1','coverage_sha256':hashlib.sha256((root/'sequel/rom-byte-coverage.json').read_bytes()).hexdigest(),'resolved':resolved,'issues':issues}
(run/'selector-scan-v1.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'resolved':resolved,'issues':len(issues),'by_path':dict(collections.Counter(r['evidence_path'] for r in issues))},indent=2))
