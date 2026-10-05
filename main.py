import sys

from PySide6.QtWidgets import QApplication

from main_window import MainWindow

if __name__ == "__main__":
    app: QApplication = QApplication(sys.argv)
    window: MainWindow = MainWindow()
    window.show()
    sys.exit(app.exec())
