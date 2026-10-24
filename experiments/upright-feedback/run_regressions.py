import json,unittest
from pathlib import Path
from robot_lab import BalanceEnv
original=BalanceEnv.reset;events=[]
def reset(self,*args,**kwargs):
 events.append(dict(seed=kwargs.get('seed'),positional_seed=args[0] if args else None))
 return original(self,*args,**kwargs)
BalanceEnv.reset=reset
suite=unittest.TestSuite()
for pattern in ('test_robustness.py','test_evaluation.py'):
 suite.addTests(unittest.defaultTestLoader.discover('tests',pattern=pattern))
result=unittest.TextTestRunner(verbosity=2).run(suite)
Path('experiments/upright-feedback/regression-counts.json').write_text(json.dumps(dict(reset_rollouts_including_zero_step_tests=len(events),events=events,tests=result.testsRun,passed=result.wasSuccessful()),indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
