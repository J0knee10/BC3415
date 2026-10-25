@echo off
rem Runs the Meridian AP FX Exposure Bot.
rem   run_bot.cmd            - watch the bot work in a Chrome window
rem   run_bot.cmd -headless  - run without a window (e.g. from Task Scheduler at 09:00)
rem
rem TagUI location: set TAGUI_SRC to TagUI's src folder, otherwise C:\tagui\src is tried
rem (the default install path from the TagUI docs), then the copy used to build this bot.
setlocal
cd /d "%~dp0"
if not defined TAGUI_SRC if exist "C:\tagui\src\tagui.cmd" set "TAGUI_SRC=C:\tagui\src"
if not defined TAGUI_SRC if exist "%~dp0..\..\_runtime\tagui\src\tagui.cmd" set "TAGUI_SRC=%~dp0..\..\_runtime\tagui\src"
if not defined TAGUI_SRC (
  echo TagUI not found. Install TagUI v6.110 to C:\tagui, run
  echo   powershell -ExecutionPolicy Bypass -File tools\patch_tagui_2026.ps1 -TagUISrc C:\tagui\src
  echo then run this file again.
  exit /b 1
)
rem Windows tools first, so TagUI's batch commands are not shadowed by Git/Unix ones
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem;%SystemRoot%\System32\WindowsPowerShell\v1.0"
call "%TAGUI_SRC%\tagui.cmd" fx_ap_bot.tag %*
endlocal
