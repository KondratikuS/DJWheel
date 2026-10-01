@echo off
rem Создаёт MIDI-петлю «DJ Wheel A» <-> «DJ Wheel B» (Windows MIDI Services).
rem Петля временная: живёт до перезапуска службы MIDI или ПК — тогда запустить снова.
rem Постоянную можно сделать в приложении MIDI Settings (Пуск -> MIDI Settings -> Loopbacks).
"C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" loopback create --name-a "DJ Wheel A" --name-b "DJ Wheel B"
python "%~dp0midi_loop_check.py" "DJ Wheel"
pause
