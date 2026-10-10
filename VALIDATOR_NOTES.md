# Independent schedule validation

`compile_recipe` now calls `validate_schedule` after scheduling and before reporting success. The validator checks each step exactly once, nonnegative integer start times, exact durations, resource lists, predecessor completion, concurrent resource capacities, and makespan consistency.

The scheduling algorithm is **unchanged** and remains a heuristic. The validator proves feasibility of the produced schedule against these checks, **not global optimality**.

Run: `python3 -m unittest discover -s tests -v`
