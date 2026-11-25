@echo off
rem Проверка стенда перед запуском: Python, Chrome, MIDI-устройства, занятость портов.
echo === Python
if exist "%~dp0..\python\python.exe" (echo   свой, в папке python) else (where python py 2>nul || echo   НЕТ: поставить Python 3 с python.org, галочка Add to PATH)
echo === Chrome
set CHR=
for %%R in (HKLM HKCU) do reg query "%%R\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe" /ve >nul 2>&1 && set CHR=1
if defined CHR (echo   есть) else (echo   Chrome не найден: подойдёт Edge, но лучше поставить Chrome)
echo === Порты 8090 (игра) и 7777 (мост): если ниже есть строки LISTENING - уже запущено
netstat -ano | findstr ":8090 :7777" | findstr LISTENING
echo === MIDI-устройства
powershell -NoProfile -Command "$d = Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'MIDI|XDJ|DDJ|Pioneer' } | Select-Object -ExpandProperty FriendlyName -Unique; if ($d) { $d } else { '  дека не видна: USB, питание, CONTROL MODE' }"
echo === Windows MIDI Services (для виртуального порта в Resolume/MA, не обязательно)
if exist "C:\Program Files\Windows MIDI Services\Tools\Console\midi.exe" (echo   есть) else (echo   нет: winget install Microsoft.MIDI.SDK)
pause
