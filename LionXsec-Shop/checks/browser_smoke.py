"""Optional local browser checks: python -m checks.browser_smoke (Playwright + Chromium)."""
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright

from server import App, Store


def run():
    with tempfile.TemporaryDirectory() as folder:
        store = Store(Path(folder) / 'shop.sqlite3')
        password = secrets.token_urlsafe(24)
        store.init_admin(password)
        server = App(('127.0.0.1', 0), store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                            args=['--no-sandbox'])
                context = browser.new_context(viewport={'width':1440,'height':1000})
                page = context.new_page()
                errors, external = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('request', lambda r: external.append(r.url) if not r.url.startswith(origin) else None)
                page.goto(origin)
                page.locator('.product-card').first.wait_for()
                assert page.locator('.product-card').count() == 6
                assert page.locator('.service-chip').count() == 7
                assert page.locator('.product-card[data-brand=nordvpn] img.service-logo').count()==1
                assert page.locator('.product-card[data-brand=crunchyroll] img.service-logo').count()==1
                assert page.locator('.product-card[data-brand=dazn] img.service-logo').count()==1
                for language, direction in [('en','ltr'),('ar','rtl'),('es','ltr'),('fa','rtl')]:
                    page.locator('.language').select_option(language)
                    assert page.locator('html').get_attribute('lang') == language
                    assert page.locator('html').get_attribute('dir') == direction
                    assert page.locator('.product-card').count() == 6
                page.screenshot(path='/workspace/LionXsec-Shop-v1.2-desktop.png', full_page=True)
                page.screenshot(path='/workspace/LionXsec-Shop-v1.2-preview.png', full_page=False)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path='/workspace/LionXsec-Shop-v1.2-mobile.png', full_page=True)
                page.set_viewport_size({'width':1440,'height':1000})
                page.locator('.language').select_option('en')
                first=page.locator('.product-card').first
                first.locator('input[type=number]').fill('4')
                first.locator('[data-add]').click()
                assert page.locator('#cart-count').inner_text() == '0'
                first.locator('input[type=number]').fill('5')
                first.locator('[data-add]').click()
                assert page.locator('#cart-count').inner_text() == '5'
                page.locator('#cart-open').click()
                page.locator('#checkout').click()
                assert page.locator('#checkout-form').count() == 0
                page.keyboard.press('Escape')
                page.goto(origin+'/admin')
                page.locator('[name=password]').fill(password)
                page.locator('#login-form [type=submit]').click()
                page.locator('#dashboard').wait_for(state='visible')
                page.locator('[data-edit-product]').first.click()
                page.locator('[name=brand]').select_option('surfshark')
                for language in ('fa','en','ar','es'):
                    page.locator(f'[data-edit-lang={language}]').click()
                    page.locator(f'[name=name_{language}]').fill('Surfshark')
                page.locator('[name=price]').fill('2.75')
                page.locator('#product-form [type=submit]').click()
                page.locator('#edit-dialog').wait_for(state='hidden')
                assert store.catalog()['products'][0]['brand']=='surfshark'
                page.locator('[data-tab=wallets]').click()
                page.locator('[name=usdt_bep20]').fill('0x'+'12'*20)
                # Synthetic checksum-valid fixture; never used on a blockchain.
                page.locator('[name=ltc]').fill('LM9Ri4xRD9Q6PoiWNrZxeSYg6ffCpmXvcc')
                page.locator('[name=ltc_usdt_rate]').fill('50')
                with page.expect_response('**/api/admin/settings') as response:
                    page.locator('#wallet-form [type=submit]').click()
                assert response.value.status == 200
                page.goto(origin)
                page.locator('.product-card').first.wait_for()
                page.locator('#cart-open').click()
                page.locator('#checkout').click()
                page.locator('#checkout-form').wait_for()
                page.locator('[name=telegram]').fill('@local_demo')
                page.locator('#checkout-form [type=submit]').click()
                page.locator('#order-dialog').wait_for(state='visible')
                assert page.locator('.payment-amount').inner_text().startswith('13.75')
                assert 'BEP-20' in page.locator('#order-content').inner_text()
                assert page.locator('.copy-field input').input_value() == '0x'+'12'*20
                token=page.evaluate("localStorage.getItem('lx-order-token')")
                order=store.order(token)
                assert order['total_cents'] == 1375 and order['status']=='awaiting_payment'
                order_link=urlsplit(page.locator('.order-actions a').get_attribute('href'))
                assert (order_link.scheme,order_link.netloc,order_link.path)==('https','t.me','/LionXSec')
                assert order['id'] in parse_qs(order_link.query)['text'][0]
                page.keyboard.press('Escape')
                page.goto(origin+'/admin')
                page.locator('[data-tab=orders]').wait_for()
                page.locator('[data-tab=orders]').click()
                page.locator('[data-edit-order]').first.click()
                page.locator('[name=status]').select_option('paid')
                page.locator('#order-form [type=submit]').click()
                page.locator('#order-error').wait_for(state='visible')
                assert store.order(token)['status']=='awaiting_payment'
                page.locator('[name=manual_confirmed]').check()
                page.locator('#order-form [type=submit]').click()
                page.locator('#edit-dialog').wait_for(state='hidden')
                assert store.order(token)['status']=='paid'
                page.goto(origin)
                page.locator('.product-card').filter(has_not=page.locator('.demo-badge')).first.locator('[data-add]').click()
                page.locator('#cart-open').click()
                page.locator('#checkout').click()
                page.locator('[name=method][value=LTC]').check()
                page.locator('#checkout-form [type=submit]').click()
                page.locator('#order-dialog').wait_for(state='visible')
                token2=page.evaluate("localStorage.getItem('lx-order-token')")
                second=store.order(token2)
                assert second['method']=='LTC' and second['amount']=='0.27500000'
                assert page.locator('.copy-field input').input_value() == 'LM9Ri4xRD9Q6PoiWNrZxeSYg6ffCpmXvcc'
                assert not errors, errors
                assert not external, external
                browser.close()
                print('PASS: four languages / RTL, responsive layout, minimum quantity, demo blocking, admin edit, wallet save, USDT + LTC checkout, exact totals, manual confirmation; no external requests or JS errors.')
        finally:
            server.shutdown(); server.server_close(); thread.join()


if __name__ == '__main__':
    run()
