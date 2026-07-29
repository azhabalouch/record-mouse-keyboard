"""
player.py
---------
Replays events recorded by recorder.py. Supports dynamic random delay
injection configurable via GUI or direct arguments.
"""

import json
import random
import time
from pynput import keyboard, mouse


class Player:
    def __init__(self, events, on_progress=None, on_state_change=None,
                 enable_random_delay=False, min_delay=0.1, max_delay=0.5):
        self.events = events
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

        self.is_running = True
        self.is_paused = False
        self._seek_requested = False
        self._target_time = 0.0

        # Random Delay Controls
        self.enable_random_delay = enable_random_delay
        self.min_delay = min_delay
        self.max_delay = max_delay

        self.on_progress = on_progress
        self.on_state_change = on_state_change
        self._esc_listener = None

    @staticmethod
    def parse_key(key_str):
        if key_str is None:
            return None
        if key_str.startswith("Key."):
            key_name = key_str.split(".", 1)[1]
            return getattr(keyboard.Key, key_name, None)
        if key_str.startswith("__vk__:"):
            # Char-less keycode (e.g. the 'c' in Ctrl+C) recorded by its
            # raw virtual key code -- reconstruct a pressable KeyCode.
            try:
                vk = int(key_str.split(":", 1)[1])
            except (ValueError, IndexError):
                return None
            return keyboard.KeyCode.from_vk(vk)
        return key_str

    def _on_esc_press(self, key):
        if key == keyboard.Key.esc:
            if self.is_paused:
                self.resume()
            else:
                self.pause()

    def _wait_while_paused(self):
        while self.is_paused and self.is_running:
            time.sleep(0.05)

    def play(self):
        if not self.events:
            return

        self._esc_listener = keyboard.Listener(on_press=self._on_esc_press)
        self._esc_listener.start()

        try:
            current_index = 0
            last_event_time = 0.0
            # Extra pause queued up by the previous click's random delay
            # (see below) -- applied to the *next* event's wait, so it
            # lands as a gap AFTER the click completes rather than
            # stretching how long the mouse button stays held down.
            pending_extra_delay = 0.0

            while current_index < len(self.events) and self.is_running:
                if self._seek_requested:
                    self._seek_requested = False
                    current_index = 0
                    for idx, ev in enumerate(self.events):
                        if ev["time"] >= self._target_time:
                            current_index = idx
                            break
                    else:
                        # target_time is past every event -- finish
                        # playback instead of silently restarting from
                        # the beginning.
                        current_index = len(self.events)
                    last_event_time = self._target_time
                    pending_extra_delay = 0.0
                    continue

                event = self.events[current_index]

                if self.on_progress:
                    self.on_progress(event["time"])

                delay = (event["time"] - last_event_time) + pending_extra_delay
                pending_extra_delay = 0.0
                last_event_time = event["time"]

                if delay > 0:
                    waited = 0.0
                    step = 0.01
                    while waited < delay and self.is_running and not self._seek_requested:
                        self._wait_while_paused()
                        time.sleep(step)
                        waited += step

                if not self.is_running or self._seek_requested:
                    continue

                self._dispatch(event)

                # Apply GUI-defined random delay if enabled: queue it up
                # as a pause before the *next* event, right after this
                # click's release actually happens.
                if self.enable_random_delay and event["type"] == "mouse_click" and not event.get("pressed", True):
                    pending_extra_delay = random.uniform(self.min_delay, self.max_delay)

                current_index += 1
        finally:
            if self._esc_listener:
                self._esc_listener.stop()

    def _move_and_settle(self, x, y, settle=0.015):
        """Fixes inaccurate coordinates by allowing OS/display server to settle pointer position."""
        self.mouse_controller.position = (int(x), int(y))
        time.sleep(settle)
        if self.mouse_controller.position != (int(x), int(y)):
            self.mouse_controller.position = (int(x), int(y))
            time.sleep(settle)

    def _dispatch(self, event):
        event_type = event["type"]
        try:
            if event_type == "mouse_move":
                self.mouse_controller.position = (int(event["x"]), int(event["y"]))

            elif event_type == "mouse_click":
                button = getattr(mouse.Button, event["button"])
                self._move_and_settle(event["x"], event["y"])
                if event["pressed"]:
                    self.mouse_controller.press(button)
                else:
                    self.mouse_controller.release(button)

            elif event_type == "mouse_scroll":
                self.mouse_controller.position = (int(event["x"]), int(event["y"]))
                self.mouse_controller.scroll(event["dx"], event["dy"])

            elif event_type in ("key_press", "key_release"):
                key = self.parse_key(event["key"])
                if key is not None:
                    if event_type == "key_press":
                        self.keyboard_controller.press(key)
                    else:
                        self.keyboard_controller.release(key)
        except Exception as exc:
            # Don't let one bad event silently kill accuracy with no
            # trace -- surface what happened so failures are visible
            # instead of just "playback didn't quite match".
            print(f"[Player] Failed to dispatch event {event!r}: {exc}")

    def pause(self):
        if not self.is_paused:
            self.is_paused = True
            if self.on_state_change:
                self.on_state_change(True)

    def resume(self):
        if self.is_paused:
            self.is_paused = False
            if self.on_state_change:
                self.on_state_change(False)

    def stop(self):
        self.is_running = False

    def seek_to(self, seconds):
        self._target_time = seconds
        self._seek_requested = True