"""Offline integration: real browser/server/database, simulated AI/Telegram responses."""
from pathlib import Path
import secrets
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect
from assistant import Runner
from automation import ingest, process_one
from server import App, Store


def run():
    with tempfile.TemporaryDirectory() as folder:
        store=Store(Path(folder)/'shop.sqlite3')
        password=secrets.token_urlsafe(24)
        store.init_admin(password)
        for index,kind in enumerate(('sale','tutorial','article','sale'),1):
            channel='' if index==4 else 'my_channel'
            ingest(store,[{'update_id':index,'channel_post':{'message_id':index,
                'chat':{'type':'channel','id':-1001234567890,'username':channel},
                'text':'Netflix Premium 1 month 12.50 USDT' if index==1 else 'Sample subscription 12.50 USDT'}}],'-1001234567890','local-test')
            class Model:
                def analyze(self,text,media=None):
                    local=lambda value:dict.fromkeys(('fa','en','ar','es'),value)
                    title={'fa':'اشتراک Netflix Premium یک‌ماهه','en':'Netflix Premium — 1 month',
                           'ar':'اشتراك Netflix Premium لشهر واحد','es':'Netflix Premium — 1 mes'} if index==1 else local('نمونه '+kind)
                    return {'kind':kind,'title':title,'summary':local('توضیحات آزمایشی'),
                            'body':local('<img src=x onerror=alert(1)> متن توضیحات'),
                            'price':{'amount':'12.50','currency':'USDT'}}
            process_one(store,Model())
        app=App(('127.0.0.1',0),store)
        thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
        runner=Runner(store);runner.start()
        origin=f'http://127.0.0.1:{app.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];external=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.on('request',lambda r:external.append(r.url) if not r.url.startswith(origin) else None)
                page.goto(origin)
                for kind in ('sale','tutorial','article'):
                    expect(page.locator('#assistant-'+kind+' .assistant-card')).to_have_count(2 if kind=='sale' else 1)
                expect(page.locator('#catalog #assistant-sale')).to_be_visible()
                expect(page.locator('#tutorials #assistant-tutorial')).to_be_visible()
                expect(page.locator('#assistant-sale strong')).to_have_text(['12.50 USDT','12.50 USDT'])
                page.locator('#assistant-sale summary').first.click()
                expect(page.locator('#assistant-sale .assistant-body').first).to_contain_text('<img')
                expect(page.locator('#assistant-sale .assistant-body img')).to_have_count(0)
                for logo in page.locator('.assistant-logo img').all():
                    expect(logo).to_have_attribute('src','/assets/lion-logo.png')
                    expect(logo).to_have_css('filter','none')
                expect(page.locator('.brand-lion')).to_have_attribute('src','/assets/lion-logo.png')
                expect(page.locator('link[rel=icon]')).to_have_attribute('href','/assets/lion-logo.png')
                assert page.locator('.assistant-logo img').evaluate_all('(images)=>images.every(i=>i.complete&&i.naturalWidth>0)')
                expect(page.locator('#assistant-sale .assistant-source[href*="/c/"]')).to_have_count(1)
                expect(page.locator('[data-support-handle]').first).to_contain_text('@LionXSec')
                for language in ('fa','en','ar','es'):
                    page.locator('.language').select_option(language)
                    for order in page.locator('.assistant-order').all():
                        expect(order).to_have_attribute('href','https://t.me/LionXSec')
                    expect(page.locator('#assistant-sale [data-brand=netflix] h3')).to_contain_text('Netflix Premium')
                    page.set_viewport_size({'width':390,'height':844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('.language').select_option('fa')
                # Contact changes affect old cards and checkout/support without re-running AI.
                store.save_social_links({'telegram':'https://t.me/shop_contact'})
                page.reload()
                expect(page.locator('.assistant-order').first).to_have_attribute('href','https://t.me/shop_contact')
                expect(page.locator('[data-support-link]').first).to_have_attribute('href','https://t.me/shop_contact')
                store.save_social_links({'telegram':'https://t.me/LionXSec'})
                page.reload()
                expect(page.locator('.assistant-order').first).to_have_attribute('href','https://t.me/LionXSec')
                page.set_viewport_size({'width':1440,'height':1000})
                page.locator('#assistant-sale').screenshot(path=str(Path(__file__).resolve().parents[1]/'test-results/assistant-cards.png'))
                page.goto(origin+'/admin')
                assert page.request.get(origin+'/api/admin/assistant').status==401
                assert page.request.post(origin+'/api/admin/assistant/reprocess',data={}).status==401
                page.locator('[name=password]').fill(password)
                page.locator('#login-form [type=submit]').click()
                page.locator('[data-tab=assistant]').click()
                expect(page.locator('#assistant-form')).to_be_visible()
                expect(page.locator('[name=enabled]')).not_to_be_checked()
                assert page.request.put(origin+'/api/admin/assistant',data={'enabled':False}).status==403
                assert page.request.post(origin+'/api/admin/assistant/reprocess',data={}).status==403
                with page.expect_response('**/api/admin/assistant/reprocess') as rewritten:
                    page.locator('#assistant-reprocess').click()
                assert rewritten.value.status==200
                assert rewritten.value.json()['queued']==4
                expect(page.locator('#assistant-reprocess-result')).to_contain_text('4')
                assert len(page.request.get(origin+'/api/assistant/posts').json()['posts'])==4
                assert page.request.get(origin+'/api/admin/assistant').json()['counts']=={'pending':4}
                page.locator('[name=channel]').fill('@my_channel')
                page.locator('[name=bot_token]').fill('LOCAL_TEST_BOT_SENTINEL')
                page.locator('[name=api_key]').fill('LOCAL_TEST_AI_SENTINEL')
                with page.expect_response('**/api/admin/assistant') as saved:
                    page.locator('#assistant-form [type=submit]').click()
                assert saved.value.status==200
                response=page.request.get(origin+'/api/admin/assistant')
                assert 'SENTINEL' not in response.text()
                assert response.json()['runtime']['state']=='disabled'
                assert page.request.get(origin+'/data/assistant-config.json').status==404
                assert page.request.get(origin+'/assistant-config.json').status==404
                page.reload();page.locator('[data-tab=assistant]').click()
                expect(page.locator('[name=channel]')).to_have_value('@my_channel')
                expect(page.locator('[name=api_key]')).to_have_value('')
                page.locator('[name=source]').select_option('account')
                expect(page.locator('[name=bot_token]')).to_be_hidden()
                page.locator('[name=telegram_api_id]').fill('123456')
                page.locator('[name=telegram_api_hash]').fill('a'*32)
                with page.expect_response('**/api/admin/assistant') as account_saved:
                    page.locator('#assistant-form [type=submit]').click()
                assert account_saved.value.status==200
                account_config=page.request.get(origin+'/api/admin/assistant').json()['config']
                assert account_config['source']=='account'
                assert 'telegram_api_hash' not in account_config
                page.reload();page.locator('[data-tab=assistant]').click()
                expect(page.locator('[name=source]')).to_have_value('account')
                expect(page.locator('[name=telegram_api_hash]')).to_have_value('')
                page.locator('[name=provider]').select_option('ollama')
                expect(page.locator('[name=api_key]')).to_be_hidden()
                expect(page.locator('[name=model]')).to_have_value('qwen3-vl:4b')
                page.set_viewport_size({'width':1440,'height':1000})
                page.screenshot(path=str(Path(__file__).resolve().parents[1]/'test-results/assistant-admin.png'),full_page=True)
                assert not errors,errors
                assert not external,external
                browser.close()
                print('PASS: real local server/browser; uniform lion logos, header and favicon; public/private source vs order contact; legacy contact refresh; four languages/mobile; escaped AI text; authenticated/CSRF-protected rewrite preserving current posts; admin settings; secret redaction; zero external calls. Model/Telegram responses simulated.')
        finally:
            runner.stop.set();runner.thread.join(timeout=4)
            app.shutdown();app.server_close();thread.join()


if __name__=='__main__':
    run()
