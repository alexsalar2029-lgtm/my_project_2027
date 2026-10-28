"""Install private DLL search paths before importing Qt."""
import os
import sys
import traceback
from pathlib import Path

_dll_handles = []
if os.name == "nt" and getattr(sys, "frozen", False):
    base = Path(sys._MEIPASS)
    for directory in [base, base / "PySide6", base / "PySide6" / "Qt" / "bin"]:
        if directory.is_dir():
            _dll_handles.append(os.add_dll_directory(str(directory)))
try:
    if "--self-test" in sys.argv:
        from selftest import main
        main(Path(sys.argv[sys.argv.index("--self-test") + 1]))
    else:
        from app import main
        main()
except Exception:
    target = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TelegramFolderPublisher" / "startup-error.log"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(traceback.format_exc(), "utf-8")
    if os.name == "nt" and "--self-test" not in sys.argv:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, "Startup failed. Details saved to:\n" + str(target), "Telegram Publisher", 16)
    raise SystemExit(1)
