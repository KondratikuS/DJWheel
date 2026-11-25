# Builds dist\DJWheel-Setup\: DJWheel-Setup.exe (the game, the bridge, a portable Python) and programs\
# next to it - installers from the project's programs\ folder (Resolume Arena, grandMA2 onPC, Windows MIDI
# Services, XDJ-XZ driver; not in git), hard-linked. Copy the whole folder to the other PC.
# Needs nothing but Windows (csc.exe of .NET Framework 4) and a Python 3 on this machine to copy.
# -Python <folder>: take the portable Python from there instead of the machine's own - e.g. the python\ of an
# installed DJ Wheel (%USERPROFILE%\DJWheel\python) on a PC that has no Python.
param([string]$Python)
$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$stage = Join-Path $root "tools\out\installer\DJWheel"
if (Test-Path $stage) { Remove-Item -Recurse -Force $stage }
New-Item -ItemType Directory -Force $stage | Out-Null
Copy-Item -Recurse (Join-Path $root "app") (Join-Path $stage "app")
New-Item -ItemType Directory (Join-Path $stage "tools") | Out-Null
foreach ($f in "start.cmd","serve.cmd","bridge.cmd","check.cmd","midi_loop.cmd","bridge.py","bridge.json","osc_listen.py","midi_listen.py","midi_loop_check.py") {
  Copy-Item (Join-Path $root "tools\$f") (Join-Path $stage "tools") }
Copy-Item (Join-Path $root "RUN.md"), (Join-Path $root "README.md"), (Join-Path $root "START DJ Wheel.cmd"), (Join-Path $root "SETUP DJ Wheel.cmd") $stage
# portable Python: the stdlib of this machine's Python, without packages, tests and Tk
$py = if ($Python) { (Resolve-Path -LiteralPath $Python).Path } else { Split-Path (Get-Command python).Source }
$dst = Join-Path $stage "python"
New-Item -ItemType Directory $dst | Out-Null
Get-ChildItem $py -File | Where-Object { $_.Extension -in ".exe",".dll",".txt" } | Copy-Item -Destination $dst
Copy-Item -Recurse (Join-Path $py "DLLs") (Join-Path $dst "DLLs")
robocopy (Join-Path $py "Lib") (Join-Path $dst "Lib") /E /NFL /NDL /NJH /NJS /XD site-packages test tests idlelib tkinter turtledemo ensurepip __pycache__ | Out-Null
& (Join-Path $dst "python.exe") -I -c "import http.server, json, ctypes, socket, argparse; print('portable python ok')"
if ($LASTEXITCODE -ne 0) { throw "portable python broken" }
$zip = Join-Path $root "tools\out\installer\DJWheel.zip"
if (Test-Path $zip) { Remove-Item $zip }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[IO.Compression.ZipFile]::CreateFromDirectory($stage, $zip, [IO.Compression.CompressionLevel]::Optimal, $false)
$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
$fw = Split-Path $csc
$out = Join-Path $root "dist\DJWheel-Setup"
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force (Join-Path $out "programs") | Out-Null
$exe = Join-Path $out "DJWheel-Setup.exe"
& $csc /nologo /target:winexe /optimize+ "/out:$exe" /reference:System.Windows.Forms.dll /reference:System.Drawing.dll `
  "/reference:$fw\System.IO.Compression.dll" "/reference:$fw\System.IO.Compression.FileSystem.dll" `
  "/resource:$zip,DJWheel.zip" (Join-Path $PSScriptRoot "installer\Setup.cs")
if ($LASTEXITCODE -ne 0) { throw "csc failed" }
# programs\ beside the exe: hard links where the drive allows, copies otherwise
# only the installers Setup.cs knows (its Programs masks): anything else lying in programs\ stays out of the package
$masks = "Resolume_Arena_*Installer.exe","gMA2onPC_*.exe","Windows.MIDI.Services*.exe","XDJ-XZ*.exe"
foreach ($p in Get-ChildItem (Join-Path $root "programs") -File -ErrorAction SilentlyContinue | Where-Object { $n = $_.Name; $masks | Where-Object { $n -like $_ } }) {
  $to = Join-Path $out "programs\$($p.Name)"
  try { New-Item -ItemType HardLink -Path $to -Target $p.FullName -ErrorAction Stop | Out-Null } catch { Copy-Item $p.FullName $to } }
"built: $out  exe $([math]::Round((Get-Item $exe).Length / 1MB, 1)) MB, programs: " + ((Get-ChildItem (Join-Path $out "programs")).Name -join ", ")

