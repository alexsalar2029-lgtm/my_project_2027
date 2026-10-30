import io
import json
import os
import socket
import ssl
from http.client import RemoteDisconnected, IncompleteRead
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from assistant import Runner, check_ollama, save_config
from automation import ingest, process_one, public_posts, status
from server import Store
from service_transport import RemoteError, http_json, ollama_json


class TransportTests(unittest.TestCase):
    def test_connection_failures_are_distinct_and_do_not_leak_exception_text(self):
        for error, code in (
            (URLError(ConnectionRefusedError(111, 'PRIVATE detail')), 'connection_refused'),
            (TimeoutError('PRIVATE detail'), 'connection_timeout'),
            (URLError(TimeoutError('PRIVATE detail')), 'connection_timeout'),
            (URLError(socket.gaierror(-2, 'PRIVATE detail')), 'dns_failed'),
            (URLError(ssl.SSLError('PRIVATE detail')), 'tls_failed'),
            (ConnectionResetError('PRIVATE detail'), 'connection_closed'),
            (RemoteDisconnected('PRIVATE detail'), 'connection_closed'),
            (IncompleteRead(b'PRIVATE partial response'), 'connection_closed'),
            (URLError('PRIVATE unknown error'), 'connection_failed'),
        ):
            with self.subTest(code=code), patch('service_transport.urlopen', side_effect=error):
                with self.assertRaises(RemoteError) as caught:
                    http_json('https://service.invalid/token/PRIVATE', {})
                self.assertEqual(caught.exception.code, code)
                self.assertTrue(caught.exception.pause_queue)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_windows_socket_numbers_are_supported(self):
        for number, code in ((10061, 'connection_refused'), (10060, 'connection_timeout'),
                             (10054, 'connection_closed')):
            error = OSError('PRIVATE Windows error')
            error.winerror = number
            with self.subTest(number=number), patch('service_transport.urlopen', side_effect=URLError(error)):
                with self.assertRaises(RemoteError) as caught:
                    http_json('https://service.invalid', {})
                self.assertEqual(caught.exception.code, code)

    def test_unreadable_service_json_is_not_a_connection_error(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        for raw in (b'<html>PRIVATE</html>', b'\xff\xfeinvalid'):
            response.read.return_value = raw
            with self.subTest(raw=raw), patch('service_transport.urlopen', return_value=response):
                with self.assertRaisesRegex(RemoteError, '^service_response_invalid$'):
                    http_json('https://service.invalid', {})

    def test_local_errors_have_provider_and_memory_specific_codes(self):
        for http_status, message, code in (
            (500, 'model requires more system memory (PRIVATE)', 'ollama_out_of_memory'),
            (500, 'CUDA error: out of memory PRIVATE', 'ollama_out_of_memory'),
            (500, 'llama runner process has terminated PRIVATE', 'ollama_runner_stopped'),
            (404, 'model PRIVATE not found', 'ollama_model_missing'),
            (500, 'PRIVATE unrecognized error', 'ollama_http_500'),
            (400, 'PRIVATE bad request', 'ollama_http_400'),
        ):
            error = HTTPError('http://127.0.0.1:11434/api/chat', http_status, 'PRIVATE',
                              {'Retry-After':'120'}, io.BytesIO(json.dumps({'error':message}).encode()))
            opener = Mock()
            opener.open.side_effect = error
            with self.subTest(code=code), patch('service_transport.build_opener', return_value=opener):
                with self.assertRaises(RemoteError) as caught:
                    ollama_json('/api/chat', {})
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(caught.exception.pause_queue, http_status != 400)
                self.assertEqual(caught.exception.retry, 120)
                self.assertNotIn('PRIVATE', str(caught.exception))

    def test_local_connection_error_keeps_provider_prefix(self):
        opener = Mock()
        opener.open.side_effect = URLError(ConnectionRefusedError())
        with patch('service_transport.build_opener', return_value=opener):
            with self.assertRaisesRegex(RemoteError, '^ollama_connection_refused$'):
                ollama_json('/api/tags')

    def test_local_transport_refuses_non_loopback_destinations(self):
        with self.assertRaisesRegex(ValueError, 'invalid_ollama_address'):
            http_json('https://remote.invalid/api/chat', {}, local=True)


class DiagnosticsTests(unittest.TestCase):
    def test_installed_but_unloaded_model_is_available_without_running_it(self):
        transport = Mock(return_value={'models':[{'name':'qwen3-vl:4b'}]})
        report = check_ollama({'provider':'ollama', 'model':'qwen3-vl:4b'}, transport)
        self.assertTrue(report['ok'])
        self.assertEqual(report['code'], 'ollama_ready')
        transport.assert_called_once_with('/api/tags')

    def test_missing_model_and_service_failure_are_distinct(self):
        config = {'provider':'ollama', 'model':'qwen3-vl:4b'}
        missing = check_ollama(config, Mock(return_value={'models':[{'name':'qwen3-vl:2b'}]}))
        self.assertEqual(missing['code'], 'ollama_model_missing')
        refused = check_ollama(config, Mock(side_effect=RemoteError('ollama_connection_refused')))
        self.assertEqual(refused['code'], 'ollama_connection_refused')
        malformed = check_ollama(config, Mock(return_value={'PRIVATE':'not a model list'}))
        self.assertEqual(malformed['code'], 'ollama_service_response_invalid')
        self.assertNotIn('PRIVATE', json.dumps(malformed))

    def test_latest_alias_and_other_provider(self):
        report = check_ollama({'provider':'ollama', 'model':'local-model'},
                              Mock(return_value={'models':[{'name':'local-model:latest'}]}))
        self.assertTrue(report['ok'])
        transport = Mock()
        report = check_ollama({'provider':'openai', 'model':'cloud-model'}, transport)
        self.assertEqual(report['code'], 'ollama_not_selected')
        transport.assert_not_called()


class LocalHTTPTests(unittest.TestCase):
    def test_loopback_bypasses_system_proxy_and_never_follows_redirects(self):
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                calls.append(self.path)
                if self.path == '/redirect':
                    self.send_response(302)
                    self.send_header('Location', '/must-not-follow')
                    self.end_headers()
                else:
                    data = json.dumps({'models':[{'name':'qwen3-vl:4b'}]}).encode()
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Length', str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
        app = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        origin = 'http://127.0.0.1:' + str(app.server_port)
        try:
            with patch('service_transport.OLLAMA_ORIGIN', origin), patch.dict(os.environ, {
                    'http_proxy':'http://127.0.0.1:1', 'HTTP_PROXY':'http://127.0.0.1:1',
                    'no_proxy':'', 'NO_PROXY':''}):
                self.assertTrue(check_ollama({'provider':'ollama', 'model':'qwen3-vl:4b'})['ok'])
                with self.assertRaisesRegex(RemoteError, '^ollama_http_302$'):
                    ollama_json('/redirect')
            self.assertEqual(calls, ['/api/tags', '/redirect'])
        finally:
            app.shutdown()
            app.server_close()
            thread.join()


def generated_post():
    localized = lambda text: dict.fromkeys(('fa', 'en', 'ar', 'es'), text)
    return {'kind':'sale', 'title':localized('Spotify Premium'),
            'summary':localized('One-month subscription'),
            'body':localized('One-month subscription'), 'price':None}


class QueueAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'shop.sqlite3')
        save_config(self.store, {'enabled':True, 'source':'account', 'provider':'ollama',
            'channel':'@my_channel', 'model':'qwen3-vl:4b', 'telegram_api_id':'12345',
            'telegram_api_hash':'a'*32})
        for index in range(1, 4):
            ingest(self.store, [{'update_id':index, 'channel_post':{'message_id':index,
                'chat':{'id':-1001234567890, 'type':'channel', 'username':'my_channel'},
                'text':'Spotify Premium 1 month'}}], '@my_channel', 'test')

    def tearDown(self):
        self.temp.cleanup()

    def run_once(self, health, model):
        runner = Runner(self.store)
        # End the synchronous runner at its first scheduled wait; no sleeping in tests.
        def stop_at_wait(delay):
            runner.stop.set()
            return True
        with patch('assistant.check_ollama', return_value=health) as probe, \
             patch('assistant.configured_model', return_value=model), \
             patch.object(runner.stop, 'wait', side_effect=stop_at_wait) as wait:
            runner.run()
        with self.store.db() as db:
            runtime = json.loads(db.execute("SELECT value FROM assistant_state WHERE key='runtime'").fetchone()[0])
        return runtime, probe, wait

    def test_unavailable_service_does_not_consume_any_post_attempts(self):
        model = Mock()
        state, probe, wait = self.run_once({'ok':False, 'code':'ollama_connection_refused'}, model)
        model.analyze.assert_not_called()
        self.assertEqual(probe.call_count, 1)
        self.assertEqual(status(self.store)['counts'], {'pending':3})
        self.assertTrue(all(row['attempts'] == 0 for row in status(self.store)['recent']))
        self.assertEqual(state['state'], 'waiting_service')
        self.assertEqual(state['code'], 'ollama_connection_refused')
        wait.assert_called_once_with(60)

    def test_connection_lost_mid_job_pauses_before_touching_remaining_posts(self):
        model = Mock()
        model.analyze.side_effect = RemoteError('ollama_connection_closed', 60, pause_queue=True)
        state, probe, wait = self.run_once({'ok':True}, model)
        model.analyze.assert_called_once()
        self.assertEqual(status(self.store)['counts'], {'pending':2, 'retry':1})
        self.assertEqual(sum(row['attempts'] for row in status(self.store)['recent']), 1)
        self.assertEqual(state['code'], 'ollama_connection_closed')
        self.assertEqual(state['state'], 'waiting_service')
        wait.assert_called_once_with(60)
        # The next service check succeeds; all work resumes without resetting good posts.
        with self.store.db() as db:
            db.execute('UPDATE assistant_jobs SET retry_at=0')
        model.analyze.side_effect = None
        model.analyze.return_value = generated_post()
        state, _, _ = self.run_once({'ok':True}, model)
        self.assertEqual(status(self.store)['counts'], {'published':3})
        self.assertEqual(len(public_posts(self.store)), 3)
        self.assertEqual(state['state'], 'account_mode')

    def test_active_message_is_visible_and_preflight_skips_empty_queue(self):
        def analyze(*args):
            with self.store.db() as db:
                state = json.loads(db.execute("SELECT value FROM assistant_state WHERE key='runtime'").fetchone()[0])
            self.assertEqual(state['state'], 'processing')
            self.assertIn(state['message'], (1, 2, 3))
            return generated_post()
        model = Mock()
        model.analyze.side_effect = analyze
        self.run_once({'ok':True}, model)
        _, probe, _ = self.run_once({'ok':True}, model)
        probe.assert_not_called()
        self.assertEqual(status(self.store)['counts'], {'published':3})

    def test_invalid_post_does_not_pause_the_service_or_other_posts(self):
        model = Mock(spec=['analyze'])
        model.analyze.side_effect = [{'kind':'broken'}, generated_post(), generated_post()]
        state, _, _ = self.run_once({'ok':True}, model)
        self.assertEqual(status(self.store)['counts'], {'published':2, 'retry':1})
        self.assertEqual(state['state'], 'account_mode')

    def test_preflight_does_not_change_existing_published_or_ignored_records(self):
        process_one(self.store, Mock(analyze=Mock(return_value=generated_post())))
        with self.store.db() as db:
            db.execute("UPDATE assistant_jobs SET status='ignored' WHERE key=(SELECT key FROM assistant_jobs WHERE status='pending' LIMIT 1)")
        original = public_posts(self.store)
        self.run_once({'ok':False, 'code':'ollama_model_missing'}, Mock())
        self.assertEqual(status(self.store)['counts'], {'ignored':1, 'pending':1, 'published':1})
        self.assertEqual(public_posts(self.store), original)
