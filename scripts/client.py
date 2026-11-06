"""One request or a persistent client for the separate horror bridge."""
from pathlib import Path
import json
import socket
import uuid

CONFIG = Path(__file__).resolve().parents[1] / "runtime" / "connection.json"


class HorrorClient:
    def __init__(self):
        config = json.loads(CONFIG.read_text(encoding="utf8"))
        if config["host"] != "127.0.0.1" or config["game"] != "PVZ-Scared":
            raise RuntimeError("Wrong bridge target")
        self.token = config["token"]
        self.socket = socket.create_connection((config["host"], config["port"]), timeout=15)
        self.reader = self.socket.makefile("rb")

    def request(self, op, **args):
        request_id = uuid.uuid4().hex
        data = {"id": request_id, "token": self.token, "op": op, **args}
        try:
            self.socket.sendall((json.dumps(data, ensure_ascii=False, allow_nan=False) + "\n").encode("utf8"))
            line = self.reader.readline(8 * 1024 * 1024 + 1)
        except OSError as exc:
            self.close()
            raise RuntimeError("Connection interrupted; action outcome unknown. Reconnect and observe, never replay automatically.") from exc
        if not line or len(line) > 8 * 1024 * 1024 or not line.endswith(b"\n"):
            raise RuntimeError("Outcome unknown; do not replay the action")
        response = json.loads(line)
        if response.get("id") != request_id:
            raise RuntimeError("Response mismatch; do not replay the action")
        return response

    def close(self):
        self.reader.close()
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


if __name__ == "__main__":
    import sys
    with HorrorClient() as game:
        args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        print(json.dumps(game.request(sys.argv[1] if len(sys.argv) > 1 else "observe", **args), ensure_ascii=False, indent=2))
