import json
import unittest
from pathlib import Path

from app.orchestrator import Orchestrator


TEMPLATES = json.loads((Path(__file__).resolve().parents[2] /
    'frontend/src/components/scenarioTemplates.json').read_text(encoding='utf-8'))


class ScenarioTemplatesTest(unittest.TestCase):
    def test_every_template_runs_its_actions_once_when_triggered(self):
        for template in TEMPLATES:
            with self.subTest(template=template['key']):
                home = Orchestrator()
                home.scenarios.clear()
                scenario = home.create_scenario(template['scenario'])
                condition = scenario['when']
                value = condition['value'] + {'>': 1, '<': -1, '==': 0}[condition['operator']]
                # Inject the measured condition, then run the real rule engine.
                home.devices[condition['device']].set_value(condition['signal'], value)
                home._evaluate_scenarios()
                for action in scenario['do']:
                    self.assertEqual(home.devices[action['device']].signals[action['signal']].value, action['value'])
                events = [e for e in home.events if e['type'] == 'scenario_triggered']
                self.assertEqual(len(events), 1)
                home._evaluate_scenarios()
                self.assertEqual(len([e for e in home.events if e['type'] == 'scenario_triggered']), 1)

    def test_fire_template_turns_off_every_kitchen_heater(self):
        home = Orchestrator()
        home.scenarios.clear()
        home.create_scenario(next(t['scenario'] for t in TEMPLATES if t['key'] == 'fire'))
        for signal in ['burner_1', 'burner_2', 'burner_3', 'burner_4']:
            home.request_command('stove_1', signal, 5, False)
        home.request_command('oven_1', 'power', 1, False)
        home.request_command('kettle_1', 'power', 1, False)
        home.devices['fire_1'].set_smoke(80)
        home.step()
        self.assertEqual(home.devices['fire_1'].signals['alarm'].value, 1)
        self.assertEqual([home.devices['stove_1'].signals[f'burner_{i}'].value for i in range(1, 5)], [0, 0, 0, 0])
        self.assertEqual(home.devices['oven_1'].signals['power'].value, 0)
        self.assertEqual(home.devices['kettle_1'].signals['power'].value, 0)


if __name__ == '__main__':
    unittest.main()
