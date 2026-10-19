import contextlib
from pathlib import Path
import sys
import unittest
here=Path(__file__).resolve().parent
with Path(sys.argv[1]).open('x') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(here),pattern='test_full_renderer.py'))
 raise SystemExit(not result.wasSuccessful())
