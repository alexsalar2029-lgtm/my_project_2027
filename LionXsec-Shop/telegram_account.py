"""Read one selected channel with an explicitly authorized LOCAL Telegram session."""
import argparse
import asyncio
import base64
import getpass
import json
import os
from pathlib import Path
import tempfile
import time

from assistant import read_config
from automation import queue_message


def invite_hash(value):
    """Return a private Telegram invite hash without accepting arbitrary URLs."""
    for prefix in ('https://t.me/+','https://t.me/joinchat/'):
        if value.startswith(prefix):
            return value[len(prefix):]
    return ''


def media_details(message):
    kind = next((name for name in ('video','gif','photo','audio','voice','document','sticker')
                 if getattr(message,name,None)), '')
    if not kind:
        return '', ''
    details=[]
    document=getattr(message,'document',None)
    for attribute in getattr(document,'attributes',[]) or []:
        duration=getattr(attribute,'duration',None)
        filename=getattr(attribute,'file_name',None)
        if duration is not None and not any(value.startswith('duration:') for value in details):
            details.append('duration: '+str(int(duration))+' seconds')
        if filename:
            details.append('filename: '+str(filename)[:200])
    return ('animation' if kind=='gif' else kind), '\n'.join(details)


def video_duration(message):
    for attribute in getattr(getattr(message,'document',None),'attributes',[]) or []:
        duration=getattr(attribute,'duration',None)
        if duration is not None:
            return max(0,float(duration))
    return 0


def video_frame_times(duration):
    if duration<=1:
        return [0]
    values=(0,min(duration-0.2,max(1,duration*0.5)),max(0,duration-0.5))
    return list(dict.fromkeys(round(value,2) for value in values))


def ffmpeg_executable():
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError,RuntimeError,OSError):
        return 'ffmpeg'


async def video_frames(client,message,maximum_bytes=100*1024*1024):
    size=getattr(getattr(message,'file',None),'size',0) or 0
    if size>maximum_bytes:
        return []
    with tempfile.TemporaryDirectory(prefix='lionxsec-video-') as folder:
        source=Path(folder)/'source-video'
        try:
            downloaded=await client.download_media(message,file=str(source))
            if not downloaded:
                return []
            frames=[]
            for index,second in enumerate(video_frame_times(video_duration(message))):
                target=Path(folder)/('frame-'+str(index)+'.jpg')
                process=await asyncio.create_subprocess_exec(ffmpeg_executable(),'-hide_banner','-loglevel','error',
                    '-ss',str(second),'-i',str(downloaded),'-frames:v','1','-vf',
                    "scale='min(960,iw)':-2",'-q:v','3','-y',str(target),
                    stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                if await process.wait()==0 and target.is_file():
                    value=image_data(target.read_bytes())
                    if value:
                        frames.append(value)
            return frames[:3]
        except (OSError,ValueError,TypeError):
            return []


def image_data(raw):
    if not isinstance(raw,(bytes,bytearray)) or len(raw)>1_800_000:
        return ''
    if raw.startswith(b'\xff\xd8\xff'):
        mime='image/jpeg'
    elif raw.startswith(b'\x89PNG\r\n\x1a\n'):
        mime='image/png'
    elif raw.startswith(b'RIFF') and raw[8:12]==b'WEBP':
        mime='image/webp'
    else:
        return ''
    return 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')


async def message_payload(client,message):
    kind,details=media_details(message)
    media=[]
    try:
        if kind=='photo':
            value=image_data(await client.download_media(message.photo,file=bytes))
            if value:
                media.append(value)
        elif kind in ('video','animation'):
            media=await video_frames(client,message)
        if not media and kind in ('video','animation','document','sticker') and document_thumbs(message):
            # Offer images forwarded as files keep a thumbnail; show it to the vision model.
            value=image_data(await client.download_media(message,file=bytes,thumb=-1))
            if value:
                media.append(value)
    except Exception:
        # Metadata/caption still reaches the model when a preview cannot be downloaded.
        pass
    return {'message_id':message.id,'text':getattr(message,'message','') or '',
            'media_kind':kind,'media_description':details,'media':media}


def document_thumbs(message):
    document=getattr(message,'document',None) or getattr(getattr(message,'sticker',None),'thumbs',None)
    return getattr(document,'thumbs',None) if not isinstance(document,list) else document


def set_status(store, state, code=''):
    with store.db() as db:
        db.execute('INSERT OR REPLACE INTO assistant_state VALUES(?,?)',
            ('account_runtime',json.dumps({'state':state,'code':code,'updated':int(time.time())})))


def checkpoint(store, chat, message, advance=True, payload=None):
    """Atomically persist text and history position; same post IDs as Bot API."""
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        queue_message(db,chat,payload or {'message_id':message.id,'text':getattr(message,'message','') or ''})
        if advance:
            key='account_cursor:'+str(chat['id'])
            old=db.execute('SELECT value FROM assistant_state WHERE key=?',(key,)).fetchone()
            position=max(int(old[0]) if old else 0,message.id)
            db.execute('INSERT OR REPLACE INTO assistant_state VALUES(?,?)',(key,str(position)))


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
    client=TelegramClient(str(session),int(config['telegram_api_id']),config['telegram_api_hash'])
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
        payload_cache={}
        async def cached_payload(client,message):
            edited=getattr(message,'edit_date',None)
            key=(message.id,str(edited),getattr(message,'message','') or '')
            if key not in payload_cache:
                payload_cache[key]=await message_payload(client,message)
                if len(payload_cache)>500:
                    payload_cache.pop(next(iter(payload_cache)))
            return payload_cache[key]
        @client.on(events.MessageEdited(chats=entity))
        async def edited(event):
            if active():
                checkpoint(store,chat,event.message,advance=False,
                           payload=await cached_payload(client,event.message))
        if args.rescan_limit:
            set_status(store,'rescanning')
            await rescan_history(client,entity,store,chat,args.rescan_limit,active,cached_payload)
        print('Reading the selected channel locally. Press Ctrl+C to stop.')
        while active():
            try:
                set_status(store,'syncing')
                await sync_history(client,entity,store,chat,args.history_limit,active,cached_payload)
                if not active():
                    break
                # Also pick up recent edits that happened while this receiver was offline.
                async for message in client.iter_messages(entity,limit=50):
                    if not active():
                        break
                    checkpoint(store,chat,message,advance=False,
                               payload=await cached_payload(client,message))
                set_status(store,'receiving')
                await asyncio.sleep(15)
            except errors.FloodWaitError as error:
                set_status(store,'rate_limited')
                remaining=error.seconds+1
                while remaining>0 and active():
                    await asyncio.sleep(min(5,remaining));remaining-=5
            except (OSError,asyncio.TimeoutError):
                set_status(store,'connection_retry')
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
