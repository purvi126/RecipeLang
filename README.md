# RecipeLang — Compiler Workbench

The original Review 2 version is preserved on `main` at baseline commit `4b28152`.
The improvements are on `improvements/editor-scheduler-simulation`. Existing recipe
syntax, units, CLI, synchronous compiler API, and the eight live phases are preserved.
Historical sample exports and release notes remain available unchanged.

## Windows setup

Run these commands from the project directory (Python with Tkinter installed):

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m unittest discover -s tests -v
.\.venv\Scripts\python gui.py
```

## Ubuntu / WSL2 setup

```bash
# Run from your project directory.
sudo apt install python3-tk python3-pil
python3 -m unittest discover -s tests -v
python3 gui.py
```

If `python3-pil` is unavailable for your Python environment, install Pillow in a virtual environment:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python gui.py
```

CLI: `python3 recipelang.py examples/demo.recipe`.

## Live compilation walkthrough

1. Open the **Compiler phases** tab (or click **Compile + Optimize**, which selects it automatically).
2. The application now runs the *actual* lexer, parser, semantic validation, symbol table, dependency IR, scheduler, independent validator, and final timeline as eight separately scheduled operations. It displays progress as each finishes. This is **real staged execution**, not a replay of precomputed logs.
3. Tokens, AST, symbol table, DAG, and scheduler data appear as their respective phases execute. The timeline becomes available after independent validation.
4. Switch to **Timeline**, **Tokens**, **AST**, **Symbol table**, **Dependency DAG**, and **Scheduler** to explain the output.
5. Try **Next event**, **Play**, **Pause**, **Next minute**, **Reset**, and speed controls. Playback defaults to **Events**; choose **Minutes** to retain minute-by-minute playback. Open `examples/complex.recipe` for the eight-step demonstration.
6. Click **Export all** to save labeled Gantt and DAG PNGs, compilation/tokens/AST/graph/schedule JSON and timeline CSV.

## Editor, graph, and simulation

- The editor highlights keywords, quantities, units, comments, and invalid characters even while a recipe is incomplete. Line numbers follow scrolling. Underlined errors in **Compiler phases** jump to the reported source line when clicked; errors without a source line are displayed without a link.
- Editing or loading source cancels pending compilation/playback and clears outdated results. Click **Compile + Optimize** to run a fresh snapshot.
- In **Dependency DAG**, use **+**, **−**, **Fit**, and **100%**. Drag to pan or use the scrollbars. Ctrl+wheel zooms; Ctrl+Button-4/5 is supported on Linux.
- **Next event** jumps to the next start or finish time. All changes at the same minute happen together: task intervals include their start and exclude their end.
- The simulation table explains unfinished dependencies, occupied resources and their holders, future resource reservations, or deliberate waiting for a scheduled start. This replays the validated schedule; it does not reschedule tasks during playback. Speed controls the delay per event or minute.

## Scheduling guarantees and limitations

- The scheduler respects explicit dependencies and declared resource capacities. The independent validator checks its output.
- Exact event-time search is attempted only for recipes with up to eight steps and has a 120,000-state budget; it may fall back to a heuristic. **Only claim optimality when the result's `provably_optimal` flag is true, or the makespan matches a valid lower bound.**
- Time resolution is whole minutes; `uses` requires one unit of each named resource.
- The critical-path lower bound ignores resource contention.
- Five deterministic priority orders are compared: the original topological order, longest remaining dependency path, least slack, resource pressure, and longest duration. Each uses earliest-feasible placement. Retaining the original order as a candidate prevents regression against that heuristic.
- Each resource contributes `ceil(total usage minutes / capacity)`. A stronger bound adds the minimum dependency release time and minimum downstream tail among its users. The overall `lower_bound` is the maximum of these resource bounds and the critical path; bounds for different resources are not added together.
- Small-instance exact search starts with the best heuristic schedule and prunes using dependency and remaining resource-work bounds. The old factorial priority-list enumeration is no longer needed. Search is skipped when the heuristic already meets the proven lower bound.
- `provably_optimal` is true only after exhaustive search completes or the schedule matches the lower bound. `optimality_gap_minutes` measures distance to the lower bound, not necessarily distance to the true optimum. An exact optimum may still have a positive gap if the bound is loose.
- The phase display uses Tkinter's event loop between stages. A long individual scheduling phase can still temporarily occupy the UI thread. It is not a continuous token-by-token animation.
- PNG exports require Pillow; compiler, CLI, GUI and JSON/CSV exports otherwise use Python standard library.

## Earlier release features

- True phase-by-phase compilation via lazy `compile_stages()` generator, retaining synchronous `compile_recipe()` API.
- Actual lexer source columns instead of GUI guesses.
- Exported Gantt chart includes task names, time ticks, durations; exported DAG includes names, durations and directed dependency arrows.
- Added final-release regression tests and corrected the documentation.

## Verification

Run `python3 -m unittest discover -s tests -v` (or the Windows command above).
The 49 tests include original compatibility/export checks, Windows CLI encoding and JSON export checks, independent minute-grid
exhaustive comparisons on 16 seeded small recipes, capacity bounds, larger-recipe
priority improvements, waiting reasons, and real Tk checks for staged output,
editor diagnostics, graph fit/zoom, and playback controls. Tk tests skip when a
graphical display is unavailable. Ubuntu/WSLg appearance still needs verification
on that platform; the current run used Windows and Python 3.14.
