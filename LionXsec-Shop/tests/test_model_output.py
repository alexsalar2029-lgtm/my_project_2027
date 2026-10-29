import json
from pathlib import Path
import tempfile
import unittest

from assistant import Model, OllamaModel, RemoteError
from automation import ingest, process_one, public_posts, requeue_failed, status, validate
from model_output import ModelOutputError, parse_output
from server import Store


def post():
    translated=lambda text:dict.fromkeys(('fa','en','ar','es'),text)
    return {'kind':'sale','brand':'spotify','title':translated('Spotify Premium'),
            'summary':translated('One-month subscription'),
            'body':translated('One-month subscription with manual delivery.'),'price':None}


class OutputTests(unittest.TestCase):
    def test_fenced_json_and_bom_are_accepted_without_interpreting_prose(self):
        for raw in (json.dumps(post()), '\ufeff'+json.dumps(post()),
                    '```json\n'+json.dumps(post())+'\n```'):
            self.assertEqual(parse_output(raw),post())
        for raw in ('prefix '+json.dumps(post()), json.dumps([post()]), '{"title":', ''):
            with self.subTest(raw=raw),self.assertRaises(ModelOutputError):
                parse_output(raw)

    def test_reported_truncation_never_publishes_even_parseable_json(self):
        with self.assertRaisesRegex(ModelOutputError,'model_output_truncated'):
            parse_output(json.dumps(post()),truncated=True)

    def test_harmless_formatting_and_extra_languages_are_normalized(self):
        value=post()
        value['title']['fa']='  Spotify\nPremium  '
        value['title']['de']='Spotify Premium'
        clean=validate(value,'Spotify Premium')
        self.assertEqual(clean['title']['fa'],'Spotify Premium')
        self.assertEqual(set(clean['title']),{'fa','en','ar','es'})

    def test_short_source_may_have_overlapping_descriptions(self):
        value=post()
        value['body']=dict(value['summary'])
        self.assertEqual(validate(value,'One-month Spotify subscription')['body'],value['summary'])

    def test_missing_empty_wrong_type_and_long_translations_have_precise_codes(self):
        for change,expected in ((None,'missing'),('', 'empty'),(10,'not_text'),('a'*181,'too_long')):
            value=post()
            if change is None:del value['title']['fa']
            else:value['title']['fa']=change
            with self.subTest(change=change),self.assertRaisesRegex(ModelOutputError,'model_title_fa_'+expected):
                validate(value,'Spotify Premium')


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'shop.sqlite3')
        ingest(self.store,[{'update_id':1,'channel_post':{'message_id':26,
            'chat':{'id':-1001234567890,'type':'channel','username':'sales_channel'},
            'text':'Spotify Premium 1 month'}}],'@sales_channel','test-offset')

    def tearDown(self):
        self.temp.cleanup()

    def test_ollama_repairs_missing_language_with_original_evidence_once(self):
        calls=[]
        def transport(url,payload,headers=None):
            calls.append(payload)
            value=post()
            if len(calls)==1:del value['summary']['es']
            return {'message':{'content':json.dumps(value)},'done':True,'done_reason':'stop'}
        model=OllamaModel({'model':'qwen3-vl:4b'},transport)
        process_one(self.store,model)
        self.assertEqual(len(calls),2)
        self.assertEqual(calls[0]['messages'][1],calls[1]['messages'][1])
        self.assertIn('summary.es',calls[1]['messages'][-1]['content'])
        self.assertEqual(status(self.store)['counts'],{'published':1})
        self.assertEqual(len(public_posts(self.store)),1)
        self.assertFalse(process_one(self.store,model))

    def test_ollama_truncation_requests_compact_replacement(self):
        calls=[]
        def transport(url,payload,headers=None):
            calls.append(payload)
            return {'message':{'content':json.dumps(post())},'done':True,
                    'done_reason':'length' if len(calls)==1 else 'stop'}
        process_one(self.store,OllamaModel({'model':'qwen3-vl:4b'},transport))
        self.assertEqual(len(calls),2)
        self.assertIn('ran out of output space',calls[1]['messages'][-1]['content'])
        self.assertEqual(status(self.store)['counts'],{'published':1})

    def test_failed_repair_is_bounded_and_preserves_published_post(self):
        class GoodModel:
            def analyze(self,text,media=None):return post()
        process_one(self.store,GoodModel())
        original=public_posts(self.store)
        with self.store.db() as db:
            db.execute("UPDATE assistant_jobs SET status='pending'")
        calls=[]
        def transport(url,payload,headers=None):
            calls.append(payload)
            return {'message':{'content':'PRIVATE_PROVIDER_TEXT not JSON'}}
        process_one(self.store,OllamaModel({'model':'qwen3-vl:4b'},transport))
        self.assertEqual(len(calls),2)
        self.assertEqual(public_posts(self.store),original)
        state=status(self.store)
        self.assertEqual(state['counts'],{'retry':1})
        self.assertEqual(state['recent'][0]['error'],'model_json_invalid')
        self.assertEqual(state['recent'][0]['attempts'],1)
        self.assertNotIn('PRIVATE_PROVIDER_TEXT',json.dumps(state))
        self.assertNotIn('PRIVATE_PROVIDER_TEXT',json.dumps(calls))

    def test_network_failure_does_not_trigger_immediate_corrective_call(self):
        calls=[]
        def transport(*args,**kwargs):
            calls.append(1)
            raise RemoteError('connection_failed')
        process_one(self.store,OllamaModel({'model':'qwen3-vl:4b'},transport))
        self.assertEqual(calls,[1])
        self.assertEqual(status(self.store)['recent'][0]['error'],'connection_failed')

    def test_openai_uses_the_same_bounded_repair_path(self):
        calls=[]
        def transport(url,payload,headers=None):
            calls.append(payload)
            return {'choices':[{'message':{'content':'not JSON' if len(calls)==1 else json.dumps(post())},
                                'finish_reason':'stop'}]}
        process_one(self.store,Model({'model':'gpt-4.1-mini','api_key':'local-test'},transport))
        self.assertEqual(len(calls),2)
        self.assertEqual(status(self.store)['counts'],{'published':1})

    def test_retry_reset_only_changes_failed_jobs_and_is_repeatable(self):
        with self.store.db() as db:
            db.execute("UPDATE assistant_jobs SET status='retry',attempts=3,retry_at=9999999999,error='model_response_invalid'")
        self.assertEqual(requeue_failed(self.store),1)
        self.assertEqual(requeue_failed(self.store),0)
        state=status(self.store)
        self.assertEqual(state['counts'],{'pending':1})
        self.assertEqual(state['recent'][0]['attempts'],0)
        self.assertEqual(state['recent'][0]['retry_at'],0)
        self.assertEqual(state['recent'][0]['error'],'')
        class GoodModel:
            def analyze(self,text,media=None):return post()
        process_one(self.store,GoodModel())
        self.assertEqual(requeue_failed(self.store),0)
        self.assertEqual(len(public_posts(self.store)),1)
