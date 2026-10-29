#!/usr/bin/env python3
"""LionXsec Shop — persistent storefront, manual payments, no external API calls."""
from __future__ import annotations

import argparse
import base64
import contextlib
from decimal import Decimal, InvalidOperation, ROUND_UP
import getpass
import hashlib
import hmac
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
from urllib.parse import urlsplit, unquote, parse_qs
from content import ResourceStoreMixin, ContentError, LIMITS
from social import DEFAULT_LINKS, validate_links
import automation
from assistant import Runner, read_config, save_config

ROOT = Path(__file__).resolve().parent
LANGS = ("fa", "en", "ar", "es")
BRANDS = ("generic", "nordvpn", "crunchyroll", "dazn", "netflix", "spotify", "youtube", "surfshark")
SUPPORT = DEFAULT_LINKS['telegram']
MIN_QTY, MAX_QTY = 5, 10000
STATUSES = {"awaiting_payment", "under_review", "paid", "delivered", "cancelled"}
TRANSITIONS = {
    "awaiting_payment": {"under_review", "paid", "cancelled"},
    "under_review": {"paid", "cancelled"}, "paid": {"delivered"},
    "delivered": set(), "cancelled": set(),
}


class Problem(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


def now():
    return int(time.time())


def localized(value, required=True):
    if not isinstance(value, dict) or set(value) != set(LANGS):
        raise Problem("translations_required")
    out = {}
    for lang in LANGS:
        text = value[lang]
        if not isinstance(text, str) or len(text.strip()) > 250 or (required and not text.strip()):
            raise Problem("invalid_translation")
        out[lang] = text.strip()
    return out


def money_cents(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not Decimal("0.01") <= amount <= Decimal("100000"):
            raise ValueError
        if amount.quantize(Decimal(".01")) != amount:
            raise ValueError
        return int(amount * 100)
    except (InvalidOperation, ValueError, TypeError):
        raise Problem("invalid_price") from None


def valid_ltc(address):
    """Validate Litecoin mainnet base58check or SegWit checksum, not ownership."""
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    if address.startswith(("L", "M")):
        try:
            n = 0
            for c in address:
                n = n * 58 + alphabet.index(c)
            raw = n.to_bytes((n.bit_length()+7)//8, "big")
            raw = b"\0" * (len(address)-len(address.lstrip("1"))) + raw
            return len(raw) == 25 and raw[0] in (48, 50) and hmac.compare_digest(
                hashlib.sha256(hashlib.sha256(raw[:-4]).digest()).digest()[:4], raw[-4:])
        except (ValueError, OverflowError):
            return False
    if address.lower() != address and address.upper() != address:
        return False
    a = address.lower()
    if not a.startswith("ltc1") or not 14 <= len(a) <= 90:
        return False
    chars = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    try:
        data = [chars.index(c) for c in a[4:]]
    except ValueError:
        return False
    hrp = "ltc"
    values = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + data
    chk = 1
    for v in values:
        top = chk >> 25
        chk = ((chk & 0x1ffffff) << 5) ^ v
        for i, generator in enumerate((0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)):
            if (top >> i) & 1:
                chk ^= generator
    if len(data) < 7 or data[0] > 16 or chk != (1 if data[0] == 0 else 0x2bc830a3):
        return False
    # Decode witness program and reject nonzero/excessive padding.
    acc = bits = 0
    program = []
    for v in data[1:-6]:
        acc = (acc << 5) | v
        bits += 5
        while bits >= 8:
            bits -= 8
            program.append((acc >> bits) & 255)
    return bits < 5 and ((acc << (8-bits)) & 255) == 0 and 2 <= len(program) <= 40 and (
        data[0] != 0 or len(program) in (20, 32))


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600000).hex()
    return salt + ":" + digest


def password_matches(password, stored):
    salt = stored.split(":", 1)[0]
    return hmac.compare_digest(password_hash(password, salt), stored)


class Store(ResourceStoreMixin):
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS products (id TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS admin (id INTEGER PRIMARY KEY CHECK(id=1), password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, csrf TEXT NOT NULL, expires INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL,
              created INTEGER NOT NULL, status TEXT NOT NULL, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, created INTEGER NOT NULL,
              action TEXT NOT NULL, subject TEXT NOT NULL);
            """)
            if not db.execute("SELECT 1 FROM settings").fetchone():
                db.execute("INSERT INTO settings VALUES(1,?)", (json.dumps({
                    "usdt_bep20": "", "ltc": "", "ltc_usdt_rate": "", "rate_updated": 0,
                }),))
                for name, price, category, brand in (
                    ("NordVPN", 350, "work", "nordvpn"), ("Crunchyroll", 590, "creative", "crunchyroll"),
                    ("DAZN", 650, "other", "dazn"), ("Netflix", 450, "creative", "netflix"),
                    ("Spotify", 250, "creative", "spotify"), ("YouTube Premium", 390, "learning", "youtube")):
                    product = {"id": secrets.token_hex(8), "name": {l: name for l in LANGS},
                        "duration": dict(zip(LANGS, ("۳۰ روز", "30 days", "٣٠ يومًا", "30 días"))),
                        "delivery": dict(zip(LANGS, ("تحویل دستی در تلگرام", "Manual delivery on Telegram",
                            "تسليم يدوي عبر تيليجرام", "Entrega manual por Telegram"))),
                        "price_cents": price, "category": category, "brand": brand, "active": True, "demo": True}
                    db.execute("INSERT INTO products VALUES(?,?)", (product["id"], json.dumps(product)))
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        self.init_content()
        automation.initialize(self)

    @contextlib.contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def init_admin(self, password):
        if not isinstance(password, str) or not 12 <= len(password) <= 256:
            raise Problem("password_length")
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO admin VALUES(1,?)", (password_hash(password),))
            db.execute("DELETE FROM sessions")

    def settings(self, db):
        value = json.loads(db.execute("SELECT value FROM settings WHERE id=1").fetchone()[0])
        value['social_links'] = DEFAULT_LINKS | value.get('social_links', {})
        # Upgrade the previous bundled contact while preserving custom profiles and hidden links.
        if value['social_links']['telegram'].rstrip('/').lower() == 'https://t.me/link_lion':
            value['social_links']['telegram'] = SUPPORT
        return value

    def save_social_links(self, data):
        try:
            links = validate_links(data)
        except ValueError:
            raise Problem('invalid_social_url') from None
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            value = self.settings(db)
            value['social_links'].update(links)
            db.execute('UPDATE settings SET value=? WHERE id=1', (json.dumps(value),))
            self.log(db, 'social_links_saved', 'settings')
        return value['social_links']

    def catalog(self, admin=False):
        with self.db() as db:
            products = [json.loads(r[0]) for r in db.execute("SELECT value FROM products ORDER BY rowid")]
            settings = self.settings(db)
        methods = []
        if settings["usdt_bep20"]:
            methods.append("USDT_BEP20")
        if settings["ltc"] and settings["ltc_usdt_rate"] and now()-settings["rate_updated"] <= 86400:
            methods.append("LTC")
        return {"products": products if admin else [p for p in products if p["active"]],
                "settings": settings, "methods": methods, "minimum_quantity": MIN_QTY,
                "support": settings['social_links']['telegram'] or SUPPORT}

    def save_product(self, data, pid=None):
        if not isinstance(data, dict):
            raise Problem("invalid_product")
        p = {"id": pid or secrets.token_hex(8), "name": localized(data.get("name")),
             "duration": localized(data.get("duration")), "delivery": localized(data.get("delivery")),
             "price_cents": money_cents(data.get("price")), "category": data.get("category", "work"),
             "active": data.get("active", True), "brand": data.get("brand", "generic"),
             "logo_id": data.get("logo_id") or None, "demo": False}
        if p["category"] not in ("work", "creative", "learning", "other") or type(p["active"]) is not bool or p["brand"] not in BRANDS:
            raise Problem("invalid_product")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if p["logo_id"]:
                self.media_record(p["logo_id"], "logo", db)
            if pid and not db.execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
                raise Problem("not_found", 404)
            if pid:
                db.execute("UPDATE products SET value=? WHERE id=?", (json.dumps(p), pid))
            else:
                db.execute("INSERT INTO products VALUES(?,?)", (p["id"], json.dumps(p)))
            self.log(db, "product_saved", p["id"])
        return p

    @staticmethod
    def log(db, action, subject):
        db.execute("INSERT INTO audit(created,action,subject) VALUES(?,?,?)", (now(), action, subject))

    def save_settings(self, data):
        usdt, ltc = data.get("usdt_bep20", ""), data.get("ltc", "")
        if not isinstance(usdt, str) or not isinstance(ltc, str):
            raise Problem("invalid_wallet")
        usdt, ltc = usdt.strip(), ltc.strip()
        if usdt and (not re.fullmatch(r"0x[0-9a-fA-F]{40}", usdt) or int(usdt[2:], 16) == 0):
            raise Problem("invalid_usdt_wallet")
        if ltc and not valid_ltc(ltc):
            raise Problem("invalid_ltc_wallet")
        rate = str(data.get("ltc_usdt_rate", "")).strip()
        if rate:
            try:
                n = Decimal(rate)
                if not n.is_finite() or not Decimal("0.01") <= n <= Decimal("1000000") or n.as_tuple().exponent < -8:
                    raise ValueError
                rate = format(n, "f")
            except (ValueError, InvalidOperation):
                raise Problem("invalid_rate") from None
        value = {"usdt_bep20": usdt, "ltc": ltc, "ltc_usdt_rate": rate, "rate_updated": now() if rate else 0}
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            value['social_links'] = self.settings(db)['social_links']
            db.execute("UPDATE settings SET value=? WHERE id=1", (json.dumps(value),))
            self.log(db, "wallets_saved", "settings")
        return value

    def create_order(self, data):
        items = data.get("items")
        lang, method = data.get("language", "fa"), data.get("method")
        username = data.get("telegram", "").strip() if isinstance(data.get("telegram", ""), str) else "!"
        if username and not re.fullmatch(r"@?[A-Za-z][A-Za-z0-9_]{4,31}", username):
            raise Problem("invalid_telegram")
        if lang not in LANGS or method not in ("LTC", "USDT_BEP20"):
            raise Problem("invalid_order")
        if not isinstance(items, list) or not 1 <= len(items) <= 30:
            raise Problem("invalid_order")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            settings = self.settings(db)
            address = settings["ltc" if method == "LTC" else "usdt_bep20"]
            if not address:
                raise Problem("payment_unavailable", 409)
            if method == "LTC" and (not settings["ltc_usdt_rate"] or now()-settings["rate_updated"] > 86400):
                raise Problem("rate_expired", 409)
            snapshots, seen = [], set()
            for item in items:
                if not isinstance(item, dict):
                    raise Problem("invalid_order")
                pid, qty = item.get("id"), item.get("quantity")
                if not isinstance(pid, str) or pid in seen or type(qty) is not int or not MIN_QTY <= qty <= MAX_QTY:
                    raise Problem("minimum_quantity")
                seen.add(pid)
                row = db.execute("SELECT value FROM products WHERE id=?", (pid,)).fetchone()
                if not row:
                    raise Problem("product_unavailable", 409)
                p = json.loads(row[0])
                if not p["active"] or p.get("demo"):
                    raise Problem("product_unavailable", 409)
                snapshots.append({"id": pid, "name": p["name"], "duration": p["duration"],
                    "delivery": p["delivery"], "unit_cents": p["price_cents"], "quantity": qty})
            total = sum(p["unit_cents"] * p["quantity"] for p in snapshots)
            if total > 100000000:
                raise Problem("order_too_large")
            amount = Decimal(total) / 100
            rate = settings["ltc_usdt_rate"] if method == "LTC" else None
            if rate:
                amount = (amount / Decimal(rate)).quantize(Decimal(".00000001"), rounding=ROUND_UP)
            else:
                amount = amount.quantize(Decimal(".01"))
            oid, token = "LX-" + secrets.token_hex(6).upper(), secrets.token_urlsafe(32)
            order = {"id": oid, "created": now(), "status": "awaiting_payment", "items": snapshots,
                "total_cents": total, "method": method, "address": address, "amount": str(amount),
                "rate": rate, "quote_expires": now()+1800, "telegram": username, "language": lang,
                "txid": "", "notes": "", "updated": now()}
            db.execute("INSERT INTO orders VALUES(?,?,?,?,?)", (oid, hashlib.sha256(token.encode()).hexdigest(),
                order["created"], order["status"], json.dumps(order)))
            self.log(db, "order_created", oid)
        return {**self.public_order(order), "access_token": token}

    @staticmethod
    def public_order(order):
        return {k: v for k, v in order.items() if k not in ("notes", "txid", "telegram")}

    def order(self, token):
        with self.db() as db:
            r = db.execute("SELECT value FROM orders WHERE token=?", (hashlib.sha256(token.encode()).hexdigest(),)).fetchone()
        if not r:
            raise Problem("not_found", 404)
        return self.public_order(json.loads(r[0]))

    def update_order(self, oid, data):
        status = data.get("status")
        notes, txid = data.get("notes", ""), data.get("txid", "")
        if status not in STATUSES or not isinstance(notes, str) or len(notes) > 2000 or not isinstance(txid, str):
            raise Problem("invalid_order")
        txid = txid.strip()
        if txid and not re.fullmatch(r"(?:0x)?[0-9a-fA-F]{64}", txid):
            raise Problem("invalid_txid")
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            r = db.execute("SELECT value FROM orders WHERE id=?", (oid,)).fetchone()
            if not r:
                raise Problem("not_found", 404)
            order = json.loads(r[0])
            if status != order["status"] and status not in TRANSITIONS[order["status"]]:
                raise Problem("invalid_status_transition", 409)
            if status != order["status"] and status in ("paid", "delivered") and data.get("manual_confirmed") is not True:
                raise Problem("manual_confirmation_required")
            order.update(status=status, notes=notes.strip(), txid=txid, updated=now())
            db.execute("UPDATE orders SET status=?,value=? WHERE id=?", (status, json.dumps(order), oid))
            self.log(db, "order_"+status, oid)
        return order


class App(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store, origin=""):
        self.store, self.origin = store, origin.rstrip("/")
        self.login_attempts, self.order_attempts = {}, {}
        self.limit_lock = threading.Lock()
        super().__init__(address, Handler)

    def limited(self, group, key, count, window):
        with self.limit_lock:
            records = self.login_attempts if group == "login" else self.order_attempts
            cutoff = time.time()-window
            for ip in list(records):
                records[ip] = [t for t in records[ip] if t > cutoff]
                if not records[ip]:
                    del records[ip]
            values = records.setdefault(key, [])
            if len(values) >= count:
                return True
            values.append(time.time())
            return False


class Handler(BaseHTTPRequestHandler):
    server_version = "LionXsecShop/1.2"

    def log_message(self, fmt, *args):
        # Public order tokens, credentials and order details never enter access logs.
        pass

    def send(self, value, status=200, headers=None, kind="application/json; charset=utf-8"):
        body = json.dumps(value, ensure_ascii=False).encode() if isinstance(value, (dict, list)) else value
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if self.server.origin.startswith("https:"):
            self.send_header("Strict-Transport-Security", "max-age=31536000")
        for key, val in (headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def body(self):
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            raise Problem("json_required", 415)
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise Problem("invalid_request") from None
        if not 1 <= size <= 65536:
            raise Problem("request_too_large", 413)
        try:
            data = json.loads(self.rfile.read(size))
        except (ValueError, UnicodeDecodeError):
            raise Problem("invalid_json") from None
        if not isinstance(data, dict):
            raise Problem("invalid_json")
        return data

    def session(self, mutation=False):
        c = cookies.SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except cookies.CookieError:
            raise Problem("unauthorized", 401) from None
        token = c.get("lx_session")
        if not token:
            raise Problem("unauthorized", 401)
        with self.server.store.db() as db:
            s = db.execute("SELECT * FROM sessions WHERE token=? AND expires>?", (
                hashlib.sha256(token.value.encode()).hexdigest(), now())).fetchone()
        if not s:
            raise Problem("unauthorized", 401)
        if mutation and not hmac.compare_digest(s["csrf"], self.headers.get("X-CSRF-Token", "")):
            raise Problem("csrf", 403)
        return s

    def check_origin(self):
        origin = self.headers.get("Origin")
        expected = self.server.origin or "http://" + self.headers.get("Host", "")
        if origin and origin != expected:
            raise Problem("origin", 403)
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise Problem("origin", 403)

    def cookie(self, token, age=28800):
        return f"lx_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={age}" + (
            "; Secure" if self.server.origin.startswith("https:") else "")

    def do_GET(self):
        try:
            path = unquote(urlsplit(self.path).path)
            if path == "/api/health":
                return self.send({"ok": True})
            if path == "/api/catalog":
                return self.send(self.server.store.catalog())
            if path == "/api/resources":
                return self.send({"resources": self.server.store.resources()})
            if path.startswith('/media/'):
                return self.serve_media(path.removeprefix('/media/'))
            if path.startswith("/api/orders/"):
                return self.send(self.server.store.order(path.removeprefix("/api/orders/")))
            if path == "/api/admin/me":
                session = self.session()
                return self.send({"authenticated": True, "csrf": session["csrf"]})
            if path == "/api/admin/catalog":
                self.session()
                return self.send(self.server.store.catalog(True))
            if path == "/api/admin/resources":
                self.session()
                return self.send({"resources":self.server.store.resources(True)})
            if path == '/api/assistant/posts':
                return self.send({'posts':automation.public_posts(self.server.store)})
            if path == '/api/admin/assistant':
                self.session()
                with self.server.store.db() as db:
                    row = db.execute("SELECT value FROM assistant_state WHERE key='runtime'").fetchone()
                    account_row = db.execute("SELECT value FROM assistant_state WHERE key='account_runtime'").fetchone()
                return self.send({'config':read_config(self.server.store,public=True),
                                  'receiver':json.loads(account_row[0]) if account_row else {'state':'not_started'},
                                  'runtime':json.loads(row[0]) if row else {'state':'not_started'},
                                  **automation.status(self.server.store)})
            if path == "/api/admin/uploads":
                self.session()
                return self.send({"uploads":self.server.store.media_list()})
            if path == "/api/admin/orders":
                self.session()
                with self.server.store.db() as db:
                    orders = [json.loads(r[0]) for r in db.execute("SELECT value FROM orders ORDER BY created DESC,rowid DESC LIMIT 500")]
                return self.send({"orders": orders})
            files = {"/": "index.html", "/admin": "admin.html", "/app.js": "app.js", "/content.js": "content.js", "/content-admin.js": "content-admin.js",
                     "/admin.js": "admin.js", "/shared.js": "shared.js", "/styles.css": "styles.css",
                     "/theme.css": "theme.css", "/favicon.svg": "favicon.svg",
                     "/social.js": "social.js", "/social-admin.js": "social-admin.js"}
            files.update({'/assistant-ui.js':'assistant-ui.js','/assistant-feed.js':'assistant-feed.js',
                          '/assistant-status.js':'assistant-status.js'})
            assets = {f"{brand}.svg" for brand in BRANDS if brand != "generic"} | {"lion-mark.svg", "lion-hero.png", "lion-logo.png"}
            files.update({"/assets/"+asset: "assets/"+asset for asset in assets})
            if path not in files:
                raise Problem("not_found", 404)
            file = ROOT / "static" / files[path]
            kinds = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                     ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png"}
            return self.send(file.read_bytes(), kind=kinds[file.suffix])
        except (Problem, ContentError) as e:
            self.send({"error": e.code}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_HEAD(self):
        self.do_GET()

    def serve_media(self, mid):
        row = self.server.store.media_record(mid)
        path = self.server.store.media_dir / row['filename']
        if not path.is_file():
            raise ContentError('media_not_found',404)
        size, start = path.stat().st_size, 0
        end, status = size-1, 200
        requested = self.headers.get('Range')
        if requested:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)',requested) if len(requested)<128 else None
            if not match or not any(match.groups()):
                return self.send(b'',416,{'Content-Range':f'bytes */{size}'},row['mime'])
            left,right=match.groups()
            if left:
                start=int(left);end=min(int(right),size-1) if right else size-1
            else:
                count=int(right);start=max(0,size-count)
                if count == 0:
                    return self.send(b'',416,{'Content-Range':f'bytes */{size}'},row['mime'])
            if start>=size or end<start:
                return self.send(b'',416,{'Content-Range':f'bytes */{size}'},row['mime'])
            status=206
        self.send_response(status)
        self.send_header('Content-Type',row['mime'])
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'none'; sandbox")
        self.send_header('Cache-Control','public, max-age=3600')
        if status==206:
            self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers()
        if self.command=='HEAD':
            return
        with path.open('rb') as file:
            file.seek(start)
            remaining=end-start+1
            while remaining:
                chunk=file.read(min(65536,remaining))
                if not chunk:break
                self.wfile.write(chunk);remaining-=len(chunk)

    def receive_upload(self):
        self.session(mutation=True)
        kind=parse_qs(urlsplit(self.path).query).get('kind',[''])[0]
        try:
            length=int(self.headers.get('Content-Length','0'))
        except ValueError:
            raise ContentError('invalid_request') from None
        if kind not in LIMITS:
            raise ContentError('invalid_upload_kind')
        if not 1<=length<=LIMITS[kind] or self.headers.get('Transfer-Encoding'):
            raise ContentError('upload_too_large',413)
        previous=self.connection.gettimeout()
        self.connection.settimeout(30)
        try:
            result=self.server.store.upload(self.rfile,kind,length,unquote(self.headers.get('X-Upload-Name','upload')))
        except TimeoutError:
            raise ContentError('upload_timeout',408) from None
        finally:
            self.connection.settimeout(previous)
        return self.send(result,201)

    def do_POST(self):
        self.mutate("POST")

    def do_PUT(self):
        self.mutate("PUT")

    def do_DELETE(self):
        self.mutate("DELETE")

    def mutate(self, method):
        try:
            self.check_origin()
            path = urlsplit(self.path).path
            if path=='/api/admin/uploads' and method=='POST':
                return self.receive_upload()
            data = self.body()
            store = self.server.store
            if path == "/api/admin/login" and method == "POST":
                if self.server.limited("login", self.client_address[0], 8, 900):
                    raise Problem("rate_limited", 429)
                password = data.get("password")
                if not isinstance(password, str) or len(password) > 256:
                    raise Problem("invalid_credentials", 401)
                with store.db() as db:
                    admin = db.execute("SELECT password FROM admin WHERE id=1").fetchone()
                    if not admin:
                        raise Problem("admin_not_configured", 503)
                    if not password_matches(password, admin[0]):
                        raise Problem("invalid_credentials", 401)
                    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
                    db.execute("DELETE FROM sessions WHERE expires<?", (now(),))
                    db.execute("INSERT INTO sessions VALUES(?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), csrf, now()+28800))
                return self.send({"csrf": csrf}, headers={"Set-Cookie": self.cookie(token)})
            if path == "/api/orders" and method == "POST":
                if self.server.limited("orders", self.client_address[0], 15, 3600):
                    raise Problem("rate_limited", 429)
                return self.send(store.create_order(data), 201)
            if path.startswith("/api/admin/"):
                session = self.session(mutation=True)
                if path=='/api/admin/resources' and method=='POST':
                    return self.send(store.save_resource(data),201)
                if path.startswith('/api/admin/resources/'):
                    rid=path.removeprefix('/api/admin/resources/')
                    if method=='PUT':return self.send(store.save_resource(data,rid))
                    if method=='DELETE':
                        store.delete_resource(rid)
                        return self.send({'ok':True})
                if path.startswith('/api/admin/uploads/') and method=='DELETE':
                    store.delete_media(path.removeprefix('/api/admin/uploads/'))
                    return self.send({'ok':True})
                if path == "/api/admin/logout" and method == "POST":
                    with store.db() as db:
                        db.execute("DELETE FROM sessions WHERE token=?", (session["token"],))
                    return self.send({"ok": True}, headers={"Set-Cookie": self.cookie("", 0)})
                if path == "/api/admin/settings" and method == "PUT":
                    return self.send(store.save_settings(data))
                if path == "/api/admin/social-links" and method == "PUT":
                    return self.send(store.save_social_links(data))
                if path == '/api/admin/assistant/reprocess' and method == 'POST':
                    return self.send({'queued': automation.requeue_published(store)})
                if path == '/api/admin/assistant/retry' and method == 'POST':
                    return self.send({'queued': automation.requeue_failed(store)})
                if path == '/api/admin/assistant' and method == 'PUT':
                    try:
                        return self.send(save_config(store,data))
                    except ValueError as error:
                        raise Problem(str(error)) from None
                if path == "/api/admin/products" and method == "POST":
                    return self.send(store.save_product(data), 201)
                prefix = "/api/admin/products/"
                if path.startswith(prefix) and re.fullmatch(r"[0-9a-f]{16}", path[len(prefix):]):
                    pid = path[len(prefix):]
                    if method == "PUT":
                        return self.send(store.save_product(data, pid))
                    if method == "DELETE":
                        with store.db() as db:
                            if not db.execute("DELETE FROM products WHERE id=?", (pid,)).rowcount:
                                raise Problem("not_found", 404)
                            store.log(db, "product_deleted", pid)
                        return self.send({"ok": True})
                prefix = "/api/admin/orders/"
                if path.startswith(prefix) and method == "PUT":
                    return self.send(store.update_order(path[len(prefix):], data))
            raise Problem("not_found", 404)
        except (Problem, ContentError) as e:
            self.send({"error": e.code}, e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            # Never return tracebacks containing private order data to clients.
            self.send({"error": "internal_error"}, 500)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="serve", choices=("serve", "init-admin", "start"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    os.umask(0o077)
    store = Store(args.data_dir / "shop.sqlite3")
    with store.db() as db:
        has_admin = bool(db.execute("SELECT 1 FROM admin").fetchone())
    if args.command == "init-admin" or (args.command == "start" and not has_admin):
        password = getpass.getpass("New admin password (12+ characters): ")
        if password != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords do not match.")
        try:
            store.init_admin(password)
        except Problem as e:
            raise SystemExit(e.code) from None
        print("Admin password saved. Existing admin sessions revoked.")
        if args.command == "init-admin":
            return
    origin = os.environ.get("PUBLIC_ORIGIN", "").rstrip("/")
    if args.host not in ("127.0.0.1", "localhost", "::1") and not origin.startswith("https://"):
        raise SystemExit("Public hosting requires PUBLIC_ORIGIN=https://your-domain and an HTTPS reverse proxy.")
    app = App((args.host, args.port), store, origin)
    runner = Runner(store)
    runner.start()
    print(f"LionXsec Shop listening on {args.host}:{app.server_port}. Ctrl+C to stop.")
    try:
        app.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop.set()
        app.server_close()


if __name__ == "__main__":
    main()
