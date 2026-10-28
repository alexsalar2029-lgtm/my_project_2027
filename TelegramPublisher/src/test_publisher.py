import asyncio
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from core import DEFAULTS, Scanner, Store, allowed_at, caption, clean_title, digest, inspect_file, utf16_trim
from engine import Engine
from telethon import errors
from telethon.tl.types import InputFile


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / "data"
        self.source = self.root / "source"
        self.data.mkdir()
        self.source.mkdir()
        self.store = Store(self.data / "queue.db")
        self.path = self.source / "lesson_01.txt"
        self.path.write_bytes(b"hello sample content")
        self.info = {"title": "درس اول", "kind": "document", "mime": "application/pdf"}
        self.config = {**DEFAULTS, "folder": str(self.source), "timezone": "UTC", "start": "00:00", "end": "00:00"}

    def tearDown(self):
        self.temp.cleanup()

    def add(self, scope="1:1"):
        return self.store.enqueue(scope, self.path, self.info, digest(self.path), self.path.stat())

    def test_duplicate_content_is_scoped_by_account_and_destination(self):
        self.assertTrue(self.add())
        self.assertFalse(self.add())
        self.assertTrue(self.add("1:2"))
        self.assertEqual(len(self.store.rows("1:1")), 1)

    def test_restart_never_requeues_inflight_delivery(self):
        self.add()
        self.store.update(1, status="sending")
        reopened = Store(self.data / "queue.db")
        self.assertEqual(reopened.rows("1:1")[0]["status"], "uncertain")

    def test_sent_file_is_not_requeued_on_scan(self):
        self.add()
        self.store.update(1, status="sent")
        self.assertFalse(self.add())
        self.assertEqual(self.store.rows("1:1")[0]["status"], "sent")

    def test_edit_survives_rescan(self):
        self.add()
        self.store.update(1, title="عنوان انتخابی")
        self.add()
        self.assertEqual(self.store.rows("1:1")[0]["title"], "عنوان انتخابی")

    def test_scanner_waits_for_stable_copy(self):
        scanner = Scanner(self.store)
        with patch("core.time.monotonic", return_value=100), patch("core.time.time", return_value=time.time() + 100):
            self.assertEqual(scanner.scan(self.config, "1:1"), 0)
        self.path.write_bytes(b"new content")
        with patch("core.time.monotonic", return_value=120), patch("core.time.time", return_value=time.time() + 100):
            self.assertEqual(scanner.scan(self.config, "1:1"), 0)
        with patch("core.time.monotonic", return_value=140), patch("core.time.time", return_value=time.time() + 100):
            self.assertEqual(scanner.scan(self.config, "1:1"), 1)

    def test_scanner_never_includes_own_credentials(self):
        (self.data / "auth.dat").write_bytes(b"secret")
        scanner = Scanner(self.store)
        config = {**self.config, "folder": str(self.data)}
        with patch("core.time.monotonic", return_value=100):
            scanner.scan(config, "1:1")
        with patch("core.time.monotonic", return_value=140):
            self.assertEqual(scanner.scan(config, "1:1"), 0)
        self.assertEqual(self.store.rows("1:1"), [])

    def test_signature_wins_over_wrong_extension(self):
        path = self.source / "image.bin"
        path.write_bytes(bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 64)
        self.assertEqual(inspect_file(path)["kind"], "photo")
        self.assertEqual(inspect_file(path)["mime"], "image/png")

    def test_title_cleaning_preserves_persian_and_episode(self):
        self.assertEqual(clean_title("درس_دوم.1080p.قسمت_02"), "درس دوم قسمت 02")

    def test_caption_braces_in_title_are_literal(self):
        row = {**self.info, "title": "{filename}", "size": 100, "path": str(self.path)}
        self.assertEqual(caption(row, {"template": "{title}"}), "{filename}")
        self.assertLessEqual(len(utf16_trim("😀" * 700).encode("utf-16-le")), 2000)

    def test_daytime_boundaries(self):
        config = {**self.config, "days": [0], "start": "09:00", "end": "22:00"}
        self.assertTrue(allowed_at(datetime(2026, 10, 26, 9, tzinfo=timezone.utc), config))
        self.assertFalse(allowed_at(datetime(2026, 10, 26, 22, tzinfo=timezone.utc), config))
        self.assertFalse(allowed_at(datetime(2026, 10, 27, 9, tzinfo=timezone.utc), config))

    def test_overnight_uses_starting_weekday(self):
        config = {**self.config, "days": [0], "start": "22:00", "end": "02:00"}
        self.assertTrue(allowed_at(datetime(2026, 10, 26, 23, tzinfo=timezone.utc), config))
        self.assertTrue(allowed_at(datetime(2026, 10, 27, 1, tzinfo=timezone.utc), config))
        self.assertFalse(allowed_at(datetime(2026, 10, 27, 23, tzinfo=timezone.utc), config))

    def test_tehran_and_not_before(self):
        config = {**self.config, "timezone": "Asia/Tehran", "start": "09:00", "end": "22:00",
                  "not_before": "2026-10-28T10:00:00"}
        self.assertFalse(allowed_at(datetime(2026, 10, 28, 6, tzinfo=timezone.utc), config))
        self.assertTrue(allowed_at(datetime(2026, 10, 28, 7, tzinfo=timezone.utc), config))

    def engine(self, fake):
        self.add()
        engine = Engine(self.data, self.config, self.store)
        engine.client = fake
        if not hasattr(fake, 'upload_file'):
            async def upload(path, file_name, progress_callback):
                return InputFile(1, 1, file_name, 'test')
            fake.upload_file = upload
        engine.scope = "1:1"
        engine.entity = "me"
        engine.active = True
        engine.paused.clear()
        return engine, self.store.rows("1:1")[0]

    def test_send_success_records_receipt_and_preserves_filename(self):
        seen = []
        class Fake:
            async def upload_file(self, path, file_name, **kwargs):
                seen.append(file_name)
                self.assert_content = Path(path).read_bytes()
                return InputFile(1, 1, file_name, 'test')
            async def send_file(self, target, media, **kwargs):
                return SimpleNamespace(id=88)
        engine, row = self.engine(Fake())
        asyncio.run(engine.send(row))
        result = self.store.rows("1:1")[0]
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["message_id"], 88)
        self.assertEqual(seen, [self.path.name])
        self.assertTrue(float(self.store.state("last:1:1")) > 0)
        self.assertFalse(list(self.data.glob("upload-*")))

    def test_send_timeout_is_uncertain_and_pauses(self):
        class Fake:
            async def send_file(self, *args, **kwargs):
                raise asyncio.TimeoutError()
        engine, row = self.engine(Fake())
        asyncio.run(engine.send(row))
        self.assertEqual(self.store.rows("1:1")[0]["status"], "uncertain")
        self.assertTrue(engine.paused.is_set())

    def test_floodwait_stays_queued_and_persists_wait(self):
        class Fake:
            async def send_file(self, *args, **kwargs):
                raise errors.FloodWaitError(request=None, capture=70)
        engine, row = self.engine(Fake())
        asyncio.run(engine.send(row))
        self.assertEqual(self.store.rows("1:1")[0]["status"], "queued")
        self.assertGreater(float(self.store.state("blocked:1:1")), time.time() + 65)

    def test_changed_source_is_not_sent(self):
        class Fake:
            async def send_file(self, *args, **kwargs):
                raise AssertionError("must never upload a changed source")
        engine, row = self.engine(Fake())
        self.path.write_bytes(b"changed")
        asyncio.run(engine.send(row))
        self.assertEqual(self.store.rows("1:1")[0]["status"], "failed")
        self.assertFalse(list(self.data.glob("upload-*")))

    def test_pause_before_network_preserves_queue(self):
        class Fake:
            async def send_file(self, *args, **kwargs):
                raise AssertionError("paused")
        engine, row = self.engine(Fake())
        engine.pause_now()
        asyncio.run(engine.send(row))
        self.assertEqual(self.store.rows("1:1")[0]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
