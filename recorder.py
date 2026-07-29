"""
recorder.py
-----------
Records mouse and keyboard events (with timestamps) so they can be replayed
later by player.py. Can be run standalone (`python recorder.py`) or imported
and driven programmatically (used by app.py's GUI).
"""

import json
import random
import time
from pynput import keyboard, mouse


def add_random_delay_after_clicks(events, min_delay=2.0, max_delay=5.0):
    """
    Returns a NEW list of events with an extra random delay (min_delay to
    max_delay seconds, uniformly chosen) inserted into the timeline after
    every completed mouse click (i.e. right after each mouse_click
    "release" event). Every later event's timestamp is shifted forward by
    the same cumulative amount, so relative timing elsewhere in the
    recording is preserved -- only the gaps after clicks grow.
    """
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


class Recorder:
    """Records mouse/keyboard events into self.events as a list of dicts."""

    def __init__(self, move_throttle=0.01, move_min_distance=2,
                 random_click_delay=True, click_delay_range=(2.0, 5.0)):
        self.events = []
        self.start_time = 0.0
        self.pause_offset = 0.0
        self.pause_start = 0.0
        self.is_paused = False
        self.is_running = False

        self.mouse_listener = None
        self.keyboard_listener = None

        # Throttle mouse_move recording to avoid flooding the recording
        # with near-identical events (fixes playback timing drift).
        self.move_throttle = move_throttle       # min seconds between samples
        self.move_min_distance = move_min_distance  # min pixels moved
        self._last_move_time = 0.0
        self._last_move_pos = None

        # After recording finishes, insert a random 2-5s (configurable)
        # pause into the timeline after every click. Set
        # random_click_delay=False to disable.
        self.random_click_delay = random_click_delay
        self.click_delay_min, self.click_delay_max = click_delay_range

    # --- timing ---
    def get_elapsed_time(self):
        if self.is_paused:
            return self.pause_start - self.start_time - self.pause_offset
        return time.time() - self.start_time - self.pause_offset

    # --- key serialization ---
    @staticmethod
    def _key_to_str(key):
        """Convert a pynput key object to a JSON-safe string.

        `key.char` can be None (not an AttributeError) for modifier
        combinations like Ctrl+C, so we must explicitly fall back
        instead of relying on except.

        When char is None we are dealing with either:
          * a "special" key (Key.ctrl_l, Key.shift, Key.esc, ...) -- for
            these str(key) already produces "Key.<name>", which
            player.py's parse_key can map straight back to the
            keyboard.Key enum.
          * a regular character key whose char got suppressed because a
            modifier (Ctrl/Alt/...) was held (e.g. the 'c' in Ctrl+C) --
            for these str(key) does NOT produce a "Key.<name>" string,
            so it can't be turned back into a pressable key object. We
            instead store the raw virtual key code (vk) with a
            recognizable "__vk__:" prefix so it can be reconstructed
            with keyboard.KeyCode.from_vk() during playback.
        """
        key_val = getattr(key, "char", None)
        if key_val is not None:
            return key_val

        key_str = str(key)
        if key_str.startswith("Key."):
            return key_str

        vk = getattr(key, "vk", None)
        if vk is not None:
            return f"__vk__:{vk}"

        # Last resort fallback (shouldn't normally happen).
        return key_str

    # --- pynput callbacks ---
    def _on_move(self, x, y):
        if not (self.is_running and not self.is_paused):
            return
        now = time.time()
        if self._last_move_pos is not None:
            last_x, last_y = self._last_move_pos
            dist = ((x - last_x) ** 2 + (y - last_y) ** 2) ** 0.5
            if dist < self.move_min_distance and (now - self._last_move_time) < self.move_throttle:
                return
        self._last_move_time = now
        self._last_move_pos = (x, y)
        self.events.append({"type": "mouse_move", "time": self.get_elapsed_time(), "x": x, "y": y})

    def _on_click(self, x, y, button, pressed):
        if not (self.is_running and not self.is_paused):
            return
        self.events.append({
            "type": "mouse_click",
            "time": self.get_elapsed_time(),
            "x": x, "y": y,
            "button": button.name,
            "pressed": pressed,
        })

    def _on_scroll(self, x, y, dx, dy):
        if not (self.is_running and not self.is_paused):
            return
        self.events.append({
            "type": "mouse_scroll",
            "time": self.get_elapsed_time(),
            "x": x, "y": y, "dx": dx, "dy": dy,
        })

    def _on_press(self, key):
        if key == keyboard.Key.esc:
            # Stop recording on ESC. Deliberately do NOT record this press,
            # so playback never replays a dangling, un-released ESC.
            self.is_running = False
            return False
        if self.is_running and not self.is_paused:
            self.events.append({
                "type": "key_press",
                "time": self.get_elapsed_time(),
                "key": self._key_to_str(key),
            })

    def _on_release(self, key):
        if key == keyboard.Key.esc:
            return False
        if self.is_running and not self.is_paused:
            self.events.append({
                "type": "key_release",
                "time": self.get_elapsed_time(),
                "key": self._key_to_str(key),
            })

    # --- controls ---
    def start(self):
        self.events = []
        self.start_time = time.time()
        self.pause_offset = 0.0
        self.is_paused = False
        self.is_running = True
        self._last_move_time = 0.0
        self._last_move_pos = None

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
            self.pause_start = time.time()

    def resume(self):
        if self.is_running and self.is_paused:
            self.pause_offset += time.time() - self.pause_start
            self.is_paused = False

    def stop(self):
        """Stop recording programmatically (e.g. a GUI Stop button)."""
        self.is_running = False
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.mouse_listener:
            self.mouse_listener.stop()

    def wait_until_done(self):
        """Blocks until recording stops (ESC pressed or stop() called),
        then post-processes self.events (random post-click delay)."""
        if self.keyboard_listener:
            self.keyboard_listener.join()
        if self.mouse_listener:
            self.mouse_listener.stop()

        if self.random_click_delay:
            self.events = add_random_delay_after_clicks(
                self.events, self.click_delay_min, self.click_delay_max
            )

    def save(self, path="recording.json"):
        with open(path, "w") as f:
            json.dump(self.events, f, indent=2)
        return path


def record_to_file(path="recording.json"):
    """Blocking, CLI-style recording helper."""
    print("Recording started... Press ESC to stop and save.")
    rec = Recorder()
    rec.start()
    rec.wait_until_done()
    rec.save(path)
    print(f"Recording stopped. Total events recorded: {len(rec.events)}. Saved to {path}")
    return rec.events


if __name__ == "__main__":
    record_to_file()
