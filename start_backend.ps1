# Start the NDA Reviewer backend — SAFELY.
#
# Why this script exists:
#   On Windows, a process bound to 127.0.0.1:8000 and another bound to
#   0.0.0.0:8000 can BOTH listen on port 8000 at the same time. When the
#   browser hits http://localhost:8000, Windows routes to the most-specific
#   listener (127.0.0.1) — which may be an OLD, stale server still running
#   from a previous launch. The result: code fixes appear to "not work"
#   because your requests are being answered by a zombie process running
#   outdated bytecode.
#
#   Launching uvicorn manually each time silently stacked up these zombies.
#   This script guarantees exactly ONE backend by killing every listener on
#   port 8000 (and any stray uvicorn) before starting a fresh instance.

$ErrorActionPreference = "SilentlyContinue"
$port = 8000

Write-Host "Stopping any existing server on port $port ..." -ForegroundColor Yellow

# 1. Kill whatever owns the port (covers both 127.0.0.1 and 0.0.0.0 binds)
$owners = Get-NetTCPConnection -LocalPort $port -State Listen | Select-Object -ExpandProperty OwningProcess -Unique
foreach ($procId in $owners) {
    try { Stop-Process -Id $procId -Force; Write-Host "  killed PID $procId (port owner)" } catch {}
}

# 2. Kill any lingering uvicorn reloader/worker processes that failed to bind
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object { $_.CommandLine -like "*uvicorn*main:app*" } |
    ForEach-Object {
        try { Stop-Process -Id $_.ProcessId -Force; Write-Host "  killed PID $($_.ProcessId) (stray uvicorn)" } catch {}
    }

Start-Sleep -Seconds 1

# 3. Confirm the port is actually free before starting
$still = Get-NetTCPConnection -LocalPort $port -State Listen
if ($still) {
    Write-Host "ERROR: port $port is still in use. Aborting to avoid another zombie." -ForegroundColor Red
    $still | Select-Object LocalAddress, OwningProcess | Format-Table -AutoSize
    exit 1
}

Write-Host "Starting single backend on http://127.0.0.1:$port ..." -ForegroundColor Green

# Bind explicitly to 127.0.0.1 (what 'localhost' resolves to) so there is never
# a competing wildcard bind. --reload picks up code edits automatically.
Set-Location "$PSScriptRoot\backend"
python -m uvicorn main:app --host 127.0.0.1 --port $port --reload
