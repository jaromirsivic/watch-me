@echo off
setlocal
rem Called with WM_ROOT already resolved by the H1 launcher.
where uv >nul 2>nul
if errorlevel 1 (
  >&2 echo {"ok":false,"code":"UV_MISSING","message":"Install uv, then retry this launcher."}
  exit /b 20
)
if not exist "%WM_ROOT%\.venv\Scripts\python.exe" (
  >&2 echo {"ok":false,"code":"PYTHON_MISSING","message":"Prepare the project environment with uv sync --locked."}
  exit /b 22
)
set "WM_BOOT_MARKER=%TEMP%\watch-me-boot-%RANDOM%-%RANDOM%.tmp"
"%WM_ROOT%\.venv\Scripts\python.exe" -I "%WM_ROOT%\scripts\bootstrap.py" %*
set "WM_EXIT=%ERRORLEVEL%"
if not exist "%WM_BOOT_MARKER%" (
  >&2 echo {"ok":false,"code":"PYTHON_MISSING","message":"The project Python could not start its bootstrap."}
  exit /b 22
)
del /q "%WM_BOOT_MARKER%" >nul 2>nul
exit /b %WM_EXIT%
