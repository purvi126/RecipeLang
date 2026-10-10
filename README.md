# RecipeLang — Review 2 Final Release

This is a separate final-release copy of the submitted RecipeLang implementation. Original versions remain unchanged.

## Ubuntu / WSL2 setup

```bash
cd /mnt/d/purvi/Downloads/RecipeLang_Review2_Final/RecipeLang_Review2_Complete
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
3. The token table, AST and DAG data are populated as their respective phases execute; final schedule and timeline appear on completion.
4. Switch to **Timeline**, **Tokens**, **AST**, **Symbol table**, **Dependency DAG**, and **Scheduler** to explain the output.
5. Try **Play**, **Pause**, **Next minute**, **Reset**, and speed controls. Open `examples/complex.recipe` for the eight-step demonstration.
6. Click **Export all** to save labeled Gantt and DAG PNGs, compilation/tokens/AST/graph/schedule JSON and timeline CSV.

## Scheduling guarantees and limitations

- The scheduler respects explicit dependencies and declared resource capacities. The independent validator checks its output.
- Exact event-time search is attempted only for recipes with up to eight steps and has a 120,000-state budget; it may fall back to a heuristic. **Only claim optimality when the result's `provably_optimal` flag is true, or the makespan matches a valid lower bound.**
- Time resolution is whole minutes; `uses` requires one unit of each named resource.
- The critical-path lower bound ignores resource contention.
- The phase display uses Tkinter's event loop between stages. A long individual scheduling phase can still temporarily occupy the UI thread. It is not a continuous token-by-token animation.
- PNG exports require Pillow; compiler, CLI, GUI and JSON/CSV exports otherwise use Python standard library.

## What changed since the prior build

- True phase-by-phase compilation via lazy `compile_stages()` generator, retaining synchronous `compile_recipe()` API.
- Actual lexer source columns instead of GUI guesses.
- Exported Gantt chart includes task names, time ticks, durations; exported DAG includes names, durations and directed dependency arrows.
- Added final-release regression tests and corrected the documentation.

## Verification

Run `python3 -m unittest discover -s tests -v` and check the actual result on your machine. GUI appearance and playback must also be verified on your Ubuntu/WSLg setup.
