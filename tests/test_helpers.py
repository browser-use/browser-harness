import unittest
from unittest.mock import patch

import helpers


class PressKeyTests(unittest.TestCase):
    def events_for(self, key, modifiers=0):
        with patch.object(helpers, "cdp") as dispatch:
            helpers.press_key(key, modifiers)
        self.assertTrue(all(call.args == ("Input.dispatchKeyEvent",) for call in dispatch.call_args_list))
        return [call.kwargs for call in dispatch.call_args_list]

    def test_tab_moves_focus_without_inserting_text_into_next_field(self):
        for modifiers in (0, 8):
            with self.subTest(modifiers=modifiers):
                events = self.events_for("Tab", modifiers)
                self.assertEqual([event["type"] for event in events], ["keyDown", "keyUp"])
                for event in events:
                    self.assertNotIn("text", event)
                    self.assertEqual(event["key"], "Tab")
                    self.assertEqual(event["code"], "Tab")
                    self.assertEqual(event["modifiers"], modifiers)
                    self.assertEqual(event["windowsVirtualKeyCode"], 9)
                    self.assertEqual(event["nativeVirtualKeyCode"], 9)

    def test_printable_keys_keep_their_text_events(self):
        for key, code, virtual_key in (("a", "a", 97), (" ", "Space", 32)):
            with self.subTest(key=key):
                events = self.events_for(key)
                self.assertEqual([event["type"] for event in events], ["keyDown", "char", "keyUp"])
                self.assertEqual(events[0]["text"], key)
                self.assertEqual(events[1]["text"], key)
                self.assertNotIn("text", events[2])
                for event in events:
                    self.assertEqual(event["code"], code)
                    self.assertEqual(event["windowsVirtualKeyCode"], virtual_key)

    def test_enter_behavior_is_preserved(self):
        events = self.events_for("Enter")
        self.assertEqual([event["type"] for event in events], ["keyDown", "char", "keyUp"])
        self.assertEqual(events[0]["text"], "\r")
        self.assertEqual(events[1]["text"], "\r")


if __name__ == "__main__":
    unittest.main()
