import json
import os
import tempfile
from pathlib import Path

def main(report: Path):
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication
    from app import Window, STYLE
    import vault
    app = QApplication([])
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    app.setStyleSheet(STYLE)
    with tempfile.TemporaryDirectory() as temporary:
        data = Path(temporary)
        if os.name == "nt":
            vault.save(data / "auth.dat", {"test": "DPAPI roundtrip"})
            assert vault.load(data / "auth.dat")["test"] == "DPAPI roundtrip"
        window = Window(data)
        window.show()
        QTimer.singleShot(700, lambda: window.grab().save(str(report.with_suffix(".png"))))
        QTimer.singleShot(1200, window.close)
        QTimer.singleShot(15000, app.quit)
        app.exec()
        assert window.engine.wait(1000), "Worker did not shut down"
        report.write_text(json.dumps({"ok": True, "qt_loaded": True, "gui_opened": True,
                                      "worker_shutdown": True, "dpapi": os.name == "nt"}), "utf-8")
