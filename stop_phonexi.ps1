# Stops the detached Phonexi daemon (pythonw running main.py from this folder).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$procs = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -like '*main.py*' -and $_.CommandLine -like "*$($here -replace '\\','\\')*" }

if (-not $procs) {
    # Fallback: any pythonw running a main.py
    $procs = Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
        Where-Object { $_.CommandLine -like '*main.py*' }
}

if (-not $procs) {
    Write-Host "Phonexi not running."
    return
}

foreach ($p in $procs) {
    Write-Host "Killing PID $($p.ProcessId) -> $($p.CommandLine)"
    Stop-Process -Id $p.ProcessId -Force
}
Write-Host "Phonexi stopped."
