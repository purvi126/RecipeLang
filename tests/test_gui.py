"""Real Tk smoke tests; skipped on systems without a graphical display."""
import tkinter as tk
import unittest
from gui import App


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = App()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.app.update()

    def tearDown(self):
        if hasattr(self, 'app'):
            self.app.pause()
            if self.app.phase_job:
                self.app.after_cancel(self.app.phase_job)
            if self.app.source_editor.pending:
                self.app.source_editor.after_cancel(self.app.source_editor.pending)
            self.app.destroy()

    def source(self, text):
        self.app.editor.delete('1.0', 'end')
        self.app.editor.insert('1.0', text)
        self.app.update()

    def finish_compile(self):
        self.app.compile()
        while self.app.compiling:
            self.app.after_cancel(self.app.phase_job)
            self.app.advance_phase()

    def test_editor_and_error_navigation(self):
        self.source('# step 123\nstep a\n duration 2 min\nend\n@')
        self.app.source_editor.highlight()
        self.assertIn('comment', self.app.editor.tag_names('1.3'))
        self.assertNotIn('keyword', self.app.editor.tag_names('1.3'))
        self.assertIn('keyword', self.app.editor.tag_names('2.0'))
        self.assertIn('number', self.app.editor.tag_names('3.10'))
        self.assertTrue(self.app.source_editor.gutter.find_all())
        self.finish_compile()
        self.assertEqual(self.app.editor.index('insert'), '5.0')
        self.assertTrue(self.app.phases.tag_ranges('diagnostic'))
        self.assertTrue(self.app.phases.tag_bind('diagnostic', '<Button-1>', None))

    def test_eight_live_phases_and_edit_invalidation(self):
        self.app.compile()
        for expected in range(1, 9):
            self.app.after_cancel(self.app.phase_job)
            self.app.advance_phase()
            self.assertEqual(len(self.app.phase_history), expected)
            if expected < 8:
                self.assertIsNone(self.app.result)
        self.assertIsNotNone(self.app.result)
        self.app.editor.insert('end', '\n# edited')
        self.app.update()
        self.assertIsNone(self.app.result)
        self.assertFalse(self.app.tokens.get_children())


if __name__ == '__main__':
    unittest.main()
