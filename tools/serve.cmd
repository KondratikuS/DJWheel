@echo off
rem Поднимает игру на http://localhost:8090/ из папки app и открывает её в Chrome. Без моста.
cd /d "%~dp0..\app"
set PY="%~dp0..\python\python.exe"
if not exist %PY% (where python >nul 2>&1 && (set PY=python) || (set PY=py))
rem Web MIDI есть в Chrome и Edge; браузер по умолчанию может его не уметь
set B=msedge
for %%R in (HKLM HKCU) do reg query "%%R\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve >nul 2>&1 && set B=chrome
start "" %B% "http://localhost:8090/"
title DJ Wheel server
%PY% -m http.server 8090
