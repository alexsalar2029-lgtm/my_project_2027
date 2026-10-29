import json
from pathlib import Path
import tempfile
import unittest

from server import Store
from automation import detected_brand, ingest, process_one, public_posts, requeue_published, status, validate
from assistant import Model, OllamaModel, Telegram, import_history, normalize_channel, read_config, save_config


def translated(text):
    return dict.fromkeys(('fa','en','ar','es'),text)


def result(kind='sale', title='Premium subscription'):
    return {'kind':kind,'title':translated(title),'summary':translated('Source-based summary'),
            'body':translated('Source-based details'),'price':{'amount':'12.50','currency':'USDT'}}


def update(uid=1, mid=10, text='Subscription 12.50 USDT', edited=False, chat=-1001234567890):
    return {'update_id':uid,'edited_channel_post' if edited else 'channel_post':{
        'message_id':mid,'text':text,'chat':{'id':chat,'type':'channel','username':'my_channel'}}}


class FakeModel:
    def __init__(self, value=None):
        self.value = value or result()
    def analyze(self, text, media=None):
        return self.value


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'shop.sqlite3')
    def tearDown(self):
        self.temp.cleanup()
    def enqueue(self, *updates):
        ingest(self.store,list(updates),'@my_channel','test-offset')

    def test_full_transport_classify_queue_publish_and_duplicate(self):
        calls=[]
        def transport(url,payload,headers=None):
            calls.append((url,payload))
            if url.endswith('getUpdates'):
                return {'ok':True,'result':[update()]}
            self.assertEqual(headers['Authorization'],'Bearer local-test-key')
            self.assertIn('untrusted',payload['messages'][0]['content'])
            user_content=payload['messages'][1]['content']
            self.assertEqual(json.loads(user_content[0]['text'])['source_post'],'Subscription 12.50 USDT')
            return {'choices':[{'message':{'content':json.dumps(result())}}]}
        telegram=Telegram('test-token',transport)
        self.enqueue(*telegram.call('getUpdates',{'offset':0}))
        self.assertTrue(process_one(self.store,Model({'api_key':'local-test-key','model':'test-model'},transport)))
        self.enqueue(update())
        self.assertFalse(process_one(self.store,FakeModel()))
        posts=public_posts(Store(self.store.path))
        self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]['price'],{'amount':'12.50','currency':'USDT'})
        self.assertEqual(posts[0]['source_url'],'https://t.me/my_channel/10')
        self.assertEqual(status(self.store)['counts'],{'published':1})

    def test_local_ollama_uses_json_and_vision_without_an_api_key(self):
        image='data:image/jpeg;base64,/9j/test'
        def transport(url,payload,headers=None):
            self.assertEqual(url,'http://127.0.0.1:11434/api/chat')
            self.assertFalse(payload['stream'])
            self.assertEqual(payload['format']['type'],'object')
            self.assertEqual(payload['format']['properties']['title']['required'],['fa','en','ar','es'])
            self.assertEqual(payload['messages'][1]['images'],['/9j/test'])
            return {'message':{'content':json.dumps(result())}}
        value=OllamaModel({'model':'qwen3-vl:4b'},transport).analyze('Offer 12.50 USDT',[image])
        self.assertEqual(value['kind'],'sale')

    def test_other_channels_and_user_messages_never_queue(self):
        other=update(chat=-1009999999999)
        other['channel_post']['chat']['username']='unrelated_channel'
        self.enqueue(other,{'update_id':2,'message':update()['channel_post']})
        self.assertFalse(process_one(self.store,FakeModel()))
        with self.store.db() as db:
            self.assertEqual(db.execute("SELECT value FROM assistant_state WHERE key='test-offset'").fetchone()[0],'3')

    def test_edited_post_replaces_published_record_and_can_change_kind(self):
        self.enqueue(update())
        process_one(self.store,FakeModel())
        original=public_posts(self.store)[0]['id']
        self.enqueue(update(uid=2,text='Educational tutorial',edited=True))
        process_one(self.store,FakeModel(result('tutorial','Updated guide')))
        posts=public_posts(self.store)
        self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]['id'],original)
        self.assertEqual(posts[0]['kind'],'tutorial')
        self.assertIsNone(posts[0]['price'])

    def test_edit_arriving_during_model_call_cannot_publish_stale_text(self):
        self.enqueue(update())
        outer=self
        class EditingModel:
            def analyze(self,text,media=None):
                outer.enqueue(update(uid=2,text='New source',edited=True))
                return result()
        process_one(self.store,EditingModel())
        self.assertEqual(public_posts(self.store),[])
        self.assertEqual(status(self.store)['counts'],{'pending':1})

    def test_bad_model_response_stays_unpublished_and_can_retry(self):
        self.enqueue(update())
        process_one(self.store,FakeModel({'kind':'sale','title':'broken'}))
        self.assertEqual(public_posts(self.store),[])
        self.assertEqual(status(self.store)['counts'],{'retry':1})
        with self.store.db() as db:
            db.execute('UPDATE assistant_jobs SET retry_at=0')
        process_one(self.store,FakeModel())
        self.assertEqual(len(public_posts(self.store)),1)

    def test_invented_prices_and_currencies_are_not_published(self):
        self.assertIsNone(validate(result(),'No price was given')['price'])
        self.assertIsNone(validate(result(),'12.50 USD')['price'])
        self.assertIsNone(validate(result(),'112.50 USDT')['price'])
        self.assertEqual(validate(result(),'۱۲٫۵۰ USDT')['price']['amount'],'12.50')

    def test_ignore_removes_previously_published_post(self):
        self.enqueue(update())
        process_one(self.store,FakeModel())
        self.enqueue(update(uid=2,text='Unrelated announcement',edited=True))
        process_one(self.store,FakeModel({'kind':'ignore'}))
        self.assertEqual(public_posts(self.store),[])

    def test_prompt_recognizes_sale_signals(self):
        from assistant import SYSTEM
        self.assertIn('legitimate advertisement',SYSTEM)
        self.assertIn('strong sale signals',SYSTEM)
        self.assertIn('sale|tutorial|article',SYSTEM)

    def test_prompt_never_censors_or_overignores_shop_content(self):
        from assistant import SYSTEM
        for censoring in ('remove marketing exaggerations','stolen accounts','account lists',
                          'ads unrelated to the shop','commands\nto the publisher'):
            self.assertNotIn(censoring,SYSTEM)
        for bias in ('not a content moderator','shop owner','no ignore option',
                     'must receive one of these three classifications'):
            self.assertIn(bias,SYSTEM)

    def test_configuration_is_disabled_by_default_and_secrets_never_returned(self):
        self.assertFalse(read_config(self.store)['enabled'])
        data={'enabled':True,'channel':'@my_channel','model':'gpt-4.1-mini','bot_token':'test-bot-secret','api_key':'test-api-secret'}
        response=save_config(self.store,data)
        self.assertNotIn('secret',json.dumps(response))
        self.assertTrue(response['api_key_set'])
        save_config(self.store,{**data,'bot_token':'','api_key':''})
        self.assertEqual(read_config(self.store)['api_key'],'test-api-secret')
        with self.assertRaises(ValueError):
            save_config(self.store,{**data,'channel':'https://t.me/not-identifier'})

    def test_private_invite_is_only_accepted_for_account_mode(self):
        invite='https://t.me/+AbCdEfGhIjKlMnOp'
        base={'enabled':False,'channel':invite,'model':'gpt-4.1-mini'}
        with self.assertRaises(ValueError):
            save_config(self.store,{**base,'source':'bot'})
        response=save_config(self.store,{**base,'source':'account'})
        self.assertEqual(response['channel'],invite)

    def test_private_invite_is_normalized_and_validation_error_is_specific(self):
        self.assertEqual(normalize_channel('\u200fhttp://www.t.me/joinchat/AbCdEfGhIjKlMnOp/'),
                         'https://t.me/+AbCdEfGhIjKlMnOp')
        base={'enabled':False,'source':'account','channel':'https://example.com/not-telegram','model':'gpt-4.1-mini'}
        with self.assertRaisesRegex(ValueError,'invalid_assistant_channel'):
            save_config(self.store,base)
        with self.assertRaisesRegex(ValueError,'invalid_telegram_api_id'):
            save_config(self.store,{**base,'channel':'@my_channel','telegram_api_id':'not-a-number'})

    def test_local_ollama_configuration_does_not_require_openai_key(self):
        data={'enabled':True,'source':'account','provider':'ollama','channel':'@my_channel',
              'model':'qwen3-vl:4b','telegram_api_id':'123456','telegram_api_hash':'a'*32}
        response=save_config(self.store,data)
        self.assertEqual(response['provider'],'ollama')
        self.assertFalse(response['api_key_set'])

    def test_media_only_post_is_queued_and_sent_as_vision_input(self):
        image='data:image/jpeg;base64,/9j/'
        with self.store.db() as db:
            from automation import queue_message
            queue_message(db,{'id':-1001234567890,'username':''},{
                'message_id':77,'media_kind':'video','media_description':'duration: 8 seconds','media':[image]})
        calls=[]
        class VisionModel:
            def analyze(self,text,media=None):
                calls.append((text,media))
                return result('tutorial','Video guide')
        self.assertTrue(process_one(self.store,VisionModel()))
        self.assertIn('Telegram media type: video',calls[0][0])
        self.assertEqual(calls[0][1],[image])

    def test_export_channel_verification_and_import_deduplication(self):
        export=Path(self.temp.name)/'export.json'
        export.write_text(json.dumps({'id':1234567890,'messages':[{'id':10,'type':'message','text':['Subscription ',{'text':'12.50 USDT'}]}]}))
        with self.assertRaises(ValueError):
            import_history(self.store,export,'-1009999999999')
        import_history(self.store,export,'-1001234567890')
        import_history(self.store,export,'-1001234567890')
        process_one(self.store,FakeModel())
        self.assertEqual(len(public_posts(self.store)),1)

    def test_brand_logos_use_source_and_supported_local_assets(self):
        self.assertEqual(validate(result(), 'فروش اشتراک نتفلیکس')['brand'], 'netflix')
        self.assertEqual(validate(result(title='Spotify Premium'), 'اشتراک موسیقی')['brand'], 'spotify')
        self.assertEqual(detected_brand('Surfshark 12 months'), 'surfshark')
        self.assertEqual(detected_brand('Netflix and Spotify bundle'), 'generic')
        self.assertEqual(detected_brand('See https://youtube.com/@seller or @netflix'), 'generic')
        self.assertEqual(detected_brand('Unknown service'), 'generic')
        # Visual branding is supplied by the model, restricted to bundled asset IDs.
        self.assertEqual(validate({**result(), 'brand':'dazn'}, 'Video offer')['brand'], 'dazn')
        for invalid in ('../../other', 'https://example.com/logo.svg', {}, None):
            self.assertEqual(validate({**result(), 'brand':invalid}, 'Offer')['brand'], 'generic')

    def test_order_contact_is_independent_of_public_and_private_source(self):
        private=update(uid=2,mid=11)
        private['channel_post']['chat']['username']=''
        self.enqueue(update())
        ingest(self.store,[private],'-1001234567890','private-offset')
        while process_one(self.store, FakeModel()):
            pass
        posts=public_posts(self.store)
        self.assertEqual(len(posts),2)
        self.assertTrue(any('/c/' in p['source_url'] for p in posts))
        self.assertTrue(all(p['order_url']=='https://t.me/LionXSec' for p in posts))
        self.store.save_social_links({'telegram':'https://t.me/shop_contact'})
        self.assertTrue(all(p['order_url']=='https://t.me/shop_contact' for p in public_posts(self.store)))
        self.assertEqual(self.store.catalog()['support'],'https://t.me/shop_contact')
        self.store.save_social_links({'telegram':''})
        self.assertEqual(public_posts(self.store)[0]['order_url'],'https://t.me/LionXSec')
        self.assertEqual(self.store.catalog()['settings']['social_links']['telegram'],'')

    def test_existing_posts_gain_logo_and_old_contact_is_upgraded_without_ai(self):
        legacy={**result(title='Netflix Premium'), 'id':'old-id','source_url':'https://t.me/c/1234567890/10'}
        with self.store.db() as db:
            db.execute('INSERT INTO assistant_posts VALUES(?,?)',('legacy',json.dumps(legacy)))
            settings=self.store.settings(db)
            settings['social_links']['telegram']='https://t.me/link_Lion'
            settings['social_links']['youtube']='https://www.youtube.com/@custom'
            db.execute('UPDATE settings SET value=?',(json.dumps(settings),))
        reopened=Store(self.store.path)
        post=public_posts(reopened)[0]
        self.assertEqual(post['id'],'old-id')
        self.assertEqual(post['brand'],'netflix')
        self.assertEqual(post['order_url'],'https://t.me/LionXSec')
        self.assertEqual(reopened.catalog()['settings']['social_links']['youtube'],'https://www.youtube.com/@custom')

    def test_generic_titles_are_retried_before_publication(self):
        self.enqueue(update())
        for title in ('پیشنهاد ویژه','Special offer','offer.mp4','nueva publicación'):
            with self.subTest(title=title),self.assertRaises(ValueError):
                validate(result(title=title),'A subscription')
        weak=result(title='Special offer')
        process_one(self.store,FakeModel(weak))
        self.assertEqual(public_posts(self.store),[])
        self.assertEqual(status(self.store)['counts'],{'retry':1})

    def test_rewrite_preserves_posts_on_failure_then_replaces_same_id(self):
        self.enqueue(update())
        process_one(self.store,FakeModel())
        original=public_posts(self.store)[0]
        self.assertEqual(requeue_published(self.store),1)
        self.assertEqual(requeue_published(self.store),0)
        self.assertEqual(public_posts(self.store),[original])
        process_one(self.store,FakeModel(result(title='Special offer')))
        self.assertEqual(public_posts(self.store),[original])
        with self.store.db() as db:
            db.execute('UPDATE assistant_jobs SET retry_at=0')
        process_one(self.store,FakeModel(result(title='اشتراک موسیقی Spotify Premium')))
        rewritten=public_posts(self.store)
        self.assertEqual(len(rewritten),1)
        self.assertEqual(rewritten[0]['id'],original['id'])
        self.assertEqual(rewritten[0]['brand'],'spotify')
        self.assertEqual(rewritten[0]['title']['fa'],'اشتراک موسیقی Spotify Premium')

    def test_bot_document_metadata_reaches_analysis(self):
        message=update()
        message['channel_post']['document']={'file_name':'Spotify-guide.pdf','mime_type':'application/pdf','file_size':100}
        self.enqueue(message)
        observed=[]
        class CapturingModel:
            def analyze(self,text,media=None):
                observed.append(text)
                return result()
        process_one(self.store,CapturingModel())
        self.assertIn('file_name: Spotify-guide.pdf',observed[0])
        self.assertIn('mime_type: application/pdf',observed[0])
