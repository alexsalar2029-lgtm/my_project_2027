import asyncio
import base64
import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from telethon.tl import types
from core import DEFAULTS, next_due, digest, inspect_file, Store
from media import telegram_media
from calendar_ui import chosen_instant, display_instant

class CalendarTests(unittest.TestCase):
    def test_jalali_date_is_converted_to_utc_once(self):
        self.assertEqual(chosen_instant(1405,8,6,10,0).isoformat(),'2026-10-28T06:30:00+00:00')
    def test_midnight_in_tehran_has_next_calendar_day(self):
        result=display_instant(datetime(2026,10,27,21,0,tzinfo=timezone.utc))
        self.assertTrue(result.startswith('۱۴۰۵/۰۸/۰۶'))
        self.assertTrue(result.endswith('۰۰:۳۰:۰۰'))
    def test_invalid_jalali_date_is_rejected(self):
        with self.assertRaises(ValueError):chosen_instant(1405,12,30,9,0)
    def test_next_due_uses_tehran_not_host_timezone(self):
        config={**DEFAULTS,'start':'09:00','end':'22:00'}
        due=next_due(datetime(2026,10,28,1,tzinfo=timezone.utc),config)
        self.assertEqual(due,datetime(2026,10,28,5,30,tzinfo=timezone.utc))
    def test_next_due_skips_closed_window(self):
        config={**DEFAULTS,'start':'09:00','end':'10:00','timezone':'UTC','days':[0]}
        due=next_due(datetime(2026,10,26,11,tzinfo=timezone.utc),config)
        self.assertEqual(due,datetime(2026,11,2,9,tzinfo=timezone.utc))
    def test_not_before_is_preserved_when_window_opens(self):
        config={**DEFAULTS,'not_before':'2026-10-29T06:30:00+00:00'}
        due=next_due(datetime(2026,10,28,tzinfo=timezone.utc),config)
        self.assertEqual(due,datetime(2026,10,29,6,30,tzinfo=timezone.utc))

class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.upload=types.InputFile(1,1,'picture.bin','test')
        self.row={'path':'picture.bin','title':'عنوان','kind':'photo','mime':'image/png','size':100}
    def test_png_with_bin_extension_is_sent_as_photo(self):
        self.assertIsInstance(telegram_media(self.upload,self.row),types.InputMediaUploadedPhoto)
    def test_document_override_preserves_original_filename(self):
        media=telegram_media(self.upload,self.row,True)
        self.assertIsInstance(media,types.InputMediaUploadedDocument)
        self.assertEqual(media.attributes[0].file_name,'picture.bin')
    def test_large_image_uses_document(self):
        self.assertIsInstance(telegram_media(self.upload,{**self.row,'size':11*1024**2}),types.InputMediaUploadedDocument)
    def test_audio_has_audio_attribute(self):
        media=telegram_media(self.upload,{**self.row,'mime':'audio/mpeg','kind':'audio'})
        self.assertTrue(any(isinstance(a,types.DocumentAttributeAudio) for a in media.attributes))
    def test_unsupported_image_is_preserved_as_document(self):
        self.assertIsInstance(telegram_media(self.upload,{**self.row,'mime':'image/heic'}),types.InputMediaUploadedDocument)

class GuiFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app=QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
    def setUp(self):
        from app import Window
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        data=self.root/'data';data.mkdir()
        self.source=self.root/'source';self.source.mkdir()
        from PySide6.QtGui import QImage
        image=QImage(32,32,QImage.Format_RGB32)
        image.fill(0xff287bc0)
        self.assertTrue(image.save(str(self.source/'تصویر_اول.bin'),'PNG'))
        self.window=Window(data)
        self.window.folder.setText(str(self.source))
        self.window.show()
    def wait_for(self,predicate,seconds=8):
        from PySide6.QtTest import QTest
        import time
        until=time.monotonic()+seconds
        while not predicate() and time.monotonic()<until:QTest.qWait(50)
        self.assertTrue(predicate(),'Timed out waiting for GUI/engine result')
    def tearDown(self):
        self.window.close()
        self.wait_for(lambda:not self.window.engine.isRunning())
        self.window.clock_timer.stop()
        self.window.deleteLater()
        self.app.processEvents()
        self.temp.cleanup()
    def test_offline_scan_title_edit_and_immediate_publish(self):
        window=self.window
        window.prepare(False)
        self.wait_for(lambda:len(window.rows)==1 and not window.is_busy)
        self.assertEqual(window.rows[0]['kind'],'photo')
        self.assertTrue(window.scope.startswith('preview:'))
        window.store.update(window.rows[0]['id'],title='عنوان انتخابی من')
        window.refresh()
        window.table.selectRow(0)
        class FakeTelegram:
            sent=[]
            async def is_user_authorized(self):return True
            async def get_me(self):return types.User(id=101,is_self=True,first_name='Test')
            async def get_entity(self,target):return await self.get_me()
            async def get_input_entity(self,target):return types.InputPeerUser(101,0)
            async def disconnect(self):pass
            async def upload_file(self,path,file_name,progress_callback):
                assert Path(path).read_bytes()==(self_source/'تصویر_اول.bin').read_bytes()
                await progress_callback(100,100)
                return types.InputFile(1,1,file_name,'test')
            async def send_file(self,target,media,caption,parse_mode):
                self.sent.append((target,media,caption))
                return SimpleNamespace(id=501)
        self_source=self.source
        fake=FakeTelegram()
        window.engine.client=fake
        window.send_selected(True)
        self.wait_for(lambda:any(r['status']=='sent' for r in window.store.rows('101:101')))
        self.assertEqual(len(fake.sent),1)
        self.assertIsInstance(fake.sent[0][1],types.InputMediaUploadedPhoto)
        self.assertIn('عنوان انتخابی من',fake.sent[0][2])
    def test_calendar_switch_preserves_the_selected_instant(self):
        window=self.window
        picker=window.date
        picker.year.setValue(1405);picker.month.setValue(8);picker.day.setValue(6)
        from PySide6.QtCore import QTime
        picker.time.setTime(QTime(10,0))
        expected=picker.instant()
        picker.calendar.setCurrentIndex(1)
        self.assertEqual(picker.instant(),expected)
        self.assertEqual(picker.year.value(),2026)

    def test_worker_waits_for_scheduled_instant_before_publishing(self):
        window=self.window
        class FakeTelegram:
            sent_at=None
            async def is_user_authorized(self):return True
            async def get_me(self):return types.User(id=101,is_self=True,first_name='Test')
            async def get_entity(self,target):return await self.get_me()
            async def get_input_entity(self,target):return types.InputPeerUser(101,0)
            async def disconnect(self):pass
            async def upload_file(self,path,file_name,**kwargs):return types.InputFile(1,1,file_name,'test')
            async def send_file(self,*args,**kwargs):
                self.sent_at=datetime.now(timezone.utc)
                return SimpleNamespace(id=502)
        fake=FakeTelegram()
        window.engine.client=fake
        due=datetime.now(timezone.utc)+timedelta(seconds=4)
        config={**window.read_config(),'not_before':due.isoformat()}
        window.engine.submit('start',config)
        self.wait_for(lambda:window.engine.active)
        self.assertIsNone(fake.sent_at)
        self.wait_for(lambda:fake.sent_at is not None)
        self.assertGreaterEqual(fake.sent_at,due)

    def test_timezone_switch_preserves_selected_instant(self):
        picker=self.window.date
        expected=picker.instant()
        self.window.zone.setCurrentText('UTC')
        self.assertEqual(picker.instant(),expected)

if __name__=='__main__':unittest.main()
