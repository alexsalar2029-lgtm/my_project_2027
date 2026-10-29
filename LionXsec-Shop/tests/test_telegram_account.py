import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from assistant import read_config, save_config
from server import Store
from telegram_account import checkpoint, document_thumbs, image_data, invite_hash, last_position, media_details, rescan_history, sync_history, video_frame_times


CHAT={'id':-1001234567890,'username':'my_channel'}


class HistoryClient:
    def __init__(self,messages):
        self.messages=messages
        self.calls=[]
    async def iter_messages(self,entity,**options):
        self.calls.append(options)
        messages=[m for m in self.messages if m.id>options.get('min_id',0)]
        messages.sort(key=lambda m:m.id,reverse=not options.get('reverse',False))
        limit=options.get('limit')
        for msg in messages if limit is None else messages[:limit]:
            yield msg


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'shop.sqlite3')
    def tearDown(self):
        self.temp.cleanup()
    def messages(self,start,end):
        return [SimpleNamespace(id=i,message='Post '+str(i)) for i in range(start,end+1)]
    def test_initial_window_then_restart_catches_all_gap_messages(self):
        client=HistoryClient(self.messages(1,6))
        asyncio.run(sync_history(client,None,self.store,CHAT,limit=2))
        self.assertEqual(last_position(self.store,CHAT['id']),6)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assistant_jobs').fetchone()[0],2)
        reopened=Store(self.store.path)
        client=HistoryClient(self.messages(1,15))
        asyncio.run(sync_history(client,None,reopened,CHAT,limit=2))
        self.assertEqual(client.calls[0],{'min_id':6,'reverse':True,'limit':None})
        with reopened.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assistant_jobs').fetchone()[0],11)

    def test_all_history_and_bot_compatible_keys(self):
        client=HistoryClient(self.messages(1,8))
        asyncio.run(sync_history(client,None,self.store,CHAT,limit=0))
        checkpoint(self.store,CHAT,SimpleNamespace(id=8,message='Post 8'))
        with self.store.db() as db:
            rows=db.execute('SELECT key FROM assistant_jobs').fetchall()
        self.assertEqual(len(rows),8)
        self.assertIn('-1001234567890:8',[r[0] for r in rows])

    def test_disabled_configuration_stops_history_without_acking(self):
        asyncio.run(sync_history(HistoryClient(self.messages(1,8)),None,self.store,CHAT,limit=0,keep_going=lambda:False))
        self.assertEqual(last_position(self.store,CHAT['id']),0)

    def test_rescan_requeues_old_window_without_moving_cursor_backwards(self):
        client=HistoryClient(self.messages(1,10))
        checkpoint(self.store,CHAT,SimpleNamespace(id=10,message='Post 10'))
        asyncio.run(rescan_history(client,None,self.store,CHAT,limit=3))
        self.assertEqual(last_position(self.store,CHAT['id']),10)
        with self.store.db() as db:
            self.assertEqual([row[0] for row in db.execute('SELECT message FROM assistant_jobs ORDER BY message')],[8,9,10])

    def test_edit_keeps_watermark_and_requeues_same_message(self):
        checkpoint(self.store,CHAT,SimpleNamespace(id=10,message='Old post'))
        checkpoint(self.store,CHAT,SimpleNamespace(id=5,message='Edited earlier post'),advance=False)
        self.assertEqual(last_position(self.store,CHAT['id']),10)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT text FROM assistant_jobs WHERE message=5').fetchone()[0],'Edited earlier post')

    def test_service_message_advances_without_generating_content(self):
        checkpoint(self.store,CHAT,SimpleNamespace(id=10))
        self.assertEqual(last_position(self.store,CHAT['id']),10)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assistant_jobs').fetchone()[0],0)

    def test_private_invite_and_video_metadata_are_recognized(self):
        self.assertEqual(invite_hash('https://t.me/+AbCdEfGhIjKlMnOp'),'AbCdEfGhIjKlMnOp')
        self.assertEqual(invite_hash('https://example.com/+AbCdEfGhIjKlMnOp'),'')
        attribute=SimpleNamespace(duration=12,file_name='offer.mp4')
        message=SimpleNamespace(video=True,gif=None,photo=None,audio=None,voice=None,
                                document=SimpleNamespace(attributes=[attribute]),sticker=None)
        kind,details=media_details(message)
        self.assertEqual(kind,'video')
        self.assertIn('duration: 12 seconds',details)
        self.assertTrue(image_data(b'\xff\xd8\xfftest').startswith('data:image/jpeg;base64,'))
        self.assertEqual(video_frame_times(10),[0,5.0,9.5])
        self.assertEqual(video_frame_times(1),[0])

    def test_offer_image_sent_as_document_exposes_a_thumbnail(self):
        message=SimpleNamespace(video=None,gif=None,photo=None,audio=None,voice=None,sticker=None,
                                document=SimpleNamespace(attributes=[],thumbs=[object()]))
        kind,details=media_details(message)
        self.assertEqual(kind,'document')
        self.assertTrue(document_thumbs(message))
        sticker=SimpleNamespace(video=None,gif=None,photo=None,audio=None,voice=None,document=None,
                                sticker=SimpleNamespace(thumbs=[object()]))
        self.assertEqual(media_details(sticker)[0],'sticker')
        self.assertTrue(document_thumbs(sticker))
        self.assertFalse(document_thumbs(SimpleNamespace(video=None,gif=None,photo=None,audio=None,
                                voice=None,document=None,sticker=None)))

    def test_account_mode_needs_app_credentials_but_not_bot_token(self):
        data={'enabled':True,'source':'account','channel':'@my_channel','model':'gpt-4.1-mini','api_key':'local-test-api-key'}
        with self.assertRaises(ValueError):
            save_config(self.store,data)
        response=save_config(self.store,{**data,'telegram_api_id':'123456','telegram_api_hash':'a'*32})
        self.assertNotIn('telegram_api_hash',response)
        self.assertTrue(response['telegram_api_hash_set'])
        self.assertEqual(response['source'],'account')
        self.assertEqual(read_config(self.store)['bot_token'],'')
        save_config(self.store,{**data,'telegram_api_id':'','telegram_api_hash':''})
        self.assertEqual(read_config(self.store)['telegram_api_hash'],'a'*32)

    def test_invalid_api_id_hash_and_source_rejected(self):
        base={'enabled':False,'source':'account','channel':'@my_channel','model':'gpt-4.1-mini'}
        for update in ({'telegram_api_id':'abc'},{'telegram_api_hash':'not-a-hash'},{'source':'unknown'}):
            with self.subTest(update=update),self.assertRaises(ValueError):
                save_config(self.store,base|update)


if __name__=='__main__':
    unittest.main()
