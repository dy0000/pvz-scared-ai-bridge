"""Prepare an isolated environment and machine-local AI configuration; never drive the game."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify_game(game: Path, root: Path = ROOT) -> Path:
    game = game.expanduser().resolve()
    if game.is_dir():
        game /= "PVZ-Scared.exe"
    if game.name.lower() != "pvz-scared.exe":
        raise ValueError("Select the PVZ-Scared.exe file or its containing folder.")
    profile = json.loads((root / "profile.json").read_text(encoding="utf8"))
    for name, expected in profile["sha256"].items():
        path = game.parent / name
        if not path.is_file():
            raise ValueError(f"Game file missing: {name}. Extract the complete Windows 1.0.1 game first.")
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Unsupported game file: {name}. This bridge supports only the pinned Windows 1.0.1 build; do not bypass the hash check.")
    return game


def write_configuration(game: Path, root: Path = ROOT) -> None:
    generated = root / "generated"
    generated.mkdir(exist_ok=True)
    python = str(root / ".venv" / "Scripts" / "python.exe")
    server = {"command": python, "args": ["-X", "utf8", str(root / "scripts" / "run_mcp.py")]}
    (root / "config.local.json").write_text(json.dumps(
        {"game_executable": str(game)}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    (generated / "mcp.json").write_text(json.dumps(
        {"mcpServers": {"pvz_scared": server}}, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    # JSON basic strings are also TOML basic strings for these Windows paths/arguments.
    (generated / "codex.toml").write_text(
        "[mcp_servers.pvz_scared]\ncommand = " + json.dumps(python, ensure_ascii=False) +
        "\nargs = " + json.dumps(server["args"], ensure_ascii=False) + "\n", encoding="utf8")
    (generated / "START_HERE.txt").write_text(
        f"请通过 PVZ Scared AI Bridge 帮我玩植物大战僵尸恐怖版剧情模式。\n"
        f"项目目录：{root}\n"
        f"先读 {root / 'skills/pvz-horror-player/SKILL.md'} 和其 references/api.md。\n"
        "使用 pvz_scared MCP 的 pvzh_* 工具。若客户端尚未加载，先按 README 完成注册并重启客户端。\n"
        "先读取 capabilities、observe 和 menu，再作为唯一控制者 take_control。\n"
        "使用当前 ID，保留原生费用和冷却；未经我明确授权，不购物、不用 test_assist。\n"
        "F8/F9 停止锁只能由我按 F10 解除；结束时 release_control 并确认交还。\n",
        encoding="utf8")


def mcp_smoke(python: str, root: Path = ROOT) -> int:
    messages = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    result = subprocess.run([python, "-X", "utf8", str(root / "scripts/run_mcp.py")],
                            input="".join(json.dumps(m) + "\n" for m in messages),
                            text=True, encoding="utf8", capture_output=True, check=True, timeout=15)
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    if len(replies) != 2 or replies[0].get("id") != 1 or replies[1].get("id") != 2:
        raise RuntimeError("MCP handshake returned an unexpected response")
    if "serverInfo" not in replies[0].get("result", {}):
        raise RuntimeError("MCP initialization failed")
    tools = replies[1]["result"]["tools"]
    if not tools or not all(tool["name"].startswith("pvzh_") for tool in tools):
        raise RuntimeError("MCP tool definitions are missing")
    return len(tools)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game", required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != "win32" or sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise SystemExit("Use Windows with 64-bit Python 3.12.")
    # The same host lock protects the environment against updates while it is in use.
    import msvcrt
    runtime = ROOT / "runtime"
    runtime.mkdir(exist_ok=True)
    with (runtime / "controller.lock").open("a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit("The bridge is running. Release control and stop this project's host before installing updates.")
        print("[1/4] Checking game files (read-only)...", flush=True)
        game = verify_game(args.game)
        python = ROOT / ".venv/Scripts/python.exe"
        print("[2/4] Preparing project Python environment...", flush=True)
        if not python.exists():
            subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
        print("[3/4] Installing pinned bridge dependency...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--disable-pip-version-check",
                        "-r", str(ROOT / "requirements.txt")], check=True)
        print("[4/4] Writing configuration and checking MCP...", flush=True)
        write_configuration(game)
        count = mcp_smoke(str(python))
        print(f"MCP handshake OK: {count} tools. Game files verified. No game controller started.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
