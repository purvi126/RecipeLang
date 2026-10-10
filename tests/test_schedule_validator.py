import unittest
from pathlib import Path
from recipelang import Parser, lex, compile_recipe
from schedule_validator import validate_schedule, ScheduleValidationError

DEMO = (Path(__file__).resolve().parents[1] / "examples" / "demo.recipe").read_text()

class ScheduleValidatorTests(unittest.TestCase):
    def setUp(self):
        self.recipe = Parser(lex(DEMO)).parse()
        self.schedule = compile_recipe(DEMO)["schedule"]

    def test_valid_demo(self):
        self.assertTrue(validate_schedule(self.recipe, self.schedule))

    def test_missing_step(self):
        bad = {**self.schedule, "slots": self.schedule["slots"][:-1]}
        with self.assertRaisesRegex(ScheduleValidationError, "every step"):
            validate_schedule(self.recipe, bad)

    def test_duplicate_step(self):
        bad = {**self.schedule, "slots": self.schedule["slots"] + [self.schedule["slots"][0]]}
        with self.assertRaisesRegex(ScheduleValidationError, "every step"):
            validate_schedule(self.recipe, bad)

    def test_dependency_violation(self):
        slots = [dict(s) for s in self.schedule["slots"]]
        cook = next(s for s in slots if s["name"] == "cook")
        cook["start"], cook["end"] = 0, 15
        with self.assertRaisesRegex(ScheduleValidationError, "dependency"):
            validate_schedule(self.recipe, {**self.schedule, "slots": slots})

    def test_resource_conflict(self):
        slots = [dict(s) for s in self.schedule["slots"]]
        fry = next(s for s in slots if s["name"] == "fry_vegetables")
        fry["start"], fry["end"] = 0, 8
        with self.assertRaisesRegex(ScheduleValidationError, "resource capacity"):
            validate_schedule(self.recipe, {**self.schedule, "slots": slots})

    def test_wrong_duration(self):
        slots = [dict(s) for s in self.schedule["slots"]]
        slots[0]["end"] += 1
        with self.assertRaisesRegex(ScheduleValidationError, "duration"):
            validate_schedule(self.recipe, {**self.schedule, "slots": slots})

    def test_wrong_resource(self):
        slots = [dict(s) for s in self.schedule["slots"]]
        slots[0]["uses"] = []
        with self.assertRaisesRegex(ScheduleValidationError, "resources"):
            validate_schedule(self.recipe, {**self.schedule, "slots": slots})

    def test_wrong_makespan(self):
        with self.assertRaisesRegex(ScheduleValidationError, "makespan"):
            validate_schedule(self.recipe, {**self.schedule, "optimized_minutes": 999})

    def test_parallel_capacity_two(self):
        source = "resource oven 2\n" + "".join(f"step s{i}\n uses oven\n duration 10 min\nend\n" for i in range(3))
        recipe = Parser(lex(source)).parse()
        self.assertTrue(validate_schedule(recipe, compile_recipe(source)["schedule"]))

if __name__ == "__main__": unittest.main()
