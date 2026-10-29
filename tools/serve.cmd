@echo off
rem Поднимает игру на http://localhost:8090/ из папки app и открывает её в Chrome. Без моста.
cd /d "%~dp0..\app"
where python >nul 2>&1 && (set PY=python) || (set PY=py)
start "" "http://localhost:8090/"
title DJ Wheel server
%PY% -m http.server 8090
