"""Keep action forms and translations aligned with the executable schemas."""

import json
import unittest
from pathlib import Path

import yaml
from test_control import services

ROOT = Path(__file__).resolve().parents[1] / "custom_components/pixelit"


def flatten(fields):
    result = {}
    for name, field in fields.items():
        if "fields" in field:
            result.update(flatten(field["fields"]))
        else:
            result[name] = field
    return result


class ActionFormTests(unittest.TestCase):
    def test_every_action_field_and_section_is_translated(self):
        descriptions = yaml.safe_load((ROOT / "services.yaml").read_text())
        self.assertEqual(set(descriptions), set(services.ACTION_SCHEMAS))
        for language in ("en", "de"):
            strings = json.loads((ROOT / f"translations/{language}.json").read_text())
            for name, description in descriptions.items():
                fields = description.get("fields", {})
                flat = flatten(fields)
                schema = services.ACTION_SCHEMAS[name]
                self.assertEqual(set(flat), {str(key.schema) for key in schema}, name)
                self.assertEqual(
                    set(flat), set(strings["services"][name].get("fields", {})), name
                )
                for key, value in fields.items():
                    if "fields" in value:
                        self.assertIn(key, strings["services"][name]["sections"])

    def test_common_forms_have_native_inputs_and_hide_raw_content(self):
        descriptions = yaml.safe_load((ROOT / "services.yaml").read_text())
        for name in ("show_message", "show_alert", "set_screen"):
            fields = descriptions[name]["fields"]
            self.assertIn("text", fields["message"]["selector"])
            self.assertEqual(fields["color"]["selector"], {"text": {"type": "color"}})
            self.assertNotIn("screen", fields)
            self.assertTrue(fields["advanced_options"]["collapsed"])
        self.assertEqual(
            descriptions["set_playlist"]["fields"]["screens"]["selector"],
            {"text": {"multiple": True}},
        )
        self.assertNotIn("fields", descriptions["stop_playlist"])

    def test_selector_option_keys_match_ha_translation_rules(self):
        import re

        descriptions = yaml.safe_load((ROOT / "services.yaml").read_text())
        for language in ("en", "de"):
            strings = json.loads((ROOT / f"translations/{language}.json").read_text())
            for action in descriptions.values():
                for field in flatten(action.get("fields", {})).values():
                    selector = field.get("selector", {}).get("select", {})
                    key = selector.get("translation_key")
                    if key:
                        translated = strings["selector"][key]["options"]
                        self.assertEqual(set(selector["options"]), set(translated))
                        for option in translated:
                            self.assertIsNotNone(
                                re.fullmatch(r"[a-z0-9]+(?:[-_][a-z0-9]+)*", option)
                            )
