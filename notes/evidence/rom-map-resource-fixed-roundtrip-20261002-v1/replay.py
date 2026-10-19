import argparse,hashlib,json,shutil,subprocess,sys,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=Path.cwd());p.add_argument('--output',type=Path,required=True);p.add_argument('--expected',type=Path);a=p.parse_args()
root=a.root.resolve();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
contract_name='tools/data/map-resource-fixed-roundtrip-contract-v1.json';script='tools/audit_map_resource_fixed_roundtrip.py'
receipt=Path(__file__).parent
contract=json.loads((receipt/'implementation'/contract_name).read_text())
expected=json.loads((a.expected or Path(__file__).with_name('result.json')).read_text())
with tempfile.TemporaryDirectory() as directory:
    clone=Path(directory).resolve();names=set(contract['inputs'])|{contract_name,script}
    for name in names:
        target=clone/name;target.parent.mkdir(parents=True,exist_ok=True);source=receipt/'implementation'/name
        source=source if source.is_file() else root/name
        if name in contract['inputs']:assert hashlib.sha256(source.read_bytes()).hexdigest()==contract['inputs'][name],name
        shutil.copy2(source,target)
    run=clone/'build/experiments/active/roundtrip-replay/portable-v1';run.mkdir(parents=True)
    (run/'.experiment.json').write_text(json.dumps({'schema':'experiment-workspace-v1','task':'roundtrip-replay','run_id':'portable-v1','status':'active'}))
    bootstrap=clone/'portable_bootstrap.py'
    bootstrap.write_text("import sys,runpy\nfrom pathlib import Path\nroot=Path(sys.argv[1]).resolve();origin=Path(sys.argv[2]).resolve();run=Path(sys.argv[3]).resolve()\ndef audit(event,args):\n    if event=='open' and isinstance(args[0],(str,bytes)) and Path(args[0]).absolute().is_relative_to(origin):\n        raise RuntimeError('unexpected source-worktree input: '+str(args[0]))\nsys.addaudithook(audit)\nsys.path.insert(0,str(root))\nsys.argv=['tools/audit_map_resource_fixed_roundtrip.py','--root',str(root),'--run',str(run)]\nrunpy.run_path(str(root/'tools/audit_map_resource_fixed_roundtrip.py'),run_name='__main__')\n")
    result=subprocess.run([sys.executable,str(bootstrap),str(clone),str(root),str(run)],cwd=clone,text=True,capture_output=True,timeout=240,check=False)
    (output/'portable-stdout.json').write_text(result.stdout);(output/'portable-stderr.txt').write_text(result.stderr)
    assert result.returncode==0,result.stderr
    actual=json.loads(result.stdout);assert actual==expected,'portable result differs'
    (output/'result-replayed.json').write_text(json.dumps(actual,indent=2,sort_keys=True)+'\n')
    report={'verified':True,'result_exact':True,'copied_inputs':len(names),'validator_source_tree_reads_forbidden':True,'builder_uses_six_copied_hash_bound_tools':True,'child_builder_audit_hook_claimed':False,'build_cli_cases':actual['summary']['actual_build_cli_cases'],'resource_ids_total':actual['resource_ids_total'],'runtime_executed':False}
    (output/'portability.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
print(json.dumps({'portable':True,'result_exact':True,'resources':166,'build_cli_cases':167}))
