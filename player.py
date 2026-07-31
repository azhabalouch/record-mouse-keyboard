"""
player.py
---------
High-precision, native Win32 macro playback engine using SendInput.
Supports speed scaling, loop counts, and high-resolution Windows timers.
"""

import time
import ctypes
from ctypes import wintypes
import random
from pynput import keyboard

# Enable High-Precision Multimedia Timer
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# --- Win32 Direct Input Definitions ---
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_VIRTUALDESK = 0x4000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))
    ]

class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD)
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT)
    ]

class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("u", _INPUT_UNION)
    ]


class Player:
    def __init__(self, events, speed_multiplier=1.0, loop_count=1,
                 enable_random_delay=False, min_delay=0.1, max_delay=0.5,
                 on_progress=None, on_state_change=None):
        self.events = events
        self.speed_multiplier = max(0.1, speed_multiplier)
        self.loop_count = loop_count  # 0 means infinite loop
        self.enable_random_delay = enable_random_delay
        self.min_delay = min_delay
        self.max_delay = max_delay

        self.on_progress = on_progress
        self.on_state_change = on_state_change

        self.is_running = True
        self.is_paused = False
        self._seek_requested = False
        self._target_time = 0.0
        self._esc_listener = None

    @staticmethod
    def _send_native_input(inp):
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

    def _set_cursor_position(self, x, y):
        ctypes.windll.user32.SetCursorPos(int(x), int(y))

    def _on_esc_press(self, key):
        if key == keyboard.Key.esc:
            if self.is_paused:
                self.resume()
            else:
                self.pause()

    def _wait_precise(self, delay_seconds):
        if delay_seconds <= 0:
            return
        start = time.perf_counter()
        while (time.perf_counter() - start) < delay_seconds:
            if not self.is_running or self._seek_requested:
                break
            while self.is_paused and self.is_running:
                if self._seek_requested or not self.is_running:
                    break
                time.sleep(0.02)
            time.sleep(0.0005)

    def play(self):
        if not self.events:
            return

        self._esc_listener = keyboard.Listener(on_press=self._on_esc_press)
        self._esc_listener.start()

        current_loop = 0
        try:
            while self.is_running and (self.loop_count == 0 or current_loop < self.loop_count):
                current_index = 0
                last_event_time = 0.0
                pending_extra_delay = 0.0

                # Handle seek if set prior to execution
                if self._seek_requested:
                    self._seek_requested = False
                    for idx, ev in enumerate(self.events):
                        if ev["time"] >= self._target_time:
                            current_index = idx
                            break
                    else:
                        current_index = len(self.events)
                    last_event_time = self._target_time

                while current_index < len(self.events) and self.is_running:
                    if self._seek_requested:
                        self._seek_requested = False
                        current_index = 0
                        for idx, ev in enumerate(self.events):
                            if ev["time"] >= self._target_time:
                                current_index = idx
                                break
                        else:
                            current_index = len(self.events)
                        last_event_time = self._target_time
                        pending_extra_delay = 0.0
                        continue

                    event = self.events[current_index]

                    if self.on_progress:
                        self.on_progress(event["time"])

                    raw_delay = (event["time"] - last_event_time) / self.speed_multiplier
                    delay = max(0.0, raw_delay + pending_extra_delay)
                    pending_extra_delay = 0.0
                    last_event_time = event["time"]

                    self._wait_precise(delay)

                    if not self.is_running or self._seek_requested:
                        continue

                    self._dispatch(event)

                    if self.enable_random_delay and event["type"] == "mouse_click" and not event.get("pressed", True):
                        pending_extra_delay = random.uniform(self.min_delay, self.max_delay)

                    current_index += 1

                current_loop += 1
        finally:
            if self._esc_listener:
                self._esc_listener.stop()

    def _dispatch(self, event):
        etype = event["type"]
        try:
            if etype == "mouse_move":
                self._set_cursor_position(event["x"], event["y"])

            elif etype == "mouse_click":
                self._set_cursor_position(event["x"], event["y"])
                btn = event["button"].lower()
                pressed = event["pressed"]

                inp = INPUT()
                inp.type = INPUT_MOUSE
                flags = 0

                if btn == "left":
                    flags = MOUSEEVENTF_LEFTDOWN if pressed else MOUSEEVENTF_LEFTUP
                elif btn == "right":
                    flags = MOUSEEVENTF_RIGHTDOWN if pressed else MOUSEEVENTF_RIGHTUP
                elif btn == "middle":
                    flags = MOUSEEVENTF_MIDDLEDOWN if pressed else MOUSEEVENTF_MIDDLEUP

                inp.u.mi.dwFlags = flags
                self._send_native_input(inp)

            elif etype == "mouse_scroll":
                self._set_cursor_position(event["x"], event["y"])
                inp = INPUT()
                inp.type = INPUT_MOUSE
                inp.u.mi.dwFlags = MOUSEEVENTF_WHEEL
                inp.u.mi.mouseData = int(event["dy"] * 120)
                self._send_native_input(inp)

            elif etype in ("key_press", "key_release"):
                self._dispatch_key(event["key"], event["type"] == "key_press")

        except Exception as exc:
            print(f"[Player Error] Failed event: {event!r} | Error: {exc}")

    def _dispatch_key(self, key_str, is_press):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD

        if key_str.startswith("__vk__:"):
            vk = int(key_str.split(":", 1)[1])
            inp.u.ki.wVk = vk
            inp.u.ki.dwFlags = 0 if is_press else KEYEVENTF_KEYUP
            
        elif key_str.startswith("Key."):
            key_name = key_str.split(".", 1)[1]
            vk = self._get_vk_for_special_key(key_name)
            if vk:
                inp.u.ki.wVk = vk
                inp.u.ki.dwFlags = 0 if is_press else KEYEVENTF_KEYUP
            else:
                return
                
        else:
            # Single character key — use Win32 KEYEVENTF_UNICODE
            inp.u.ki.wVk = 0
            inp.u.ki.wScan = ord(key_str[0])
            flags = KEYEVENTF_UNICODE
            if not is_press:
                flags |= KEYEVENTF_KEYUP
            inp.u.ki.dwFlags = flags

        self._send_native_input(inp)

    @staticmethod
    def _get_vk_for_special_key(name):
        special_map = {
            "shift": 0x10, "shift_r": 0xA1, "ctrl": 0x11, "ctrl_r": 0xA3,
            "alt": 0x12, "alt_r": 0xA5, "enter": 0x0D, "esc": 0x1B,
            "space": 0x20, "tab": 0x09, "backspace": 0x08, "delete": 0x2E,
            "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
            "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73, "f5": 0x74,
            "f6": 0x75, "f7": 0x76, "f8": 0x77, "f9": 0x78, "f10": 0x79,
            "f11": 0x7A, "f12": 0x7B
        }
        return special_map.get(name.lower(), None)

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
        self.is_paused = False

    def seek_to(self, seconds):
        self._target_time = seconds
        self._seek_requested = True