import tkinter as tk
import asyncio
import tempfile
import utils
from tkinter import filedialog, messagebox, ttk
from file_processing_text import extract_text_from_excel, extract_text_from_markdown
from file_processing_images import (
    extract_images_from_image,
    process_images_in_folder,      # ← Diese Zeile muss vorhanden sein!
    extract_text_and_images_from_pdf
)
from file_processing_utils import find_input_files, standardize_formatting, cleanup_temp_images
from saving import write_to_word
from pathlib import Path
from utils import debug_log, log_error
from threading import Thread

def create_gui():
    global BASE_DIR
    BASE_DIR = Path(tempfile.gettempdir()) / "file_converter"

    utils.debug_log("GUI gestartet und Log initialisiert.")
    utils.debug_log(f"Log-Datei: {utils.log_file_path}")

    root = tk.Tk()
    root.title("Dateikonverter")
    root.geometry("500x300")

    label = tk.Label(root, text="Willkommen beim Datei-Konverter!", font=("Arial", 16))
    label.pack(pady=20)

    start_button = tk.Button(root, text="Starten", command=lambda: start_conversion_threaded(root), font=("Arial", 12))
    start_button.pack(pady=10)

    info_label = tk.Label(root, text=f"Log-Dateien werden gespeichert in: {utils.log_file_path}", font=("Arial", 10))
    info_label.pack(pady=10)

    root.mainloop()

def choose_target_directory():
    target_dir = filedialog.askdirectory(title="Zielordner auswählen")
    if not target_dir:
        messagebox.showerror("Fehler", "Kein Zielordner ausgewählt.")
        return None
    return target_dir

def start_conversion_threaded(root):
    thread = Thread(target=start_conversion, args=(root,))
    thread.start()

def start_conversion(root):
    target_dir = choose_target_directory()
    if not target_dir:
        return

    save_path = filedialog.asksaveasfilename(
        title="Speicherort auswählen",
        filetypes=[("Word-Datei", "*.docx"), ("PDF-Datei", "*.pdf")],
        defaultextension=".docx"
    )
    if not save_path:
        messagebox.showerror("Fehler", "Kein Speicherort ausgewählt.")
        return

    input_files = find_input_files(Path(target_dir))
    if not input_files:
        messagebox.showinfo("Information", "Keine passenden Dateien gefunden.")
        return

    progress_window = tk.Toplevel(root)
    progress_window.title("Verarbeitung läuft")
    progress_window.geometry("400x120")

    progress_label = tk.Label(progress_window, text="Verarbeitung startet...")
    progress_label.pack(pady=5)

    progress_bar = ttk.Progressbar(progress_window, length=300, mode='determinate')
    progress_bar.pack(pady=5)

    pdf_progress_label = tk.Label(progress_window, text="")
    pdf_progress_label.pack(pady=5)

    asyncio.run(
        process_files_async(
            input_files,
            Path(save_path),
            progress_label,
            progress_bar,
            pdf_progress_label,
            progress_window,
            root
        )
    )

def process_images_from_folder():
    folder_path = filedialog.askdirectory(title="Ordner mit Bildern auswählen")
    if not folder_path:
        messagebox.showinfo("Abbruch", "Kein Ordner ausgewählt.")
        return

    output_docx_path = filedialog.asksaveasfilename(
        title="Speichern als",
        defaultextension=".docx",
        filetypes=[("Word-Dokument", "*.docx")]
    )
    if not output_docx_path:
        messagebox.showinfo("Abbruch", "Kein Speicherort ausgewählt.")
        return

    try:
        process_images_in_folder(folder_path, output_docx_path)
        messagebox.showinfo("Erfolg", f"Die Bilder wurden erfolgreich in {output_docx_path} gespeichert.")
    except Exception as e:
        messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}")

async def process_files_async(
    input_files,
    save_path,
    progress_label,
    progress_bar,
    pdf_progress_label,
    progress_window,
    root
):
    contents = []
    total_files = len(input_files)

    try:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def process_file_sync(file_path: Path):
            temp_dir = Path(tempfile.gettempdir())
            processed_content = {"text": "", "images": []}
            try:
                suffix = file_path.suffix.lower()
                if suffix == ".docx":
                    formatted_file = temp_dir / f"{file_path.stem}_formatted.docx"
                    standardize_formatting(file_path, formatted_file)
                    processed_content["text"] = formatted_file.read_text(encoding="utf-8", errors="replace")
                elif suffix == ".pdf":
                    pdf_result = extract_text_and_images_from_pdf(file_path, 100, True)
                    processed_content["text"] = pdf_result.get("text", "")
                    processed_content["images"] = pdf_result.get("images", [])
                elif suffix in [".png", ".jpg", ".jpeg", ".webp"]:
                    processed_content = extract_images_from_image(file_path)
                elif suffix == ".xlsx":
                    processed_content["text"] = extract_text_from_excel(file_path)
                elif suffix == ".md":
                    processed_content["text"] = extract_text_from_markdown(file_path)
            except Exception as e:
                log_error(f"Fehler bei der Verarbeitung von Datei {file_path}: {e}")
            return file_path, processed_content

        def update_progress_gui(completed: int, total: int, percent: int):
            progress_label.config(text=f"Verarbeite Datei {completed} von {total}...")
            progress_bar["value"] = percent
            progress_label.update_idletasks()
            progress_bar.update_idletasks()

        contents = []
        completed_files = 0

        with ThreadPoolExecutor() as executor:
            future_to_file = {executor.submit(process_file_sync, f): f for f in input_files}
            for future in as_completed(future_to_file):
                file_path, processed_content = future.result()
                if processed_content:
                    contents.append((file_path, processed_content))
                completed_files += 1
                percent = int((completed_files / total_files) * 100)
                root.after(0, update_progress_gui, completed_files, total_files, percent)

        if contents:
            # Zeige an, dass jetzt die Datei erstellt wird
            root.after(0, update_progress_gui, total_files, total_files, 100)
            root.after(0, lambda: progress_label.config(text="Speichere Word-Datei... Bitte warten."))
            await asyncio.to_thread(write_to_word, contents, save_path, Path(tempfile.gettempdir()))
            root.after(0, lambda: messagebox.showinfo("Erfolg", f"Datei erfolgreich gespeichert: {save_path}"))
        else:
            root.after(0, lambda: messagebox.showwarning("Warnung", "Keine Inhalte zum Speichern gefunden."))
    except Exception as e:
        log_error(f"Fehler während der Verarbeitung: {e}")
        root.after(0, lambda: messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {e}"))
    finally:
        root.after(0, progress_bar.stop)
        root.after(0, progress_window.destroy)
        cleanup_temp_images()

def update_pdf_progress(pdf_progress_label, file, current_page, total_pages_in_pdf):
    pdf_progress_label.config(text=f"PDF {file.name}: Seite {current_page} von {total_pages_in_pdf}")
    pdf_progress_label.update_idletasks()
