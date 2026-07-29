import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QFileDialog, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
    QGroupBox, QStyle
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


# ==========================================
# TIME CONVERSION HELPERS
# ==========================================
def seconds_to_time_str(seconds: float) -> str:
    """Converts seconds (e.g. 94.5) to MM:SS.ms format (e.g. 01:34.500)."""
    mins, secs = divmod(seconds, 60)
    return f"{int(mins):02d}:{secs:06.3f}"


def time_str_to_seconds(time_str: str) -> float:
    """Parses 'MM:SS.ms' or raw seconds float into float seconds."""
    time_str = time_str.strip()
    if ":" in time_str:
        parts = time_str.split(":")
        return float(parts[0]) * 60.0 + float(parts[1])
    return float(time_str)


# ==========================================
# MODERN DARK THEME STYLESHEET
# ==========================================
DARK_STYLESHEET = """
QMainWindow {
    background-color: #181825;
}
QWidget {
    color: #cdd6f4;
    font-family: "Aptos", "Fira Sans", "Segoe UI", sans-serif;
    font-size: 13px;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 6px;
    padding-top: 10px;
    background-color: #1e1e2e;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #89b4fa;
}
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 600;
    color: #cdd6f4;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton#primaryBtn {
    background-color: #89b4fa;
    color: #11111b;
    border: none;
}
QPushButton#primaryBtn:hover {
    background-color: #b4befe;
}
QPushButton#dangerBtn {
    background-color: #f38ba8;
    color: #11111b;
    border: none;
}
QPushButton#dangerBtn:hover {
    background-color: #f5e0dc;
}
QLineEdit {
    background-color: #11111b;
    border: 1px solid #45475a;
    border-radius: 6px;
    color: #cdd6f4;
    padding: 5px 8px;
}
QLineEdit:focus {
    border-color: #89b4fa;
}
QTableWidget {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 8px;
    gridline-color: #313244;
    color: #cdd6f4;
}
QTableWidget::item:selected {
    background-color: #45475a;
    color: #89b4fa;
}
QHeaderView::section {
    background-color: #1e1e2e;
    color: #89b4fa;
    font-weight: bold;
    border: 1px solid #313244;
    padding: 6px;
}
QLabel#statBox {
    background-color: #1e1e2e;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: bold;
}
"""


# ==========================================
# MAIN APPLICATION WINDOW
# ==========================================
class MacroEditorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JSON Macro Timeline Studio")
        self.resize(820, 580)
        self.setStyleSheet(DARK_STYLESHEET)

        self.file_path = ""
        self.events = []

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)

        # Get system standard icon provider
        sys_icon = self.style().standardIcon

        # --- TOP PANEL: FILE OPTIONS & FILTER ---
        top_box = QGroupBox("File & Filter Tools")
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
        self.table.cellChanged.connect(self.on_cell_edited)

        main_layout.addWidget(self.table)

        # --- TOOLBAR & ACTION BUTTONS ---
        btn_layout = QHBoxLayout()

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

        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_duplicate)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_retime)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_save_as)

        main_layout.addLayout(btn_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

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
            x_val = str(ev.get("x", ""))
            y_val = str(ev.get("y", ""))
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
            x_item = QTableWidgetItem(x_val if "x" in ev else "")
            y_item = QTableWidgetItem(y_val if "y" in ev else "")
            kb_item = QTableWidgetItem(kb_val)

            state_val = ""
            if "pressed" in ev:
                state_val = "DOWN" if ev["pressed"] else "UP"
            elif "dx" in ev or "dy" in ev:
                state_val = f"dx={ev.get('dx')}, dy={ev.get('dy')}"

            state_item = QTableWidgetItem(state_val)

            bg_color = QColor("#181825")
            if e_type == "mouse_click":
                bg_color = QColor("#1e3a29")
            elif e_type in ("key_press", "key_release"):
                bg_color = QColor("#1e2a3a")
            elif e_type == "mouse_scroll":
                bg_color = QColor("#3a2e1e")

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
                ev["time"] = time_str_to_seconds(cell_text)
            elif col == 2:
                ev["type"] = cell_text
            elif col == 3 and cell_text:
                ev["x"] = int(float(cell_text))
            elif col == 4 and cell_text:
                ev["y"] = int(float(cell_text))
            elif col == 5:
                if ev.get("type") in ("key_press", "key_release"):
                    ev["key"] = cell_text
                elif ev.get("type") == "mouse_click":
                    ev["button"] = cell_text
        except ValueError:
            QMessageBox.warning(self, "Invalid Value", f"Invalid format '{cell_text}' for this column.")

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
            cloned_ev["time"] += 0.050
            self.events.insert(idx + 1, cloned_ev)

        self.populate_table()

    def move_event(self, direction):
        real_indexes = self.get_selected_real_indexes()
        if len(real_indexes) != 1:
            return

        idx = real_indexes[0]
        target_idx = idx + direction

        if 0 <= target_idx < len(self.events):
            self.events[idx], self.events[target_idx] = self.events[target_idx], self.events[idx]
            self.populate_table()

    def recalculate_timeline(self):
        if not self.events:
            return

        first_time = self.events[0].get("time", 0.0)
        for ev in self.events:
            ev["time"] = max(0.0, round(ev.get("time", 0.0) - first_time, 3))

        self.populate_table()
        QMessageBox.information(self, "Timeline Reset", "Timestamps resynced to eliminate leading dead space.")

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