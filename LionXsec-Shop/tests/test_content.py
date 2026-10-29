import base64
import concurrent.futures
import http.cookiejar
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import zipfile
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler,HTTPCookieProcessor

from content import ContentError,LIMITS
from server import App,Store,LANGS

PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=')
VIDEO=b'\x00\x00\x00\x18ftypisom\x00\x00\x00\x00isomiso2'+b'\0'*1000


class ContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.store=Store(self.root/'shop.sqlite3');self.store.init_admin('temporary-admin-password')
        self.app=App(('127.0.0.1',0),self.store)
        self.worker=threading.Thread(target=self.app.serve_forever,daemon=True);self.worker.start()
        self.base=f'http://127.0.0.1:{self.app.server_port}'
        self.admin=build_opener(ProxyHandler({}),HTTPCookieProcessor(http.cookiejar.CookieJar()))
        result,status,_=self.request('/api/admin/login',{'password':'temporary-admin-password'},admin=True)
        assert status==200;self.csrf=result['csrf']

    def tearDown(self):
        self.app.shutdown();self.app.server_close();self.worker.join();self.temp.cleanup()

    def request(self,path,data=None,method=None,admin=False,csrf=False,headers=None):
        h={'Origin':self.base}
        if csrf:h['X-CSRF-Token']=self.csrf
        if isinstance(data,dict):data=json.dumps(data).encode();h['Content-Type']='application/json'
        elif data is not None:h['Content-Type']='application/octet-stream'
        h.update(headers or {})
        req=Request(self.base+path,data=data,method=method,headers=h)
        try:r=(self.admin if admin else build_opener(ProxyHandler({}))).open(req,timeout=5)
        except HTTPError as error:r=error
        body=r.read()
        if r.headers.get_content_type()=='application/json':body=json.loads(body)
        return body,r.status,r.headers

    def media(self,kind='logo'):
        raw=PNG if kind=='logo' else VIDEO
        return self.store.upload(io.BytesIO(raw),kind,len(raw),'sample.png' if kind=='logo' else 'sample.mp4')

    def resource(self,kind='tutorial',**kw):
        d={'kind':kind,'title':{l:'Local guide' for l in LANGS},'description':{l:'Description' for l in LANGS},'published':True}
        if kind=='tutorial':d['video_id']=self.media('video')['id']
        else:d['download_url']='https://example.com/tool.zip'
        return {**d,**kw}

    def test_binary_upload_needs_login_and_csrf(self):
        _,status,_=self.request('/api/admin/uploads?kind=logo',PNG);self.assertEqual(status,401)
        _,status,_=self.request('/api/admin/uploads?kind=logo',PNG,admin=True);self.assertEqual(status,403)
        media,status,_=self.request('/api/admin/uploads?kind=logo',PNG,admin=True,csrf=True,headers={'X-Upload-Name':'logo.png'})
        self.assertEqual(status,201);self.assertEqual(media['mime'],'image/png')
        raw,status,headers=self.request(media['url']);self.assertEqual(status,200);self.assertEqual(raw,PNG)
        self.assertEqual(headers['X-Content-Type-Options'],'nosniff')

    def test_any_format_is_identified_instead_of_refused(self):
        cases={
            b'<svg xmlns="http://www.w3.org/2000/svg"/>':('image/svg+xml','.svg'),
            b'<html><body>guide</body></html>':('text/html','.html'),
            b'MZ'+b'\x00'*500:('application/x-msdownload','.exe'),
            b'%PDF-1.7\n'+b'x'*200:('application/pdf','.pdf'),
            b'PK\x03\x04'+b'x'*200:('application/zip','.zip'),
            b'GIF89a'+b'\x00'*200:('image/gif','.gif'),
            b'ID3'+b'\x00'*200:('audio/mpeg','.mp3'),
            b'\x00'*200:('application/octet-stream','.bin'),
            b'hello admin, plain notes here\nsecond line':('text/plain','.txt'),
        }
        for payload,(mime,ext) in cases.items():
            media=self.store.upload(io.BytesIO(payload),'video',len(payload),'guide')
            self.assertEqual(media['mime'],mime)
            self.assertEqual(self.store.media_record(media['id'])['filename'],media['id']+ext)

    def test_spoofed_and_active_formats_are_rejected_from_the_logo_slot(self):
        for payload in (b'<svg onload="alert(1)"/>',b'<html>not an image</html>',b'MZ'+b'x'*500):
            _,status,_=self.request('/api/admin/uploads?kind=logo',payload,admin=True,csrf=True,headers={'Content-Type':'image/png'})
            self.assertEqual(status,415)
        for payload,expect in ((b'<svg onload="alert(1)"/>','image/svg+xml'),(b'MZ'+b'x'*500,'application/x-msdownload')):
            media,status,_=self.request('/api/admin/uploads?kind=video',payload,admin=True,csrf=True,headers={'X-Upload-Name':'tool.bin'})
            self.assertEqual(status,201);self.assertEqual(media['mime'],expect)
        self.assertEqual(len(self.store.media_list()),2)
        self.assertFalse(any(self.store.media_dir.glob('*.part')))

    def test_real_images_still_work_in_the_logo_slot(self):
        for payload,name,mime in ((b'GIF89a'+b'\x00'*200,'badge.gif','image/gif'),(b'RIFFxxxxWEBP','photo.webp','image/webp')):
            media=self.store.upload(io.BytesIO(payload),'logo',len(payload),name)
            self.assertEqual(media['mime'],mime)

    def test_declared_size_limit_rejected_without_allocating_video(self):
        class Unreadable:
            def read(self,*a):raise AssertionError('oversized upload should not be read')
        with self.assertRaises(ContentError) as error:self.store.upload(Unreadable(),'video',LIMITS['video']+1,'huge.mp4')
        self.assertEqual(error.exception.status,413)

    def test_interrupted_upload_leaves_no_partial_file(self):
        with self.assertRaises(ContentError):self.store.upload(io.BytesIO(PNG),'logo',len(PNG)+10,'short.png')
        self.assertFalse(list(self.store.media_dir.iterdir()))
        self.assertEqual(self.store.media_list(),[])

    def test_custom_logo_survives_restart_and_can_be_removed(self):
        media=self.media()
        data={'name':{l:'Custom' for l in LANGS},'duration':{l:'30 days' for l in LANGS},'delivery':{l:'Telegram' for l in LANGS},'price':'2.50','logo_id':media['id']}
        p=self.store.save_product(data)
        reopened=next(x for x in Store(self.store.path).catalog()['products'] if x['id']==p['id'])
        self.assertEqual(reopened['logo_id'],media['id'])
        with self.assertRaises(ContentError):self.store.delete_media(media['id'])
        p=self.store.save_product({**data,'logo_id':''},p['id']);self.assertIsNone(p['logo_id'])
        self.store.delete_media(media['id']);self.assertFalse(list(self.store.media_dir.iterdir()))

    def test_logo_must_reference_an_image_not_a_video_or_path(self):
        data={'name':{l:'Custom' for l in LANGS},'duration':{l:'30 days' for l in LANGS},'delivery':{l:'Telegram' for l in LANGS},'price':'2.50'}
        for logo in ('../../private',self.media('video')['id']):
            with self.assertRaises(ContentError):self.store.save_product({**data,'logo_id':logo})

    def test_unpublished_resources_are_hidden_from_public_listing(self):
        d=self.resource(published=False);item=self.store.save_resource(d)
        self.assertEqual(self.store.resources(),[])
        self.assertEqual(len(self.store.resources(True)),1)
        self.store.save_resource({**d,'published':True},item['id'])
        r=self.store.resources()[0];self.assertEqual(r['video_url'],'/media/'+d['video_id'])
        self.assertEqual(set(r['title']),set(LANGS))
        self.store.delete_resource(item['id']);self.assertEqual(self.store.resources(),[])

    def test_resource_crud_requires_admin_and_valid_links(self):
        payload=self.resource('tool')
        _,status,_=self.request('/api/admin/resources',payload);self.assertEqual(status,401)
        item,status,_=self.request('/api/admin/resources',payload,admin=True,csrf=True);self.assertEqual(status,201)
        result,status,_=self.request('/api/resources');self.assertEqual(status,200);self.assertEqual(result['resources'][0]['id'],item['id'])
        for url in ('javascript:alert(1)','data:text/html,hi','http://example.com/x','https://a:b@example.com/x'):
            with self.subTest(url=url),self.assertRaises(ContentError):self.store.save_resource(self.resource('tool',download_url=url))
        self.assertEqual(len(Store(self.store.path).resources()),1)

    def test_video_byte_ranges_and_head(self):
        media=self.media('video')
        for requested,expected in [('bytes=0-15',VIDEO[:16]),('bytes=16-',VIDEO[16:]),('bytes=-8',VIDEO[-8:])]:
            body,status,h=self.request(media['url'],headers={'Range':requested})
            self.assertEqual(status,206);self.assertEqual(body,expected);self.assertIn('bytes ',h['Content-Range'])
        for requested in ('bytes=99999-','bytes=4-2','bytes=-0','bytes=0-1,3-4','bytes='):
            _,status,_=self.request(media['url'],headers={'Range':requested});self.assertEqual(status,416)
        body,status,h=self.request(media['url'],method='HEAD');self.assertEqual(status,200);self.assertEqual(body,b'');self.assertEqual(int(h['Content-Length']),len(VIDEO))

    def test_file_names_cannot_escape_media_directory(self):
        media=self.store.upload(io.BytesIO(PNG),'logo',len(PNG),'../../secret\r\n.html')
        row=self.store.media_record(media['id'])
        self.assertTrue((self.store.media_dir/row['filename']).is_file())
        self.assertNotIn('/',row['filename']);self.assertNotIn('\n',row['original_name'])
        _,status,_=self.request('/media/../../server.py');self.assertEqual(status,404)

    def test_video_deletion_protected_until_content_removed(self):
        payload=self.resource();item=self.store.save_resource(payload)
        with self.assertRaises(ContentError):self.store.delete_media(payload['video_id'])
        self.store.delete_resource(item['id']);self.store.delete_media(payload['video_id'])
        self.assertEqual(self.store.media_list(),[])

    def test_existing_database_migrates_without_erasing_products_or_orders(self):
        before=self.store.catalog()['products']
        with self.store.db() as db:db.execute('DROP TABLE resources');db.execute('DROP TABLE media')
        upgraded=Store(self.store.path)
        self.assertEqual(upgraded.catalog()['products'],before)
        self.assertEqual(upgraded.resources(),[])

    def test_backup_bundle_includes_database_and_uploaded_files(self):
        media=self.media();backup=self.root/'backup.zip'
        subprocess.run([sys.executable,'backup.py',str(backup),'--source',str(self.store.path)],check=True,capture_output=True)
        with zipfile.ZipFile(backup) as archive:
            self.assertIsNone(archive.testzip())
            self.assertIn('shop.sqlite3',archive.namelist())
            row=self.store.media_record(media['id'])
            self.assertEqual(archive.read('media/'+row['filename']),PNG)
            restored=self.root/'restored.sqlite3'
            restored.write_bytes(archive.read('shop.sqlite3'))
        connection=sqlite3.connect(restored)
        try:self.assertEqual(connection.execute('SELECT id FROM media').fetchone()[0],media['id'])
        finally:connection.close()
        result=subprocess.run([sys.executable,'backup.py',str(backup),'--source',str(self.store.path)],capture_output=True)
        self.assertNotEqual(result.returncode,0)
        self.assertTrue(backup.is_file())


if __name__=='__main__':unittest.main()
