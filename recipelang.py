"""RecipeLang: lexer, parser, semantic validation, DAG IR and resource scheduling."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from itertools import permutations, combinations
import argparse, json, re
from schedule_validator import validate_schedule

class RecipeError(Exception):
    def __init__(self, phase, message, line=0):
        super().__init__(f'{phase} error' + (f' at line {line}' if line else '') + f': {message}')
        self.phase, self.line, self.message = phase, line, message

@dataclass
class Token:
    kind: str
    value: str
    line: int
    column: int = 1

@dataclass
class Ingredient:
    name: str
    quantity: float
    unit: str
    line: int

@dataclass
class Step:
    name: str
    duration: int
    needs: list[str] = field(default_factory=list)
    uses: list[str] = field(default_factory=list)
    takes: list[tuple[str, float, str]] = field(default_factory=list)
    line: int = 0

@dataclass
class Recipe:
    ingredients: dict[str, Ingredient] = field(default_factory=dict)
    resources: dict[str, int] = field(default_factory=dict)
    steps: dict[str, Step] = field(default_factory=dict)

@dataclass
class Slot:
    name: str
    start: int
    end: int
    uses: list[str]

KEYWORDS = {'ingredient','resource','step','end','duration','needs','uses','takes'}
UNITS = {'pcs': ('count', 1), 'pc': ('count', 1), 'g': ('mass', 1), 'kg': ('mass', 1000),
         'ml': ('volume', 1), 'l': ('volume', 1000), 'cup': ('volume', 240), 'cups': ('volume', 240),
         'tsp': ('volume', 5), 'tbsp': ('volume', 15), 'mg': ('mass', 0.001)}
TOKEN_RE = re.compile(r'(?P<SPACE>[ \t\r]+)|(?P<COMMENT>\#[^\n]*)|(?P<NEWLINE>\n)|(?P<NUMBER>\d+(?:\.\d+)?)|(?P<IDENT>[A-Za-z_][A-Za-z_0-9]*)|(?P<COMMA>,)|(?P<BAD>.)')

def lex(source):
    tokens, line, line_start = [], 1, 0
    for m in TOKEN_RE.finditer(source):
        kind, value = m.lastgroup, m.group()
        if kind == 'NEWLINE':
            tokens.append(Token('NEWLINE', value, line, m.start()-line_start+1)); line += 1; line_start = m.end()
        elif kind == 'BAD':
            raise RecipeError('Lexical', f'unrecognized character {value!r}', line)
        elif kind not in ('SPACE', 'COMMENT'):
            tokens.append(Token('KEYWORD' if value in KEYWORDS else kind, value, line, m.start()-line_start+1))
    tokens.append(Token('EOF', '', line, len(source)-line_start+1))
    return tokens

class Parser:
    def __init__(self, tokens):
        self.lines = []
        current = []
        for token in tokens:
            if token.kind in ('NEWLINE', 'EOF'):
                if current: self.lines.append(current)
                current = []
            else: current.append(token)

    @staticmethod
    def fail(line, msg): raise RecipeError('Syntax', msg, line)

    def parse(self):
        recipe, current = Recipe(), None
        for row in self.lines:
            words = [t.value for t in row]
            command, line = words[0], row[0].line
            if current is None:
                if command == 'ingredient':
                    if len(words) != 4 or row[2].kind != 'NUMBER' or row[1].kind != 'IDENT': self.fail(line, 'expected: ingredient NAME NUMBER UNIT')
                    name = words[1]
                    if name in recipe.ingredients: self.fail(line, f'duplicate ingredient {name}')
                    recipe.ingredients[name] = Ingredient(name, float(words[2]), words[3], line)
                elif command == 'resource':
                    if len(words) != 3 or row[2].kind != 'NUMBER' or row[1].kind != 'IDENT': self.fail(line, 'expected: resource NAME INTEGER')
                    if words[1] in recipe.resources: self.fail(line, f'duplicate resource {words[1]}')
                    if not float(words[2]).is_integer(): self.fail(line, 'resource capacity must be an integer')
                    recipe.resources[words[1]] = int(words[2])
                elif command == 'step':
                    if len(words) != 2 or row[1].kind != 'IDENT': self.fail(line, 'expected: step NAME')
                    if words[1] in recipe.steps: self.fail(line, f'duplicate step {words[1]}')
                    current = Step(words[1], 0, line=line)
                    recipe.steps[current.name] = current
                    current._seen = set()
                else: self.fail(line, f'unexpected declaration {command!r}')
            else:
                if command == 'end':
                    if len(words) != 1: self.fail(line, 'end takes no arguments')
                    if 'duration' not in current._seen: self.fail(line, f'step {current.name} missing duration')
                    del current._seen
                    current = None
                    continue
                if command not in ('duration', 'needs', 'uses', 'takes'): self.fail(line, f'unknown step field {command!r}')
                if command in current._seen and command != 'takes': self.fail(line, f'duplicate field {command} in {current.name}')
                current._seen.add(command)
                args = row[1:]
                if command == 'duration':
                    if len(args) != 2 or args[0].kind != 'NUMBER' or args[1].value not in ('min', 'hr', 'sec'): self.fail(line, 'expected: duration NUMBER min|hr|sec')
                    minutes = float(args[0].value) * {'min':1, 'hr':60, 'sec':1/60}[args[1].value]
                    if not minutes.is_integer(): self.fail(line, 'duration must resolve to whole minutes')
                    current.duration = int(minutes)
                elif command in ('needs', 'uses'):
                    if not args or len(args) % 2 != 1 or any(t.kind != 'IDENT' for t in args[::2]) or any(t.kind != 'COMMA' for t in args[1::2]):
                        self.fail(line, f'expected: {command} NAME, NAME, ...')
                    setattr(current, command, [t.value for t in args[::2]])
                elif command == 'takes':
                    if len(args) != 3 or args[0].kind != 'IDENT' or args[1].kind != 'NUMBER' or args[2].kind != 'IDENT': self.fail(line, 'expected: takes INGREDIENT NUMBER UNIT')
                    current.takes.append((args[0].value, float(args[1].value), args[2].value))
        if current is not None: self.fail(current.line, f'step {current.name} missing end')
        return recipe

def validate(recipe):
    if not recipe.steps: raise RecipeError('Semantic', 'recipe has no steps')
    for ing in recipe.ingredients.values():
        if ing.unit not in UNITS: raise RecipeError('Semantic', f'unknown unit {ing.unit}', ing.line)
        if ing.quantity <= 0: raise RecipeError('Semantic', f'ingredient {ing.name} must have positive quantity', ing.line)
    for name, count in recipe.resources.items():
        if count <= 0: raise RecipeError('Semantic', f'resource {name} must have positive capacity')
    consumed = defaultdict(float)
    for step in recipe.steps.values():
        if step.duration <= 0: raise RecipeError('Semantic', f'{step.name} duration must be positive', step.line)
        if len(step.needs) != len(set(step.needs)): raise RecipeError('Semantic', f'{step.name} has repeated dependencies', step.line)
        if len(step.uses) != len(set(step.uses)): raise RecipeError('Semantic', f'{step.name} has repeated resources', step.line)
        for need in step.needs:
            if need not in recipe.steps: raise RecipeError('Semantic', f'{step.name} needs undefined step {need}', step.line)
        for resource in step.uses:
            if resource not in recipe.resources: raise RecipeError('Semantic', f'{step.name} uses undefined resource {resource}', step.line)
        for name, quantity, unit in step.takes:
            if name not in recipe.ingredients: raise RecipeError('Semantic', f'{step.name} takes undefined ingredient {name}', step.line)
            if unit not in UNITS: raise RecipeError('Semantic', f'unknown unit {unit}', step.line)
            original = recipe.ingredients[name]
            if UNITS[unit][0] != UNITS[original.unit][0]: raise RecipeError('Semantic', f'incompatible units for {name}: {original.unit} vs {unit}', step.line)
            if quantity <= 0: raise RecipeError('Semantic', f'{name} consumption must be positive', step.line)
            consumed[name] += quantity * UNITS[unit][1]
    for name, amount in consumed.items():
        ing = recipe.ingredients[name]
        if amount > ing.quantity * UNITS[ing.unit][1] + 1e-9:
            raise RecipeError('Semantic', f'not enough {name}: need {amount:g} base units, have {ing.quantity * UNITS[ing.unit][1]:g}', ing.line)
    state = {}
    def visit(name):
        if state.get(name) == 1: raise RecipeError('Semantic', f'cyclic dependency involving {name}', recipe.steps[name].line)
        if state.get(name) == 2: return
        state[name] = 1
        for dep in recipe.steps[name].needs: visit(dep)
        state[name] = 2
    for name in recipe.steps: visit(name)
    return {'ingredients': {k: asdict(v) for k, v in recipe.ingredients.items()}, 'resources': recipe.resources,
            'steps': {k: asdict(v) for k, v in recipe.steps.items()}, 'edges': [[dep, step.name] for step in recipe.steps.values() for dep in step.needs]}

def topological(recipe):
    seen, result = set(), []
    def walk(name):
        if name in seen: return
        seen.add(name)
        for dep in recipe.steps[name].needs: walk(dep)
        result.append(name)
    for name in recipe.steps: walk(name)
    return result

def critical_path(recipe):
    memo = {}
    def longest(name):
        if name not in memo: memo[name] = recipe.steps[name].duration + max((longest(d) for d in recipe.steps[name].needs), default=0)
        return memo[name]
    return max(longest(n) for n in recipe.steps)

def place_in_order(recipe, order):
    slots = {}
    for name in order:
        step = recipe.steps[name]
        earliest = max((slots[d].end for d in step.needs), default=0)
        t = earliest
        while True:
            # Capacity test at all change-points inside the proposed interval.
            boundaries = {t, t + step.duration}
            for s in slots.values():
                if s.start < t + step.duration and s.end > t:
                    boundaries.add(max(t, s.start)); boundaries.add(min(t + step.duration, s.end))
            points = sorted(boundaries)
            conflict_end = None
            for a, b in zip(points, points[1:]):
                if a == b: continue
                for res in step.uses:
                    active = [s for s in slots.values() if res in s.uses and s.start < b and s.end > a]
                    if len(active) >= recipe.resources[res]:
                        conflict_end = min(s.end for s in active) if conflict_end is None else min(conflict_end, min(s.end for s in active))
            if conflict_end is None: break
            t = max(t + 1, conflict_end)
        slots[name] = Slot(name, t, t + step.duration, step.uses[:])
    return sorted(slots.values(), key=lambda s: (s.start, s.end, s.name))


def exact_schedule(recipe, state_limit=120000):
    """Exact event-time branch-and-bound for small nonpreemptive RCPSP instances.

    At every completion event, branch over feasible subsets of newly ready jobs,
    including deliberate idling while jobs run. This enumerates active and
    non-delay alternatives. Returns None on state-budget exhaustion.
    """
    names = tuple(sorted(recipe.steps))
    best = None
    best_finish = float('inf')
    explored = 0
    seen = {}
    capacities = recipe.resources

    class BudgetExceeded(Exception): pass

    def recurse(t, done, running, slots):
        nonlocal best, best_finish, explored
        explored += 1
        if explored > state_limit: raise BudgetExceeded()
        if len(done) == len(names):
            if t < best_finish:
                best_finish = t
                best = [dict(x) for x in slots]
            return
        if t >= best_finish: return
        key = (tuple(sorted(done)), tuple(sorted((n, end-t) for n, end in running.items())))
        if seen.get(key, float('inf')) <= t: return
        seen[key] = t
        active = set(running)
        ready = [n for n in names if n not in done and n not in active
                 and all(dep in done for dep in recipe.steps[n].needs)]
        used = {r: sum(r in recipe.steps[n].uses for n in active) for r in capacities}
        subsets = []
        for count in range(len(ready), -1, -1):
            for subset in combinations(ready, count):
                if not subset and not running: continue
                if all(used[r] + sum(r in recipe.steps[n].uses for n in subset) <= capacities[r] for r in capacities):
                    subsets.append(subset)
        for subset in subsets:
            new_running = dict(running)
            new_slots = list(slots)
            for n in subset:
                step = recipe.steps[n]
                end = t + step.duration
                new_running[n] = end
                new_slots.append({'name': n, 'start': t, 'end': end, 'uses': list(step.uses)})
            if not new_running: continue
            next_t = min(new_running.values())
            finished = {n for n, end in new_running.items() if end == next_t}
            recurse(next_t, done | finished,
                    {n:end for n,end in new_running.items() if end > next_t}, new_slots)

    try: recurse(0, set(), {}, [])
    except BudgetExceeded: return None, explored
    return sorted(best, key=lambda x: (x['start'], x['end'], x['name'])), explored


def schedule(recipe):
    n = len(recipe.steps)
    order = topological(recipe)
    heuristic = place_in_order(recipe, order)
    tested = 1
    if n <= 8:
        # Improve the heuristic incumbent by enumerating topological priority lists.
        best = heuristic
        def explore(prefix, remaining):
            nonlocal best, tested
            if not remaining:
                candidate = place_in_order(recipe, prefix)
                tested += 1
                if max(s.end for s in candidate) < max(s.end for s in best): best = candidate
                return
            for name in sorted(remaining):
                if all(d in prefix for d in recipe.steps[name].needs):
                    explore(prefix + [name], remaining - {name})
        explore([], set(recipe.steps))
        heuristic = best
    slots = [asdict(s) for s in heuristic]
    method = 'topological earliest-feasible heuristic'
    optimal = False
    states = 0
    if n <= 8:
        exact, states = exact_schedule(recipe)
        if exact is not None:
            slots = exact
            method = 'exact event-time exhaustive search (provably optimal for this instance)'
            optimal = True
        else:
            method += ' (exact search exceeded state budget)'
    baseline = sum(s.duration for s in recipe.steps.values())
    finish = max(s['end'] for s in slots)
    return {'slots': slots, 'sequential_minutes': baseline, 'optimized_minutes': finish,
            'minutes_saved': baseline-finish, 'improvement_percent': round(100*(baseline-finish)/baseline, 2),
            'critical_path_lower_bound': critical_path(recipe), 'method': method,
            'provably_optimal': optimal, 'exact_states_evaluated': states,
            'priority_orders_evaluated': tested}


def critical_path_nodes(recipe):
    """Return nodes on any dependency-only longest path."""
    order = topological(recipe)
    finish = {}
    for n in order:
        finish[n] = recipe.steps[n].duration + max((finish[d] for d in recipe.steps[n].needs), default=0)
    maximum = max(finish.values())
    critical = set()
    def backtrack(n):
        if n in critical: return
        critical.add(n)
        for dep in recipe.steps[n].needs:
            if finish[dep] == finish[n] - recipe.steps[n].duration: backtrack(dep)
    for n in order:
        if finish[n] == maximum: backtrack(n)
    return sorted(critical)

def compile_stages(source):
    """Execute compiler stages lazily. Each yield occurs AFTER real work completes.

    The GUI advances this generator on Tk's event loop; no phase is fabricated.
    """
    phases = []
    tokens = lex(source)
    phases.append(f'Lexical analysis: {len(tokens)-1} tokens')
    yield ('Lexical analysis', phases[-1], {'tokens': [asdict(t) for t in tokens if t.kind != 'EOF']})
    recipe = Parser(tokens).parse()
    phases.append(f'Syntax analysis: AST with {len(recipe.steps)} steps')
    yield ('Syntax analysis', phases[-1], {'ast': asdict(recipe)})
    ir = validate(recipe)
    phases.append('Semantic analysis: passed (units, names, quantities, DAG)')
    yield ('Semantic analysis', phases[-1], {'ir': ir})
    phases.append(f'Symbol table: {len(recipe.ingredients)} ingredients, {len(recipe.resources)} resources, {len(recipe.steps)} steps')
    yield ('Symbol table', phases[-1], {'ast': asdict(recipe)})
    phases.append(f'Dependency graph IR: {len(ir["edges"])} edges')
    yield ('Dependency graph IR', phases[-1], {'ir': ir, 'ast': asdict(recipe)})
    result = schedule(recipe)
    phases.append(f'Schedule optimization: {result["method"]}')
    yield ('Schedule optimization', phases[-1], {'schedule': result})
    validate_schedule(recipe, result)
    phases.append('Resource validation: independently verified (dependencies, durations, capacities)')
    yield ('Resource validation', phases[-1], {'schedule': result})
    phases.append('Timeline generation: complete')
    compiled = {'phases': phases, 'tokens': [asdict(t) for t in tokens if t.kind != 'EOF'],
                'ast': asdict(recipe), 'ir': ir, 'schedule': result,
                'critical_path_nodes': critical_path_nodes(recipe)}
    yield ('Timeline generation', phases[-1], {'result': compiled})


def compile_recipe(source):
    """Synchronous compiler API; retains backward compatibility with CLI/tests."""
    final = None
    for _, _, snapshot in compile_stages(source):
        if 'result' in snapshot:
            final = snapshot['result']
    return final

def timeline(result):
    s = result['schedule']
    lines = [f'{x["start"]:02d}:00 - {x["end"]:02d}:00 | {x["name"]} [{", ".join(x["uses"]) or "no resources"}]' for x in s['slots']]
    return '\n'.join(lines + [f'FINISHED at {s["optimized_minutes"]} min; sequential {s["sequential_minutes"]} min; saved {s["minutes_saved"]} min'])

def main():
    ap = argparse.ArgumentParser(description='Compile and schedule a RecipeLang recipe')
    ap.add_argument('file', help='.recipe source file')
    ap.add_argument('--json', dest='json_file', help='write complete compiler results as JSON')
    ap.add_argument('--tokens', action='store_true')
    ap.add_argument('--ast', action='store_true')
    ap.add_argument('--ir', action='store_true')
    args = ap.parse_args()
    try:
        with open(args.file, encoding='utf-8') as f: result = compile_recipe(f.read())
        for phase in result['phases']: print('✓', phase)
        if args.tokens: print('\nTOKENS:', json.dumps(result['tokens'], indent=2))
        if args.ast: print('\nAST:', json.dumps(result['ast'], indent=2))
        if args.ir: print('\nIR:', json.dumps(result['ir'], indent=2))
        print('\nOPTIMIZED COOKING TIMELINE\n' + timeline(result))
        print('Scheduling method:', result['schedule']['method'])
        if args.json_file:
            with open(args.json_file, 'w', encoding='utf-8') as f: json.dump(result, f, indent=2)
            print('Saved', args.json_file)
    except (RecipeError, OSError) as e:
        ap.exit(1, f'ERROR: {e}\n')

if __name__ == '__main__': main()
