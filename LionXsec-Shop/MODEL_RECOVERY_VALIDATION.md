# Model response recovery — v1.9.2

Reported symptom: `account_mode`, 4 published posts, 57 retry jobs, and `model_response_invalid` on recent jobs. The user identified `qwen3-vl:4b` as the model. `account_mode` itself is a normal receiver configuration, not an error.

The former code collapsed JSON parsing, missing translations, length violations and editorial checks into one error. Reproductions confirmed that a newline in an otherwise valid title, an additional language, and identical summary/body text for a short post could be rejected. The user's actual model replies/database were not available, so these reproductions do not establish the cause of every reported retry.

## Changes

- Ollama uses a JSON schema with all four required languages, bounded generation (title 180 / summary 350 / body 1200 characters per language), a 16384-token context and the existing 4096-token output limit. The larger context accommodates source text, video frames and four-language output; it may use more memory than the previous 8192-token context.
- The decoder accepts a complete JSON object, including a BOM or enclosing JSON Markdown fence. Prose, truncated JSON and non-object results are rejected. Provider-reported truncation is distinguished from malformed JSON.
- Title whitespace is normalized, additional language keys are discarded, and legitimate overlap in short descriptions is accepted. Identical summary/body text appears once in the storefront. Required languages, nonempty strings, length checks, specific titles and source-verified prices remain enforced.
- A model-output failure gets at most one corrective model call per queued attempt, using the original source/images and a locally constructed explanation. Network/authentication failures use the existing scheduled backoff without an additional immediate call. A correction can therefore require a second inference (or billed API request for OpenAI).
- Safe error codes identify the field/language or parsing/truncation problem. The admin panel translates them and shows failed-attempt counts and scheduled retry times. Raw model replies, request headers and credentials are not saved as diagnostics.
- The authenticated, CSRF-protected `POST /api/admin/assistant/retry` button and `assistant.py retry-failed` reset only retry/failed jobs to pending, clearing their retry deadline and attempt count. Published records and ignored jobs remain intact. Current published content remains visible if its replacement fails.

## Executed checks

From `LionXsec-Shop`:

```bash
python -m unittest discover -s tests
PYTHONPATH=. python checks/assistant_smoke.py
```

- All 76 unit/integration tests passed, including 11 new parsing, validation, bounded-repair, transport-failure, privacy and retry-reset regression tests.
- The real local HTTP/SQLite/Chromium smoke test passed: lion logos and contact link, four languages/mobile layout, readable error causes, retry authentication/CSRF, resetting only failed jobs, preserving published content, admin configuration and zero external requests.
- Python and JavaScript syntax checks passed.

Model/Telegram responses in these checks were simulated. Ollama/Qwen is not installed in the managed test environment; actual inference on the user's device and recovery of the user's 57 jobs remain to be checked after installing the update. The patch does not claim those remote jobs have already published successfully.
