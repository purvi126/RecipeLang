import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recipelang import compile_recipe, RecipeError
BASE = Path(__file__).resolve().parents[1] / 'examples'

class CompilerTests(unittest.TestCase):
    def test_demo(self):
        result = compile_recipe((BASE / 'demo.recipe').read_text())
        self.assertEqual(result['schedule']['optimized_minutes'], 33)
        self.assertEqual(result['schedule']['sequential_minutes'], 38)
        self.assertEqual(result['schedule']['minutes_saved'], 5)
        self.assertEqual(len(result['ir']['edges']), 3)

    def test_units_conversion(self):
        self.assertEqual(compile_recipe((BASE / 'units.recipe').read_text())['schedule']['optimized_minutes'], 18)

    def test_cycle(self):
        with self.assertRaisesRegex(RecipeError, 'cyclic'):
            compile_recipe((BASE / 'error_cycle.recipe').read_text())

    def test_incompatible_units(self):
        with self.assertRaisesRegex(RecipeError, 'incompatible units'):
            compile_recipe((BASE / 'error_units.recipe').read_text())

    def test_missing_step(self):
        with self.assertRaisesRegex(RecipeError, 'undefined step'):
            compile_recipe('step a\n needs b\n duration 1 min\nend')

    def test_missing_resource(self):
        with self.assertRaisesRegex(RecipeError, 'undefined resource'):
            compile_recipe('step a\n uses oven\n duration 1 min\nend')

    def test_insufficient_ingredient(self):
        with self.assertRaisesRegex(RecipeError, 'not enough'):
            compile_recipe('ingredient milk 100 ml\nstep a\n takes milk 1 l\n duration 1 min\nend')

    def test_lexer(self):
        with self.assertRaisesRegex(RecipeError, 'Lexical'):
            compile_recipe('step a @\n duration 1 min\nend')

    def test_syntax(self):
        with self.assertRaisesRegex(RecipeError, 'Syntax'):
            compile_recipe('step a\n duration banana min\nend')

    def test_resource_capacity(self):
        src = 'resource oven 2\n' + ''.join(f'step s{i}\n uses oven\n duration 10 min\nend\n' for i in range(3))
        self.assertEqual(compile_recipe(src)['schedule']['optimized_minutes'], 20)

    def test_no_resource_overlap(self):
        src = 'resource oven 1\n' + ''.join(f'step s{i}\n uses oven\n duration 10 min\nend\n' for i in range(3))
        self.assertEqual(compile_recipe(src)['schedule']['optimized_minutes'], 30)

    def test_invalid_duration(self):
        with self.assertRaisesRegex(RecipeError, 'positive'):
            compile_recipe('step a\n duration 0 min\nend')

if __name__ == '__main__': unittest.main()
