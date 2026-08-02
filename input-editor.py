"""
Task Easier — Macro Timeline Studio with Integrated Live Recorder & Bulk Time Adjuster
"""

import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QGroupBox, QStyle, QDialog, QFormLayout, QDoubleSpinBox,
    QDialogButtonBox, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QAction

# Import the Recorder module
from recorder import Recorder


# ==========================================
# TIME CONVERSION HELPERS
# ==========================================
def seconds_to_time_str(seconds: float) -> str:
    """Converts seconds (e.g. 94.5) to MM:SS.ms format (e.g. 01:34.500)."""
    mins, secs = divmod(max(0.0, seconds), 60)
    return f"{int(mins):02d}:{secs:06.3f}"


def time_str_to_seconds(time_str: str) -> float:
    """Parses 'MM:SS.ms' or raw seconds float into float seconds."""
    time_str = time_str.strip()
    if ":" in time_str:
        parts = time_str.split(":")
        return float(parts[0]) * 60.0 + float(parts[1])
    return float(time_str)


# ==========================================
# BULK TIME ADJUSTMENT DIALOG
# ==========================================
class TimeAdjustDialog(QDialog):
    def __init__(self, initial_time: float, count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Adjust Time of Actions")
        self.resize(380, 200)

        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        info_lbl = QLabel(f"Modifying timing for <b>{count}</b> selected action(s).")
        info_lbl.setWordWrap(True)
        layout.addWidget(info_lbl)

        self.time_input = QLineEdit(seconds_to_time_str(initial_time))
        self.time_input.setPlaceholderText("e.g. 07:05.000 or 425.0")
        form_layout.addRow("New Start Time (MM:SS.ms or Secs):", self.time_input)

        self.stagger_spin = QDoubleSpinBox()
        self.stagger_spin.setRange(0.0, 600.0)
        self.stagger_spin.setSingleStep(0.05)
        self.stagger_spin.setDecimals(3)
        self.stagger_spin.setValue(0.100)
        self.stagger_spin.setSuffix(" s")
        form_layout.addRow("Stagger Interval Between Actions:", self.stagger_spin)

        layout.addLayout(form_layout)

        # Standard Dialog Buttons
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.target_start_time = initial_time
        self.stagger_interval = 0.100

    def validate_and_accept(self):
        raw_txt = self.time_input.text().strip()
        try:
            val = time_str_to_seconds(raw_txt)
            if val < 0:
                raise ValueError("Time cannot be negative.")
            self.target_start_time = round(val, 4)
            self.stagger_interval = round(self.stagger_spin.value(), 4)
            self.accept()
        except Exception as e:
            QMessageBox.warning(
                self, "Invalid Time Format",
                f"Could not parse '{raw_txt}' into a valid timestamp.\nError: {str(e)}"
            )


# ==========================================
# THREADING FOR INTEGRATED RECORDER
# ==========================================
class EditorRecordThread(QThread):
    finished_signal = pyqtSignal(list)

    def __init__(self, record_mouse_moves=True):
        super().__init__()
        self.recorder = Recorder(record_mouse_moves=record_mouse_moves, random_click_delay=False)

    def run(self):
        self.recorder.start()
        self.recorder.wait_until_done()
        self.finished_signal.emit(self.recorder.events)

    def stop(self):
        self.recorder.stop()


# ==========================================
# MODERN ENTERPRISE DARK STYLESHEET
# ==========================================
DARK_STYLESHEET = """
QMainWindow {
    background-color: #0f172a;
}
QWidget {
    color: #f8fafc;
    font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
    font-size: 13px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #1e293b;
    border-radius: 8px;
    margin-top: 6px;
    padding-top: 10px;
    background-color: #1e293b;
    color: #0284c7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    color: #f8fafc;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #38bdf8;
}
QPushButton:pressed {
    background-color: #0284c7;
}
QPushButton#primaryBtn {
    background-color: #0284c7;
    color: #ffffff;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #0369a1;
}
QPushButton#recordBtn {
    background-color: #166534;
    color: #ffffff;
    border: none;
}
QPushButton#recordBtn:hover {
    background-color: #15803d;
}
QPushButton#dangerBtn {
    background-color: #991b1b;
    color: #ffffff;
    border: none;
}
QPushButton#dangerBtn:hover {
    background-color: #dc2626;
}
QLineEdit, QSpinBox, QDoubleSpinBox {
    background-color: #020617;
    border: 1px solid #334155;
    border-radius: 6px;
    color: #f8fafc;
    padding: 5px 8px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #38bdf8;
}
QTableWidget {
    background-color: #020617;
    border: 1px solid #1e293b;
    border-radius: 8px;
    gridline-color: #1e293b;
    color: #f8fafc;
}
QTableWidget::item:selected {
    background-color: #334155;
    color: #38bdf8;
}
QHeaderView::section {
    background-color: #1e293b;
    color: #38bdf8;
    font-weight: bold;
    border: 1px solid #1e293b;
    padding: 6px;
}
QLabel#statBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
QMenu {
    background-color: #1e293b;
    border: 1px solid #334155;
    color: #f8fafc;
}
QMenu::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}
"""


# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================
class MacroEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Task Easier — Macro Timeline Studio")
        self.resize(950, 620)
        self.setStyleSheet(DARK_STYLESHEET)

        self.file_path = ""
        self.events = []
        self.record_thread = None

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        sys_icon = self.style().standardIcon

        # --- TOP PANEL: FILE OPTIONS & FILTER ---
        top_box = QGroupBox("FILE & SEARCH TOOLS")
        top_layout = QHBoxLayout()

        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("No file loaded... Click 'Open File'")
        self.path_input.setReadOnly(True)

        self.btn_open = QPushButton("Open File")
        self.btn_open.setIcon(sys_icon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.btn_open.clicked.connect(self.load_file)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter actions (e.g. click, key_press, x=200)...")
        self.search_input.addAction(
            sys_icon(QStyle.StandardPixmap.SP_FileDialogListView),
            QLineEdit.ActionPosition.LeadingPosition
        )
        self.search_input.textChanged.connect(self.populate_table)

        top_layout.addWidget(self.path_input, stretch=2)
        top_layout.addWidget(self.btn_open)
        top_layout.addWidget(self.search_input, stretch=2)

        top_box.setLayout(top_layout)
        main_layout.addWidget(top_box)

        # --- STATS DASHBOARD ---
        stats_layout = QHBoxLayout()
        self.lbl_stat_duration = QLabel("Total Time: 00:00.000")
        self.lbl_stat_duration.setObjectName("statBox")

        self.lbl_stat_count = QLabel("Actions: 0")
        self.lbl_stat_count.setObjectName("statBox")

        self.lbl_stat_clicks = QLabel("Clicks: 0")
        self.lbl_stat_clicks.setObjectName("statBox")

        self.lbl_stat_keys = QLabel("Keys: 0")
        self.lbl_stat_keys.setObjectName("statBox")

        stats_layout.addWidget(self.lbl_stat_duration)
        stats_layout.addWidget(self.lbl_stat_count)
        stats_layout.addWidget(self.lbl_stat_clicks)
        stats_layout.addWidget(self.lbl_stat_keys)
        main_layout.addLayout(stats_layout)

        # --- MAIN ACTION TABLE ---
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "#", "Time (MM:SS.ms)", "Action Type", "X", "Y", "Key / Button", "State / Details"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.cellChanged.connect(self.on_cell_edited)

        main_layout.addWidget(self.table)

        # --- TOOLBAR & ACTION BUTTONS ---
        btn_layout = QHBoxLayout()

        self.btn_record_new = QPushButton("Record Action")
        self.btn_record_new.setObjectName("recordBtn")
        self.btn_record_new.setIcon(sys_icon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_record_new.clicked.connect(self.start_live_recording)

        self.btn_adjust_time = QPushButton("Adjust Time...")
        self.btn_adjust_time.setIcon(sys_icon(QStyle.StandardPixmap.SP_FileDialogInfoView))
        self.btn_adjust_time.clicked.connect(self.open_time_adjust_dialog)

        self.btn_up = QPushButton("Move Up")
        self.btn_up.setIcon(sys_icon(QStyle.StandardPixmap.SP_ArrowUp))
        self.btn_up.clicked.connect(lambda: self.move_event(-1))

        self.btn_down = QPushButton("Move Down")
        self.btn_down.setIcon(sys_icon(QStyle.StandardPixmap.SP_ArrowDown))
        self.btn_down.clicked.connect(lambda: self.move_event(1))

        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_duplicate.setIcon(sys_icon(QStyle.StandardPixmap.SP_FileDialogContentsView))
        self.btn_duplicate.clicked.connect(self.duplicate_selected_rows)

        self.btn_delete = QPushButton("Delete Selected")
        self.btn_delete.setObjectName("dangerBtn")
        self.btn_delete.setIcon(sys_icon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_delete.clicked.connect(self.delete_selected_rows)

        self.btn_sort = QPushButton("Sort Chronologically")
        self.btn_sort.setIcon(sys_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_sort.clicked.connect(self.sort_timeline)

        self.btn_retime = QPushButton("Recalculate Gaps")
        self.btn_retime.setIcon(sys_icon(QStyle.StandardPixmap.SP_BrowserReload))
        self.btn_retime.clicked.connect(self.recalculate_timeline)

        self.btn_save = QPushButton("Save Over")
        self.btn_save.setIcon(sys_icon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save.clicked.connect(self.save_file)

        self.btn_save_as = QPushButton("Save As")
        self.btn_save_as.setObjectName("primaryBtn")
        self.btn_save_as.setIcon(sys_icon(QStyle.StandardPixmap.SP_DriveFDIcon))
        self.btn_save_as.clicked.connect(self.save_file_as)

        btn_layout.addWidget(self.btn_record_new)
        btn_layout.addWidget(self.btn_adjust_time)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_duplicate)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_sort)
        btn_layout.addWidget(self.btn_retime)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_save_as)

        main_layout.addLayout(btn_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    # --- CONTEXT MENU & TIME ADJUSTMENT LOGIC ---
    def show_table_context_menu(self, pos):
        real_indexes = self.get_selected_real_indexes()
        if not real_indexes:
            return

        menu = QMenu(self)
        adjust_action = QAction(f"Adjust Time of Selected ({len(real_indexes)} actions)...", self)
        adjust_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogInfoView))
        adjust_action.triggered.connect(self.open_time_adjust_dialog)
        menu.addAction(adjust_action)

        delete_action = QAction("Delete Selected", self)
        delete_action.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        delete_action.triggered.connect(self.delete_selected_rows)
        menu.addAction(delete_action)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def open_time_adjust_dialog(self):
        real_indexes = self.get_selected_real_indexes()
        if not real_indexes:
            QMessageBox.information(self, "Selection Required", "Please select one or more actions to adjust their timing.")
            return

        initial_time = self.events[real_indexes[0]].get("time", 0.0)
        dialog = TimeAdjustDialog(initial_time=initial_time, count=len(real_indexes), parent=self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_start_time = dialog.target_start_time
            stagger = dialog.stagger_interval

            # Generate target timestamps for selected actions
            target_times = [round(new_start_time + (i * stagger), 4) for i in range(len(real_indexes))]

            # Check for collisions with UNSELECTED actions
            unselected_times = {
                round(ev.get("time", 0.0), 4)
                for idx, ev in enumerate(self.events)
                if idx not in real_indexes
            }

            collisions = set(target_times).intersection(unselected_times)

            if collisions:
                coll_str = ", ".join(seconds_to_time_str(t) for t in sorted(list(collisions))[:5])
                res = QMessageBox.warning(
                    self,
                    "Timestamp Collision Warning",
                    f"Warning: {len(collisions)} target timestamp(s) collide with existing actions on the timeline!\n\n"
                    f"Colliding Times: {coll_str}...\n\n"
                    f"Do you still want to apply these timestamps and re-sort?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if res != QMessageBox.StandardButton.Yes:
                    return

            # Apply updated timestamps to selected events
            for i, real_idx in enumerate(real_indexes):
                self.events[real_idx]["time"] = target_times[i]

            self.sort_timeline_silent()
            self.populate_table()
            QMessageBox.information(
                self,
                "Time Shift Applied",
                f"Successfully updated timestamp(s) for {len(real_indexes)} action(s) starting from {seconds_to_time_str(new_start_time)}."
            )

    # --- INTEGRATED LIVE RECORDER LOGIC ---
    def start_live_recording(self):
        if self.record_thread and self.record_thread.isRunning():
            self.record_thread.stop()
            return

        self.btn_record_new.setText("Recording... (Press ESC to stop)")
        self.btn_record_new.setEnabled(False)

        self.record_thread = EditorRecordThread(record_mouse_moves=True)
        self.record_thread.finished_signal.connect(self.on_live_recording_finished)
        self.record_thread.start()

    def on_live_recording_finished(self, new_events):
        self.btn_record_new.setText("Record Action")
        self.btn_record_new.setEnabled(True)
        self.record_thread = None

        if not new_events:
            QMessageBox.information(self, "Recorder", "No events were recorded.")
            return

        offset = 0.0
        if self.events:
            offset = round(self.events[-1].get("time", 0.0) + 0.500, 4)

        for ev in new_events:
            ev["time"] = round(ev.get("time", 0.0) + offset, 4)
            self.events.append(ev)

        self.sort_timeline_silent()
        self.populate_table()
        QMessageBox.information(
            self, "Recorded Actions Appended",
            f"Successfully recorded and appended {len(new_events)} actions to your timeline!"
        )

    # --- FILE HANDLING ---
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Macro JSON", "", "JSON Files (*.json)")
        if not file_path:
            return

        self.file_path = file_path
        self.path_input.setText(file_path)

        try:
            with open(file_path, "r") as f:
                self.events = json.load(f)

            if isinstance(self.events, list):
                self.sort_timeline_silent()
                self.populate_table()
            else:
                QMessageBox.warning(self, "Format Error", "JSON root must be a list of action dicts.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to open JSON file:\n{str(e)}")

    def update_dashboard_stats(self):
        if not self.events:
            self.lbl_stat_duration.setText("Total Time: 00:00.000")
            self.lbl_stat_count.setText("Actions: 0")
            self.lbl_stat_clicks.setText("Clicks: 0")
            self.lbl_stat_keys.setText("Keys: 0")
            return

        total_time = self.events[-1].get("time", 0.0) if self.events else 0.0
        clicks = sum(1 for e in self.events if e.get("type") == "mouse_click" and not e.get("pressed", True))
        keys = sum(1 for e in self.events if e.get("type") in ("key_press", "key_release"))

        self.lbl_stat_duration.setText(f"Total Time: {seconds_to_time_str(total_time)}")
        self.lbl_stat_count.setText(f"Actions: {len(self.events)}")
        self.lbl_stat_clicks.setText(f"Clicks: {clicks}")
        self.lbl_stat_keys.setText(f"Keys: {keys}")

    def populate_table(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        query = self.search_input.text().lower().strip()

        for idx, ev in enumerate(self.events):
            e_type = str(ev.get("type", ""))
            x_val = str(ev.get("x", "")) if "x" in ev else ""
            y_val = str(ev.get("y", "")) if "y" in ev else ""
            kb_val = str(ev.get("key") or ev.get("button", ""))

            match_str = f"{e_type} {x_val} {y_val} {kb_val}".lower()
            if query and query not in match_str:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)

            idx_item = QTableWidgetItem(str(idx + 1))
            idx_item.setData(Qt.ItemDataRole.UserRole, idx)
            idx_item.setFlags(idx_item.flags() ^ Qt.ItemFlag.ItemIsEditable)

            formatted_time = seconds_to_time_str(ev.get("time", 0.0))
            time_item = QTableWidgetItem(formatted_time)

            type_item = QTableWidgetItem(e_type)
            x_item = QTableWidgetItem(x_val)
            y_item = QTableWidgetItem(y_val)
            kb_item = QTableWidgetItem(kb_val)

            state_val = ""
            if "pressed" in ev:
                state_val = "DOWN" if ev["pressed"] else "UP"
            elif "dx" in ev or "dy" in ev:
                state_val = f"dx={ev.get('dx', 0)}, dy={ev.get('dy', 0)}"

            state_item = QTableWidgetItem(state_val)

            bg_color = QColor("#020617")
            if e_type == "mouse_click":
                bg_color = QColor("#064e3b")
            elif e_type in ("key_press", "key_release"):
                bg_color = QColor("#1e3a8a")
            elif e_type == "mouse_scroll":
                bg_color = QColor("#78350f")

            for col_idx, item in enumerate([idx_item, time_item, type_item, x_item, y_item, kb_item, state_item]):
                item.setBackground(bg_color)
                self.table.setItem(row, col_idx, item)

        self.table.blockSignals(False)
        self.update_dashboard_stats()

    # --- EDITING & TIMELINE ACTIONS ---
    def on_cell_edited(self, row, col):
        idx_item = self.table.item(row, 0)
        if not idx_item:
            return

        real_idx = idx_item.data(Qt.ItemDataRole.UserRole)
        if real_idx is None or real_idx >= len(self.events):
            return

        ev = self.events[real_idx]
        cell_text = self.table.item(row, col).text().strip()

        try:
            if col == 1:
                ev["time"] = max(0.0, round(time_str_to_seconds(cell_text), 4))
            elif col == 2:
                new_type = cell_text.lower()
                ev["type"] = new_type
                if new_type == "mouse_click":
                    ev.setdefault("x", 0)
                    ev.setdefault("y", 0)
                    ev.setdefault("button", "left")
                    ev.setdefault("pressed", True)
                elif new_type in ("key_press", "key_release"):
                    ev.setdefault("key", "a")
                    ev["pressed"] = (new_type == "key_press")
                elif new_type == "mouse_move":
                    ev.setdefault("x", 0)
                    ev.setdefault("y", 0)
            elif col == 3 and cell_text:
                ev["x"] = int(float(cell_text))
            elif col == 4 and cell_text:
                ev["y"] = int(float(cell_text))
            elif col == 5:
                if ev.get("type") in ("key_press", "key_release"):
                    ev["key"] = cell_text
                elif ev.get("type") == "mouse_click":
                    ev["button"] = cell_text.lower()
            elif col == 6:
                txt_upper = cell_text.upper()
                if txt_upper in ("DOWN", "PRESS", "TRUE", "1"):
                    ev["pressed"] = True
                elif txt_upper in ("UP", "RELEASE", "FALSE", "0"):
                    ev["pressed"] = False

        except ValueError:
            QMessageBox.warning(self, "Invalid Value", f"Invalid format '{cell_text}' for this field.")

        self.populate_table()

    def get_selected_real_indexes(self):
        selected_rows = set(index.row() for index in self.table.selectedIndexes())
        real_indexes = []
        for r in selected_rows:
            idx_item = self.table.item(r, 0)
            if idx_item:
                real_indexes.append(idx_item.data(Qt.ItemDataRole.UserRole))
        return sorted(real_indexes)

    def delete_selected_rows(self):
        real_indexes = self.get_selected_real_indexes()
        if not real_indexes:
            QMessageBox.information(self, "Selection", "Select rows to delete.")
            return

        for idx in reversed(real_indexes):
            del self.events[idx]

        self.populate_table()

    def duplicate_selected_rows(self):
        real_indexes = self.get_selected_real_indexes()
        if not real_indexes:
            return

        for idx in real_indexes:
            cloned_ev = dict(self.events[idx])
            cloned_ev["time"] = round(cloned_ev.get("time", 0.0) + 0.050, 4)
            self.events.insert(idx + 1, cloned_ev)

        self.sort_timeline_silent()
        self.populate_table()

    def move_event(self, direction):
        real_indexes = self.get_selected_real_indexes()
        if len(real_indexes) != 1:
            return

        idx = real_indexes[0]
        target_idx = idx + direction

        if 0 <= target_idx < len(self.events):
            self.events[idx], self.events[target_idx] = self.events[target_idx], self.events[idx]

            t_temp = self.events[idx].get("time", 0.0)
            self.events[idx]["time"] = self.events[target_idx].get("time", 0.0)
            self.events[target_idx]["time"] = t_temp

            self.populate_table()

    def sort_timeline_silent(self):
        if self.events:
            self.events.sort(key=lambda e: e.get("time", 0.0))

    def sort_timeline(self):
        if not self.events:
            return
        self.sort_timeline_silent()
        self.populate_table()
        QMessageBox.information(self, "Sorted", "All macro events sorted chronologically by timestamp.")

    def recalculate_timeline(self):
        if not self.events:
            return

        first_time = self.events[0].get("time", 0.0)
        for ev in self.events:
            ev["time"] = max(0.0, round(ev.get("time", 0.0) - first_time, 4))

        self.sort_timeline_silent()
        self.populate_table()
        QMessageBox.information(self, "Timeline Reset", "Timestamps resynced starting from 00:00.000.")

    # --- SAVE OPERATIONS ---
    def save_file(self):
        if not self.file_path:
            self.save_file_as()
            return
        self._write_to_disk(self.file_path)

    def save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Macro JSON As", "", "JSON Files (*.json)")
        if path:
            self.file_path = path
            self.path_input.setText(path)
            self._write_to_disk(path)

    def _write_to_disk(self, save_path):
        try:
            self.sort_timeline_silent()
            with open(save_path, "w") as f:
                json.dump(self.events, f, indent=2)
            QMessageBox.information(self, "Saved", f"Saved {len(self.events)} frame actions to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MacroEditorApp()
    window.show()
    sys.exit(app.exec())