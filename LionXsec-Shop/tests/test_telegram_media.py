import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from automation import process_one, public_posts, requeue_failed, status
from server import Store
from telegram_account import MediaLoader, checkpoint, last_position, retry_pending_media, sync_history
from telegram_media import message_payload, message_revision, video_frames

CHAT={'id':-1001234567890,'username':'my_channel'}
JPEG=b'\xff\xd8\xffpreview'
TelegramTimeout=type('TimeoutError',(Exception,),{})
FloodWaitError=type('FloodWaitError',(Exception,),{})
FileReferenceExpiredError=type('FileReferenceExpiredError',(Exception,),{})


def photo(mid=1,text='Spotify Premium 1 month'):
    return SimpleNamespace(id=mid,message=text,edit_date=None,photo=SimpleNamespace(id=mid),document=None)


def video(mid=1):
    return SimpleNamespace(id=mid,message='Product tutorial',edit_date=None,video=True,
        document=SimpleNamespace(id=mid,thumbs=[object()],attributes=[SimpleNamespace(duration=3)]),
        file=SimpleNamespace(size=100))


class DownloadTests(unittest.IsolatedAsyncioTestCase):
    async def test_telegram_get_file_timeout_is_not_silently_accepted(self):
        client=SimpleNamespace(download_media=AsyncMock(side_effect=TelegramTimeout('PRIVATE raw RPC error')))
        payload=await message_payload(client,photo())
        self.assertEqual(payload['media_error'],'telegram_media_timeout')
        self.assertEqual(payload['media'],[])
        self.assertNotIn('PRIVATE',json.dumps(payload))

    async def test_photo_deadline_cancels_the_stuck_download(self):
        cancelled=[]
        async def stuck(*args,**kwargs):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
        with patch('telegram_media.IMAGE_TIMEOUT',0.01):
            payload=await message_payload(SimpleNamespace(download_media=stuck),photo())
        self.assertEqual(cancelled,[True])
        self.assertEqual(payload['media_error'],'telegram_media_timeout')

    async def test_video_rpc_failure_still_tries_independent_thumbnail(self):
        client=SimpleNamespace(download_media=AsyncMock(side_effect=[TelegramTimeout('PRIVATE'),JPEG]))
        payload=await message_payload(client,video())
        self.assertNotIn('media_error',payload)
        self.assertEqual(len(payload['media']),1)
        self.assertIn('thumbnail only',payload['media_description'])
        self.assertEqual(client.download_media.call_args_list[-1].kwargs,{'file':bytes,'thumb':-1})

    async def test_failed_video_and_thumbnail_remain_retryable(self):
        client=SimpleNamespace(download_media=AsyncMock(side_effect=TelegramTimeout('PRIVATE')))
        payload=await message_payload(client,video())
        self.assertEqual(payload['media_error'],'telegram_media_timeout')
        self.assertEqual(client.download_media.call_count,2)

    async def test_video_download_timeout_removes_partial_file(self):
        paths=[]
        async def download(message,file):
            path=Path(file)
            path.write_bytes(b'partial')
            paths.append(path)
            await asyncio.Event().wait()
        with patch('telegram_media.VIDEO_TIMEOUT',0.01):
            with self.assertRaises(TimeoutError):
                await video_frames(SimpleNamespace(download_media=download),video())
        self.assertTrue(paths)
        self.assertFalse(paths[0].parent.exists())

    async def test_stuck_ffmpeg_is_killed_and_temporary_directory_is_removed(self):
        paths=[]
        async def download(message,file):
            Path(file).write_bytes(b'video fixture')
            paths.append(Path(file))
            return file
        process=SimpleNamespace(returncode=None,wait=AsyncMock(side_effect=[TimeoutError(),0]),kill=Mock())
        with patch('telegram_media.asyncio.create_subprocess_exec',AsyncMock(return_value=process)):
            with self.assertRaises(TimeoutError):
                await video_frames(SimpleNamespace(download_media=download),video())
        process.kill.assert_called_once()
        self.assertEqual(process.wait.call_count,2)
        self.assertFalse(paths[0].parent.exists())

    async def test_flood_wait_is_propagated_without_thumbnail_or_post_failure(self):
        error=FloodWaitError('PRIVATE')
        error.seconds=25
        client=SimpleNamespace(download_media=AsyncMock(side_effect=error))
        with self.assertRaises(FloodWaitError):
            await message_payload(client,video())
        self.assertEqual(client.download_media.call_count,1)

    async def test_cancellation_is_not_converted_to_a_media_retry(self):
        client=SimpleNamespace(download_media=AsyncMock(side_effect=asyncio.CancelledError()))
        with self.assertRaises(asyncio.CancelledError):
            await message_payload(client,photo())

    async def test_account_session_errors_are_not_misreported_as_file_failures(self):
        for name,code in (('SessionRevokedError',401),('UnauthorizedError',401),
                          ('AuthKeyDuplicatedError',406),('AuthKeyNotFound',None)):
            error=type(name,(Exception,),{'code':code})('PRIVATE')
            client=SimpleNamespace(download_media=AsyncMock(side_effect=error))
            with self.subTest(name=name),self.assertRaises(type(error)):
                await message_payload(client,photo())

    async def test_text_only_posts_need_no_download(self):
        client=SimpleNamespace(download_media=AsyncMock())
        payload=await message_payload(client,SimpleNamespace(id=5,message='Spotify offer'))
        self.assertNotIn('media_error',payload)
        client.download_media.assert_not_called()


class HistoryClient:
    def __init__(self,messages):
        self.messages=messages
        self.download_media=AsyncMock(side_effect=TelegramTimeout('PRIVATE'))
        self.get_messages=AsyncMock(side_effect=lambda entity,ids:next((m for m in self.messages if m.id==ids),None))
    async def iter_messages(self,entity,**options):
        messages=sorted(self.messages,key=lambda m:m.id,reverse=not options.get('reverse',False))
        for message in messages[:options.get('limit')]:
            if message.id>options.get('min_id',0):
                yield message


def generated():
    localized=lambda text:dict.fromkeys(('fa','en','ar','es'),text)
    return {'kind':'sale','title':localized('Spotify Premium'),'summary':localized('One-month plan'),
            'body':localized('One-month plan'),'price':None}


class MediaQueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'shop.sqlite3')
        self.client=HistoryClient([photo(),SimpleNamespace(id=2,message='Netflix offer')])
        self.loader=MediaLoader(self.store,CHAT)
    def tearDown(self):
        self.temp.cleanup()
    async def receive(self,message,advance=True,loader=None):
        payload=await (loader or self.loader).payload(self.client,message)
        checkpoint(self.store,CHAT,message,advance=advance,payload=payload)
        return payload
    def due(self):
        with self.store.db() as db:
            db.execute("UPDATE assistant_jobs SET retry_at=0 WHERE status='waiting_media'")
    def ready(self):
        self.client.download_media.side_effect=None
        self.client.download_media.return_value=JPEG

    async def test_failed_media_does_not_block_later_posts_or_publish_metadata_only(self):
        await sync_history(self.client,None,self.store,CHAT,limit=0,payload_builder=self.loader.payload)
        self.assertEqual(last_position(self.store,CHAT['id']),2)
        self.assertEqual(status(self.store)['counts'],{'pending':1,'waiting_media':1})
        model=SimpleNamespace(analyze=Mock(return_value=generated()))
        self.assertTrue(process_one(self.store,model))
        self.assertFalse(process_one(self.store,model))
        self.assertEqual(model.analyze.call_count,1)
        self.assertEqual(public_posts(self.store)[0]['message_id'],2)

    async def test_retry_survives_restart_and_recovers_old_post_without_moving_cursor(self):
        await self.receive(photo())
        checkpoint(self.store,CHAT,SimpleNamespace(id=100,message='Latest post'))
        self.due();self.ready()
        reopened=Store(self.store.path)
        loader=MediaLoader(reopened,CHAT)
        await retry_pending_media(self.client,None,reopened,CHAT,payload_builder=loader.payload)
        self.client.get_messages.assert_awaited_once_with(None,ids=1)
        self.assertEqual(last_position(reopened,CHAT['id']),100)
        self.assertEqual(status(reopened)['counts'],{'pending':2})
        with reopened.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM assistant_media_pending').fetchone()[0],0)
            self.assertTrue(json.loads(db.execute('SELECT media FROM assistant_jobs WHERE message=1').fetchone()[0]))

    async def test_rescans_before_deadline_do_not_repeat_download_or_spend_attempts(self):
        await self.receive(photo())
        await self.receive(photo())
        await self.receive(photo(),loader=MediaLoader(self.store,CHAT))
        self.assertEqual(self.client.download_media.call_count,1)
        self.assertEqual(status(self.store)['recent'][0]['attempts'],1)
        self.assertEqual(status(self.store)['recent'][0]['error'],'telegram_media_timeout')

    async def test_success_is_cached_but_failure_is_not_cached_forever(self):
        await self.receive(photo())
        self.due();self.ready()
        await self.receive(photo())
        await self.receive(photo(),loader=MediaLoader(Store(self.store.path),CHAT))
        self.assertEqual(self.client.download_media.call_count,2)
        self.assertEqual(status(self.store)['counts'],{'pending':1})

    async def test_changed_message_bypasses_old_failure_deadline(self):
        await self.receive(photo())
        self.ready()
        changed=photo(text='Updated Spotify offer')
        await self.receive(changed)
        self.assertEqual(self.client.download_media.call_count,2)
        self.assertEqual(status(self.store)['counts'],{'pending':1})

    async def test_five_failures_wait_for_manual_media_retry_without_entering_ai_queue(self):
        for _ in range(5):
            self.due()
            await self.receive(photo())
        self.assertEqual(status(self.store)['counts'],{'media_failed':1})
        await self.receive(photo())
        self.assertEqual(self.client.download_media.call_count,5)
        self.assertEqual(requeue_failed(self.store),1)
        self.assertEqual(requeue_failed(self.store),0)
        state=status(self.store)
        self.assertEqual(state['counts'],{'waiting_media':1})
        self.assertEqual(state['recent'][0]['attempts'],0)
        model=SimpleNamespace(analyze=Mock(return_value=generated()))
        self.assertFalse(process_one(self.store,model))
        model.analyze.assert_not_called()
        self.ready()
        await retry_pending_media(self.client,None,self.store,CHAT,payload_builder=self.loader.payload)
        self.assertTrue(process_one(self.store,model))
        self.assertEqual(len(public_posts(self.store)),1)

    async def test_missing_message_is_recorded_without_losing_job(self):
        await self.receive(photo())
        self.due()
        self.client.messages=[]
        await retry_pending_media(self.client,None,self.store,CHAT,payload_builder=self.loader.payload)
        state=status(self.store)
        self.assertEqual(state['counts'],{'media_failed':1})
        self.assertEqual(state['recent'][0]['error'],'telegram_message_unavailable')

    async def test_expired_file_reference_is_refetched_without_changing_content_revision(self):
        original=photo()
        original.photo.file_reference=b'expired'
        self.client.download_media.side_effect=FileReferenceExpiredError('PRIVATE')
        await self.receive(original)
        fresh=photo()
        fresh.photo.file_reference=b'fresh'
        self.assertEqual(message_revision(original),message_revision(fresh))
        self.client.messages=[fresh]
        self.due();self.ready()
        await retry_pending_media(self.client,None,self.store,CHAT,payload_builder=self.loader.payload)
        self.assertIs(self.client.download_media.call_args.args[0],fresh.photo)
        self.assertEqual(status(self.store)['counts'],{'pending':1})

    async def test_failed_edit_preserves_published_card_until_media_and_rewrite_succeed(self):
        self.ready()
        await self.receive(photo())
        model=SimpleNamespace(analyze=Mock(return_value=generated()))
        process_one(self.store,model)
        original=public_posts(self.store)
        changed=photo(text='Edited offer')
        self.client.download_media.side_effect=TelegramTimeout('PRIVATE')
        await self.receive(changed)
        self.assertEqual(public_posts(self.store),original)
        self.assertFalse(process_one(self.store,model))
        self.due();self.ready()
        await self.receive(changed)
        process_one(self.store,model)
        self.assertEqual(public_posts(self.store)[0]['id'],original[0]['id'])
        self.assertEqual(len(public_posts(self.store)),1)

    async def test_flood_wait_does_not_acknowledge_the_message_or_count_as_download_failure(self):
        self.client.download_media.side_effect=FloodWaitError('PRIVATE')
        with self.assertRaises(FloodWaitError):
            await sync_history(self.client,None,self.store,CHAT,limit=0,payload_builder=self.loader.payload)
        self.assertEqual(last_position(self.store,CHAT['id']),0)
        self.assertEqual(status(self.store)['counts'],{})

    async def test_cursor_and_media_retry_commit_together(self):
        payload=await message_payload(self.client,photo())
        with patch('telegram_account.record_media_failure',side_effect=RuntimeError('simulated transaction failure')):
            with self.assertRaises(RuntimeError):
                checkpoint(self.store,CHAT,photo(),payload=payload)
        self.assertEqual(last_position(self.store,CHAT['id']),0)
        self.assertEqual(status(self.store)['counts'],{})

    async def test_media_deferral_during_ai_call_prevents_stale_publication_or_error_overwrite(self):
        failed=await message_payload(self.client,photo())
        legacy={key:value for key,value in failed.items() if key!='media_error'}
        for raise_error in (False,True):
            with self.subTest(raise_error=raise_error):
                checkpoint(self.store,CHAT,photo(),payload=legacy)
                def analyze(*args):
                    checkpoint(self.store,CHAT,photo(),payload=failed)
                    if raise_error:
                        raise ValueError('bad model response')
                    return generated()
                process_one(self.store,SimpleNamespace(analyze=analyze))
                self.assertEqual(public_posts(self.store),[])
                self.assertEqual(status(self.store)['counts'],{'waiting_media':1})
                self.assertEqual(status(self.store)['recent'][0]['error'],'telegram_media_timeout')

    async def test_legacy_caption_only_record_gains_media_on_rescan(self):
        old=await message_payload(self.client,photo())
        old.pop('media_error')
        checkpoint(self.store,CHAT,photo(),payload=old)
        model=SimpleNamespace(analyze=Mock(return_value=generated()))
        process_one(self.store,model)
        original=public_posts(self.store)[0]['id']
        self.ready()
        await self.receive(photo(),advance=False)
        process_one(self.store,model)
        self.assertEqual(public_posts(self.store)[0]['id'],original)
        self.assertEqual(status(self.store)['counts'],{'published':1})
