import gzip
import contextlib
import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


class RebuildLegacyAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder=importlib.import_module('tools.rebuild_legacy_artifact_acceptance')

    def test_rebuild_is_deterministic_and_contains_exact_source_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input.txt').write_bytes(b'input')
            catalog=json.dumps({'input_files':{'input.txt':{'mode':'100644','size':5,
                'sha256':hashlib.sha256(b'input').hexdigest()}}}).encode()
            a=root/'a.gz';b=root/'b.gz'
            self.builder.rebuild(root,catalog,a);self.builder.rebuild(root,catalog,b)
            self.assertEqual(a.read_bytes(),b.read_bytes())
            self.assertEqual({'schema':'legacy-artifact-snapshot-v1','files':{'input.txt':{
                'mode':'100644','data_base64':'aW5wdXQ='}}},json.loads(gzip.decompress(a.read_bytes())))

    def test_failure_leaves_no_output_and_never_replaces_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input.txt').write_bytes(b'wrong');out=root/'out.gz'
            catalog=json.dumps({'input_files':{'input.txt':{'mode':'100644','size':5,
                'sha256':hashlib.sha256(b'input').hexdigest()}}}).encode()
            with self.assertRaises(ValueError):self.builder.rebuild(root,catalog,out)
            self.assertFalse(out.exists())
            out.write_bytes(b'existing')
            with self.assertRaises((ValueError,FileExistsError)):self.builder.rebuild(root,catalog,out)
            self.assertEqual(b'existing',out.read_bytes())

    def test_symlink_mode_change_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'real.txt').write_bytes(b'input');(root/'link.txt').symlink_to('real.txt')
            for name,mode in [('link.txt','100644'),('real.txt','100755'),('../escape','100644')]:
                catalog=json.dumps({'input_files':{name:{'mode':mode,'size':5,
                    'sha256':hashlib.sha256(b'input').hexdigest()}}}).encode()
                with self.assertRaises(ValueError):self.builder.rebuild(root,catalog,root/'out.gz')
                self.assertFalse((root/'out.gz').exists())

    def test_cli_requires_exact_frozen_snapshot_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'input.txt').write_bytes(b'input')
            catalog=json.dumps({'input_files':{'input.txt':{'mode':'100644','size':5,
                'sha256':hashlib.sha256(b'input').hexdigest()}}}).encode()
            catalog_path=root/'catalog.json';catalog_path.write_bytes(catalog)
            encoded=(json.dumps({'schema':'legacy-artifact-snapshot-v1','files':{'input.txt':{
                'mode':'100644','data_base64':'aW5wdXQ='}}},sort_keys=True,indent=2)+'\n').encode()
            expected=gzip.compress(encoded,compresslevel=9,mtime=0)
            pin={'sha256':hashlib.sha256(expected).hexdigest(),'size':len(expected),'mode':'100644'}
            for number,snapshot_pin in enumerate((None,{},dict(pin,mode='100755'),
                                                   {k:v for k,v in pin.items() if k != 'mode'},
                                                   dict(pin,sha256='0'*64),
                                                   dict(pin,size=len(expected)+1),pin)):
                with self.subTest(snapshot_pin=snapshot_pin):
                    out=root/f'output-{number}.gz'
                    pins={'catalog.json':{'sha256':hashlib.sha256(catalog).hexdigest(),'size':len(catalog)},
                          'snapshot.json.gz':snapshot_pin}
                    argv=['rebuild','--root',str(root),'--catalog',str(catalog_path),'--output',str(out)]
                    log=io.StringIO()
                    with mock.patch.object(self.builder,'BUNDLE_IDENTITIES',pins), \
                         mock.patch('sys.argv',argv), contextlib.redirect_stdout(log):
                        result=self.builder.main()
                    if snapshot_pin == pin:
                        self.assertEqual(0,result);self.assertEqual(expected,out.read_bytes())
                        self.assertTrue(json.loads(log.getvalue())['rebuilt'])
                    else:
                        self.assertEqual(1,result)
                        self.assertFalse(out.exists())
                        self.assertFalse(json.loads(log.getvalue())['rebuilt'])
                        self.assertIn('frozen snapshot',json.loads(log.getvalue())['error'])
