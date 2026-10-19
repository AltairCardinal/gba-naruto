import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
phase=sys.argv[1]
names=sys.argv[2:]
with open(Path(__file__).parent/(phase+".log"),"w") as stream:
 suite=unittest.TestLoader().loadTestsFromNames(names)
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
