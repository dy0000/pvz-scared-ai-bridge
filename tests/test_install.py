"""Installation boundaries: exact build, portable paths, MCP smoke and public-source packaging."""
import hashlib
import importlib.util
import json
from pathlib import Path
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
    def test_build_must_match_every_pinned_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            game = root / "game"
            game.mkdir()
            names = ["PVZ-Scared.exe", "GameAssembly.dll", "UnityPlayer.dll",
                     "PVZ-Scared_Data/il2cpp_data/Metadata/global-metadata.dat"]
            hashes = {}
            for name in names:
                path = game / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / "profile.json").write_text(json.dumps({"sha256": hashes}))
            self.assertEqual(installer.verify_game(game, root), game / "PVZ-Scared.exe")
            for name in names:
                with self.subTest(file=name):
                    path = game / name
                    original = path.read_bytes()
                    path.write_bytes(b"different build")
                    with self.assertRaisesRegex(ValueError, "Unsupported game file"):
                        installer.verify_game(game / "PVZ-Scared.exe", root)
                    path.unlink()
                    with self.assertRaisesRegex(ValueError, "Game file missing"):
                        installer.verify_game(game, root)
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
