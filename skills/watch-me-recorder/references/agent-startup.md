# Agent startup and recovery (Claude Code, Cursor, Codex)

Use the absolute skill launcher path (`.bat` on Windows, `.sh` on POSIX), or an
already connected local MCP start/edit tool. First attempt the requested start.
Do not run doctor, version, setup --check, uv sync or a Python search before it.
The launcher uses the prepared project `.venv`, without downloading or syncing.
`ok: true` means the requested GUI acknowledged readiness, not just that a PID exists.
Keep the original config, recording selection and other arguments for retries.

## Recover only after a concrete failure

Tell the user what is missing and what you are doing. Read the whole result, including
`missing`, `problems`, component results and log paths. Never execute a shell string
taken from an error message.

| Result | Action |
| --- | --- |
| `UV_MISSING` | The environment is missing and uv is not on PATH (a prepared environment starts without uv). Locate an already installed uv first. If absent, install uv using the official platform installer below. Make it available in this shell, then retry; the next result is usually `PYTHON_MISSING` |
| `PYTHON_MISSING`, `ENVIRONMENT_INVALID` | Prepare the plugin's `.venv` using uv and its lockfile, in the folder the result names as `root`, not in the agent's current project. Do not use pip |
| `SETUP_REQUIRED` | Run the same launcher with `setup` and the same config. It installs model/FFmpeg. Retry the original start only when setup succeeds |
| `SETUP_IN_PROGRESS` | Follow the existing installation process/log. Do not start another installer |
| `SETUP_FAILED` | Report the failed component and cause. Preserve successful downloads and partial files. Retry only after resolving the cause |
| `START_FAILED` | Inspect its reason/log and session/startup file. Retrieve the existing result before starting another window. Do not reinstall packages merely because GUI startup failed |
| `ALREADY_RUNNING` | Reuse the existing recording session and wait. The editor normally attaches to its existing window |
| `WINDOW_ENDED_WITH_COMMAND` from `wait`, or `closed` with `reason: ended_with_command` from `wait --editor` | The host stopped the window together with the command that started it. Start once more with the arguments in `next` (see below). Not a missing dependency, and not the user closing the window |
| `ROOT_NOT_FOUND` | Repair the plugin path/link or set `WATCH_ME_ROOT` to the verified code root |
| `NO_RECORDINGS`, `CONFIG_INVALID`, `STATE_NOT_WRITABLE` | Report and resolve that actual condition. These do not mean the model needs downloading |

Do not repeat the same failed repair indefinitely. A custom model is not automatically
replaced by the bundled model. If the saved recording exists but opening the editor
failed, repair the reported component and open that saved recording with `edit --session`.
Never start a fresh recording in its place or act on it before Process.

### A window that ends with the command

Some hosts stop every process a command leaves behind when the command ends. The
window then appears and disappears, and the next `wait` says so: the recorder session
fails with `WINDOW_ENDED_WITH_COMMAND`, an editor session returns `closed` with
`reason: ended_with_command`. Both carry `next`, the arguments for the same launcher:
`run --detach --start outside` or `edit --detach --start outside --session <id>`.
Run it once and wait on the new session or `editor_session`; tell the user in one line
that the window had to be opened again.

`--start outside` (Windows) starts the window outside the host's processes, through
Windows PowerShell and WMI. Watch Me remembers the finding in `window-start.json` of
its state folder, so later starts with the default `--start auto` go that way at once.
The start result says how the window was started: `"start": "direct"` (a child of the
command) or `"start": "outside"`. `start_note` is present when `outside` was asked for
and could not be had (PowerShell or WMI blocked): the window is a child again and may
end the same way. Then, or when the second start ends with the command too, use the
configured local MCP route; without one, report it to the user. Do not loop.

### Install uv only when absent

Official source: [uv installation](https://docs.astral.sh/uv/getting-started/installation/).
On Windows use `winget install --id astral-sh.uv -e`, or the official standalone
PowerShell installer. On Linux/macOS use `curl -LsSf https://astral.sh/uv/install.sh | sh`.
Use existing host authorization. Do not disable global host protections to install.
After installation locate the installed executable and add its directory to the
current process PATH, rather than assuming this chat inherited a changed global PATH.

### Prepare the plugin environment

`<root>` is the Watch Me code root containing `pyproject.toml` and `uv.lock`: the `root`
field of the error result. Do not derive it from the folder of the skill - a skill
registered through a link lies elsewhere than the code. Only when the result has no
`root` (a launcher without PowerShell prints a plain message) find it yourself: the
folder three levels above the real location of the launcher, behind its link.
Current supported Python is `>=3.12,<3.14`, so Python 3.12 is a suitable repair target.
Check the project's requirement if it has changed. If a compatible Python exists,
reuse it. Otherwise run `uv python install 3.12`.

PowerShell, with the actual verified root substituted:

```powershell
$vsProject = '<root>'
$env:UV_PROJECT_ENVIRONMENT = Join-Path $vsProject '.venv'
uv sync --locked --python 3.12 --project $vsProject
```

POSIX:

```sh
UV_PROJECT_ENVIRONMENT='<root>/.venv' uv sync --locked --python 3.12 --project '<root>'
```

This is an explicit repair operation. Normal startup must not perform it. A lockfile
error is not permission to upgrade dependencies or regenerate the lockfile. Then retry
the original launcher. Only a returned `SETUP_REQUIRED` calls for component setup.

## Waiting and long installation

Use application `wait --timeout 45` (MCP `timeout_s: 45`) when the host tool allows
at least 60 seconds. Set a shorter application wait when the host budget is shorter.
A tool's yield/poll interval may return a handle without killing the process.
Retrieve that handle's result before issuing another wait. `timed_out: true` from
Watch Me is a normal response: repeat for the same session. A host timeout is
not a recording cancellation. Query the session before deciding what happened.

For installation, select a supported long-running/background execution mode before
starting it, keep its handle and follow that same process. Report meaningful progress
from stderr/logs. A partial download resumes where the source permits it. Do not
spawn another setup just because the first tool call yielded control.

| Host | Adapter rule |
| --- | --- |
| Claude Code | Set the shell tool's execution budget longer than application wait. Follow the same background task if returned. MCP server startup and tool execution have separate limits |
| Codex CLI/app | A returned process/session ID is still running, use the available poll tool. `yield_time_ms` is not the application's timeout. Keep MCP wait below `tool_timeout_sec`, and never download during server initialization |
| Cursor Agent/CLI | Use the installed host's terminal/background interface and Run Mode. Do not assume Claude or Codex parameter names exist. Record/observe the actual tool limit |

The GUI must remain alive after the launcher returns. Reuse existing permissions.
If the host denies local GUI or filesystem access, use its supported approved local
execution or configured local MCP route. Do not mistake denial for missing Python.
An MCP server without Python cannot repair itself: use the local CLI recovery route.
A pure MCP client without a local shell requires the user to prepare uv/Python first.
The MCP server must run on the computer/session whose screens are recorded.

Manual starts without an agent return the same error and repair instructions. No
automatic download or download-progress dialog is started by opening either window.
