import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path.cwd().resolve();sys.path.insert(0,str(root))
from tools.run_macos_mgba_replay import guarded_command,emulator_command,validate_guard_summary,validate_completion_marker,_replay_environment,validate_output_bundle,_expected_payload as expected_zero
from tools.run_macos_mgba_single_input import _environment,_expected_payload as expected_input,_validate_output_bundle
from tools.macos_mgba_runtime_residue import probe_runtime_residue
from tools.inspect_mgba_savestate import load_gba_state
from tools.render_mode0_checkpoint import render_checkpoint
from PIL import Image
root=Path('.').resolve();run=root/'build/experiments/active/menu-portrait-pointer-ab/runtime-20261001-v1';plan=json.loads((run/'plan.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(Path(plan['binary']))==plan['binary_sha256']
for n,h in plan['repository_inputs'].items():assert sha(root/n)==h
assert not (root/'build/resource-guard/mgba-crash-latch.json').exists()
assert sha(root/plan['input_state'])==plan['input_state_sha256']
assert sha(root/plan['build']/'build-manifest.json')==plan['build_manifest_sha256']
for n,h in plan['scripts'].items():assert sha(root/n)==h
rows=[];domains=[('IO',0x04000000,0x400),('PRAM',0x05000000,0x400),('VRAM',0x06000000,0x18000),('OAM',0x07000000,0x400),('IWRAM',0x03000000,0x8000),('EWRAM',0x02000000,0x40000)]
for case in plan['cases']:
    name=case['name'];folder=run/'runtime'/name;reusing=False
    assert not folder.exists(), 'fresh case directory already exists'
    folder.mkdir(parents=True)
    print(json.dumps({'starting':name}),flush=True)
    row=plan['variants'][case['variant']];rom=root/plan['build']/row['rom_path'];assert sha(rom)==row['rom_sha256'];assert not rom.with_suffix('.sav').exists()
    staged=folder/'staged.gba'
    if reusing:assert sha(staged)==row['rom_sha256']
    else:shutil.copy2(rom,staged)
    args=argparse.Namespace(state=root/plan['input_state'],output_state=folder/'frame80.ss9',output_png=folder/'frame80.png',audit=folder/'audit.json',sentinel=folder/'sentinel.json',done_marker=folder/'guard.json.done.json',capture_frame=80,expected_rom_sha256=row['rom_sha256'],expected_state_sha256=plan['input_state_sha256'],key='A',down_frame=5,up_frame=13)
    run_id='menu-gfx-ptr-20261001-'+name
    script=root/('tools/mgba_single_input_replay.lua' if case['input'] else 'tools/mgba_checkpoint_replay.lua')
    child=emulator_command(Path(plan['binary']),[],script,staged)
    command=guarded_command(folder/'guard.json',args.done_marker,child,180,90)
    assert command.count('--lock-file')==1
    command[command.index('--lock-file')+1]=str(root/'build/experiments/heavy.lock')
    env=_environment(args,run_id) if case['input'] else _replay_environment(args,run_id)
    env['DYLD_LIBRARY_PATH']=plan['DYLD_LIBRARY_PATH']
    assert sha(Path(plan['library']))==plan['library_sha256']
    if not reusing:
        (folder/'launch.json').write_text(json.dumps({'command':child,'guard_command':command,'binary_sha256':plan['binary_sha256'],'script_sha256':sha(script),'run_id':run_id,'input':case['input'],'library_sha256':plan['library_sha256'],'DYLD_LIBRARY_PATH':plan['DYLD_LIBRARY_PATH']},indent=2,sort_keys=True)+'\n')
        with (folder/'stdout.log').open('w') as stdout,(folder/'stderr.log').open('w') as stderr:
            completed=subprocess.run(command,cwd=root,env=env,stdout=stdout,stderr=stderr,check=False)
    guard=json.loads((folder/'guard.json').read_text());validate_guard_summary(guard,child,guard['exit_code'] if reusing else completed.returncode)
    validate_completion_marker(args.done_marker,{'run_id':run_id,'capture_frame':80,'status':'capture-complete'})
    expected=expected_input(args,run_id) if case['input'] else expected_zero(args,run_id)
    bundle=_validate_output_bundle(args,expected) if case['input'] else validate_output_bundle(args.output_state,args.output_png,args.audit,args.sentinel,expected)
    residue=probe_runtime_residue(guard['child_pid']);(folder/'residue.json').write_text(json.dumps(residue,indent=2,sort_keys=True)+'\n')
    assert residue['pgid_clean'] is True and residue['mgba_listener_clean'] is True
    assert not rom.with_suffix('.sav').exists()
    state=load_gba_state(args.output_state)
    rgb=Image.open(args.output_png).convert('RGB').tobytes();assert render_checkpoint(args.output_state)[0]==rgb
    observed={'name':name,'variant':case['variant'],'input':case['input'],'state_sha256':sha(args.output_state),'png_sha256':sha(args.output_png),'rgb_sha256':hashlib.sha256(rgb).hexdigest(),'domain_sha256':{n:hashlib.sha256(state.read_memory(a,s)).hexdigest() for n,a,s in domains},'guard_sha256':sha(folder/'guard.json'),'pgid_clean':residue['pgid_clean'],'new_runtime_sample':True}
    rows.append(observed);(folder/'observed.json').write_text(json.dumps(observed,indent=2,sort_keys=True)+'\n')
    if name=='zero-baseline-2':assert rows[0]['domain_sha256']==rows[1]['domain_sha256'] and rows[0]['rgb_sha256']==rows[1]['rgb_sha256'],'zero replay nondeterministic'
    if name=='zero-candidate':assert rows[0]['domain_sha256']==rows[2]['domain_sha256'] and rows[0]['rgb_sha256']==rows[2]['rgb_sha256'],'candidate differs before input'
    (run/'progress.json').write_text(json.dumps({'completed':len(rows),'total':len(plan['cases']),'last':name},indent=2)+'\n')
    print(json.dumps({'finished':name,'peak_tree_rss_mib':guard['peak_tree_rss_mib']}),flush=True)
for n,h in plan['repository_inputs'].items():assert sha(root/n)==h
(run/'capture-result.json').write_text(json.dumps({'schema':'menu-gfx-pointer-capture-v1','samples':rows,'verified_capture':True,'semantic_verification_pending':True},indent=2,sort_keys=True)+'\n')
