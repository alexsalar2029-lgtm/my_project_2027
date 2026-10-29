"""Validated, idempotent local publishing from one explicitly selected channel."""
import hashlib
import json
import re
import time
from decimal import Decimal, InvalidOperation
from social import DEFAULT_LINKS, validate_links

LANGS = ('fa', 'en', 'ar', 'es')
DIGITS = str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')
BRAND_NAMES = {
    'nordvpn': ('nordvpn', 'nord vpn', 'نورد وی پی ان', 'نورد وی‌پی‌ان'),
    'crunchyroll': ('crunchyroll', 'crunchy roll', 'کرانچی رول', 'کرانچی‌رول'),
    'dazn': ('dazn', 'دازن'),
    'netflix': ('netflix', 'نتفلیکس', 'نتفليكس'),
    'spotify': ('spotify', 'اسپاتیفای', 'اسپاتی فای', 'سبوتيفاي'),
    'youtube': ('youtube', 'you tube', 'یوتیوب', 'يوتيوب'),
    'surfshark': ('surfshark', 'surf shark', 'سرف شارک', 'سرف‌شارک'),
}


def detected_brand(source='', title=None, suggested=None):
    """Use local logos only; a provider cannot supply an image URL or asset path."""
    for text in (source, ' '.join((title or {}).values())):
        # Contact URLs and channel names are not evidence of the advertised service.
        text = re.sub(r'https?://\S+|@[\w]+', '', text).casefold()
        found = [key for key, names in BRAND_NAMES.items() if any(
            re.search(r'(?<!\w)'+re.escape(name)+r'(?!\w)', text) for name in names)]
        if found:
            return found[0] if len(found) == 1 else 'generic'
    return suggested if isinstance(suggested, str) and suggested in BRAND_NAMES else 'generic'


def initialize(store):
    with store.db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS assistant_state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_jobs (
            key TEXT PRIMARY KEY, chat TEXT NOT NULL, message INTEGER NOT NULL,
            source TEXT NOT NULL, text TEXT NOT NULL, digest TEXT NOT NULL,
            status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
            retry_at INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', updated INTEGER NOT NULL,
            media TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS assistant_posts (
            key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        # Upgrade databases created by v1.5 without discarding queued posts.
        if 'media' not in {row[1] for row in db.execute('PRAGMA table_info(assistant_jobs)')}:
            db.execute("ALTER TABLE assistant_jobs ADD COLUMN media TEXT NOT NULL DEFAULT '[]'")


def channel_matches(chat, configured):
    return chat.get('type') == 'channel' and (
        str(chat.get('id')) == configured or
        (configured.startswith('@') and '@'+str(chat.get('username', '')).lower() == configured.lower()))


def queue_message(db, chat, message):
    mid = message.get('message_id')
    if type(mid) is not int or mid <= 0:
        return
    text = message.get('text') or message.get('caption') or ''
    if not isinstance(text, str):
        return
    media_kind = message.get('media_kind') or next((kind for kind in
        ('video','animation','photo','audio','voice','document','sticker') if message.get(kind)), '')
    description = message.get('media_description','')
    if not isinstance(description,str):
        description = ''
    details = message.get(media_kind)
    if isinstance(details, dict) and not description:
        description = '\n'.join(f'{key}: {details[key]}' for key in
                                ('file_name','mime_type','duration','file_size') if key in details)
    if media_kind:
        media_note = 'Telegram media type: '+str(media_kind)[:40]
        if description.strip():
            media_note += '\n'+description.strip()[:1000]
        text = text.strip()+'\n\n'+media_note
    text = text[:16000].strip()
    if not text:
        return
    media = message.get('media',[])
    if not isinstance(media,list):
        media=[]
    media=[value for value in media[:3] if isinstance(value,str) and
           len(value)<=2_500_000 and value.startswith(('data:image/jpeg;base64,','data:image/png;base64,','data:image/webp;base64,'))]
    media_json=json.dumps(media,separators=(',',':'))
    key = str(chat['id'])+':'+str(mid)
    digest = hashlib.sha256((text+'\0'+media_json).encode()).hexdigest()
    old = db.execute('SELECT digest FROM assistant_jobs WHERE key=?', (key,)).fetchone()
    if old and old[0] == digest:
        return
    username = chat.get('username', '')
    source = ('https://t.me/'+username+'/'+str(mid)) if re.fullmatch(r'[A-Za-z0-9_]+', username) else ''
    if not source and re.fullmatch(r'-100\d+', str(chat['id'])):
        source = 'https://t.me/c/'+str(chat['id'])[4:]+'/'+str(mid)
    db.execute('''INSERT INTO assistant_jobs(key,chat,message,source,text,digest,status,updated,media)
        VALUES(?,?,?,?,?,?,'pending',?,?) ON CONFLICT(key) DO UPDATE SET
        source=excluded.source,text=excluded.text,digest=excluded.digest,media=excluded.media,status='pending',
        attempts=0,retry_at=0,error='',updated=excluded.updated''',
        (key,str(chat['id']),mid,source,text,digest,int(time.time()),media_json))


def ingest(store, updates, configured, cursor_key):
    """Queue and acknowledge an update batch in one transaction; never acknowledge on failure."""
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        old = db.execute('SELECT value FROM assistant_state WHERE key=?', (cursor_key,)).fetchone()
        offset = int(old[0]) if old else 0
        for update in updates:
            uid = update.get('update_id')
            if type(uid) is not int or uid < offset:
                continue
            msg = update.get('channel_post') or update.get('edited_channel_post')
            if isinstance(msg, dict) and channel_matches(msg.get('chat', {}), configured):
                queue_message(db, msg['chat'], msg)
            offset = max(offset, uid+1)
        db.execute('INSERT OR REPLACE INTO assistant_state VALUES(?,?)', (cursor_key,str(offset)))


def localized(value, maximum):
    if not isinstance(value, dict) or set(value) != set(LANGS):
        raise ValueError('invalid_translations')
    if any(not isinstance(v, str) or not v.strip() or len(v) > maximum for v in value.values()):
        raise ValueError('invalid_text')
    return {key:value[key].strip() for key in LANGS}


def validate(result, source):
    if not isinstance(result, dict) or result.get('kind') not in ('sale','tutorial','article','ignore'):
        raise ValueError('invalid_classification')
    if result['kind'] == 'ignore':
        return {'kind':'ignore'}
    item = {'kind':result['kind'], 'title':localized(result.get('title'),180),
            'summary':localized(result.get('summary'),700), 'body':localized(result.get('body'),6000)}
    generic_titles = {'عنوان', 'عنوان محصول', 'پیشنهاد ویژه', 'پست جدید', 'توضیحات محصول',
                      'product title', 'special offer', 'new post', 'untitled',
                      'عنوان المنتج', 'عرض خاص', 'عنوان المنشور',
                      'título del producto', 'oferta especial', 'nueva publicación'}
    for lang in LANGS:
        title = item['title'][lang]
        if (title.casefold().strip(' .!؟?') in generic_titles or '\n' in title or
                re.fullmatch(r'[^\s/]+\.(?:mp4|mkv|mov|zip|rar|jpg|png|pdf)',title,re.I) or
                item['body'][lang].casefold() == item['summary'][lang].casefold()):
            raise ValueError('uninformative_content')
    item['brand'] = detected_brand(source, item['title'], result.get('brand'))
    # A claimed price is published only when its exact amount AND currency are present in the source.
    item['price'] = None
    price = result.get('price')
    if item['kind'] == 'sale' and isinstance(price, dict):
        try:
            amount = Decimal(str(price.get('amount')))
            currency = price.get('currency')
            normalized = source.translate(DIGITS).replace('٫', '.')
            if amount.is_finite() and amount > 0 and currency in ('USDT','USD','EUR'):
                for match in re.finditer(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(USDT|USD|EUR)(?!\w)',normalized,re.I):
                    if Decimal(match[1]) == amount and match[2].upper() == currency:
                        item['price'] = {'amount':format(amount,'f'), 'currency':currency}
                        break
        except (InvalidOperation, ValueError, TypeError):
            pass
    return item


def process_one(store, model, max_attempts=5):
    """Model work outside a transaction; atomic publish with optimistic revision check."""
    with store.db() as db:
        job = db.execute("""SELECT * FROM assistant_jobs
            WHERE status IN ('pending','retry') AND retry_at<=?
            ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, updated DESC, key LIMIT 1""",
            (int(time.time()),)).fetchone()
    if not job:
        return False
    try:
        media=json.loads(job['media']) if job['media'] else []
        item = validate(model.analyze(job['text'],media), job['text'])
    except Exception as exc:
        # Never log provider errors or request URLs: Telegram URLs contain a token.
        code = 'model_response_invalid' if isinstance(exc, ValueError) else getattr(exc,'code','provider_unavailable')
        attempts = job['attempts']+1
        with store.db() as db:
            db.execute('UPDATE assistant_jobs SET attempts=?,status=?,retry_at=?,error=? WHERE key=? AND digest=?',
                       (attempts,'failed' if attempts>=max_attempts else 'retry',int(time.time())+max(min(3600,30*2**attempts),min(3600,getattr(exc,'retry',0))),code,job['key'],job['digest']))
        return True
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        current = db.execute('SELECT digest FROM assistant_jobs WHERE key=?', (job['key'],)).fetchone()
        if not current or current[0] != job['digest']:
            return True
        if item['kind'] == 'ignore':
            db.execute('DELETE FROM assistant_posts WHERE key=?', (job['key'],))
        else:
            item.update(id=hashlib.sha256(job['key'].encode()).hexdigest()[:16],
                        source_url=job['source'],updated=int(time.time()),message_id=job['message'])
            db.execute('INSERT OR REPLACE INTO assistant_posts VALUES(?,?)', (job['key'],json.dumps(item,ensure_ascii=False)))
        db.execute("UPDATE assistant_jobs SET status=?,error='' WHERE key=?", ('ignored' if item['kind']=='ignore' else 'published',job['key']))
    return True


def public_posts(store):
    with store.db() as db:
        posts = [json.loads(row[0]) for row in db.execute('SELECT value FROM assistant_posts ORDER BY rowid DESC LIMIT 300')]
        contact = store.settings(db)['social_links'].get('telegram', '')
    # Resolve the current shop contact at read time, including for already-published posts.
    try:
        contact = validate_links({'telegram': contact})['telegram'] or DEFAULT_LINKS['telegram']
    except ValueError:
        contact = DEFAULT_LINKS['telegram']
    for post in posts:
        brand = post.get('brand')
        if brand not in (*BRAND_NAMES, 'generic'):
            brand = detected_brand(title=post.get('title'))
        post.update(brand=brand, order_url=contact)
    return posts


def requeue_published(store):
    """Keep current posts visible until a validated rewrite replaces the same IDs."""
    with store.db() as db:
        return db.execute("""UPDATE assistant_jobs SET status='pending',attempts=0,
            retry_at=0,error='',updated=? WHERE status='published'
            AND key IN (SELECT key FROM assistant_posts)""", (int(time.time()),)).rowcount


def status(store):
    with store.db() as db:
        counts = dict(db.execute('SELECT status,count(*) FROM assistant_jobs GROUP BY status').fetchall())
        recent = [dict(row) for row in db.execute('SELECT message,status,error,updated FROM assistant_jobs ORDER BY updated DESC LIMIT 20')]
    return {'counts':counts,'recent':recent}
