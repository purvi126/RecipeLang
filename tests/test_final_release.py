import tempfile
import unittest
from pathlib import Path
from recipelang import lex, compile_recipe, compile_stages
from exporters import export_all

ROOT = Path(__file__).resolve().parents[1]

class FinalReleaseTests(unittest.TestCase):
    def test_lexer_source_columns(self):
        tokens = lex('  ingredient onion 2 pcs\n')
        self.assertEqual((tokens[0].line, tokens[0].column), (1, 3))
        self.assertEqual((tokens[1].line, tokens[1].column), (1, 14))
        self.assertEqual((tokens[2].line, tokens[2].column), (1, 20))

    def test_real_compiler_stages(self):
        source = (ROOT/'examples'/'demo.recipe').read_text()
        stages = list(compile_stages(source))
        self.assertEqual(len(stages), 8)
        self.assertIn('tokens', stages[0][2])
        self.assertIn('ast', stages[1][2])
        self.assertIn('ir', stages[2][2])
        self.assertEqual(stages[-1][2]['result'], compile_recipe(source))

    def test_complex_export_images(self):
        source = (ROOT/'examples'/'complex.recipe').read_text()
        result = compile_recipe(source)
        with tempfile.TemporaryDirectory() as folder:
            export_all(result, folder)
            from PIL import Image
            for name in ('gantt.png', 'dependency_graph.png'):
                im = Image.open(Path(folder)/name)
                self.assertGreater(im.width, 500)
                self.assertGreater(im.height, 300)
                self.assertGreater(len(im.getcolors(maxcolors=1000000) or []), 10)

if __name__ == '__main__': unittest.main()
