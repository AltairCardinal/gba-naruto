import contextlib
from pathlib import Path
import sys,unittest
with Path(sys.argv[1]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
    suite=unittest.defaultTestLoader.discover(str(Path(__file__).resolve().parent),pattern='test_object_native.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
