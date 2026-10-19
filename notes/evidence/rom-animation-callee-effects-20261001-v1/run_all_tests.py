import ast
import contextlib
import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path(__file__).parent))
HERE = Path(__file__).parent

def main():
    suite = unittest.TestSuite()
    for name in ('test_effects','test_flow_base','test_summary_flow','test_frontier_base','test_summary_frontier'):
        spec = importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.wasSuccessful() and result.testsRun == 38
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text())
        assert not any(line.rstrip()!=line for line in path.read_text().splitlines()),path

if __name__ == '__main__':
    with Path(sys.argv[1]).open('x') as stream,contextlib.redirect_stdout(stream),contextlib.redirect_stderr(stream):
        try:
            main()
        except BaseException:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
