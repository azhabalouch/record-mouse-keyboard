import sys
import os
import json
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QFileDialog, QSlider,
    QSpinBox, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from pynput import keyboard, mouse

# ==========================================
# THREAD 1: RECORDER WORKER
# ==========================================
class RecordThread(QThread):
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.events = []
        self.start_time = 0.0
        self.is_paused = False
        self.is_running = True
        self.pause_offset = 0.0
        self.pause_start = 0.0
        self.mouse_listener = None
        self.keyboard_listener = None

    def get_elapsed_time(self):
        if self.is_paused:
            return self.pause_start - self.start_time - self.pause_offset
        return time.time() - self.start_time - self.pause_offset

    def run(self):
        self.events = []
        self.start_time = time.time()
        self.pause_offset = 0.0

        def on_move(x, y):
            if not self.is_paused and self.is_running:
                self.events.append({"type": "mouse_move", "time": self.get_elapsed_time(), "x": x, "y": y})

        def on_click(x, y, button, pressed):
            if not self.is_paused and self.is_running:
                self.events.append({
                    "type": "mouse_click", "time": self.get_elapsed_time(),
                    "x": x, "y": y, "button": button.name, "pressed": pressed
                })

        def on_scroll(x, y, dx, dy):
            if not self.is_paused and self.is_running:
                self.events.append({
                    "type": "mouse_scroll", "time": self.get_elapsed_time(),
                    "x": x, "y": y, "dx": dx, "dy": dy
                })

        def on_press(key):
            if not self.is_paused and self.is_running:
                try:
                    key_val = key.char
                except AttributeError:
                    key_val = str(key)
                self.events.append({"type": "key_press", "time": self.get_elapsed_time(), "key": key_val})

        def on_release(key):
            if key == keyboard.Key.esc:
                self.is_running = False
                return False
            if not self.is_paused and self.is_running:
                try:
                    key_val = key.char
                except AttributeError:
                    key_val = str(key)
                self.events.append({"type": "key_release", "time": self.get_elapsed_time(), "key": key_val})

        self.mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)

        self.mouse_listener.start()
        self.keyboard_listener.start()

        while self.is_running:
            time.sleep(0.05)

        self.mouse_listener.stop()
        self.keyboard_listener.stop()
        self.finished_signal.emit(self.events)

    def pause(self):
        if not self.is_paused:
            self.is_paused = True
            self.pause_start = time.time()

    def resume(self):
        if self.is_paused:
            self.pause_offset += (time.time() - self.pause_start)
            self.is_paused = False

    def stop(self):
        self.is_running = False


# ==========================================
# THREAD 2: PLAYER WORKER
# ==========================================
class PlayThread(QThread):
    progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal()

    def __init__(self, events):
        super().__init__()
        self.events = events
        self.is_running = True
        self.is_paused = False
        self.seek_requested = False
        self.target_time = 0.0
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()

    def parse_key(self, key_str):
        if key_str is None:
            return None
        if key_str.startswith("Key."):
            key_name = key_str.split(".")[1]
            return getattr(keyboard.Key, key_name, None)
        return key_str

    def run(self):
        if not self.events:
            self.finished_signal.emit()
            return

        current_index = 0

        while current_index < len(self.events) and self.is_running:
            if self.seek_requested:
                self.seek_requested = False
                current_index = 0
                for idx, ev in enumerate(self.events):
                    if ev["time"] >= self.target_time:
                        current_index = idx
                        break

            if current_index >= len(self.events):
                break

            event = self.events[current_index]
            current_time = event["time"]

            self.progress_signal.emit(current_time)

            if current_index < len(self.events) - 1:
                next_time = self.events[current_index + 1]["time"]
                delay = next_time - current_time

                start_wait = time.time()
                while time.time() - start_wait < delay and self.is_running:
                    if self.seek_requested:
                        break
                    while self.is_paused and self.is_running and not self.seek_requested:
                        time.sleep(0.05)
                    time.sleep(0.01)

            if self.seek_requested or not self.is_running:
                if not self.seek_requested:
                    break
                continue

            event_type = event["type"]
            try:
                if event_type == "mouse_move":
                    self.mouse_controller.position = (event["x"], event["y"])
                elif event_type == "mouse_click":
                    btn = getattr(mouse.Button, event["button"])
                    self.mouse_controller.position = (event["x"], event["y"])
                    if event["pressed"]:
                        self.mouse_controller.press(btn)
                    else:
                        self.mouse_controller.release(btn)
                elif event_type == "mouse_scroll":
                    self.mouse_controller.position = (event["x"], event["y"])
                    self.mouse_controller.scroll(event["dx"], event["dy"])
                elif event_type in ("key_press", "key_release"):
                    key = self.parse_key(event["key"])
                    if key is not None:
                        if event_type == "key_press":
                            self.keyboard_controller.press(key)
                        else:
                            self.keyboard_controller.release(key)
            except Exception:
                pass

            current_index += 1

        self.finished_signal.emit()

    def seek_to(self, seconds):
        self.target_time = seconds
        self.seek_requested = True

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def stop(self):
        self.is_running = False


# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================
class MacroApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Input Player")
        self.setFixedSize(380, 310)  # Slightly heightened for timer spinboxes

        self.record_thread = None
        self.play_thread = None
        self.loaded_events = []
        self.recording_duration = 0.0

        # Timers for Recording Duration and Delay Countdowns
        self.rec_timer = QTimer()
        self.rec_timer.setInterval(100)
        self.rec_timer.timeout.connect(self.update_rec_time)

        self.rec_delay_timer = QTimer()
        self.rec_delay_timer.setInterval(1000)
        self.rec_delay_timer.timeout.connect(self.handle_rec_delay_countdown)
        self.rec_delay_remaining = 0

        self.play_delay_timer = QTimer()
        self.play_delay_timer.setInterval(1000)
        self.play_delay_timer.timeout.connect(self.handle_play_delay_countdown)
        self.play_delay_remaining = 0

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        tabs = QTabWidget()

        tabs.addTab(self.create_recorder_tab(), "Recorder")
        tabs.addTab(self.create_player_tab(), "Player")

        main_layout.addWidget(tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    # --- TAB 1: RECORDER ---
    def create_recorder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # File Configuration
        file_layout = QHBoxLayout()
        self.filename_input = QLineEdit("recording.json")
        file_layout.addWidget(QLabel("File Name:"))
        file_layout.addWidget(self.filename_input)

        # Directory Configuration
        dir_layout = QHBoxLayout()
        self.use_curr_dir_cb = QCheckBox("Use current location")
        self.use_curr_dir_cb.setChecked(True)
        self.use_curr_dir_cb.toggled.connect(self.toggle_dir_selection)

        self.path_input = QLineEdit(os.getcwd())
        self.path_input.setEnabled(False)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self.browse_location)

        dir_layout.addWidget(self.path_input)
        dir_layout.addWidget(self.browse_btn)

        # Delay Control
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Start Delay (seconds):"))
        self.rec_delay_spin = QSpinBox()
        self.rec_delay_spin.setRange(0, 300)
        self.rec_delay_spin.setValue(0)
        delay_layout.addWidget(self.rec_delay_spin)

        # Status / Time Display
        self.rec_status_lbl = QLabel("Ready (ESC key also stops recording)")
        self.rec_time_lbl = QLabel("00:00.0")
        self.rec_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rec_time_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")

        # Controls
        ctrl_layout = QHBoxLayout()
        self.rec_play_btn = QPushButton("Record")
        self.rec_pause_btn = QPushButton("Pause")
        self.rec_stop_btn = QPushButton("Stop")

        self.rec_pause_btn.setEnabled(False)
        self.rec_stop_btn.setEnabled(False)

        self.rec_play_btn.clicked.connect(self.start_recording_flow)
        self.rec_pause_btn.clicked.connect(self.pause_recording)
        self.rec_stop_btn.clicked.connect(self.stop_recording)

        ctrl_layout.addWidget(self.rec_play_btn)
        ctrl_layout.addWidget(self.rec_pause_btn)
        ctrl_layout.addWidget(self.rec_stop_btn)

        layout.addLayout(file_layout)
        layout.addWidget(self.use_curr_dir_cb)
        layout.addLayout(dir_layout)
        layout.addLayout(delay_layout)
        layout.addWidget(self.rec_time_lbl)
        layout.addWidget(self.rec_status_lbl)
        layout.addLayout(ctrl_layout)

        tab.setLayout(layout)
        return tab

    # --- TAB 2: PLAYER ---
    def create_player_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        # Load File Section
        load_layout = QHBoxLayout()
        self.load_path_input = QLineEdit()
        self.load_path_input.setPlaceholderText("Select .json file...")
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.load_file)

        load_layout.addWidget(self.load_path_input)
        load_layout.addWidget(self.load_btn)

        # Delay Control
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Start Delay (seconds):"))
        self.play_delay_spin = QSpinBox()
        self.play_delay_spin.setRange(0, 300)
        self.play_delay_spin.setValue(0)
        delay_layout.addWidget(self.play_delay_spin)

        # Media Seek Slider
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.user_seek)

        # Media Time Counter
        self.play_time_lbl = QLabel("00:00 / 00:00")
        self.play_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Player Controls
        ctrl_layout = QHBoxLayout()
        self.play_start_btn = QPushButton("Play")
        self.play_pause_btn = QPushButton("Pause")
        self.play_stop_btn = QPushButton("Stop")

        self.play_start_btn.setEnabled(False)
        self.play_pause_btn.setEnabled(False)
        self.play_stop_btn.setEnabled(False)

        self.play_start_btn.clicked.connect(self.start_playback_flow)
        self.play_pause_btn.clicked.connect(self.pause_playback)
        self.play_stop_btn.clicked.connect(self.stop_playback)

        ctrl_layout.addWidget(self.play_start_btn)
        ctrl_layout.addWidget(self.play_pause_btn)
        ctrl_layout.addWidget(self.play_stop_btn)

        layout.addLayout(load_layout)
        layout.addLayout(delay_layout)
        layout.addWidget(self.seek_slider)
        layout.addWidget(self.play_time_lbl)
        layout.addLayout(ctrl_layout)

        tab.setLayout(layout)
        return tab

    # --- RECORDER LOGIC ---
    def toggle_dir_selection(self, checked):
        self.path_input.setEnabled(not checked)
        self.browse_btn.setEnabled(not checked)
        if checked:
            self.path_input.setText(os.getcwd())

    def browse_location(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory")
        if folder:
            self.path_input.setText(folder)

    def start_recording_flow(self):
        if self.record_thread and self.record_thread.is_paused:
            self.record_thread.resume()
            self.rec_status_lbl.setText("Recording...")
            self.rec_play_btn.setEnabled(False)
            self.rec_pause_btn.setEnabled(True)
            return

        delay = self.rec_delay_spin.value()
        if delay > 0:
            self.rec_delay_remaining = delay
            self.rec_play_btn.setEnabled(False)
            self.rec_stop_btn.setEnabled(True)
            self.rec_play_btn.setText(f"Starting in {self.rec_delay_remaining}s...")
            self.rec_status_lbl.setText(f"Waiting {delay} seconds to record...")
            self.rec_delay_timer.start()
        else:
            self.execute_start_recording()

    def handle_rec_delay_countdown(self):
        self.rec_delay_remaining -= 1
        if self.rec_delay_remaining > 0:
            self.rec_play_btn.setText(f"Starting in {self.rec_delay_remaining}s...")
            self.rec_status_lbl.setText(f"Waiting {self.rec_delay_remaining} seconds to record...")
        else:
            self.rec_delay_timer.stop()
            self.rec_play_btn.setText("Record")
            self.execute_start_recording()

    def execute_start_recording(self):
        self.record_thread = RecordThread()
        self.record_thread.finished_signal.connect(self.on_recording_finished)
        self.record_thread.start()

        self.rec_timer.start()
        self.rec_status_lbl.setText("Recording...")
        self.rec_play_btn.setEnabled(False)
        self.rec_pause_btn.setEnabled(True)
        self.rec_stop_btn.setEnabled(True)

    def pause_recording(self):
        if self.record_thread:
            self.record_thread.pause()
            self.rec_status_lbl.setText("Paused")
            self.rec_play_btn.setEnabled(True)
            self.rec_pause_btn.setEnabled(False)

    def stop_recording(self):
        if self.rec_delay_timer.isActive():
            self.rec_delay_timer.stop()
            self.rec_play_btn.setText("Record")
            self.rec_play_btn.setEnabled(True)
            self.rec_stop_btn.setEnabled(False)
            self.rec_status_lbl.setText("Recording cancelled.")
            return

        if self.record_thread:
            self.record_thread.stop()
            self.rec_timer.stop()

    def update_rec_time(self):
        if self.record_thread:
            elapsed = self.record_thread.get_elapsed_time()
            mins, secs = divmod(elapsed, 60)
            self.rec_time_lbl.setText(f"{int(mins):02d}:{secs:04.1f}")

    def on_recording_finished(self, events):
        self.rec_timer.stop()
        filename = self.filename_input.text().strip()
        if not filename.endswith(".json"):
            filename += ".json"

        save_path = os.path.join(self.path_input.text(), filename)

        with open(save_path, "w") as f:
            json.dump(events, f, indent=2)

        self.rec_status_lbl.setText(f"Saved: {filename}")
        self.rec_play_btn.setText("Record")
        self.rec_play_btn.setEnabled(True)
        self.rec_pause_btn.setEnabled(False)
        self.rec_stop_btn.setEnabled(False)
        QMessageBox.information(self, "Success", f"Recorded {len(events)} events to:\n{save_path}")

    # --- PLAYER LOGIC ---
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Macro File", "", "JSON Files (*.json)")
        if file_path:
            self.load_path_input.setText(file_path)
            try:
                with open(file_path, "r") as f:
                    self.loaded_events = json.load(f)

                if self.loaded_events:
                    self.recording_duration = self.loaded_events[-1]["time"]
                    self.seek_slider.setEnabled(True)
                    self.play_start_btn.setEnabled(True)
                    self.update_playback_time_label(0.0)
                else:
                    QMessageBox.warning(self, "Warning", "Selected JSON file contains no events.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def update_playback_time_label(self, current_sec):
        curr_m, curr_s = divmod(current_sec, 60)
        tot_m, tot_s = divmod(self.recording_duration, 60)
        self.play_time_lbl.setText(f"{int(curr_m):02d}:{int(curr_s):02d} / {int(tot_m):02d}:{int(tot_s):02d}")

    def start_playback_flow(self):
        if self.play_thread and self.play_thread.is_paused:
            self.play_thread.resume()
            self.play_start_btn.setEnabled(False)
            self.play_pause_btn.setEnabled(True)
            return

        delay = self.play_delay_spin.value()
        if delay > 0:
            self.play_delay_remaining = delay
            self.play_start_btn.setEnabled(False)
            self.play_stop_btn.setEnabled(True)
            self.play_start_btn.setText(f"Starting in {self.play_delay_remaining}s...")
            self.play_delay_timer.start()
        else:
            self.execute_start_playback()

    def handle_play_delay_countdown(self):
        self.play_delay_remaining -= 1
        if self.play_delay_remaining > 0:
            self.play_start_btn.setText(f"Starting in {self.play_delay_remaining}s...")
        else:
            self.play_delay_timer.stop()
            self.play_start_btn.setText("Play")
            self.execute_start_playback()

    def execute_start_playback(self):
        self.play_thread = PlayThread(self.loaded_events)
        self.play_thread.progress_signal.connect(self.on_playback_progress)
        self.play_thread.finished_signal.connect(self.on_playback_finished)
        self.play_thread.start()

        self.play_start_btn.setEnabled(False)
        self.play_pause_btn.setEnabled(True)
        self.play_stop_btn.setEnabled(True)

    def pause_playback(self):
        if self.play_thread:
            self.play_thread.pause()
            self.play_start_btn.setEnabled(True)
            self.play_pause_btn.setEnabled(False)

    def stop_playback(self):
        if self.play_delay_timer.isActive():
            self.play_delay_timer.stop()
            self.play_start_btn.setText("Play")
            self.play_start_btn.setEnabled(True)
            self.play_stop_btn.setEnabled(False)
            return

        if self.play_thread:
            self.play_thread.stop()

    def user_seek(self, value):
        if self.recording_duration > 0:
            target_time = (value / 1000.0) * self.recording_duration
            self.update_playback_time_label(target_time)
            if self.play_thread:
                self.play_thread.seek_to(target_time)

    def on_playback_progress(self, current_time):
        if self.recording_duration > 0:
            progress_ratio = current_time / self.recording_duration
            self.seek_slider.setValue(int(progress_ratio * 1000))
            self.update_playback_time_label(current_time)

    def on_playback_finished(self):
        self.play_start_btn.setText("Play")
        self.play_start_btn.setEnabled(True)
        self.play_pause_btn.setEnabled(False)
        self.play_stop_btn.setEnabled(False)
        self.seek_slider.setValue(0)
        self.update_playback_time_label(0.0)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacroApp()
    window.show()
    sys.exit(app.exec())