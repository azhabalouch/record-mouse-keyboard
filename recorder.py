"""
recorder.py
-----------
Tracks mouse and keyboard input with DPI awareness and micro-drag filtering.
"""

import json
import random
import time
from pynput import keyboard, mouse

def add_random_delay_after_clicks(events, min_delay=1.0, max_delay=2.0):
    if not events:
        return events

    adjusted = []
    cumulative_shift = 0.0

    for event in events:
        new_event = dict(event)
        new_event["time"] = event["time"] + cumulative_shift
        adjusted.append(new_event)

        if event["type"] == "mouse_click" and event["pressed"] is False:
            cumulative_shift += random.uniform(min_delay, max_delay)

    return adjusted


def normalize_key_name(text):
    """
    Convert a user-typed key name (e.g. "esc", "Shift", "a", "Key.tab")
    into the canonical string form produced by Recorder._key_to_str,
    so it can be matched against recorded/incoming keys.

    Returns None if the text doesn't look like a single character or a
    recognized special key name.
    """
    text = text.strip()
    if not text:
        return None

    # Single printable character - stored as-is (lowercase for consistency).
    if len(text) == 1:
        return text.lower()

    lower = text.lower()
    name = lower[4:] if lower.startswith("key.") else lower

    if hasattr(keyboard.Key, name):
        return f"Key.{name}"

    return None


_MODIFIER_ALIASES = {
    "Key.shift": ("Key.shift", "Key.shift_l", "Key.shift_r"),
    "Key.ctrl": ("Key.ctrl", "Key.ctrl_l", "Key.ctrl_r"),
    "Key.alt": ("Key.alt", "Key.alt_l", "Key.alt_r", "Key.alt_gr"),
    "Key.cmd": ("Key.cmd", "Key.cmd_l", "Key.cmd_r"),
}


def expand_key_variants(key_str):
    """Expand a canonical key string into every concrete form that could
    actually be reported for it (see _MODIFIER_ALIASES)."""
    return _MODIFIER_ALIASES.get(key_str, (key_str,))


class Recorder:
    def __init__(self, move_throttle=0.01, move_min_distance=2,
                 record_mouse_moves=True, random_click_delay=False,
                 click_delay_range=(1.0, 2.0), excluded_keys=None):
        self.events = []
        # Normalized set of key strings (as produced by _key_to_str) that
        # should never be written to the recorded event list. The key is
        # still processed normally (e.g. ESC still stops recording) - it's
        # just not logged. Generic modifier names are expanded to their
        # concrete left/right forms so restricting "shift" (etc.) actually
        # matches the real keypress events pynput reports.
        self.excluded_keys = set()
        for key_str in (excluded_keys or []):
            self.excluded_keys.update(expand_key_variants(key_str))
        self.start_time = 0.0
        self.pause_offset = 0.0
        self.pause_start = 0.0
        self.is_paused = False
        self.is_running = False

        self.record_mouse_moves = record_mouse_moves
        self.move_throttle = move_throttle
        self.move_min_distance = move_min_distance
        self._last_move_time = 0.0
        self._last_move_pos = None

        self.random_click_delay = random_click_delay
        self.click_delay_min, self.click_delay_max = click_delay_range
        self._last_press_pos = None

        self.mouse_listener = None
        self.keyboard_listener = None

    def get_elapsed_time(self):
        if self.is_paused:
            return self.pause_start - self.start_time - self.pause_offset
        return time.perf_counter() - self.start_time - self.pause_offset

    @staticmethod
    def _key_to_str(key):
        key_val = getattr(key, "char", None)
        if key_val is not None:
            return key_val

        key_str = str(key)
        if key_str.startswith("Key."):
            return key_str

        vk = getattr(key, "vk", None)
        if vk is not None:
            return f"__vk__:{vk}"

        return key_str

    def _on_move(self, x, y):
        if not (self.is_running and not self.is_paused) or not self.record_mouse_moves:
            return
        now = time.perf_counter()
        if self._last_move_pos is not None:
            last_x, last_y = self._last_move_pos
            dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
            if dist < self.move_min_distance and (now - self._last_move_time) < self.move_throttle:
                return
        self._last_move_time = now
        self._last_move_pos = (int(x), int(y))
        self.events.append({
            "type": "mouse_move",
            "time": round(self.get_elapsed_time(), 4),
            "x": int(x),
            "y": int(y)
        })

    def _on_click(self, x, y, button, pressed):
        if not (self.is_running and not self.is_paused):
            return

        # Record actual click/drag position directly
        self.events.append({
            "type": "mouse_click",
            "time": round(self.get_elapsed_time(), 4),
            "x": int(x),
            "y": int(y),
            "button": button.name,
            "pressed": pressed,
        })

    def _on_scroll(self, x, y, dx, dy):
        if not (self.is_running and not self.is_paused):
            return
        self.events.append({
            "type": "mouse_scroll",
            "time": round(self.get_elapsed_time(), 4),
            "x": int(x), "y": int(y), "dx": dx, "dy": dy,
        })

    def _on_press(self, key):
        if key == keyboard.Key.esc:
            self.is_running = False
            return False
        if self.is_running and not self.is_paused:
            key_str = self._key_to_str(key)
            if key_str in self.excluded_keys:
                return
            self.events.append({
                "type": "key_press",
                "time": round(self.get_elapsed_time(), 4),
                "key": key_str,
            })

    def _on_release(self, key):
        if key == keyboard.Key.esc:
            return False
        if self.is_running and not self.is_paused:
            key_str = self._key_to_str(key)
            if key_str in self.excluded_keys:
                return
            self.events.append({
                "type": "key_release",
                "time": round(self.get_elapsed_time(), 4),
                "key": key_str,
            })

    def start(self):
        self.events = []
        self.start_time = time.perf_counter()
        self.pause_offset = 0.0
        self.is_paused = False
        self.is_running = True

        self.mouse_listener = mouse.Listener(
            on_move=self._on_move, on_click=self._on_click, on_scroll=self._on_scroll
        )
        self.keyboard_listener = keyboard.Listener(
            on_press=self._on_press, on_release=self._on_release
        )
        self.mouse_listener.start()
        self.keyboard_listener.start()

    def pause(self):
        if self.is_running and not self.is_paused:
            self.is_paused = True
            self.pause_start = time.perf_counter()

    def resume(self):
        if self.is_running and self.is_paused:
            self.pause_offset += time.perf_counter() - self.pause_start
            self.is_paused = False

    def stop(self):
        self.is_running = False
        self.is_paused = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

    def wait_until_done(self):
        if self.keyboard_listener:
            self.keyboard_listener.join()
        if self.mouse_listener:
            self.mouse_listener.stop()

        if self.random_click_delay:
            self.events = add_random_delay_after_clicks(
                self.events, self.click_delay_min, self.click_delay_max
            )