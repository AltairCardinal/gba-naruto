import contextlib
from pathlib import Path
import sys
import traceback
import unittest

sys.path.insert(0, str(Path.cwd()))

with Path(sys.argv[1]).open('w', buffering=1) as stream:
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        try:
            suite = unittest.defaultTestLoader.loadTestsFromNames(sys.argv[2:])
            result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
            code = 0 if result.wasSuccessful() else 1
        except BaseException:
            traceback.print_exc()
            code = 1
raise SystemExit(code)
