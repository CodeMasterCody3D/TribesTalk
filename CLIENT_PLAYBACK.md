# Client playback: verified source path and remaining proof

## Rules

1. The client must possess the sound bytes before playback.
2. A server filename or chat message does not transfer WAV contents.
3. Never execute chat text as script or accept arbitrary playback paths.
4. Generated Breeze-derived material stays private and noncommercial.

## Source evidence

Pinned T2Mapper revision: b9dda9eaf153d706e94fc71f242866d2f2709394.
Files are retained under `game_scripts`.

- `message.cs`, lines 30–50: `~w` server messages call the CLIENT's
  `alxGetWaveLen`, `alxCreateSource(AudioChat, filename)` and `alxPlay`.
- `message.cs`, lines 149–187: chat constructs `voice/<voice>/<name>.wav`
  locally, sets pitch, and checks the configured maximum chat WAV length.
- `message.cs`, lines 245–255: the server sends command arguments to the
  client, not sample bytes.
- `TrainingGui.cs`, lines 220–232: briefings use local `AudioGui` playback
  and schedule the next local clip from its wave length.

These establish the native script playback mechanism. They do not establish
whether a particular engine build supports any additional file-transfer API.
No live native client/server playback has been exercised in this session.
T2Mapper's browser client is a distinct implementation, not automatically supported.

## Implemented preinstalled-phrase route

If a phrase has been rendered and reviewed:
  Package its WAV and allowlisted ID with `package_game.py`.
  Install the private VL2 in each client's base directory.
  Load `scripts/t2vl_client.cs` on clients and the companion server script.
  After connecting, run `T2VLReady()` on the client.
  An administrator can send `commandToServer('T2VLAnnounce', "<phrase id>")`.
  The server sends an allowlisted ID only to clients with matching pack versions.

If a client has no matching pack:
  It receives a text notification, not a claim that audio played.

If text or a username is newly invented after pack installation:
  This static phrase route cannot speak it.
  A client companion that receives text and uses the sample-only renderer,
  or an explicitly implemented authenticated audio transport, is still required.
   The local companion route below is implemented but NOT deployed or native-tested.

## Local live-text companion — implemented, acceptance pending

1. "Both the game and companion run as the same trusted local user."
2. "The user explicitly installs and enables it; nothing auto-starts."
3. "Requests and responses are data, never executable chat text."
4. "Only a matching bank, allowed voice/style and one outstanding request are accepted."
5. "Timer acknowledgement is not proof that a person heard audio."

If the administrator sends approved text:
  The opt-in client appends a versioned, session-bound request to a private local mailbox.
If the companion accepts it:
  The existing CPU sample renderer writes the local WAV and publishes a response atomically.
If the client sees its matching response:
  It plays only the fixed session-and-sequence WAV path.
If rendering refuses a word, unit or style:
  The client reports refusal; details remain in the companion error record.
If another request is already outstanding:
  It is refused as busy, not silently queued or overwritten.
If the connection changes or the user stops:
  Playback is stopped and the pending request is cancelled.
If acknowledgement is missing:
  The companion times out explicitly, without silently replaying speech.

State: source implementation and Python parse checks only. Transport fixtures
are authored but NOT EXECUTED because the authorized Kaggle lifetime ended.
No actual game installation was identified; no native syntax/compiler/audio
acceptance claim is made. The existing preinstalled-phrase route is unchanged.

### Existing native APIs reused

- `TrainingGui.cs` lines 22–43: FileObject openForRead, readLine and isEOF.
- `OptionsDlg.cs` lines 1738–1745: FileObject openForAppend and writeLine.
- `OptionsDlg.cs` lines 126 and 563: ServerConnection existence and getId usage.
- `message.cs` and `TrainingGui.cs`: local WAV playback, as above.

No TCPObject, network file download or remote code evaluation is assumed. The
companion opens no network listener. Native commandToClient/commandToServer
remains the game connection's text transport, with an administrator-only server
handler and a version/bank handshake. Only enable it on a server you trust.

### Prepared installation procedure — do not confuse with an executed test

Use `companion.py install` with an explicit existing game base, reviewed bank,
exported dictionary and overrides. It writes a private configuration, an empty
mailbox and the generated client/server scripts. Existing configuration or client
script is refused rather than overwritten. No install command was run here.

Start `companion.py serve` on that same machine. On the server, explicitly load
the generated server script. In the native client, load the generated client
script and call `T2VLLiveStart()` AFTER joining the intended server. An approved
administrator sends `commandToServer('T2VLLiveAnnounce', "Announcer", "neutral", "Welcome to the server!")`.
Call `T2VLLiveStop()` to disable playback. Reconnect requires enabling again;
native behavior on the intended engine/OS must still be tested.

The installer defaults to reviewed units only. `--audition-unverified` is an
explicit PRIVATE audition option, not promotion or production clearance.
`--bank-pronunciations` enables the already-tested dictionary/pause path search.
Keep local configuration credentials private; never distribute the mailbox
configuration as part of a voice bank or source archive. Server script has no
client secret. Its bank digest must match participating clients.

Requests are bounded to 240 characters; style markup/control characters are
refused. Single clips are limited to 30 seconds. Request logs and session outputs
have explicit storage budgets. Exhaustion requires preserving/archiving owned
files and an explicit reset decision; there is no automatic deletion. Restart
retains cursor/sequence/pending state. Truncation, replacement, stale requests,
wrong credentials and changed bank/dictionary configuration refuse explicitly.

This is not exactly-once audible delivery: an interruption after consuming a
request may lose that request; it is never automatically replayed as if safe.
Local file permissions assume a trusted same-user host, not an isolation boundary
against other applications running as that user. Windows/native file visibility
and replacement behavior remain live acceptance items.

## Live acceptance still required

Use one actual native client and server with the intended version and OS.
Confirm missing-pack behavior, matching-pack playback, filename case behavior,
audio format support, repeated announcements, disconnect and version mismatch.
Record the client console plus audible capture. The ready handshake alone is not
an acoustic playback test. Do not deploy the generated scripts without that test.
