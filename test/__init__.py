from test.integrationtests.skills.skill_tester import SkillTest
from mock import MagicMock


class MockLight():
    def __init__(self):
        self.label = "Bedroom"
        self.group = MockGroup()
        self._color = [0, 0, 0, 3500]
        self._power = False

    def get_color(self):
        return self._color

    def get_label(self):
        return self.label

    def get_group_label(self):
        return self.group.get_label()

    def set_colortemp(self, temp, duration=None):
        self._color[3] = temp

    def set_brightness(self, bright, duration=None):
        self._color[2] = bright

    def set_saturation(self, sat, duration=None):
        self._color[1] = sat

    def set_power(self, pwr, duration=None):
        self._power = pwr


class MockGroup:
    def __init__(self):
        super().__init__()
        self.label = "Room 1"
        self._color = [0, 0, 0, 3500]
        self._power = False

    def get_label(self):
        return self.label

    def set_colortemp(self, temp, duration=None):
        self._color[3] = temp

    def set_brightness(self, bright, duration=None):
        self._color[2] = bright

    def set_saturation(self, sat, duration=None):
        self._color[1] = sat

    def set_power(self, pwr, duration=None):
        self._power = pwr


def test_runner(skill, example, emitter, loader):
    s = [s for s in loader.skills if s and s.root_dir == skill][0]

    s.lights = {"Bedroom": MockLight()}
    s.groups = {"Room 1": MockGroup()}

    s.lifxlan = MagicMock()

    s.lifxlan.get_lights.return_value = [s.lights["Bedroom"]]
    s.lifxlan.get_devices_by_group.return_value = [s.lights["Bedroom"]]

    s.targets = {"Bedroom": MockLight(),
                 "Room 1": MockGroup()}

    s.register_vocabulary("Bedroom", "Target")
    s.register_vocabulary("Room 1", "Target")

    res = SkillTest(skill, example, emitter).run(loader)
    if example.endswith('006.handle_toggle_context.intent.json'):
        s.remove_context('Target')
    return res
