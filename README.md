## System Requirements

The `pynput` library is required to monitor and control hardware input devices accurately [1].

The `PyQt6` library is required to create GUI.

pip install PyQt6 pynput

## Phase 1: Recording Script Logic

1. **Initialise Listeners:**
Start `pynput.mouse.Listener` and `pynput.keyboard.Listener` in the background to monitor physical inputs.


2. **Log Events and Time:**
Capture each key press, mouse click, and coordinate change. Attach a precise system timestamp to each action. This is necessary to measure the exact delay between your inputs.


3. **Export Data:**
Save the collected sequence array into a structured file format, such as JSON. This creates a permanent, readable record of your exact pattern.


## Phase 2: Playback Script Logic

1. **Import Data:**
Read the JSON file containing the recorded input sequence into the second script.


2. **Process Timing Delays:**
Calculate the time difference between each recorded action. Use the `time.sleep()` function to pause the script for that exact duration. This ensures the playback speed matches the original human recording.


3. **Execute Actions:**
Use `pynput.mouse.Controller` and `pynput.keyboard.Controller` to trigger the saved coordinates and key presses on the operating system in the exact chronological order.


### References

[1] M. Palmer, "pynput: Send and catch keyboard and mouse events," *Read the Docs*, 2026. [Online]. Available: [https://pynput.readthedocs.io/en/latest/](https://pynput.readthedocs.io/en/latest/). [Accessed: 27-Jul-2026].