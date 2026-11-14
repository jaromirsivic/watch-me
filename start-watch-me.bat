@echo off
setlocal
if "%~1"=="" (
  call "%~dp0skills\watch-me\scripts\watch-me.bat" run --detach
) else (
  call "%~dp0skills\watch-me\scripts\watch-me.bat" %* --detach
)
exit /b %ERRORLEVEL%
