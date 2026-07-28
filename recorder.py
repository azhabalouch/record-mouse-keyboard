import json
import time
from pynput import keyboard, mouse

# Store recorded events and start time
events = []
start_time = time.time()


def get_elapsed_time():
    return time.time() - start_time


# --- Mouse Handlers ---
def on_move(x, y):
    events.append(
        {"type": "mouse_move", "time": get_elapsed_time(), "x": x, "y": y}
    )


def on_click(x, y, button, pressed):
    events.append(
        {
            "type": "mouse_click",
            "time": get_elapsed_time(),
            "x": x,
            "y": y,
            "button": button.name,
            "pressed": pressed,
        }
    )


def on_scroll(x, y, dx, dy):
    events.append(
        {
            "type": "mouse_scroll",
            "time": get_elapsed_time(),
            "x": x,
            "y": y,
            "dx": dx,
            "dy": dy,
        }
    )


# --- Keyboard Handlers ---
def on_press(key):
    try:
        # Regular character keys (a, b, 1, etc.)
        key_val = key.char
    except AttributeError:
        # Special keys (shift, enter, space, etc.)
        key_val = str(key)

    events.append(
        {
            "type": "key_press",
            "time": get_elapsed_time(),
            "key": key_val,
        }
    )


def on_release(key):
    if key == keyboard.Key.esc:
        # Stop recording when ESC is pressed
        return False

    try:
        key_val = key.char
    except AttributeError:
        key_val = str(key)

    events.append(
        {
            "type": "key_release",
            "time": get_elapsed_time(),
            "key": key_val,
        }
    )


print("Recording started... Press ESC to stop and save.")

# Start monitoring both mouse and keyboard
mouse_listener = mouse.Listener(
    on_move=on_move, on_click=on_click, on_scroll=on_scroll
)
keyboard_listener = keyboard.Listener(
    on_press=on_press, on_release=on_release
)

mouse_listener.start()
keyboard_listener.start()

# Wait for keyboard listener to stop (when ESC is pressed)
keyboard_listener.join()
mouse_listener.stop()

# Save recorded events to JSON file
with open("recording.json", "w") as f:
    json.dump(events, f, indent=2)

print(
    f"Recording stopped. Total events recorded: {len(events)}. Saved to recording.json"
)