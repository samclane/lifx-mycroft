from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG

import lifxlan
import lifxlan.utils
from fuzzywuzzy import fuzz
import webcolors

HUE, SATURATION, BRIGHTNESS, KELVIN = range(4)


class LifxSkill(MycroftSkill):
    dim_step = int(.10 * 65535)
    temperature_step = int(.10 * (9000 - 2500))

    def __init__(self):
        super(LifxSkill, self).__init__(name="LifxSkill")

        self.lifxlan = lifxlan.LifxLAN()
        self.lights = {}
        self.groups = {}

    def initialize(self):
        for light in self.lifxlan.get_lights():
            light: lifxlan.Light = light
            self.lights[light.get_label()] = light
            self.register_vocabulary(light.get_label(), "Light")
            LOG.info("{} was found".format(light.get_label()))
            if not (light.get_group_label() in self.groups.keys()):
                self.groups[light.get_group_label()] = self.lifxlan.get_devices_by_group(light.get_group_label())
                self.register_vocabulary(light.get_group_label(), "Group")
                LOG.info("Group {} was found".format(light.get_group_label()))

        for color_name in webcolors.css3_hex_to_names.values():
            self.register_vocabulary(color_name, "Color")

    def get_target_from_message(self, message):
        if "Light" in message.data:
            target = self.get_fuzzy_value_from_dict(message.data["Light"], self.lights)
            name = message.data["Light"]
        elif "Group" in message.data:
            target = self.get_fuzzy_value_from_dict(message.data["Group"], self.groups)
            name = message.data["Group"]
        else:
            assert False, "Triggered intent without Light or Group. Message: {}".format(message.data["utterance"])

        return target, name

    @staticmethod
    def get_fuzzy_value_from_dict(key, dict_: dict):
        best_score = 0
        score = 0
        best_item = None

        for k, v in dict_.items():
            score = fuzz.ratio(key, k)
            if score > best_score:
                best_score = score
                best_item = v

        return best_item

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group").one_of("Off", "On")
                    .optionally("_TestRunner").build())
    def handle_toggle_intent(self, message):
        if "Off" in message.data:
            power_status = False
            status_str = "Off"
        elif "On" in message.data:
            power_status = True
            status_str = "On"
        else:
            assert False, "Triggered toggle intent without On/Off keyword."

        target, name = self.get_target_from_message(message)

        if not message.data.get("_TestRunner"):
            target.set_power(power_status)

        self.speak_dialog('Switch', {'name': name,
                                     'status': status_str})

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group").require("Color")
                    .optionally("_TestRunner").build())
    def handle_color_intent(self, message):
        color_str = message.data["Color"]
        rgb = webcolors.name_to_rgb(color_str)
        hsbk = lifxlan.utils.RGBtoHSBK(rgb)

        target, name = self.get_target_from_message(message)

        if not message.data.get("_TestRunner"):
            target.set_color(hsbk)

        self.speak_dialog('Color', {'name': name,
                                    'color': color_str})

    @intent_handler(IntentBuilder("").optionally("Turn").require("Light").one_of("Increase", "Decrease")
                    .optionally("_TestRunner").build())
    def handle_dim_intent(self, message):
        if "Increase" in message.data:
            is_darkening = False
            status_str = "Brighten"
        elif "Decrease" in message.data:
            is_darkening = True
            status_str = "Darken"
        else:
            assert False, "Triggered hue intent without Darken/Brighten keyword."

        target, name = self.get_target_from_message(message)

        if not message.data.get("_TestRunner"):
            current_brightness = target.get_color()[BRIGHTNESS]
            new_brightness = max(min(current_brightness + self.dim_step * (-1 if is_darkening else 1), 65535), 0)
            target.set_brightness(new_brightness)

        self.speak_dialog('Dim', {'name': name,
                                  'change': status_str})

    @intent_handler(IntentBuilder("").require("Temperature").require("Turn").require("Light")
                    .one_of("Increase", "Decrease").optionally("_TestRunner"))
    def handle_temperature_intent(self, message):
        if "Increase" in message.data:
            is_cooling = False
            status_str = "Hot"
        elif "Decrease" in message.data:
            is_cooling = True
            status_str = "Cold"
        else:
            assert False, "Triggered temperature intent without Hot/Cold keyword."

        target, name = self.get_target_from_message(message)
        target: lifxlan.Light = target

        if not message.data.get("_TestRunner"):
            current_temperature = target.get_color()[KELVIN]
            new_temperature = \
                max(min(current_temperature + self.temperature_step * (1 if is_cooling else -1), 9000), 2500)
            target.set_colortemp(new_temperature)

        self.speak_dialog('Temperature', {'name': name,
                                          'temperature': status_str})


def create_skill():
    return LifxSkill()
