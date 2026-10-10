"""RecipeLang visual compiler workbench. Run: python3 gui.py"""
import json
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from collections import defaultdict
from recipelang import compile_recipe, compile_stages, RecipeError
from exporters import export_all

ROOT = Path(__file__).resolve().parent
PALETTE = ('#4f46e5', '#0891b2', '#16a34a', '#d97706', '#be185d', '#7c3aed')

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('RecipeLang | Visual Compiler Workbench')
        self.geometry('1250x790')
        self.minsize(950, 610)
        self.result = None
        self.compiling = False
        self.phase_job = None
        self.phase_stream = None
        self.phase_history = []
        self.minute = 0
        self.playing = False
        self.after_id = None
        self.current_path = None
        style = ttk.Style(self)
        if 'clam' in style.theme_names(): style.theme_use('clam')
        style.configure('TNotebook.Tab', padding=(12, 8))
        bar = ttk.Frame(self, padding=8)
        bar.pack(fill='x')
        for title, command in [('Open', self.open_file), ('Save', self.save_file), ('Compile + Optimize', self.compile),
                               ('▶ Play', self.play), ('Ⅱ Pause', self.pause), ('Next minute', self.next_minute),
                               ('Reset', self.reset), ('Export all', self.export_results)]:
            ttk.Button(bar, text=title, command=command).pack(side='left', padx=2)
        ttk.Label(bar, text='Speed:').pack(side='left', padx=(12, 2))
        self.speed = tk.StringVar(value='2×')
        ttk.Combobox(bar, textvariable=self.speed, values=['1×', '2×', '5×', '10×'], width=5, state='readonly').pack(side='left')
        self.clock = ttk.Label(bar, text='Simulation 00:00', font=('Arial', 11, 'bold'))
        self.clock.pack(side='right', padx=6)
        pan = ttk.Panedwindow(self, orient='horizontal')
        pan.pack(fill='both', expand=True, padx=8, pady=5)
        left, right = ttk.Frame(pan), ttk.Frame(pan)
        pan.add(left, weight=2)
        pan.add(right, weight=5)
        ttk.Label(left, text='RECIPE SOURCE', font=('Arial', 11, 'bold')).pack(anchor='w', pady=(0, 4))
        ef = ttk.Frame(left); ef.pack(fill='both', expand=True)
        self.editor = tk.Text(ef, font=('DejaVu Sans Mono', 10), wrap='none', undo=True, tabs=('2c',))
        sy = ttk.Scrollbar(ef, orient='vertical', command=self.editor.yview)
        sx = ttk.Scrollbar(ef, orient='horizontal', command=self.editor.xview)
        self.editor.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        ef.grid_rowconfigure(0, weight=1); ef.grid_columnconfigure(0, weight=1)
        self.editor.grid(row=0, column=0, sticky='nsew'); sy.grid(row=0, column=1, sticky='ns'); sx.grid(row=1, column=0, sticky='ew')
        self.editor.tag_configure('error', background='#fecaca')
        self.notebook = ttk.Notebook(right); self.notebook.pack(fill='both', expand=True)
        self.tabs = {}
        for name in ('Timeline', 'Tokens', 'AST', 'Symbol table', 'Dependency DAG', 'Scheduler', 'Compiler phases'):
            tab = ttk.Frame(self.notebook); self.notebook.add(tab, text=name); self.tabs[name] = tab
        self.stats = ttk.Label(self.tabs['Timeline'], text='Compile a recipe to generate a schedule.', wraplength=800)
        self.stats.pack(anchor='w', padx=8, pady=6)
        self.timeline = self.make_canvas(self.tabs['Timeline'])
        self.active = ttk.Label(self.tabs['Timeline'], text='', wraplength=800)
        self.active.pack(anchor='w', padx=8, pady=5)
        self.tokens = self.make_table(self.tabs['Tokens'], ('Type', 'Value', 'Line', 'Column'))
        self.ast = ttk.Treeview(self.tabs['AST'], show='tree')
        self.ast.pack(fill='both', expand=True, padx=7, pady=7)
        self.symbols = self.make_table(self.tabs['Symbol table'], ('Kind', 'Name', 'Value', 'Details'))
        self.graph = self.make_canvas(self.tabs['Dependency DAG'])
        self.schedule_table = self.make_table(self.tabs['Scheduler'], ('Step', 'Start', 'End', 'Duration', 'Resources', 'Dependencies'))
        self.schedule_note = ttk.Label(self.tabs['Scheduler'], text='', wraplength=800)
        self.schedule_note.pack(anchor='w', padx=8, pady=8)
        self.phases = tk.Text(self.tabs['Compiler phases'], font=('DejaVu Sans Mono', 10), wrap='word', state='disabled')
        self.phases.pack(fill='both', expand=True, padx=7, pady=7)
        self.phase_progress = ttk.Progressbar(self.tabs['Compiler phases'], maximum=8, mode='determinate')
        self.phase_progress.pack(fill='x', padx=7, pady=(0, 7))
        self.timeline.bind('<Configure>', lambda e: self.draw_timeline())
        self.graph.bind('<Configure>', lambda e: self.draw_graph())
        self.load_file(ROOT / 'examples' / 'demo.recipe')

    @staticmethod
    def make_table(parent, cols):
        frame = ttk.Frame(parent); frame.pack(fill='both', expand=True, padx=7, pady=7)
        table = ttk.Treeview(frame, columns=cols, show='headings')
        for col in cols:
            table.heading(col, text=col)
            table.column(col, width=110 if col not in ('Details', 'Dependencies') else 200, stretch=True)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=table.yview)
        table.configure(yscrollcommand=scroll.set)
        table.pack(side='left', fill='both', expand=True); scroll.pack(side='right', fill='y')
        return table

    @staticmethod
    def make_canvas(parent):
        frame = ttk.Frame(parent); frame.pack(fill='both', expand=True, padx=7, pady=7)
        canvas = tk.Canvas(frame, bg='white', highlightthickness=0)
        sy = ttk.Scrollbar(frame, orient='vertical', command=canvas.yview)
        sx = ttk.Scrollbar(frame, orient='horizontal', command=canvas.xview)
        canvas.configure(yscrollcommand=sy.set, xscrollcommand=sx.set)
        frame.grid_rowconfigure(0, weight=1); frame.grid_columnconfigure(0, weight=1)
        canvas.grid(row=0, column=0, sticky='nsew'); sy.grid(row=0, column=1, sticky='ns'); sx.grid(row=1, column=0, sticky='ew')
        return canvas

    def load_file(self, path):
        try: content = Path(path).read_text(encoding='utf-8')
        except OSError as e: messagebox.showerror('Open failed', str(e)); return
        self.editor.delete('1.0', 'end'); self.editor.insert('1.0', content)
        self.current_path = Path(path)
        self.title(f'RecipeLang | {self.current_path.name}')

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('RecipeLang recipes', '*.recipe'), ('All files', '*.*')])
        if path: self.load_file(path)

    def save_file(self):
        path = self.current_path or filedialog.asksaveasfilename(defaultextension='.recipe', filetypes=[('RecipeLang recipes', '*.recipe')])
        if not path: return
        try: Path(path).write_text(self.editor.get('1.0', 'end-1c'), encoding='utf-8')
        except OSError as e: messagebox.showerror('Save failed', str(e)); return
        self.current_path = Path(path)
        self.title(f'RecipeLang | {self.current_path.name}')

    def set_phases(self, text):
        self.phases.configure(state='normal'); self.phases.delete('1.0', 'end')
        self.phases.insert('1.0', text); self.phases.configure(state='disabled')

    @staticmethod
    def clear_table(table):
        for item in table.get_children(): table.delete(item)

    def compile(self):
        self.pause()
        if self.phase_job is not None:
            self.after_cancel(self.phase_job)
            self.phase_job = None
        self.minute = 0
        self.result = None
        self.compiling = True
        self.phase_history = []
        self.phase_progress['value'] = 0
        self.editor.tag_remove('error', '1.0', 'end')
        self.set_phases('Starting compiler pipeline...\n')
        self.stats.configure(text='Compiling: lexical analysis pending...')
        self.notebook.select(self.tabs['Compiler phases'])
        self.phase_stream = compile_stages(self.editor.get('1.0', 'end-1c'))
        self.phase_job = self.after(80, self.advance_phase)

    def advance_phase(self):
        self.phase_job = None
        if not self.compiling:
            return
        try:
            phase, message, snapshot = next(self.phase_stream)
        except RecipeError as e:
            self.compiling = False
            self.result = None
            self.set_phases('\n'.join(self.phase_history + ['✗ ' + str(e)]))
            self.stats.configure(text='Compilation failed — see Compiler phases')
            if e.line:
                self.editor.tag_add('error', f'{e.line}.0', f'{e.line}.end')
                self.editor.see(f'{e.line}.0')
            self.draw_timeline(); self.draw_graph()
            return
        except StopIteration:
            self.compiling = False
            return
        self.phase_history.append('✓ ' + message)
        self.phase_progress['value'] = len(self.phase_history)
        self.set_phases('\n'.join(self.phase_history) + f'\n\nCurrent phase: {phase}')
        self.stats.configure(text=f'Compiling: {phase} ({len(self.phase_history)}/8)')
        if 'tokens' in snapshot:
            self.clear_table(self.tokens)
            for t in snapshot['tokens']:
                self.tokens.insert('', 'end', values=(t['kind'], repr(t['value']) if t['kind']=='NEWLINE' else t['value'], t['line'], t['column']))
        if 'ast' in snapshot:
            for item in self.ast.get_children(): self.ast.delete(item)
            self.insert_ast('', 'Program', snapshot['ast'])
        if 'result' in snapshot:
            self.result = snapshot['result']
            self.compiling = False
            self.populate_compilation()
            self.notebook.select(self.tabs['Timeline'])
        else:
            self.phase_job = self.after(220, self.advance_phase)

    def populate_compilation(self):
        r = self.result; s = r['schedule']
        self.set_phases('\n'.join('✓ ' + phase for phase in r['phases']))
        self.stats.configure(text=f'Sequential {s["sequential_minutes"]} min  •  Scheduled {s["optimized_minutes"]} min  •  Saved {s["minutes_saved"]} min  •  Critical-path lower bound {s["critical_path_lower_bound"]} min')
        self.clear_table(self.tokens)
        for t in r['tokens']: self.tokens.insert('', 'end', values=(t['kind'], repr(t['value']) if t['kind']=='NEWLINE' else t['value'], t['line'], t.get('column', 1)))
        for item in self.ast.get_children(): self.ast.delete(item)
        self.insert_ast('', 'Program', r['ast'])
        self.clear_table(self.symbols)
        for name, ing in r['ast']['ingredients'].items():
            self.symbols.insert('', 'end', values=('Ingredient', name, f'{ing["quantity"]:g} {ing["unit"]}', f'line {ing["line"]}'))
        for name, count in r['ast']['resources'].items():
            self.symbols.insert('', 'end', values=('Resource', name, count, 'capacity'))
        for name, step in r['ast']['steps'].items():
            self.symbols.insert('', 'end', values=('Step', name, f'{step["duration"]} min', f'needs: {", ".join(step["needs"]) or "none"}; uses: {", ".join(step["uses"]) or "none"}'))
        self.clear_table(self.schedule_table)
        for slot in s['slots']:
            step = r['ast']['steps'][slot['name']]
            self.schedule_table.insert('', 'end', values=(slot['name'], slot['start'], slot['end'], slot['end']-slot['start'], ', '.join(slot['uses']) or '—', ', '.join(step['needs']) or '—'))
        self.schedule_note.configure(text=f'Method: {s["method"]}. Priority orders evaluated: {s["priority_orders_evaluated"]}. Critical path is a dependency-only lower bound, not a proof of global optimality.')
        self.notebook.select(self.tabs['Timeline'])
        self.draw_timeline(); self.draw_graph()


    def export_results(self):
        if not self.result:
            messagebox.showwarning('Export', 'Compile a recipe first.')
            return
        directory = filedialog.askdirectory(title='Choose export destination')
        if not directory: return
        try:
            export_all(self.result, directory)
        except (OSError, ImportError, ValueError) as exc:
            messagebox.showerror('Export failed', str(exc))
            return
        messagebox.showinfo('Export complete', f'Compiler results saved to {directory}')

    def insert_ast(self, parent, name, obj):
        if isinstance(obj, dict):
            node = self.ast.insert(parent, 'end', text=name, open=(parent == ''))
            for key, value in obj.items(): self.insert_ast(node, str(key), value)
        elif isinstance(obj, list):
            node = self.ast.insert(parent, 'end', text=f'{name} [{len(obj)}]', open=False)
            for i, value in enumerate(obj): self.insert_ast(node, str(i), value)
        else: self.ast.insert(parent, 'end', text=f'{name}: {obj}')

    def draw_timeline(self):
        c = self.timeline; c.delete('all')
        if not self.result: return
        slots = self.result['schedule']['slots']; max_t = max(1, self.result['schedule']['optimized_minutes'])
        w = max(670, c.winfo_width()); x0 = 165; pw = max(400, w-x0-45); rh = 46
        for t in range(0, max_t+1, max(1, (max_t+9)//10)):
            x = x0 + t/max_t*pw
            c.create_line(x, 30, x, 65+len(slots)*rh, fill='#e2e8f0')
            c.create_text(x, 16, text=str(t), fill='#64748b')
        for i, slot in enumerate(slots):
            y = 46+i*rh; x1 = x0+slot['start']/max_t*pw; x2 = x0+slot['end']/max_t*pw
            c.create_text(8, y+14, anchor='w', text=slot['name'], font=('Arial', 10))
            c.create_rectangle(x1, y, x2, y+29, fill=PALETTE[i%len(PALETTE)], outline='')
            c.create_text((x1+x2)/2, y+14, text=f'{slot["start"]}–{slot["end"]}', fill='white', font=('Arial', 9, 'bold'))
        x = x0 + self.minute/max_t*pw
        c.create_line(x, 28, x, 65+len(slots)*rh, fill='#ef4444', width=3)
        c.configure(scrollregion=(0, 0, w, max(400, 90+len(slots)*rh)))
        self.update_clock()

    def draw_graph(self):
        c = self.graph; c.delete('all')
        if not self.result: return
        steps = self.result['ast']['steps']; edges = self.result['ir']['edges']
        levels = {}
        def level(name):
            if name not in levels: levels[name] = 1 + max((level(d) for d in steps[name]['needs']), default=-1)
            return levels[name]
        for name in steps: level(name)
        groups = defaultdict(list)
        for name, depth in levels.items(): groups[depth].append(name)
        width = max(c.winfo_width(), 680, 210*len(groups)+70)
        height = max(c.winfo_height(), 400, max(map(len, groups.values()))*110+90)
        pos = {}
        for depth, names in groups.items():
            for i, name in enumerate(names):
                pos[name] = (105+depth*210, (height/(len(names)+1))*(i+1))
        critical = set(self.result.get('critical_path_nodes', []))
        for a, b in edges:
            x1,y1 = pos[a]; x2,y2 = pos[b]
            c.create_line(x1+70,y1,x2-70,y2,arrow='last',arrowshape=(12,14,6),fill='#dc2626' if a in critical and b in critical else '#64748b',width=3 if a in critical and b in critical else 2)
        for name, (x,y) in pos.items():
            c.create_rectangle(x-70,y-26,x+70,y+26,fill='#fee2e2' if name in critical else '#e0e7ff',outline='#dc2626' if name in critical else '#4338ca',width=3 if name in critical else 2)
            c.create_text(x,y-7,text=name,font=('Arial',10,'bold'))
            c.create_text(x,y+12,text=f'{steps[name]["duration"]} min',fill='#475569')
        c.configure(scrollregion=(0,0,width,height))

    def update_clock(self):
        self.clock.configure(text=f'Simulation {self.minute:02d}:00')
        if not self.result: return
        slots = self.result['schedule']['slots']
        running = [x['name'] for x in slots if x['start'] <= self.minute < x['end']]
        done = [x['name'] for x in slots if x['end'] <= self.minute]
        self.active.configure(text=f'Running: {", ".join(running) or "none"}    |    Completed: {", ".join(done) or "none"}')

    def next_minute(self):
        if not self.result: return
        self.minute = min(self.minute+1, self.result['schedule']['optimized_minutes'])
        self.draw_timeline()
        if self.minute >= self.result['schedule']['optimized_minutes']: self.pause()

    def play(self):
        if not self.result or self.playing: return
        if self.minute >= self.result['schedule']['optimized_minutes']: self.minute = 0
        self.playing = True; self.tick()

    def tick(self):
        if not self.playing: return
        self.next_minute()
        if self.playing:
            delay = int(1000/int(self.speed.get().rstrip('×')))
            self.after_id = self.after(delay, self.tick)

    def pause(self):
        self.playing = False
        if self.after_id is not None:
            self.after_cancel(self.after_id); self.after_id = None

    def reset(self):
        self.pause(); self.minute = 0; self.draw_timeline()

if __name__ == '__main__': App().mainloop()
