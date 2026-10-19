import ast,contextlib,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(Path.cwd()))
sys.path.insert(0,str(Path('notes/evidence/rom-animation-interprocedural-identities-20261001-v1').resolve()))
sys.path.insert(0,str(HERE))
import test_provenance
from writers import main
with (HERE/'validation.log').open('x') as out,contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):
    try:
        result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_provenance))
        assert result.wasSuccessful() and result.testsRun==9
        for f in HERE.glob('*.py'):
            ast.parse(f.read_text());assert not any(l.rstrip()!=l for l in f.read_text().splitlines()),f
        main()
    except BaseException:
        import traceback;traceback.print_exc();raise SystemExit(1)
