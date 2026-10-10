"""Source editor helpers; highlighting deliberately tolerates incomplete programs."""
import tkinter as tk
from tkinter import ttk
from recipelang import TOKEN_RE, KEYWORDS, UNITS


class SourceEditor(ttk.Frame):
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.pending = None
        self.gutter = tk.Canvas(self, width=48, background='#f1f5f9', highlightthickness=0)
        self.text = tk.Text(self, font=('DejaVu Sans Mono', 10), wrap='none', undo=True, tabs=('2c',))
        sy = ttk.Scrollbar(self, orient='vertical', command=self.text.yview)
        sx = ttk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.text.configure(yscrollcommand=lambda a, b: (sy.set(a, b), self.redraw_numbers()), xscrollcommand=sx.set)
        self.gutter.grid(row=0, column=0, sticky='ns')
        self.text.grid(row=0, column=1, sticky='nsew')
        sy.grid(row=0, column=2, sticky='ns')
        sx.grid(row=1, column=1, sticky='ew')
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        for tag, color in [('keyword', '#7c3aed'), ('number', '#b45309'), ('unit', '#0369a1'), ('comment', '#64748b'), ('invalid', '#dc2626')]:
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure('error', background='#fecaca')
        self.text.bind('<<Modified>>', self.changed)
        self.text.bind('<Configure>', lambda event: self.redraw_numbers())

    def changed(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.text.tag_remove('error', '1.0', 'end')
        if self.on_change:
            self.on_change()
        if self.pending is not None:
            self.after_cancel(self.pending)
        # Coalesce rapid typing without executing the compiler or disturbing undo.
        self.pending = self.after(80, self.highlight)
        self.redraw_numbers()

    def highlight(self):
        if self.pending is not None:
            self.after_cancel(self.pending)
        self.pending = None
        for tag in ('keyword', 'number', 'unit', 'comment', 'invalid'):
            self.text.tag_remove(tag, '1.0', 'end')
        source = self.text.get('1.0', 'end-1c')
        for match in TOKEN_RE.finditer(source):
            kind, word = match.lastgroup, match.group()
            tag = {'NUMBER': 'number', 'COMMENT': 'comment', 'BAD': 'invalid'}.get(kind)
            if kind == 'IDENT':
                tag = 'keyword' if word in KEYWORDS else 'unit' if word in UNITS or word in ('min', 'hr', 'sec') else None
            if tag:
                self.text.tag_add(tag, f'1.0+{match.start()}c', f'1.0+{match.end()}c')
        self.text.tag_raise('error')
        self.redraw_numbers()

    def redraw_numbers(self):
        self.gutter.delete('all')
        digits = len(self.text.index('end-1c').split('.')[0])
        width = max(48, 12 + digits * 10)
        self.gutter.configure(width=width)
        index = self.text.index('@0,0')
        while True:
            info = self.text.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(width-8, info[1], anchor='ne', text=index.split('.')[0], fill='#64748b', font=self.text.cget('font'))
            index = self.text.index(f'{index}+1line')

    def go_to_error(self, line):
        self.text.tag_remove('error', '1.0', 'end')
        self.text.tag_add('error', f'{line}.0', f'{line}.end+1c')
        self.text.mark_set('insert', f'{line}.0')
        self.text.see(f'{line}.0')
        self.text.focus_set()
