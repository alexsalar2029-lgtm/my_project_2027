"""Windows DPAPI: API hash and Telegram session are bound to the Windows user."""
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def crypt(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("ذخیرهٔ امن ورود در این نسخه فقط در ویندوز پشتیبانی می‌شود.")
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buf)
    target = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    name = "CryptUnprotectData" if decrypt else "CryptProtectData"
    fn = getattr(library, name)
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL
    if not fn(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


def save(path: Path, value: dict):
    payload = crypt(json.dumps(value).encode("utf-8"))
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def load(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(crypt(path.read_bytes(), decrypt=True).decode("utf-8"))
