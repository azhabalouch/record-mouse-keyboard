"""
app.py
------
Task Easier — Windows Input Automation
Built with PyQt6 using modern Win32 Native SendInput drivers.
"""

import sys
import os
import json
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QFileDialog, QSlider,
    QSpinBox, QDoubleSpinBox, QMessageBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer

from recorder import Recorder
from player import Player

# Force Windows Per-Monitor V2 DPI Awareness BEFORE QApplication creation
if sys.platform == "win32":
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


class ClickableSlider(QSlider):
    """Custom slider that immediately jumps and seeks when clicked anywhere on the track."""
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            val = int(self.minimum() + (self.maximum() - self.minimum()) * (event.position().x() / self.width()))
            val = max(self.minimum(), min(self.maximum(), val))
            self.setValue(val)
            self.sliderMoved.emit(val)
        super().mousePressEvent(event)


class RecordThread(QThread):
    finished_signal = pyqtSignal(list)

    def __init__(self, record_mouse_moves=True):
        super().__init__()
        self.recorder = Recorder(record_mouse_moves=record_mouse_moves, random_click_delay=False)

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

    def __init__(self, events, speed=1.0, loops=1, enable_rnd=False, min_d=0.1, max_d=0.5):
        super().__init__()
        self.player = Player(
            events,
            speed_multiplier=speed,
            loop_count=loops,
            enable_random_delay=enable_rnd,
            min_delay=min_d,
            max_delay=max_d,
            on_progress=self.progress_signal.emit,
            on_state_change=self.pause_state_signal.emit
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


class TaskEasierApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Easier")
        self.setFixedSize(620, 640)

        self.record_thread = None
        self.play_thread = None
        self.loaded_events = []
        self.recording_duration = 0.0

        # Timers
        self.rec_timer = QTimer()
        self.rec_timer.setInterval(50)
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
        self.apply_enterprise_theme()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        # Executive Header Bar
        header_layout = QHBoxLayout()
        title_lbl = QLabel("TASK EASIER")
        title_lbl.setObjectName("appTitle")
        
        ver_lbl = QLabel("v1.0.0")
        ver_lbl.setObjectName("verBadge")

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(ver_lbl)
        header_layout.addStretch()

        # Elevation Security Badge
        admin_lbl = QLabel()
        if is_admin():
            admin_lbl.setText("● ELEVATED ADMIN")
            admin_lbl.setObjectName("adminActive")
        else:
            admin_lbl.setText("● STANDARD USER")
            admin_lbl.setObjectName("adminWarning")
            admin_lbl.setToolTip("Re-run application as Administrator to automate elevated/UAC windows.")
        header_layout.addWidget(admin_lbl)

        main_layout.addLayout(header_layout)

        # Tab View
        tabs = QTabWidget()
        tabs.addTab(self.create_recorder_tab(), "Macro Recorder")
        tabs.addTab(self.create_player_tab(), "Macro Player")

        main_layout.addWidget(tabs)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    # --- TAB 1: RECORDER ---
    def create_recorder_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        file_box = QGroupBox("OUTPUT CONFIGURATION")
        fb_layout = QVBoxLayout()
        fb_layout.setSpacing(8)

        f_line = QHBoxLayout()
        f_line.addWidget(QLabel("Preset Name:"))
        self.filename_input = QLineEdit("task_macro.json")
        f_line.addWidget(self.filename_input)

        dir_line = QHBoxLayout()
        self.use_curr_dir_cb = QCheckBox("Save in working directory")
        self.use_curr_dir_cb.setChecked(True)
        self.use_curr_dir_cb.toggled.connect(self.toggle_dir_selection)

        self.path_input = QLineEdit(os.getcwd())
        self.path_input.setEnabled(False)
        self.browse_btn = QPushButton("Browse")
        self.browse_btn.setEnabled(False)
        self.browse_btn.clicked.connect(self.browse_location)

        dir_line.addWidget(self.path_input)
        dir_line.addWidget(self.browse_btn)

        fb_layout.addLayout(f_line)
        fb_layout.addWidget(self.use_curr_dir_cb)
        fb_layout.addLayout(dir_line)
        file_box.setLayout(fb_layout)

        opts_box = QGroupBox("CAPTURE SETTINGS")
        opts_layout = QVBoxLayout()
        opts_layout.setSpacing(8)

        self.rec_moves_cb = QCheckBox("Track Mouse Pointer Movements (Uncheck for clicks & keys only)")
        self.rec_moves_cb.setChecked(True)
        opts_layout.addWidget(self.rec_moves_cb)

        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Countdown Start Delay:"))
        self.rec_delay_spin = QSpinBox()
        self.rec_delay_spin.setRange(0, 30)
        self.rec_delay_spin.setValue(0)
        self.rec_delay_spin.setSuffix(" sec")
        delay_layout.addWidget(self.rec_delay_spin)
        delay_layout.addStretch()
        opts_layout.addLayout(delay_layout)
        opts_box.setLayout(opts_layout)

        timer_card = QFrame()
        timer_card.setObjectName("timerCard")
        tc_layout = QVBoxLayout(timer_card)
        tc_layout.setContentsMargins(10, 10, 10, 10)

        self.rec_time_lbl = QLabel("00:00.0")
        self.rec_time_lbl.setObjectName("timerDisplay")
        self.rec_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.rec_status_lbl = QLabel("READY — ESC key stops recording")
        self.rec_status_lbl.setObjectName("statusLabel")
        self.rec_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tc_layout.addWidget(self.rec_time_lbl)
        tc_layout.addWidget(self.rec_status_lbl)

        ctrl_layout = QHBoxLayout()
        self.rec_play_btn = QPushButton("Record")
        self.rec_play_btn.setObjectName("btnPrimary")
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

        layout.addWidget(file_box)
        layout.addWidget(opts_box)
        layout.addWidget(timer_card)
        layout.addLayout(ctrl_layout)

        tab.setLayout(layout)
        return tab

    # --- TAB 2: PLAYER ---
    def create_player_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 16, 12, 12)
        layout.setSpacing(12)

        load_box = QGroupBox("MACRO TARGET")
        lb_layout = QHBoxLayout()
        self.load_path_input = QLineEdit()
        self.load_path_input.setPlaceholderText("Select recorded macro JSON file...")
        self.load_btn = QPushButton("Browse")
        self.load_btn.clicked.connect(self.load_file)

        lb_layout.addWidget(self.load_path_input)
        lb_layout.addWidget(self.load_btn)
        load_box.setLayout(lb_layout)

        exec_box = QGroupBox("EXECUTION & TIMING CONTROLS")
        exec_layout = QVBoxLayout()
        exec_layout.setSpacing(8)

        h1 = QHBoxLayout()
        h1.addWidget(QLabel("Speed Scale:"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.25, 5.0)
        self.speed_spin.setValue(1.0)
        self.speed_spin.setSingleStep(0.25)
        self.speed_spin.setSuffix(" x")
        h1.addWidget(self.speed_spin)

        h1.addWidget(QLabel("Loops:"))
        self.loop_spin = QSpinBox()
        self.loop_spin.setRange(0, 9999)
        self.loop_spin.setValue(1)
        self.loop_spin.setToolTip("Set to 0 for infinite looping")
        h1.addWidget(self.loop_spin)

        h1.addWidget(QLabel("Start Delay:"))
        self.play_delay_spin = QSpinBox()
        self.play_delay_spin.setRange(0, 30)
        self.play_delay_spin.setValue(0)
        self.play_delay_spin.setSuffix(" sec")
        h1.addWidget(self.play_delay_spin)
        exec_layout.addLayout(h1)

        rnd_layout = QHBoxLayout()
        self.rnd_delay_cb = QCheckBox("Inject Random Human Delays")
        self.rnd_min_spin = QDoubleSpinBox()
        self.rnd_min_spin.setRange(0.0, 5.0)
        self.rnd_min_spin.setValue(0.1)
        self.rnd_max_spin = QDoubleSpinBox()
        self.rnd_max_spin.setRange(0.0, 5.0)
        self.rnd_max_spin.setValue(0.5)

        rnd_layout.addWidget(self.rnd_delay_cb)
        rnd_layout.addWidget(QLabel("Min:"))
        rnd_layout.addWidget(self.rnd_min_spin)
        rnd_layout.addWidget(QLabel("Max:"))
        rnd_layout.addWidget(self.rnd_max_spin)
        exec_layout.addLayout(rnd_layout)

        exec_box.setLayout(exec_layout)

        play_card = QFrame()
        play_card.setObjectName("timerCard")
        pc_layout = QVBoxLayout(play_card)
        pc_layout.setContentsMargins(10, 10, 10, 10)

        # Custom Clickable Seek Slider
        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.setEnabled(False)
        self.seek_slider.sliderMoved.connect(self.user_seek)

        self.play_time_lbl = QLabel("00:00 / 00:00")
        self.play_time_lbl.setObjectName("timerDisplay")
        self.play_time_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.play_status_lbl = QLabel("READY — Press ESC to Pause/Resume during execution")
        self.play_status_lbl.setObjectName("statusLabel")
        self.play_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        pc_layout.addWidget(self.seek_slider)
        pc_layout.addWidget(self.play_time_lbl)
        pc_layout.addWidget(self.play_status_lbl)

        ctrl_layout = QHBoxLayout()
        self.play_start_btn = QPushButton("Play")
        self.play_start_btn.setObjectName("btnPrimary")
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

        layout.addWidget(load_box)
        layout.addWidget(exec_box)
        layout.addWidget(play_card)
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
        if self.record_thread and self.record_thread.isRunning():
            if self.record_thread.is_paused:
                self.record_thread.resume()
                self.rec_status_lbl.setText("RECORDING IN PROGRESS — Press ESC to Stop")
                self.rec_play_btn.setEnabled(False)
                self.rec_pause_btn.setEnabled(True)
            return

        delay = self.rec_delay_spin.value()
        if delay > 0:
            self.rec_delay_remaining = delay
            self.rec_play_btn.setEnabled(False)
            self.rec_stop_btn.setEnabled(True)
            self.rec_status_lbl.setText(f"Starting in {self.rec_delay_remaining}s...")
            self.rec_delay_timer.start()
        else:
            self.execute_start_recording()

    def handle_rec_delay_countdown(self):
        self.rec_delay_remaining -= 1
        if self.rec_delay_remaining > 0:
            self.rec_status_lbl.setText(f"Starting in {self.rec_delay_remaining}s...")
        else:
            self.rec_delay_timer.stop()
            self.execute_start_recording()

    def execute_start_recording(self):
        self.record_thread = RecordThread(record_mouse_moves=self.rec_moves_cb.isChecked())
        self.record_thread.finished_signal.connect(self.on_recording_finished)
        self.record_thread.start()

        self.rec_timer.start()
        self.rec_status_lbl.setText("RECORDING IN PROGRESS — Press ESC to Stop")
        self.rec_play_btn.setEnabled(False)
        self.rec_pause_btn.setEnabled(True)
        self.rec_stop_btn.setEnabled(True)

    def pause_recording(self):
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.pause()
            self.rec_status_lbl.setText("RECORDING PAUSED")
            self.rec_play_btn.setEnabled(True)
            self.rec_pause_btn.setEnabled(False)

    def stop_recording(self):
        if self.rec_delay_timer.isActive():
            self.rec_delay_timer.stop()
            self.rec_play_btn.setEnabled(True)
            self.rec_stop_btn.setEnabled(False)
            self.rec_status_lbl.setText("Recording cancelled.")
            return

        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
        self.rec_timer.stop()

    def update_rec_time(self):
        if self.record_thread and self.record_thread.isRunning():
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

        self.loaded_events = events
        self.rec_status_lbl.setText(f"SAVED: {filename} ({len(events)} events)")
        self.rec_play_btn.setEnabled(True)
        self.rec_pause_btn.setEnabled(False)
        self.rec_stop_btn.setEnabled(False)
        self.record_thread = None

        self.load_path_input.setText(save_path)
        if events:
            self.recording_duration = events[-1]["time"]
            self.seek_slider.setEnabled(True)
            self.play_start_btn.setEnabled(True)
            self.update_playback_time_label(0.0)

        QMessageBox.information(self, "Recording Complete", f"Successfully recorded {len(events)} actions to:\n{save_path}")

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
                    self.play_status_lbl.setText(f"LOADED: {os.path.basename(file_path)} ({len(self.loaded_events)} events)")
                else:
                    QMessageBox.warning(self, "Warning", "Selected file contains no valid events.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def update_playback_time_label(self, current_sec):
        curr_m, curr_s = divmod(current_sec, 60)
        tot_m, tot_s = divmod(self.recording_duration, 60)
        self.play_time_lbl.setText(f"{int(curr_m):02d}:{int(curr_s):02d} / {int(tot_m):02d}:{int(tot_s):02d}")

    def start_playback_flow(self):
        if self.play_thread and self.play_thread.isRunning():
            if self.play_thread.is_paused:
                self.play_thread.resume()
                self.play_status_lbl.setText("PLAYBACK IN PROGRESS — Press ESC to Pause/Resume")
                self.play_start_btn.setEnabled(False)
                self.play_pause_btn.setEnabled(True)
            return

        delay = self.play_delay_spin.value()
        if delay > 0 and not self.play_delay_timer.isActive():
            self.play_delay_remaining = delay
            self.play_start_btn.setEnabled(False)
            self.play_stop_btn.setEnabled(True)
            self.play_status_lbl.setText(f"Starting playback in {self.play_delay_remaining}s...")
            self.play_delay_timer.start()
        else:
            self.execute_start_playback()

    def handle_play_delay_countdown(self):
        self.play_delay_remaining -= 1
        if self.play_delay_remaining > 0:
            self.play_status_lbl.setText(f"Starting playback in {self.play_delay_remaining}s...")
        else:
            self.play_delay_timer.stop()
            self.execute_start_playback()

    def execute_start_playback(self):
        self.play_thread = PlayThread(
            self.loaded_events,
            speed=self.speed_spin.value(),
            loops=self.loop_spin.value(),
            enable_rnd=self.rnd_delay_cb.isChecked(),
            min_d=self.rnd_min_spin.value(),
            max_d=self.rnd_max_spin.value()
        )
        self.play_thread.progress_signal.connect(self.on_playback_progress)
        self.play_thread.finished_signal.connect(self.on_playback_finished)
        self.play_thread.pause_state_signal.connect(self.on_playback_pause_state_changed)

        # Pre-seek if timeline was set prior to pressing play
        initial_seek_time = (self.seek_slider.value() / 1000.0) * self.recording_duration
        if initial_seek_time > 0:
            self.play_thread.seek_to(initial_seek_time)

        self.play_thread.start()

        self.play_status_lbl.setText("PLAYBACK IN PROGRESS — Press ESC to Pause/Resume")
        self.play_start_btn.setEnabled(False)
        self.play_pause_btn.setEnabled(True)
        self.play_stop_btn.setEnabled(True)

    def pause_playback(self):
        if self.play_thread and self.play_thread.isRunning():
            self.play_thread.pause()
            self.play_status_lbl.setText("PLAYBACK PAUSED")

    def stop_playback(self):
        if self.play_delay_timer.isActive():
            self.play_delay_timer.stop()
            self.play_start_btn.setEnabled(True)
            self.play_stop_btn.setEnabled(False)
            self.play_status_lbl.setText("Playback cancelled.")
            return

        if self.play_thread and self.play_thread.isRunning():
            self.play_thread.stop()

    def user_seek(self, value):
        if self.recording_duration > 0:
            target_time = (value / 1000.0) * self.recording_duration
            self.update_playback_time_label(target_time)
            if self.play_thread and self.play_thread.isRunning():
                self.play_thread.seek_to(target_time)

    def on_playback_progress(self, current_time):
        if self.recording_duration > 0 and not self.seek_slider.isSliderDown():
            progress_ratio = current_time / self.recording_duration
            self.seek_slider.setValue(int(progress_ratio * 1000))
            self.update_playback_time_label(current_time)

    def on_playback_pause_state_changed(self, is_paused):
        self.play_start_btn.setEnabled(is_paused)
        self.play_pause_btn.setEnabled(not is_paused)

    def on_playback_finished(self):
        self.play_start_btn.setEnabled(True)
        self.play_pause_btn.setEnabled(False)
        self.play_stop_btn.setEnabled(False)
        self.seek_slider.setValue(0)
        self.update_playback_time_label(0.0)
        self.play_status_lbl.setText("PLAYBACK COMPLETE")
        self.play_thread = None

    def apply_enterprise_theme(self):
        enterprise_qss = """
        QMainWindow {
            background-color: #0f172a;
        }
        QWidget {
            color: #f8fafc;
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            font-size: 13px;
        }
        
        #appTitle {
            font-size: 18px;
            font-weight: 800;
            color: #38bdf8;
            letter-spacing: 1px;
        }
        #verBadge {
            background-color: #1e293b;
            color: #94a3b8;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: bold;
        }
        #adminActive {
            background-color: #064e3b;
            color: #34d399;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }
        #adminWarning {
            background-color: #451a03;
            color: #fb923c;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
        }

        QTabWidget::pane {
            border: 1px solid #1e293b;
            background-color: #0f172a;
            border-radius: 8px;
        }
        QTabBar::tab {
            background-color: #1e293b;
            color: #94a3b8;
            padding: 10px 24px;
            margin-right: 4px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            font-weight: 600;
        }
        QTabBar::tab:selected {
            background-color: #0284c7;
            color: #ffffff;
        }

        QGroupBox {
            border: 1px solid #1e293b;
            background-color: #1e293b;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 14px;
            font-weight: 700;
            font-size: 11px;
            color: #0284c7;
            letter-spacing: 0.5px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 4px;
        }

        #timerCard {
            background-color: #020617;
            border: 1px solid #1e293b;
            border-radius: 8px;
        }
        #timerDisplay {
            font-size: 32px;
            font-weight: 800;
            color: #38bdf8;
            font-family: 'Consolas', 'Courier New', monospace;
        }
        #statusLabel {
            font-size: 11px;
            font-weight: 600;
            color: #64748b;
            letter-spacing: 0.5px;
        }

        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #020617;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 6px 10px;
            color: #f8fafc;
            selection-background-color: #0284c7;
        }
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border-color: #38bdf8;
        }
        QCheckBox {
            spacing: 8px;
            color: #cbd5e1;
        }
        
        QPushButton {
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 8px 16px;
            color: #f8fafc;
            font-weight: 700;
        }
        QPushButton:hover {
            background-color: #334155;
            border-color: #475569;
        }
        QPushButton:disabled {
            background-color: #0f172a;
            color: #475569;
            border-color: #1e293b;
        }
        #btnPrimary {
            background-color: #0284c7;
            border: none;
        }
        #btnPrimary:hover {
            background-color: #0369a1;
        }
        #btnPrimary:disabled {
            background-color: #0f172a;
            color: #475569;
        }

        QSlider::groove:horizontal {
            border: none;
            height: 6px;
            background: #1e293b;
            border-radius: 3px;
        }
        QSlider::sub-page:horizontal {
            background: #0284c7;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #38bdf8;
            border: none;
            width: 14px;
            height: 14px;
            margin: -4px 0;
            border-radius: 7px;
        }
        """
        self.setStyleSheet(enterprise_qss)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TaskEasierApp()
    window.show()
    sys.exit(app.exec())