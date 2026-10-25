"""Image back ends for portraits (opt-in; image generation costs money).

codex   a signed-in Codex CLI draws the image; the style reference and the earlier version are attached.
openai  the OpenAI Images API (needs "image_model" in config.json and OPENAI_API_KEY); attachments are not sent, so a
        new version of a character may look less like the earlier one.
"""
import base64
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.error
import urllib.request

from . import llm


def codex_image(prompt, attachments, workdir, codex=None):
    started = time.time()
    root = Path.home() / '.codex' / 'generated_images'
    codex = codex or llm.find_codex()
    if not codex:
        raise RuntimeError('Codex CLI not found; install it and run "codex login", or choose image_provider "openai"')
    answer = Path(workdir) / 'answer.txt'
    args = [codex, '--ask-for-approval', 'never', 'exec', '--ignore-user-config', '--skip-git-repo-check',
            '--sandbox', 'workspace-write', '-c', 'project_doc_max_bytes=0', '-C', str(workdir)]
    for a in attachments:
        args += ['-i', str(a)]
    args += ['--output-last-message', str(answer), '-']
    result = subprocess.run(args, input=prompt, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=900, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise RuntimeError(f'Codex failed ({result.returncode})')
    reply = answer.read_text(encoding='utf-8').strip() if answer.exists() else ''
    path = Path(reply.splitlines()[-1].strip()) if reply else None
    if not (path and path.exists()):
        fresh = [p for p in root.rglob('*.png') if p.stat().st_mtime >= started - 2] if root.exists() else []
        path = max(fresh, key=lambda p: p.stat().st_mtime) if fresh else None
    if not path or not path.exists():
        raise RuntimeError('Codex returned no image')
    return path


def openai_image(prompt, model, key, workdir, post=None):
    body = {'model': model, 'prompt': prompt, 'size': '1024x1024', 'n': 1}
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key}

    def default_post(url, headers, body):
        request = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        try:
            with urllib.request.build_opener(llm.NoRedirect()).open(request, timeout=600) as response:
                return json.loads(response.read(40000000))
        except urllib.error.HTTPError as error:
            raise RuntimeError(f'OpenAI Images API HTTP {error.code}; check key, model and billing') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise RuntimeError('OpenAI Images API connection failed') from None
    result = (post or default_post)('https://api.openai.com/v1/images/generations', headers, body)
    try:
        data = base64.b64decode(result['data'][0]['b64_json'])
    except (KeyError, IndexError, TypeError, ValueError):
        raise RuntimeError('The Images API returned no inline image; use a model that returns b64_json') from None
    path = Path(workdir) / 'portrait.png'
    path.write_bytes(data)
    return path


def make_runner(settings):
    """runner(prompt, attachments, client, workdir) -> path of a PNG."""
    provider = settings['image_provider']
    if provider == 'codex':
        return lambda prompt, attachments, client, workdir: codex_image(prompt, attachments, workdir)
    if provider == 'openai':
        model, key = settings['image_model'].strip(), os.environ.get('OPENAI_API_KEY', '').strip()
        if not model or not key:
            raise RuntimeError('image_provider "openai" needs "image_model" in config.json and OPENAI_API_KEY')
        return lambda prompt, attachments, client, workdir: openai_image(prompt, model, key, workdir)
    raise ValueError('image_provider must be "codex" or "openai"')
