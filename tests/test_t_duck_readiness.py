"""Offline, standard-library-only T-Duck integration readiness checks.

This validates source-tree prerequisites, not simulated motion.
Run: python -m unittest discover -s tests -p 'test_t_duck_readiness.py' -v
"""
import pathlib
import unittest
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]

class TduckReadiness(unittest.TestCase):
    def test_existing_baseline_preserved(self):
        for path in ("robot_lab/env.py", "assets/robot.xml", "train.py", "evaluate.py"):
            with self.subTest(path=path):
                self.assertTrue((ROOT / path).is_file())

    def test_baseline_xml_is_well_formed(self):
        root = ET.parse(ROOT / "assets/robot.xml").getroot()
        self.assertEqual(root.tag, "mujoco")

    def test_tduck_plan_has_verifiable_gates(self):
        plan = (ROOT / "docs/T_DUCK_ROADMAP.md").read_text(encoding="utf-8")
        for term in ("SHA-256", "ONNX", "10 consecutive", "licensing", "no merge"):
            with self.subTest(term=term):
                self.assertIn(term.lower(), plan.lower())

if __name__ == "__main__":
    unittest.main()
