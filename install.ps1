param(
    [string]$GamePath = '',
    [ValidateSet('Auto','Codex','Generic')][string]$Client = 'Auto',
    [string]$PythonPath = '',
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$projectRoot = $PSScriptRoot

function Find-Python312 {
    $candidates = @()
    if ($PythonPath) { $candidates += $PythonPath }
    $candidates += (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
    foreach ($key in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath',
                       'HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
        if (Test-Path $key) { $candidates += (Join-Path (Get-Item $key).GetValue('') 'python.exe') }
    }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command -and $command.Source -notlike '*\WindowsApps\*') { $candidates += $command.Source }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $located = & $launcher.Source -3.12 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0) { $candidates += $located }
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) { continue }
        & $candidate -c 'import sys,struct; sys.exit(0 if sys.version_info[:2]==(3,12) and struct.calcsize(chr(80))==8 else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    return $null
}

try {
    Write-Host 'PVZ Scared AI Bridge - preparing your AI game bridge'
    if (-not $GamePath) {
        $bundled = Join-Path $projectRoot 'game\PVZ-Scared.exe'
        if (Test-Path -LiteralPath $bundled) { $GamePath = $bundled }
        elseif ($NonInteractive) { throw 'Pass -GamePath with the full game folder or PVZ-Scared.exe path.' }
        else { $GamePath = (Read-Host 'Paste the game folder or PVZ-Scared.exe path').Trim().Trim('"') }
    }
    if (-not (Test-Path -LiteralPath $GamePath)) { throw "Game path does not exist: $GamePath" }
    $selectedPython = Find-Python312
    if (-not $selectedPython) {
        if ($PythonPath) { throw '-PythonPath must point to 64-bit Python 3.12.' }
        $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
        if (-not $winget) { throw 'Install Python 3.12 x64 from https://www.python.org/downloads/windows/ and run install.cmd again.' }
        Write-Host 'Installing Python 3.12 for the current user through winget...'
        & $winget.Source install --id Python.Python.3.12 --exact --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Python installation failed. Install Python 3.12 x64 manually and retry.' }
        $selectedPython = Find-Python312
        if (-not $selectedPython) { throw 'Python was not found after installation. Reopen the terminal and retry.' }
    }
    & $selectedPython -X utf8 (Join-Path $projectRoot 'scripts\install.py') --game $GamePath
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Read the error above; no game controller was started.' }

    $codex = Get-Command codex -ErrorAction SilentlyContinue
    if ($Client -eq 'Codex' -or ($Client -eq 'Auto' -and $codex)) {
        if (-not $codex) { throw 'Codex CLI was not found. Use -Client Generic and import generated\mcp.json manually.' }
        $venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
        & $codex.Source mcp add pvz_scared -- $venvPython -X utf8 (Join-Path $projectRoot 'scripts\run_mcp.py')
        if ($LASTEXITCODE -ne 0) { throw 'MCP registration failed. Import generated\mcp.json manually or retry -Client Codex.' }
        Write-Host 'Registered the pvz_scared MCP server with Codex. Restart your AI client to load it.'
    }
    else { Write-Host 'Import generated\mcp.json into your AI client (stdio MCP).' }
    Write-Host 'Setup complete. Double-click start.cmd, then give your AI generated\START_HERE.txt.'
    exit 0
}
catch { Write-Error $_ -ErrorAction Continue; exit 1 }
