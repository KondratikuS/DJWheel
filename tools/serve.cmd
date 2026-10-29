@echo off
rem Поднимает игру на http://localhost:8090/ из папки app и открывает её в Chrome.
cd /d "%~dp0..\app"
start "" "http://localhost:8090/"
python -m http.server 8090
