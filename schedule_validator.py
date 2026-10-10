"""Independent schedule verification for RecipeLang."""
from collections import defaultdict

class ScheduleValidationError(ValueError):
    pass

def validate_schedule(recipe, schedule):
    """Raise on invalid timing, precedence, resource usage, or missing steps.

    Intervals are half-open [start, end). Resource demand is one unit per
    distinct resource listed on a step, matching the current DSL semantics.
    """
    slots = schedule["slots"] if isinstance(schedule, dict) else slots_from(schedule)
    names = [s["name"] for s in slots]
    if len(names) != len(set(names)) or set(names) != set(recipe.steps):
        raise ScheduleValidationError("schedule must contain every step exactly once")
    by_name = {s["name"]: s for s in slots}
    for s in slots:
        step = recipe.steps[s["name"]]
        start, end = s["start"], s["end"]
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise ScheduleValidationError(f"invalid start time for {step.name}")
        if not isinstance(end, int) or isinstance(end, bool) or end-start != step.duration:
            raise ScheduleValidationError(f"invalid duration for {step.name}")
        if sorted(s["uses"]) != sorted(step.uses):
            raise ScheduleValidationError(f"incorrect resources for {step.name}")
        for predecessor in step.needs:
            if by_name[predecessor]["end"] > start:
                raise ScheduleValidationError(f"dependency violation: {predecessor} -> {step.name}")
    for resource, capacity in recipe.resources.items():
        events = []
        for s in slots:
            if resource in s["uses"]:
                events.extend(((s["start"], 1), (s["end"], -1)))
        # Finish events before start events at equal timestamps.
        active = 0
        for timestamp, delta in sorted(events, key=lambda x: (x[0], x[1])):
            active += delta
            if active > capacity:
                raise ScheduleValidationError(f"resource capacity exceeded: {resource} at {timestamp}")
            if active < 0:
                raise ScheduleValidationError(f"invalid resource event sequence: {resource}")
    makespan = max(s["end"] for s in slots)
    if isinstance(schedule, dict) and schedule.get("optimized_minutes") != makespan:
        raise ScheduleValidationError("reported makespan does not match slots")
    return True

def slots_from(slots):
    return slots
