"""Installation boundaries: game layout without a version gate, portable paths and packaging."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


installer = load("install")
packager = load("package_release")


class InstallTests(unittest.TestCase):
    def test_entry_point_installs_without_game_or_interactive_input(self):
        with tempfile.TemporaryDirectory(prefix="pvzh no game ") as temp:
            root = Path(temp)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "install.ps1", root / "install.ps1")
            (root / "scripts/install.py").write_text(
                "import json,sys\nfrom pathlib import Path\n"
                "Path(__file__).parents[1].joinpath('arguments.json').write_text(json.dumps(sys.argv[1:]))\n")
            result = subprocess.run([
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(root / "install.ps1"),
                "-Client", "Generic", "-PythonPath", sys.executable, "-NonInteractive",
            ], input="", capture_output=True, text=True, encoding="utf8", errors="replace", timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Setup complete", result.stdout)
            # Real game discovery may link an open game, but must never require a path.
            args = json.loads((root / "arguments.json").read_text())
            self.assertTrue(args == [] or len(args) == 2 and args[0] == "--game")

    def test_game_layout_allows_new_builds_but_requires_complete_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            game.mkdir()
            names = ["PVZ-Scared.exe", "GameAssembly.dll", "UnityPlayer.dll",
                     "PVZ-Scared_Data/il2cpp_data/Metadata/global-metadata.dat"]
            for name in names:
                path = game / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            self.assertEqual(installer.validate_game_path(game), game / "PVZ-Scared.exe")
            for name in names:
                with self.subTest(file=name):
                    path = game / name
                    original = path.read_bytes()
                    path.write_bytes(b"different build")
                    self.assertEqual(installer.validate_game_path(game / "PVZ-Scared.exe"), game / "PVZ-Scared.exe")
                    path.unlink()
                    with self.assertRaisesRegex(ValueError, "Game file missing"):
                        installer.validate_game_path(game)
                    path.write_bytes(original)

    def test_generated_configs_support_spaces_unicode_and_external_game(self):
        with tempfile.TemporaryDirectory(prefix="pvzh-install-") as temp:
            root = Path(temp) / "AI 游戏 project"
            root.mkdir()
            game = Path(temp) / "游戏 elsewhere" / "PVZ-Scared.exe"
            installer.write_configuration(game, root)
            settings = json.loads((root / "config.local.json").read_text(encoding="utf8"))
            self.assertEqual(settings["game_executable"], str(game))
            server = json.loads((root / "generated/mcp.json").read_text(encoding="utf8"))["mcpServers"]["pvz_scared"]
            toml = tomllib.loads((root / "generated/codex.toml").read_text(encoding="utf8"))
            self.assertEqual(server, toml["mcp_servers"]["pvz_scared"])
            self.assertEqual(server["command"], str(root / ".venv/Scripts/python.exe"))
            self.assertEqual(server["args"][-1], str(root / "scripts/run_mcp.py"))
            self.assertIn(str(root), (root / "generated/START_HERE.txt").read_text(encoding="utf8"))

    def test_configuration_can_be_created_before_game_is_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            installer.write_configuration(None, root)
            config = json.loads((root / "config.local.json").read_text(encoding="utf8"))
            self.assertEqual(config["game_executable"], str(root / "game/PVZ-Scared.exe"))
            self.assertTrue((root / "generated/mcp.json").exists())

    def test_mcp_setup_check_needs_no_running_game(self):
        self.assertEqual(installer.mcp_smoke(sys.executable), 32)

    def test_package_allowlist_excludes_private_and_generated_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in packager.FILES:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("public")
            for directory in packager.DIRECTORIES:
                (root / directory).mkdir(exist_ok=True)
                (root / directory / "source.py").write_text("public")
            private = ["config.local.json", "game/GameAssembly.dll", "runtime/connection.json",
                       "runtime/purchases.json", "generated/mcp.json", "evidence/save.json",
                       ".venv/secret.py", "research/private.py", "scripts/__pycache__/private.py"]
            for name in private:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("secret")
            files = {p.relative_to(root).as_posix() for p in packager.release_files(root)}
            self.assertTrue(set(packager.FILES).issubset(files))
            self.assertFalse(files.intersection(private))
            self.assertIn("skills/source.py", files)


if __name__ == "__main__":
    unittest.main(verbosity=2)
