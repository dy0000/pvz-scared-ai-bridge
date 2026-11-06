"""Run the download entry point with a local ZIP fixture; no network or real installer."""
from pathlib import Path
import json
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
HARNESS = r'''
param([string]$Bootstrap, [string]$Fixture, [string]$InstallDir, [string]$Archive)
$ErrorActionPreference = 'Stop'
$global:fixtureArchive = $Archive
$global:fixtureRoot = $Fixture
function Invoke-WebRequest {
    param($Uri, $OutFile, [switch]$UseBasicParsing)
    Add-Content -LiteralPath (Join-Path $global:fixtureRoot 'downloads.txt') -Value 'download'
    Copy-Item -LiteralPath $global:fixtureArchive -Destination $OutFile
}
& ([scriptblock]::Create((Get-Content -LiteralPath $Bootstrap -Raw))) -GamePath 'D:\Game with spaces\PVZ-Scared.exe' -Client Generic -InstallDir $InstallDir -NonInteractive
'''
FAKE_INSTALLER = r'''
param([string]$GamePath,[string]$Client,[switch]$NonInteractive)
@{game=$GamePath;client=$Client;noninteractive=[bool]$NonInteractive} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'installed.json')
exit 0
'''


class BootstrapTests(unittest.TestCase):
    def run_fixture(self, fixture, install_dir):
        return subprocess.run([
            "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(fixture / "harness.ps1"),
            "-Bootstrap", str(ROOT / "bootstrap.ps1"), "-Fixture", str(fixture),
            "-InstallDir", str(install_dir), "-Archive", str(fixture / "source.zip"),
        ], capture_output=True, text=True, encoding="utf8", errors="replace", timeout=20)

    def prepare(self, root):
        (root / "harness.ps1").write_text(HARNESS, encoding="utf8")
        with zipfile.ZipFile(root / "source.zip", "w") as archive:
            archive.writestr("pvz-scared-ai-bridge-main/install.ps1", FAKE_INSTALLER)
            archive.writestr("pvz-scared-ai-bridge-main/.gitignore", "private\n")

    def test_download_extract_and_repeat_reuses_existing_installation(self):
        with tempfile.TemporaryDirectory(prefix="pvzh-bootstrap-") as temp:
            root = Path(temp)
            self.prepare(root)
            target = root / "AI project with spaces"
            for attempt in range(2):
                result = self.run_fixture(root, target)
                self.assertEqual(result.returncode, 0, result.stderr)
                installed = json.loads((target / "installed.json").read_text(encoding="utf-8-sig"))
                self.assertEqual(installed, {"game": r"D:\Game with spaces\PVZ-Scared.exe", "client": "Generic", "noninteractive": True})
            self.assertTrue((target / ".gitignore").exists())
            self.assertEqual((root / "downloads.txt").read_text().splitlines(), ["download"])

    def test_unrelated_nonempty_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory(prefix="pvzh-bootstrap-") as temp:
            root = Path(temp)
            self.prepare(root)
            target = root / "unrelated"
            target.mkdir()
            keep = target / "keep.txt"
            keep.write_text("existing")
            result = self.run_fixture(root, target)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not empty", result.stderr)
            self.assertEqual(keep.read_text(), "existing")
            self.assertFalse((root / "downloads.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
