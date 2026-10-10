
import unittest, sys, tempfile, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from recipelang import compile_recipe, RecipeError, Parser, lex, exact_schedule
from exporters import export_all
from schedule_validator import validate_schedule
BASE=Path(__file__).resolve().parents[1]/'examples'

class CompleteTests(unittest.TestCase):
    def test_complex(self):
        result=compile_recipe((BASE/'complex.recipe').read_text())
        self.assertEqual(len(result['schedule']['slots']),8)
    def test_capacity(self):
        result=compile_recipe((BASE/'parallel_capacity.recipe').read_text())
        self.assertTrue(result['schedule']['provably_optimal'])
    def test_sequential(self):
        result=compile_recipe((BASE/'sequential.recipe').read_text())
        self.assertEqual(result['schedule']['optimized_minutes'],12)
    def test_exact_demo(self):
        result=compile_recipe((BASE/'demo.recipe').read_text())
        self.assertTrue(result['schedule']['provably_optimal'])
        self.assertEqual(result['schedule']['optimized_minutes'],33)
    def test_multiple_takes(self):
        src='ingredient milk 2 l\nstep pour\n takes milk 250 ml\n takes milk 250 ml\n duration 1 min\nend'
        self.assertEqual(len(Parser(lex(src)).parse().steps['pour'].takes),2)
    def test_hour_duration(self):
        self.assertEqual(compile_recipe('step a\n duration 1 hr\nend')['schedule']['optimized_minutes'],60)
    def test_mg_conversion(self):
        self.assertEqual(compile_recipe('ingredient spice 1 g\nstep a\n takes spice 500 mg\n duration 1 min\nend')['schedule']['optimized_minutes'],1)
    def test_bad_duration(self):
        with self.assertRaises(RecipeError): compile_recipe('step a\n duration 1 sec\nend')
    def test_missing_resource(self):
        with self.assertRaises(RecipeError): compile_recipe((BASE/'error_missing_resource.recipe').read_text())
    def test_ingredient_shortage(self):
        with self.assertRaises(RecipeError): compile_recipe((BASE/'error_ingredient.recipe').read_text())
    def test_critical_nodes(self):
        r=compile_recipe((BASE/'demo.recipe').read_text())
        self.assertIn('cook',r['critical_path_nodes'])
        self.assertIn('boil_water',r['critical_path_nodes'])
    def test_export(self):
        r=compile_recipe((BASE/'demo.recipe').read_text())
        with tempfile.TemporaryDirectory() as d:
            export_all(r,d)
            self.assertEqual(len(list(Path(d).iterdir())),8)
            self.assertEqual((Path(d)/'gantt.png').read_bytes()[:8],b'\x89PNG\r\n\x1a\n')
            self.assertEqual(json.loads((Path(d)/'schedule.json').read_text())['optimized_minutes'],33)
    def test_validation(self):
        r=compile_recipe((BASE/'complex.recipe').read_text())
        recipe=Parser(lex((BASE/'complex.recipe').read_text())).parse()
        self.assertTrue(validate_schedule(recipe,r['schedule']))
