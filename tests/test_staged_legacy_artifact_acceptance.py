"""A committed immutable acceptance package is required before legacy staging."""
import base64
import gzip
import json
from pathlib import Path
import shutil
from unittest import mock

from tests.test_check_staged_artifact_policy import CheckStagedArtifactPolicyTests
from tests.test_verify_legacy_artifact_acceptance import fixture, raw, ROOTS
from tools import check_staged_artifact_policy as policy
from tools import verify_legacy_artifact_acceptance as verifier

DIRECTORY = 'artifacts/rom-legacy-acceptance-20260905-v1'


class StagedLegacyAcceptanceTests(CheckStagedArtifactPolicyTests):
    def git(self, *args):
        result=policy._git(self.repo,*args)
        self.assertEqual(0,result.returncode,result.stderr)
        return result.stdout

    def seed_acceptance(self, commit=True):
        inputs=fixture();inspected=verifier.inspect_snapshot(inputs,ROOTS)
        snapshot=gzip.compress(raw({'schema':'legacy-artifact-snapshot-v1','files':{
            p:{'mode':mode,'data_base64':base64.b64encode(value).decode()} for p,(mode,value) in inputs.items()}}),mtime=0)
        catalog=raw({'schema':'legacy-artifact-acceptance-catalog-v1',**inspected,
                     'input_files':verifier.identities(inputs)})
        self.bundle={'catalog.json':('100644',catalog),'snapshot.json.gz':('100644',snapshot)}
        manifest={'schema':'git-artifact-promotion-v1','artifact_status':'accepted',
                  'files':{p:{'sha256':verifier.sha(value),'size':len(value)} for p,(_,value) in self.bundle.items()},
                  'verifier':{'command':['python3','tools/verify_legacy_artifact_acceptance.py'], 'exit_code':0}}
        self.bundle['manifest.json']=('100644',raw(manifest))
        for name,(_,value) in self.bundle.items():
            path=self.repo/DIRECTORY/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
        source_root=Path(policy.__file__).resolve().parents[1]
        for name in ('check_staged_artifact_policy.py','verify_legacy_artifact_acceptance.py','legacy_artifact_acceptance_contract.py'):
            path=self.repo/'tools'/name;path.parent.mkdir(exist_ok=True)
            shutil.copyfile(source_root/'tools'/name,path)
        self.git('add','tools',DIRECTORY)
        if commit:self.git('commit','-qm','acceptance package only')
        self.pins=mock.patch.object(verifier,'BUNDLE_IDENTITIES',verifier.identities(self.bundle));self.pins.start();self.addCleanup(self.pins.stop)
        self.inputs=inputs
        names=mock.patch.object(policy,'LEGACY_ROOTS',tuple(ROOTS),create=True)
        names.start();self.addCleanup(names.stop)

    def stage_legacy(self, only=None):
        for path,(mode,value) in self.inputs.items():
            if any(path.startswith(root+'/') for root in (only or ROOTS)):
                out=self.repo/path;out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(value)
        self.git('add',*(only or ROOTS))

    def test_precommitted_exact_legacy_members_are_accepted(self):
        self.seed_acceptance();self.stage_legacy()
        self.assertEqual([],policy.check(self.repo))

    def test_bundle_cannot_authorize_itself_in_its_first_commit(self):
        self.seed_acceptance(commit=False);self.stage_legacy()
        self.assertTrue(policy.check(self.repo))

    def test_staged_legacy_bytes_and_modes_must_match_even_if_worktree_restored(self):
        self.seed_acceptance();self.stage_legacy();path=self.repo/ROOTS[0]/'manifest.json';good=path.read_bytes()
        path.write_bytes(b'wrong');self.git('add',ROOTS[0]);path.write_bytes(good)
        errors=policy.check(self.repo)
        self.assertTrue(any('legacy member identity mismatch' in e for e in errors),errors)
        self.git('add',ROOTS[0]);self.git('update-index','--chmod=+x',str(path.relative_to(self.repo)))
        errors=policy.check(self.repo)
        self.assertTrue(any('legacy member identity mismatch' in e for e in errors),errors)

    def test_missing_and_extra_legacy_members_fail(self):
        self.seed_acceptance();self.stage_legacy()
        (self.repo/ROOTS[0]/'extra.bin').write_bytes(b'x');self.git('add',ROOTS[0])
        errors=policy.check(self.repo)
        self.assertTrue(any('legacy member identity mismatch' in e for e in errors),errors)

    def test_changing_bundle_or_policy_cannot_consume_baseline_authorization(self):
        for name in [DIRECTORY+'/manifest.json','tools/check_staged_artifact_policy.py',
                     'tools/verify_legacy_artifact_acceptance.py','tools/legacy_artifact_acceptance_contract.py']:
            with self.subTest(name=name):
                if not hasattr(self,'inputs'):self.seed_acceptance();self.stage_legacy()
                path=self.repo/name;original=path.read_bytes();path.write_bytes(original+b'\n');self.git('add',name)
                errors=policy.check(self.repo)
                self.assertTrue(any('acceptance authority changed' in e for e in errors),errors)
                path.write_bytes(original);self.git('add',name)

    def test_worktree_only_bundle_does_not_influence_frozen_tree(self):
        self.seed_acceptance();self.stage_legacy()
        (self.repo/DIRECTORY/'snapshot.json.gz').write_bytes(b'corrupt worktree only')
        self.assertEqual([],policy.check(self.repo))

    def test_partial_legacy_batch_is_rejected(self):
        self.seed_acceptance();self.stage_legacy(only=[ROOTS[0]])
        errors=policy.check(self.repo)
        self.assertTrue(any('incomplete legacy batch' in e for e in errors),errors)

    def test_unrelated_modern_artifact_does_not_consume_historical_authority(self):
        self.seed_acceptance()
        self.stage_structured_artifact()
        with mock.patch.object(verifier,'BUNDLE_IDENTITIES',{}):
            self.assertEqual([],policy.check(self.repo))
