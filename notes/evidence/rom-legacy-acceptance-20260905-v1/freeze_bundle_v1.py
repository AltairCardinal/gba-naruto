"""Freeze the complete modern envelope after independent candidate verification."""
import ast
import hashlib
import json
from pathlib import Path
import pprint
import sys
import zlib

ROOT=Path('/Users/altair/github/gba-naruto-reverse')
RUN=Path(__file__).parent
REL=RUN.relative_to(ROOT).as_posix()
DIRECTORY='artifacts/rom-legacy-acceptance-20260905-v1'
VERIFIER='tools/verify_legacy_artifact_acceptance.py'
BUILDER='tools/rebuild_legacy_artifact_acceptance.py'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode()


candidate=RUN/'candidate-v4'
report_raw=(RUN/'candidate-verify-v4.json').read_bytes()
report=json.loads(report_raw)
assert report['verified'] is True and report['contract_ok'] is True
assert report['artifact_status']=='candidate'
assert len(report['authorizations'])==64
members={p.name:p.read_bytes() for p in candidate.iterdir()}
assert set(members)=={'catalog.json','snapshot.json.gz'}
assert sha(members['catalog.json'])==report['catalog_sha256']=='e687009c79e4ee3b6e584f61e710bbfaea1fd2bb75a5f52758ee79df237b342c'
assert sha(members['snapshot.json.gz'])==report['snapshot_sha256']=='184f34a1871e7d451b429ecab0c6e1b9502080665e96db5290ac108d25fa0b93'
catalog=json.loads(members['catalog.json'])
assert set(catalog['roots'])==set(report['authorizations'])
assert sha((ROOT/VERIFIER).read_bytes())=='6d04c962fd00885cd80c1a6da4ea39d5004d91a90056052a0a0829a83b000d15'
manifest={'schema':'git-artifact-promotion-v1',
          'artifact_schema':'legacy-artifact-acceptance-v1', 'artifact_status':'accepted',
          'files':{p:{'sha256':sha(b),'size':len(b)} for p,b in members.items()},
          'summary':report['summary'],
          'producer':{'script_path':BUILDER,'script_sha256':sha((ROOT/BUILDER).read_bytes()),
                      'command':['python3',BUILDER,'--root','.', '--catalog',REL+'/final/catalog.json',
                                 '--output',REL+'/rebuilt-snapshot-v4.json.gz'],
                      'python_version':sys.version,'zlib_runtime_version':zlib.ZLIB_RUNTIME_VERSION,
                      'source_tree':'f7cac66c107a9ec129608188235117f5379a3c70'},
          'verifier':{'command':['python3',VERIFIER,'--artifact',REL+'/final'],
                      'script_sha256':sha((ROOT/VERIFIER).read_bytes()),'exit_code':0,
                      'candidate_report_sha256':sha(report_raw)},
          'scope':{'fixed_historical_identities':True,'new_semantic_classification':False,
                   'semantic_verifiers_reexecuted':False,'external_trust_anchor_verified':False,
                   'can_authorize_its_own_commit':False}}
members['manifest.json']=encode(manifest)
final=RUN/'final'
assert not final.is_symlink()
final.mkdir(exist_ok=True)
assert not list(final.iterdir()),'final must be empty'
for name,raw in members.items():
    with (final/name).open('xb') as stream:
        stream.write(raw)
pins={p:{'mode':'100644','size':len(b),'sha256':sha(b)} for p,b in sorted(members.items())}
contract=ROOT/'tools/legacy_artifact_acceptance_contract.py'
old=contract.read_bytes()
values={node.targets[0].id:ast.literal_eval(node.value) for node in ast.parse(old).body
        if isinstance(node,ast.Assign)}
assert values['BUNDLE_IDENTITIES']=={} and values['LEGACY_ROOTS']==()
with (RUN/'contract-before-pins.py').open('xb') as stream:
    stream.write(old)
source=('"""Fixed complete bundle identity; authority applies only after a prior commit."""\n'
        +'BUNDLE_DIRECTORY = '+repr(DIRECTORY)+'\n'
        +'BUNDLE_IDENTITIES = '+pprint.pformat(pins,sort_dicts=True,width=100)+'\n'
        +'LEGACY_ROOTS = '+pprint.pformat(tuple(sorted(report['authorizations'])),width=100)+'\n')
temp=contract.with_suffix('.py.tmp')
with temp.open('x') as stream:
    stream.write(source)
temp.replace(contract)
receipt={'status':'frozen_envelope_pending_full_bundle_and_rebuild_verification',
         'bundle_directory':DIRECTORY,'members':pins,'legacy_roots':len(report['authorizations']),
         'contract_sha256':sha(contract.read_bytes())}
with (RUN/'frozen-bundle-v1.json').open('xb') as stream:
    stream.write(encode(receipt))
print(json.dumps(receipt,sort_keys=True))
