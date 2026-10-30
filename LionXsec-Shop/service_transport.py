"""Bounded JSON requests with safe, actionable service error codes."""
import errno
import http.client
import json
import socket
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener, urlopen

OLLAMA_ORIGIN = 'http://127.0.0.1:11434'
MAX_RESPONSE = 32 * 1024 * 1024


class RemoteError(Exception):
    def __init__(self, code, retry=30, pause_queue=False):
        super().__init__(code)
        self.code, self.retry, self.pause_queue = code, retry, pause_queue


class NoLocalRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Ollama has no redirects; a local request must never leave loopback.
        return None


def connection_code(error):
    reason = error.reason if isinstance(error, URLError) else error
    number = getattr(reason, 'winerror', None) or getattr(reason, 'errno', None)
    if isinstance(reason, TimeoutError) or number in (errno.ETIMEDOUT, 10060):
        return 'connection_timeout'
    if isinstance(reason, ConnectionRefusedError) or number in (errno.ECONNREFUSED, 10061):
        return 'connection_refused'
    if isinstance(reason, socket.gaierror):
        return 'dns_failed'
    if isinstance(reason, ssl.SSLError):
        return 'tls_failed'
    if isinstance(reason, (ConnectionError, http.client.HTTPException)) or number in (
            errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE, 10053, 10054):
        return 'connection_closed'
    return 'connection_failed'


def ollama_error_code(value, status=500):
    """Inspect a bounded error locally; never retain or return its arbitrary text."""
    message = value.get('error', '') if isinstance(value, dict) else ''
    message = message.lower()[:8192] if isinstance(message, str) else ''
    if any(part in message for part in ('out of memory', 'not enough memory',
            'requires more system memory', 'insufficient memory', 'unable to allocate',
            'failed to allocate', 'cuda error: out of memory')):
        return 'ollama_out_of_memory'
    if 'model' in message and any(part in message for part in ('not found', 'does not exist')):
        return 'ollama_model_missing'
    if any(part in message for part in ('runner process has terminated', 'runner process exited',
                                       'runner process no longer running')):
        return 'ollama_runner_stopped'
    return 'ollama_http_' + str(status)


def http_json(url, payload=None, headers=None, timeout=80, *, local=False):
    if local and urlsplit(url)[:2] != urlsplit(OLLAMA_ORIGIN)[:2]:
        raise ValueError('invalid_ollama_address')
    prefix = 'ollama_' if local else ''
    try:
        request = Request(url, None if payload is None else json.dumps(payload).encode(),
                          {'Content-Type': 'application/json', **(headers or {})})
        # Windows VPN/system proxies may intercept localhost unless explicitly excluded.
        # External services retain the normal inherited proxy and CA settings.
        opener = build_opener(ProxyHandler({}), NoLocalRedirect()).open if local else urlopen
        with opener(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise RemoteError(prefix + 'response_too_large')
        value = json.loads(raw)
        if local and isinstance(value, dict) and value.get('error'):
            raise RemoteError(ollama_error_code(value), 60, pause_queue=True)
        return value
    except HTTPError as error:
        try:
            wait = min(3600, max(5, int(error.headers.get('Retry-After', '30'))))
        except (ValueError, TypeError, AttributeError):
            wait = 30
        code = 'http_' + str(error.code)
        try:
            if local:
                try:
                    value = json.loads(error.read(8192))
                except (ValueError, OSError, http.client.HTTPException):
                    value = {}
                code = ollama_error_code(value, error.code)
        finally:
            error.close()
        pause = error.code in (401, 403, 429) or error.code >= 500 or code == 'ollama_model_missing'
        raise RemoteError(code, max(60, wait) if pause else wait, pause_queue=pause) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RemoteError(prefix + 'service_response_invalid', 60, pause_queue=True) from None
    except (URLError, OSError, http.client.HTTPException) as error:
        raise RemoteError(prefix + connection_code(error), 60, pause_queue=True) from None


def ollama_json(path, payload=None, timeout=5):
    return http_json(OLLAMA_ORIGIN + path, payload, timeout=timeout, local=True)
