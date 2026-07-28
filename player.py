import json
import time
from pynput import keyboard, mouse

# Initialize controllers
mouse_controller = mouse.Controller()
keyboard_controller = keyboard.Controller()

# Helper function to convert JSON key representations back to pynput Key objects
def parse_key(key_str):
    if key_str is None:
        return None
    if key_str.startswith("Key."):
        key_name = key_str.split(".")[1]
        return getattr(keyboard.Key, key_name, None)
    return key_str


print("Loading recording.json...")
try:
    with open("recording.json", "r") as f:
        events = json.load(f)
except FileNotFoundError:
    print("Error: recording.json not found! Run recorder.py first.")
    exit()

print("Starting playback in 3 seconds... Switch to your target window!")
time.sleep(3)

last_event_time = 0.0

for event in events:
    # Sleep to preserve exact timing between events
    delay = event["time"] - last_event_time
    if delay > 0:
        time.sleep(delay)
    last_event_time = event["time"]

    event_type = event["type"]

    # --- Mouse Actions ---
    if event_type == "mouse_move":
        mouse_controller.position = (event["x"], event["y"])

    elif event_type == "mouse_click":
        button = getattr(mouse.Button, event["button"])
        mouse_controller.position = (event["x"], event["y"])
        if event["pressed"]:
            mouse_controller.press(button)
        else:
            mouse_controller.release(button)

    elif event_type == "mouse_scroll":
        mouse_controller.position = (event["x"], event["y"])
        mouse_controller.scroll(event["dx"], event["dy"])

    # --- Keyboard Actions ---
    elif event_type in ("key_press", "key_release"):
        key = parse_key(event["key"])
        if key is not None:
            if event_type == "key_press":
                keyboard_controller.press(key)
            else:
                keyboard_controller.release(key)

print("Playback completed successfully!")