from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from telethon import TelegramClient, errors, utils
from telethon.sessions import StringSession

import vault
from core import Scanner, Store, allowed_at, caption, digest, save_config, next_due
from calendar_ui import display_instant
from media import telegram_media


def friendly(error: Exception) -> str:
    names = {
        "ApiIdInvalidError": "API ID یا API Hash معتبر نیست. اطلاعات my.telegram.org را بررسی کنید.",
        "PhoneNumberInvalidError": "شماره تلفن معتبر نیست؛ با کد کشور، مثلاً +98 وارد کنید.",
        "PhoneCodeInvalidError": "کد ورود اشتباه است؛ دوباره اتصال را انجام دهید.",
        "PhoneCodeExpiredError": "کد ورود منقضی شده؛ دوباره اتصال را انجام دهید.",
        "PasswordHashInvalidError": "رمز دومرحله‌ای اشتباه است.",
        "ChatWriteForbiddenError": "حساب شما اجازهٔ ارسال به این مقصد را ندارد.",
        "ChannelPrivateError": "کانال خصوصی در دسترس حساب شما نیست.",
        "AuthKeyUnregisteredError": "نشست ورود معتبر نیست؛ خروج و ورود دوباره لازم است.",
        "SessionRevokedError": "نشست از تلگرام لغو شده؛ دوباره وارد شوید.",
        "UserBannedInChannelError": "حساب در این مقصد اجازهٔ ارسال ندارد.",
        "ChatAdminRequiredError": "ارسال به این مقصد به دسترسی مدیر نیاز دارد.",
        "FilePartsInvalidError": "تلگرام فایل را نپذیرفت؛ اندازه و نوع آن را بررسی کنید.",
    }
    if isinstance(error, (ConnectionError, OSError, asyncio.TimeoutError)):
        return "ارتباط برقرار نشد یا قطع شد. اینترنت، VPN یا پراکسی تنظیم‌شده را بررسی کنید."
    return names.get(type(error).__name__, "عملیات انجام نشد (" + type(error).__name__ + ").")


def snapshot(row: dict, folder: Path) -> Path:
    source = Path(row["path"])
    directory = Path(tempfile.mkdtemp(prefix="upload-", dir=folder))
    target = directory / source.name
    try:
        shutil.copyfile(source, target)
        if digest(target) != row["hash"]:
            raise ValueError("محتوای فایل تغییر کرده است؛ ردیف قدیمی را کنار بگذارید و پوشه را دوباره بررسی کنید.")
        return target
    except BaseException:
        target.unlink(missing_ok=True)
        directory.rmdir()
        raise


class Engine(QThread):
    log = Signal(str)
    changed = Signal()
    account = Signal(str)
    destination = Signal(str, str)
    dialogs = Signal(list)
    prompt = Signal(str, str)
    running = Signal(bool)
    progress = Signal(int)
    timing = Signal(str)
    busy = Signal(bool)
    error = Signal(str)
    scan_status = Signal(str)

    def __init__(self, data: Path, config: dict, store: Store):
        super().__init__()
        self.data, self.config, self.store = data, dict(config), store
        self.scanner = Scanner(store)
        self.loop = None
        self.queue = None
        self.client = None
        self.scope = ""
        self.entity = None
        self.auth_future = None
        self.active = False
        self.paused = threading.Event()
        self.paused.set()
        self.last_scan = 0
        self.initial_scan_pending = False
        self.next_at = 0
        self.stopping = False
        self.pending = []
        self.pending_lock = threading.Lock()

    def submit(self, name: str, payload=None):
        with self.pending_lock:
            if self.loop and self.queue:
                self.loop.call_soon_threadsafe(self.queue.put_nowait, (name, payload))
            else:
                self.pending.append((name, payload))

    def pause_now(self):
        # Safe even while network I/O is blocked. Current upload may still finish.
        self.paused.set()

    def answer(self, text):
        if self.loop:
            def settle():
                if self.auth_future and not self.auth_future.done():
                    self.auth_future.set_result(text)
            self.loop.call_soon_threadsafe(settle)

    def run(self):
        asyncio.run(self.main())

    async def ask(self, kind: str, text: str) -> str:
        self.auth_future = self.loop.create_future()
        self.prompt.emit(kind, text)
        result = await self.auth_future
        if result is None:
            raise ValueError("ورود لغو شد.")
        return result

    async def main(self):
        self.loop = asyncio.get_running_loop()
        with self.pending_lock:
            self.queue = asyncio.Queue()
            for command in self.pending:
                self.queue.put_nowait(command)
            self.pending.clear()
        self.gate = asyncio.Lock()
        scheduler = asyncio.create_task(self.scheduler())
        try:
            while not self.stopping:
                name, payload = await self.queue.get()
                self.busy.emit(True)
                try:
                    async with self.gate:
                        if name == "stop":
                            self.stopping = True
                        elif name == "login":
                            await self.login(payload)
                        elif name == "dialogs":
                            if not self.client or not await self.client.is_user_authorized():
                                raise ValueError("ابتدا وارد تلگرام شوید.")
                            result = [("پیام‌های ذخیره‌شدهٔ من", "me")]
                            async for dialog in self.client.iter_dialogs(limit=None):
                                if not dialog.entity or getattr(dialog.entity, "deleted", False):
                                    continue
                                result.append((dialog.name, str(utils.get_peer_id(dialog.entity))))
                            self.dialogs.emit(result)
                            self.log.emit(f"{len(result)} مقصد دریافت شد.")
                        elif name in {"inspect", "prepare", "start", "send_now"}:
                            self.paused.set()
                            self.active = False
                            self.running.emit(False)
                            self.config = dict(payload["config"] if name == "send_now" else payload)
                            save_config(self.data / "settings.json", self.config)
                            if name == "inspect":
                                self.scope = "preview:" + hashlib.sha256(self.config["folder"].encode()).hexdigest()[:16]
                                self.entity = None
                                self.destination.emit(self.scope, "پیش‌نمایش پوشه؛ هنوز مقصد ارسال تأیید نشده")
                            else:
                                await self.resolve()
                            if name == "send_now":
                                source = payload["row"]
                                self.store.enqueue(self.scope, Path(source["path"]), source, source["hash"], Path(source["path"]).stat())
                                row = next(r for r in self.store.rows(self.scope) if r["hash"] == source["hash"])
                                if row["status"] != "queued":
                                    raise ValueError("این محتوا قبلاً ارسال شده یا نیاز به تعیین وضعیت دارد؛ صف مقصد را بررسی کنید.")
                                self.running.emit(True)
                                self.paused.clear()
                                try:
                                    await self.send(row, immediate=True)
                                finally:
                                    self.paused.set()
                                    self.running.emit(False)
                            else:
                                self.scan_status.emit("در حال بررسی فایل‌ها؛ لطفاً صبر کنید…")
                                await self.scan()
                                await asyncio.sleep(2.1)
                                await self.scan()
                            self.initial_scan_pending = True
                            if name == "start":
                                last = float(self.store.state("last:" + self.scope, "0"))
                                blocked = float(self.store.state("blocked:" + self.scope, "0"))
                                self.next_at = max(time.time(), last + self.config["interval"] * 60, blocked)
                                self.active = True
                                self.paused.clear()
                                self.running.emit(True)
                                self.log.emit("ارسال زمان‌بندی‌شده فعال شد.")
                        elif name == "pause":
                            self.active = False
                            self.running.emit(False)
                            self.log.emit("ارسال متوقف شد؛ فایل بعدی ارسال نمی‌شود.")
                        elif name == "logout":
                            self.active = False
                            self.paused.set()
                            if self.client:
                                if await self.client.is_user_authorized():
                                    await self.client.log_out()
                                await self.client.disconnect()
                            self.client = None
                            self.entity, self.scope = None, ""
                            (self.data / "auth.dat").unlink(missing_ok=True)
                            self.account.emit("حساب متصل نیست")
                            self.destination.emit("", "مقصد انتخاب نشده")
                            self.log.emit("از حساب خارج شدید و نشست محلی حذف شد.")
                            self.running.emit(False)
                except Exception as exc:
                    message = str(exc) if isinstance(exc, ValueError) else friendly(exc)
                    self.log.emit(message)
                    self.error.emit(message)
                finally:
                    self.busy.emit(False)
                    self.changed.emit()
        finally:
            scheduler.cancel()
            await asyncio.gather(scheduler, return_exceptions=True)
            if self.client:
                await self.client.disconnect()

    async def login(self, values: dict):
        self.paused.set()
        self.active = False
        self.running.emit(False)
        self.entity, self.scope = None, ""
        self.destination.emit("", "مقصد انتخاب نشده")
        api_id = values["api_id"].strip()
        api_hash = values["api_hash"].strip()
        if not api_id.isdigit() or not 0 < int(api_id) < 2**31:
            raise ValueError("API ID باید عدد معتبر باشد.")
        if len(api_hash) != 32 or any(c not in "0123456789abcdefABCDEF" for c in api_hash):
            raise ValueError("API Hash باید دقیقاً ۳۲ نویسهٔ هگزادسیمال باشد؛ مقدار کامل را از my.telegram.org کپی کنید.")
        auth = {}
        try:
            auth = vault.load(self.data / "auth.dat")
        except Exception:
            self.log.emit("نشست ذخیره‌شده قابل خواندن نیست؛ ورود تازه انجام می‌شود.")
        session = auth.get("session", "") if str(auth.get("api_id")) == api_id and auth.get("api_hash") == api_hash else ""
        if self.client:
            await self.client.disconnect()
        proxy = None
        if values.get("proxy_host"):
            import socks
            proxy = (socks.SOCKS5, values["proxy_host"].strip(), int(values["proxy_port"]), True,
                     values.get("proxy_user") or None, values.get("proxy_password") or None)
        self.client = TelegramClient(StringSession(session), int(api_id), api_hash,
                                     proxy=proxy, connection_retries=2, request_retries=0,
                                     timeout=20, flood_sleep_threshold=0,
                                     device_model="Telegram Folder Publisher Desktop")
        await asyncio.wait_for(self.client.connect(), timeout=40)
        if not await self.client.is_user_authorized():
            phone = values.get("phone", "").strip()
            if not phone.startswith("+"):
                raise ValueError("شماره تلفن را همراه کد کشور و + وارد کنید.")
            sent = await self.client.send_code_request(phone)
            code = await self.ask("code", "کد تأیید ارسال‌شده از طرف تلگرام را وارد کنید:")
            code = "".join(str(int(c)) for c in code if c.isdecimal())
            try:
                await self.client.sign_in(phone=phone, code=code, phone_code_hash=sent.phone_code_hash)
            except errors.SessionPasswordNeededError:
                password = await self.ask("password", "رمز دومرحله‌ای حساب تلگرام را وارد کنید:")
                await self.client.sign_in(password=password)
                password = ""
        me = await self.client.get_me()
        try:
            vault.save(self.data / "auth.dat", {"api_id": api_id, "api_hash": api_hash, "session": self.client.session.save()})
        except Exception:
            self.log.emit("ورود انجام شد، ولی نشست روی این دستگاه ذخیره نشد.")
        self.config["api_id"] = api_id
        save_config(self.data / "settings.json", self.config)
        self.account.emit("متصل: " + (me.first_name or "") + (" @" + me.username if me.username else ""))
        self.log.emit("ورود به حساب شخصی انجام شد. مقصد و پوشه را انتخاب کنید.")

    async def resolve(self):
        self.entity, self.scope = None, ""
        self.destination.emit("", "در حال بررسی مقصد…")
        if not self.client or not await self.client.is_user_authorized():
            raise ValueError("ابتدا در زبانهٔ اتصال وارد حساب تلگرام شوید.")
        target = self.config["target"].strip()
        if not target:
            raise ValueError("مقصد را انتخاب کنید.")
        if target.lstrip("-").isdigit():
            target = int(target)
            # StringSession has no persistent entity cache. Resolve numeric peers from dialogs.
            async for dialog in self.client.iter_dialogs():
                if utils.get_peer_id(dialog.entity) == target:
                    target = dialog.entity
                    break
        entity = await self.client.get_entity(target)
        if getattr(entity, "broadcast", False) and not getattr(entity, "creator", False):
            rights = getattr(entity, "admin_rights", None)
            if not rights or not rights.post_messages:
                raise ValueError("این حساب در کانال انتخاب‌شده اجازهٔ انتشار ندارد.")
        me = await self.client.get_me()
        self.entity = await self.client.get_input_entity(entity)
        self.scope = f"{me.id}:{utils.get_peer_id(entity)}"
        name = "پیام‌های ذخیره‌شدهٔ من" if entity.id == me.id else (
            getattr(entity, "title", None) or getattr(entity, "first_name", "") or str(target))
        self.destination.emit(self.scope, name)

    async def scan(self):
        if not self.scope or not self.config.get("folder"):
            return
        count = await asyncio.to_thread(self.scanner.scan, dict(self.config), self.scope)
        self.last_scan = time.monotonic()
        self.changed.emit()
        if count:
            self.log.emit(f"{count} فایل تازه به صف افزوده شد.")
        report = self.scanner.last_report
        self.scan_status.emit(f"{report.get('found',0)} فایل بررسی شد · {report.get('waiting',0)} در انتظار اتمام کپی · {len(report.get('errors',[]))} خطا")
        for error in report.get('errors', [])[:5]:
            self.log.emit("بررسی فایل: " + error)

    async def scheduler(self):
        while True:
            await asyncio.sleep(1)
            if self.gate.locked():
                continue
            async with self.gate:
                try:
                    if self.scope and self.config.get("folder") and (self.config.get("auto_scan", True) or self.initial_scan_pending) and time.monotonic() - self.last_scan >= 20:
                        await self.scan()
                        self.initial_scan_pending = False
                    if not self.active or self.paused.is_set():
                        self.timing.emit("ارسال متوقف است")
                        continue
                    if not allowed_at(datetime.now(timezone.utc), self.config):
                        due = next_due(datetime.now(timezone.utc), self.config, self.next_at)
                        self.timing.emit("ارسال بعدی: " + display_instant(due, self.config['timezone'], self.config.get('calendar','jalali')) if due else "روز مجازی برای ارسال انتخاب نشده")
                        continue
                    if time.time() < self.next_at:
                        self.timing.emit("ارسال بعدی: " + display_instant(datetime.fromtimestamp(self.next_at, timezone.utc), self.config['timezone'], self.config.get('calendar','jalali')))
                        continue
                    row = next((r for r in self.store.rows(self.scope) if r["status"] == "queued"), None)
                    if not row:
                        self.timing.emit("صف خالی است؛ در انتظار فایل تازه")
                        continue
                    self.timing.emit("در حال آماده‌سازی و ارسال فایل…")
                    await self.send(row)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.paused.set()
                    self.active = False
                    self.running.emit(False)
                    self.log.emit(str(exc) if isinstance(exc, ValueError) else friendly(exc))

    async def send(self, row: dict, immediate=False):
        temp = None
        started = False
        try:
            if row["size"] > 2 * 1024**3:
                raise ValueError("این نسخه فایل‌های بزرگ‌تر از ۲ گیگابایت را ارسال نمی‌کند.")
            temp = await asyncio.to_thread(snapshot, row, self.data)
            if self.paused.is_set() or (not immediate and not allowed_at(datetime.now(timezone.utc), self.config)):
                return
            # A snapshot prevents a changing source file from changing an upload.
            self.store.update(row["id"], status="sending", error="")
            self.changed.emit()
            last_progress = [0.0]
            async def progress(sent, total):
                if time.monotonic() - last_progress[0] > .3 or sent == total:
                    self.progress.emit(int(sent * 100 / max(total, 1)))
                    last_progress[0] = time.monotonic()
            uploaded = await self.client.upload_file(str(temp), file_name=Path(row['path']).name, progress_callback=progress)
            if self.paused.is_set():
                self.store.update(row['id'], status='queued', error='ارسال پیش از انتشار متوقف شد.')
                return
            media = telegram_media(uploaded, row, self.config.get('as_document', False))
            started = True
            result = await self.client.send_file(self.entity, media, caption=caption(row, self.config), parse_mode=None)
            now = time.time()
            self.store.update(row["id"], status="sent", sent_at=now, message_id=result.id, error="")
            self.store.set_state("last:" + self.scope, str(now))
            self.next_at = now + self.config["interval"] * 60
            self.log.emit("ارسال شد: " + row["title"])
        except errors.FloodWaitError as exc:
            self.next_at = time.time() + exc.seconds + 5
            self.store.set_state("blocked:" + self.scope, str(self.next_at))
            self.store.update(row["id"], status="queued", error=f"تلگرام {exc.seconds} ثانیه انتظار درخواست کرد.")
            self.log.emit(f"محدودیت موقت تلگرام؛ ادامه پس از {exc.seconds} ثانیه.")
        except Exception as exc:
            # MTProto/network interruption can leave delivery uncertain. Require a human check.
            uncertain = started and not isinstance(exc, errors.RPCError)
            message = str(exc) if isinstance(exc, ValueError) else friendly(exc)
            self.store.update(row["id"], status="uncertain" if uncertain else "failed", error=message)
            self.paused.set()
            self.active = False
            self.running.emit(False)
            self.log.emit(message + (" مقصد را پیش از تلاش دوباره بررسی کنید." if uncertain else ""))
        finally:
            if temp:
                temp.unlink(missing_ok=True)
                temp.parent.rmdir()
            self.progress.emit(0)
            self.changed.emit()
