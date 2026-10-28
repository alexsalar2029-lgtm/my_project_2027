from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import jdatetime
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QSpinBox, QComboBox, QTimeEdit, QLabel

DIGITS = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')

def display_instant(value: datetime, zone='Asia/Tehran', calendar='jalali'):
    local = value.astimezone(ZoneInfo(zone))
    shown = jdatetime.datetime.fromgregorian(datetime=local) if calendar == 'jalali' else local
    return shown.strftime('%Y/%m/%d  %H:%M:%S').translate(DIGITS)

def chosen_instant(year, month, day, hour, minute, calendar='jalali', zone='Asia/Tehran'):
    if calendar == 'jalali':
        gregorian = jdatetime.date(year, month, day).togregorian()
        year, month, day = gregorian.year, gregorian.month, gregorian.day
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(zone)).astimezone(timezone.utc)

class DatePicker(QWidget):
    changed = Signal()
    def __init__(self, iso='', zone='Asia/Tehran', calendar='jalali'):
        super().__init__()
        self.zone = zone
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        self.calendar = QComboBox()
        self.calendar.addItem('شمسی', 'jalali')
        self.calendar.addItem('میلادی', 'gregorian')
        self.calendar.setCurrentIndex(0 if calendar == 'jalali' else 1)
        self.year, self.month, self.day = QSpinBox(), QSpinBox(), QSpinBox()
        self.year.setRange(1300, 2200)
        self.month.setRange(1, 12)
        self.day.setRange(1, 31)
        self.time = QTimeEdit()
        self.time.setDisplayFormat('HH:mm')
        self.time.setLayoutDirection(Qt.LeftToRight)
        self.time.setMinimumWidth(90)
        self.date_group = QWidget()
        date_row = QHBoxLayout(self.date_group)
        date_row.setContentsMargins(0, 0, 0, 0)
        self.date_group.setLayoutDirection(Qt.LeftToRight)
        for w in [self.year, QLabel('/'), self.month, QLabel('/'), self.day]:
            date_row.addWidget(w)
        row.addWidget(self.calendar)
        row.addWidget(self.date_group)
        row.addWidget(self.time)
        value = datetime.fromisoformat(iso) if iso else datetime.now(timezone.utc)
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo(zone))
        self.set_instant(value)
        self.previous_calendar = self.calendar.currentData()
        self.calendar.currentIndexChanged.connect(self.switch_calendar)
        for w in [self.year, self.month, self.day]:
            w.valueChanged.connect(self.changed)
        self.time.timeChanged.connect(self.changed)

    def set_instant(self, instant):
        local = instant.astimezone(ZoneInfo(self.zone))
        shown = jdatetime.datetime.fromgregorian(datetime=local) if self.calendar.currentData() == 'jalali' else local
        self.year.setValue(shown.year)
        self.month.setValue(shown.month)
        self.day.setValue(shown.day)
        self.time.setTime(QTime(local.hour, local.minute))

    def instant(self):
        return chosen_instant(self.year.value(), self.month.value(), self.day.value(),
                              self.time.time().hour(), self.time.time().minute(),
                              self.calendar.currentData(), self.zone)

    def switch_calendar(self):
        try:
            instant = chosen_instant(self.year.value(), self.month.value(), self.day.value(),
                self.time.time().hour(), self.time.time().minute(), self.previous_calendar, self.zone)
            self.set_instant(instant)
        except ValueError:
            self.set_instant(datetime.now(timezone.utc))
        self.previous_calendar = self.calendar.currentData()
        self.changed.emit()
