import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from ui.settings.window import SettingsWindow


def main():
    app = QApplication(sys.argv)
    window = SettingsWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
