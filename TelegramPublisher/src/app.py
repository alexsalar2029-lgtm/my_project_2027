from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PySide6.QtCore import Qt, QTimer, QTime, QDateTime, QLockFile
from PySide6.QtGui import QFont, QColor, QTextCursor
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QPushButton, QTabWidget, QGroupBox, QCheckBox, QSpinBox,
    QComboBox, QTimeEdit, QDateTimeEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMessageBox, QInputDialog, QTextEdit, QProgressBar,
    QPlainTextEdit, QSplitter, QScrollArea)

import vault
from core import Store, STATES, KINDS, caption, human_size, load_config, save_config
from engine import Engine


STYLE = """
QWidget { font-family: 'Segoe UI', Tahoma; font-size: 13px; color: #25334a; }
QMainWindow, QWidget#root { background: #f3f6fa; }
QLabel#hero { font-size: 27px; font-weight: 700; color: #132b42; }
QLabel#sub { color: #61748b; }
QLabel#badge { background: #e0f4ef; color: #107365; padding: 12px; border-radius: 10px; }
QLabel#stat { background: white; border: 1px solid #dfe7ef; padding: 16px; border-radius: 12px; font-size: 17px; }
QGroupBox { background: white; border: 1px solid #dfe7ef; border-radius: 10px; margin-top: 18px; padding: 18px 12px 12px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top right; right: 16px; padding: 0 6px; }
QLineEdit, QComboBox, QSpinBox, QTimeEdit, QDateTimeEdit, QPlainTextEdit, QTextEdit {
 background: white; border: 1px solid #cfdbe6; border-radius: 6px; padding: 7px; selection-background-color: #b5e3db; }
QPushButton { background: white; border: 1px solid #cfdae6; padding: 10px 18px; border-radius: 7px; font-weight: 600; }
QPushButton:hover { background: #e9f3f5; border-color: #2c9d8c; }
QPushButton#primary { background: #127d70; color: white; border-color: #127d70; }
QPushButton#danger { color: #b74949; }
QPushButton:disabled { color: #8b9bad; background: #edf0f4; border-color: #e0e6ed; }
QTabWidget::pane { border: 0; background: #f3f6fa; }
QTabBar::tab { padding: 12px 24px; background: #e7edf4; border-radius: 6px; margin-left: 5px; }
QTabBar::tab:selected { background: #127d70; color: white; }
QTableWidget { border: 1px solid #dfe7ef; border-radius: 8px; background: white; gridline-color: #eef2f6; }
QHeaderView::section { background: #eaf0f6; padding: 10px; border: 0; font-weight: 600; }
QProgressBar { background: #e2e9f0; border: 0; border-radius: 5px; text-align: center; height: 20px; }
QProgressBar::chunk { background: #2bb79e; border-radius: 5px; }
QCheckBox { spacing: 7px; }
"""


def button(label, callback, primary=False):
    b = QPushButton(label)
    b.clicked.connect(callback)
    if primary:
        b.setObjectName("primary")
    return b


def ltr(widget):
    widget.setLayoutDirection(Qt.LeftToRight)
    return widget


class Window(QMainWindow):
    def __init__(self, data: Path):
        super().__init__()
        self.data = data
        self.config = load_config(data / "settings.json")
        self.store = Store(data / "queue.db")
        self.scope = ""
        self.is_active = False
        self.is_busy = False
        self.closing = False
        self.controls = []
        self.rows = []
        self.setWindowTitle("تلگرام‌یار | انتشار خودکار فایل")
        self.resize(1120, 850)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 20)
        layout.setSpacing(14)
        title = QLabel("تلگرام‌یار")
        title.setObjectName("hero")
        layout.addWidget(title)
        subtitle = QLabel("از پوشه تا تلگرام • عنوان خودکار، صف قابل بررسی و انتشار زمان‌بندی‌شده")
        subtitle.setObjectName("sub")
        layout.addWidget(subtitle)
        self.account_label = QLabel("حساب متصل نیست")
        self.account_label.setTextFormat(Qt.PlainText)
        self.account_label.setObjectName("badge")
        layout.addWidget(self.account_label)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        self.make_connect()
        self.make_publish()
        self.make_queue()
        self.make_logs()
        bottom = QHBoxLayout()
        self.timing = QLabel("ارسال متوقف است")
        bottom.addWidget(self.timing, 1)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(210)
        self.progress.setValue(0)
        bottom.addWidget(self.progress)
        layout.addLayout(bottom)
        self.engine = Engine(data, self.config, self.store)
        self.engine.log.connect(self.add_log)
        self.engine.changed.connect(self.refresh)
        self.engine.account.connect(self.account_label.setText)
        self.engine.destination.connect(self.set_destination)
        self.engine.dialogs.connect(self.set_dialogs)
        self.engine.prompt.connect(self.auth_prompt)
        self.engine.running.connect(self.set_running)
        self.engine.progress.connect(self.progress.setValue)
        self.engine.timing.connect(self.timing.setText)
        self.engine.busy.connect(self.set_busy)
        self.engine.start()
        self.refresh()
        self.add_log("آماده است. برنامه پس از بازشدن، هیچ فایلی را خودکار ارسال نمی‌کند؛ «شروع زمان‌بندی» را بزنید.")
        try:
            saved = vault.load(data / "auth.dat")
            if saved:
                self.api_id.setText(saved.get("api_id", ""))
                self.api_hash.setText(saved.get("api_hash", ""))
                self.add_log("نشست ذخیره‌شده آماده است؛ برای اتصال دکمهٔ ورود را بزنید.")
        except Exception:
            self.add_log("نشست ذخیره‌شده قابل خواندن نیست. می‌توانید دوباره وارد شوید.")

    def page(self, title):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 12, 0, 0)
        self.tabs.addTab(page, title)
        return layout

    def make_connect(self):
        layout = self.page("۱. اتصال تلگرام")
        box = QGroupBox("ورود به حساب شخصی")
        form = QFormLayout(box)
        self.api_id = ltr(QLineEdit(str(self.config.get("api_id", ""))))
        self.api_id.setPlaceholderText("API ID")
        self.api_hash = ltr(QLineEdit())
        self.api_hash.setEchoMode(QLineEdit.Password)
        self.api_hash.setPlaceholderText("API Hash — 32 characters")
        self.phone = ltr(QLineEdit())
        self.phone.setPlaceholderText("+989xxxxxxxxx")
        form.addRow("API ID", self.api_id)
        form.addRow("API Hash", self.api_hash)
        form.addRow("شماره تلفن", self.phone)
        note = QLabel("اطلاعات API را از my.telegram.org → API development tools بگیرید.\n"
                      "کد ورود ممکن است داخل تلگرام برسد. رمز دومرحله‌ای فقط هنگام ورود پرسیده می‌شود.\n"
                      "نشست ورود با رمزگذاری ویندوز برای همین کاربر ذخیره می‌شود.")
        note.setWordWrap(True)
        form.addRow(note)
        layout.addWidget(box)
        proxy = QGroupBox("پراکسی SOCKS5 — اختیاری")
        pf = QFormLayout(proxy)
        self.proxy_host = ltr(QLineEdit())
        self.proxy_host.setPlaceholderText("127.0.0.1 — blank to disable")
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(1, 65535)
        self.proxy_port.setValue(1080)
        self.proxy_user = ltr(QLineEdit())
        self.proxy_password = ltr(QLineEdit())
        self.proxy_password.setEchoMode(QLineEdit.Password)
        pf.addRow("آدرس", self.proxy_host)
        pf.addRow("پورت", self.proxy_port)
        pf.addRow("نام کاربری (اختیاری)", self.proxy_user)
        pf.addRow("رمز پراکسی (اختیاری)", self.proxy_password)
        layout.addWidget(proxy)
        row = QHBoxLayout()
        self.login_button = button("اتصال / ورود به حساب", self.login, True)
        self.logout_button = button("خروج و حذف نشست", self.logout)
        self.logout_button.setObjectName("danger")
        row.addWidget(self.login_button)
        row.addWidget(self.logout_button)
        row.addStretch()
        layout.addLayout(row)
        layout.addStretch()
        self.controls += [self.api_id, self.api_hash, self.phone, self.proxy_host, self.proxy_port,
                          self.proxy_user, self.proxy_password, self.login_button, self.logout_button]

    def make_publish(self):
        outer = self.page("۲. پوشه و زمان‌بندی")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        source = QGroupBox("منبع و مقصد انتشار")
        form = QFormLayout(source)
        frow = QHBoxLayout()
        self.folder = ltr(QLineEdit(self.config["folder"]))
        pick = button("انتخاب پوشه…", self.pick_folder)
        frow.addWidget(self.folder, 1)
        frow.addWidget(pick)
        form.addRow("پوشهٔ فایل‌ها", frow)
        self.recursive = QCheckBox("فایل‌های زیرپوشه‌ها هم بررسی شوند")
        self.recursive.setChecked(self.config["recursive"])
        form.addRow(self.recursive)
        trow = QHBoxLayout()
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.addItem("پیام‌های ذخیره‌شدهٔ من", "me")
        if self.config.get("target", "me") != "me":
            self.target.addItem(self.config["target"], self.config["target"])
            self.target.setCurrentIndex(1)
        self.dialogs_button = button("دریافت گفت‌وگوها", lambda: self.engine.submit("dialogs"))
        trow.addWidget(self.target, 1)
        trow.addWidget(self.dialogs_button)
        form.addRow("ارسال به", trow)
        self.dest_label = QLabel("مقصد فعال: هنوز بررسی نشده")
        self.dest_label.setTextFormat(Qt.PlainText)
        self.dest_label.setWordWrap(True)
        form.addRow(self.dest_label)
        tip = QLabel("می‌توانید @username یا شناسهٔ عددی مقصد را هم بنویسید. برای کانال باید اجازهٔ انتشار داشته باشید.")
        tip.setWordWrap(True)
        form.addRow(tip)
        layout.addWidget(source)
        schedule = QGroupBox("زمان‌بندی انتشار")
        sf = QFormLayout(schedule)
        self.interval = QSpinBox()
        self.interval.setRange(1, 10080)
        self.interval.setValue(self.config["interval"])
        self.interval.setSuffix(" دقیقه")
        sf.addRow("فاصلهٔ میان دو فایل", self.interval)
        times = QHBoxLayout()
        self.start_time = ltr(QTimeEdit(QTime.fromString(self.config["start"], "HH:mm")))
        self.end_time = ltr(QTimeEdit(QTime.fromString(self.config["end"], "HH:mm")))
        self.start_time.setDisplayFormat("HH:mm")
        self.end_time.setDisplayFormat("HH:mm")
        times.addWidget(QLabel("از"))
        times.addWidget(self.start_time)
        times.addWidget(QLabel("تا"))
        times.addWidget(self.end_time)
        times.addStretch()
        sf.addRow("بازهٔ روزانه", times)
        self.zone = ltr(QComboBox())
        self.zone.setEditable(True)
        self.zone.addItems(["Asia/Tehran", "UTC", "Europe/Istanbul"])
        self.zone.setCurrentText(self.config["timezone"])
        sf.addRow("منطقهٔ زمانی", self.zone)
        days = QHBoxLayout()
        self.days = {}
        for day, name in [(5, "شنبه"), (6, "یکشنبه"), (0, "دوشنبه"), (1, "سه‌شنبه"), (2, "چهارشنبه"), (3, "پنجشنبه"), (4, "جمعه")]:
            check = QCheckBox(name)
            check.setChecked(day in self.config["days"])
            self.days[day] = check
            days.addWidget(check)
        sf.addRow("روزهای انتشار", days)
        self.use_date = QCheckBox("شروع از تاریخ و ساعت مشخص (میلادی، در منطقهٔ زمانی بالا)")
        self.date = ltr(QDateTimeEdit(QDateTime.currentDateTime()))
        self.date.setCalendarPopup(True)
        self.date.setDisplayFormat("yyyy-MM-dd HH:mm")
        if self.config.get("not_before"):
            self.use_date.setChecked(True)
            self.date.setDateTime(QDateTime.fromString(self.config["not_before"], Qt.ISODate))
        sf.addRow(self.use_date)
        sf.addRow("شروع انتشار", self.date)
        sf.addRow(QLabel("ساعت شروع و پایان یکسان یعنی تمام روز. بازهٔ شبانه به روز شروع آن تعلق دارد."))
        layout.addWidget(schedule)
        titles = QGroupBox("عنوان و متن زیر فایل")
        tf = QFormLayout(titles)
        self.template = QPlainTextEdit(self.config["template"])
        self.template.setMaximumHeight(100)
        tf.addRow("قالب کپشن", self.template)
        tf.addRow(QLabel("متغیرها: {title} عنوان • {type} نوع • {size} حجم • {filename} نام اصلی"))
        text = QLabel("عنوان از نام مرتب‌شدهٔ فایل، عنوان PDF یا تگ فایل صوتی ساخته می‌شود.\n"
                      "عنوان تحلیلی از محتوای تصویر/ویدئو تولید نمی‌شود. عنوان هر فایل در صف قابل ویرایش است.")
        text.setWordWrap(True)
        tf.addRow(text)
        layout.addWidget(titles)
        self.auto_scan = QCheckBox("پوشه هر ۲۰ ثانیه برای فایل تازه بررسی شود")
        self.auto_scan.setChecked(self.config["auto_scan"])
        layout.addWidget(self.auto_scan)
        note = QLabel("برای کارکرد زمان‌بندی، برنامه و کامپیوتر باید روشن بمانند. پس از خواب ویندوز، ارسال‌ها با فاصله ادامه می‌یابند.")
        note.setWordWrap(True)
        layout.addWidget(note)
        actions = QHBoxLayout()
        self.scan_button = button("بررسی پوشه و ساخت صف", lambda: self.prepare(False))
        self.start_button = button("شروع زمان‌بندی", lambda: self.prepare(True), True)
        self.pause_button = button("توقف ارسال", self.pause)
        self.pause_button.setEnabled(False)
        actions.addWidget(self.scan_button)
        actions.addWidget(self.start_button)
        actions.addWidget(self.pause_button)
        outer.addLayout(actions)
        self.controls += [self.folder, pick, self.recursive, self.target, self.dialogs_button,
            self.interval, self.start_time, self.end_time, self.zone, *self.days.values(), self.use_date,
            self.date, self.template, self.auto_scan, self.scan_button, self.start_button]

    def make_queue(self):
        layout = self.page("۳. صف و سابقه")
        stats = QHBoxLayout()
        self.stats = []
        for text in ["در صف: ۰", "ارسال شده: ۰", "نیازمند بررسی: ۰"]:
            label = QLabel(text)
            label.setObjectName("stat")
            self.stats.append(label)
            stats.addWidget(label)
        layout.addLayout(stats)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["عنوان", "نوع", "حجم", "وضعیت", "نام فایل", "زمان ارسال"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self.show_detail)
        layout.addWidget(self.table, 1)
        self.detail = QLabel("پس از بررسی پوشه، فایل‌ها اینجا نمایش داده می‌شوند. ثابت‌بودن فایل دست‌کم ۱۵ ثانیه بررسی می‌شود.")
        self.detail.setTextFormat(Qt.PlainText)
        self.detail.setWordWrap(True)
        self.detail.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.detail)
        row = QHBoxLayout()
        self.edit_button = button("ویرایش عنوان", self.edit_title)
        self.preview_button = button("پیش‌نمایش کپشن", self.preview_caption)
        self.skip_button = button("کنار گذاشتن", self.skip)
        self.retry_button = button("بازگرداندن به صف", self.retry)
        self.sent_button = button("تأیید ارسال در تلگرام", self.mark_sent)
        for b in [self.edit_button, self.preview_button, self.skip_button, self.retry_button, self.sent_button]:
            row.addWidget(b)
        layout.addLayout(row)
        self.controls += [self.edit_button, self.skip_button, self.retry_button, self.sent_button]

    def make_logs(self):
        layout = self.page("۴. گزارش فعالیت")
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        layout.addWidget(self.logs)
        layout.addWidget(QLabel("اطلاعات ورود و کد تأیید در گزارش ثبت نمی‌شوند. صف و تنظیمات در LocalAppData ذخیره می‌شوند."))

    def add_log(self, text):
        # Plain text avoids interpreting titles as HTML or links.
        self.logs.moveCursor(QTextCursor.End)
        self.logs.insertPlainText(datetime.now(ZoneInfo("Asia/Tehran")).strftime("%H:%M:%S") + "  " + text + "\n")
        self.logs.ensureCursorVisible()
        self.statusBar().showMessage(text, 12000)

    def read_config(self):
        folder = Path(self.folder.text().strip())
        if not folder.is_dir():
            raise ValueError("یک پوشهٔ معتبر انتخاب کنید.")
        zone = self.zone.currentText().strip()
        try:
            ZoneInfo(zone)
        except Exception:
            raise ValueError("منطقهٔ زمانی معتبر نیست. مثال: Asia/Tehran")
        days = [d for d, check in self.days.items() if check.isChecked()]
        if not days:
            raise ValueError("دست‌کم یک روز برای انتشار انتخاب کنید.")
        target = self.target.currentData() if self.target.currentIndex() >= 0 and self.target.currentText() == self.target.itemText(self.target.currentIndex()) else self.target.currentText()
        if not str(target or "").strip():
            raise ValueError("مقصد را انتخاب کنید.")
        return {**self.config, "folder": str(folder.resolve()), "recursive": self.recursive.isChecked(),
            "target": str(target).strip(), "interval": self.interval.value(),
            "start": self.start_time.time().toString("HH:mm"), "end": self.end_time.time().toString("HH:mm"),
            "timezone": zone, "days": days, "template": self.template.toPlainText(),
            "auto_scan": self.auto_scan.isChecked(), "api_id": self.api_id.text().strip(),
            "not_before": self.date.dateTime().toString("yyyy-MM-ddTHH:mm:ss") if self.use_date.isChecked() else ""}

    def prepare(self, start):
        try:
            config = self.read_config()
        except ValueError as e:
            QMessageBox.warning(self, "تنظیمات", str(e))
            return
        self.config = config
        self.engine.submit("start" if start else "prepare", config)
        self.tabs.setCurrentIndex(2)
        if not start:
            self.add_log("بررسی پوشه آغاز شد؛ فایل تازه پس از ثابت‌ماندن دست‌کم ۱۵ ثانیه و بررسی مجدد وارد صف می‌شود.")
    def login(self):
        self.engine.submit("login", {"api_id": self.api_id.text(), "api_hash": self.api_hash.text(),
            "phone": self.phone.text(), "proxy_host": self.proxy_host.text(),
            "proxy_port": self.proxy_port.value(), "proxy_user": self.proxy_user.text(),
            "proxy_password": self.proxy_password.text()})

    def auth_prompt(self, kind, text):
        echo = QLineEdit.Password if kind == "password" else QLineEdit.Normal
        value, ok = QInputDialog.getText(self, "ورود تلگرام", text, echo)
        self.engine.answer(value if ok else None)

    def logout(self):
        if QMessageBox.question(self, "خروج", "نشست این برنامه از تلگرام خارج و از این ویندوز حذف شود؟") == QMessageBox.Yes:
            self.engine.submit("logout")
            self.api_hash.clear()
            self.phone.clear()

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, "انتخاب پوشه", self.folder.text())
        if path:
            self.folder.setText(path)

    def set_dialogs(self, dialogs):
        current = self.target.currentData() or self.target.currentText()
        self.target.clear()
        for name, id_ in dialogs:
            self.target.addItem(name, id_)
        index = self.target.findData(current)
        self.target.setCurrentIndex(max(0, index))

    def set_destination(self, scope, name):
        self.scope = scope
        self.dest_label.setText("مقصد فعال: " + name)
        self.refresh()

    def pause(self):
        self.engine.pause_now()
        self.engine.submit("pause")
        self.timing.setText("توقف درخواست شد؛ ارسال در حال انجام ممکن است تکمیل شود.")

    def set_running(self, value):
        self.is_active = value
        self.update_controls()

    def set_busy(self, value):
        self.is_busy = value
        self.update_controls()

    def update_controls(self):
        for widget in self.controls:
            widget.setEnabled(not self.is_active and not self.is_busy and not self.closing)
        self.pause_button.setEnabled(self.is_active and not self.closing)

    def selected(self):
        index = self.table.currentRow()
        return self.rows[index] if 0 <= index < len(self.rows) else None

    def refresh(self):
        selected = self.selected()
        selected_id = selected["id"] if selected else None
        self.rows = self.store.rows(self.scope) if self.scope else []
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            sent_at = datetime.fromtimestamp(row["sent_at"], ZoneInfo(self.config["timezone"])).strftime("%Y-%m-%d %H:%M") if row["sent_at"] else "—"
            values = [row["title"], KINDS[row["kind"]], human_size(row["size"]), STATES[row["status"]], Path(row["path"]).name, sent_at]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(row["error"] or row["path"])
                if column == 3:
                    item.setForeground(QColor("#127d70" if row["status"] == "sent" else "#ba6142" if row["status"] in {"failed", "uncertain"} else "#506581"))
                self.table.setItem(i, column, item)
            if row["id"] == selected_id:
                self.table.selectRow(i)
        counts = [sum(r["status"] == "queued" for r in self.rows), sum(r["status"] == "sent" for r in self.rows),
                  sum(r["status"] in {"failed", "uncertain"} for r in self.rows)]
        for label, name, value in zip(self.stats, ["در صف", "ارسال شده", "نیازمند بررسی"], counts):
            label.setText(f"{name}: {value}")
        self.show_detail()

    def show_detail(self):
        row = self.selected()
        if row:
            self.detail.setText(row["path"] + ("\n" + row["error"] if row["error"] else ""))

    def editable(self):
        row = self.selected()
        if not row or self.is_active or self.is_busy or row["status"] == "sending":
            return None
        return row

    def edit_title(self):
        row = self.editable()
        if row and row["status"] != "sent":
            text, ok = QInputDialog.getText(self, "ویرایش عنوان", "عنوان فایل:", text=row["title"])
            if ok and text.strip():
                self.store.update(row["id"], title=text.strip()[:240])
                self.refresh()

    def preview_caption(self):
        row = self.selected()
        if row:
            config = {**self.config, "template": self.template.toPlainText()}
            message = QMessageBox(self)
            message.setWindowTitle("پیش‌نمایش کپشن")
            message.setTextFormat(Qt.PlainText)
            message.setText(caption(row, config) or "(بدون کپشن)")
            message.exec()

    def skip(self):
        row = self.editable()
        if row and row["status"] != "sent":
            self.store.update(row["id"], status="skipped")
            self.refresh()

    def retry(self):
        row = self.editable()
        if not row or row["status"] not in {"failed", "uncertain", "skipped"}:
            return
        if row["status"] == "uncertain":
            answer = QMessageBox.question(self, "بررسی ارسال", "تلگرام را بررسی کرده‌اید و این فایل ارسال نشده است؟ تلاش دوباره ممکن است فایل تکراری ایجاد کند.")
            if answer != QMessageBox.Yes:
                return
        self.store.update(row["id"], status="queued", error="")
        self.refresh()

    def mark_sent(self):
        row = self.editable()
        if row and row["status"] == "uncertain":
            if QMessageBox.question(self, "تأیید دستی", "وجود این فایل را در مقصد تلگرام بررسی و تأیید کرده‌اید؟") == QMessageBox.Yes:
                self.store.update(row["id"], status="sent", error="تأیید دستی کاربر", sent_at=datetime.now().timestamp())
                self.refresh()

    def closeEvent(self, event):
        if not self.engine.isRunning():
            event.accept()
            return
        event.ignore()
        if self.closing:
            return
        self.closing = True
        self.engine.pause_now()
        self.engine.answer(None)
        self.engine.submit("stop")
        self.update_controls()
        self.timing.setText("در حال بستن؛ منتظر پایان عملیات جاری…")
        self.exit_timer = QTimer(self)
        self.exit_timer.timeout.connect(self.finish_close)
        self.exit_timer.start(200)

    def finish_close(self):
        if not self.engine.isRunning():
            self.exit_timer.stop()
            self.close()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TelegramFolderPublisher")
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(STYLE)
    data = Path(os.environ.get("PUBLISHER_DATA_DIR") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TelegramFolderPublisher")
    data.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, "تلگرام‌یار", "یک نسخهٔ دیگر از برنامه باز است.")
        return
    window = Window(data)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
