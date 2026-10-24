import json,unittest
from pathlib import Path
from robot_lab import BalanceEnv
original=BalanceEnv.reset;seeds=[]
def reset(self,*args,**kw):
 seeds.append(kw.get('seed'));return original(self,*args,**kw)
BalanceEnv.reset=reset
suite=unittest.defaultTestLoader.discover('tests',pattern='test_residual_feedback.py')
result=unittest.TextTestRunner(verbosity=2).run(suite)
Path('experiments/residual-feedback/pretraining-tests.json').write_text(json.dumps(dict(passed=result.wasSuccessful(),tests=result.testsRun,reset_rollouts_including_zero_step_tests=len(seeds),seeds=seeds,learn_calls=0),indent=2)+'\n')
raise SystemExit(not result.wasSuccessful())
