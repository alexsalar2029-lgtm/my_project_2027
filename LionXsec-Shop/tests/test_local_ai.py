import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
import zipfile

from assistant import (LlamaCppModel, LOCAL_MODEL, Runner, check_llamacpp, configured_model,
                       config_path, read_config, save_config)
from automation import ingest, process_one, public_posts, status
from local_ai import (ASSETS, BUILD, MODEL_ALIAS, extract_runtime, install_runtime,
                      select_local_model, server_command, test_image, test_model)
from model_output import ModelOutputError
from server import Store
from service_transport import RemoteError, http_json, llamacpp_json


def post():
    return {'kind':'sale', 'brand':'spotify',
            'title':dict.fromkeys(('fa','en','ar','es'), 'Spotify Premium'),
            'summary':{'fa':'اشتراک یک ماهه', 'en':'One-month subscription',
                       'ar':'اشتراك لمدة شهر', 'es':'Suscripción de un mes'},
            'body':{'fa':'تحویل دستی', 'en':'Manual delivery', 'ar':'تسليم يدوي', 'es':'Entrega manual'},
            'price':{'amount':'12.50', 'currency':'USDT'}}


def completion(value, finish='stop'):
    return {'choices':[{'message':{'content':json.dumps(value, ensure_ascii=False)}, 'finish_reason':finish}]}


CONFIG = {'provider':'llamacpp', 'model':LOCAL_MODEL}


def ready(path, payload=None):
    return {'/health':{'status':'ok'}, '/v1/models':{'data':[{'id':LOCAL_MODEL}]},
            '/props':{'modalities':{'vision':True}, 'model_path':'PRIVATE/path'}}[path]


class ModelTests(unittest.TestCase):
    def test_real_payload_uses_images_schema_and_no_online_credentials(self):
        transport = Mock(return_value=completion(post()))
        config = {**CONFIG, 'api_key':'SECRET'}
        model = configured_model(config)
        self.assertIsInstance(model, LlamaCppModel)
        value = LlamaCppModel(config, transport).analyze('Spotify 12.50 USDT', [test_image()])
        self.assertEqual(value, post())
        path, payload = transport.call_args.args
        self.assertEqual(path, '/v1/chat/completions')
        self.assertNotIn('SECRET', json.dumps(payload))
        self.assertFalse(payload['stream'])
        self.assertEqual(payload['response_format']['schema']['properties']['title']['required'], ['fa','en','ar','es'])
        self.assertIn('UNTRUSTED SOURCE DATA:', payload['messages'][0]['content'][0]['text'])
        self.assertEqual(payload['messages'][0]['content'][1]['image_url']['url'], test_image())

    def test_truncated_and_empty_results_cannot_publish(self):
        for value, code in [(completion(post(), 'length'), 'model_output_truncated'),
                            ({'choices':[]}, 'model_output_empty'),
                            ({'choices':[{'message':{}}]}, 'model_output_empty')]:
            with self.subTest(code=code), self.assertRaisesRegex(ModelOutputError, code):
                LlamaCppModel(CONFIG, Mock(return_value=value)).analyze('test')

    def test_repair_preserves_original_evidence_and_gemma_single_turn(self):
        transport = Mock(return_value=completion(post()))
        LlamaCppModel(CONFIG, transport).repair('Original source', [test_image()], ModelOutputError('model_summary_es_missing'))
        messages = transport.call_args.args[1]['messages']
        self.assertEqual(len(messages), 1)
        self.assertIn('summary.es', messages[0]['content'][0]['text'])
        self.assertIn('Original source', messages[0]['content'][0]['text'])
        self.assertEqual(messages[0]['content'][1]['image_url']['url'], test_image())

    def test_readiness_requires_matching_model_and_vision_without_exposing_paths(self):
        transport = Mock(side_effect=ready)
        report = check_llamacpp(CONFIG, transport)
        self.assertTrue(report['ok'])
        self.assertNotIn('PRIVATE', json.dumps(report))
        transport.assert_any_call('/props')
        for replacement, code in [({'data':[]}, 'llamacpp_model_mismatch'),
                                   ({'broken':True}, 'llamacpp_service_response_invalid')]:
            def changed(path):
                return replacement if path == '/v1/models' else ready(path)
            self.assertEqual(check_llamacpp(CONFIG, changed)['code'], code)
        def no_vision(path):
            return {'modalities':{'vision':False}} if path == '/props' else ready(path)
        self.assertEqual(check_llamacpp(CONFIG, no_vision)['code'], 'llamacpp_vision_unavailable')

    def test_unselected_loading_or_broken_service_does_not_claim_ready(self):
        probe = Mock()
        self.assertFalse(check_llamacpp({'provider':'openai'}, probe)['ok'])
        probe.assert_not_called()
        self.assertEqual(check_llamacpp(CONFIG, Mock(return_value={'status':'loading'}))['code'], 'llamacpp_loading')
        self.assertEqual(check_llamacpp(CONFIG, Mock(side_effect=RemoteError('llamacpp_connection_refused')))['code'],
                         'llamacpp_connection_refused')

    def test_real_diagnostic_requires_both_vision_and_four_language_generation(self):
        def transport(path, payload=None):
            if payload is None:
                return ready(path)
            return completion({'color':'blue'} if payload['max_tokens'] == 48 else post())
        progress = Mock()
        report = test_model(transport, progress)
        self.assertTrue(report['ok'])
        self.assertEqual(report['code'], 'llamacpp_test_passed')
        self.assertEqual(progress.call_count, 2)
        self.assertIn('seconds', report)

    def test_color_failure_stops_before_copy_test(self):
        calls = []
        def transport(path, payload=None):
            if payload is None:
                return ready(path)
            calls.append(payload)
            return completion({'color':'red'})
        report = test_model(transport, Mock())
        self.assertFalse(report['ok'])
        self.assertEqual(report['code'], 'llamacpp_vision_test_failed')
        self.assertEqual(len(calls), 1)

    def test_valid_json_alone_does_not_pass_the_copy_test(self):
        invalid = post()
        invalid['summary']['fa'] = 'English in the Persian field'
        def transport(path, payload=None):
            if payload is None:
                return ready(path)
            return completion({'color':'blue'} if payload['max_tokens'] == 48 else invalid)
        report = test_model(transport, Mock())
        self.assertFalse(report['ok'])
        self.assertEqual(report['code'], 'llamacpp_copy_test_failed')


class MigrationAndQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'shop.sqlite3')

    def tearDown(self):
        self.temp.cleanup()

    def queue(self, number=1):
        ingest(self.store, [{'update_id':number, 'channel_post':{'message_id':number,
            'chat':{'id':-1001234567890, 'type':'channel', 'username':'my_channel'},
            'text':'Spotify Premium 12.50 USDT'}}], '@my_channel', 'test')

    def test_fresh_config_is_local_but_existing_providers_are_preserved_until_setup(self):
        self.assertEqual(read_config(self.store)['provider'], 'llamacpp')
        self.assertFalse(read_config(self.store)['enabled'])
        config_path(self.store).write_text(json.dumps({'enabled':False, 'model':'legacy-cloud'}))
        self.assertEqual(read_config(self.store)['provider'], 'openai')
        self.assertEqual(read_config(self.store)['model'], 'legacy-cloud')

    def test_setup_preserves_secrets_session_and_queue_but_pauses_publishing(self):
        previous = {'enabled':True, 'source':'account', 'provider':'ollama', 'model':'qwen3-vl:4b',
                    'channel':'@my_channel', 'telegram_api_id':'1234', 'telegram_api_hash':'a'*32,
                    'api_key':'PRIVATE-key'}
        save_config(self.store, previous)
        session = self.root / 'telegram.session'
        session.write_bytes(b'private-session-fixture')
        self.queue(1)
        process_one(self.store, Mock(analyze=Mock(return_value=post())))
        self.queue(2)
        original = public_posts(self.store)
        before = status(self.store)
        select_local_model(self.root)
        current = read_config(self.store)
        self.assertEqual(current['provider'], 'llamacpp')
        self.assertEqual(current['model'], MODEL_ALIAS)
        self.assertFalse(current['enabled'])
        for key in ('telegram_api_id','telegram_api_hash','api_key','source','channel'):
            self.assertEqual(current[key], previous[key])
        self.assertEqual(public_posts(self.store), original)
        self.assertEqual(status(self.store), before)
        self.assertEqual(session.read_bytes(), b'private-session-fixture')
        self.assertNotIn('PRIVATE', json.dumps(read_config(self.store, public=True)))

    def test_local_config_enables_without_an_api_key(self):
        response = save_config(self.store, {**CONFIG, 'enabled':True, 'source':'account',
            'channel':'@my_channel', 'telegram_api_id':'1234', 'telegram_api_hash':'a'*32})
        self.assertTrue(response['enabled'])
        self.assertFalse(response['api_key_set'])

    def test_missing_vision_pauses_queue_without_spending_attempts_then_recovers(self):
        config = {**CONFIG, 'enabled':True, 'source':'account', 'channel':'@my_channel',
                  'telegram_api_id':'1234', 'telegram_api_hash':'a'*32}
        save_config(self.store, config)
        self.queue(1)
        self.queue(2)
        runner = Runner(self.store)
        model = Mock(analyze=Mock(return_value=post()))
        with patch('assistant.check_llamacpp', return_value={'ok':False,'code':'llamacpp_vision_unavailable'}), \
                patch('assistant.configured_model', return_value=model):
            with self.assertRaisesRegex(RemoteError, 'llamacpp_vision_unavailable'):
                runner.process_queue(read_config(self.store))
        model.analyze.assert_not_called()
        self.assertEqual(status(self.store)['counts'], {'pending':2})
        self.assertTrue(all(row['attempts'] == 0 for row in status(self.store)['recent']))
        with patch('assistant.check_llamacpp', return_value={'ok':True}), \
                patch('assistant.configured_model', return_value=model):
            runner.process_queue(read_config(self.store))
        self.assertEqual(status(self.store)['counts'], {'published':2})


class InstallerTests(unittest.TestCase):
    def test_setup_verifies_then_extracts_official_layout_and_is_repeatable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / '.local-ai'
            cache.mkdir()
            archive = cache / ASSETS['vulkan'][0]
            with zipfile.ZipFile(archive, 'w') as output:
                for name in ('llama-server.exe','llama.dll','ggml-base.dll'):
                    output.writestr(name, 'fixture')
            checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
            with patch.dict(ASSETS, {'vulkan':(archive.name,checksum)}), \
                    patch('local_ai.platform.system', return_value='Windows'), \
                    patch('local_ai.platform.machine', return_value='AMD64'), \
                    patch('local_ai.urlopen') as network:
                runtime = install_runtime(root)
                self.assertEqual(install_runtime(root), runtime)
                self.assertTrue((runtime / 'llama-server.exe').is_file())
                network.assert_not_called()

    def test_corrupt_download_never_installs_or_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch('local_ai.platform.system', return_value='Windows'), \
                    patch('local_ai.platform.machine', return_value='AMD64'), \
                    patch('local_ai.urlopen', return_value=io.BytesIO(b'not the pinned runtime')), \
                    patch('local_ai.extract_runtime') as extract:
                with self.assertRaisesRegex(ValueError, 'download_checksum_mismatch'):
                    install_runtime(root)
                extract.assert_not_called()
            self.assertFalse((root / '.local-ai' / (BUILD + '-vulkan')).exists())
            self.assertEqual(list((root / '.local-ai').iterdir()), [])

    def test_archive_traversal_and_incomplete_layout_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('../escape', 'dir/file', 'C:\\escape', 'only.txt'):
                archive = root / 'test.zip'
                with zipfile.ZipFile(archive, 'w') as output:
                    output.writestr(name, 'bad')
                with self.subTest(name=name), self.assertRaises(ValueError):
                    extract_runtime(archive, root / 'target')
            self.assertFalse((root / 'target').exists())

    def test_start_modes_use_same_vision_model_and_private_listener(self):
        for backend in ('cpu', 'vulkan'):
            command = server_command(Path('C:/Users/Computer 123/Shop'), backend, offline=True)
            self.assertIn('Computer 123', command[0])
            self.assertIn('--offline', command)
            self.assertEqual(command[command.index('--host') + 1], '127.0.0.1')
            self.assertEqual(command[command.index('--parallel') + 1], '1')
            self.assertEqual(command[command.index('--cors-origins') + 1], 'localhost')
            self.assertEqual(command[command.index('--alias') + 1], MODEL_ALIAS)
            self.assertIn('gemma-3-4b', command[command.index('--hf-repo') + 1])
            self.assertNotIn('--no-mmproj', command)
            if backend == 'cpu':
                self.assertEqual(command[command.index('--device') + 1], 'none')
                self.assertIn('--no-mmproj-offload', command)


class TransportTests(unittest.TestCase):
    def test_local_origin_cannot_be_changed_by_payload_path_or_redirect(self):
        for url in ('https://remote.invalid/api', 'http://127.0.0.1:11434/api/chat',
                    'http://user@127.0.0.1:8081/v1/chat/completions'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'invalid_llamacpp_address'):
                http_json(url, {}, local='llamacpp')

    def test_model_server_errors_are_safe_and_distinguish_loading_memory_and_context(self):
        for message, status_code, code, pause in [
            ('Loading model PRIVATE', 503, 'llamacpp_loading', True),
            ('failed to allocate PRIVATE', 500, 'llamacpp_out_of_memory', True),
            ('request exceeds the available context PRIVATE', 400, 'llamacpp_context_exceeded', False),
            ('PRIVATE request error', 400, 'llamacpp_http_400', False),
        ]:
            error = HTTPError('http://127.0.0.1:8081', status_code, 'PRIVATE', {},
                              io.BytesIO(json.dumps({'error':{'message':message}}).encode()))
            opener = Mock()
            opener.open.side_effect = error
            with self.subTest(code=code), patch('service_transport.build_opener', return_value=opener):
                with self.assertRaises(RemoteError) as caught:
                    llamacpp_json('/v1/chat/completions', {})
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.pause_queue, pause)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_real_http_pipeline_bypasses_proxy_and_never_follows_redirects(self):
        received = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/must-not-follow')
                    self.end_headers()
                    return
                self.respond(ready(self.path))
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                received.append(body)
                self.respond(completion({'color':'blue'} if body['max_tokens'] == 48 else post()))
            def respond(self, value):
                body = json.dumps(value).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
        app = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            with patch('service_transport.LLAMACPP_ORIGIN', 'http://127.0.0.1:' + str(app.server_port)), \
                    patch.dict(os.environ, {'http_proxy':'http://127.0.0.1:1',
                                            'HTTP_PROXY':'http://127.0.0.1:1', 'NO_PROXY':'','no_proxy':''}):
                self.assertTrue(test_model(progress=Mock())['ok'])
                self.assertEqual(len(received), 2)
                with self.assertRaisesRegex(RemoteError, 'llamacpp_http_302'):
                    llamacpp_json('/redirect')
        finally:
            app.shutdown()
            app.server_close()
            thread.join()
