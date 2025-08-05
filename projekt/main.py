# main.py
import sys
import os

from gui import create_gui
import utils

# Sicherstellen, dass das Projektverzeichnis im sys.path liegt (falls nötig)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def main():
    """
    Hauptfunktion des Programms.
    - Legt den Logpfad fest (über Umgebungsvariable oder Standardordner)
    - Initialisiert die Logdatei
    - Rüstet Poppler und Tesseract nach
    - Startet die GUI
    """
    from pathlib import Path

    default_log_dir = Path.home() / "file_converter_logs"
    logs_dir = Path(os.environ.get("LOG_DIR", default_log_dir)).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    utils.log_file_path = str(logs_dir / "app_log.txt")

    utils.initialize_log()
    utils.debug_log("Test-Logeintrag: Logging funktioniert (main.py)")

    utils.setup_paths()

    create_gui()

if __name__ == "__main__":
    main()
