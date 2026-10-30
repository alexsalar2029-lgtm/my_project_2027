"""Install and run pinned llama.cpp + Gemma 3 vision locally on Windows x64."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import tempfile
import time
from urllib.request import urlopen
import zipfile
import zlib

ROOT = Path(__file__).resolve().parent
BUILD = 'b11960'
MODEL_REPO = 'ggml-org/gemma-3-4b-it-GGUF:Q4_K_M'
MODEL_ALIAS = 'lionxsec-gemma-3-4b'
ASSETS = {
    'vulkan': ('llama-b11960-bin-win-vulkan-x64.zip',
               'bac6914b5e83523eb008c6789eaa12669f93fbc196c3b9e8237b6672323b33e9'),
    'cpu': ('llama-b11960-bin-win-cpu-x64.zip',
            '73f962f82850d244db47eaacb9d913637027b82399124324298576d58c5f4287'),
}


def runtime_dir(root, backend):
    return root / '.local-ai' / (BUILD + '-' + backend)


def verify_archive(path, expected):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        # file_digest was added in Python 3.11. Keep the installer compatible
        # with older Python versions without weakening the checksum check.
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    if digest.hexdigest() != expected:
        raise ValueError('download_checksum_mismatch: delete the ZIP and run setup again')


def extract_runtime(archive, destination):
    """The pinned official Windows assets are flat; reject other archive layouts."""
    with zipfile.ZipFile(archive) as source:
        members = source.infolist()
        if sum(m.file_size for m in members) > 512 * 1024 * 1024:
            raise ValueError('runtime_archive_too_large')
        for member in members:
            if (member.filename != Path(member.filename).name or
                    any(c in member.filename for c in ('/', '\\', ':')) or
                    member.filename in ('.', '..') or
                    (member.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError('runtime_archive_invalid_path')
        names = {m.filename for m in members}
        if not {'llama-server.exe', 'llama.dll', 'ggml-base.dll'} <= names:
            raise ValueError('runtime_archive_incomplete')
        source.extractall(destination)


def install_runtime(root=ROOT, backend='vulkan'):
    if platform.system() != 'Windows' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise ValueError('This installer needs Windows x64. See LOCAL_AI_FA.md for manual setup.')
    asset, checksum = ASSETS[backend]
    destination = runtime_dir(root, backend)
    marker = destination / 'verified-sha256.txt'
    if (destination / 'llama-server.exe').is_file() and marker.is_file() and marker.read_text().strip() == checksum:
        print('Verified runtime is already installed.', flush=True)
        return destination
    if destination.exists():
        raise ValueError('Incomplete runtime folder: rename ' + str(destination) + ' and run setup again')
    cache = root / '.local-ai'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / asset
    part = archive.with_suffix('.part')
    if not archive.exists() and part.exists():
        # Recover a complete download left by an interrupted verification or
        # rename. Incomplete/invalid data is discarded and downloaded again.
        try:
            verify_archive(part, checksum)
        except ValueError:
            part.unlink()
        else:
            part.replace(archive)
    if not archive.exists():
        print('Downloading official llama.cpp ' + BUILD + ' (' + backend + ')...', flush=True)
        try:
            url = 'https://github.com/ggml-org/llama.cpp/releases/download/' + BUILD + '/' + asset
            with urlopen(url, timeout=60) as response, part.open('wb') as output:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 256 * 1024 * 1024:
                        raise ValueError('runtime_download_too_large')
                    output.write(chunk)
                    if size // (8 * 1024 * 1024) != (size - len(chunk)) // (8 * 1024 * 1024):
                        print(str(size // (1024 * 1024)) + ' MiB downloaded', flush=True)
            verify_archive(part, checksum)
            part.replace(archive)
        except ValueError:
            # Never extract a mismatched or oversized download. Other failures
            # retain the part for verification on the next setup attempt.
            part.unlink(missing_ok=True)
            raise
    verify_archive(archive, checksum)
    with tempfile.TemporaryDirectory(prefix='install-', dir=cache) as temporary:
        staged = Path(temporary) / 'runtime'
        staged.mkdir()
        extract_runtime(archive, staged)
        (staged / marker.name).write_text(checksum + '\n', encoding='ascii')
        staged.replace(destination)
    print('SHA-256 verified; runtime installed.', flush=True)
    return destination


def select_local_model(data_dir):
    """Explicit setup action; preserve credentials, source, queue and published posts."""
    from assistant import read_config, save_config
    from server import Store
    store = Store(data_dir / 'shop.sqlite3')
    previous = read_config(store)
    save_config(store, {**previous, 'provider':'llamacpp', 'model':MODEL_ALIAS, 'enabled':False})
    print('Gemma selected. Publishing is paused until you test and enable it in the admin panel.')


def server_command(root=ROOT, backend='vulkan', offline=False):
    command = [str(runtime_dir(root, backend) / 'llama-server.exe'),
               '--hf-repo', MODEL_REPO, '--alias', MODEL_ALIAS,
               '--host', '127.0.0.1', '--port', '8081', '--no-webui',
               '--cors-origins', 'localhost', '--no-cors-credentials',
               '--ctx-size', '16384', '--parallel', '1', '--batch-size', '512',
               '--ubatch-size', '128', '--cache-ram', '0', '--jinja',
               '--no-context-shift', '--timeout', '1800']
    if backend == 'cpu':
        command += ['--device', 'none', '--gpu-layers', '0', '--no-mmproj-offload']
    else:
        # Partial offload leaves room for the vision projector and context on older GPUs.
        command += ['--gpu-layers', '20']
    if offline:
        command.append('--offline')
    return command


def start_server(root=ROOT, backend='vulkan', offline=False):
    command = server_command(root, backend, offline)
    if not Path(command[0]).is_file():
        raise ValueError('Run first: python local_ai.py setup --backend ' + backend)
    cache = root / '.local-ai' / 'models'
    cache.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment['LLAMA_CACHE'] = str(cache)
    print('Local AI: http://127.0.0.1:8081 | Gemma 3 4B Q4_K_M | ' + backend, flush=True)
    if not offline:
        print('First start downloads the model AND vision projector from Hugging Face (several GB).', flush=True)
    print('Keep this window open. Run python local_ai.py test in a SECOND window after loading.', flush=True)
    # Argument list handles Windows paths with spaces; no shell or remote script execution.
    child = subprocess.Popen(command, cwd=root, env=environment)
    try:
        return child.wait()
    except KeyboardInterrupt:
        # Ctrl+C also reaches the Windows console child. Reap it before exiting.
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        return 130


def test_image():
    """A synthetic solid blue PNG, generated without an image-library dependency."""
    def chunk(kind, value):
        return struct.pack('!I', len(value)) + kind + value + struct.pack('!I', zlib.crc32(kind + value))
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 64, 64, 8, 2, 0, 0, 0))
    png += chunk(b'IDAT', zlib.compress((b'\0' + b'\0\0\xff' * 64) * 64)) + chunk(b'IEND', b'')
    return 'data:image/png;base64,' + base64.b64encode(png).decode('ascii')


def test_model(transport=None, progress=print):
    """Real local vision + four-language generation; does not read or publish posts."""
    from assistant import check_llamacpp, LlamaCppModel, LOCAL_TIMEOUT
    from automation import validate
    from model_output import ModelOutputError, parse_output
    from service_transport import llamacpp_json, RemoteError
    from decimal import Decimal
    import functools
    config = {'provider':'llamacpp', 'model':MODEL_ALIAS}
    report = check_llamacpp(config, transport)
    if not report['ok']:
        return report
    transport = transport or functools.partial(llamacpp_json, timeout=LOCAL_TIMEOUT)
    started = time.monotonic()
    stage = 'vision'
    try:
        progress('1/2: Testing image understanding with a synthetic color image...')
        image = test_image()
        value = transport('/v1/chat/completions', {
            'model':MODEL_ALIAS, 'stream':False, 'temperature':0, 'max_tokens':48,
            'messages':[{'role':'user', 'content':[
                {'type':'text', 'text':'What is the dominant color in this image? Return JSON with key color in English.'},
                {'type':'image_url', 'image_url':{'url':image}}]}],
            'response_format':{'type':'json_object', 'schema':{'type':'object',
                'properties':{'color':{'type':'string', 'enum':['red','green','blue','white','black']}},
                'required':['color'], 'additionalProperties':False}}})
        try:
            choice = value['choices'][0]
            color = parse_output(choice['message'].get('content'), choice.get('finish_reason') == 'length')
        except (KeyError, TypeError, IndexError, AttributeError):
            raise ModelOutputError('model_output_empty') from None
        if color.get('color') != 'blue':
            return report | {'ok':False, 'code':'llamacpp_vision_test_failed', 'stage':stage}
        stage = 'shop_copy'
        progress('2/2: Testing Persian, English, Arabic and Spanish shop copy with an image...')
        source = 'فروش اشتراک Spotify Premium یک ماهه، قیمت 12.50 USDT، تحویل دستی.'
        generated = LlamaCppModel(config, transport).analyze(source, [image])
        post = validate(generated, source)
        price = post['price']
        if (post['kind'] != 'sale' or not price or price['currency'] != 'USDT' or
                Decimal(price['amount']) != Decimal('12.50')):
            return report | {'ok':False, 'code':'llamacpp_copy_test_failed', 'stage':stage}
        # A four-language structure alone does not establish that Persian/Arabic were generated.
        for lang in ('fa', 'ar'):
            if not any('\u0600' <= c <= '\u06ff' for c in post['summary'][lang]):
                return report | {'ok':False, 'code':'llamacpp_copy_test_failed', 'stage':stage}
        return report | {'ok':True, 'code':'llamacpp_test_passed',
                         'seconds':round(time.monotonic() - started, 1)}
    except (RemoteError, ModelOutputError) as error:
        return report | {'ok':False, 'code':error.code, 'stage':stage}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['setup', 'start', 'test'])
    parser.add_argument('--backend', choices=ASSETS, default='vulkan')
    parser.add_argument('--offline', action='store_true', help='Start only from the downloaded model cache')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'data')
    args = parser.parse_args()
    if args.command == 'setup':
        install_runtime(backend=args.backend)
        select_local_model(args.data_dir)
        print('Next: python local_ai.py start --backend ' + args.backend)
        print('Model license: https://ai.google.dev/gemma/terms (Gemma weights); llama.cpp: MIT.')
    elif args.command == 'start':
        return start_server(backend=args.backend, offline=args.offline)
    else:
        report = test_model(progress=lambda text: print(text, flush=True))
        print(json.dumps(report, ensure_ascii=True))
        if report['ok']:
            print('PASS. Enable publishing in the admin panel and retry failed posts once.')
        return 0 if report['ok'] else 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print('Local AI setup/start failed: ' + str(error))
        print('See LOCAL_AI_FA.md. No posts have been deleted.')
        raise SystemExit(1)
