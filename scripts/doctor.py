"""Read-only local diagnostics. Does not connect to or control a running game."""
import json
import sys
from pathlib import Path

from install import ROOT, mcp_smoke, verify_game


def main():
    import frida
    config = json.loads((ROOT / "config.local.json").read_text(encoding="utf8"))
    verify_game(Path(config["game_executable"]))
    print("Game build: pinned Windows PVZ-Scared 1.0.1, SHA256 OK")
    print(f"Python: {sys.version.split()[0]}, Frida: {frida.__version__}")
    print(f"MCP: initialize + tools/list OK ({mcp_smoke(sys.executable)} tools)")
    print(f"AI configuration: {ROOT / 'generated/mcp.json'}")
    connection = ROOT / "runtime/connection.json"
    if connection.exists():
        state = json.loads(connection.read_text(encoding="utf8"))
        print(f"Last host record: state={state.get('state')}, host_pid={state.get('host_pid')}, game_pid={state.get('pid')}")
        print("This record alone does not prove the host is currently running. Start with start.cmd.")
    print("Local checks passed. Live gameplay was not exercised; no token was displayed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Check failed: {exc}\nRun install.cmd again or see README troubleshooting.", file=sys.stderr)
        raise SystemExit(1)
