"""Run the real launcher in a temporary tree with mocked process/network commands."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
param([string]$Case, [string]$Root, [string]$PythonPath)
$ErrorActionPreference='Stop'
$global:fixtureCase=$Case
$global:fixtureRoot=$Root
$global:fixtureOccupied=$false
function Write-FixtureConnection([string]$State='ready',[int]$Owner=123456) {
    $global:fixtureOccupied=$true
    $game = Join-Path $global:fixtureRoot 'game\PVZ-Scared.exe'
    $settings = Join-Path $global:fixtureRoot 'config.local.json'
    if (Test-Path -LiteralPath $settings) { $game = (Get-Content -LiteralPath $settings -Raw | ConvertFrom-Json).game_executable }
    @{host='127.0.0.1';port=47633;game='PVZ-Scared';executable=$game;session_id='test-session';token='test-token';host_pid=$Owner;pid=234567;state=$State} |
        ConvertTo-Json | Set-Content -LiteralPath (Join-Path $global:fixtureRoot 'runtime\connection.json')
}
function Get-NetTCPConnection {
    param($LocalAddress,$LocalPort,$State,$ErrorAction)
    if ($global:fixtureOccupied) { [pscustomobject]@{OwningProcess=123456} }
}
function Get-Process {
    param($Name,$ErrorAction)
    if ($global:fixtureCase -eq 'auto-discover') {
        [pscustomobject]@{Id=234567;Path=(Join-Path $global:fixtureRoot 'running game\PVZ-Scared.exe')}
    }
}
function Start-Process {
    param($FilePath,$ArgumentList,$WorkingDirectory,$WindowStyle,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru)
    if ($global:fixtureCase -eq 'auto-discover' -and
        ($ArgumentList -notcontains '--pid' -or $ArgumentList -notcontains '234567')) { throw 'Expected automatic attach to the discovered exact process' }
    Set-Content -LiteralPath (Join-Path $global:fixtureRoot 'started') -Value 'started'
    Set-Content -LiteralPath $RedirectStandardError -Value 'fixture startup failure'
    $process=[pscustomobject]@{Id=123456;HasExited=$false;ExitCode=7;RefreshCount=0}
    $process | Add-Member -MemberType ScriptMethod -Name Refresh -Value {
        $this.RefreshCount++
        if ($global:fixtureCase -eq 'failure') { $this.HasExited=$true }
        if ($global:fixtureCase -in @('new-ready','auto-discover') -and $this.RefreshCount -eq 2) { Write-FixtureConnection }
    }
    return $process
}
if ($Case -eq 'auto-discover') {
    New-Item -ItemType Directory -Path (Join-Path $Root 'running game') | Out-Null
    New-Item -ItemType File -Path (Join-Path $Root 'running game\PVZ-Scared.exe') | Out-Null
}
else {
    New-Item -ItemType Directory -Path (Join-Path $Root 'game') | Out-Null
    New-Item -ItemType File -Path (Join-Path $Root 'game\PVZ-Scared.exe') | Out-Null
}
if ($Case -eq 'existing-ready') { Write-FixtureConnection }
if ($Case -eq 'external-ready') {
    Write-FixtureConnection
    $externalGame = Join-Path $Root 'other game\PVZ-Scared.exe'
    @{game_executable=$externalGame} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Root 'config.local.json')
    $configPath = Join-Path $Root 'runtime\connection.json'
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $config.executable = $externalGame
    $config | ConvertTo-Json | Set-Content -LiteralPath $configPath
}
if ($Case -eq 'wrong-owner') { Write-FixtureConnection -Owner 999999 }
if ($Case -eq 'release-blocked') { Write-FixtureConnection -State 'release_blocked' }
& (Join-Path $Root 'scripts\launch.ps1') -StartupTimeoutSeconds 1 -PythonPath $PythonPath
'''


class LauncherTests(unittest.TestCase):
    def run_case(self, case):
        with tempfile.TemporaryDirectory(prefix='pvzh-launcher-test-') as temp:
            root = Path(temp)
            (root/'scripts').mkdir()
            (root/'runtime').mkdir()
            shutil.copy2(ROOT/'scripts/launch.ps1', root/'scripts/launch.ps1')
            (root/'harness.ps1').write_text(HARNESS, encoding='utf8')
            result = subprocess.run(
                ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                 str(root/'harness.ps1'),'-Case',case,'-Root',str(root),'-PythonPath',sys.executable],
                capture_output=True, text=True, encoding='utf8', errors='replace', timeout=15)
            return result, (root/'started').exists()

    def test_waits_for_new_host_readiness(self):
        result, started = self.run_case('new-ready')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(started)
        self.assertIn('bridge ready', result.stdout)

    def test_start_failure_returns_nonzero_and_shows_log(self):
        result, started = self.run_case('failure')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(started)
        self.assertIn('fixture startup failure', result.stderr)
        self.assertNotIn('bridge ready', result.stdout)

    def test_readiness_timeout_returns_nonzero(self):
        result, started = self.run_case('timeout')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(started)
        self.assertIn('readiness timed out', result.stderr)

    def test_reuses_verified_existing_host_without_starting(self):
        result, started = self.run_case('existing-ready')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(started)

    def test_configured_external_game_reuses_its_existing_host(self):
        result, started = self.run_case('external-ready')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(started)

    def test_first_start_discovers_and_attaches_an_open_game(self):
        result, started = self.run_case('auto-discover')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(started)

    def test_does_not_treat_another_port_owner_as_ready(self):
        result, started = self.run_case('wrong-owner')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(started)
        self.assertIn('could not be verified', result.stderr)

    def test_does_not_start_over_a_blocked_release(self):
        result, started = self.run_case('release-blocked')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(started)
        self.assertIn('Native release is unconfirmed', result.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
