import contextlib
from pathlib import Path
import runpy
import sys
sys.path.insert(0,str(Path.cwd()));sys.path.insert(0,str(Path(__file__).parent))
with Path(sys.argv[1]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
    sys.argv=[str(Path(__file__).with_name('test_children.py'))]
    runpy.run_path(sys.argv[0],run_name='__main__')
