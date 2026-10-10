import random
import unittest
from functools import lru_cache
from itertools import combinations
from recipelang import Recipe, Step, schedule, exact_schedule, place_in_order, topological
from schedule_validator import validate_schedule


def brute_force_minutes(recipe):
    """Independent tiny-instance oracle: advance one minute, allowing idling."""
    names = list(recipe.steps)
    horizon = sum(s.duration for s in recipe.steps.values())

    @lru_cache(None)
    def visit(t, done, running):
        done = set(done)
        running = dict(running)
        if len(done) == len(names):
            return t
        if t >= horizon:
            return horizon
        ready = [n for n in names if n not in done and n not in running
                 and set(recipe.steps[n].needs) <= done]
        best = horizon
        for count in range(len(ready)+1):
            for chosen in combinations(ready, count):
                active = set(running) | set(chosen)
                if any(sum(r in recipe.steps[n].uses for n in active) > cap for r, cap in recipe.resources.items()):
                    continue
                work = dict(running, **{n: recipe.steps[n].duration for n in chosen})
                completed = done | {n for n, remaining in work.items() if remaining == 1}
                future = tuple(sorted((n, remaining-1) for n, remaining in work.items() if remaining > 1))
                best = min(best, visit(t+1, tuple(sorted(completed)), future))
        return best
    return visit(0, (), ())


class PriorityTests(unittest.TestCase):
    def test_large_recipe_improves_source_order(self):
        recipe = Recipe(resources={'pan': 1})
        recipe.steps = {'a': Step('a', 5, uses=['pan']), 'b': Step('b', 1, uses=['pan']),
                        'c': Step('c', 10, needs=['b'])}
        recipe.steps.update({f'f{i}': Step(f'f{i}', 1) for i in range(6)})
        old = max(s.end for s in place_in_order(recipe, topological(recipe)))
        result = schedule(recipe)
        self.assertEqual(old, 16)
        self.assertEqual(result['optimized_minutes'], 11)
        self.assertTrue(result['provably_optimal'])
        self.assertTrue(validate_schedule(recipe, result))

    def test_resource_bound_exceeds_critical_path(self):
        recipe = Recipe(resources={'pan': 2}, steps={f'a{i}': Step(f'a{i}', 3, uses=['pan']) for i in range(5)})
        result = schedule(recipe)
        self.assertEqual(result['critical_path_lower_bound'], 3)
        self.assertEqual(result['lower_bound'], 8)
        self.assertEqual(result['optimized_minutes'], 9)
        self.assertTrue(result['provably_optimal'])

    def test_bounds_and_exact_search_against_minute_oracle(self):
        rng = random.Random(17)
        for case in range(16):
            recipe = Recipe(resources={'pan': rng.randint(1, 2), 'cook': 1})
            for i in range(5):
                name = f's{i}'
                recipe.steps[name] = Step(name, rng.randint(1, 3),
                    needs=[n for n in recipe.steps if rng.random() < .25],
                    uses=[r for r in recipe.resources if rng.random() < .5])
            with self.subTest(case=case):
                expected = brute_force_minutes(recipe)
                result = schedule(recipe)
                self.assertLessEqual(result['lower_bound'], expected)
                self.assertEqual(result['optimized_minutes'], expected)
                self.assertTrue(validate_schedule(recipe, result))
                exact, _ = exact_schedule(recipe)
                self.assertEqual(max(s['end'] for s in exact), expected)

    def test_exact_budget_is_honest(self):
        recipe = Recipe(steps={'a': Step('a', 1)})
        slots, states = exact_schedule(recipe, state_limit=0)
        self.assertIsNone(slots)
        self.assertEqual(states, 1)
