"""Read one selected channel with an explicitly authorized LOCAL Telegram session."""
import argparse
import asyncio
import getpass
import json
import os
from pathlib import Path
import time

from assistant import read_config
from automation import queue_message
from telegram_media import (document_thumbs, image_data, media_details, message_payload,
                            message_revision, media_failure_code, video_frame_times)


def invite_hash(value):
    """Return a private Telegram invite hash without accepting arbitrary URLs."""
    for prefix in ('https://t.me/+','https://t.me/joinchat/'):
        if value.startswith(prefix):
            return value[len(prefix):]
    return ''


def set_status(store, state, code='', **details):
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO assistant_state VALUES(?,?)',
            ('account_runtime',json.dumps({'state':state,'code':code,'updated':int(time.time()),**details})))


def record_media_failure(db, key, revision, code, attempts, missing=False):
    failed=missing or attempts>=5
    retry_at=0 if failed else int(time.time())+min(3600,60*2**min(attempts-1,6))
    db.execute('INSERT OR REPLACE INTO assistant_media_pending VALUES(?,?)',(key,revision))
    db.execute('UPDATE assistant_jobs SET status=?,attempts=?,retry_at=?,error=?,updated=? WHERE key=?',
               ('media_failed' if failed else 'waiting_media',attempts,retry_at,code,int(time.time()),key))


def checkpoint(store, chat, message, advance=True, payload=None):
    """Persist media retries and the cursor atomically, so later messages can continue."""
    payload=payload or {'message_id':message.id,'text':getattr(message,'message','') or ''}
    key=str(chat['id'])+':'+str(message.id)
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        if not payload.get('media_deferred') and not payload.get('unchanged'):
            previous=db.execute('''SELECT j.attempts,m.revision FROM assistant_media_pending m
                JOIN assistant_jobs j ON j.key=m.key WHERE m.key=?''',(key,)).fetchone()
            queue_message(db,chat,payload)
            if payload.get('media_error'):
                db.execute('DELETE FROM assistant_media_seen WHERE key=?',(key,))
                revision=payload['media_revision']
                attempts=previous['attempts']+1 if previous and previous['revision']==revision else 1
                record_media_failure(db,key,revision,payload['media_error'],attempts)
            else:
                if payload.get('media_revision'):
                    db.execute('INSERT OR REPLACE INTO assistant_media_seen VALUES(?,?)',(key,payload['media_revision']))
                if previous:
                    db.execute('DELETE FROM assistant_media_pending WHERE key=?',(key,))
                    db.execute("UPDATE assistant_jobs SET status='pending',attempts=0,retry_at=0,error='',updated=? WHERE key=?",
                               (int(time.time()),key))
        if advance:
            cursor_key='account_cursor:'+str(chat['id'])
            old=db.execute('SELECT value FROM assistant_state WHERE key=?',(cursor_key,)).fetchone()
            position=max(int(old[0]) if old else 0,message.id)
            db.execute('INSERT OR REPLACE INTO assistant_state VALUES(?,?)',(cursor_key,str(position)))
    if payload.get('media_error'):
        print(f"Post #{message.id}: {payload['media_error']}; media saved for retry. Continuing with other posts.")


class MediaLoader:
    """Persist successful revisions and retry deadlines; never cache a missing preview."""
    def __init__(self, store, chat):
        self.store,self.chat=store,chat

    async def payload(self, client, message):
        revision=message_revision(message)
        key=str(self.chat['id'])+':'+str(message.id)
        with self.store.db() as db:
            pending=db.execute('''SELECT m.revision,j.status,j.retry_at FROM assistant_media_pending m
                JOIN assistant_jobs j ON j.key=m.key WHERE m.key=?''',(key,)).fetchone()
            seen=db.execute('''SELECT s.revision FROM assistant_media_seen s
                JOIN assistant_jobs j ON j.key=s.key WHERE s.key=?''',(key,)).fetchone()
        if pending and pending['revision']==revision and (
                pending['status']=='media_failed' or pending['retry_at']>int(time.time())):
            return {'media_deferred':True}
        if not pending and seen and seen['revision']==revision:
            return {'unchanged':True}
        if media_details(message)[0]:
            set_status(self.store,'downloading',message=message.id)
        return await message_payload(client,message)


async def retry_pending_media(client, entity, store, chat, keep_going=lambda:True,
                              payload_builder=message_payload, limit=3):
    with store.db() as db:
        rows=db.execute('''SELECT j.key,j.message,m.revision FROM assistant_media_pending m
            JOIN assistant_jobs j ON j.key=m.key WHERE j.chat=? AND j.status='waiting_media'
            AND j.retry_at<=? ORDER BY j.retry_at,j.message LIMIT ?''',
            (str(chat['id']),int(time.time()),limit)).fetchall()
    for row in rows:
        if not keep_going():
            return
        missing=False
        payload=None
        try:
            # Re-fetch the message to renew expired Telegram file references, including old posts.
            message=await asyncio.wait_for(client.get_messages(entity,ids=row['message']),30)
            if message is not None and type(message).__name__!='MessageEmpty':
                payload=await payload_builder(client,message)
            else:
                missing=True
                code='telegram_message_unavailable'
        except Exception as error:
            code=media_failure_code(error)
        if payload is not None:
            # Database errors must propagate; they are not Telegram download failures.
            checkpoint(store,chat,message,advance=False,payload=payload)
            continue
        with store.db() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('''SELECT m.revision,j.attempts FROM assistant_media_pending m
                JOIN assistant_jobs j ON j.key=m.key WHERE m.key=?''',(row['key'],)).fetchone()
            if current and current['revision']==row['revision']:
                record_media_failure(db,row['key'],row['revision'],code,current['attempts']+1,missing)


def last_position(store, chat_id):
    with store.db() as db:
        row=db.execute('SELECT value FROM assistant_state WHERE key=?',('account_cursor:'+str(chat_id),)).fetchone()
    return int(row[0]) if row else 0


async def sync_history(client, entity, store, chat, limit=200, keep_going=lambda:True,
                       payload_builder=message_payload):
    position=last_position(store,chat['id'])
    if position or limit==0:
        # After restart, catch up ALL missed messages rather than skipping a gap.
        async for message in client.iter_messages(entity,min_id=position,reverse=True,limit=None):
            if not keep_going():
                return
            checkpoint(store,chat,message,payload=await payload_builder(client,message))
    else:
        messages=[m async for m in client.iter_messages(entity,limit=limit)]
        for message in reversed(messages):
            if not keep_going():
                return
            checkpoint(store,chat,message,payload=await payload_builder(client,message))


async def rescan_history(client, entity, store, chat, limit, keep_going=lambda:True,
                         payload_builder=message_payload):
    """Re-evaluate a bounded recent window without moving the saved cursor backwards."""
    messages=[message async for message in client.iter_messages(entity,limit=limit)]
    for message in reversed(messages):
        if not keep_going():
            return
        checkpoint(store,chat,message,advance=False,
                   payload=await payload_builder(client,message))


async def run(args,store):
    try:
        from telethon import TelegramClient, events, utils, errors
        from telethon.tl.functions.messages import CheckChatInviteRequest
    except ImportError:
        raise SystemExit('Install optional dependencies: python -m pip install -r requirements-account.txt') from None
    config=read_config(store)
    if not config.get('telegram_api_id') or not config.get('telegram_api_hash'):
        raise SystemExit('Enter Telegram App API ID and API hash in the local admin assistant tab first.')
    session=store.path.parent/'telegram-account'
    client=TelegramClient(str(session),int(config['telegram_api_id']),config['telegram_api_hash'],
                          request_retries=1,raise_last_call_error=True,flood_sleep_threshold=0)
    def active():
        current=read_config(store)
        return current['enabled'] and current['source']=='account' and all(
            current[key]==config[key] for key in ('channel','telegram_api_id','telegram_api_hash'))
    try:
        if args.command=='login':
            # All interactive inputs remain in the user's own terminal.
            await client.start(phone=lambda:input('Your Telegram phone number (international format): '),
                password=lambda:getpass.getpass('Telegram two-step password (local only): '),
                code_callback=lambda:getpass.getpass('Telegram login code (local only): '))
            set_status(store,'authenticated')
            print('Local account session saved. Never share the data folder or session file.')
            return
        if not active():
            raise SystemExit('Select Account mode and enable the assistant in local admin first.')
        await client.connect()
        if not await client.is_user_authorized():
            raise SystemExit('Local login required: python telegram_account.py login')
        selected_invite=invite_hash(config['channel'])
        target=int(config['channel']) if config['channel'].startswith('-100') else config['channel']
        try:
            if selected_invite:
                invitation=await client(CheckChatInviteRequest(selected_invite))
                entity=getattr(invitation,'chat',None)
                if entity is None:
                    raise SystemExit('Join the private channel with this account first, then run watch again.')
            else:
                entity=await client.get_entity(target)
        except (ValueError,errors.InviteHashExpiredError,errors.InviteHashInvalidError):
            entity=None
            if isinstance(target,int):
                async for dialog in client.iter_dialogs():
                    if utils.get_peer_id(dialog.entity)==target:
                        entity=dialog.entity
                        break
            if entity is None:
                raise SystemExit('Selected channel or private invite link is not accessible to this account.') from None
        if not getattr(entity,'broadcast',False):
            raise SystemExit('Select a Telegram channel, not a user or group.')
        permissions=await client.get_permissions(entity,'me')
        if not (permissions.is_creator or permissions.is_admin):
            raise SystemExit('Use a channel you own or administer.')
        chat={'id':utils.get_peer_id(entity),'username':getattr(entity,'username',None) or ''}
        loader=MediaLoader(store,chat)
        pending_edits={}
        @client.on(events.MessageEdited(chats=entity))
        async def edited(event):
            if active():
                # Serialize downloads in the main loop, including edits and retry jobs.
                pending_edits[event.message.id]=event.message
        rescan_remaining=args.rescan_limit
        print('Reading the selected channel locally. Press Ctrl+C to stop.')
        while active():
            try:
                if rescan_remaining:
                    set_status(store,'rescanning')
                    await rescan_history(client,entity,store,chat,rescan_remaining,active,loader.payload)
                    rescan_remaining=0
                set_status(store,'syncing')
                await sync_history(client,entity,store,chat,args.history_limit,active,loader.payload)
                if not active():
                    break
                for mid,message in list(pending_edits.items()):
                    if not active():
                        break
                    checkpoint(store,chat,message,advance=False,payload=await loader.payload(client,message))
                    if pending_edits.get(mid) is message:
                        pending_edits.pop(mid)
                # Also pick up recent edits that happened while this receiver was offline.
                async for message in client.iter_messages(entity,limit=50):
                    if not active():
                        break
                    checkpoint(store,chat,message,advance=False,
                               payload=await loader.payload(client,message))
                await retry_pending_media(client,entity,store,chat,active,loader.payload)
                set_status(store,'receiving')
                await asyncio.sleep(15)
            except (errors.FloodWaitError,errors.FloodPremiumWaitError) as error:
                set_status(store,'rate_limited','telegram_rate_limited',retry_at=int(time.time())+error.seconds+1)
                remaining=error.seconds+1
                while remaining>0 and active():
                    await asyncio.sleep(min(5,remaining));remaining-=5
            except (OSError,asyncio.TimeoutError,errors.ServerError,errors.TimedOutError):
                set_status(store,'connection_retry','telegram_connection_retry',retry_at=int(time.time())+15)
                await asyncio.sleep(15)
        set_status(store,'stopped')
    finally:
        await client.disconnect()
        for file in store.path.parent.glob('telegram-account.session*'):
            try:
                file.chmod(0o600)
            except OSError:
                pass


def main():
    from server import Store
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('login','watch'))
    parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent/'data')
    parser.add_argument('--history-limit',type=int,default=200,help='Initial posts; 0 imports all accessible history.')
    parser.add_argument('--rescan-limit',type=int,default=0,
                        help='Re-analyze this many recent posts once, without resetting the saved cursor.')
    args=parser.parse_args()
    if args.history_limit<0 or args.rescan_limit<0:
        parser.error('history-limit and rescan-limit must be >= 0')
    os.umask(0o077)
    store=Store(args.data_dir/'shop.sqlite3')
    try:
        asyncio.run(run(args,store))
    except KeyboardInterrupt:
        print('Receiver stopped.')
    except Exception:
        set_status(store,'error','account_connection_failed')
        raise SystemExit('Account connection failed. Check local login, network and selected channel; no credentials were logged.') from None


if __name__=='__main__':
    main()
