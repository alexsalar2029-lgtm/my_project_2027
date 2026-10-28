"""Local queue, file inspection and scheduling. No Telegram side effects here."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import sqlite3
import time
import unicodedata
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

KINDS = {"photo": "تصویر", "video": "ویدئو", "audio": "صوت", "document": "سند / فایل"}
STATES = {"queued": "در صف", "sending": "در حال ارسال", "sent": "ارسال شد",
          "failed": "خطا؛ نیاز به بررسی", "uncertain": "نتیجه نامشخص؛ تلگرام را بررسی کنید", "skipped": "کنار گذاشته شد"}
DEFAULTS = {"folder": "", "recursive": False, "interval": 10, "start": "00:00", "end": "00:00",
            "days": list(range(7)), "timezone": "Asia/Tehran", "template": "{title}\n{type} • {size}",
            "prefix": "", "auto_scan": True, "not_before": "", "api_id": "", "target": "me",
            "version": 2, "calendar": "jalali", "window_enabled": False, "as_document": False}


def utf16_trim(text: str, limit: int = 1000) -> str:
    return text.encode("utf-16-le")[:limit * 2].decode("utf-16-le", errors="ignore")


def human_size(size: int) -> str:
    for suffix in ("B", "KB", "MB", "GB"):
        if size < 1024 or suffix == "GB":
            return f"{size:.1f} {suffix}"
        size /= 1024


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def clean_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", str(value))
    value = "".join(c for c in value if not unicodedata.category(c).startswith("C"))
    value = re.sub(r"[_.]+", " ", value)
    value = re.sub(r"(?i)\b(?:1080p|720p|2160p|480p|x264|x265|h264|h265|webrip|bluray)\b", "", value)
    return re.sub(r"\s+", " ", value).strip(" -")[:240]


def inspect_file(path: Path) -> dict:
    import filetype
    guessed = filetype.guess(str(path))
    mime = guessed.mime if guessed else (mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    kind = "document"
    if mime.startswith("image/") and mime != "image/gif":
        kind = "photo"
    elif mime == "image/gif":
        kind = "video"
    elif mime.startswith("video/"):
        kind = "video"
    elif mime.startswith("audio/"):
        kind = "audio"
    title = ""
    # Metadata only: no remote AI service and no contents leave the computer here.
    try:
        if mime == "application/pdf":
            from pypdf import PdfReader
            with path.open("rb") as f:
                reader = PdfReader(f, strict=False)
                if not reader.is_encrypted and reader.metadata:
                    title = clean_title(reader.metadata.title or "")
        elif kind == "audio":
            from mutagen import File
            audio = File(str(path), easy=True)
            if audio:
                title = clean_title(" — ".join(filter(None, [
                    (audio.get("artist") or [""])[0], (audio.get("title") or [""])[0]])))
    except Exception:
        pass  # Malformed metadata must not stop the rest of the queue.
    title = title or clean_title(path.stem) or "فایل بدون عنوان"
    return {"title": title, "kind": kind, "mime": mime}


def caption(row: dict, config: dict) -> str:
    # A fixed list of replacements makes braces in file names safe and literal.
    result = config.get("template", DEFAULTS["template"])
    values = {"title": row["title"], "type": KINDS[row["kind"]], "size": human_size(row["size"]),
              "filename": Path(row["path"]).name, "prefix": config.get("prefix", "")}
    return utf16_trim(re.sub(r"\{(title|type|size|filename|prefix)\}", lambda m: values[m[1]], result))


def allowed_at(now: datetime, config: dict) -> bool:
    local = now.astimezone(ZoneInfo(config.get("timezone", "Asia/Tehran")))
    if config.get("not_before"):
        earliest = datetime.fromisoformat(config["not_before"])
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=ZoneInfo(config["timezone"]))
        if now < earliest:
            return False
    start = tuple(map(int, config["start"].split(":")))
    end = tuple(map(int, config["end"].split(":")))
    clock = (local.hour, local.minute)
    day = local.weekday()
    if start == end:
        return day in config["days"]  # Explicit all-day mode.
    if start < end:
        return day in config["days"] and start <= clock < end
    # Overnight window belongs to the day on which it starts.
    return (day in config["days"] and clock >= start) or (
        (local - timedelta(days=1)).weekday() in config["days"] and clock < end)


def next_due(now: datetime, config: dict, minimum: float = 0) -> datetime | None:
    """Return the next permitted UTC instant, including overnight and start-date rules."""
    from datetime import timezone
    zone = ZoneInfo(config.get("timezone", "Asia/Tehran"))
    candidate = max(now.astimezone(timezone.utc), datetime.fromtimestamp(minimum, timezone.utc))
    if config.get("not_before"):
        earliest = datetime.fromisoformat(config["not_before"])
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=zone)
        candidate = max(candidate, earliest.astimezone(timezone.utc))
    sh, sm = map(int, config["start"].split(":"))
    eh, em = map(int, config["end"].split(":"))
    if (sh, sm) == (eh, em):
        sh = sm = eh = em = 0
    for offset in range(-1, 9):
        day = candidate.astimezone(zone).date() + timedelta(days=offset)
        if day.weekday() not in config["days"]:
            continue
        beginning = datetime(day.year, day.month, day.day, sh, sm, tzinfo=zone)
        ending = datetime(day.year, day.month, day.day, eh, em, tzinfo=zone)
        if (sh, sm) >= (eh, em):
            ending += timedelta(days=1)
        beginning, ending = beginning.astimezone(timezone.utc), ending.astimezone(timezone.utc)
        if candidate < ending:
            return max(candidate, beginning)
    return None


class Store:
    def __init__(self, path: Path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs(
              id INTEGER PRIMARY KEY, scope TEXT NOT NULL, hash TEXT NOT NULL,
              path TEXT NOT NULL, size INTEGER NOT NULL, mtime INTEGER NOT NULL,
              title TEXT NOT NULL, kind TEXT NOT NULL, mime TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'queued', error TEXT DEFAULT '',
              message_id INTEGER, sent_at REAL, created REAL NOT NULL,
              UNIQUE(scope,hash));
            CREATE TABLE IF NOT EXISTS state(key TEXT PRIMARY KEY, value TEXT);
            """)
            # An interrupted in-flight request must never be blindly resent.
            db.execute("UPDATE jobs SET status='uncertain', error=? WHERE status='sending'",
                       ("برنامه هنگام ارسال بسته شده؛ مقصد را بررسی و وضعیت را تعیین کنید.",))

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def rows(self, scope: str) -> list[dict]:
        with self.connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE scope=? ORDER BY id", (scope,))]

    def enqueue(self, scope: str, path: Path, info: dict, hash_: str, stat) -> bool:
        with self.connect() as db:
            if not scope.startswith("preview:"):
                staged = db.execute("SELECT title FROM jobs WHERE hash=? AND scope LIKE 'preview:%' ORDER BY id DESC LIMIT 1", (hash_,)).fetchone()
                if staged:
                    info = {**info, "title": staged["title"]}
            c = db.execute("""INSERT OR IGNORE INTO jobs
              (scope,hash,path,size,mtime,title,kind,mime,created) VALUES(?,?,?,?,?,?,?,?,?)""",
              (scope, hash_, str(path), stat.st_size, stat.st_mtime_ns,
               info["title"], info["kind"], info["mime"], time.time()))
            # If an unsent duplicate moved, keep the current usable path and edited title.
            if c.rowcount == 0:
                db.execute("UPDATE jobs SET path=?,size=?,mtime=? WHERE scope=? AND hash=? AND status='queued'",
                           (str(path), stat.st_size, stat.st_mtime_ns, scope, hash_))
            return c.rowcount > 0

    def update(self, id_: int, **fields):
        if not fields or not set(fields) <= {"status", "error", "message_id", "sent_at", "title"}:
            raise ValueError("invalid fields")
        with self.connect() as db:
            db.execute("UPDATE jobs SET " + ",".join(k + "=?" for k in fields) + " WHERE id=?",
                       (*fields.values(), id_))

    def state(self, key: str, default: str = "") -> str:
        with self.connect() as db:
            row = db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            return row[0] if row else default

    def set_state(self, key: str, value: str):
        with self.connect() as db:
            db.execute("INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


class Scanner:
    def __init__(self, store: Store):
        self.store = store
        self.seen = {}
        self.cached = {}
        self.last_report = {}

    def scan(self, config: dict, scope: str) -> int:
        root = Path(config["folder"]).resolve()
        if not root.is_dir():
            raise ValueError("پوشهٔ انتخاب‌شده در دسترس نیست.")
        paths = root.rglob("*") if config.get("recursive") else root.glob("*")
        count = 0
        report = {"found": 0, "waiting": 0, "duplicates": 0, "ignored": 0, "errors": []}
        for path in sorted(paths):
            if path.is_symlink() or not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() in {".part", ".tmp", ".crdownload", ".download", ".session", ".journal"}:
                continue
            # Never post this app's own auth, configuration, database or cache.
            if path.resolve().is_relative_to(self.store.path.parent.resolve()):
                continue
            try:
                report["found"] += 1
                stat = path.stat()
                signature = (stat.st_size, stat.st_mtime_ns)
                previous, since = self.seen.get(str(path), (None, time.monotonic()))
                if previous != signature:
                    self.seen[str(path)] = (signature, time.monotonic())
                    report["waiting"] += 1
                    continue
                if time.monotonic() - since < 2 or time.time() - stat.st_mtime < 2:
                    report["waiting"] += 1
                    continue
                if not stat.st_size:
                    report["ignored"] += 1
                    continue
                cache_key = (scope, str(path), signature)
                if cache_key in self.cached:
                    report["duplicates"] += 1
                    continue
                hash_ = digest(path)
                after = path.stat()
                if signature != (after.st_size, after.st_mtime_ns):
                    continue
                info = inspect_file(path)
                count += self.store.enqueue(scope, path.resolve(), info, hash_, stat)
                self.cached[cache_key] = True
            except (OSError, ValueError) as exc:
                report["errors"].append(path.name + ': ' + type(exc).__name__)
                continue
        report["added"] = count
        self.last_report = report
        return count


def load_config(path: Path) -> dict:
    config = {**DEFAULTS, "days": list(DEFAULTS["days"])}
    try:
        config.update(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError):
        pass
    return config


def save_config(path: Path, config: dict):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(config, ensure_ascii=False, indent=2), "utf-8")
    temp.replace(path)
