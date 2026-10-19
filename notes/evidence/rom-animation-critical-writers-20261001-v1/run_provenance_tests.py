import contextlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path('notes/evidence/rom-animation-interprocedural-identities-20261001-v1').resolve()))
sys.path.insert(0,str(Path(__file__).parent))
with Path(sys.argv[1]).open('x') as out,contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
    try:
        import test_provenance
        r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_provenance))
        assert r.wasSuccessful() and r.testsRun==9
    except BaseException:
        import traceback;traceback.print_exc();raise SystemExit(1)
