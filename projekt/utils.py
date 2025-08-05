import time
import os
from pathlib import Path
from threading import Lock

log_lock = Lock()
log_initialized = False
log_file_path = None
app_log_path = None

def initialize_log():
    """
    Legt die Logdatei neu an. Dabei wird app_log_path immer auf log_file_path gesetzt,
    sodass alle Fehler- und Debug-Ausgaben ins gleiche Log geschrieben werden.
    """
    global log_file_path, app_log_path
    if not log_file_path:
        print("Fehler: Kein log_file_path definiert!")
        return

    log_path_obj = Path(log_file_path)
    log_path_obj.parent.mkdir(parents=True, exist_ok=True)

    if log_path_obj.exists():
        log_path_obj.unlink()

    with log_path_obj.open(mode='w', encoding='utf-8') as f:
        f.write("Processing Error Log\n=====================\n")

    app_log_path = log_file_path
    debug_log("Log initialisiert!")

def debug_log(msg):
    global log_file_path
    try:
        if not log_file_path:
            print("Fehler: Kein log_file_path definiert!")
            return
        with open(log_file_path, "a", encoding="utf-8") as f:
            f.write(f"[DEBUG] {msg}\n")
    except Exception as e:
        print(f"Fehler beim Schreiben in debug_log: {e}")

def log_error(message, context=None):
    """
    Loggt Fehlermeldungen in die Logdatei.  Es wird entweder ``app_log_path``
    oder – falls dieser nicht gesetzt ist – ``log_file_path`` verwendet.
    """
    try:
        target_path = app_log_path if app_log_path else log_file_path
        if not target_path:
            print("Fehler: Kein Logpfad definiert!")
            return

        with log_lock:
            sanitized_message = sanitize_text_line(message)
            if context and isinstance(context, dict) and 'file_path' in context:
                sanitized_message += f" | Datei: {os.path.basename(context['file_path'])}"
            with open(target_path, "a", encoding="utf-8") as log_file:
                log_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')} ERROR] {sanitized_message}"
                log_file.write(log_message + "\n")
                log_file.flush()
    except Exception as e:
        print(f"Fehler beim Schreiben in log_error: {e}")

def sanitize_text_line(line):
    """
    Bereinigt eine Textzeile, um nicht druckbare Zeichen zu entfernen und die Länge zu begrenzen.
    """
    valid_chars = [ch for ch in line if ch.isprintable() or ch in ['\n', '\t', ' ']]
    sanitized = ''.join(valid_chars)
    return sanitized[:500] + "..." if len(sanitized) > 500 else sanitized

def find_executable(executable_name, search_dirs):
    """
    Sucht rekursiv nach einer ausführbaren Datei in den angegebenen Verzeichnissen.
    """
    for directory in search_dirs:
        for root, dirs, files in os.walk(directory):
            if executable_name in files:
                return os.path.join(root, executable_name)
    return None

def log_missing_image(image_identifier):
    """
    Loggt fehlende oder nicht verarbeitbare Bilder. Verwendet denselben Pfad wie log_error.
    """
    target_path = app_log_path if app_log_path else log_file_path
    if not target_path:
        return
    try:
        with open(target_path, "a", encoding="utf-8") as log_file:
            log_message = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Fehlendes Bild gefunden: {image_identifier}"
            log_file.write(log_message + "\n")
            log_file.flush()
    except Exception:
        pass

def setup_paths():
    """
    Findet Poppler und Tesseract und setzt ihre Pfade, falls nicht in PATH.
    """
    common_dirs = [
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\",
        "D:\\"
    ]
    poppler_path = find_executable("pdftoppm.exe", common_dirs)
    if poppler_path:
        os.environ["PATH"] += os.pathsep + os.path.dirname(poppler_path)
    else:
        log_error("Poppler nicht gefunden. Bitte installieren oder manuell hinzufügen.")

    tesseract_path = find_executable("tesseract.exe", common_dirs)
    if tesseract_path:
        os.environ["PATH"] += os.pathsep + os.path.dirname(tesseract_path)
    else:
        log_error("Tesseract nicht gefunden. Bitte installieren oder manuell hinzufügen.")

def run_with_timeout(func, *args, timeout=120, **kwargs):
    """
    Führt eine Funktion in einem separaten Thread mit Timeout aus.
    """
    import queue
    from threading import Thread

    q = queue.Queue()

    def wrapper():
        try:
            result = func(*args, **kwargs)
            q.put(result)
        except Exception as e:
            q.put(e)

    t = Thread(target=wrapper, daemon=True)
    t.start()

    try:
        result = q.get(timeout=timeout)
        if isinstance(result, Exception):
            log_error(f"Fehler in Funktion {func.__name__}: {result}")
            raise result
        return result
    except queue.Empty:
        log_error(f"Timeout bei Funktion: {func.__name__} mit Argumenten: {args}")
        return None
