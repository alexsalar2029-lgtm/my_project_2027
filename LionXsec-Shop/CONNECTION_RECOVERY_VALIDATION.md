# Service connection recovery — v1.9.3

The report had 1 ignored, 28 pending, 6 published and 27 retry jobs, with the generic `connection_failed` description. The uploaded archive's application files matched v1.9.2 exactly. It did not contain the user's runtime database or Ollama logs.

User-side checks established that both `qwen3-vl:4b` and `qwen3-vl:2b` were installed, a short CLI request to the 4B model completed, and Python received HTTP 200 from the local `/api/tags` endpoint. An empty earlier `ollama ps` showed no model loaded at that moment. These observations establish present connectivity and simple inference, not the cause of earlier failures or the ability to process the full multilingual vision request. No out-of-memory diagnosis is claimed without an Ollama error reporting it.

## Changes

- Distinguish connection refused, timeout, closed connection, DNS, TLS and invalid service JSON. Ollama errors use provider-specific codes. Bounded Ollama error responses are classified for missing model, insufficient memory and stopped model runner; arbitrary error text, paths, headers and tokens are not returned or persisted.
- Only fixed local Ollama requests bypass system proxies. They cannot follow redirects. OpenAI and Telegram retain their normal proxy and certificate handling. The existing 1800-second generation timeout and model/output settings are unchanged.
- Before each due Ollama job, the runner checks `/api/tags` with a 5-second timeout and validates the saved model's presence. A failed check pauses the worker for 60 seconds without consuming queued post attempts. A service failure during inference records that one failed attempt, then pauses before touching the rest of the queue. The next loop checks readiness again. Invalid generated content still uses per-post validation/backoff.
- Add an authenticated, CSRF-protected `POST /api/admin/assistant/diagnostics` and `python assistant.py check-ollama`. Both report service reachability and model installation only; they do not run inference, download models, publish posts or expose credentials.
- Show waiting-for-service and active-message states. Poll status every 5 seconds while the assistant tab is visible, without replacing the form or losing unsaved settings. Polling stops when that form is removed.
- Published content, queue identities, source/media evidence, Telegram order link and lion branding are preserved. The existing retry button resets only retry/failed jobs.

## Validation

Commands (from the application directory, with local socket access):

```sh
python -m unittest discover -s tests -v
PYTHONPATH=. python checks/assistant_smoke.py
python -m py_compile assistant.py automation.py server.py service_transport.py
node --check static/assistant-status.js
node --check static/assistant-ui.js
```

The 91 unit/integration tests passed, including 15 new tests covering Windows/POSIX connection errors, safe diagnostics, installed-but-unloaded models, service failure before and during a job, recovery, published/ignored record preservation and active-message status. A real temporary local HTTP server verified requests work with an unusable system proxy and do not follow redirects.

The Chromium smoke test covers the actual shop HTTP/SQLite/browser path: four-language diagnostic results, authentication/CSRF enforcement, live waiting/active-message updates that retain unsaved model edits, mobile layout, retry/rewrite behavior, logos/contact links and secret redaction. Model, Telegram and Ollama responses are simulated; real Qwen vision generation and recovery of the user's 55 outstanding jobs must be checked after installation on the user's device.
