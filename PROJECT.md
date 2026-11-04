# Tribes 2 sample-stitching voice lab

## Authority and acceptance

Latest scope, November 4: deliver the standalone voice engine and a private repo
for the user's friend. The friend will integrate it into the game however he
chooses. Native client/server installation, companion deployment and in-game
playback testing are NOT completion gates for this project. Preserve optional
integration code as untested reference; do not continue that work by inertia.

The user approved one fresh private Kaggle GPU session on November 4 to continue
voice generation/testing and clarified that the interruption was accidental.
Use the dedicated tribes2-voice lane within its configured lifetime. That approval
does not imply further replacement sessions, extra agents or public publication.

Latest continuation: the user said “finish it” after the review-gate stop.
Continue independent private candidate preparation and delivery rather than
stopping all work for listening. This is not acoustic approval: keep reference,
speaker, emotion, boundaries and event review flags honest and unverified until
supported. No new VM, extra agents or timer extension is authorized.

User authorized implementation and Kaggle testing on November 3, 2026.
Prepare all fourteen character packs, announcer, female instructor and male
briefing narrator. Training folder membership is not speaker evidence.
Use Breeze TTS 2 only during preparation, never in the game runtime.
Keep all notebooks, datasets and audio development artifacts private.
Respect Breeze's self-hosted research/noncommercial license and third-party rights.

## Existing implementation to reuse

- User attachment: /home/cody/Downloads/tribes2_voice_lab.ipynb.
- Embedded voice_lab and expression_support helpers: pinned asset inventory,
  hash-checked downloads, review CSVs, reference assembly and Breeze pilots.
- Existing Kaggle control plane: /home/cody/onebit-forge/vmkit/kaggle_vm.py
  and kvm.py. Use a dedicated tribes2-voice tag, not another line's VM.
- Existing Breeze longform driver in /home/cody/Apps/voiceclone is a reference
  for the official load-once runtime, not permission to modify that project.

## Evidence rules

Transcript hints and machine transcripts are unverified until reviewed.
Predicted transitions are not usable-audio coverage. Only validated alignments
may enter released sample banks. Speaker/emotion/event labels need review.
Never fabricate missing units or silently change speaker.
If optional game integration is ever claimed, it requires source and live-client
evidence; a WAV alone is not integration. That work now belongs to the friend.
Current acceptance is standalone text-to-WAV/API behavior, actual voice-library
coverage/review, tested errors, private source/data handoff and license provenance.

## Initial measured state

CLI 2.2.4 supports kernels pull -m, push --accelerator and quota.
CLI account is codemastercody3d; quota reports 43.01 GPU hours remaining.
Pulling codemastercody/tribes-2-voice-lab-breeze-and-diphone-builder failed
with HTTP 403. User explicitly provided attachment fallback.
No dedicated tribes2-voice VM pointer was found.
Model inference and substantive numerical/audio tests run remotely, not laptop.
