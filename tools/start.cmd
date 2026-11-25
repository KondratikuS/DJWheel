@echo off
rem Запуск стенда целиком: Resolume Arena + grandMA2 onPC (если стоят), мост в своём окне, игра в Chrome.
rem "start.cmd setup" - без игры, только мастер привязки падов. Закрыть всё - закрыть окна.
cd /d "%~dp0"
set PY="%~dp0..\python\python.exe"
if not exist %PY% (where python >nul 2>&1 && (set PY=python) || (set PY=py))
tasklist /fi "imagename eq Arena.exe" | find /i "Arena.exe" >nul || (if exist "%ProgramFiles%\Resolume Arena\Arena.exe" start "" "%ProgramFiles%\Resolume Arena\Arena.exe")
set MA=
for /f "delims=" %%F in ('where /r "%ProgramFiles%\MA Lighting Technologies" gma2onpc.exe 2^>nul') do set "MA=%%F"
tasklist /fi "imagename eq gma2onpc.exe" | find /i "gma2onpc" >nul || (if defined MA start "" "%MA%")
start "DJ Wheel bridge" cmd /k ""C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" loopback create --name-a "DJ Wheel Out A" --name-b "DJ Wheel Out B" >nul 2>&1 & %PY% bridge.py -v"
cd /d "%~dp0..\app"
rem Web MIDI есть в Chrome и Edge; браузер по умолчанию может его не уметь
set B=msedge
for %%R in (HKLM HKCU) do reg query "%%R\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve >nul 2>&1 && set B=chrome
rem Настройки моста (мастер привязки падов) открываются при каждом запуске отдельным окном рядом с игрой;
rem "start.cmd setup" открывает только их.
if /i not "%~1"=="setup" start "" %B% "http://localhost:8090/"
start "" %B% --new-window "http://localhost:8090/setup.html"
title DJ Wheel server
%PY% -m http.server 8090
