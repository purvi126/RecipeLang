"""Regression checks for demo navigation, file safety and schedule explanations."""
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gui import App, ROOT
from recipelang import compile_recipe, RecipeError, Parser, lex, schedule, place_in_order, priority_order, topological, scheduling_metrics
from simulation import resource_lanes


class ExplanationTests(unittest.TestCase):
    def test_cycle_arrows_follow_prerequisite_to_step(self):
        source = 'step a\n needs c\n duration 1 min\nend\nstep b\n needs a\n duration 1 min\nend\nstep c\n needs b\n duration 1 min\nend\n'
        with self.assertRaisesRegex(RecipeError, 'a -> b -> c -> a'):
            compile_recipe(source)

    def test_shortage_uses_declared_units_after_conversion(self):
        source = 'ingredient milk 1 l\nstep a\n takes milk 750 ml\n duration 1 min\nend\nstep b\n takes milk 0.5 l\n duration 1 min\nend\n'
        with self.assertRaisesRegex(RecipeError, 'need 1.25 l, have 1 l; short by 0.25 l'):
            compile_recipe(source)

    def test_comparison_records_real_candidate_results(self):
        recipe = Parser(lex((ROOT / 'examples/complex.recipe').read_text())).parse()
        result = schedule(recipe)
        metrics = scheduling_metrics(recipe)
        self.assertEqual(len(result['priority_results']), 5)
        for row in result['priority_results']:
            order = topological(recipe) if row['rule'] == 'source_topological' else priority_order(recipe, metrics, row['rule'])
            self.assertEqual(row['minutes'], max(s.end for s in place_in_order(recipe, order)))
        self.assertEqual(result['heuristic_minutes'], min(r['minutes'] for r in result['priority_results']))
        self.assertLessEqual(result['optimized_minutes'], result['heuristic_minutes'])

    def test_exact_proof_is_distinct_from_a_lower_bound_match(self):
        source = 'resource pan 2\n' + ''.join(f'step a{i}\n uses pan\n duration 3 min\nend\n' for i in range(5))
        result = compile_recipe(source)['schedule']
        self.assertEqual(result['exact_status'], 'proven_optimal')
        self.assertEqual(result['optimality_gap_minutes'], 1)
        self.assertIn('search completed', result['optimality_reason'])

    def test_budget_limit_never_claims_proof(self):
        source = 'resource pan 2\n' + ''.join(f'step a{i}\n uses pan\n duration 3 min\nend\n' for i in range(5))
        with patch('recipelang.exact_schedule', return_value=(None, 120001)):
            result = compile_recipe(source)['schedule']
        self.assertFalse(result['provably_optimal'])
        self.assertEqual(result['exact_status'], 'limit_reached')
        self.assertIn('not proven', result['optimality_reason'])

    def test_large_unproven_recipe_explains_size_limit(self):
        source = 'resource pan 2\n' + ''.join(f'step a{i}\n uses pan\n duration 3 min\nend\n' for i in range(9))
        result = compile_recipe(source)['schedule']
        self.assertFalse(result['provably_optimal'])
        self.assertEqual(result['exact_status'], 'skipped_size')
        self.assertIn('8 steps', result['optimality_reason'])

    def test_lanes_cover_each_resource_use_without_overlap(self):
        result = compile_recipe((ROOT / 'examples/complex.recipe').read_text())
        rows = resource_lanes(result)
        expected = sorted((s['name'], r) for s in result['schedule']['slots'] for r in s['uses'])
        actual = sorted((s['name'], row['resource']) for row in rows for s in row['slots'])
        self.assertEqual(actual, expected)
        for row in rows:
            self.assertLessEqual(row['unit'], result['ast']['resources'][row['resource']])
            for a, b in zip(row['slots'], row['slots'][1:]):
                self.assertLessEqual(a['end'], b['start'])

    def test_capacity_two_lanes_reuse_units_at_end_boundary(self):
        source = 'resource oven 2\n' + ''.join(f'step a{i}\n uses oven\n duration 2 min\nend\n' for i in range(4))
        result = compile_recipe(source)
        rows = resource_lanes(result)
        self.assertEqual([len(r['slots']) for r in rows], [2, 2])
        for row in rows:
            self.assertEqual(row['slots'][0]['end'], row['slots'][1]['start'])


class FileAndViewTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = App()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app') and self.app.winfo_exists():
            self.app.pause()
            if self.app.phase_job:
                self.app.after_cancel(self.app.phase_job)
            if self.app.source_editor.pending:
                self.app.source_editor.after_cancel(self.app.source_editor.pending)
            self.app.destroy()

    def compile(self):
        self.app.compile()
        while self.app.compiling:
            self.app.after_cancel(self.app.phase_job)
            self.app.advance_phase()

    def test_cancel_example_switch_preserves_unsaved_buffer(self):
        a = self.app
        a.editor.insert('end', '\n# unsaved')
        before = a.editor.get('1.0', 'end-1c')
        a.example_name.set('complex.recipe')
        with patch('gui.messagebox.askyesnocancel', return_value=None):
            a.load_example()
        self.assertEqual(a.editor.get('1.0', 'end-1c'), before)
        self.assertEqual(a.example_name.get(), 'demo.recipe')
        self.assertTrue(a.is_dirty())

    def test_discard_example_clears_results_and_undo_history(self):
        a = self.app
        self.compile()
        a.editor.insert('end', '\n# unsaved')
        a.example_name.set('complex.recipe')
        with patch('gui.messagebox.askyesnocancel', return_value=False):
            a.load_example()
        self.assertEqual(a.current_path.name, 'complex.recipe')
        self.assertFalse(a.is_dirty())
        self.assertIsNone(a.result)
        self.assertFalse(a.comparison.get_children())
        with self.assertRaises(tk.TclError):
            a.editor.edit_undo()

    def test_save_as_writes_copy_and_marks_clean(self):
        a = self.app
        a.editor.insert('end', '\n# new copy')
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'copy.recipe'
            with patch('gui.filedialog.asksaveasfilename', return_value=str(target)):
                self.assertTrue(a.save_as())
            self.assertEqual(target.read_text(), a.editor.get('1.0', 'end-1c'))
            self.assertEqual(a.current_path, target)
            self.assertFalse(a.is_dirty())

    def test_failed_or_cancelled_save_blocks_file_switch(self):
        a = self.app
        a.editor.insert('end', '\n# keep this')
        before = a.editor.get('1.0', 'end-1c')
        with patch('gui.messagebox.askyesnocancel', return_value=True), patch.object(a, 'save_file', return_value=False):
            self.assertFalse(a.load_file(ROOT / 'examples/complex.recipe'))
        self.assertEqual(a.editor.get('1.0', 'end-1c'), before)
        with patch('gui.filedialog.asksaveasfilename', return_value=''):
            self.assertFalse(a.save_as())
        with patch('pathlib.Path.write_text', side_effect=OSError('denied')), patch('gui.messagebox.showerror'):
            self.assertFalse(a.save_file())
        self.assertTrue(a.is_dirty())

    def test_cancel_close_keeps_window(self):
        self.app.editor.insert('end', '\n# unsaved')
        with patch('gui.messagebox.askyesnocancel', return_value=None), patch.object(self.app, 'destroy') as destroy:
            self.app.close_file()
            destroy.assert_not_called()

    def test_save_on_close_requires_success(self):
        self.app.editor.insert('end', '\n# unsaved')
        with patch('gui.messagebox.askyesnocancel', return_value=True), patch.object(self.app, 'save_file', return_value=True), patch.object(self.app, 'destroy') as destroy:
            self.app.close_file()
            destroy.assert_called_once()
        self.app.source_editor.pending = None

    def test_clean_buffer_does_not_prompt(self):
        with patch('gui.messagebox.askyesnocancel') as dialog:
            self.assertTrue(self.app.load_file(ROOT / 'examples/sequential.recipe'))
            dialog.assert_not_called()

    def test_graph_click_details_source_and_drag(self):
        a = self.app
        self.compile()
        a.notebook.select(a.tabs['Dependency DAG'])
        a.update()
        a.reset_graph_zoom()
        box = a.graph.bbox('node:cook')
        x, y = (box[0]+box[2])/2, (box[1]+box[3])/2
        event = SimpleNamespace(x=int(x-a.graph.canvasx(0)), y=int(y-a.graph.canvasy(0)))
        a.graph_press(event)
        a.graph_release(event)
        self.assertEqual(a.selected_node, 'cook')
        self.assertIn('stove', a.node_details.cget('text'))
        a.goto_node()
        self.assertEqual(a.editor.index('insert'), str(a.result['ast']['steps']['cook']['line']) + '.0')
        a.graph_press(SimpleNamespace(x=0, y=0))
        a.graph_release(event)
        self.assertEqual(a.selected_node, 'cook')
        a.editor.insert('end', '\n# changed')
        a.update()
        self.assertIsNone(a.selected_node)

    def test_comparison_and_resource_view_refresh_with_playback(self):
        a = self.app
        self.compile()
        self.assertEqual(len(a.comparison.get_children()), 8)
        final = next(a.comparison.item(i, 'values') for i in a.comparison.get_children() if a.comparison.item(i, 'values')[0] == 'Final schedule')
        self.assertEqual(final[1], '33')
        self.assertTrue(a.resource_canvas.find_withtag('resource_slot'))
        a.next_event()
        self.assertIn('At 5 min', a.resource_note.cget('text'))
        self.assertIn('cook: 0/1', a.resource_note.cget('text'))
        a.editor.insert('end', '\n# changed')
        a.update()
        self.assertFalse(a.resource_canvas.find_all())
        self.assertFalse(a.comparison.get_children())


if __name__ == '__main__':
    unittest.main()
