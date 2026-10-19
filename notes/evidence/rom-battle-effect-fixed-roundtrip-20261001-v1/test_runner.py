import argparse,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
p=argparse.ArgumentParser();p.add_argument('--log',required=True);p.add_argument('modules',nargs='+');a=p.parse_args()
suite=unittest.TestLoader().loadTestsFromNames(a.modules)
with open(a.log,'w') as stream:r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
raise SystemExit(0 if r.wasSuccessful() else 1)
