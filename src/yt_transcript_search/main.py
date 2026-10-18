import logging
import sys

from PySide6.QtWidgets import QApplication

from yt_transcript_search.main_window import MainWindow

if __name__ == "__main__":
    logging.basicConfig(
        filename="error.log",
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app: QApplication = QApplication(sys.argv)
    window: MainWindow = MainWindow()
    window.show()
    sys.exit(app.exec())
