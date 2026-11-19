<!-- Shipped as INSTALL.md in the root of a distribution (see docs/distribution.md in the repository). Links are relative to the distribution root. -->
# Installing Watch Me

Watch Me is a plugin for Claude Code, Codex and Cursor. You narrate what you do on screen,
Watch Me records your microphone, your screens and the cursor, transcribes the speech
offline, and the agent then acts on what you said and showed. The plugin has two skills:
**Watch Me Recorder** ("Start Watch Me") and **Watch Me Video Editor** ("Edit Watch Me").

This folder is the complete plugin. It does not contain the Python environment, the
speech model or FFmpeg: they are downloaded on your computer at the first start (see
"First start" below).

## Before you install

- **Put the folder where it can stay**, for example `C:\Tools\WatchMe` or `~/WatchMe`.
  Use a path without spaces and reuse the same path for later versions: the name of the
  folder does not matter, so drop the version number from it. Claude Code and Codex
  remember the path as the source of the plugin.
- **Do not run anything inside the folder** (no `uv sync`, no launcher). The host copies
  the folder as it is, and an environment created here would be copied with it and would
  not work in the copy.
- **Internet access is needed for the first start**: about 550 MB for the speech model
  plus Python 3.12, the Python packages and FFmpeg.
- Linux and macOS, when the archive was made on Windows: make the launchers executable
  with `chmod +x scripts/*.sh skills/*/scripts/*.sh` in the folder.
- macOS: install FFmpeg yourself (`brew install ffmpeg`); it is not downloaded there.
- Supported: Windows 10/11, Linux with an X11 session (not Wayland), macOS 13 or newer.
  The details are in [docs/installation.md](docs/installation.md), "Requirements".

## Claude Code

In a Claude Code session:

```text
/plugin marketplace add C:\Tools\WatchMe
/plugin install watch-me@watch-me-local
```

Or in a terminal:

```bash
claude plugin marketplace add C:\Tools\WatchMe
claude plugin install watch-me@watch-me-local
```

Then start a new session.

## Codex

```bash
codex plugin marketplace add C:\Tools\WatchMe
```

In the Codex CLI open `/plugins`, pick the `watch-me-local` tab and install `watch-me`.
In the ChatGPT desktop app restart the app and install it from **Plugins**. Then start a
new chat. The Codex IDE extension does not support plugins; use the skill links described
in [docs/installation.md](docs/installation.md) there.

Codex runs commands in a sandbox. Approve the request to run the Watch Me launcher
outside the sandbox, otherwise the window cannot stay open.

## Cursor

Copy this folder to `~/.cursor/plugins/local/watch-me` (on Windows
`%USERPROFILE%\.cursor\plugins\local\watch-me`). It has to be a real copy: Cursor skips
links. Restart Cursor or run **Developer: Reload Window**; **Customize** then lists both
skills.

## First start

Say **Start Watch Me** to the agent.

The first time, the agent reports that the environment is missing and prepares it. Let
it do so and approve its commands (network access, running outside the sandbox):

1. it installs [uv](https://docs.astral.sh/uv/) when it is not on the computer yet,
2. it creates the Python environment next to the installed copy of the plugin
   (uv downloads Python 3.12 and the packages),
3. it downloads the Whisper speech model (548 MB) and FFmpeg into `~/.watch-me`
   (`C:\Users\<you>\.watch-me`).

This takes several minutes, mostly the model. Then the small Watch Me Recorder window
opens: press **Record**, talk while you work, press **Stop**, and hand the recording to
the agent with the green **Process** button in the editor. Later starts are immediate
and work offline.

**Edit Watch Me** opens the Video Editor with the stored recordings.

Recordings are stored in `~/Videos/WatchMe`. How to use the recorder and the editor is
described in [README.md](README.md).

## Updating

Replace the content of the folder with the new version (delete the old files first, keep
the path), then:

- Claude Code: `claude plugin marketplace update watch-me-local`, then
  `claude plugin update watch-me@watch-me-local`, and start a new session.
- Codex: open `/plugins`, uninstall `watch-me` and install it again from the
  `watch-me-local` tab.
- Cursor: replace the copy in `~/.cursor/plugins/local/watch-me` and reload the window.

After an update the agent creates the Python environment once more at the first start.
The model, FFmpeg and your settings in `~/.watch-me` stay, and so do your recordings.

## Uninstalling

- Claude Code: `claude plugin uninstall watch-me@watch-me-local`, then
  `claude plugin marketplace remove watch-me-local`.
- Codex: uninstall `watch-me` in `/plugins`, then
  `codex plugin marketplace remove watch-me-local`.
- Cursor: delete `~/.cursor/plugins/local/watch-me`.

Delete `~/.watch-me` to remove the model, FFmpeg and the settings. Your recordings in
`~/Videos/WatchMe` are yours to keep or delete.

## When something does not work

- The window appears and closes at once, or never appears: the host stopped it together
  with the command. See "What the window needs from the host" and "Troubleshooting" in
  [docs/installation.md](docs/installation.md).
- The download of the model failed: say "Start Watch Me" again; the download continues
  where it stopped.

Watch Me is used in practice with Claude Code on Windows. The steps for Codex and Cursor
follow the documentation of those hosts and have not been exercised yet.
