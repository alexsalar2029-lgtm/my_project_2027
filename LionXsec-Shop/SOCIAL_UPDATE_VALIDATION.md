# Version 1.3 — headline and social links

Changes verified locally:

- Persian headline and its English, Arabic and Spanish translations updated.
- YouTube links to https://www.youtube.com/@ComboList-qe7yy.
- Telegram links to https://t.me/link_Lion.
- Both header icons open the intended URL in a new tab.
- Admin Social networks tab edits eight supported platforms; blank links hide their icons.
- HTTPS and matching-platform URL validation; admin authentication and CSRF protection use the existing server checks.
- Saved links survive reload/reopening the database and subsequent payment-setting saves.
- Updating social links does not modify payment configuration.

Validation run:

```
python3 -m unittest discover -s tests -v
# 31 passed
PYTHONPATH=. python3 checks/social_smoke.py
# Passed in Chromium, four languages at 320 / 390 / 768 / 1440 px.
```

Syntax checks passed for app.js, admin.js, social.js and social-admin.js.
Browser checks used a temporary local database and intercepted outgoing social
navigation. No real accounts were contacted or messages sent. No public site was
deployed. The ZIP excludes runtime databases, media, credentials and caches.
Playwright is only needed for browser validation, not for running the shop.

The earlier VALIDATION.md documents the original v1.2 checks.
