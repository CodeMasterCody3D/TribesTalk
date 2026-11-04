# Tribes 2 sample-only voices

Private research/noncommercial development. **Not a completed seventeen-voice release.**
Current measured progress and blockers are in `BOARD.md`.

**Deliverable:** the standalone voice engine and a private repository for a friend.
The friend handles game integration. No native Tribes 2 installation or playback
test is required to complete the voice-engine handoff. Start with `HANDOFF.md`
for direct text-to-WAV and Python API usage; game scripts are optional references.
The source repo alone does not include speech samples or a finished voice bank.

## Earlier checkpoints and acceptance limits

These dated preparation checkpoints are history, not current bank counts.
See `HANDOFF.md` for the latest standalone data bundle, measured coverage and
remaining blockers. No candidate count below is acoustic approval.

All 121 preparation clips were generated and hash checked. Exact-word ASR passed
114 of 117 speech clips; three are withheld. MFA extracted 3,835 candidate units
across 17 voices. None are acoustically reviewed or production-eligible yet.
The announcer neutral bank covers 302 of the declared 333 target transitions as
unverified candidates; other voice/style banks contain only short pilot material.
Predicted complete coverage did not survive actual pronunciation/pause alignment.
For example, MFA aligned a reduced vowel in “to” where the frontend's first
dictionary pronunciation requests a full vowel. Commas also do not guarantee a
recorded silence. Missing transitions are refused, never fabricated.

Thirty-eight remote regression tests passed. Real sample-only rendering runs
with CUDA disabled and Python site packages disabled. This proves execution,
not naturalness, voice identity, emotional delivery or native game playback.
The sample-only voice/style matrix produced 57 playable candidates and 28
explicit missing-unit refusals for “Defend the generator!”; each voice ID has
at least one playable candidate. None of these is an approved production bank.

The November 4 opt-in pronunciation-path repair improves the SAME candidate bank
to 84/85 matrix requests and 6/6 announcer phrases, with 46 remote regression
tests passing. See `iterations/i0001/evidence.json`. The previous source/notebook
archive is preserved as its older snapshot; current development continues under
GRIP and is not a final project release.

The next coverage pass preserves earlier alignments while adding existing stock
speech and a real paused carrier. It produces 25,669 unreviewed candidates and
renders all 85/85 SHORT-PHRASE matrix requests. This does not establish custom-text
coverage: a larger 555-message phone-path check supports 499 announcer-neutral
messages, but only 0–26 messages for the other neutral voices and generally 0–1
per expressive style. Exact gaps and receipts are in `iterations/i0002`.

## Components

- `workflow/tribes2_sample_engine.ipynb`: self-contained staged Kaggle workflow.
- `toolchain-lock.json` and `requirements-breeze.lock.txt`: tested source/model
  revisions and resolved Breeze dependencies, not floating latest.
- `prep/`: recovered preparation notebook helpers and pinned 2,393-file inventory.
- `remote_prepare.py`, `asr_entry.py`, `setup_remote.py`: remote download, decode,
  resumable ASR and isolated dependencies. No local model execution.
- `pilot.py`: separate provisional references and load-once Breeze pilots with
  source/model revisions, dependency versions, timings and GPU memory.
- `speaker_audit.py`: pinned WeSpeaker ONNX comparisons; no inferred identity is
  silently certified, and window disagreement remains visible.
- `phonetics.py`, `build_reports.py`: CMUdict normalization, pronunciation/username
  overrides, cross-word and silence transitions, per-speaker coverage and set cover.
- `alignment.py`: actual MFA phone alignments, not ASR word-time slicing.
- `bank.py`, `build_bank.py`: midpoint diphones with 5 ms handles, stress/allophone
  metadata, release protection and review gates.
- `events.py`: reviewed whole-sample events, excluding generated carrier speech.
- `renderer.py`: Python standard-library sample stitching, complementary 5–10 ms
  crossfades, explicit errors/fallback, checksum-checked phrase caching.
- `render_voice_matrix.py`: explicit 17-voice/five-style sample-only audition
  matrix, retaining missing-unit refusals rather than substituting another voice.
- `package_game.py`: private reviewed phrase VL2 and allowlisted client/server
  scripts. See `CLIENT_PLAYBACK.md`; the static pack is not live audio transport.
- `companion.py`: opt-in local native-game mailbox and generated client/server
  scripts for live custom text, reusing the sample-only renderer. Implemented,
  Python parse-checked, NOT installed or runtime/native-tested. Seventeen remote
  transport fixtures are authored in `test_companion.py`, not yet executed.

## Sample-only runtime

Copy a reviewed bank, exported dictionary, overrides, `phonetics.py`, `bank.py`
and `renderer.py` to the playback host. Python is the only software dependency.

```sh
python renderer.py --bank reviewed-bank --lexicon cmudict.json \
  --overrides pronunciation-overrides.json --speaker Announcer \
  --text '[angry]Defend the generator![/angry] [grunt]' \
  --output announcement.wav --cache phrase-cache
```

Missing words, speech units, emotion variants or events fail explicitly. There
is no automatic voice substitution or neural fallback. `--emotion-fallback neutral`
and `--stress-fallback` are opt-in and produce warnings. `--audition-unverified`
is for listening to a candidate bank only; it never marks samples verified.

`--bank-pronunciations` is an optional sample-only path search over dictionary
alternatives and recorded pauses. It reports every non-default pronunciation,
word-boundary pause or comma without silence. Explicit phone overrides remain
authoritative; strong sentence punctuation still requires recorded silence.
It does not invent units, change their phone labels, waive review, mix speakers
or enable neutral/stress fallback. Without this flag the strict first-dictionary
pronunciation and literal punctuation behavior remains unchanged.

Reuse one loaded Renderer instance for warm/cache latency; dictionary startup
is measured separately. The full dictionary is immutable; create a new Lexicon
and Renderer to replace it. Alias/override changes invalidate cache keys.

## Remote preparation

Use the existing VM-kit client with the dedicated `tribes2-voice` tag. Do not reuse
an unrelated model VM or push another notebook for every change. The notebook
and source archive are reusable preparation deliverables; staging uses file put,
jobs use run/log, and results use get. Keep runtime artifacts under the job's
artifact directory; exclude environments, model caches and credentials from exports.

Both transcript predictions and machine-aligned samples remain candidates until
review. For plosives, annotate a stable closure anchor and a protected full release
interval. Crossfade handles must not touch that release. Stress is preserved in
phone keys. Actual allophones need acoustic review, not invented labels.

The sample bank builder defaults to reviewed material only:

```sh
python build_bank.py --alignments reviewed-alignments --output reviewed-bank \
  --events reviewed-events.json
```

Generated event cue jobs retain full carrier sentences until listened to and
bounded. Spoken cheering and spoken "aww" must not be mislabeled as wordless
cheers or crying. The stock list of 125 expressive candidates is unverified.

## Scope and licensing

The gap target is a declared Tribes-themed workload, not all English diphones.
No natural-language passage or finite dictionary guarantees arbitrary username
pronunciations. Add explicit aliases or phone overrides and report unknowns.

Breeze code is Apache-2.0; weights and self-hosted outputs have a separate
[research/noncommercial license](https://huggingface.co/BreezeBlue/Breeze-TTS-2/blob/main/LICENSE).
Sections 5(c) and 5(d) require explicit performer consent and the necessary input
recording rights. The user confirmed those permissions for this project's named
voices; no contracts were independently reviewed. A persistent, voice-scoped
permission record gates cloning. Reusable source ships a FALSE example, not
another user's permission attestation.

Noncommercial intent alone is not clearance for every deployment. Section 1.7
defines commercial purpose broadly, including production/service/plugin uses;
section 3 requires separate written licensing for commercial purpose. A sample-only
runtime does not remove restrictions from Breeze-derived banks. Nothing here
certifies a production/public server deployment. Preserve the pinned full license
and notice exported with the private artifacts.

Game audio rights are separate. Private development is not a redistribution grant.
WeSpeaker comparison model: CC-BY-4.0, attribution to WeSpeaker authors;
revision and model digest are recorded in its report. CMUdict attribution/license
must accompany any dictionary export. No artifact was published publicly.
