import utils
import re
import tempfile
from pathlib import Path
from utils import log_error
from pytesseract import image_to_string
from PIL import Image

# Unterstützte Dateiendungen für Bild- und Dokumentverarbeitung
SUPPORTED_IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".webp"]
SUPPORTED_DOC_EXTS = [".md", ".pdf", ".docx", ".xlsx"]

# Gemeinsamer temporärer Bilderordner im systemweiten Temp-Pfad
TEMP_IMAGE_DIR = Path(tempfile.gettempdir()) / "tempimage"
TEMP_IMAGE_DIR.mkdir(parents=True, exist_ok=True)

def find_input_files(directory: Path) -> list:
    """
    Sucht rekursiv nach unterstützten Dateien im angegebenen Verzeichnis.
    """
    input_files: list[Path] = []
    try:
        for file in Path(directory).rglob("*"):
            ext = file.suffix.lower()
            if ext in SUPPORTED_IMAGE_EXTS or ext in SUPPORTED_DOC_EXTS:
                input_files.append(file)
                utils.debug_log(f"Datei gefunden: {file}")
        if not input_files:
            utils.debug_log(f"Keine unterstützten Dateien im Verzeichnis gefunden: {directory}")
        return input_files
    except Exception as e:
        utils.log_error(
            f"Fehler beim Durchsuchen des Verzeichnisses: {e}",
            context={"directory": str(directory)},
        )
        return []

def standardize_formatting(doc_path, output_path):
    """
    Standardisiert die Formatierung eines Word-Dokuments:
    - Vereinheitlicht Überschriften.
    - Entfernt doppelte Leerzeilen.
    - Markiert unvollständige Inhalte.
    """
    from docx import Document
    doc = Document(doc_path)
    header_regex = re.compile(r"^(#+)\s*(.*)")  # Markdown-Style Überschriften
    placeholder_regex = re.compile(r"___|\(Hier.*?\)|\[.*?\]")  # Platzhalter erkennen

    for paragraph in doc.paragraphs:
        match = header_regex.match(paragraph.text)
        if match:
            level = len(match.group(1))
            paragraph.text = match.group(2).strip()
            paragraph.style = f"Heading {min(level, 3)}"
        if placeholder_regex.search(paragraph.text):
            paragraph.text = f"[UNVOLLSTÄNDIG] {paragraph.text}"
        if not paragraph.text.strip():
            paragraph.clear()
    doc.save(output_path)
    utils.debug_log(f"Formatierung abgeschlossen und gespeichert: {output_path}")

def clean_text(text: str) -> str:
    """
    Bereinigt den Text:
    - Entfernt Dateiendungen (.md)
    - Entfernt Verlinkungen wie [[Maho#^xyz|Text]] und behält nur den Text.
    - Entfernt NULL-Bytes und nicht-druckbare Steuerzeichen.
    - Loggt und entfernt eingebettete Base64-Bilder.
    """
    text = re.sub(r"\.md", "", text)
    text = re.sub(r"\[\[.*?\|(.*?)\]\]", r"\1", text)
    text = re.sub(r"\[\[.*?\]\]", "", text)
    text = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", text)
    base64_pattern = re.compile(r"!\[\]\(data:image\/[^\)]+\)")
    for match in base64_pattern.findall(text):
        utils.log_missing_image(match)
    text = base64_pattern.sub("", text)
    return text.strip()

def check_image_for_text(image_path) -> bool:
    """
    Prüft, ob ein Bild Text enthält, indem OCR verwendet wird.
    """
    try:
        text = image_to_string(Image.open(image_path))
        return bool(text.strip())
    except Exception as e:
        print(f"Fehler bei der Texterkennung: {e}")
        return False

def extract_image_references(text: str, base_directory: Path) -> list:
    """
    Extrahiert Bildreferenzen aus einem Text und prüft, ob die Bilder existieren.
    """
    image_references = re.findall(r"!\[\[(.*?)\]\]", text)
    valid_images: list[Path] = []
    for image_ref in image_references:
        try:
            image_path = Path(base_directory) / image_ref
            if image_path.exists():
                valid_images.append(image_path)
            else:
                log_error(f"Bilddatei fehlt: {image_path}")
        except Exception as e:
            log_error(f"Fehler bei der Verarbeitung der Bildreferenz '{image_ref}': {e}")
    return valid_images

def cleanup_temp_images(base_temp_dir: Path | str | None = None) -> None:
    """
    Löscht alle temporären Bilder aus dem angegebenen Ordner.
    """
    dir_path = Path(base_temp_dir) if base_temp_dir else TEMP_IMAGE_DIR
    if dir_path.is_dir():
        for temp_image_path in dir_path.glob("*"):
            try:
                if temp_image_path.is_file():
                    temp_image_path.unlink()
                    utils.debug_log(f"Temporäre Bilddatei gelöscht: {temp_image_path}")
            except Exception as e:
                utils.log_error(f"Fehler beim Löschen von Bild {temp_image_path}: {e}")
    else:
        utils.debug_log(f"Ordner für temporäre Bilder nicht gefunden: {dir_path}")
