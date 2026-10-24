"""Regression for the metadata/export error that ended the single training attempt."""
import csv,importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]/'experiments/residual-feedback'

def load(name,file):
 spec=importlib.util.spec_from_file_location(name,ROOT/file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class TestResidualReporting(unittest.TestCase):
 def test_paired_hash_metadata_is_not_a_controller_trial(self):
  residual=load('residual_export_test','residual.py')
  with patch.dict(sys.modules,{'residual':residual}):runner=load('residual_export_runner','run.py')
  report=dict(results=[dict(scenario=dict(name='nominal'),trials=[dict(seed=4008,candidate=dict(seed=4008,seconds=10.,success=True),frozen_base_initial_state_sha256='metadata-hash')])])
  with tempfile.TemporaryDirectory() as tmp:
   with patch.object(runner,'ROOT',Path(tmp)):runner.save_report('example',report)
   with (Path(tmp)/'example.csv').open() as stream:rows=list(csv.DictReader(stream))
   self.assertEqual(len(rows),1);self.assertEqual(rows[0]['controller'],'candidate')
   self.assertEqual(json.loads((Path(tmp)/'example.json').read_text()),report)
