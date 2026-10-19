import argparse, importlib.util, sys, unittest
from pathlib import Path
root = Path.cwd().resolve()
sys.path.insert(0, str(root))
p = argparse.ArgumentParser()
p.add_argument('--log', required=True)
p.add_argument('--stub', action='store_true')
p.add_argument('modules', nargs='+')
a = p.parse_args()
if a.stub:
    spec = importlib.util.spec_from_file_location('tools.verify_data_table_b_partial_bank', Path(__file__).with_name('red-stub.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules[spec.name] = module
suite = unittest.TestLoader().loadTestsFromNames(a.modules)
with open(a.log, 'w') as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
