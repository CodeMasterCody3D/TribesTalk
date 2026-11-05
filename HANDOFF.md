# TribesTalk voice-engine handoff

Public source: https://github.com/CodeMasterCody3D/TribesTalk

## What this project delivers

Text goes in. A WAV comes out by joining recorded sound units. Playback uses
Python's standard library only: no Breeze, neural model, internet or GPU.
Breeze and alignment tools are used only to prepare the sound library offline.

Your game integration is separate. Call the renderer however suits your game;
you do not need the experimental native companion or a Tribes 2 installation
to use or finish the standalone voice engine.

## Current bundle — prototype, not a complete voice release

The i0007 preparation pass and private export are complete. The measurements
below describe the delivered wave-5 bank. Full custom-text coverage and acoustic
review remain unfinished; the previous i0006 bundle is preserved separately.

- The tested sample-only engine supports normalization, username aliases,
  pronunciation overrides, stress variants, optional bank-aware pronunciations,
  explicit missing-unit errors, styles, reviewed whole events and phrase caching.
- All 85 short voice/style checks rendered using the i0007 wave-5 candidate
  bank. This does NOT mean those voices can speak every message.
- A 555-message phone-path check supports 554 announcer-neutral messages;
  other neutral voices support 217–420. Angry groups support 213–431,
  sad 101–536, excited 32–388 and calm 86–363, each out of 555 messages.
  These are candidate phone paths, not verified intelligible speech.
- There are 50,122 candidate units and **zero acoustically reviewed units**.
  Identity, emotional delivery, plosive boundaries and events are not certified.
- The current source passed 34 engine and 25 preparation regression cases remotely,
  including incremental gap planning and opt-in workload-frequency priority.
  The optional companion's 17 new cases are authored but NOT executed.
- This increment generated 560 clips; 541 passed machine word checks and 19
  mismatches were withheld. It added 14,603 candidates without deleting earlier
  material. All five delta archives, new raw clips and new unit checksums were
  independently verified locally and the archives backed up privately.
- Ten frozen, previously ungenerated messages across all 17 voices and five styles
  rendered **135/850**, up from **57/850** on the restored i0006 baseline.
  All previously successful requests remain supported; all 17 voice totals improved.
  **715 requests still fail for missing coverage.** These are different texts and
  styles from the earlier neutral-only check; do not compare its 58/170 directly.
- The 256,128,989-byte portable runtime-data bundle passed fresh-extraction checks
  for all 50,130 manifest files, a standard-library render with CUDA disabled,
  and strict refusal of unreviewed samples. Independent local verification checked
  every manifest entry, the export allowlist and the coverage-to-bank binding.
  The separate comparison archive contains 192 checksum-verified audition WAVs
  (57 before and 135 after) and all 1,700 request outcomes. Both archives are
  privately backed up. Successful rendering is not a listening-quality verdict.

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
`tribes2-friend-runtime-i0007.tar.gz` and its checksum receipt through private
access. Its manifest identifies the exact bank, every file checksum, reviewed
count and parent bank; its coverage report is bound to that bank's index hash.
Do not substitute an older report or claim the candidate count is usable coverage.
Expected archive SHA256:
`c066f636db090763396d558418127f3f25809aff445a262a5130d903d0422915`.

For before/after listening, the separate `tribes2-unseen-i0007.tar.gz` is
25,681,781 bytes, SHA256
`12b3a18c49bac00c91f1afaa41ca1336ae8ba3df4d306a9b003ee747815a6fe7`.
Its page is `artifacts/unseen-i0007/index.html` after extraction. It displays
both successful renders and explicit missing-unit refusals; no review is implied.

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

Use the reusable source notebook in `workflow` and the pinned toolchain records.
Executed notebooks and prepared audio remain private.
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
