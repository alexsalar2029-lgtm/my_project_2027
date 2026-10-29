# Telegram publishing fixes and lion logo — v1.9.1

The source was taken from the supplied `LionXsec-Shop.rar`. Source files are now available in this directory as well as in the distribution ZIP. No production database, Telegram session, uploaded media or credentials were supplied or included in the release.

## Changes

- All assistant cards render the new transparent lion-head PNG, including already-published posts. The same logo is used in the storefront/admin headers, hero emblem, browser icon and generic product fallback. Manually selected product logos remain configurable. The logo is served locally with its original colors; it does not use the service-icon recoloring filters.
- Order buttons resolve the shop's Telegram contact, defaulting to `https://t.me/LionXSec`. Original public/private channel posts have a separate link. Checkout, support and the social default use the corrected contact. The former bundled `link_Lion` contact is upgraded; custom contacts are preserved. Empty social links hide the social icon; ordering falls back to LionXSec.
- The shared OpenAI/Ollama editing prompt specifies product-specific titles, natural translations, distinct summaries and fact-based paragraphs. File metadata is only evidence, not a headline or a subscription duration. OpenAI vision detail uses `auto` to read offer text. Bot document metadata now reaches analysis.
- Generic placeholder titles, raw filename titles and a body identical to its summary are retried instead of published. Existing amount/currency verification remains in place.
- The authenticated, CSRF-protected rewrite action and `python assistant.py reprocess-published` queue published records for rewriting. The current post remains visible on failure; a valid result replaces the same post ID.

## Verification

Tested in the managed Linux environment with Python 3.12, Telethon 1.45.0, imageio-ffmpeg 0.6.0, Playwright 1.64.1 and the preinstalled Chromium.

Run from this directory with the development virtual environment active:

```bash
python -m unittest discover -s tests
PYTHONPATH=. python checks/assistant_smoke.py
PYTHONPATH=. python checks/browser_smoke.py
PYTHONPATH=. python checks/social_smoke.py
```

- 65 unit/integration tests passed (59 original tests plus 6 regression tests).
- Assistant browser check: real HTTP server/database, real local PNG requests and Chromium; the same lion logo on known/unknown products and all post types, header/favicon paths, public/private post sources, correct contact and changes to it, Persian/English/Arabic/Spanish, narrow layouts, escaped model text, rewrite authentication/CSRF and preservation of published content.
- Store browser check: cart, demo restrictions, minimum quantities, product edits, wallet settings, USDT/LTC checkout and manual confirmation. The Telegram checkout URL includes the correct contact and order ID.
- Social browser check: four languages and 320/390/768/1440 widths, link targets, editing, validation, persistence and hidden empty profiles.
- JavaScript/Python syntax checks passed.

The browser checks create temporary databases and do not contact Telegram, OpenAI or payment services. Their Telegram and model responses are simulated. Live Telegram login, production deployment and the actual prose returned by the user's model have not been verified. Model quality still depends on the source evidence and selected model; these checks do not claim otherwise.

The web application needs only Python 3.11+. Account intake and video extraction use `requirements-account.txt`. Playwright is a development-only dependency. Cloud startup/install instructions are saved separately in the environment configuration draft; publication is handled by the environment UI.
