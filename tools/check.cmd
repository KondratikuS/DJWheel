@echo off
rem Проверка стенда перед запуском: Python, Chrome, MIDI-устройства, занятость портов.
echo === Python
where python py 2>nul || echo   НЕТ: поставить Python 3 с python.org (галочка "Add to PATH")
echo === Chrome
reg query "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve 2>nul | find "REG_SZ" || echo   Chrome не найден (подойдёт и Edge)
echo === Порты 8090 (игра) и 7777 (мост): если ниже есть строки LISTENING — уже запущено
netstat -ano | findstr ":8090 :7777" | findstr LISTENING
echo === MIDI-устройства
powershell -NoProfile -Command "Get-PnpDevice -Class MEDIA -Status OK | Select-Object -ExpandProperty FriendlyName"
echo === Windows MIDI Services (для виртуального порта в Resolume/MA, не обязательно)
if exist "C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" (echo   есть) else (echo   нет: winget install Microsoft.MIDI.SDK)
pause
