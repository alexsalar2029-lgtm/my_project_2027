"""Local browser checks for the headline and configurable social profiles."""
from pathlib import Path
import secrets
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect
from server import App, Store
from social import DEFAULT_LINKS


def run():
    with tempfile.TemporaryDirectory() as folder:
        store = Store(Path(folder) / 'shop.sqlite3')
        password = secrets.token_urlsafe(24)
        store.init_admin(password)
        app = App(('127.0.0.1', 0), store)
        worker = threading.Thread(target=app.serve_forever, daemon=True)
        worker.start()
        origin = f'http://127.0.0.1:{app.server_port}'
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox'])
                context = browser.new_context(viewport={'width':1440, 'height':1000})
                # Clicking social links must not contact any real accounts during checks.
                context.route('https://**/*', lambda route: route.fulfill(status=200, body='Local social navigation test'))
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(origin)
                expect(page.locator('h1')).to_contain_text('خرید عمده اکانت پرمیوم با گارانتی')
                expect(page.locator('h1')).to_contain_text('و خرید ابزارهای خصوصی کمیاب')
                expect(page.locator('#social-links a')).to_have_count(2)
                for key in ('youtube', 'telegram'):
                    link = page.locator(f'[data-social={key}]')
                    expect(link).to_be_visible()
                    expect(link).to_have_attribute('href', DEFAULT_LINKS[key])
                    with page.expect_popup() as popup:
                        link.click()
                    popup.value.wait_for_load_state()
                    assert popup.value.url == DEFAULT_LINKS[key]
                    popup.value.close()
                for language in ('fa', 'en', 'ar', 'es'):
                    page.locator('.language').select_option(language)
                    for width in (320, 390, 768, 1440):
                        page.set_viewport_size({'width':width, 'height':1000})
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (language, width)
                        expect(page.locator('[data-social=youtube]')).to_be_visible()
                        assert page.locator('h1').bounding_box()['width'] <= width
                page.locator('.language').select_option('fa')
                page.screenshot(path='/workspace/LionXsec-Shop-v1.3-desktop.png', full_page=True)
                page.set_viewport_size({'width':390, 'height':844})
                page.screenshot(path='/workspace/LionXsec-Shop-v1.3-mobile.png', full_page=True)
                response = context.request.put(origin+'/api/admin/social-links', data={'youtube':''})
                assert response.status == 401
                page.goto(origin+'/admin')
                page.locator('[name=password]').fill(password)
                page.locator('#login-form [type=submit]').click()
                page.locator('[data-tab=social]').click()
                expect(page.locator('[name=youtube]')).to_have_value(DEFAULT_LINKS['youtube'])
                # Server rejects misleading links, even when valid browser URL syntax.
                page.locator('[name=instagram]').fill('https://example.com/wrong-network')
                page.locator('#social-form [type=submit]').click()
                expect(page.locator('#social-error')).to_be_visible()
                page.locator('[name=instagram]').fill('https://www.instagram.com/local_test/')
                page.locator('[name=youtube]').fill('')
                with page.expect_response('**/api/admin/social-links') as saved:
                    page.locator('#social-form [type=submit]').click()
                assert saved.value.status == 200
                page.reload()
                page.locator('[data-tab=social]').click()
                expect(page.locator('[name=youtube]')).to_have_value('')
                expect(page.locator('[name=instagram]')).to_have_value('https://www.instagram.com/local_test/')
                page.goto(origin)
                expect(page.locator('[data-social=youtube]')).to_have_count(0)
                expect(page.locator('[data-social=instagram]')).to_be_visible()
                reopened = Store(store.path)
                assert reopened.catalog()['settings']['social_links']['youtube'] == ''
                reopened.save_settings({'usdt_bep20':'', 'ltc':'', 'ltc_usdt_rate':''})
                assert reopened.catalog()['settings']['social_links']['instagram'] == 'https://www.instagram.com/local_test/'
                assert not errors, errors
                browser.close()
                print('PASS: four languages, 320/390/768/1440 layouts, YouTube and Telegram click destinations, admin editing, URL validation, persistence, hidden empty links and payment-setting compatibility.')
        finally:
            app.shutdown()
            app.server_close()
            worker.join()


if __name__ == '__main__':
    run()
