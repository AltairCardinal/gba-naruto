import sys, json, runpy
from pathlib import Path
root = Path(sys.argv[1]).resolve()
forbidden_root = '/Users/altair/github/gba-naruto-reverse/'
forbidden_binary = '/Users/altair/github/mgba-build-c16/'
forbidden_source = str(Path(sys.argv[2]).resolve()) + '/' if len(sys.argv) > 2 else forbidden_root
def audit(event, args):
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = str(Path(args[0]).absolute())
        if name.startswith(forbidden_root) or name.startswith(forbidden_binary) or name.startswith(forbidden_source):
            raise RuntimeError('hidden capture-host input: ' + name)
    if event == 'subprocess.Popen':
        raise RuntimeError('offline replay attempted process launch')
sys.addaudithook(audit)
sys.path.insert(0, str(root))
sys.argv = ['tools/verify_data_table_b_partial_bank.py', '--root', str(root)]
runpy.run_path(str(root / 'tools/verify_data_table_b_partial_bank.py'), run_name='__main__')
