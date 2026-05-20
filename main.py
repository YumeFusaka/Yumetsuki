import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from config.manager import ConfigManager
from ui.chat.window import ChatWindow


def main():
    app = QApplication(sys.argv)

    config = ConfigManager()

    # Find first character directory
    char_dir = None
    characters_path = Path(__file__).parent / "data" / "characters"
    if characters_path.is_dir():
        for d in characters_path.iterdir():
            if d.is_dir() and (d / "prompt.md").exists():
                char_dir = d
                break

    window = ChatWindow(config.api.llm, character_dir=char_dir)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
