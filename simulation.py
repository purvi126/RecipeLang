"""Read-only event simulation of the compiled schedule, using [start, end) times."""


def next_event(result, minute):
    events = {s[key] for s in result['schedule']['slots'] for key in ('start', 'end')}
    return min((t for t in events if t > minute), default=result['schedule']['optimized_minutes'])


def simulation_state(result, minute):
    slots = result['schedule']['slots']
    by_name = {s['name']: s for s in slots}
    steps = result['ast']['steps']
    capacities = result['ast']['resources']
    state = []
    for slot in slots:
        name = slot['name']
        if slot['end'] <= minute:
            status, kind, reason = 'Completed', 'completed', f'Finished at {slot["end"]} min'
        elif slot['start'] <= minute:
            status, kind, reason = 'Running', 'running', f'Finishes at {slot["end"]} min'
        else:
            status = 'Waiting'
            pending = [n for n in steps[name]['needs'] if by_name[n]['end'] > minute]
            if pending:
                kind = 'dependencies'
                reason = 'Dependencies: ' + ', '.join(f'{n} (ends {by_name[n]["end"]})' for n in pending)
            else:
                blocked, reserved = [], []
                for resource in slot['uses']:
                    active = [s for s in slots if resource in s['uses'] and s['start'] <= minute < s['end']]
                    if len(active) >= capacities[resource]:
                        blocked.append(f'{resource} held by ' + ', '.join(s['name'] for s in active))
                    else:
                        # Availability now does not imply a nonpreemptive task fits:
                        # a future reserved interval can consume the last unit.
                        end = minute + steps[name]['duration']
                        points = {minute} | {s['start'] for s in slots if minute < s['start'] < end}
                        for t in sorted(points):
                            holders = [s['name'] for s in slots if s['name'] != name and resource in s['uses'] and s['start'] <= t < s['end']]
                            if len(holders) >= capacities[resource]:
                                reserved.append(f'{resource} reserved at {t} for ' + ', '.join(holders))
                                break
                if blocked:
                    kind, reason = 'resources', '; '.join(blocked)
                elif reserved:
                    kind, reason = 'reservation', '; '.join(reserved)
                else:
                    kind, reason = 'scheduled', 'Ready; waiting for the compiled schedule'
            reason += f'; starts at {slot["start"]} min'
        state.append({'name': name, 'status': status, 'kind': kind, 'reason': reason})
    return state
