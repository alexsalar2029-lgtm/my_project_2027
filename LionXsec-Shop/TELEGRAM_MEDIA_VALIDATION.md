# Telegram media recovery — v1.9.4

The reported warning is Telethon's `TimeoutError: Timeout while fetching data (caused by GetFileRequest)`. Inspection of installed Telethon 1.45.0 confirms this warning comes from RPC retries during file retrieval. It does not identify the specific file or prove whether the underlying cause is a temporary Telegram worker problem or a network problem. No actual user Telegram connection or session was accessed in this environment.

## Findings and changes

- Previously, media downloads and FFmpeg waits lacked application deadlines. A Telegram RPC error while downloading a video could bypass the thumbnail fallback. Failed, empty previews could then be cached for the rest of the receiver session, while metadata-only jobs reached the model.
- Image/thumbnail downloads now have a 30-second deadline, full video downloads 90 seconds, and each FFmpeg frame extraction 15 seconds. Cancelled frame processes are killed/reaped and temporary directories cleaned up. The existing 100 MiB full-video limit and three-frame sampling remain.
- A failed full-video request independently tries Telegram's thumbnail. The model input identifies thumbnail-only evidence. If expected visual evidence is still unavailable, the post remains in `waiting_media` and does not enter model processing. Text-only posts continue normally.
- The history checkpoint atomically records a media retry before advancing the cursor. Later posts can proceed. Four delayed retries follow the initial failure (1, 2, 4, 8 minute minimum delays); after five failures, `media_failed` waits for manual retry. Actual execution may be later while the receiver handles other work.
- Failed files are re-fetched by message ID, including beyond the recent-message window, to refresh file references. Retry jobs and completed source revisions survive receiver restarts. Successful unchanged media is not downloaded each polling cycle, and large base64 previews are no longer kept in an unbounded in-memory cache.
- The worker serializes edit and history downloads. Telethon performs bounded internal request retries and surfaces its last error. Account `FloodWait` delays are honored by the receiver without spending a post's media retry budget. Session/authentication errors are not converted into per-file retries.
- The existing authenticated/CSRF-protected retry button resets failed media back to the receiver queue, preserving published posts and keeping incomplete media out of the AI queue. Optimistic publish/failure checks also respect media deferral occurring during an in-flight AI call, even when the source digest has not changed.
- The admin panel translates media failure states in four languages and refreshes the receiver state, active message number and retry deadline. Application retry records and added progress messages contain safe local error codes and message IDs, not raw provider errors, credentials, phone numbers or file-reference tokens. Telethon's own bounded retry warnings may still appear in the terminal.

## Validation

```sh
python -m unittest discover -s tests -q
PYTHONPATH=. python checks/assistant_smoke.py
python -m py_compile telegram_account.py telegram_media.py automation.py assistant.py
node --check static/assistant-status.js
node --check static/assistant-ui.js
```

114 unit/integration tests passed, including 23 new tests for Telegram RPC timeouts, cancellation, video-to-thumbnail fallback, FFmpeg cleanup, rate limits and invalid sessions, durable retries, cursor atomicity, cache recovery, fresh file references, old-message recovery, retry caps, published-post preservation, legacy-media rescans and concurrent AI/media deferral.

The real local HTTP/SQLite/Chromium smoke test passed: translated media states in four languages, live receiver/message status, media retry separation from AI, existing model diagnostics, authentication/CSRF, logo/contact links, mobile layout and preservation of published posts and unsaved settings. A separate check used real FFmpeg to extract three JPEG frames from a temporary two-second test video. Telegram download transports were simulated.

The release cannot repair Telegram outages, unavailable/deleted source files, or the user's network path. Actual media downloads and publication of the user's backlog require validation on their Windows machine. Users updating from older releases can run a bounded `--rescan-limit 200` once to revisit legacy posts whose failed previews were not tracked; the window size is explicit and adjustable.
