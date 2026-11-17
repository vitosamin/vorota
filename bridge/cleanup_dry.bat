@echo off
setlocal enabledelayedexpansion
set OUT=C:\Users\Public\cleanup_list.txt
set KEEP=GateBridge.exe GateCtl.exe GateUnblock.exe PsExec64.exe read_last_event.vbs run_bridge.vbs kill_bridge.vbs bridge_watchdog.bat make_watchdog.bat compile_bridge3.bat compile_bridge3.vbs gate_map.json gate_bridge.log
echo === TO DELETE === > "%OUT%"
for %%F in (C:\Users\Public\*) do (
  set "NAME=%%~nxF"
  set "SKIP="
  for %%K in (%KEEP%) do if /i "!NAME!"=="%%K" set "SKIP=1"
  if not defined SKIP (
    if /i not "%%~nxF"=="cleanup_list.txt" if /i not "%%~nxF"=="cleanup_dry.bat" if /i not "%%~nxF"=="run_cleanup.vbs" if /i not "%%~nxF"=="cleanup.bat" (
      if exist "%%F" if not exist "%%F\" echo %%F >> "%OUT%"
    )
  )
)
echo === KEEP === >> "%OUT%"
for %%K in (%KEEP%) do echo %%K >> "%OUT%"
