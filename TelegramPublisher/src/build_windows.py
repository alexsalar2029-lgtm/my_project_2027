import os
import subprocess
import sys
from pathlib import Path

if os.name != "nt":
    raise SystemExit("Build on Windows x64")
args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
        "--name", "TelegramPublisher", "--collect-all", "filetype", "--collect-all", "tzdata",
        "--collect-all", "jdatetime", "--collect-all", "telethon", "--hidden-import", "socks",
        "--hidden-import", "selftest"]
redist = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Microsoft Visual Studio/2022/Enterprise/VC/Redist/MSVC"
crt = sorted(redist.glob("*/x64/Microsoft.VC143.CRT")) if redist.exists() else []
if crt:
    for dll in crt[-1].glob("*.dll"):
        args += ["--add-binary", str(dll) + ";."]
args.append("TelegramPublisher.pyw")
subprocess.run(args, check=True)
