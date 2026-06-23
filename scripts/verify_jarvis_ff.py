from __future__ import annotations

import argparse
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freefire_kill_sender import (  # noqa: E402
    FFQueueEntry,
    PlayerKill,
    derive_ff_queue_action_endpoint,
    derive_jarvis_endpoint,
    derive_kills_action_endpoint,
    fetch_ff_overlay_realtime,
    fetch_ff_queue_realtime,
    fetch_kills_realtime,
    parse_ff_queue_state,
    parse_realtime_state,
    send_ff_overlay_realtime_update,
    send_ff_queue_action_update,
    send_ff_queue_realtime_update,
    send_kills_action_update,
    send_kills_realtime_update,
)


class MockJarvisHandler(BaseHTTPRequestHandler):
    state: dict[str, dict[str, Any]] = {
        "kills": {"players": []},
        "queue": {"queue": []},
        "overlay": {"players": [], "queue": []},
    }
    headers_seen: dict[str, dict[str, str]] = {
        "kills": {},
        "queue": {},
        "overlay": {},
    }

    def log_message(self, *_args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        mode = str(payload.get("mode") or "")
        if self.path.rstrip("/").endswith("/freefire-kills/action"):
            self.headers_seen["kills"] = {key: value for key, value in self.headers.items()}
            player_name = str(payload.get("name") or "AizenVerify")
            player_kills = int(payload.get("kills") or 18)
            self.state["kills"] = {
                "ranking": [{"name": player_name, "kills": player_kills, "key": player_name.casefold()}],
                "daily_ranking": [{"name": player_name, "kills": player_kills, "key": player_name.casefold()}],
            }
            self._send_json({"ok": True, **self.state["kills"]})
            return
        if self.path.rstrip("/").endswith("/freefire-queue/action"):
            self.headers_seen["queue"] = {key: value for key, value in self.headers.items()}
            player_name = str(payload.get("name") or payload.get("display_name") or "AizenVerify")
            rooms = max(1, int(payload.get("rooms") or payload.get("credits") or 1))
            self.state["queue"] = {
                "mode": "ff_queue",
                "room": payload.get("room"),
                "queue": [{"name": player_name, "rooms": rooms, "credits": rooms, "user_id": "mock-user"}],
            }
            self._send_json({"ok": True, **self.state["queue"]})
            return
        if mode == "ff_queue":
            self.state["queue"] = payload
            self.headers_seen["queue"] = {key: value for key, value in self.headers.items()}
        elif mode == "ff_overlay":
            self.state["overlay"] = payload
            self.headers_seen["overlay"] = {key: value for key, value in self.headers.items()}
        else:
            self.state["kills"] = payload
            self.headers_seen["kills"] = {key: value for key, value in self.headers.items()}
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        if "freefire-overlay" in self.path or "mode=ff_overlay" in self.path:
            self._send_json(self.state["overlay"])
        elif "freefire-queue" in self.path or "mode=ff_queue" in self.path:
            self._send_json(self.state["queue"])
        else:
            self._send_json(self.state["kills"])


def start_mock_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockJarvisHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def config_value(config: dict[str, Any], key: str, fallback: str = "") -> str:
    return str(config.get(key) or fallback).strip()


def load_verify_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config nao encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def assert_mock_write_contract(
    panel: str,
    expected_mode: str,
    room: str,
    device_id: str,
    device_name: str,
    token: str,
) -> None:
    payload = MockJarvisHandler.state.get(panel, {})
    headers = MockJarvisHandler.headers_seen.get(panel, {})
    if str(payload.get("mode") or "") != expected_mode:
        raise RuntimeError(f"{panel}: mode divergente no POST: {payload.get('mode')!r}")
    if str(payload.get("room") or "") != room:
        raise RuntimeError(f"{panel}: room divergente no POST: {payload.get('room')!r}")
    if int(payload.get("sync_version") or 0) < 2:
        raise RuntimeError(f"{panel}: sync_version ausente ou antigo.")
    if str(payload.get("client_id") or "") != device_id:
        raise RuntimeError(f"{panel}: client_id divergente.")
    if str(payload.get("client_name") or "") != device_name:
        raise RuntimeError(f"{panel}: client_name divergente.")
    if str(payload.get("app_version") or "") == "":
        raise RuntimeError(f"{panel}: app_version ausente.")
    device = payload.get("device")
    if not isinstance(device, dict) or str(device.get("id") or "") != device_id:
        raise RuntimeError(f"{panel}: device.id ausente ou divergente.")
    if str(headers.get("X-Aizen-Client-Id") or "") != device_id:
        raise RuntimeError(f"{panel}: header X-Aizen-Client-Id divergente.")
    if str(headers.get("X-Aizen-Room") or "") != room:
        raise RuntimeError(f"{panel}: header X-Aizen-Room divergente.")
    if expected_mode != "manual" and str(headers.get("X-Aizen-Mode") or "") != expected_mode:
        raise RuntimeError(f"{panel}: header X-Aizen-Mode divergente.")
    if token and str(headers.get("X-Aizen-Token") or "") != token:
        raise RuntimeError(f"{panel}: header X-Aizen-Token divergente.")
    if panel == "overlay" and not isinstance(payload.get("options"), dict):
        raise RuntimeError("overlay: options ausente no POST.")


def verify_contracts() -> None:
    base_url = "https://jarvis.squareweb.app/admin"
    expected_endpoints = {
        "kills": "https://jarvis.squareweb.app/api/freefire-kills",
        "queue": "https://jarvis.squareweb.app/api/freefire-queue",
        "overlay": "https://jarvis.squareweb.app/api/freefire-overlay",
    }
    for panel, expected in expected_endpoints.items():
        actual = derive_jarvis_endpoint(base_url, panel)
        if actual != expected:
            raise RuntimeError(f"Endpoint {panel} divergente: {actual} != {expected}")
    if derive_jarvis_endpoint("https://jarvis.squareweb.app", "queue") != expected_endpoints["queue"]:
        raise RuntimeError("Derivacao por URL raiz falhou.")
    direct_overlay = derive_jarvis_endpoint("https://jarvis.squareweb.app/api/freefire-overlay", "overlay")
    if direct_overlay != expected_endpoints["overlay"]:
        raise RuntimeError(f"Derivacao por endpoint direto falhou: {direct_overlay}")
    direct_kills_to_queue = derive_jarvis_endpoint("https://jarvis.squareweb.app/api/freefire-kills", "queue")
    if direct_kills_to_queue != expected_endpoints["queue"]:
        raise RuntimeError(f"Derivacao entre endpoints falhou: {direct_kills_to_queue}")
    if derive_kills_action_endpoint(expected_endpoints["kills"]) != "https://jarvis.squareweb.app/api/freefire-kills/action":
        raise RuntimeError("Derivacao da action Kills FF falhou.")
    if derive_ff_queue_action_endpoint(expected_endpoints["queue"]) != "https://jarvis.squareweb.app/api/freefire-queue/action":
        raise RuntimeError("Derivacao da action Fila FF falhou.")

    kills_state = parse_realtime_state(
        {
            "ranking": [
                {"participantName": "Aizen", "score": "12"},
                {"displayName": "Jarvis", "points": 4},
            ],
            "ignored": [{"name": "Oculto", "key": "oculto", "ignored_at": 123}],
            "lastUpdatedBy": "Painel Jarvis",
            "onlineDevices": [{"name": "PC Live"}],
        }
    )
    if [(item.name, item.kills) for item in kills_state.players] != [("Aizen", 12), ("Jarvis", 4)]:
        raise RuntimeError(f"Parser Kills FF divergente: {kills_state.players!r}")
    if kills_state.updated_by != "Painel Jarvis" or not kills_state.devices:
        raise RuntimeError("Metadados Kills FF nao foram lidos.")
    if not kills_state.ignored_players or kills_state.ignored_players[0].name != "Oculto":
        raise RuntimeError(f"Ignorados Kills FF nao foram lidos: {kills_state.ignored_players!r}")

    queue_state = parse_ff_queue_state(
        {
            "fila": [
                {"playerName": "Aizen", "room": "squad", "status": "playing", "quantity": 2},
                {"username": "Jarvis", "sala": "duo", "called": True},
            ],
            "sourceName": "Site Jarvis",
        }
    )
    expected_queue = [
        ("Aizen", "squad", "Jogando", 2),
        ("Jarvis", "duo", "Chamado", 1),
    ]
    if [(item.name, item.note, item.status, item.rooms) for item in queue_state.entries] != expected_queue:
        raise RuntimeError(f"Parser Fila FF divergente: {queue_state.entries!r}")
    if queue_state.updated_by != "Site Jarvis":
        raise RuntimeError("Metadados Fila FF nao foram lidos.")

    overlay_kills = parse_realtime_state({"players": [{"username": "Overlay", "total": 9}]})
    overlay_queue = parse_ff_queue_state({"queue": [{"participant": "Overlay", "phase": "waiting"}]})
    if [(item.name, item.kills) for item in overlay_kills.players] != [("Overlay", 9)]:
        raise RuntimeError(f"Parser Overlay/Kills divergente: {overlay_kills.players!r}")
    if [(item.name, item.status, item.rooms) for item in overlay_queue.entries] != [("Overlay", "Na fila", 1)]:
        raise RuntimeError(f"Parser Overlay/Fila divergente: {overlay_queue.entries!r}")

    print("Contratos Jarvis FF OK: endpoints e parsers locais validados.")


def verify(
    base_url: str,
    token: str,
    room: str,
    device_id: str,
    device_name: str,
    overlay_required: bool,
    kills_url: str = "",
    queue_url: str = "",
    overlay_url: str = "",
) -> None:
    kills_url = kills_url or derive_jarvis_endpoint(base_url, "kills")
    queue_url = queue_url or derive_jarvis_endpoint(base_url, "queue")
    overlay_url = overlay_url or derive_jarvis_endpoint(base_url, "overlay")
    print(f"Kills FF endpoint: {kills_url}")
    print(f"Fila FF endpoint: {queue_url}")
    print(f"Overlay FF endpoint: {overlay_url}")
    if base_url.rstrip("/").endswith("/api/freefire-overlay") and not overlay_url.endswith("/api/freefire-overlay"):
        raise RuntimeError(f"Derivacao de overlay invalida: {overlay_url}")

    players = [PlayerKill("AizenVerify", 17), PlayerKill("JarvisVerify", 5)]
    queue = [
        FFQueueEntry("AizenVerify", "squad", "Jogando"),
        FFQueueEntry("JarvisVerify", "duo", "Chamado"),
    ]

    send_kills_realtime_update(kills_url, "Kills da partida", players, device_id, device_name, room, token)
    if kills_url.startswith("http://127.0.0.1:"):
        assert_mock_write_contract("kills", "manual", room, device_id, device_name, token)
    fetched_kills = fetch_kills_realtime(kills_url, device_id, device_name, room, token)
    if [(item.name, item.kills) for item in fetched_kills.players] != [(item.name, item.kills) for item in players]:
        raise RuntimeError(f"Kills FF divergente: {fetched_kills.players!r}")
    if kills_url.startswith("http://127.0.0.1:"):
        action_state = send_kills_action_update(
            kills_url,
            "set",
            PlayerKill("AizenVerify", 18, key="aizenverify"),
            kills=18,
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not action_state.daily_ranking or action_state.daily_ranking[0].kills != 18:
            raise RuntimeError(f"Action Kills FF divergente: {action_state.daily_ranking!r}")

    send_ff_queue_realtime_update(queue_url, queue, device_id, device_name, room, token)
    if queue_url.startswith("http://127.0.0.1:"):
        assert_mock_write_contract("queue", "ff_queue", room, device_id, device_name, token)
    fetched_queue = fetch_ff_queue_realtime(queue_url, device_id, device_name, room, token)
    if [(item.name, item.note, item.status, item.rooms) for item in fetched_queue.entries] != [
        (item.name, item.note, item.status, item.rooms) for item in queue
    ]:
        raise RuntimeError(f"Fila FF divergente: {fetched_queue.entries!r}")
    if queue_url.startswith("http://127.0.0.1:"):
        action_queue = send_ff_queue_action_update(
            queue_url,
            "add_credit",
            FFQueueEntry("AizenVerify", rooms=3, user_id="mock-user"),
            credits=3,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not action_queue.entries or action_queue.entries[0].rooms != 3:
            raise RuntimeError(f"Action Fila FF divergente: {action_queue.entries!r}")

    try:
        send_ff_overlay_realtime_update(
            overlay_url,
            players,
            queue,
            {"compact": False, "show_kills": True, "show_queue": True},
            device_id,
            device_name,
            room,
            token,
        )
        if overlay_url.startswith("http://127.0.0.1:"):
            assert_mock_write_contract("overlay", "ff_overlay", room, device_id, device_name, token)
        overlay_kills, overlay_queue = fetch_ff_overlay_realtime(overlay_url, device_id, device_name, room, token)
        if [(item.name, item.kills) for item in overlay_kills.players] != [(item.name, item.kills) for item in players]:
            raise RuntimeError(f"Overlay FF/Kills divergente: {overlay_kills.players!r}")
        if [(item.name, item.note, item.status, item.rooms) for item in overlay_queue.entries] != [
            (item.name, item.note, item.status, item.rooms) for item in queue
        ]:
            raise RuntimeError(f"Overlay FF/Fila divergente: {overlay_queue.entries!r}")
        print("Overlay FF GET aplicavel: endpoint retornou players e queue no mesmo payload.")
    except Exception:
        if overlay_required:
            raise
        print("Overlay FF opcional nao respondeu; Kills FF e Fila FF foram validados.")
        return

    print("Jarvis FF OK: Kills FF, Fila FF e Overlay FF validados.")


def verify_read_only(
    base_url: str,
    token: str,
    room: str,
    device_id: str,
    device_name: str,
    overlay_required: bool,
    kills_url: str = "",
    queue_url: str = "",
    overlay_url: str = "",
) -> None:
    kills_url = kills_url or derive_jarvis_endpoint(base_url, "kills")
    queue_url = queue_url or derive_jarvis_endpoint(base_url, "queue")
    overlay_url = overlay_url or derive_jarvis_endpoint(base_url, "overlay")
    print(f"Kills FF endpoint: {kills_url}")
    print(f"Fila FF endpoint: {queue_url}")
    print(f"Overlay FF endpoint: {overlay_url}")

    kills_state = fetch_kills_realtime(kills_url, device_id, device_name, "", token)
    queue_state = fetch_ff_queue_realtime(queue_url, device_id, device_name, room, token)
    kills_count = kills_state.total_players if kills_state.total_players is not None else len(kills_state.players)
    kills_total = kills_state.total_kills if kills_state.total_kills is not None else sum(player.kills for player in kills_state.players)
    print(f"Kills FF GET OK: {kills_count} jogador(es), {kills_total} kill(s).")
    print(f"Fila FF GET OK: {len(queue_state.entries)} item(ns).")

    try:
        overlay_kills, overlay_queue = fetch_ff_overlay_realtime(overlay_url, device_id, device_name, room, token)
    except Exception:
        if overlay_required:
            raise
        print("Overlay FF GET opcional nao respondeu; Kills FF e Fila FF foram lidos.")
        return

    print(
        "Overlay FF GET OK: "
        f"{len(overlay_kills.players)} jogador(es), {len(overlay_queue.entries)} item(ns) de fila."
    )
    print("Jarvis FF read-only OK: endpoints configurados responderam sem escrita.")


def print_resolved_endpoints(base_url: str, kills_url: str = "", queue_url: str = "", overlay_url: str = "") -> None:
    kills_url = kills_url or derive_jarvis_endpoint(base_url, "kills")
    queue_url = queue_url or derive_jarvis_endpoint(base_url, "queue")
    overlay_url = overlay_url or derive_jarvis_endpoint(base_url, "overlay")
    if not kills_url or not queue_url:
        raise RuntimeError("nao foi possivel resolver Kills FF e Fila FF.")
    print(f"Kills FF endpoint: {kills_url}")
    print(f"Fila FF endpoint: {queue_url}")
    print(f"Overlay FF endpoint: {overlay_url}")
    print("Jarvis FF endpoints resolvidos sem rede.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida os contratos Jarvis FF usados pelo Aizen Stream Control.")
    parser.add_argument("--base-url", default="", help="URL base do Jarvis, por exemplo https://jarvis.squareweb.app")
    parser.add_argument("--config", type=Path, default=None, help="Lê URL/token/sala de um config.json do app.")
    parser.add_argument("--token", default="", help="Token Jarvis enviado em X-Aizen-Token.")
    parser.add_argument("--room", default="principal", help="Sala usada nos endpoints.")
    parser.add_argument("--device-id", default="verify-script", help="ID do cliente de teste.")
    parser.add_argument("--device-name", default="Aizen Verify", help="Nome do cliente de teste.")
    parser.add_argument("--mock", action="store_true", help="Sobe um servidor local fake e valida contra ele.")
    parser.add_argument("--require-overlay", action="store_true", help="Falha se /api/freefire-overlay nao responder.")
    parser.add_argument("--read-only", action="store_true", help="Valida apenas GET, sem enviar dados de teste.")
    parser.add_argument("--resolve-only", action="store_true", help="Mostra endpoints resolvidos sem acessar a rede.")
    parser.add_argument("--contracts", action="store_true", help="Valida derivacao de endpoints e parsers locais sem rede.")
    args = parser.parse_args()

    if args.contracts:
        try:
            verify_contracts()
            return 0
        except Exception as exc:
            print(f"Contratos Jarvis FF falharam: {exc}", file=sys.stderr)
            return 1

    server: ThreadingHTTPServer | None = None
    base_url = args.base_url
    kills_url = ""
    queue_url = ""
    overlay_url = ""
    token = args.token
    room = args.room
    device_id = args.device_id
    device_name = args.device_name
    if args.config is not None:
        config = load_verify_config(args.config)
        base_url = base_url or config_value(config, "jarvis_base_url")
        kills_url = config_value(config, "kills_realtime_url", config_value(config, "jarvis_endpoint_url"))
        queue_url = config_value(config, "ff_queue_realtime_url")
        overlay_url = config_value(config, "ff_overlay_realtime_url")
        token = token or config_value(config, "jarvis_api_token")
        room = args.room if args.room != "principal" else config_value(config, "kills_sync_room", "principal")
        device_id = args.device_id if args.device_id != "verify-script" else config_value(config, "device_id", "verify-script")
        device_name = args.device_name if args.device_name != "Aizen Verify" else config_value(config, "device_name", "Aizen Verify")
    if args.mock:
        server, base_url = start_mock_server()
    if not base_url and not (kills_url and queue_url):
        parser.error("informe --base-url, use --config com endpoints, ou use --mock")

    try:
        if args.resolve_only:
            print_resolved_endpoints(base_url, kills_url=kills_url, queue_url=queue_url, overlay_url=overlay_url)
            return 0
        verifier = verify_read_only if args.read_only else verify
        verifier(
            base_url,
            token,
            room,
            device_id,
            device_name,
            args.require_overlay or args.mock,
            kills_url=kills_url,
            queue_url=queue_url,
            overlay_url=overlay_url,
        )
        return 0
    except Exception as exc:
        print(f"Jarvis FF falhou: {exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None:
            server.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
