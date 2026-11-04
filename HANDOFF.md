# TribesTalk voice-engine handoff

Public source: https://github.com/CodeMasterCody3D/TribesTalk

## What this project delivers

Text goes in. A WAV comes out by joining recorded sound units. Playback uses
Python's standard library only: no Breeze, neural model, internet or GPU.
Breeze and alignment tools are used only to prepare the sound library offline.

Your game integration is separate. Call the renderer however suits your game;
you do not need the experimental native companion or a Tribes 2 installation
to use or finish the standalone voice engine.

## Current readiness — prototype, not a complete voice release

- The tested sample-only engine supports normalization, username aliases,
  pronunciation overrides, stress variants, optional bank-aware pronunciations,
  explicit missing-unit errors, styles, reviewed whole events and phrase caching.
- All 85 short voice/style checks rendered using the preserved i0006 wave-8 candidate
  bank. This does NOT mean those voices can speak every message.
- A 555-message phone-path check supports 554 announcer-neutral messages;
  other neutral voices support 25–331. Expressive styles support only 1–26.
  These are candidate phone paths, not verified intelligible speech.
- There are 35,519 candidate units and **zero acoustically reviewed units**.
  Identity, emotional delivery, plosive boundaries and events are not certified.
- The unchanged engine retains 34 passing regression cases; 23 current preparation
  cases passed remotely, including incremental gap planning and opt-in acceleration.
  The optional companion's 17 new cases are authored but NOT executed.
- This increment generated 264 clips; 260 passed machine word checks and four
  mismatches were withheld. It added 9,170 candidates without deleting earlier
  material. All eight delta archives, new raw clips and new unit checksums were
  independently verified locally and the archives backed up privately.
- Ten separate, previously ungenerated neutral messages per voice rendered
  58/170 across the 17 voices, up from 22/170 on the preserved parent bank.
  Fourteen voices improved, Announcer stayed 8/10, and both narrator voices stayed
  0/10. This is a concrete remaining coverage failure, not an acoustic verdict.
- The 184,162,799-byte portable runtime bundle passed fresh-extraction checks
  for all 35,527 manifest files, a standard-library render with CUDA disabled,
  and strict refusal of unreviewed samples. Downloaded checksums were independently
  verified and the runtime bundle privately backed up.

The repository contains source and preparation instructions, not model weights,
original game recordings or a production-ready voice bank. Keep the separate
bank/dictionary bundle and its license notices with your deployment. A Git clone
alone does not contain speech samples and cannot synthesize speech.

## Standalone command

Run from the checkout with an exported bank and dictionary:

```sh
python3 renderer.py --bank /path/to/reviewed-bank \
  --lexicon /path/to/cmudict.json --overrides pronunciation-overrides.json \
  --speaker Announcer --text 'Defend the generator!' \
  --output announcement.wav --cache /path/to/phrase-cache \
  --bank-pronunciations
```

For PRIVATE listening to the current unreviewed candidate bank, explicitly add
`--audition-unverified`. This flag does not promote or approve the samples.
Without it, the current zero-reviewed bank correctly refuses rendering.

## Separate private runtime data

The source repository deliberately excludes audio. Obtain the separately shared
`tribes2-friend-runtime-i0006.tar.gz` and its checksum receipt through private
access. Its manifest identifies the exact bank, every file checksum, reviewed
count and parent bank; its coverage report is bound to that bank's index hash.
Do not substitute an older report or claim the candidate count is usable coverage.
Expected archive SHA256:
`7ecba4fefec371d5aaa37bdabec0cdd6c7de2e51fbd606a3b8400f0600dd9259`.

Extract into a new directory, not over an existing bank. With `DATA` set to that
directory, run from the source checkout:

```sh
python3 -S renderer.py --bank "$DATA/bank" --lexicon "$DATA/lexicon.json" \
  --overrides "$DATA/pronunciation-overrides.json" --speaker Announcer \
  --text 'Defend the generator!' --output announcement.wav \
  --bank-pronunciations --audition-unverified
```

The bundle contains sample data, the exported dictionary, overrides, actual
phone-path coverage and license notices. It excludes models, credentials, the
owner's permission attestation and private continuation state. Keep it private;
providing the files does not establish production or redistribution rights.

## Python API

Reuse the loaded renderer instead of reloading the dictionary for every message:

```python
from phonetics import Lexicon
from renderer import Renderer, MissingUnit

lexicon = Lexicon.load('/path/to/cmudict.json', 'pronunciation-overrides.json')
voice = Renderer('/path/to/reviewed-bank', lexicon, bank_pronunciations=True)
metadata = voice.render('Announcer', 'Defend the generator!', 'announcement.wav')
```

The result includes timing, audio length, checksum, cache state and warnings.
Unknown words raise `UnknownWords`; missing speech/style/event units raise
`MissingUnit`. Report those errors rather than silently choosing another voice
or adding a neural fallback. Audio is mono PCM16 WAV; OS playback is up to you.

## Controls

- Voice IDs: Male1–Male5, Fem1–Fem5, Derm1–Derm3, Bot1, Announcer,
  TrainingFemale and BriefingMale. These are asset-pack/candidate role IDs,
  not verified performer or in-game display-name mappings.
- Styles: `[angry]text[/angry]`, `[sad]text[/sad]`,
  `[excited]text[/excited]`, `[calm]text[/calm]`; unmarked text is neutral.
- Events: `[laugh]`, `[sigh]`, `[grunt]`, `[cheer]`, `[cough]`,
  `[clear_throat]`, `[pain]`, `[death_cry]`. An event requires a reviewed
  isolated sample. Current generated carriers are not approved events.
- Aliases and phone overrides: `pronunciation-overrides.json`.
  New usernames may need explicit aliases; no finite corpus covers all names.
- Neutral/style and stress fallback are OFF unless explicitly selected.
  Bank-aware dictionary/pause choices are reported, not relabeled as exact audio.

## Offline preparation and permissions

Use the staged private notebook in `workflow` and the pinned toolchain records.
Read the consent gate and model license first. The reusable permission example
is FALSE; another user's attestation and credentials are never distributed here.
Do not mass-clone unreviewed references. Check actual aligned-audio gaps rather
than assuming the generated text covered every requested transition.

Model inference, alignment and substantive audio/model tests run on authorized
remote compute, not the protected development laptop. New remote sessions need
current authorization; an old status entry does not authorize launching one.

## Licensing and optional game code

See `THIRD_PARTY_NOTICES.md` and the pinned full notices under `licenses`.
Private research access is not blanket public/production deployment clearance.
Do not publish source-derived voice banks or original recordings without the
necessary rights. No model or game-audio rights are granted by this repository.

`companion.py`, `package_game.py` and `CLIENT_PLAYBACK.md` are optional integration
references. The friend owns game integration; native installation/playback is
not a completion gate for the voice-engine deliverable. The companion remains
uninstalled and native/runtime untested.
