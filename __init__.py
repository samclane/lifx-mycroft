"""
    lifx-mycroft: Mycroft interaction for Lifx smart-lights
    Copyright (C) 2018 Sawyer McLane

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG

import lifxlan
import lifxlan.utils
from fuzzywuzzy import fuzz
import webcolors

HUE, SATURATION, BRIGHTNESS, KELVIN = range(4)
MAX_VALUE = 65535
MAX_COLORTEMP = 9000
MIN_COLORTEMP = 2500
TRANSITION = 1250


class LifxSkill(MycroftSkill):

    def __init__(self):
        super(LifxSkill, self).__init__(name="LifxSkill")

        self.lifxlan = lifxlan.LifxLAN()
        self.lights = {}
        self.groups = {}

    def initialize(self):
        try:
            for light in self.lifxlan.get_lights():
                light: lifxlan.Light = light
                self.lights[light.get_label()] = light
                self.register_vocabulary(light.label, "Light")
                LOG.info("{} was found".format(light.label))
                group_label = light.get_group_label()
                if not (group_label in self.groups.keys()):
                    self.groups[group_label] = self.lifxlan.get_devices_by_group(group_label)
                    self.register_vocabulary(group_label, "Group")
                    LOG.info("Group {} was found".format(group_label))
        except Exception as e:
            self.log.warning("ERROR DISCOVERING LIFX LIGHTS. FUNCTIONALITY MIGHT BE WONKY.\n{}".format(str(e)))
        if len(self.lights.items()) == 0:
            self.log.warn("NO LIGHTS FOUND DURING SEARCH.")

        for color_name in webcolors.css3_hex_to_names.values():
            self.register_vocabulary(color_name, "Color")

    @property
    def dim_step(self):
        return int(float(self.settings["percent_step"]) * MAX_VALUE)

    @property
    def temperature_step(self):
        return int(float(self.settings["percent_step"]) * (MAX_COLORTEMP - MIN_COLORTEMP))

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

    @staticmethod
    def convert_percent_to_value(percent, type_=BRIGHTNESS):
        scale = percent / 100
        if type_ == BRIGHTNESS or type_ == SATURATION:
            return scale * MAX_VALUE
        elif type_ == KELVIN:
            return (scale * (MAX_COLORTEMP - MIN_COLORTEMP)) + MIN_COLORTEMP
        else:
            assert False, "Invalid type passed to percent. Must be BRIGHTNESS, SATURATION, or KELVIN"

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

        self.speak_dialog('Switch', {'name': name,
                                     'status': status_str})

        if not message.data.get("_TestRunner"):
            target.set_power(power_status, duration=TRANSITION)

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group").require("Color")
                    .optionally("_TestRunner").build())
    def handle_color_intent(self, message):
        color_str = message.data["Color"]
        rgb = webcolors.name_to_rgb(color_str)
        hsbk = lifxlan.utils.RGBtoHSBK(rgb)

        target, name = self.get_target_from_message(message)

        self.speak_dialog('Color', {'name': name,
                                    'color': color_str})

        if not message.data.get("_TestRunner"):
            target.set_color(hsbk, duration=TRANSITION)

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

        self.speak_dialog('Dim', {'name': name,
                                  'change': status_str})

        if not message.data.get("_TestRunner"):
            current_brightness = target.get_color()[BRIGHTNESS]
            new_brightness = max(min(current_brightness + self.dim_step * (-1 if is_darkening else 1), MAX_VALUE), 0)
            target.set_brightness(new_brightness, duration=TRANSITION)

        self.set_context("Light", name)

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

        self.speak_dialog('Temperature', {'name': name,
                                          'temperature': status_str})

        if not message.data.get("_TestRunner"):
            current_temperature = target.get_color()[KELVIN]
            new_temperature = \
                max(min(current_temperature + self.temperature_step * (1 if is_cooling else -1), MAX_COLORTEMP),
                    MIN_COLORTEMP)
            target.set_colortemp(new_temperature, duration=TRANSITION)

        self.set_context("Light", name)

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group")
                    .one_of("Brightness", "Temperature", "Saturation").require("Percent").optionally("_TestRunner")
                    .build())
    def handle_percent_intent(self, message):
        target, name = self.get_target_from_message(message)
        if "Brightness" in message.data:
            func = target.set_brightness
            status_str = "brightness"
            type_ = BRIGHTNESS
        elif "Temperature" in message.data:
            func = target.set_colortemp
            status_str = "temperature"
            type_ = KELVIN
        elif "Saturation" in message.data:
            func = target.set_saturation
            status_str = "saturation"
            type_ = SATURATION
        else:
            assert False, "Triggered percent intent without Brightness/Temperature/Saturation keyword."

        self.speak_dialog('SetPercent', {'name': name,
                                         'param': status_str,
                                         'value': message.data["Percent"]})

        if not message.data.get("_TestRunner"):
            percent = int(message.data["Percent"].strip("%"))
            value = self.convert_percent_to_value(percent, type_)
            func(value, duration=TRANSITION)


def create_skill():
    return LifxSkill()
