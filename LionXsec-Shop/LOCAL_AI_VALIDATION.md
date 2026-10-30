# Local Gemma integration validation — v1.10.1

## Installer compatibility hotfix (2026-10-30)

The installer used `hashlib.file_digest`, which is unavailable before Python 3.11. It now streams 1 MiB chunks into `hashlib.sha256`; pinned digests and rejection of corrupt downloads are unchanged. A completed `.part` download is retained after an unexpected verification/rename failure and verified again before reuse. Incomplete parts are discarded and downloaded again; this is not byte-range download resumption.

- Full regression suite: **137 tests passed on Python 3.10.22 and Python 3.12.14**.
- The 23 local-AI tests passed under a real Python 3.10 interpreter with no `hashlib.file_digest`. Four new regressions cover that absent API, a complete retained download, a partial download, and interruption of verification followed by an offline reuse attempt.
- The existing real `asyncio.wait_for` deadline test now expects `asyncio.TimeoutError`, which is distinct from the builtin timeout on Python 3.10. The Telegram production code already handles both; no media behavior was changed. The 23 media tests also passed again on Python 3.12 after this portable assertion change.
- The actual official b11960 Vulkan and CPU ZIPs were checked with the new streaming implementation on Python 3.10. The actual Vulkan archive was recovered from a complete `.part` and extracted in a temporary path containing spaces, without a download. The Windows platform guard was mocked for extraction; Windows executables were not run.
- Python compilation and `git diff --check` passed. Frontend code is unchanged; the browser validation below belongs to v1.10.0 and was not repeated for this installer fix.

The small patch contains only `local_ai.py` plus its Persian update guide. Existing v1.10.0 installations do not need to replace their database, Telegram session, settings, or downloaded models. The old installer's unconditional cleanup may already have deleted the user's failed download; it cannot be recovered by this patch and will need to download once more.

No real Gemma inference or AMD GPU test was performed for this hotfix. The runtime artifact hashes and remaining model limitations below are unchanged.

## Original v1.10.0 validation

Validated on 2026-10-30 in the managed Linux development environment. This report distinguishes application tests from real model inference.

## Application checks

- `python -m unittest discover -s tests -q`: **133 tests passed** (114 existing tests plus 19 local-AI tests).
- `PYTHONPATH=. python checks/assistant_smoke.py`: **passed** against the real local HTTP server, SQLite database and Chromium. Covers the Gemma provider selection, hidden API-key field, authenticated/CSRF-protected diagnostics, messages in four languages, live queue updates, unsaved settings, retry/rewrite controls, preserved publications, media recovery, lion logos, order URL, mobile layout and secret redaction. AI and Telegram responses are simulated; no external calls are made by this browser check.
- Python compilation, JavaScript syntax checks and `git diff --check`: passed.
- After adding the final CORS flags and strengthening the failed-download test, all **19 local-AI tests passed again**.

The local-AI tests exercise schema-constrained requests with image data, truncation rejection, one-turn Gemma-compatible correction requests, model/vision readiness, safe service error codes, queue suspension without consuming pending attempts, recovery, migration preserving secrets/session/posts, failed checksum cleanup, archive traversal rejection and CPU/Vulkan launcher options. A real loopback HTTP fixture exercises the full synthetic vision/copy diagnostic with a deliberately broken system proxy and verifies that local redirects are refused.

The two-stage `python local_ai.py test` command is included for the user's Windows machine. It performs real generation when connected to a running model: identify a synthetic image color, then generate and validate a four-language sample advertisement with its source price. It never reads or publishes real Telegram posts. Its unit/integration tests use simulated completions; a passing application test is not a measured Gemma result.

## Official runtime artifacts checked

The GitHub `v0.8.0` release's `nightly-tag.txt` resolved to **b11960** during implementation. The installer pins b11960 rather than resolving `latest` on each user install.

| Artifact | Size | SHA-256 |
| --- | ---: | --- |
| `llama-b11960-bin-win-vulkan-x64.zip` | 37,345,851 bytes | `bac6914b5e83523eb008c6789eaa12669f93fbc196c3b9e8237b6672323b33e9` |
| `llama-b11960-bin-win-cpu-x64.zip` | 24,407,745 bytes | `73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287` |
| `llama-b11960-bin-ubuntu-x64.tar.gz` | 22,686,210 bytes | `31cc3a6bc638ac6c48dc4b1b74888f1eaadf3d14227c1e5f67daf9a49541d97a` |

Both actual Windows ZIP files were downloaded from the [official release](https://github.com/ggml-org/llama.cpp/releases/tag/b11960), matched the GitHub asset digests, and passed the installer's extraction flow in temporary paths containing spaces. The platform check was mocked for this extraction check; Windows binaries were **not executed** on Linux. The Vulkan package contains `ggml-vulkan.dll`; the CPU package is separate.

The official Linux binary ran and reported `0.8.0-dev`, build `11960`, commit `8642541b2`. Its help and startup accepted the launcher's arguments, including offline mode, one slot, context/batch settings, no web UI, loopback binding and restricted CORS. An offline launch with an empty model cache reached model loading and exited for missing model data. This verifies argument compatibility, not inference or model availability.

## Model selection and limits

The pinned upstream [multimodal guide](https://github.com/ggml-org/llama.cpp/blob/b11960/docs/multimodal.md) documents Gemma 3 vision and automatic model/projector selection via `--hf-repo`. The launcher uses `ggml-org/gemma-3-4b-it-GGUF:Q4_K_M`, a shared `.local-ai/models` cache and the alias `lionxsec-gemma-3-4b`. Model weights are fetched from Hugging Face on the user's first launch and are not bundled with the shop. The engine build is pinned; the model repository is selected by repository name and quantization, not by an immutable weight revision. The engine is MIT licensed; Gemma weights have their separate Gemma terms.

Hugging Face is outside this cloud environment's allowed destinations. Its public model metadata request returned `Tunnel connection failed: 403 Forbidden`. No weights were downloaded and **no real Gemma inference, quality assessment, RAM/VRAM measurement, or AMD RX590 GME execution was performed here**. Vulkan compatibility and generation speed must be checked on the user's Windows machine. CPU fallback is supplied; it is not a speed guarantee.

The local transport is fixed to `http://127.0.0.1:8081`, bypasses system proxies only for this loopback service, and refuses redirects. No online fallback is selected. The launcher binds loopback, limits CORS to localhost, disables CORS credentials and the built-in web UI, and uses a single inference slot. External downloads retain normal TLS verification and system proxy behavior.

The setup command selects Gemma and pauses publishing until the user tests/enables it. Existing Telegram credentials, sessions, jobs, media recovery records and publications are retained. It does not uninstall software or models from a remote Windows computer; the user guide includes `ollama rm qwen3-vl:4b` for the requested local removal. Changing the AI backend does not repair Telegram's `GetFileRequest` network failures.
