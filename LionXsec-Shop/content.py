"""Local administrator uploads and multilingual learning/download content."""
import mimetypes
import os
import re
import secrets
import time
from urllib.parse import urlsplit
import json

LANGS = ('fa', 'en', 'ar', 'es')
LIMITS = {'logo': 3 * 1024**2, 'video': 250 * 1024**2}


class ContentError(Exception):
    def __init__(self, code, status=400):
        self.code, self.status = code, status


def translations(value, limit=250, required=True):
    if not isinstance(value, dict) or set(value) != set(LANGS):
        raise ContentError('translations_required')
    if any(not isinstance(v, str) or len(v.strip()) > limit or (required and not v.strip()) for v in value.values()):
        raise ContentError('invalid_translation')
    return {lang: value[lang].strip() for lang in LANGS}


def download_url(value):
    if not isinstance(value, str) or len(value) > 2000 or any(c.isspace() or ord(c) < 32 for c in value):
        raise ContentError('invalid_download_url')
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.port not in (None, 443):
            raise ValueError
    except ValueError:
        raise ContentError('invalid_download_url') from None
    return value


# Formats are never refused: every upload is stored and identified from its content.
# Only the logo slot must resolve to a real image, and SVG/HTML keep the old 415 guarantee.
IMAGE_LOGO_FORBIDDEN = ('image/svg+xml', 'text/html')

SIGNATURES = (
    (b'GIF87a', 'image/gif', '.gif'), (b'GIF89a', 'image/gif', '.gif'),
    (b'BM', 'image/bmp', '.bmp'), (b'ID3', 'audio/mpeg', '.mp3'),
    (b'%PDF', 'application/pdf', '.pdf'), (b'PK\x03\x04', 'application/zip', '.zip'),
    (b'PK\x05\x06', 'application/zip', '.zip'), (b'PK\x07\x08', 'application/zip', '.zip'),
    (b'Rar!\x1a\x07', 'application/vnd.rar', '.rar'),
    (b'7z\xbc\xaf\x27\x1c', 'application/x-7z-compressed', '.7z'),
    (b'\x1f\x8b', 'application/gzip', '.gz'), (b'BZh', 'application/x-bzip2', '.bz2'),
    (b'\xfd7zXZ', 'application/x-xz', '.xz'),
    (b'\x04\x22\x4d\x18', 'application/zstd', '.zst'),
    (b'\x7fELF', 'application/x-executable', '.elf'), (b'MZ', 'application/x-msdownload', '.exe'),
    (b'\xca\xfe\xba\xbe', 'application/java-vm', '.class'),
    (b'\x00\x61\x73\x6d', 'application/wasm', '.wasm'), (b'OggS', 'audio/ogg', '.ogg'),
    (b'\x00\x00\x01\xba', 'video/mpeg', '.mpg'), (b'\x00\x00\x01\xb3', 'video/mpeg', '.mpg'),
    (b'FLV', 'video/x-flv', '.flv'),
    (b'\x21\x11\x4c\x1a', 'application/x-subrip', '.srt'),
)


def sniff(header, kind, original_name=''):
    """Identify any file type: magic bytes first, then extension, text sniff, octet-stream."""
    mime, ext = identify(header, original_name)
    if kind == 'logo' and (not mime.startswith('image/') or mime in IMAGE_LOGO_FORBIDDEN):
        raise ContentError('unsupported_upload', 415)
    return mime, ext


def identify(header, original_name):
    mime, ext = magic_type(header)
    if mime is not None:
        return mime, ext
    guessed, by_ext = extension_type(original_name)
    if guessed:
        return guessed, by_ext
    if looks_like_text(header):
        return 'text/plain', safe_extension(original_name, '.txt')
    return 'application/octet-stream', safe_extension(original_name, '.bin')


def magic_type(header):
    for prefix, mime, ext in SIGNATURES:
        if header.startswith(prefix):
            return mime, ext
    if header.startswith(b'\x89PNG\r\n\x1a\n') and header[12:16] == b'IHDR':
        return 'image/png', '.png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'image/jpeg', '.jpg'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'image/webp', '.webp'
    if header[:4] == b'RIFF':
        return 'audio/x-wav', '.wav'
    if header[:4] == b'CWS\x08' or header[:3] in (b'FWS', b'ZWS'):
        return 'application/x-shockwave-flash', '.swf'
    if len(header) >= 12 and header[4:8] == b'ftyp':
        brand = header[8:12]
        if brand.startswith(b'M4A'):
            return 'audio/mp4', '.m4a'
        if brand.startswith(b'3gp'):
            return 'video/3gpp', '.3gp'
        if brand in (b'qt  ', b'MSVQ'):
            return 'video/quicktime', '.mov'
        return 'video/mp4', '.mp4'
    if header.startswith(b'\x1aE\xdf\xa3'):
        return ('video/webm', '.webm') if b'webm' in header else ('video/x-matroska', '.mkv')
    if header.startswith(b'\x00\x00\x00\x0c\x6a\x50\x20\x20\x0d\x0a\x87\x0a'):
        return 'image/jp2', '.jp2'
    if header.startswith(b'\xff\x4a\x45\xff'):
        return 'image/jxl', '.jxl'
    if header[:2] in (b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'):
        return 'audio/mpeg', '.mp3'
    if header[:2] in (b'<?', b'\xef\xbb') or header[:1] in (b'<', b'\xff\xfe', b'\xfe\xff'):
        text = header.lstrip(b'\xef\xbb\xbf\xff\xfe\xfe\xff \t\r\n\x00').lower()
        if re.match(rb'^<(svg[\s?/])', text): return 'image/svg+xml', '.svg'
        if re.match(rb'^<!doctype\s*html', text) or re.match(rb'^<html[\s>/?]', text): return 'text/html', '.html'
        if re.match(rb'^<\?xml[\s?]', text) or re.match(rb'^<(xml|rss|feed|rdf|plist)[\s>/?]', text): return 'application/xml', '.xml'
        if re.match(rb'^[{\[]\s*[{\]"]', text): return 'application/json', '.json'
        if text.startswith(b'rtf'): return 'application/rtf', '.rtf'
    return None, None


EXT_OVERRIDES = {
    '.md': 'text/markdown', '.mkv': 'video/x-matroska', '.m4a': 'audio/mp4',
    '.flac': 'audio/flac', '.exe': 'application/x-msdownload', '.msi': 'application/x-msdownload',
    '.dll': 'application/x-msdownload', '.iso': 'application/x-iso9660-image', '.img': 'application/octet-stream',
    '.heic': 'image/heic', '.heif': 'image/heif', '.tif': 'image/tiff', '.tiff': 'image/tiff',
    '.ico': 'image/vnd.microsoft.icon', '.py': 'text/x-python', '.js': 'text/javascript',
    '.mjs': 'text/javascript', '.ts': 'text/typescript', '.tsx': 'text/typescript', '.jsx': 'text/javascript',
    '.sh': 'application/x-sh', '.bat': 'application/x-bat', '.cmd': 'application/x-bat',
    '.ps1': 'application/x-powershell', '.apk': 'application/vnd.android.package-archive',
    '.aab': 'application/vnd.android.play-aap', '.jar': 'application/java-archive',
    '.war': 'application/java-archive', '.rar': 'application/vnd.rar', '.7z': 'application/x-7z-compressed',
    '.xz': 'application/x-xz', '.zst': 'application/zstd', '.tgz': 'application/gzip',
    '.tzst': 'application/zstd', '.z': 'application/compress', '.xz5': 'application/x-xz',
    '.htm': 'text/html', '.html': 'text/html', '.xhtml': 'text/html', '.svg': 'image/svg+xml',
    '.xml': 'application/xml', '.json': 'application/json', '.csv': 'text/csv', '.tsv': 'text/tab-separated-values',
    '.txt': 'text/plain', '.log': 'text/plain', '.rtf': 'application/rtf', '.pdf': 'application/pdf',
    '.epub': 'application/epub+zip', '.mobi': 'application/x-mobipocket-ebook', '.azw3': 'application/vnd.amazon.ebook',
    '.doc': 'application/msword', '.xls': 'application/vnd.ms-excel', '.ppt': 'application/vnd.ms-powerpoint',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.odt': 'application/vnd.oasis.opendocument.text', '.ods': 'application/vnd.oasis.opendocument.spreadsheet',
    '.odp': 'application/vnd.oasis.opendocument.presentation',
    '.mpg': 'video/mpeg', '.mpeg': 'video/mpeg',
    '.flv': 'video/x-flv', '.f4v': 'video/x-flv', '.avi': 'video/x-msvideo', '.wmv': 'video/x-ms-wmv',
    '.asf': 'video/x-ms-asf', '.asx': 'video/x-ms-asf', '.wma': 'audio/x-ms-wma', '.rm': 'audio/x-pn-realaudio',
    '.ra': 'audio/x-realaudio', '.aiff': 'audio/aiff', '.aif': 'audio/aiff', '.au': 'audio/basic',
    '.caf': 'audio/x-caf', '.mka': 'audio/x-matroska', '.m3u': 'audio/x-mpegurl', '.m3u8': 'application/vnd.apple.mpegurl',
    '.ape': 'audio/ape', '.wv': 'audio/x-wavpack', '.dsf': 'audio/x-dsf', '.opu': 'application/x-opus',
    '.swf': 'application/x-shockwave-flash', '.dmg': 'application/x-apple-diskimage',
    '.vhd': 'application/x-virtual-pc-disk', '.vhdx': 'application/x-vhd',
    '.vmdk': 'application/x-vmdk', '.qcow2': 'application/x-qcow2', '.vdi': 'application/x-vdi',
    '.bin': 'application/octet-stream', '.dat': 'application/octet-stream',
    '.db': 'application/x-sqlite3', '.sqlite': 'application/x-sqlite3', '.sqlite3': 'application/x-sqlite3',
    '.deb': 'application/vnd.debian.binary-package', '.rpm': 'application/x-rpm',
    '.xap': 'application/x-silverlight-app', '.crx': 'application/chrome-extension', '.wasm': 'application/wasm',
    '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff': 'font/woff', '.woff2': 'font/woff2', '.eot': 'application/vnd.ms-fontobject',
    '.glb': 'model/gltf-binary', '.gltf': 'model/gltf+json', '.obj': 'model/obj', '.stl': 'model/stl', '.fbx': 'application/octet-stream',
    '.blend': 'application/x-blender', '.max': 'application/octet-stream', '.skp': 'application/vnd.sketchup',
    '.dwg': 'image/vnd.dwg', '.dxf': 'image/vnd.dxf', '.psd': 'image/vnd.adobe.photoshop', '.xcf': 'image/x-xcf',
    '.ai': 'application/postscript', '.eps': 'application/postscript', '.ps': 'application/postscript',
    '.pyw': 'text/x-python', '.rb': 'text/x-ruby', '.pl': 'text/x-perl', '.php': 'text/x-php',
    '.c': 'text/x-c', '.h': 'text/x-c', '.cpp': 'text/x-c++src', '.cs': 'text/x-csharp', '.go': 'text/x-go',
    '.rs': 'text/x-rust', '.java': 'text/x-java', '.kt': 'text/x-kotlin', '.swift': 'text/x-swift',
    '.lua': 'text/x-lua', '.sql': 'application/sql', '.yaml': 'text/yaml', '.yml': 'text/yaml',
    '.toml': 'application/toml', '.ini': 'text/x-ini', '.cfg': 'text/x-config', '.conf': 'text/x-config',
    '.properties': 'text/x-properties', '.env': 'text/x-env', '.tex': 'application/x-tex', '.bib': 'application/x-bibtex',
    '.srt': 'application/x-subrip', '.ass': 'text/x-ssa', '.ssa': 'text/x-ssa', '.vtt': 'text/vtt',
    '.patch': 'text/x-patch', '.diff': 'text/x-patch', '.desktop': 'application/x-desktop',
    '.appx': 'application/x-ms-appx', '.msix': 'application/x-msix',
}


def extension_type(name):
    ext = ('.' + str(name).rsplit('.', 1)[-1].lower()) if '.' in str(name) else ''
    ext = re.sub(r'[^a-z0-9]', '', ext)[1:9]
    if not ext:
        return None, None
    mime = EXT_OVERRIDES.get('.' + ext) or mimetypes.guess_type('x.' + ext)[0]
    return (mime, '.' + ext) if mime else (None, None)


def looks_like_text(header):
    if b'\x00' in header:
        return False
    try:
        decoded = header.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return not any(ord(c) < 32 and c not in '\t\r\n' for c in decoded)


def safe_extension(name, fallback):
    ext = ('.' + str(name).rsplit('.', 1)[-1].lower()) if '.' in str(name) else ''
    ext = re.sub(r'[^a-z0-9]', '', ext)[1:9]
    return '.' + ext if ext else fallback


class ResourceStoreMixin:
    def init_content(self):
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS media (id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                mime TEXT NOT NULL, filename TEXT NOT NULL, original_name TEXT NOT NULL,
                size INTEGER NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS resources (id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                value TEXT NOT NULL);
            ''')

    @property
    def media_dir(self):
        return self.path.parent / 'media'

    @staticmethod
    def media_public(row):
        return {'id':row['id'], 'url':'/media/'+row['id'], 'kind':row['kind'], 'mime':row['mime'],
                'name':row['original_name'], 'size':row['size'], 'created':row['created']}

    def media_record(self, mid, kind=None, db=None):
        if not isinstance(mid, str) or not re.fullmatch(r'[0-9a-f]{32}', mid):
            raise ContentError('media_not_found', 404)
        if db is None:
            with self.db() as connection:
                return self.media_record(mid, kind, connection)
        row = db.execute('SELECT * FROM media WHERE id=?', (mid,)).fetchone()
        if not row or (kind is not None and row['kind'] != kind):
            raise ContentError('media_not_found', 404)
        return row

    def upload(self, stream, kind, length, original_name):
        if kind not in LIMITS:
            raise ContentError('invalid_upload_kind')
        if not 1 <= length <= LIMITS[kind]:
            raise ContentError('upload_too_large', 413)
        self.media_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        original_name = str(original_name).replace('\\', '/').split('/')[-1]
        original_name = ''.join(c for c in original_name if ord(c) >= 32)[:180]
        mid = secrets.token_hex(16)
        temporary = self.media_dir / (mid+'.part')
        target = None
        try:
            # The declared MIME or extension alone is never trusted; content decides.
            header = stream.read(min(length, 128))
            mime, ext = sniff(header, kind, original_name)
            with temporary.open('xb') as file:
                file.write(header)
                remaining = length - len(header)
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        raise ContentError('incomplete_upload')
                    file.write(chunk)
                    remaining -= len(chunk)
            temporary.chmod(0o600)
            target = self.media_dir / (mid+ext)
            os.replace(temporary, target)
            stored_name = original_name or ('upload'+ext)
            with self.db() as db:
                db.execute('INSERT INTO media VALUES(?,?,?,?,?,?,?)', (
                    mid, kind, mime, mid+ext, stored_name, length, int(time.time())))
                self.log(db, 'upload_'+kind, mid)
            return self.media_public(self.media_record(mid))
        except Exception:
            if target is not None:
                target.unlink(missing_ok=True)
            raise
        finally:
            temporary.unlink(missing_ok=True)

    def media_list(self):
        with self.db() as db:
            return [self.media_public(r) for r in db.execute('SELECT * FROM media ORDER BY created DESC,rowid DESC LIMIT 500')]

    def delete_media(self, mid):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = self.media_record(mid, db=db)
            products = [json.loads(r[0]) for r in db.execute('SELECT value FROM products')]
            resources = [json.loads(r[0]) for r in db.execute('SELECT value FROM resources')]
            if any(p.get('logo_id') == mid for p in products) or any(
                    r.get('video_id') == mid or r.get('logo_id') == mid for r in resources):
                raise ContentError('media_in_use', 409)
            (self.media_dir / row['filename']).unlink(missing_ok=True)
            db.execute('DELETE FROM media WHERE id=?', (mid,))
            self.log(db, 'upload_deleted', mid)

    def resources(self, admin=False):
        with self.db() as db:
            out = []
            for row in db.execute('SELECT value FROM resources ORDER BY rowid DESC'):
                item = json.loads(row[0])
                if not admin and not item['published']:
                    continue
                if item.get('video_id'):
                    media = self.media_record(item['video_id'], 'video', db)
                    item['video_url'], item['video_mime'] = '/media/'+media['id'], media['mime']
                if item.get('logo_id'):
                    item['logo_url'] = '/media/'+item['logo_id']
                out.append(item)
            return out

    def save_resource(self, data, rid=None):
        kind = data.get('kind')
        if kind not in ('tutorial', 'tool') or type(data.get('published', True)) is not bool:
            raise ContentError('invalid_resource')
        item = {'id':rid or secrets.token_hex(8), 'kind':kind,
                'title':translations(data.get('title')), 'description':translations(data.get('description'),1000,False),
                'published':data.get('published', True), 'video_id':data.get('video_id') or None,
                'logo_id':data.get('logo_id') or None, 'download_url':'', 'updated':int(time.time())}
        if kind == 'tool':
            item['download_url'] = download_url(data.get('download_url'))
            item['video_id'] = None
        elif not item['video_id']:
            raise ContentError('video_required')
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if rid:
                old = db.execute('SELECT kind FROM resources WHERE id=?', (rid,)).fetchone()
                if not old or old['kind'] != kind:
                    raise ContentError('not_found', 404)
            if item['video_id']:
                self.media_record(item['video_id'], 'video', db)
            if item['logo_id']:
                self.media_record(item['logo_id'], 'logo', db)
            if rid:
                db.execute('UPDATE resources SET value=? WHERE id=?', (json.dumps(item),rid))
            else:
                db.execute('INSERT INTO resources VALUES(?,?,?)', (item['id'],kind,json.dumps(item)))
            self.log(db, 'resource_saved', item['id'])
        return item

    def delete_resource(self, rid):
        with self.db() as db:
            if not db.execute('DELETE FROM resources WHERE id=?', (rid,)).rowcount:
                raise ContentError('not_found',404)
            self.log(db, 'resource_deleted',rid)
