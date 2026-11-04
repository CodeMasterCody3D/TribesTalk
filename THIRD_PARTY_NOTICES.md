# Third-party notices and private handoff limits

This is a private development source repository, not a grant of public,
commercial or production rights to models, game recordings or generated voices.
No open-source license has been selected for the project's own source. Do not
infer an MIT or Apache license for the whole project from a dependency's license.

## Breeze TTS 2

- Preparation code revision: `daa6cb2efe5471f09369229f322d20bb956cb3c3`.
- Model revision: `3e28c5151381a722f1d8661b4118c298caa77aa4`.
- The preparation code is Apache-2.0; model weights and relevant outputs have
  the separate BreezeBlue Research and Non-Commercial License Agreement.
- Preserve `licenses/Breeze-TTS-2-LICENSE.txt` and `licenses/Breeze-NOTICE.txt`
  with applicable derived audio/banks. Sections 5(c) and 5(d) require performer
  consent and input-recording rights. Production licensing remains separate.
- Full pinned source: https://huggingface.co/BreezeBlue/Breeze-TTS-2/raw/3e28c5151381a722f1d8661b4118c298caa77aa4/LICENSE

Only the FALSE example permission record belongs in reusable source. A source
clone does not grant permission to clone performers or redistribute recordings.

## Pronunciation dictionary

CMUdict is used in offline dictionary export and the sample-only frontend.
Its copyright and redistribution terms are retained in
`licenses/CMUDICT-LICENSE.txt`. Ship that notice with exported dictionary data.
The dictionary is separate runtime data, not a neural model.

## Speaker comparisons and speech tools

WeSpeaker authors: pinned ResNet34-LM comparison model, revision
`f0c48c298fd835726c27956a5d617bad7115627e`, CC-BY-4.0. Model weights are NOT
included. Comparison scores are uncalibrated and do not authenticate identities.
ASR, alignment and other preparation tools retain their own dependency/model
terms. Tested revisions and resolved dependencies are in the toolchain records.

## Tribes 2 material

Original game recordings and performances have rights separate from this source
and Breeze. Reference inventory and preparation helpers came from the user's
supplied notebook; game source evidence used pinned revision
`b9dda9eaf153d706e94fc71f242866d2f2709394`. Original recordings, downloaded game
source archives, personal permission records and prepared sample banks are not
source-repository payloads. Private preparation is not a redistribution grant.
