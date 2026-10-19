@echo off
rem Мост DJ Wheel → Resolume / grandMA / MIDI. Создаёт виртуальный MIDI-порт «DJ Wheel Out A/B»
rem (временный, до перезагрузки) и запускает мост с подробным выводом. Окно не закрывать.
"C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" loopback create --name-a "DJ Wheel Out A" --name-b "DJ Wheel Out B" >nul 2>&1
cd /d "%~dp0"
python bridge.py -v
pause
