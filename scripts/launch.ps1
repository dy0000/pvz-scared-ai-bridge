param([int]$PidToAttach = 0, [ValidateRange(1,120)][int]$StartupTimeoutSeconds = 30,
      [string]$PythonPath = '', [string]$GamePath = '')
$ErrorActionPreference = 'Stop'
$horrorRoot = Split-Path -Parent $PSScriptRoot
$runtimeDirectory = Join-Path $horrorRoot 'runtime'
New-Item -ItemType Directory -Path $runtimeDirectory -Force | Out-Null
$connection = Join-Path $runtimeDirectory 'connection.json'
$targetGamePath = Join-Path $horrorRoot 'game\PVZ-Scared.exe'
$settings = Join-Path $horrorRoot 'config.local.json'
if (Test-Path -LiteralPath $settings) {
    $targetGamePath = (Get-Content -LiteralPath $settings -Raw | ConvertFrom-Json).game_executable
}
if ($GamePath) {
    if (Test-Path -LiteralPath $GamePath -PathType Container) { $GamePath = Join-Path $GamePath 'PVZ-Scared.exe' }
    $targetGamePath = [IO.Path]::GetFullPath($GamePath)
}

function Get-ReadyBridge([int]$ExpectedHostPid = 0) {
    if (-not (Test-Path -LiteralPath $connection)) { return $null }
    try { $current = Get-Content -LiteralPath $connection -Raw | ConvertFrom-Json }
    catch { return $null }
    if ($current.host -ne '127.0.0.1' -or $current.port -ne 47633 -or
        $current.game -ne 'PVZ-Scared' -or $current.executable -ne $targetGamePath -or
        -not $current.session_id -or -not $current.token -or -not $current.host_pid) { return $null }
    if ($ExpectedHostPid -gt 0 -and $current.host_pid -ne $ExpectedHostPid) { return $null }
    $listener = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $current.port -State Listen -ErrorAction SilentlyContinue
    if (-not ($listener | Where-Object { $_.OwningProcess -eq $current.host_pid })) { return $null }
    if ($current.state -eq 'release_blocked') {
        throw 'Native release is unconfirmed. The existing host retains ownership; wait for release or close the game normally.'
    }
    if ($current.state -ne 'ready') { return $null }
    if ($PidToAttach -gt 0 -and $current.pid -ne $PidToAttach) { throw 'The bridge owns a different game PID.' }
    return $current
}

$ready = Get-ReadyBridge
if ($ready) { Write-Output "Horror bridge ready. Host PID $($ready.host_pid), game PID $($ready.pid), port $($ready.port)."; exit 0 }
if (Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 47633 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Port 47633 is occupied but a ready horror bridge could not be verified. Keep the existing controller; do not start a second host.'
}
$runningGames = @(Get-Process -Name 'PVZ-Scared' -ErrorAction SilentlyContinue | Where-Object Path)
if (-not (Test-Path -LiteralPath $targetGamePath -PathType Leaf)) {
    $candidates = @($runningGames | Where-Object { $PidToAttach -eq 0 -or $_.Id -eq $PidToAttach })
    if ($candidates.Count -ne 1) { throw 'Open one PVZ-Scared game and run start.cmd again, or pass -GamePath with its full path.' }
    $targetGamePath = $candidates[0].Path
}
if ($PidToAttach -eq 0) {
    $matching = @($runningGames | Where-Object { $_.Path -eq $targetGamePath })
    if ($matching.Count -gt 1) { throw 'Multiple game processes match this path. Select one with -PidToAttach.' }
    if ($matching.Count -eq 1) { $PidToAttach = $matching[0].Id }
}
[IO.File]::WriteAllText($settings, (@{game_executable=$targetGamePath} | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
if (-not $PythonPath) { $PythonPath = Join-Path $horrorRoot '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Run install.cmd first to prepare the project Python environment.' }
$stopRequest = Join-Path $runtimeDirectory 'stop.request'
if (Test-Path -LiteralPath $stopRequest) { Remove-Item -LiteralPath $stopRequest }
$launchId = Get-Date -Format 'yyyyMMdd-HHmmss-ffff'
$logPrefix = Join-Path $runtimeDirectory "launch-$launchId"
$runnerPath = Join-Path $PSScriptRoot 'run_bridge.py'
$runnerArgs = @('-u','-X','utf8',('"' + $runnerPath + '"'))
if ($PidToAttach -gt 0) { $runnerArgs += @('--pid', $PidToAttach.ToString()) }
else { $runnerArgs += '--launch' }
$process = Start-Process -FilePath $pythonPath -ArgumentList $runnerArgs -WorkingDirectory $horrorRoot -WindowStyle Hidden -RedirectStandardOutput "$logPrefix.out.log" -RedirectStandardError "$logPrefix.err.log" -PassThru
$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
do {
    $process.Refresh()
    if ($process.HasExited) {
        $details = Get-Content -LiteralPath "$logPrefix.err.log" -Tail 15 -ErrorAction SilentlyContinue | Out-String
        throw "Horror bridge failed to start (exit $($process.ExitCode)). Logs: $logPrefix`n$details"
    }
    $ready = Get-ReadyBridge -ExpectedHostPid $process.Id
    if ($ready) { Write-Output "Horror bridge ready. Host PID $($ready.host_pid), game PID $($ready.pid), port $($ready.port). Logs: $logPrefix"; exit 0 }
    Start-Sleep -Milliseconds 200
} while ((Get-Date) -lt $deadline)
throw "Horror bridge readiness timed out. Host PID $($process.Id) may still be starting; do not start another host. Logs: $logPrefix"
