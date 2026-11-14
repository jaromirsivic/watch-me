@echo off
setlocal
rem Called with WM_ROOT already resolved by the H1 launcher (WM_HELP: its recovery guide).
rem uv is needed to repair the environment, not to start: it is looked for only when the
rem interpreter of the environment is missing.
if exist "%WM_ROOT%\.venv\Scripts\python.exe" goto run
set "WM_CODE=PYTHON_MISSING"
set "WM_EXIT=22"
set "WM_MESSAGE=Prepare the project environment with uv sync --locked."
where uv >nul 2>nul
if not errorlevel 1 goto fail
set "WM_CODE=UV_MISSING"
set "WM_EXIT=20"
set "WM_MESSAGE=Install uv, then retry this launcher."
goto fail

:run
set "WM_BOOT_MARKER=%TEMP%\watch-me-boot-%RANDOM%-%RANDOM%.tmp"
"%WM_ROOT%\.venv\Scripts\python.exe" -I "%WM_ROOT%\scripts\bootstrap.py" %*
set "WM_EXIT=%ERRORLEVEL%"
if not exist "%WM_BOOT_MARKER%" goto nostart
del /q "%WM_BOOT_MARKER%" >nul 2>nul
exit /b %WM_EXIT%

:nostart
set "WM_CODE=PYTHON_MISSING"
set "WM_EXIT=22"
set "WM_MESSAGE=The project Python could not start its bootstrap."

:fail
rem One JSON object on stderr with the code root and the guide. cmd.exe writes a pipe in
rem the console code page, which breaks a path with non-ASCII characters, so PowerShell
rem writes UTF-8 bytes (values travel through the environment, never through this text).
rem Without a usable PowerShell the plain message below is printed instead, without paths.
where powershell >nul 2>nul
if errorlevel 1 goto plain
powershell -NoProfile -NonInteractive -Command "try { $o=[ordered]@{ok=$false;code=$env:WM_CODE;message=$env:WM_MESSAGE;root=$env:WM_ROOT}; if ($env:WM_HELP) { $o.help=$env:WM_HELP }; $w=New-Object IO.StreamWriter([Console]::OpenStandardError(),(New-Object Text.UTF8Encoding $false)); $w.WriteLine((ConvertTo-Json -Compress $o)); $w.Flush() } catch { exit 1 }"
if not errorlevel 1 exit /b %WM_EXIT%

:plain
>&2 echo {"ok":false,"code":"%WM_CODE%","message":"%WM_MESSAGE%"}
exit /b %WM_EXIT%
