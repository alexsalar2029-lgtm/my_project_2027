# Local AI assistant validation — version 1.4

Executed checks:

- `python3 -m unittest discover -s tests -v`: 40 passed (31 existing shop/content tests plus 9 assistant tests).
- `PYTHONPATH=. python3 checks/assistant_smoke.py`: passed using a real local HTTP server, worker thread, SQLite and Chromium; Telegram/model responses were simulated.
- JavaScript syntax checks passed for assistant-ui.js and assistant-feed.js.

Checks exercise update intake, channel filtering, classification/translation result validation, price evidence, atomic publishing, replay deduplication, revision handling including a stale model response, ignored posts, persistent retries, history identity checks, settings, four-language/mobile rendering, escaped model text, admin authentication/CSRF and secret redaction/private paths.

No real bot, channel, OpenAI key, or live model call was configured. No content was published to a public website. Actual AI output quality and real Telegram/OpenAI connectivity remain unverified until the owner connects their own channel and API account. The default assistant is disabled.

The distributed ZIP contains no data directory, local credentials, database or runtime cache. The UI screenshot and integration fixtures contain only temporary test values and are not shipped as runtime content. Original v1.2 and v1.3 validation reports describe those earlier versions.
