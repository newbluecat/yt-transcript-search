import csv
import datetime
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

import database
from models import SearchParams

if TYPE_CHECKING:
    import sqlite3

    from database import SearchResult

from search_worker import SearchWorker

MAX_QUERY_LENGTH: Final[int] = 50
QPROGRESS_ERROR_STYLESHEET = """
    QProgressBar {
        border: 1px solid #bcbcbc;
        border-radius: 4px;
        background-color: #ffcccc; /* Light red background */
        text-align: center;
        color: #FFFFFF; /* Text color */
        font-weight: bold;
    }

    QProgressBar::chunk {
        background-color: #cc0000; /* Darker red for progress fill */
        border-radius: 3px; /* Slightly smaller than container to look clean */
}
"""


class MainWindow(QMainWindow):
    """Main window interface."""

    def __init__(self) -> None:
        """Initialize main window."""
        super().__init__()
        self.setWindowTitle("YouTube Transcript Search")
        self.resize(650, 700)

        central_widget: QWidget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout: QVBoxLayout = QVBoxLayout(central_widget)

        self._setup_menu_bar()
        self._setup_results_table(main_layout)
        self._setup_search_options(main_layout)
        self._setup_progress_and_buttons(main_layout)

    def _setup_menu_bar(self) -> None:
        """Construct the top menu bar."""
        file_menu = self.menuBar().addMenu("Options")

        export_action = file_menu.addAction("Export Results to CSV")
        export_action.triggered.connect(self.on_export_clicked)
        wipe_action = file_menu.addAction("Clear Database")
        wipe_action.triggered.connect(self.on_wipe_db_clicked)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def _setup_results_table(self, main_layout: QVBoxLayout) -> None:
        self.results_table: QTableWidget = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Title", "Channel", "Date", "Time", "Snippet"])
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.setShowGrid(False)
        self.results_table.setSortingEnabled(True)
        self.results_table.cellClicked.connect(self.on_cell_clicked)

        main_layout.addWidget(self.results_table, stretch=1)

    def _setup_search_options(self, main_layout: QVBoxLayout) -> None:
        options_layout: QVBoxLayout = QVBoxLayout()

        source_id_row: QHBoxLayout = QHBoxLayout()
        source_label: QLabel = QLabel("Source:")
        self.source_combo: QComboBox = QComboBox()
        self.source_combo.addItems(
            [
                "Playlist",
                "Channel (Videos)",
                "Channel (Live)",
                "Channel (Shorts)",
            ],
        )

        # --- ID Input Text Box ---
        id_label: QLabel = QLabel("ID:")
        self.id_input: QLineEdit = QLineEdit()
        self.source_combo.currentTextChanged.connect(self.on_source_changed)
        self.on_source_changed(self.source_combo.currentText())

        source_id_row.addWidget(source_label)
        source_id_row.addWidget(self.source_combo)
        source_id_row.addSpacing(30)
        source_id_row.addWidget(id_label)
        source_id_row.addWidget(self.id_input, stretch=1)
        options_layout.addLayout(source_id_row)

        # --- Upload Date Filter ---
        date_row: QHBoxLayout = QHBoxLayout()
        date_label: QLabel = QLabel("Upload Date:")

        self.date_any_radio: QRadioButton = QRadioButton("All Time")
        self.date_any_radio.setChecked(True)

        self.date_custom_radio: QRadioButton = QRadioButton("Custom Range:")

        self.date_from: QDateEdit = QDateEdit()
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate())
        self.date_from.setEnabled(False)

        date_separator_label: QLabel = QLabel("-")

        self.date_to: QDateEdit = QDateEdit()
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())
        self.date_to.setEnabled(False)

        self.date_custom_radio.toggled.connect(self.on_date_mode_toggled)

        date_row.addWidget(date_label)
        date_row.addSpacing(10)
        date_row.addWidget(self.date_any_radio)
        date_row.addSpacing(10)
        date_row.addWidget(self.date_custom_radio)
        date_row.addWidget(self.date_from)
        date_row.addWidget(date_separator_label)
        date_row.addWidget(self.date_to)
        date_row.addStretch()
        options_layout.addLayout(date_row)

        # --- Query Input Text Box ---
        query_row: QHBoxLayout = QHBoxLayout()
        query_label: QLabel = QLabel("Query:")
        self.query_input: QLineEdit = QLineEdit()
        self.query_input.setPlaceholderText("Search terms...")
        self.query_input.setMaxLength(MAX_QUERY_LENGTH)
        query_row.addWidget(query_label)
        query_row.addWidget(self.query_input)
        options_layout.addLayout(query_row)

        main_layout.addLayout(options_layout)

    def _setup_progress_and_buttons(self, main_layout: QVBoxLayout) -> None:
        """Construct the progress bar and control buttons."""
        # --- Progress Bar ---
        self.progress_bar: QProgressBar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("")
        main_layout.addWidget(self.progress_bar)

        # --- Button Layout ---
        button_layout: QHBoxLayout = QHBoxLayout()
        button_layout.addStretch()

        self.clear_button: QPushButton = QPushButton("Clear")
        self.clear_button.setEnabled(False)
        self.clear_button.clicked.connect(self.clear_results)

        self.abort_button: QPushButton = QPushButton("Abort")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.on_abort_clicked)

        self.search_button: QPushButton = QPushButton("Search")
        self.search_button.setEnabled(False)
        self.search_button.clicked.connect(self.on_search_clicked)

        self.id_input.textChanged.connect(self.text_changed)
        self.query_input.textChanged.connect(self.text_changed)

        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.abort_button)
        button_layout.addWidget(self.search_button)
        main_layout.addLayout(button_layout)

    def on_export_clicked(self) -> None:
        """Export the current table results to a CSV file."""
        row_count: int = self.results_table.rowCount()
        if row_count == 0:
            self.progress_bar.setFormat("No results to save")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Results",
            "search_output.csv",
            "CSV Files (*.csv)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".csv"):
            file_path += ".csv"

        with Path(file_path).open(mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Title", "Channel", "Date", "Time", "URL"])

            for row in range(row_count):
                title_item: QTableWidgetItem | None = self.results_table.item(row, 0)
                channel_item: QTableWidgetItem | None = self.results_table.item(row, 1)
                date_item: QTableWidgetItem | None = self.results_table.item(row, 2)
                time_item: QTableWidgetItem | None = self.results_table.item(row, 3)
                snippet_item: QTableWidgetItem | None = self.results_table.item(row, 4)

                title: str = title_item.text() if title_item is not None else ""
                channel: str = channel_item.text() if channel_item is not None else ""
                date_str: str = date_item.text() if date_item is not None else ""
                time_str: str = time_item.text() if time_item is not None else ""

                url: str = ""
                if snippet_item is not None:
                    stored_url: str = snippet_item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(stored_url, str):
                        url = stored_url

                writer.writerow([title, channel, date_str, time_str, url])

        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(f"Results saved to {Path(file_path).name}")

    def on_wipe_db_clicked(self) -> None:
        """Prompt the user and wipe the database if confirmed."""
        reply: QMessageBox.StandardButton = QMessageBox.question(
            self,
            "Wipe Database",
            "Are you sure you want to delete all downloaded transcripts? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            conn: sqlite3.Connection | None = None
            try:
                conn = database.get_connection("transcripts.db")
                database.clear_database(conn)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(100)
                self.progress_bar.setFormat("Database wiped successfully")
            except Exception as e:
                self.on_error(f"Failed to wipe database: {e!s}")
            finally:
                if conn is not None:
                    conn.close()

    def on_cell_clicked(self, row: int, column: int) -> None:
        """Open the hidden URL when the user clicks the snippet cell."""
        snippet_column = 4

        if column == snippet_column:
            item: QTableWidgetItem | None = self.results_table.item(row, column)
            if item is not None:
                url = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(url, str) and url:
                    QDesktopServices.openUrl(url)

    def on_source_changed(self, text: str) -> None:
        """Update the Target ID placeholder based on the selected source."""
        if text == "Playlist":
            self.id_input.setPlaceholderText("ex. PLKDZ1ig0uz-U")
        else:
            self.id_input.setPlaceholderText("ex. @YouTube or UC7_YxT-KID8kRbqZo7MyscQ")

    def on_date_mode_toggled(self, checked: bool) -> None:
        """Enable or disable custom date pickers based on radio selection."""
        self.date_from.setEnabled(checked)
        self.date_to.setEnabled(checked)

    def text_changed(self, _: str = "") -> None:
        """Dynamically enable search button only if fields have text."""
        if self.abort_button.isEnabled():
            return

        has_target: bool = bool(self.id_input.text().strip())
        has_query: bool = bool(self.query_input.text().strip())
        self.search_button.setEnabled(has_target and has_query)

    def on_search_clicked(self) -> None:
        """Trigger search state and start the background worker."""
        source_type: str = self.source_combo.currentText()
        target_id: str = self.id_input.text().strip()
        query: str = self.query_input.text().strip()

        start_date: datetime.date | None = None
        end_date: datetime.date | None = None

        if self.date_custom_radio.isChecked():
            q_start: QDate = self.date_from.date()
            q_end: QDate = self.date_to.date()
            start_date = datetime.date(q_start.year(), q_start.month(), q_start.day())
            end_date = datetime.date(q_end.year(), q_end.month(), q_end.day())

        search_params: SearchParams = SearchParams(
            source_type=source_type,
            target_id=target_id,
            query=query,
            start_date=start_date,
            end_date=end_date,
            limit=100,
        )

        self.worker: SearchWorker = SearchWorker(
            db_path="transcripts.db",
            search=search_params,
            parent=self,
        )

        self.worker.results_found.connect(self.on_search_finished)
        self.worker.error.connect(self.on_error)
        self.worker.progress.connect(self.on_progress_update)
        self.worker.start()

        self.search_button.setEnabled(False)
        self.abort_button.setEnabled(True)

        self.progress_bar.setStyleSheet("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Fetching video metadata...")

    def on_search_finished(self, search_results: list[SearchResult]) -> None:
        """Handle worker completion and table population."""
        result_count: int = len(search_results)

        self.clear_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.search_button.setEnabled(True)
        self.progress_bar.setStyleSheet("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        if result_count == 0:
            self.progress_bar.setFormat("No results found")
            return

        self.progress_bar.setFormat(f"Found {result_count} results!")
        self.results_table.setSortingEnabled(False)
        self.results_table.setRowCount(0)
        self.results_table.setRowCount(result_count)

        for row, sr in enumerate(search_results):
            self.results_table.setItem(row, 0, QTableWidgetItem(sr.title))
            self.results_table.setItem(row, 1, QTableWidgetItem(sr.channel))
            self.results_table.setItem(row, 2, QTableWidgetItem(sr.upload_date))

            hours: float
            rem: float
            hours, rem = divmod(sr.start_time, 3600)

            minutes: float
            seconds: float
            minutes, seconds = divmod(rem, 60)
            time_str: str = (
                f"{int(hours)}:{int(minutes):02d}:{int(seconds):02d}"
                if hours > 0
                else f"{int(minutes):02d}:{int(seconds):02d}"
            )
            self.results_table.setItem(row, 3, QTableWidgetItem(time_str))

            safe_video_id: str = urllib.parse.quote(sr.video_id)
            youtube_url: str = f"https://youtu.be/{safe_video_id}?t={int(sr.start_time)}"

            snippet_item: QTableWidgetItem = QTableWidgetItem(sr.snippet)
            snippet_item.setData(Qt.ItemDataRole.UserRole, youtube_url)

            font: QFont = snippet_item.font()
            font.setUnderline(True)
            snippet_item.setFont(font)

            self.results_table.setItem(row, 4, snippet_item)

        self.results_table.resizeColumnsToContents()

        # restrict column widths to prevent massive titles or channel breaking layouts
        self.results_table.setColumnWidth(0, min(self.results_table.columnWidth(0), 200))
        self.results_table.setColumnWidth(1, min(self.results_table.columnWidth(1), 150))
        self.results_table.setSortingEnabled(True)

    def on_error(self, err_msg: str) -> None:
        """Handle worker errors."""
        self.search_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.progress_bar.setStyleSheet(QPROGRESS_ERROR_STYLESHEET)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(err_msg)

    def on_progress_update(self, current: int, total: int, msg: str) -> None:
        """Update the progress bar from the worker thread."""
        self.progress_bar.setStyleSheet("")
        if total > 0 and self.progress_bar.maximum() != total:
            self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(current)
        self.progress_bar.setFormat(msg)

    def on_abort_clicked(self) -> None:
        """Trigger abort state in UI (mock handler)."""
        if getattr(self, "worker", None) is not None:
            self.worker.cancel()
        self.search_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.progress_bar.setStyleSheet("")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat("Search aborted")

    def clear_results(self) -> None:
        """Clear all rows from the results table."""
        self.results_table.setRowCount(0)
        self.clear_button.setEnabled(False)
