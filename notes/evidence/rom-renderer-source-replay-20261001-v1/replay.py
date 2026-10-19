"""Run existing source verifiers serially under their common heavy guard."""
import hashlib,json,subprocess,sys,shlex
from pathlib import Path
run=Path(__file__).parent/"attempt2"
run.mkdir(exist_ok=False)
plan=json.loads(Path('notes/evidence/rom-renderer-source-plan-20261001-v1/source-map.json').read_text())
for path,row in plan['identities'].items():
 assert hashlib.sha256(Path(path).read_bytes()).hexdigest()==row['sha256']
commands=[('inventory-v2','tools/verify_rom_cfg_inventory.py','--artifact-dir','artifacts/rom-cfg-inventory-v2'),('inventory-v3','tools/verify_rom_cfg_inventory_v3.py','--artifact-dir','artifacts/rom-cfg-inventory-v3'),('roots-v6','tools/verify_rom_cfg_proven_roots_v6.py','--artifact-dir','artifacts/rom-cfg-proven-roots-v6'),('roots-v17','tools/verify_rom_cfg_proven_roots_v17.py','--artifact','artifacts/rom-cfg-proven-roots-v17'),('roots-v18','tools/verify_rom_cfg_proven_roots_v18.py','--artifact','artifacts/rom-cfg-proven-roots-v18'),('battle-controller','tools/verify_rom_battle_controller_cfg.py','--artifact-dir','artifacts/rom-battle-controller-cfg-v1')]
rows=[]
for name,tool,arg,artifact in commands:
 command=[sys.executable,tool,'--root','.',arg,artifact]
 child_text='PYTHONPATH=. '+shlex.join(command)+' > '+shlex.quote(str(run/(name+'-child.json')))+' 2> '+shlex.quote(str(run/(name+'-child.stderr')))
 guard=[sys.executable,'tools/run_guarded.py','--summary',str(run/(name+'-guard.json')),'--lock-file','build/experiments/heavy.lock','--wall-timeout-s','180','--idle-timeout-s','120','--','sh','-c',child_text]
 with (run/(name+'-stdout.json')).open('wb')as out,(run/(name+'-stderr.log')).open('wb')as err:
  result=subprocess.run(guard,stdout=out,stderr=err)
 summary=json.loads((run/(name+'-guard.json')).read_text())
 text=(run/(name+'-child.json')).read_text();report=json.loads(text)
 row={'name':name,'command':command,'exit_code':result.returncode,'guard_reason':summary['reason'],'guard_degraded':summary['degraded'],'guard_peak_tree_rss_mib':summary['peak_tree_rss_mib'],'report':report,'verified':result.returncode==0 and report.get('verified')is True and not summary['degraded']}
 rows.append(row);print(json.dumps({'name':name,'verified':row['verified'],'errors':report.get('errors',[])}),flush=True)
 (run/'result.json').write_text(json.dumps({'schema':'renderer-source-replay-v1','rows':rows,'completed_count':len(rows),'passed_count':sum(r['verified']for r in rows),'promotion_bytes':0,'scope':'Historical source CFG semantic replay only; no new literal-to-renderer flow, Tier1, canonical or natural execution proof.'},sort_keys=True,indent=2)+'\n')
 if summary['reason']not in('completed','child-exit') or summary['degraded']:break
