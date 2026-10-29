# Version 1.5 account connector

- 47 unit/integration tests passed: existing shop/assistant tests plus 7 account-receiver tests.
- Browser check `PYTHONPATH=. python3 checks/assistant_smoke.py` passed: bot/account selector, persisted App ID/hash settings, masked secret fields, private configuration routes, existing publishing/UI/auth/CSRF checks.
- Telethon 1.45.0 and dependencies installed successfully from PyPI; login API signature and permission properties verified against the installed package.
- CLI help and JavaScript syntax checks passed.

History window selection, full history, restart/catch-up without gaps, edit watermark behavior, service-message handling, bot-compatible deduplication keys, config validation, and secret redaction were exercised with simulated channel data.

No actual Telegram login, phone verification, user session, live MTProto connection or OpenAI request was made. The user's App credentials are NOT embedded in source or the archive. Real connectivity requires the owner's local login and channel configuration. Session data, private settings and databases are excluded from the distribution. Earlier validation reports describe earlier versions.
