"""Offline preparation helpers; no neural inference is used by a game server."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.request
import wave
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent

def read_manifest():
    return json.loads((ROOT / 'assets.json').read_text())

def groups():
    return Counter(x['path'].split('/')[1] for x in read_manifest()['files'])

def git_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()

def download_assets(destination, selected=None, workers=4):
    """Pinned originals only; resume only when bytes match the recorded Git blob."""
    destination = Path(destination)
    manifest = read_manifest()
    entries = [x for x in manifest['files'] if selected is None or x['path'].split('/')[1] in selected]
    if not entries:
        raise ValueError('No source files match the selected groups.')
    def one(row):
        relative = Path(row['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe source path')
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and git_sha(target.read_bytes()) == row['sha']:
            return 'cached'
        url = 'https://raw.githubusercontent.com/' + manifest['repository'] + '/' + manifest['revision'] + '/' + quote(manifest['voice_root'] + '/' + row['path'], safe='/')
        for attempt in range(3):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'Tribes2-Voice-Lab'}), timeout=40) as response:
                    data = response.read()
                if git_sha(data) != row['sha']:
                    raise ValueError('Source hash mismatch for ' + row['path'])
                temporary = target.with_name(target.name + '.part')
                temporary.write_bytes(data)
                temporary.replace(target)
                return 'downloaded'
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(attempt + 1)
    failures, counts = [], Counter()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = {pool.submit(one, row):row for row in entries}
        for done, future in enumerate(as_completed(futures), 1):
            try:
                counts[future.result()] += 1
            except Exception as exc:
                failures.append({'path':futures[future]['path'], 'error':str(exc)})
            if done % 100 == 0 or done == len(entries):
                print(f'{done}/{len(entries)}: {dict(counts)}, failed={len(failures)}', flush=True)
    (destination / 'download_failures.json').write_text(json.dumps(failures, indent=2))
    if failures:
        raise RuntimeError(f'{len(failures)} files failed; inspect download_failures.json and rerun to resume.')
    return dict(counts)

def write_csv(path, rows, columns):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        w.writerows(rows)

def transcript_seeds():
    text = (ROOT / 'cannedChatItems.cs').read_text()
    pattern = r'''installChatItem\(\s*'[^']+'\s*,\s*"((?:\\.|[^"\\])*)"\s*,\s*"([^"\n]+)"'''
    return {name.casefold():words for words, name in re.findall(pattern, text) if words.strip()}

def build_review(path):
    """Do not infer speaker from Training subdirectory, or overwrite human review."""
    path = Path(path)
    previous = {}
    if path.exists():
        with path.open(newline='', encoding='utf-8') as f:
            previous = {x['path']:x for x in csv.DictReader(f)}
    seeds = transcript_seeds()
    rows = []
    for entry in read_manifest()['files']:
        p = Path(entry['path'])
        group = p.parts[1]
        row = {'path':entry['path'], 'group':group,
               'speaker_id': '' if group == 'Training' else group,
               'speaker_verified':'false',
               'text':seeds.get(p.stem.casefold(), '') if group not in ('Announcer','Training') else '',
               'transcript_verified':'false', 'use_as_reference':'false', 'notes':''}
        row.update(previous.get(entry['path'], {}))
        rows.append(row)
    write_csv(path, rows, list(rows[0]))
    return rows

def decode_pcm(source, destination, sample_rate=24000):
    if not shutil.which('ffmpeg'):
        raise RuntimeError('FFmpeg is required to decode the original game WAV codecs.')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.stem + '.tmp.wav')
    command = ['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-y','-i',str(source),
               '-ac','1','-ar',str(sample_rate),'-c:a','pcm_s16le',str(temporary)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        temporary.unlink(missing_ok=True)
        raise RuntimeError(result.stderr[-1500:])
    temporary.replace(destination)
    return destination

def preview_path(raw_root, pcm_root, relative):
    source = Path(raw_root) / relative
    if not source.is_file():
        raise FileNotFoundError('Download the pack first: ' + str(source))
    return decode_pcm(source, Path(pcm_root) / relative)

def make_reference(review_csv, raw_root, pcm_root, output, speaker_id):
    """Concatenate reviewed excerpts of ONE speaker; transcript must match ALL speech."""
    with Path(review_csv).open(newline='', encoding='utf-8') as f:
        rows = [x for x in csv.DictReader(f) if x['speaker_id'] == speaker_id and x['use_as_reference'].lower() == 'true']
    if not rows:
        raise ValueError('No reference clips selected for ' + speaker_id)
    if any(x['speaker_verified'].lower() != 'true' or x['transcript_verified'].lower() != 'true' or not x['text'].strip() for x in rows):
        raise ValueError('Verify speaker and complete transcript for every selected reference clip.')
    frames = []
    rate = 24000
    for row in rows:
        path = preview_path(raw_root, pcm_root, row['path'])
        with wave.open(str(path), 'rb') as w:
            if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (1,2,rate):
                raise ValueError('Reference must be mono 24 kHz PCM16')
            frames.append(w.readframes(w.getnframes()))
    data = (b'\0\0' * int(rate * .15)).join(frames)
    seconds = len(data) / (rate * 2)
    if not 3 <= seconds <= 30:
        raise ValueError(f'Reference is {seconds:.1f}s; select roughly 8–15 seconds of clean consistent speech (3–30s limit here).')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(data)
    output.with_suffix('.txt').write_text(' '.join(x['text'].strip() for x in rows))
    output.with_suffix('.json').write_text(json.dumps({'speaker_id':speaker_id,'sources':[x['path'] for x in rows], 'seconds':seconds}, indent=2))
    return output

def install_breeze(destination):
    """Separate interpreter keeps official pinned dependencies away from Kaggle's kernel."""
    destination = Path(destination)
    source = destination / 'breeze-tts'
    python = destination / 'venv' / 'bin' / 'python'
    destination.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        subprocess.run(['git','clone','--depth','1','https://github.com/breezeblue-ai/breeze-tts.git',str(source)], check=True)
    if not python.exists():
        subprocess.run([sys.executable,'-m','venv',str(destination / 'venv')], check=True)
    subprocess.run([str(python),'-m','pip','install','--upgrade','pip'], check=True)
    subprocess.run([str(python),'-m','pip','install','-r',str(source / 'requirements.txt')], check=True)
    # Record actual source/dependencies used. A rerun reuses this checkout rather than pulling changes.
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'], text=True).strip()
    (destination / 'source_revision.txt').write_text(revision + '\n')
    freeze = subprocess.check_output([str(python),'-m','pip','freeze'], text=True)
    (destination / 'requirements-resolved.txt').write_text(freeze)
    return python, source

def clone_preview(destination, reference, text, output, seed=42):
    destination, reference, output = map(Path, (destination, reference, output))
    python = destination / 'venv' / 'bin' / 'python'
    source = destination / 'breeze-tts'
    model_path = destination / 'model'
    if not python.is_file():
        raise RuntimeError('Install Breeze first.')
    subprocess.run([str(python),'-c','import torch; assert torch.cuda.is_available(), "No CUDA GPU available"'], check=True)
    # infer.py expects a local directory, not a model ID.
    subprocess.run([str(python),'-c',
        'from huggingface_hub import snapshot_download; import sys; snapshot_download("BreezeBlue/Breeze-TTS-2", local_dir=sys.argv[1])',str(model_path)],check=True)
    transcript = reference.with_suffix('.txt').read_text().strip()
    if not transcript:
        raise ValueError('Reference transcript is empty.')
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [str(python), str(source / 'infer.py'), str(model_path),
        '--ref-audio', str(reference), '--ref-text', transcript, '--text', text,
        '--output', str(output), '--seed', str(seed), '--cfg-scale','1','--no-fast-all']
    # Eager mode avoids fast-path compilation and extra graph memory. GPU compatibility remains to be tested.
    subprocess.run(command, cwd=source, check=True)
    return output
