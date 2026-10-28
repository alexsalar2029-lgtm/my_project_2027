from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTime, QTimer, QLockFile
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QSpinBox, QCheckBox, QTimeEdit, QPlainTextEdit,
    QGroupBox, QScrollArea, QMessageBox, QFrame, QSizePolicy)

from ui_base import Window as BaseWindow, button, ltr
from calendar_ui import DatePicker, display_instant
from core import next_due

STYLE = """
* {font-family:'Segoe UI',Tahoma; font-size:13px; color:#213550;}
QMainWindow,QWidget#root {background:#edf2f8;}
QLabel#hero {font-size:25px; font-weight:700; color:#152843;}
QLabel#sub {color:#677d97; font-size:13px;}
QLabel#badge {background:#e0eceb; color:#246259; padding:9px 16px; border-radius:8px;}
QLabel#headline {font-size:19px; font-weight:650; color:#152843;}
QLabel#hint {color:#70829a; font-size:12px;}
QLabel#next {background:#162e50; color:#f4f8ff; padding:16px 20px; border-radius:12px; font-size:15px;}
QLabel#error {background:#fff1ed; color:#ac4938; border:1px solid #f1d0c5; border-radius:8px; padding:9px;}
QLabel#stat {background:white; border:1px solid #dae3ee; border-radius:10px; padding:15px; font-size:17px; font-weight:600;}
QTabWidget::pane {border:0;}
QTabBar::tab {background:transparent; color:#617690; padding:13px 22px; border-bottom:3px solid transparent; margin-left:10px; font-weight:600;}
QTabBar::tab:selected {color:#1765b8; border-bottom:3px solid #297dd4;}
QTabBar::tab:hover {background:#e2eaf4;}
QGroupBox,QFrame#card {background:white; border:1px solid #dbe4ee; border-radius:12px;}
QGroupBox {margin-top:18px; padding:22px 16px 16px; font-weight:600;}
QGroupBox::title {subcontrol-origin:margin; subcontrol-position:top right; right:18px; padding:0 8px; color:#334e6d;}
QLineEdit,QComboBox,QSpinBox,QTimeEdit,QDateTimeEdit,QPlainTextEdit,QTextEdit {background:#f9fbfe; border:1px solid #d5dfeb; border-radius:7px; padding:9px; selection-background-color:#c5def8;}
QLineEdit:focus,QPlainTextEdit:focus {border:1px solid #468ed4;}
QPushButton {background:#fff; border:1px solid #cfdae7; border-radius:8px; padding:11px 16px; font-weight:600;}
QPushButton:hover {border-color:#4e8fcf; background:#edf5ff;}
QPushButton#primary {background:#246fc0; border-color:#246fc0; color:white;}
QPushButton#primary:hover {background:#195ea9;}
QPushButton#danger {background:#fff0ed; color:#ac4938; border-color:#efcfc6;}
QPushButton:disabled {color:#98a7b9; background:#e7edf4; border-color:#dce4ed;}
QCheckBox {spacing:8px; padding:4px 0;}
QCheckBox::indicator {width:17px; height:17px;}
QTableWidget {background:white; border:1px solid #d9e3ef; border-radius:10px; gridline-color:#edf2f7; alternate-background-color:#f8fafd; selection-background-color:#e1edfb; selection-color:#213550;}
QHeaderView::section {background:#e7eef7; color:#45627f; padding:12px 10px; border:0; font-weight:600;}
QProgressBar {border:0; background:#dbe5f0; border-radius:5px; height:20px; text-align:center;}
QProgressBar::chunk {background:#3a8cda; border-radius:5px;}
QScrollArea {background:transparent; border:0;}
QScrollBar:vertical {background:#edf2f8; width:8px;}
QScrollBar::handle:vertical {background:#b7c7d9; border-radius:4px; min-height:30px;}
"""

class Window(BaseWindow):
    def __init__(self, data):
        super().__init__(data)
        self.setWindowTitle('تلگرام‌یار ۲ | مدیریت انتشار')
        self.resize(1250, 940)
        self.setMinimumSize(1000, 760)
        self.centralWidget().findChild(QLabel,'hero').setText('تلگرام‌یار ۲')
        self.centralWidget().findChild(QLabel,'sub').setText('پوشه را بررسی کنید، پست را ببینید و زمان انتشار را دقیق انتخاب کنید.')
        layout=self.centralWidget().layout()
        hero=self.centralWidget().findChild(QLabel,'hero')
        subtitle=self.centralWidget().findChild(QLabel,'sub')
        for widget in [hero,subtitle,self.account_label]:layout.removeWidget(widget)
        header=QWidget()
        row=QHBoxLayout(header)
        row.setContentsMargins(0,0,0,0)
        brand=QVBoxLayout()
        brand.setSpacing(2)
        brand.addWidget(hero)
        brand.addWidget(subtitle)
        row.addLayout(brand,1)
        row.addWidget(self.account_label)
        layout.insertWidget(0,header)
        layout.setContentsMargins(22,16,22,14)
        layout.setSpacing(8)
        self.tabs.setTabText(0, 'اتصال حساب')
        self.tabs.setTabText(1, 'داشبورد انتشار')
        self.tabs.setTabText(2, 'فایل‌ها و پیش‌نمایش')
        self.tabs.setTabText(3, 'گزارش و خطاها')
        self.tabs.setCurrentIndex(1)
        self.engine.error.connect(self.show_error)
        self.engine.scan_status.connect(self.scan_status.setText)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_schedule_preview)
        self.clock_timer.start(1000)
        self.update_schedule_preview()

    def make_publish(self):
        outer = self.page('داشبورد انتشار')
        self.clock = QLabel()
        self.clock.setObjectName('hint')
        outer.addWidget(self.clock)
        self.next_label = QLabel('زمان انتشار بعدی اینجا نمایش داده می‌شود.')
        self.next_label.setObjectName('next')
        self.next_label.setWordWrap(True)
        outer.addWidget(self.next_label)
        self.error_banner = QLabel()
        self.error_banner.setObjectName('error')
        self.error_banner.setTextFormat(Qt.PlainText)
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        outer.addWidget(self.error_banner)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet('QWidget#dashboardBody {background:transparent;}')
        body.setObjectName('dashboardBody')
        grid = QGridLayout(body)
        grid.setContentsMargins(0,0,0,0)
        grid.setSpacing(16)
        scroll.setWidget(body)
        outer.addWidget(scroll,1)

        source = QGroupBox('پوشهٔ فایل‌ها')
        source.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Maximum)
        layout = QVBoxLayout(source)
        row = QHBoxLayout()
        self.folder = ltr(QLineEdit(self.config['folder']))
        self.folder.setPlaceholderText('پوشهٔ فایل‌ها را انتخاب کنید')
        pick = button('انتخاب پوشه',self.pick_folder)
        row.addWidget(self.folder,1)
        row.addWidget(pick)
        layout.addLayout(row)
        self.recursive = QCheckBox('زیرپوشه‌ها هم بررسی شوند')
        self.recursive.setChecked(self.config['recursive'])
        layout.addWidget(self.recursive)
        destination = QGroupBox('مقصد انتشار')
        destination_layout = QVBoxLayout(destination)
        row = QHBoxLayout()
        self.target = QComboBox()
        self.target.setEditable(True)
        self.target.addItem('پیام‌های ذخیره‌شدهٔ من','me')
        if self.config.get('target','me') != 'me':
            self.target.addItem(self.config['target'],self.config['target'])
            self.target.setCurrentIndex(1)
        self.dialogs_button = button('دریافت مقصدها',lambda:self.engine.submit('dialogs'))
        row.addWidget(QLabel('انتشار در'))
        row.addWidget(self.target,1)
        row.addWidget(self.dialogs_button)
        destination_layout.addLayout(row)
        self.dest_label = QLabel('مقصد ارسال هنوز بررسی نشده است.')
        self.dest_label.setObjectName('hint')
        self.dest_label.setTextFormat(Qt.PlainText)
        self.dest_label.setWordWrap(True)
        destination_layout.addWidget(self.dest_label)
        destination_layout.addWidget(QLabel('گفت‌وگو یا کانالی را انتخاب کنید که اجازهٔ ارسال در آن دارید.'))
        self.scan_status = QLabel('برای دیدن فایل‌ها به اتصال تلگرام نیاز ندارید؛ «بررسی پوشه» را بزنید.')
        self.scan_status.setWordWrap(True)
        self.scan_status.setObjectName('hint')
        layout.addWidget(self.scan_status)
        grid.addWidget(source,0,0)
        grid.addWidget(destination,0,1)

        schedule = QGroupBox('۲  زمان انتشار')
        sl = QVBoxLayout(schedule)
        self.use_date = QCheckBox('شروع از تاریخ و ساعت مشخص')
        self.use_date.setChecked(bool(self.config.get('not_before')))
        sl.addWidget(self.use_date)
        self.zone = QComboBox()
        self.zone.addItems(['Asia/Tehran','UTC'])
        self.zone.setCurrentText(self.config['timezone'])
        self.zone.setLayoutDirection(Qt.LeftToRight)
        self.date = DatePicker(self.config.get('not_before',''),self.zone.currentText(),self.config.get('calendar','jalali'))
        self.zone.currentTextChanged.connect(self.zone_changed)
        self.date.setEnabled(self.use_date.isChecked())
        self.use_date.toggled.connect(self.date.setEnabled)
        sl.addWidget(self.date)
        zr = QHBoxLayout()
        zr.addWidget(QLabel('منطقهٔ زمانی'))
        zr.addWidget(self.zone,1)
        sl.addLayout(zr)
        ir = QHBoxLayout()
        ir.addWidget(QLabel('یک فایل، هر'))
        self.interval = QSpinBox()
        self.interval.setRange(1,10080)
        self.interval.setValue(self.config['interval'])
        self.interval.setSuffix(' دقیقه')
        ir.addWidget(self.interval,1)
        sl.addLayout(ir)
        self.window_enabled = QCheckBox('فقط در این بازهٔ روزانه ارسال شود')
        self.window_enabled.setChecked(self.config.get('window_enabled',self.config['start']!=self.config['end']))
        sl.addWidget(self.window_enabled)
        tr=QHBoxLayout()
        self.start_time=ltr(QTimeEdit(QTime.fromString(self.config['start'],'HH:mm')))
        self.end_time=ltr(QTimeEdit(QTime.fromString(self.config['end'],'HH:mm')))
        for w in [self.start_time,self.end_time]:
            w.setDisplayFormat('HH:mm')
            w.setEnabled(self.window_enabled.isChecked())
            self.window_enabled.toggled.connect(w.setEnabled)
        tr.addWidget(QLabel('از'))
        tr.addWidget(self.start_time)
        tr.addWidget(QLabel('تا'))
        tr.addWidget(self.end_time)
        sl.addLayout(tr)
        self.days={}
        dr=QHBoxLayout()
        for day,name in [(5,'ش'),(6,'ی'),(0,'د'),(1,'س'),(2,'چ'),(3,'پ'),(4,'ج')]:
            w=QCheckBox(name)
            w.setToolTip(['دوشنبه','سه‌شنبه','چهارشنبه','پنجشنبه','جمعه','شنبه','یکشنبه'][day])
            w.setChecked(day in self.config['days'])
            self.days[day]=w
            dr.addWidget(w)
        sl.addLayout(dr)
        note=QLabel('بازهٔ غیرفعال یعنی تمام روز. برنامه برای زمان‌بندی باید باز بماند.')
        note.setObjectName('hint')
        note.setWordWrap(True)
        sl.addWidget(note)
        sl.addStretch()
        grid.addWidget(schedule,1,0)

        caption=QGroupBox('۳  عنوان و پیش‌نمایش متن')
        cl=QVBoxLayout(caption)
        self.template=QPlainTextEdit(self.config['template'])
        self.template.setMaximumHeight(110)
        cl.addWidget(self.template)
        hint=QLabel('{title} عنوان    {type} نوع    {size} حجم\n{filename} نام اصلی فایل')
        hint.setObjectName('hint')
        hint.setWordWrap(True)
        cl.addWidget(hint)
        self.as_document=QCheckBox('همهٔ فایل‌ها به‌صورت سند و با نام اصلی ارسال شوند')
        self.as_document.setChecked(self.config.get('as_document',False))
        cl.addWidget(self.as_document)
        self.auto_scan=QCheckBox('فایل‌های تازهٔ پوشه خودکار وارد صف شوند')
        self.auto_scan.setChecked(self.config['auto_scan'])
        cl.addWidget(self.auto_scan)
        info=QLabel('نوع فایل از محتوا تشخیص داده می‌شود. عنوان‌ها از نام فایل و اطلاعات PDF یا صوت ساخته می‌شوند؛ در صف قابل ویرایش‌اند.')
        info.setWordWrap(True)
        info.setObjectName('hint')
        cl.addWidget(info)
        preview=button('دیدن فایل‌ها و ویرایش عنوان',lambda:self.tabs.setCurrentIndex(2))
        cl.addWidget(preview)
        cl.addStretch()
        grid.addWidget(caption,1,1)
        grid.setColumnStretch(0,1)
        grid.setColumnStretch(1,1)

        actions=QHBoxLayout()
        self.scan_button=button('بررسی پوشه',lambda:self.prepare(False))
        self.start_button=button('شروع انتشار زمان‌بندی‌شده',lambda:self.prepare(True),True)
        self.pause_button=button('توقف',self.pause)
        self.pause_button.setObjectName('danger')
        self.pause_button.setEnabled(False)
        for b in [self.scan_button,self.start_button,self.pause_button]:actions.addWidget(b)
        outer.addLayout(actions)
        self.controls += [self.folder,pick,self.recursive,self.target,self.dialogs_button,self.zone,
            self.interval,self.use_date,self.date,self.window_enabled,self.start_time,self.end_time,
            *self.days.values(),self.template,self.as_document,self.auto_scan,self.scan_button,self.start_button]

    def make_queue(self):
        super().make_queue()
        page=self.tabs.widget(2).layout()
        actions=QHBoxLayout()
        self.now_button=button('ارسال فایل انتخابی اکنون',lambda:self.send_selected(False),True)
        self.test_button=button('ارسال آزمایشی انتخابی به خودم',lambda:self.send_selected(True))
        actions.addWidget(self.now_button)
        actions.addWidget(self.test_button)
        actions.addStretch()
        page.insertLayout(1,actions)
        self.controls += [self.now_button,self.test_button]
        self.detail.setText('«بررسی پوشه» فایل‌ها را بدون ورود تلگرام پیدا می‌کند. سپس ردیف دلخواه را انتخاب کنید.')
        preview=QFrame()
        preview.setObjectName('card')
        preview.setMaximumHeight(130)
        row=QHBoxLayout(preview)
        self.thumbnail=QLabel('فایل')
        self.thumbnail.setFixedSize(100,100)
        self.thumbnail.setAlignment(Qt.AlignCenter)
        self.preview_text=QLabel('یک فایل را از جدول انتخاب کنید تا پیش‌نمایش پست را ببینید.')
        self.preview_text.setTextFormat(Qt.PlainText)
        self.preview_text.setWordWrap(True)
        row.addWidget(self.thumbnail)
        row.addWidget(self.preview_text,1)
        page.insertWidget(3,preview)

    def show_detail(self):
        super().show_detail()
        if not hasattr(self,'thumbnail'):return
        row=self.selected()
        if not row:return
        from core import caption,KINDS
        from PySide6.QtGui import QPixmap
        pixmap=QPixmap(row['path']) if row['kind']=='photo' else QPixmap()
        if pixmap.isNull():
            self.thumbnail.clear()
            self.thumbnail.setText(KINDS[row['kind']])
        else:self.thumbnail.setPixmap(pixmap.scaled(100,100,Qt.KeepAspectRatio,Qt.SmoothTransformation))
        self.preview_text.setText(caption(row,{**self.config,'template':self.template.toPlainText()}))

    def schedule_config(self):
        days=[d for d,w in self.days.items() if w.isChecked()]
        if not days:raise ValueError('دست‌کم یک روز انتشار را انتخاب کنید.')
        self.date.zone=self.zone.currentText()
        try:
            first=self.date.instant().isoformat() if self.use_date.isChecked() else ''
        except ValueError:
            raise ValueError('تاریخ واردشده معتبر نیست؛ سال، ماه و روز را بررسی کنید.')
        return {**self.config,'timezone':self.zone.currentText(),'calendar':self.date.calendar.currentData(),
            'days':days,'not_before':first,'interval':self.interval.value(),
            'window_enabled':self.window_enabled.isChecked(),
            'start':self.start_time.time().toString('HH:mm') if self.window_enabled.isChecked() else '00:00',
            'end':self.end_time.time().toString('HH:mm') if self.window_enabled.isChecked() else '00:00'}

    def zone_changed(self,zone):
        try:
            instant=self.date.instant()
            self.date.zone=zone
            self.date.set_instant(instant)
        except ValueError:
            self.date.zone=zone

    def read_config(self):
        config=self.schedule_config()
        folder=Path(self.folder.text().strip())
        if not folder.is_dir():raise ValueError('ابتدا یک پوشهٔ معتبر انتخاب کنید.')
        index=self.target.currentIndex()
        target=self.target.currentData() if index>=0 and self.target.currentText()==self.target.itemText(index) else self.target.currentText()
        if not target:raise ValueError('مقصد انتشار را انتخاب کنید.')
        return {**config,'folder':str(folder.resolve()),'target':str(target).strip(),
            'recursive':self.recursive.isChecked(),'template':self.template.toPlainText(),
            'as_document':self.as_document.isChecked(),'auto_scan':self.auto_scan.isChecked(),
            'api_id':self.api_id.text().strip(),'version':2}

    def prepare(self,start):
        try:config=self.read_config()
        except ValueError as exc:
            self.show_error(str(exc));return
        self.error_banner.hide()
        self.config=config
        self.engine.submit('start' if start else 'inspect',config)
        if not start:self.tabs.setCurrentIndex(2)

    def send_selected(self,to_self):
        row=self.selected()
        if not row:
            self.show_error('در جدول، یک فایل را برای ارسال انتخاب کنید.');return
        try:config=self.read_config()
        except ValueError as exc:
            self.show_error(str(exc));return
        if to_self:config['target']='me'
        self.error_banner.hide()
        self.engine.submit('send_now',{'config':config,'row':dict(row)})

    def show_error(self,text):
        self.error_banner.setText(text)
        self.error_banner.show()
        self.statusBar().showMessage(text)
        if self.tabs.currentIndex()!=1:
            QMessageBox.warning(self,'عملیات انجام نشد',text)

    def update_schedule_preview(self):
        try:
            config=self.schedule_config()
            now=datetime.now(timezone.utc)
            self.clock.setText('اکنون: '+display_instant(now,config['timezone'],config['calendar'])+'   |   '+config['timezone'])
            due=next_due(now,config,self.engine.next_at if self.is_active else 0)
            if not due:self.next_label.setText('روز مجازی برای ارسال انتخاب نشده است.')
            elif (due-now).total_seconds()<2:
                self.next_label.setText('نخستین فایل آماده: بلافاصله پس از شروع انتشار')
            else:self.next_label.setText('زمان نخستین انتشار مجاز: '+display_instant(due,config['timezone'],config['calendar']))
        except ValueError as exc:self.next_label.setText(str(exc))

    def refresh(self):
        super().refresh()
        from PySide6.QtWidgets import QTableWidgetItem
        config=self.config
        calendar=config.get('calendar','jalali')
        self.table.setHorizontalHeaderItem(5,QTableWidgetItem('زمان انتشار · '+('شمسی' if calendar=='jalali' else 'میلادی')))
        due=next_due(datetime.now(timezone.utc),config,self.engine.next_at if hasattr(self,'engine') else 0)
        for i,row in enumerate(self.rows):
            text='—'
            if row['sent_at']:
                text=display_instant(datetime.fromtimestamp(row['sent_at'],timezone.utc),config['timezone'],calendar)
            elif row['status']=='queued' and due:
                text='برنامه: '+display_instant(due,config['timezone'],calendar)
                due=next_due(due,config,due.timestamp()+config['interval']*60)
            self.table.setItem(i,5,QTableWidgetItem(text))

    def set_busy(self,value):
        super().set_busy(value)
        if not value:
            self.date.setEnabled(self.use_date.isChecked() and not self.is_active)
            for w in [self.start_time,self.end_time]:w.setEnabled(self.window_enabled.isChecked() and not self.is_active)

def main():
    app=QApplication(sys.argv)
    app.setApplicationName('TelegramFolderPublisher')
    app.setStyle('Fusion')
    app.setLayoutDirection(Qt.RightToLeft)
    app.setFont(QFont('Segoe UI',10))
    app.setStyleSheet(STYLE)
    data=Path(os.environ.get('PUBLISHER_DATA_DIR') or Path(os.environ.get('LOCALAPPDATA',Path.home()))/'TelegramFolderPublisher')
    data.mkdir(parents=True,exist_ok=True)
    lock=QLockFile(str(data/'app.lock'))
    if not lock.tryLock(100):
        QMessageBox.information(None,'تلگرام‌یار','یک نسخهٔ دیگر از برنامه باز است.');return
    window=Window(data)
    window.show()
    sys.exit(app.exec())

if __name__=='__main__':main()
