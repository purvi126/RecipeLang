import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(ROOT/'recipelang.py'), *map(str, args)],
                              capture_output=True, text=True, encoding='cp1252',
                              env={**os.environ, 'PYTHONIOENCODING': 'cp1252'})

    def test_windows_redirected_output_and_json(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/'result.json'
            process = self.run_cli(ROOT/'examples/demo.recipe', '--tokens', '--ast', '--ir', '--json', destination)
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.count('OK '), 8)
            self.assertIn('FINISHED at 33 min', process.stdout)
            self.assertEqual(json.loads(destination.read_text())['schedule']['optimized_minutes'], 33)

    def test_invalid_recipe_returns_nonzero(self):
        process = self.run_cli(ROOT/'examples/error_cycle.recipe')
        self.assertEqual(process.returncode, 1)
        self.assertIn('cyclic dependency', process.stderr)
