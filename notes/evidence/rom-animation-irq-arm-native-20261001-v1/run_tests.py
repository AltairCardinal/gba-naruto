import contextlib
from pathlib import Path
import sys
import unittest
here=Path(__file__).resolve().parent
with Path(sys.argv[1]).open('x') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
    suite=unittest.defaultTestLoader.discover(str(here),pattern='test_arm_probe.py')
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
