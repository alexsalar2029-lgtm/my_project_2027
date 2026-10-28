"""Graphical first-run installer. Standard Windows Python (with Tk) is required."""
import hashlib
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = Path(__file__).resolve().parent
BASE = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TelegramFolderPublisher"
ENV = BASE / "runtime"
PYTHON = ENV / "Scripts" / "pythonw.exe"
CONSOLE = ENV / "Scripts" / "python.exe"
MARKER = ENV / "installed.sha256"
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def main():
    if os.name != "nt":
        raise SystemExit("This launcher is for Windows; use python app.py on other systems.")
    window = tk.Tk()
    window.title("Telegram Publisher | راه‌اندازی")
    window.geometry("640x400")
    window.configure(bg="#f3f6fa")
    window.resizable(False, False)
    style = ttk.Style(window)
    style.theme_use("clam")
    frame = ttk.Frame(window, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="تلگرام‌یار", font=("Segoe UI", 24, "bold")).pack(anchor="e")
    label = ttk.Label(frame, text="راه‌اندازی اولیه به اینترنت نیاز دارد. نصب ممکن است چند دقیقه طول بکشد.",
                      wraplength=580, justify="right", font=("Segoe UI", 11))
    label.pack(fill="x", pady=16)
    progress = ttk.Progressbar(frame, mode="indeterminate")
    progress.pack(fill="x", pady=10)
    details = tk.Text(frame, height=8, font=("Consolas", 8), state="disabled")
    details.pack(fill="both", expand=True)
    events = queue.Queue()
    running = [False]
    requirements = ROOT / "requirements.txt"
    checksum = hashlib.sha256(requirements.read_bytes()).hexdigest()

    def launch():
        subprocess.Popen([str(PYTHON), str(ROOT / "TelegramPublisher.pyw")], cwd=ROOT, creationflags=FLAGS)
        window.destroy()

    def execute(args):
        with subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, encoding="utf-8", errors="replace", creationflags=FLAGS) as process:
            for line in process.stdout:
                events.put(("line", line.rstrip()))
            if process.wait():
                raise RuntimeError("نصب کامل نشد؛ اینترنت و دسترسی به pypi.org را بررسی و دوباره تلاش کنید.")

    def install():
        try:
            BASE.mkdir(parents=True, exist_ok=True)
            original = Path(sys._base_executable)
            if original.name.lower() == "pythonw.exe":
                original = original.with_name("python.exe")
            if not CONSOLE.exists():
                execute([str(original), "-m", "venv", str(ENV)])
            execute([str(CONSOLE), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(requirements)])
            MARKER.write_text(checksum, "ascii")
            events.put(("done", ""))
        except Exception as error:
            events.put(("error", str(error)))

    def start():
        if running[0]:
            return
        running[0] = True
        action.configure(state="disabled")
        label.configure(text="در حال نصب کتابخانه‌ها… لطفاً این پنجره را باز نگه دارید.")
        progress.start(12)
        threading.Thread(target=install, daemon=True).start()

    def tick():
        try:
            while True:
                kind, text = events.get_nowait()
                if kind == "line":
                    details.configure(state="normal")
                    details.insert("end", text + "\n")
                    details.see("end")
                    details.configure(state="disabled")
                elif kind == "error":
                    progress.stop()
                    running[0] = False
                    action.configure(state="normal", text="تلاش دوباره")
                    label.configure(text="نصب کامل نشد.")
                    messagebox.showerror("راه‌اندازی", text)
                elif kind == "done":
                    launch()
                    return
        except queue.Empty:
            pass
        window.after(100, tick)

    action = ttk.Button(frame, text="نصب و اجرای برنامه", command=start)
    action.pack(pady=(15, 0), fill="x")
    def close():
        if running[0]:
            messagebox.showinfo("نصب", "لطفاً تا پایان نصب صبر کنید.")
        else:
            window.destroy()
    window.protocol("WM_DELETE_WINDOW", close)
    if sys.version_info < (3, 10):
        messagebox.showerror("Python", "Python 3.10 یا جدیدتر لازم است. Python 3.12 پیشنهاد می‌شود.")
        window.destroy()
        return
    if PYTHON.exists() and MARKER.exists() and MARKER.read_text("ascii") == checksum:
        launch()
        return
    window.after(100, tick)
    window.mainloop()


if __name__ == "__main__":
    main()
