"""End-to-end v1.2 features using local uploads, a generated test video, and Chromium."""
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import threading

from playwright.sync_api import sync_playwright,expect
from server import App,Store,ROOT


def run():
    with tempfile.TemporaryDirectory() as folder:
        folder=Path(folder)
        clip=folder/'test-guide.webm'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
                        'color=c=blue:s=160x90:r=5','-t','1','-c:v','libvpx','-an',str(clip)],check=True)
        store=Store(folder/'data'/'shop.sqlite3');password=secrets.token_urlsafe(24);store.init_admin(password)
        app=App(('127.0.0.1',0),store);thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
        origin=f'http://127.0.0.1:{app.server_port}'
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];external=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:external.append(request.url) if not request.url.startswith(origin) else None)
                page.goto(origin+'/admin');page.locator('.language').select_option('en')
                page.locator('[name=password]').fill(password);page.locator('#login-form [type=submit]').click()
                page.locator('#new-product').click()
                page.locator('[name=name_en]').fill('Local product')
                page.locator('[name=duration_en]').fill('30 days')
                page.locator('[name=delivery_en]').fill('Manual Telegram delivery')
                page.locator('#product-form .copy-translations').click()
                page.locator('[name=price]').fill('4.20')
                with page.expect_response('**/api/admin/uploads?kind=logo') as response:
                    page.locator('#product-logo-file').set_input_files(ROOT/'static/assets/lion-hero.png')
                assert response.value.status==201
                expect(page.locator('[name=logo_id]')).to_have_value(re.compile('[0-9a-f]{32}'))
                page.locator('#product-form [type=submit]').click();page.locator('#edit-dialog').wait_for(state='hidden')
                product=next(p for p in store.catalog()['products'] if p['name']['en']=='Local product')
                assert product['logo_id'] and product['price_cents']==420
                page.locator('.admin-product').filter(has_text='Local product').locator('[data-edit-product]').click()
                page.screenshot(path='/workspace/LionXsec-Shop-v1.2-admin-logo.png',full_page=True)
                page.keyboard.press('Escape')
                page.goto(origin)
                card=page.locator('.product-card').filter(has_text='Local product')
                expect(card.locator('.uploaded-logo')).to_be_visible()
                assert card.locator('img.uploaded-logo').evaluate('(img)=>img.complete && img.naturalWidth>0')
                expect(card.locator('[data-product-total]')).to_have_text('21.00 USDT')
                card.locator('[data-qty=plus]').click();expect(card.locator('[data-product-total]')).to_have_text('25.20 USDT')
                card.locator('input[type=number]').fill('10');expect(card.locator('[data-product-total]')).to_have_text('42.00 USDT')
                card.locator('[data-add]').click();page.locator('#cart-open').click()
                page.locator('[data-cart-input]').fill('12')
                expect(page.locator('.item-total')).to_have_text('50.40 USDT')
                expect(page.locator('.cart-footer .total-row strong')).to_have_text('50.40 USDT')
                page.keyboard.press('Escape')
                page.goto(origin+'/admin');page.locator('[data-tab=tutorials]').click();page.locator('#new-resource').click()
                page.locator('[name=title_en]').fill('Sample guide')
                page.locator('[name=description_en]').fill('Local video upload and playback test.')
                page.locator('#resource-copy-translations').click()
                with page.expect_response('**/api/admin/uploads?kind=video') as response:
                    page.locator('#resource-video-file').set_input_files(clip)
                assert response.value.status==201
                expect(page.locator('[name=video_id]')).to_have_value(re.compile('[0-9a-f]{32}'))
                page.locator('#resource-form [type=submit]').click();page.locator('#edit-dialog').wait_for(state='hidden')
                page.locator('[data-tab=tools]').click();page.locator('#new-resource').click()
                page.locator('[name=title_en]').fill('Example free tool')
                page.locator('[name=description_en]').fill('A local test of the download-link feature.')
                page.locator('#resource-copy-translations').click()
                page.locator('[name=download_url]').fill('https://example.com/tool.zip')
                page.locator('#resource-form [type=submit]').click();page.locator('#edit-dialog').wait_for(state='hidden')
                assert len(store.resources())==2
                page.goto(origin);page.locator('#tutorial-list video').wait_for()
                video=page.locator('#tutorial-list video')
                video.evaluate('(video)=>{video.muted=true;return video.play();}')
                assert video.evaluate('(video)=>video.readyState>=2 && video.duration>0')
                expect(page.locator('#tool-list a')).to_have_attribute('href','https://example.com/tool.zip')
                page.locator('#tutorials').screenshot(path='/workspace/LionXsec-Shop-v1.2-tutorials.png')
                for language in ('fa','ar','es','en'):
                    page.locator('.language').select_option(language)
                    expect(page.locator('#tutorial-list h3')).to_have_text('Sample guide')
                    expect(page.locator('#tool-list h3')).to_have_text('Example free tool')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('#tools').screenshot(path='/workspace/LionXsec-Shop-v1.2-tools-mobile.png')
                assert not errors,errors
                assert not external,external
                browser.close()
                print('PASS: new product, copy translations, local logo upload and persistence, live card/cart totals, video upload and actual playback, free download links, four languages, mobile, no external requests or JS errors.')
        finally:
            app.shutdown();app.server_close();thread.join()


if __name__=='__main__':run()
