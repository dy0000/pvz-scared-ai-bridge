"""Bounded first-level integration check; operates the real game through its bridge."""
from pathlib import Path
import json
import time
import uuid

from client import HorrorClient

ROOT = Path(__file__).resolve().parents[1]


def main():
    directory = ROOT / "evidence" / (time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    directory.mkdir(parents=True)
    records = []

    def log(name, response):
        records.append({"name": name, "response": response})
        (directory / "live.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf8")
        print(name, json.dumps(response, ensure_ascii=False)[:600], flush=True)
        return response

    with HorrorClient() as game:
        def request(op, **args):
            r = game.request(op, **args)
            if not r.get("ok"):
                raise RuntimeError(r)
            return r["result"]

        def wait_phase(expected, seconds=15):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                s = request("observe")
                if s["phase"] in expected:
                    return s
                time.sleep(0.25)
            raise RuntimeError("Native transition timeout: " + s["phase"])

        try:
            s = request("attach")
            if s["phase"] == "moving":
                s = wait_phase({"diary", "selection", "running"})
            if s["phase"] == "defeat":
                menu = request("menu")
                if not any(t.get("text") == "游戏结束" for t in menu["texts"]):
                    raise RuntimeError("Retry dialog identity not verified")
                action = next(a for a in menu["actions"] if a["native_class"] == "DialogBtn")
                log("native_retry", request("menu_action", menu_id=menu["menu_id"], action_id=action["action_id"]))
                s = wait_phase({"diary", "selection"})
            if s["phase"] == "diary":
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    menu = request("menu")
                    action = next((a for a in menu["actions"] if a["label"] == "Skip"), None)
                    if action:
                        break
                    time.sleep(.25)
                if not action:
                    raise RuntimeError("Diary transition did not enable skip")
                request("menu_action", menu_id=menu["menu_id"], action_id=action["action_id"])
                s = wait_phase({"selection"})
            if s["phase"] == "selection":
                for name in ("PeaShooter", "SunFlower", "Wallnut", "PotatoMine", "CherryBomb", "Squash"):
                    card = next(c for c in s["cards"] if c["plant_name"] == name)
                    log("select_" + name, request("choose_card", battle_id=s["battle_id"], card_id=card["card_id"], selected=True))
                log("start", request("start_battle", battle_id=s["battle_id"]))
                s = wait_phase({"running"})
            if s["phase"] != "running":
                raise RuntimeError("Check requires the first normal battle")
            bid = s["battle_id"]
            pea = next(c for c in s["cards"] if c["plant_name"] == "PeaShooter")
            # One committed request is replayed with the SAME ID, through the transport.
            req = {"id": uuid.uuid4().hex, "token": game.token, "op": "plant", "battle_id": bid,
                   "card_id": pea["card_id"], "row": 3, "column": 2}
            payload = (json.dumps(req) + "\n").encode()
            game.socket.sendall(payload)
            planted = json.loads(game.reader.readline())
            log("plant", planted)
            assert planted["ok"] and planted["result"]["status"] == "Committed", planted
            assert planted["result"]["sun_before"] - planted["result"]["sun_after"] == pea["cost"]
            assert planted["result"]["card"]["cooldown"] > 0
            game.socket.sendall(payload)
            duplicate = json.loads(game.reader.readline())
            assert duplicate == planted
            log("same_id_cached_once", {"equal": True})
            rejection = request("plant", battle_id=bid, card_id=pea["card_id"], row=2, column=2)
            assert rejection["status"] == "rejected"
            log("cooldown_rejection", rejection)
            for name, args in [("bounds", {"battle_id": bid, "card_id": pea["card_id"], "row": 0, "column": 1}),
                               ("stale_battle", {"battle_id": "stale", "card_id": pea["card_id"], "row": 1, "column": 1})]:
                rejected = game.request("plant", **args)
                assert not rejected["ok"]
                log(name, rejected)
            s = request("observe")
            assert len([p for p in s["plants"] if p["content_type"] == pea["plant_type"] and p["row"] == 3 and p["column"] == 2]) == 1
            log("plant_postcondition", {"sun": s["sun"], "wave": s["wave"], "max_wave": s["max_wave"], "native_selection": s["native_selection"]})
            deadline = time.monotonic() + 15
            while not s["suns"] and time.monotonic() < deadline:
                time.sleep(0.2)
                s = request("observe")
            if not s["suns"]:
                raise RuntimeError("No natural collectible observed")
            item, sun_before = s["suns"][0], s["sun"]
            log("collect", request("collect", battle_id=bid, sun_ids=[item["sun_id"]]))
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                time.sleep(0.2)
                s = request("observe")
                if s["sun"] >= sun_before + item["value"] and not any(x["sun_id"] == item["sun_id"] for x in s["suns"]):
                    break
            else:
                raise RuntimeError("Normal collection animation credit not observed")
            log("collection_credit", {"sun_before": sun_before, "sun_after": s["sun"], "value": item["value"]})
            log("auto_collect_on", request("auto_collect", battle_id=bid, enabled=True))
            time.sleep(0.25)
            log("auto_collect_off", request("auto_collect", battle_id=bid, enabled=False))
            menu = request("menu")
            action = next(a for a in menu["actions"] if a["kind"] == "in_game_menu")
            log("pause_menu", request("menu_action", menu_id=menu["menu_id"], action_id=action["action_id"]))
            s = wait_phase({"paused"}, 3)
            log("paused", {"phase": s["phase"], "sun": s["sun"]})
        finally:
            released = game.request("detach")
            log("release", released)
            assert released.get("ok") and not released["result"]["controlled"] and released["result"]["native_selection"] == 0
    (directory / "summary.json").write_text(json.dumps({"passed": True, "scope": "first normal level native bridge; no victory/special-mode claim", "checks": [x["name"] for x in records]}, ensure_ascii=False, indent=2), encoding="utf8")
    print("EVIDENCE", directory, flush=True)


if __name__ == "__main__":
    main()
