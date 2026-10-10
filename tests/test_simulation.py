import unittest
from recipelang import compile_recipe
from simulation import next_event, simulation_state


class SimulationTests(unittest.TestCase):
    def test_events_skip_idle_minutes_and_complete_together(self):
        result = compile_recipe('step a\n duration 10 min\nend\nstep b\n duration 10 min\nend')
        self.assertEqual(next_event(result, 0), 10)
        self.assertEqual(next_event(result, 10), 10)
        self.assertTrue(all(s['status'] == 'Running' for s in simulation_state(result, 0)))
        self.assertTrue(all(s['status'] == 'Completed' for s in simulation_state(result, 10)))

    def test_dependency_and_resource_reasons_at_event_boundary(self):
        result = compile_recipe('resource pan 1\nstep a\n duration 5 min\n uses pan\nend\n'
                                'step b\n duration 2 min\n uses pan\nend\n'
                                'step c\n duration 3 min\n needs a\nend')
        state = {s['name']: s for s in simulation_state(result, 0)}
        self.assertEqual(state['b']['kind'], 'resources')
        self.assertIn('pan held by a', state['b']['reason'])
        self.assertEqual(state['c']['kind'], 'dependencies')
        state = {s['name']: s for s in simulation_state(result, 5)}
        self.assertEqual(state['a']['status'], 'Completed')
        self.assertEqual(state['b']['status'], 'Running')
        self.assertEqual(state['c']['status'], 'Running')

    def test_reservation_and_deliberate_wait_are_not_false_resource_block(self):
        result = {'ast': {'resources': {'pan': 1}, 'steps': {
            'a': {'duration': 5, 'needs': []}, 'b': {'duration': 2, 'needs': []}}},
            'schedule': {'optimized_minutes': 10, 'slots': [
                {'name': 'a', 'start': 5, 'end': 10, 'uses': ['pan']},
                {'name': 'b', 'start': 2, 'end': 4, 'uses': ['pan']}]}}
        state = {s['name']: s for s in simulation_state(result, 0)}
        self.assertEqual(state['a']['kind'], 'reservation')
        self.assertEqual(state['b']['kind'], 'scheduled')
        self.assertEqual(next_event(result, 0), 2)
        self.assertEqual(next_event(result, 4), 5)
