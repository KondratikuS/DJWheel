@echo off
rem Запуск стенда целиком: мост (Resolume / grandMA / MIDI) в своём окне + игра в Chrome.
rem Закрыть всё — закрыть оба окна.
cd /d "%~dp0"
where python >nul 2>&1 && (set PY=python) || (set PY=py)
start "DJ Wheel bridge" cmd /k ""C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" loopback create --name-a "DJ Wheel Out A" --name-b "DJ Wheel Out B" >nul 2>&1 & %PY% bridge.py -v"
cd /d "%~dp0..\app"
start "" "http://localhost:8090/"
title DJ Wheel server
%PY% -m http.server 8090
