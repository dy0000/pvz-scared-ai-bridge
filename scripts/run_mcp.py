"""MCP stdio adapter for the separate local horror bridge. No action retries."""
from __future__ import annotations

import json
import math
import sys

from client import HorrorClient


def schema(properties=None, required=()):
    return {"type": "object", "properties": properties or {}, "required": list(required), "additionalProperties": False}


def tool(name, description, op, properties=None, required=()):
    return {"name": "pvzh_" + name, "description": description, "inputSchema": schema(properties, required), "_op": op}


STRING = {"type": "string", "minLength": 1}
BATTLE = {"battle_id": STRING}
TOOLS = [
    tool("capabilities", "Read the actual supported operations of the pinned PVZ-Scared native bridge.", "capabilities"),
    tool("observe", "Read native battle phase, sun, waves, card costs/remaining cooldowns, plants and live zombies. IDs belong to the current bridge session and battle.", "observe"),
    tool("menu", "Read active native menu actions and game text. Use the new menu_id/action_id; never invent identifiers.", "menu"),
    tool("take_control", "Take the unique controller in realtime; F8/F9 player lock can only be reset by F10 in game.", "attach"),
    tool("release_control", "Release AI selection and auto-collection. Leaves normal game progression unchanged.", "detach"),
    tool("stop", "Immediately release this AI session and stop its automation.", "stop"),
    tool("menu_action", "Activate one observed native menu action. navigation_requested needs a subsequent menu/phase observation. New profile uses normal native input and confirmation. Purchases are excluded.", "menu_action",
         {"menu_id": STRING, "action_id": STRING, "name": {"type": "string", "pattern": "^[A-Za-z0-9_-]{1,24}$"}}, ("menu_id", "action_id")),
    tool("choose_card", "Select/deselect one current native card candidate, preserving game locks and capacity.", "choose_card",
         {**BATTLE, "card_id": STRING, "selected": {"type": "boolean"}}, ("battle_id", "card_id")),
    tool("start_battle", "Use the native start button from card selection; observe until running.", "start_battle", BATTLE, ("battle_id",)),
    tool("plant", "Plant an observed bank, conveyor or falling card at a 1-based row/column on the current board. Uses native placement, sun deduction and cooldown. Only Committed confirms a new matching plant. Never replay an unknown outcome.", "plant",
         {**BATTLE, "card_id": STRING, "row": {"type": "integer", "minimum": 1}, "column": {"type": "integer", "minimum": 1}}, ("battle_id", "card_id", "row", "column")),
    tool("collect", "Start native collection animation for explicit observed collectible IDs. Observe later for credited sun.", "collect",
         {**BATTLE, "sun_ids": {"type": "array", "items": STRING, "minItems": 1, "maxItems": 128}}, ("battle_id", "sun_ids")),
    tool("auto_collect", "Enable/disable normal sun pickup in the current battle. Releases on disconnect, detach, player stop or battle change.", "auto_collect",
         {**BATTLE, "enabled": {"type": "boolean"}}, ("battle_id", "enabled")),
    tool("game_info", "Read native story progress, money, settings and level mechanics. Optional level reads that story level's configuration. inspect_class reads native type metadata for bridge diagnostics without a second injection session.", "game_info", {"level":{"type":"integer","minimum":1},"inspect_class":STRING}),
    tool("shovel", "Use the native shovel on one observed plant, preserving game restrictions.", "shovel", {**BATTLE,"entity_id":STRING}, ("battle_id","entity_id")),
    tool("move_plant", "Use the native glove to move one observed plant to a 1-based cell. Native cooldown and placement rules apply.", "move_plant", {**BATTLE,"entity_id":STRING,"row":{"type":"integer","minimum":1},"column":{"type":"integer","minimum":1}}, ("battle_id","entity_id","row","column")),
    tool("interact", "Perform the native primary click on an observed entity, cell, or explicit world x/y for plant abilities and special targets. Observe the resulting game state.", "interact", {**BATTLE,"entity_id":STRING,"row":{"type":"integer","minimum":1},"column":{"type":"integer","minimum":1},"x":{"type":"number"},"y":{"type":"number"}}, ("battle_id",)),
    tool("set_slow", "Enable or disable the game's native slow-motion control.", "set_slow", {**BATTLE,"enabled":{"type":"boolean"}}, ("battle_id","enabled")),
    tool("set_speed", "Set game speed through the native speed slider; the game clamps its allowed range.", "set_speed", {"speed":{"type":"number"}}, ("speed",)),
    tool("set_paused", "Pause or resume through the native battle menu.", "set_paused", {**BATTLE,"paused":{"type":"boolean"}}, ("battle_id","paused")),
    tool("set_difficulty", "Select and apply a native easy/normal/hard/nightmare preset from the difficulty menu. Native unlocks apply.", "set_difficulty", {"preset":{"type":"string","enum":["easy","normal","hard","nightmare"]}}, ("preset",)),
    tool("rewards", "Read live victory rewards and event cards, including their native names and descriptions.", "rewards"),
    tool("collect_reward", "Collect an observed native victory reward once. Observe the resulting scene; never replay an unknown outcome.", "collect_reward", {**BATTLE,"reward_id":STRING}, ("battle_id","reward_id")),
    tool("choose_event", "Click an observed native victory event card through its own button listener. Read rewards again after the animation. Available even when the victory scene has retired the battle.", "choose_event", {**BATTLE,"event_id":STRING}, ("event_id",)),
    tool("next_level", "Advance one native story-navigation step to the current unlocked level. Finish rewards and events first, then observe the resulting menu or battle.", "next_level"),
    tool("almanac", "Read the native almanac entries currently displayed and their text.", "almanac"),
    tool("almanac_select", "Open an observed plant or zombie almanac entry.", "almanac_select", {"entry_id":STRING,"kind":{"type":"string","enum":["plant","zombie"]}}, ("entry_id","kind")),
    tool("store", "Read the native store's displayed products, descriptions, prices and coin balance.", "store"),
    tool("buy", "Buy one displayed native store product directly using in-game coins. No extra approval flow; native prices, balance and locks apply. An unknown outcome must not be retried; query purchase_receipt.", "buy", {"product_id":STRING}, ("product_id",)),
    tool("purchase_receipt", "Read a persisted purchase receipt, or the most recent receipts when purchase_id is omitted. Pending/unknown never authorizes replay.", "purchase_receipt", {"purchase_id":STRING}),
    tool("ui_controls", "Read active native sliders, toggles, text fields and dropdowns with control IDs, values and hierarchy paths.", "ui_controls"),
    tool("set_ui_value", "Set an observed native UI control through its real callback: settings, speed, difficulty inputs and dropdowns use the game's own range and behavior.", "set_ui_value", {"control_id":STRING,"kind":{"type":"string","enum":["slider","toggle","input","dropdown"]},"value":{"type":["string","number","boolean"]}}, ("control_id","kind","value")),
    tool("test_assist", "Explicit testing cheat: lower live hostile health and invoke native damage/death callbacks; optionally accelerate ordinary waves. Use for user-authorized acceptance fixtures, and report assisted results separately from normal gameplay.", "test_assist", {**BATTLE,"scope":{"type":"string","enum":["mobs","all"]},"advance_waves":{"type":"boolean"}}, ("battle_id",)),
]


def main():
    client = None
    try:
        for line in sys.stdin:
            request_id = None
            error_code = -32700
            try:
                request = json.loads(line)
                error_code = -32600
                if not isinstance(request, dict):
                    raise ValueError("MCP request must be a JSON object")
                candidate_id = request.get("id")
                if "id" in request:
                    if (isinstance(candidate_id, bool) or not isinstance(candidate_id, (str, int, float))
                            or isinstance(candidate_id, float) and not math.isfinite(candidate_id)):
                        raise ValueError("Invalid MCP request ID")
                    request_id = candidate_id
                method = request.get("method")
                if (request.get("jsonrpc") != "2.0" or not isinstance(method, str)
                        or not isinstance(request.get("params", {}), dict)):
                    raise ValueError("Invalid MCP request envelope")
                if "id" not in request:
                    continue  # Valid notifications never receive replies or invoke request tools.
                error_code = -32603
                if method == "initialize":
                    result = {"protocolVersion": request.get("params", {}).get("protocolVersion", "2024-11-05"),
                              "capabilities": {"tools": {}}, "serverInfo": {"name": "pvz-scared-native", "version": "0.2.2"}}
                elif method == "tools/list":
                    result = {"tools": [{k: v for k, v in t.items() if k != "_op"} for t in TOOLS]}
                elif method == "tools/call":
                    params = request.get("params", {})
                    tool = next(t for t in TOOLS if t["name"] == params["name"])
                    args = params.get("arguments", {})
                    if not isinstance(args, dict) or set(args) - set(tool["inputSchema"]["properties"]) or set(tool["inputSchema"]["required"]) - set(args):
                        raise ValueError("Invalid tool arguments")
                    if client is None:
                        client = HorrorClient()
                    try:
                        response = client.request(tool["_op"], **args)
                    except Exception:
                        client.close()
                        client = None
                        raise
                    result = {"content": [{"type": "text", "text": json.dumps(response, ensure_ascii=False)}], "isError": not response.get("ok", False)}
                elif method == "ping":
                    result = {}
                else:
                    raise ValueError("Unsupported MCP method")
                reply = {"jsonrpc": "2.0", "id": request_id, "result": result}
                encoded = json.dumps(reply, ensure_ascii=True, allow_nan=False)
            except Exception as exc:
                reply = {"jsonrpc": "2.0", "id": request_id, "error": {"code": error_code, "message": str(exc) + "; no automatic action retry"}}
                encoded = json.dumps(reply, ensure_ascii=True, allow_nan=False)
            print(encoded, flush=True)
    finally:
        if client:
            try:
                client.request("detach")
            finally:
                client.close()


if __name__ == "__main__":
    main()
