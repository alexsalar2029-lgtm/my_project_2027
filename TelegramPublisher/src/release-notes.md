Windows x64 single-file EXE. No Python installation required.

- Bundled Qt and Visual C++ runtime libraries; explicit private DLL search paths.
- Offline folder detection and editable post preview before Telegram login.
- Telegram media routing based on detected content, including misleading file extensions.
- Immediate selected-file sending and a separate send-to-Saved-Messages test action.
- Jalali/Gregorian date selection, Tehran timezone, UTC persistence and next-publication preview.
- Reworked publishing dashboard, visible scan status and error banner.

Build validation: Windows Python tests plus execution of the actual EXE to verify Qt, GUI startup, worker shutdown and Windows DPAPI.
Telegram transport tests use a simulated service. Live account authentication and delivery require local login in the app.
