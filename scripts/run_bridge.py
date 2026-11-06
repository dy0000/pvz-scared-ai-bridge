"""Exclusive local bridge host for the pinned PVZ-Scared game, no desktop input."""
from __future__ import annotations

import argparse
from collections import OrderedDict
import ctypes
from ctypes import wintypes
import hashlib
import json
import msvcrt
import os
from pathlib import Path
import secrets
import signal
import select
import socket
import subprocess
import sys
import threading
import time

import frida

ROOT = Path(__file__).resolve().parents[1]
_settings = ROOT / "config.local.json"
GAME = (Path(json.loads(_settings.read_text(encoding="utf8"))["game_executable"]).resolve()
        if _settings.exists() else ROOT / "game" / "PVZ-Scared.exe")
RUNTIME = ROOT / "runtime"


def process_path(pid: int) -> Path:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "Cannot inspect exact game process")
    try:
        buffer = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            raise OSError(ctypes.get_last_error(), "Cannot resolve game executable")
        return Path(buffer.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def verify_game() -> dict:
    profile = json.loads((ROOT / "profile.json").read_text(encoding="utf8"))
    for name, expected in profile["sha256"].items():
        with (GAME.parent / name).open("rb") as file:
            actual = hashlib.file_digest(file, "sha256").hexdigest()
        if actual != expected:
            raise RuntimeError(f"Unsupported game file: {name}; bridge was not loaded")
    return profile


def target_exited(pid: int) -> bool:
    """A detached Frida session alone does not prove that the game has exited."""
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        return ctypes.get_last_error() == 87  # PID no longer exists; other errors are inconclusive.
    try:
        return kernel.WaitForSingleObject(handle, 0) == 0
    finally:
        kernel.CloseHandle(handle)


def release_confirmed(response: dict) -> bool:
    if not isinstance(response, dict):
        return False
    state = response.get("result", {})
    if not isinstance(state, dict):
        return False
    return (response.get("ok") is True and state.get("selection_released") is True
            and state.get("controlled") is False and state.get("auto_collect") is False
            and state.get("held_os_inputs") == 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pid", type=int, help="Attach only to this exact local game executable")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--port", type=int, default=47633)
    args = parser.parse_args()
    RUNTIME.mkdir(exist_ok=True)
    lock = (RUNTIME / "controller.lock").open("a+b")
    lock.seek(0)
    if os.fstat(lock.fileno()).st_size == 0:
        lock.write(b"0")
        lock.flush()
    lock.seek(0)
    try:
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        raise SystemExit("A maintained horror bridge already owns this target")
    profile = verify_game()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    server.bind(("127.0.0.1", args.port))
    server.listen(1)
    server.settimeout(0.5)
    if args.launch:
        existing = [p for p in frida.get_local_device().enumerate_processes() if p.name.lower() == GAME.name.lower()]
        if existing:
            raise SystemExit("Game already running; use --pid for the verified process")
        process = subprocess.Popen([str(GAME), "-screen-fullscreen", "0", "-screen-width", "1100", "-screen-height", "700", "-logFile", str(RUNTIME / "player.log")], cwd=GAME.parent)
        args.pid = process.pid
        time.sleep(5)
    if not args.pid or process_path(args.pid) != GAME.resolve():
        raise SystemExit("--pid must resolve to the configured PVZ-Scared.exe")
    session = frida.attach(args.pid)
    session_id, token = secrets.token_hex(12), secrets.token_hex(32)
    source = "const PROFILE=" + json.dumps(profile, ensure_ascii=False) + ";\nconst SESSION=" + json.dumps(session_id) + ";\n"
    source += (ROOT / "src" / "bridge.js").read_text(encoding="utf8")
    source += "\n" + (ROOT / "src" / "story.js").read_text(encoding="utf8")
    script = session.create_script(source)
    run_directory = RUNTIME / ("run-" + session_id)
    run_directory.mkdir()
    log = (run_directory / "bridge.jsonl").open("a", encoding="utf8", buffering=1)

    def record(message, data=None):
        try:
            log.write(json.dumps({"time": time.time(), "message": message}, ensure_ascii=False) + "\n")
        except OSError as exc:
            print(f"Bridge log unavailable: {exc}", file=sys.stderr, flush=True)

    script.on("message", record)
    stop = threading.Event()
    ended = threading.Event()

    def on_detached(reason, *args):
        if reason == "process-terminated":
            ended.set()
        stop.set()

    session.on("detached", on_detached)
    signal.signal(signal.SIGINT, lambda *args: stop.set())
    signal.signal(signal.SIGTERM, lambda *args: stop.set())
    script.load()
    ready = script.exports_sync.request({"op": "capabilities"})
    if not ready.get("ok"):
        raise RuntimeError(ready)
    config = {"host": "127.0.0.1", "port": args.port, "token": token, "pid": args.pid,
              "game": "PVZ-Scared", "session_id": session_id, "executable": str(GAME),
              "host_pid": os.getpid(), "state": "ready"}
    config_file = RUNTIME / "connection.json"

    def publish_state(state):
        config["state"] = state
        pending = config_file.with_suffix(".tmp")
        pending.write_text(json.dumps(config, indent=2), encoding="utf8")
        pending.replace(config_file)

    publish_state("ready")

    def note_state(state):
        try:
            publish_state(state)
        except OSError as exc:
            record({"connection_state_write_failed": str(exc), "state": state})
    (run_directory / "session.json").write_text(json.dumps({"pid": args.pid, "session_id": session_id, "profile_sha256": hashlib.sha256((ROOT / "profile.json").read_bytes()).hexdigest()}), encoding="utf8")
    print(json.dumps({"ready": True, "pid": args.pid, "port": args.port, "config": str(config_file)}), flush=True)
    cache: OrderedDict[str, tuple[str, dict]] = OrderedDict()
    seen_ids: set[str] = set()
    purchase_file = RUNTIME / "purchases.json"
    purchases = json.loads(purchase_file.read_text(encoding="utf8")) if purchase_file.exists() else {}

    def persist_purchases():
        pending = purchase_file.with_suffix(".tmp")
        pending.write_text(json.dumps(purchases, ensure_ascii=True, allow_nan=False, indent=2), encoding="utf8")
        pending.replace(purchase_file)

    def execute(request, canonical):
        if request.get("op") == "purchase_receipt":
            key = request.get("purchase_id")
            result = purchases.get(key, {"status": "not_found"}) if isinstance(key, str) else list(purchases.values())[-20:]
            return {"ok": True, "result": result}
        if request.get("op") != "buy":
            return script.exports_sync.request(request)
        key = request["id"]
        if key in purchases:
            receipt = purchases[key]
            if receipt["canonical"] != canonical:
                raise ValueError("Purchase ID reused with a different payload")
            return receipt.get("response", {"ok": True, "result": {"purchase_id": key, "status": "unknown"}})
        purchases[key] = {"purchase_id": key, "status": "unknown", "canonical": canonical,
                          "game_pid": args.pid, "session_id": session_id, "created_at": time.time()}
        # This write precedes the irreversible native callback, so a lost reply cannot replay it.
        persist_purchases()
        response = script.exports_sync.request(request)
        purchases[key].update(status=response.get("result", {}).get("status", "unknown"), response=response)
        persist_purchases()
        return response

    def release_until_confirmed(dispose=False):
        blocked = False
        while True:
            try:
                response = (script.exports_sync.dispose() if dispose else
                            script.exports_sync.request({"op": "detach"}))
            except Exception as exc:
                # Transport failures also leave release unknown; they must not retire ownership.
                response = {"ok": False, "error": str(exc)}
            if release_confirmed(response):
                if blocked and not dispose and not stop.is_set():
                    note_state("ready")
                return response
            if ended.is_set() or target_exited(args.pid):
                stop.set()
                return {"ok": True, "result": {"target_exited": True, "selection_released": True,
                                               "controlled": False, "auto_collect": False, "held_os_inputs": 0}}
            if not blocked:
                note_state("release_blocked")
                record({"release_blocked": response})
                print("Native release unconfirmed; retaining controller lock and hooks. "
                      "Waiting for release or game exit.", file=sys.stderr, flush=True)
                blocked = True
            # Never accept a new client or unload the script while release is unproved.
            time.sleep(0.5)
    try:
        while not stop.is_set():
            if (RUNTIME / "stop.request").exists():
                stop.set()
                break
            try:
                peer, address = server.accept()
            except socket.timeout:
                continue
            peer.settimeout(15)
            try:
                with peer, peer.makefile("rb") as reader:
                    while not stop.is_set():
                        if (RUNTIME / "stop.request").exists():
                            stop.set()
                            break
                        if not select.select([peer], [], [], 0.5)[0]:
                            continue
                        line = reader.readline(1024 * 1024 + 1)
                        if not line:
                            break
                        request_id = None
                        try:
                            if len(line) > 1024 * 1024 or not line.endswith(b"\n"):
                                raise ValueError("Request too large or incomplete")
                            request = json.loads(line)
                            if not isinstance(request, dict):
                                raise ValueError("Request must be a JSON object")
                            candidate_id = request.get("id")
                            if not isinstance(candidate_id, str) or not candidate_id or len(candidate_id) > 128:
                                raise ValueError("A bounded request ID is required")
                            request_id = candidate_id
                            if not secrets.compare_digest(str(request.pop("token", "")), token):
                                raise ValueError("Authentication failed")
                            canonical = json.dumps(request, sort_keys=True, ensure_ascii=False, allow_nan=False)
                            if request_id in cache:
                                previous, response = cache[request_id]
                                if previous != canonical:
                                    raise ValueError("Request ID reused with a different payload")
                            else:
                                if request_id in seen_ids:
                                    raise ValueError("Old receipt evicted; outcome unknown, refusing replay")
                                if len(seen_ids) >= 100000:
                                    raise ValueError("Session request limit reached; retire at a released boundary")
                                seen_ids.add(request_id)
                                response = {"id": request_id, **execute(request, canonical)}
                                cache[request_id] = (canonical, response)
                                if len(cache) > 256:
                                    cache.popitem(last=False)
                                record({"request_id": request_id, "op": request.get("op"), "ok": response.get("ok"), "error": response.get("error")})
                        except (ValueError, TypeError, RecursionError, frida.InvalidOperationError, frida.RPCException) as exc:
                            response = {"id": request_id, "ok": False, "error": str(exc)}
                        peer.sendall((json.dumps(response, ensure_ascii=False, allow_nan=False) + "\n").encode("utf8"))
            except (OSError, UnicodeError) as exc:
                record({"disconnect": str(exc)})
            finally:
                # Disconnect must release native selection before accepting another controller.
                released = release_until_confirmed()
                record({"released": released})
    finally:
        try:
            note_state("stopping")
            release = release_until_confirmed(dispose=True)
            record({"shutdown": release})
            print(json.dumps({"stopped": True, "release": release}, ensure_ascii=False), flush=True)
        finally:
            server.close()
            if config_file.exists() and json.loads(config_file.read_text())["session_id"] == session_id:
                config_file.unlink()
            log.close()
            lock.close()
            # Frida detach can stall after a callback unhooks itself. All native
            # selections have been released before retiring the process.
            cleanup = threading.Thread(target=session.detach, daemon=True)
            cleanup.start()
            cleanup.join(3)
            if cleanup.is_alive():
                os._exit(0)


if __name__ == "__main__":
    main()
