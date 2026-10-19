import contextlib
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
output = Path(sys.argv[1])
with output.open('x') as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
    sys.argv = [str(Path(__file__).with_name('test_analysis.py'))]
    runpy.run_path(sys.argv[0], run_name='__main__')
