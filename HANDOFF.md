# Voice-engine handoff

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
- All 85 short voice/style checks rendered using the latest private candidate
  bank. This does NOT mean those voices can speak every message.
- A 555-message phone-path check supported 499 announcer-neutral messages, but
  only 0–26 for other neutral voices and generally 0–1 for expressive styles.
- There are 25,669 candidate units and **zero acoustically reviewed units**.
  Identity, emotional delivery, plosive boundaries and events are not certified.
- Forty-seven existing engine/preparation regression cases passed remotely.
  The optional companion's 17 new cases are authored but NOT executed.

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
remote compute, not the protected development laptop. The existing assigned
session expired; a fresh session needs current authorization. Do not launch
one merely by following an old status entry.

## Licensing and optional game code

See `THIRD_PARTY_NOTICES.md` and the pinned full notices under `licenses`.
Private research access is not blanket public/production deployment clearance.
Do not publish source-derived voice banks or original recordings without the
necessary rights. No model or game-audio rights are granted by this repository.

`companion.py`, `package_game.py` and `CLIENT_PLAYBACK.md` are optional integration
references. The friend owns game integration; native installation/playback is
not a completion gate for the voice-engine deliverable. The companion remains
uninstalled and native/runtime untested.
