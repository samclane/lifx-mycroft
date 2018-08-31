from adapt.intent import IntentBuilder
from mycroft.skills.core import MycroftSkill, intent_handler
from mycroft.util.log import LOG

import lifxlan
import lifxlan.utils
from fuzzywuzzy import fuzz
import webcolors


class LifxSkill(MycroftSkill):

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
        if "Lights" in message.data.keys():
            target = self.get_fuzzy_value_from_dict(message.data["Light"], self.lights)
            name = message.data["Light"]
        elif "Groups" in message.data.keys():
            target = self.get_fuzzy_value_from_dict(message.data["Group"], self.groups)
            name = message.data["Group"]
        else:
            assert False, "Triggered intent without device or group. Message: {}".format(message.data["Utterance"])

        return target, name

    @staticmethod
    def get_fuzzy_value_from_dict(key, dict_: dict):
        best_score = 0
        score = 0
        best_item = None

        for k, v in dict_.values():
            score = fuzz.ratio(key, k)
            if score > best_score:
                best_score = score
                best_item = v

        return best_item

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group").one_of("Off", "On").build())
    def handle_toggle_intent(self, message):
        if "Off" in message.data.keys():
            power_status = False
            status_str = "Off"
        elif "On" in message.data.keys():
            power_status = True
            status_str = "On"
        else:
            assert False, "Triggered toggle intent without On/Off keyword."

        target, name = self.get_target_from_message(message)

        target.set_power(power_status)

        self.speak_dialog('Turn', {'name': name,
                                   'status': status_str})

    @intent_handler(IntentBuilder("").require("Turn").one_of("Light", "Group").require("Color").build())
    def handle_color_intent(self, message):
        color_str = message.data["Color"]
        rgb = webcolors.name_to_rgb(color_str)
        hsbk = lifxlan.utils.RGBtoHSBK(rgb)

        target, name = self.get_target_from_message(message)

        target.set_color(hsbk)

        self.speak_dialog('Turn', {'name': name,
                                   'status': color_str})


def create_skill():
    return LifxSkill()
