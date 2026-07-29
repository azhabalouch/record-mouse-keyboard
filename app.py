import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QFileDialog, QSlider,
    QSpinBox, QDoubleSpinBox, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from recorder import Recorder
from player import Player


class RecordThread(QThread):
    finished_signal = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        # Disable auto-hardcoded delays in recorder so we control them in Player GUI
        self.recorder = Recorder(random_click_delay=False)

    def run(self):
        self.recorder.start()
        self.recorder.wait_until_done()
        self.finished_signal.emit(self.recorder.events)

    def get_elapsed_time(self):
        return self.recorder.get_elapsed_time()

    @property
    def is_paused(self):
        return self.recorder.is_paused

    def pause(self):
        self.recorder.pause()

    def resume(self):
        self.recorder.resume()

    def stop(self):
        self.recorder.stop()


class PlayThread(QThread):
    progress_signal = pyqtSignal(float)
    finished_signal = pyqtSignal()
    pause_state_signal = pyqtSignal(bool)

    def __init__(self, events, enable_random_delay=False, min_delay=0.1, max_delay=0.5):
        super().__init__()
        self.player = Player(
            events,
            on_progress=self.progress_signal.emit,
            on_state_change=self.pause_state_signal.emit,
            enable_random_delay=enable_random_delay,
            min_delay=min_delay,
            max_delay=max_delay
        )

    def run(self):
        self.player.play()
        self.finished_signal.emit()

    @property
    def is_paused(self):
        return self.player.is_paused

    def pause(self):
        self.player.pause()

    def resume(self):
        self.player.resume()

    def stop(self):
        self.player.stop()

    def seek_to(self, seconds):
        self.player.seek_to(seconds)


class MacroApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Macro Controller")
        self.setFixedSize(400, 380)

        self.record_thread = None
        self.play_thread = None
        self.loaded_events = []
        self.recording_duration = 0.0

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

        file_layout = QHBoxLayout()
        self.filename_input = QLineEdit("recording.json")
        file_layout.addWidget(QLabel("File Name:"))
        file_layout.addWidget(self.filename_input)

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

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Start Delay (seconds):"))
        self.rec_delay_spin = QSpinBox()
        self.rec_delay_spin.setRange(0, 300)
        self.rec_delay_spin.setValue(0)
        delay_layout.addWidget(self.rec_delay_spin)

        self.rec_status_lbl = QLabel("Ready (ESC key stops recording)")
        self.rec_time_lbl = QLabel("00:00.0")
        self.rec_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rec_time_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")

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

        load_layout = QHBoxLayout()
        self.load_path_input = QLineEdit()
        self.load_path_input.setPlaceholderText("Select .json file...")
        self.load_btn = QPushButton("Load")
        self.load_btn.clicked.connect(self.load_file)

        load_layout.addWidget(self.load_path_input)
        load_layout.addWidget(self.load_btn)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Start Delay (seconds):"))
        self.play_delay_spin = QSpinBox()
        self.play_delay_spin.setRange(0, 300)
        self.play_delay_spin.setValue(0)
        delay_layout.addWidget(self.play_delay_spin)

        # Random Delay GUI Box
        rnd_box = QGroupBox("Random Delay Controls")
        rnd_layout = QVBoxLayout()

        self.rnd_delay_cb = QCheckBox("Enable Random Delay After Clicks")
        rnd_inputs = QHBoxLayout()
        rnd_inputs.addWidget(QLabel("Min (s):"))
        self.rnd_min_spin = QDoubleSpinBox()
        self.rnd_min_spin.setRange(0.0, 10.0)
        self.rnd_min_spin.setValue(0.1)
        self.rnd_min_spin.setSingleStep(0.1)

        rnd_inputs.addWidget(self.rnd_min_spin)
        rnd_inputs.addWidget(QLabel("Max (s):"))
        self.rnd_max_spin = QDoubleSpinBox()
        self.rnd_max_spin.setRange(0.0, 10.0)
        self.rnd_max_spin.setValue(0.5)
        self.rnd_max_spin.setSingleStep(0.1)
        rnd_inputs.addWidget(self.rnd_max_spin)

        rnd_layout.addWidget(self.rnd_delay_cb)
        rnd_layout.addLayout(rnd_inputs)
        rnd_box.setLayout(rnd_layout)

        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.user_seek)

        self.play_time_lbl = QLabel("00:00 / 00:00")
        self.play_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

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
        layout.addWidget(rnd_box)
        layout.addWidget(self.seek_slider)
        layout.addWidget(self.play_time_lbl)
        layout.addLayout(ctrl_layout)

        self.play_status_lbl = QLabel("ESC pauses / resumes playback")
        layout.addWidget(self.play_status_lbl)

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
        self.play_thread = PlayThread(
            self.loaded_events,
            enable_random_delay=self.rnd_delay_cb.isChecked(),
            min_delay=self.rnd_min_spin.value(),
            max_delay=self.rnd_max_spin.value()
        )
        self.play_thread.progress_signal.connect(self.on_playback_progress)
        self.play_thread.finished_signal.connect(self.on_playback_finished)
        self.play_thread.pause_state_signal.connect(self.on_playback_pause_state_changed)
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

    def on_playback_pause_state_changed(self, is_paused):
        self.play_start_btn.setEnabled(is_paused)
        self.play_pause_btn.setEnabled(not is_paused)

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