"""Bounded Telegram media downloads; failures remain visible and retryable."""
import asyncio
import base64
import hashlib
import json
from pathlib import Path
import tempfile

IMAGE_TIMEOUT = 30
VIDEO_TIMEOUT = 90
FRAME_TIMEOUT = 15


def media_details(message):
    kind = next((name for name in ('video','gif','photo','audio','voice','document','sticker')
                 if getattr(message,name,None)), '')
    if not kind:
        return '', ''
    details=[]
    for attribute in getattr(getattr(message,'document',None),'attributes',[]) or []:
        duration=getattr(attribute,'duration',None)
        filename=getattr(attribute,'file_name',None)
        if duration is not None and not any(value.startswith('duration:') for value in details):
            details.append('duration: '+str(int(duration))+' seconds')
        if filename:
            details.append('filename: '+str(filename)[:200])
    return ('animation' if kind=='gif' else kind), '\n'.join(details)


def message_revision(message):
    # file_reference changes when Telegram refreshes access; it is not a content edit.
    media=getattr(message,'document',None) or getattr(message,'photo',None)
    value=[message.id, str(getattr(message,'edit_date',None)),
           getattr(message,'message','') or '', getattr(media,'id',None), media_details(message)]
    return hashlib.sha256(json.dumps(value,ensure_ascii=False).encode()).hexdigest()


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
    if (getattr(getattr(message,'file',None),'size',0) or 0)>maximum_bytes:
        return []
    with tempfile.TemporaryDirectory(prefix='lionxsec-video-') as folder:
        source=Path(folder)/'source-video'
        downloaded=await asyncio.wait_for(client.download_media(message,file=str(source)), VIDEO_TIMEOUT)
        if not downloaded:
            return []
        frames=[]
        for index,second in enumerate(video_frame_times(video_duration(message))):
            target=Path(folder)/('frame-'+str(index)+'.jpg')
            process=await asyncio.create_subprocess_exec(ffmpeg_executable(),'-hide_banner','-loglevel','error',
                '-ss',str(second),'-i',str(downloaded),'-frames:v','1','-vf',
                "scale='min(960,iw)':-2",'-q:v','3','-y',str(target),
                stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
            try:
                result=await asyncio.wait_for(process.wait(), FRAME_TIMEOUT)
            except BaseException:
                # Cancelled downloads/frame extraction must release Windows file handles too.
                if process.returncode is None:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                    await process.wait()
                raise
            if result==0 and target.is_file():
                value=image_data(target.read_bytes())
                if value:
                    frames.append(value)
        return frames[:3]


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


def document_thumbs(message):
    document=getattr(message,'document',None) or getattr(getattr(message,'sticker',None),'thumbs',None)
    return getattr(document,'thumbs',None) if not isinstance(document,list) else document


def media_failure_code(error):
    name=type(error).__name__
    # Rate limits and invalid sessions concern the account, not this individual post.
    if name in ('FloodWaitError','FloodPremiumWaitError','AuthKeyUnregisteredError',
                'SessionRevokedError','SessionExpiredError','UserDeactivatedError',
                'AuthKeyDuplicatedError','AuthKeyNotFound') or getattr(error,'code',None)==401:
        raise error
    if isinstance(error,TimeoutError) or name in ('TimedOutError','TimeoutError'):
        return 'telegram_media_timeout'
    if name in ('FileReferenceExpiredError','FileReferenceEmptyError','FileReferenceInvalidError'):
        return 'telegram_file_reference_expired'
    if isinstance(error,(OSError,ConnectionError)):
        return 'telegram_media_connection_failed'
    return 'telegram_media_download_failed'


async def message_payload(client,message):
    kind,details=media_details(message)
    media=[]
    problem=''
    if kind in ('photo','video','animation'):
        try:
            if kind=='photo':
                raw=await asyncio.wait_for(client.download_media(message.photo,file=bytes), IMAGE_TIMEOUT)
                value=image_data(raw)
                if value:
                    media.append(value)
            else:
                media=await video_frames(client,message)
        except Exception as error:
            problem=media_failure_code(error)
    if not media and kind in ('video','animation','document','sticker') and document_thumbs(message):
        # A failed full-video request must still reach this independent thumbnail fallback.
        try:
            raw=await asyncio.wait_for(client.download_media(message,file=bytes,thumb=-1), IMAGE_TIMEOUT)
            value=image_data(raw)
            if value:
                media.append(value)
                if kind in ('video','animation'):
                    details+='\nVisual evidence: Telegram thumbnail only; video frames were unavailable.'
        except Exception as error:
            problem=media_failure_code(error)
    visual_expected=kind in ('photo','video','animation') or bool(document_thumbs(message))
    payload={'message_id':message.id,'text':getattr(message,'message','') or '',
             'media_kind':kind,'media_description':details,'media':media,
             'media_revision':message_revision(message)}
    if visual_expected and not media:
        payload['media_error']=problem or 'telegram_preview_unavailable'
    return payload
