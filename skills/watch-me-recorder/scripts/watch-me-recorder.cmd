@echo off
setlocal
rem Watch Me Recorder launcher (Windows). Runs the plugin through uv from the repository root.
rem The root is WATCH_ME_ROOT, else three levels above this script, else the same three
rem levels behind the junction or directory symlink the skill is registered with (the host
rem hands the agent the link path). "dir /AL" prints the link target; PowerShell is the fallback.
set "WM_ROOT="
set "DIRCMD="
if defined WATCH_ME_ROOT if exist "%WATCH_ME_ROOT%\pyproject.toml" for %%I in ("%WATCH_ME_ROOT%\.") do set "WM_ROOT=%%~fI"
if not defined WM_ROOT if exist "%~dp0..\..\..\pyproject.toml" for %%I in ("%~dp0..\..\..") do set "WM_ROOT=%%~fI"
if not defined WM_ROOT for %%P in (".|..\..\.." "..|..\.." "..\..|..") do for /f "tokens=1,2 delims=|" %%A in (%%P) do for %%D in ("%~dp0%%A") do for /f "delims=-abcdefghijkmnopqrstuvwxyz" %%L in ("%%~aD") do if not defined WM_ROOT (
  for /f "tokens=1* delims=>" %%G in ('dir /AL "%%~fD*" 2^>nul') do for /f "tokens=*" %%Z in ("%%H") do for /f "tokens=1,2 delims=[]" %%S in ("%%Z") do if /i "%%S"=="%%~nxD " if /i "%%~fT"=="%%T" if exist "%%T\%%B\pyproject.toml" for %%R in ("%%T\%%B") do set "WM_ROOT=%%~fR"
  if not defined WM_ROOT (
    set "WM_LINK=%%~fD"
    for /f "delims=" %%T in ('powershell -NoProfile -NonInteractive -Command "$i = Get-Item -LiteralPath $env:WM_LINK -Force; [IO.Path]::GetFullPath([IO.Path]::Combine($i.Parent.FullName, @($i.Target)[0]))" 2^>nul') do if exist "%%T\%%B\pyproject.toml" for %%R in ("%%T\%%B") do set "WM_ROOT=%%~fR"
  )
)
if not defined WM_ROOT (
  >&2 echo {"ok":false,"code":"ROOT_NOT_FOUND","message":"Watch Me root not found: no pyproject.toml three levels above this launcher, also not behind its junction or symlink. Register the skill again with scripts/install-hosts or set WATCH_ME_ROOT to the Watch Me directory."}
  exit /b 21
)

rem The recovery guide of this skill, named in environment errors (the path the host gave).
for %%I in ("%~dp0..\references\agent-startup.md") do set "WM_HELP=%%~fI"
rem Without arguments (a double click) the launcher opens its own window.
rem Two one-line ifs, no block: an argument may hold a closing parenthesis.
if "%~1"=="" call "%WM_ROOT%\scripts\launch.bat" run --detach
if not "%~1"=="" call "%WM_ROOT%\scripts\launch.bat" %*
exit /b %ERRORLEVEL%
