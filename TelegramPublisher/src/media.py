"""Explicit Telegram media types: the original filename never determines routing."""
from pathlib import Path
from telethon.tl import types

def telegram_media(uploaded, row, as_document=False):
    mime = row['mime']
    if not as_document and mime in {'image/jpeg','image/png'} and row['size'] <= 10*1024**2:
        return types.InputMediaUploadedPhoto(file=uploaded)
    attrs = [types.DocumentAttributeFilename(Path(row['path']).name)]
    if not as_document and row['kind'] == 'audio':
        duration = 0
        try:
            from mutagen import File
            audio = File(row['path'])
            duration = int(audio.info.length) if audio else 0
        except Exception:
            pass
        attrs.append(types.DocumentAttributeAudio(duration, title=row['title']))
    elif not as_document and mime == 'video/mp4':
        attrs.append(types.DocumentAttributeVideo(0, 1, 1, supports_streaming=True))
    elif not as_document and mime == 'image/gif':
        attrs.append(types.DocumentAttributeAnimated())
    return types.InputMediaUploadedDocument(file=uploaded, mime_type=mime, attributes=attrs)
