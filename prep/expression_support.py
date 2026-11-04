"""Prepare speaker-specific expression variants and nonverbal event candidates."""
from __future__ import annotations
import json
from pathlib import Path

EMOTIONS = {
    'neutral': None,
    'angry': 'Keep the reference speaker identity. Speak with controlled anger: firm, tense, forceful, and clearly articulated. Do not scream or distort the words.',
    'sad': 'Keep the reference speaker identity. Speak sadly, with subdued energy, a restrained sorrowful tone, and slightly slower delivery. Keep every word intelligible.',
    'excited': 'Keep the reference speaker identity. Speak with excitement and enthusiasm, bright energy, and lively emphasis. Keep every word intelligible.',
    'calm': 'Keep the reference speaker identity. Speak calmly and reassuringly, with steady pacing and clear articulation.',
}
# These English parenthesized event cues are documented by Breeze. Generation
# remains a candidate until listened to and its event boundaries are marked.
BREEZE_EVENTS = {
    'laugh': '(laugh) Welcome to the server.',
    'sigh': '(sigh) We lost the objective.',
    'cough': '(cough) Communications restored.',
    'clear_throat': '(clears throat) Attention, warriors.',
}
# Grunts and death cries exist as stock files. Awoo/woohoo is spoken cheering,
# not evidence of a wordless cheer; aww is not evidence of crying.
STOCK_CANDIDATES = {
    'avo.grunt': ('grunt', 'nonverbal_candidate'),
    'avo.pain': ('pain', 'nonverbal_candidate'),
    'avo.deathcry_01': ('death_cry', 'nonverbal_candidate'),
    'avo.deathcry_02': ('death_cry', 'nonverbal_candidate'),
    'gbl.woohoo': ('cheer', 'speech_candidate'),
    'gbl.aww': ('disappointment', 'speech_candidate'),
    'gbl.quiet': ('angry_delivery', 'speech_candidate'),
    'gbl.brag': ('confident_delivery', 'speech_candidate'),
    'gbl.sarcasm': ('sarcastic_delivery', 'speech_candidate'),
}

def build_expressive_review(lab, output):
    import csv
    output = Path(output)
    previous = {}
    if output.exists():
        with output.open(newline='', encoding='utf-8') as f:
            previous = {r['source_path']:r for r in csv.DictReader(f)}
    rows = []
    for source in lab.read_manifest()['files']:
        p = Path(source['path'])
        guess = STOCK_CANDIDATES.get(p.stem.casefold())
        if guess is None:
            continue
        group = p.parts[1]
        row = {'source_path':source['path'], 'speaker_id':'' if group == 'Training' else group,
               'candidate_label':guess[0], 'candidate_type':guess[1],
               'speaker_verified':'false', 'event_verified':'false',
               'start_seconds':'', 'end_seconds':'', 'notes':''}
        row.update(previous.get(source['path'], {}))
        rows.append(row)
    if rows:
        lab.write_csv(output, rows, list(rows[0]))
    return rows

def make_jobs(reference, speaker_id, output_root, texts, emotions=None, include_events=True):
    reference, output_root = Path(reference).resolve(), Path(output_root).resolve()
    transcript = reference.with_suffix('.txt').read_text().strip()
    if not reference.is_file() or not transcript:
        raise ValueError('A reviewed reference WAV and its complete transcript are required.')
    if not speaker_id or Path(speaker_id).name != speaker_id:
        raise ValueError('Use a single directory-safe speaker ID.')
    jobs = []
    for emotion in (emotions or list(EMOTIONS)):
        if emotion not in EMOTIONS:
            raise ValueError('Unknown emotion: '+emotion)
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            jobs.append({'id':f'{speaker_id}_{emotion}_{i:03d}', 'speaker_id':speaker_id,
                         'emotion':emotion, 'kind':'speech', 'text':text,
                         'instruction':EMOTIONS[emotion], 'ref_audio_path':str(reference),
                         'ref_text':transcript, 'seed':42,
                         'output':str(output_root/speaker_id/emotion/f'phrase_{i:03d}.wav'),
                         'verified':False})
    if include_events:
        for event, text in BREEZE_EVENTS.items():
            jobs.append({'id':f'{speaker_id}_event_{event}', 'speaker_id':speaker_id,
                         'emotion':'neutral', 'kind':'event_candidate', 'event':event,
                         'text':text, 'instruction':None, 'ref_audio_path':str(reference),
                         'ref_text':transcript, 'seed':42,
                         'output':str(output_root/speaker_id/'events'/f'{event}_with_carrier.wav'),
                         'verified':False})
    return jobs

def export_reviewed_events(lab, review_csv, raw_root, output_root, sample_rate=16000):
    """Export only reviewed nonverbal sounds, preserving each speaker identity."""
    import csv
    import wave
    with Path(review_csv).open(newline='',encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    index = []
    for row in rows:
        if row['speaker_verified'].lower() != 'true' or row['event_verified'].lower() != 'true':
            continue
        speaker = row['speaker_id']
        event = row['candidate_label']
        if any(not x or Path(x).name != x for x in (speaker,event)):
            raise ValueError('Invalid speaker or event ID')
        source = Path(raw_root)/row['source_path']
        temporary = Path(output_root)/'_decoded'/row['source_path']
        lab.decode_pcm(source,temporary,sample_rate)
        with wave.open(str(temporary),'rb') as w:
            duration = w.getnframes()/w.getframerate()
            start = float(row['start_seconds'] or 0)
            end = float(row['end_seconds'] or duration)
            if not 0 <= start < end <= duration:
                raise ValueError('Invalid event boundaries: '+row['source_path'])
            w.setpos(round(start*sample_rate))
            data = w.readframes(round((end-start)*sample_rate))
        destination = Path(output_root)/speaker/'events'/f'{event}_{len(index):03d}.wav'
        destination.parent.mkdir(parents=True,exist_ok=True)
        with wave.open(str(destination),'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(sample_rate); w.writeframes(data)
        index.append({'speaker_id':speaker,'event':event,'file':str(destination.relative_to(output_root)),
                      'source':row['source_path'],'sample_rate':sample_rate,'verified':True})
    Path(output_root).mkdir(parents=True,exist_ok=True)
    (Path(output_root)/'events.json').write_text(json.dumps(index,indent=2))
    return index
