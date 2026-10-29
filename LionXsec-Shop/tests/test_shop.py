import concurrent.futures
from decimal import Decimal
import hashlib
import http.cookiejar
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request, ProxyHandler
from unittest.mock import patch

from server import App, Store, LANGS, Problem, now, valid_ltc


def ltc_address():
    raw = bytes([48]) + b'\x15' * 20
    raw += hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    n, out = int.from_bytes(raw, 'big'), ''
    chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    while n:
        n, r = divmod(n, 58)
        out = chars[r] + out
    return out


class ShopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.store = Store(Path(cls.temp.name) / 'shop.sqlite3')
        cls.store.init_admin('test-only-long-password')
        cls.app = App(('127.0.0.1', 0), cls.store)
        cls.thread = threading.Thread(target=cls.app.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.app.server_port}'
        cls.admin = build_opener(ProxyHandler({}), HTTPCookieProcessor(http.cookiejar.CookieJar()))
        result, code, headers = cls.request('/api/admin/login', {'password':'test-only-long-password'}, opener=cls.admin)
        assert code == 200
        cls.csrf = result['csrf']
        cls.product_data = {
            'name': {l: 'Test product' for l in LANGS}, 'duration': {l: '30 days' for l in LANGS},
            'delivery': {l:'Manual Telegram delivery' for l in LANGS}, 'price':'3.49', 'active':True, 'category':'work'}
        cls.product = cls.store.save_product(cls.product_data)
        cls.wallet = '0x' + '12' * 20

    @classmethod
    def tearDownClass(cls):
        cls.app.shutdown(); cls.app.server_close(); cls.thread.join(); cls.temp.cleanup()

    @classmethod
    def request(cls, path, data=None, method=None, opener=None, csrf=False, extra=None):
        headers = {'Content-Type':'application/json', 'Origin':cls.base}
        if csrf: headers['X-CSRF-Token'] = cls.csrf
        headers.update(extra or {})
        req = Request(cls.base+path, data=json.dumps(data).encode() if data is not None else None,
                      method=method, headers=headers)
        try:
            r = (opener or build_opener(ProxyHandler({}))).open(req, timeout=10)
        except HTTPError as e:
            r = e
        body = r.read()
        try: body = json.loads(body)
        except ValueError: pass
        return body, r.status, r.headers

    def setUp(self):
        self.store.save_settings({'usdt_bep20':self.wallet, 'ltc':ltc_address(), 'ltc_usdt_rate':'71.25'})

    def order_data(self, **changes):
        return {'items':[{'id':self.product['id'],'quantity':5}], 'method':'USDT_BEP20','language':'fa', **changes}

    def test_public_catalog_and_four_translations(self):
        data, code, _ = self.request('/api/catalog')
        self.assertEqual(code, 200)
        self.assertEqual(data['minimum_quantity'], 5)
        self.assertEqual(set(data['methods']), {'LTC','USDT_BEP20'})
        for p in data['products']:
            for f in ('name','duration','delivery'): self.assertEqual(set(p[f]),set(LANGS))

    def test_minimum_and_integer_constraints_at_server(self):
        for qty in (0,1,4,-5,5.5,'5',True,10001):
            with self.subTest(qty=qty):
                data,code,_=self.request('/api/orders',self.order_data(items=[{'id':self.product['id'],'quantity':qty}]))
                self.assertEqual((code,data['error']),(400,'minimum_quantity'))

    def test_no_wallet_means_no_orders(self):
        self.store.save_settings({})
        data,code,_=self.request('/api/orders',self.order_data())
        self.assertEqual((code,data['error']),(409,'payment_unavailable'))

    def test_demo_cannot_be_ordered(self):
        demo=next(p for p in self.store.catalog()['products'] if p.get('demo'))
        with self.assertRaisesRegex(Problem,'product_unavailable'):
            self.store.create_order(self.order_data(items=[{'id':demo['id'],'quantity':5}]))

    def test_server_ignores_client_prices_and_freezes_wallet_and_product(self):
        order=self.store.create_order(self.order_data(total_cents=1,amount='0.01',address='attacker',items=[{'id':self.product['id'],'quantity':5,'unit_cents':0}]))
        self.assertEqual(order['total_cents'],1745)
        self.assertEqual(order['amount'],'17.45')
        self.assertEqual(order['address'],self.wallet)
        ids_before=[p['id'] for p in self.store.catalog()['products']]
        self.store.save_product({**self.product_data,'price':'9.99'},self.product['id'])
        self.assertEqual(ids_before,[p['id'] for p in self.store.catalog()['products']])
        self.store.save_settings({'usdt_bep20':'0x'+'34'*20})
        saved=self.store.order(order['access_token'])
        self.assertEqual(saved['total_cents'],1745)
        self.assertEqual(saved['address'],self.wallet)
        self.assertEqual(saved['items'][0]['unit_cents'],349)
        self.store.save_product(self.product_data,self.product['id'])

    def test_ltc_precise_rounded_up_quote(self):
        order=self.store.create_order(self.order_data(method='LTC'))
        expected=Decimal('17.45')/Decimal('71.25')
        self.assertGreaterEqual(Decimal(order['amount']),expected)
        self.assertLess(Decimal(order['amount'])-expected,Decimal('0.00000001'))
        self.assertEqual(order['rate'],'71.25')
        self.assertEqual(order['quote_expires']-order['created'],1800)

    def test_old_ltc_rate_is_rejected_but_usdt_still_works(self):
        with self.store.db() as db:
            s=self.store.settings(db);s['rate_updated']=now()-86401
            db.execute('UPDATE settings SET value=? WHERE id=1',(json.dumps(s),))
        with self.assertRaisesRegex(Problem,'rate_expired'): self.store.create_order(self.order_data(method='LTC'))
        self.assertEqual(self.store.create_order(self.order_data())['status'],'awaiting_payment')

    def test_duplicate_lines_and_inactive_products_rejected(self):
        with self.assertRaisesRegex(Problem,'minimum_quantity'):
            self.store.create_order(self.order_data(items=[{'id':self.product['id'],'quantity':5}]*2))
        p=self.store.save_product({**self.product_data,'active':False})
        with self.assertRaisesRegex(Problem,'product_unavailable'):
            self.store.create_order(self.order_data(items=[{'id':p['id'],'quantity':5}]))

    def test_manual_confirmation_and_transitions(self):
        order=self.store.create_order(self.order_data())
        with self.assertRaisesRegex(Problem,'manual_confirmation_required'):
            self.store.update_order(order['id'],{'status':'paid'})
        with self.assertRaisesRegex(Problem,'invalid_status_transition'):
            self.store.update_order(order['id'],{'status':'delivered','manual_confirmed':True})
        self.store.update_order(order['id'],{'status':'paid','manual_confirmed':True,'notes':'private note','txid':'a'*64})
        public=self.store.order(order['access_token'])
        self.assertEqual(public['status'],'paid')
        self.assertNotIn('notes',public);self.assertNotIn('txid',public);self.assertNotIn('telegram',public)
        self.store.update_order(order['id'],{'status':'delivered','manual_confirmed':True})
        self.assertEqual(self.store.order(order['access_token'])['status'],'delivered')

    def test_order_number_does_not_grant_public_access(self):
        order=self.store.create_order(self.order_data())
        _,code,_=self.request('/api/orders/'+order['id']);self.assertEqual(code,404)
        _,code,_=self.request('/api/orders/'+order['access_token']);self.assertEqual(code,200)
        with self.store.db() as db:
            token=db.execute('SELECT token FROM orders WHERE id=?',(order['id'],)).fetchone()[0]
        self.assertNotEqual(token,order['access_token'])

    def test_admin_access_and_csrf(self):
        for path in ('/api/admin/me','/api/admin/catalog','/api/admin/orders'):
            _,code,_=self.request(path);self.assertEqual(code,401)
        _,code,_=self.request('/api/admin/settings',{},'PUT',opener=self.admin);self.assertEqual(code,403)
        _,code,_=self.request('/api/admin/settings',{},'PUT',opener=self.admin,csrf=True);self.assertEqual(code,200)

    def test_cross_origin_login_and_writes_rejected(self):
        _,code,_=self.request('/api/admin/login',{'password':'test-only-long-password'},extra={'Origin':'https://evil.example'})
        self.assertEqual(code,403)
        _,code,_=self.request('/api/orders',self.order_data(),extra={'Sec-Fetch-Site':'cross-site'})
        self.assertEqual(code,403)

    def test_product_validation_and_persistent_crud(self):
        invalid={**self.product_data,'name':{'en':'Only English'}}
        _,code,_=self.request('/api/admin/products',invalid,opener=self.admin,csrf=True);self.assertEqual(code,400)
        for price in ('NaN','Infinity','-2','0','1.001'):
            with self.subTest(price=price),self.assertRaises(Problem): self.store.save_product({**self.product_data,'price':price})
        p,code,_=self.request('/api/admin/products',self.product_data,opener=self.admin,csrf=True);self.assertEqual(code,201)
        reopened=Store(self.store.path)
        self.assertIn(p['id'],[x['id'] for x in reopened.catalog()['products']])
        _,code,_=self.request('/api/admin/products/'+p['id'],{},'DELETE',self.admin,csrf=True);self.assertEqual(code,200)

    def test_brand_selection_is_persistent_and_only_local_assets_are_allowed(self):
        for brand in ('nordvpn','crunchyroll','dazn','surfshark','generic'):
            p=self.store.save_product({**self.product_data,'brand':brand})
            self.assertEqual(next(x for x in Store(self.store.path).catalog()['products'] if x['id']==p['id'])['brand'],brand)
        for brand in ('../../server.py','https://evil.example/logo.svg','unknown'):
            with self.subTest(brand=brand),self.assertRaises(Problem):
                self.store.save_product({**self.product_data,'brand':brand})
        for asset in ('lion-mark.svg','nordvpn.svg','crunchyroll.svg','dazn.svg'):
            _,code,headers=self.request('/assets/'+asset)
            self.assertEqual(code,200)
            self.assertEqual(headers['Content-Type'],'image/svg+xml')
        _,code,_=self.request('/assets/%2e%2e%2fserver.py');self.assertEqual(code,404)

    def test_wallet_checksums_and_rate_validation(self):
        self.assertTrue(valid_ltc(ltc_address()))
        self.assertFalse(valid_ltc(ltc_address()[:-1]+'0'))
        for data in ({'usdt_bep20':'0x'+'0'*40},{'usdt_bep20':'TRON-address'}, {'ltc':'ltc1bad'}, {'ltc_usdt_rate':'NaN'},{'ltc_usdt_rate':'0'}):
            with self.subTest(data=data),self.assertRaises(Problem): self.store.save_settings(data)

    def test_parallel_order_refs_and_private_tokens_are_unique(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            orders=list(pool.map(lambda _:self.store.create_order(self.order_data()),range(10)))
        self.assertEqual(len({o['id'] for o in orders}),10)
        self.assertEqual(len({o['access_token'] for o in orders}),10)

    def test_security_headers_static_files_and_path_traversal(self):
        for path in ('/','/admin','/app.js','/styles.css'):
            _,code,headers=self.request(path)
            self.assertEqual(code,200);self.assertEqual(headers['X-Frame-Options'],'DENY')
            self.assertIn("connect-src 'self'",headers['Content-Security-Policy'])
        _,code,_=self.request('/../server.py');self.assertEqual(code,404)

    def test_logout_revokes_server_session(self):
        client=build_opener(ProxyHandler({}),HTTPCookieProcessor(http.cookiejar.CookieJar()))
        result,code,headers=self.request('/api/admin/login',{'password':'test-only-long-password'},opener=client)
        self.assertEqual(code,200);self.assertIn('HttpOnly',headers['Set-Cookie']);self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        _,code,_=self.request('/api/admin/logout',{},opener=client,extra={'X-CSRF-Token':result['csrf']});self.assertEqual(code,200)
        _,code,_=self.request('/api/admin/me',opener=client);self.assertEqual(code,401)


if __name__=='__main__': unittest.main()
