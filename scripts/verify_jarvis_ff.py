from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from freefire_kill_sender import (  # noqa: E402
    FFQueueEntry,
    chat_command_token,
    cleanup_stale_pyinstaller_dirs,
    complete_player_names_from_references,
    derive_ff_overlay_config_endpoint,
    PlayerKill,
    derive_ff_queue_action_endpoint,
    derive_jarvis_endpoint,
    derive_kills_action_endpoint,
    derive_kills_rank_endpoint,
    derive_kills_style_endpoint,
    derive_tikfinity_ff_gifts_endpoint,
    fetch_ff_overlay_realtime,
    fetch_ff_overlay_config,
    fetch_ff_queue_realtime,
    fetch_kills_style,
    fetch_kills_realtime,
    fetch_tikfinity_ff_gifts,
    is_live_chat_event_payload,
    kills_scope_label,
    merge_ff_queue_entries,
    normalize_live_chat_payload,
    normalize_chat_command,
    normalize_kills_scope_value,
    overlay_rank_players,
    parse_ff_queue_state,
    parse_realtime_state,
    player_wire_payload,
    response_acknowledges_kills_snapshot,
    send_ff_overlay_realtime_update,
    send_ff_overlay_config_action,
    send_ff_queue_action_update,
    send_ff_queue_realtime_update,
    send_kills_action_update,
    send_kills_snapshot_update,
    send_kills_style_update,
    send_kills_realtime_update,
    send_tikfinity_ff_gifts_action,
    serve_next_queue_entries,
    write_text_if_changed,
)


class MockJarvisHandler(BaseHTTPRequestHandler):
    state: dict[str, dict[str, Any]] = {
        "kills": {"ranking": [], "daily_ranking": [], "ignored": {}},
        "kills_rank": {},
        "kills_style": {"style": {"title_text": "TOP KILLS", "font_family": "impact", "row_size": 26}},
        "queue": {"queue": []},
        "overlay": {"players": [], "queue": []},
        "overlay_config": {
            "profile": "streamer1",
            "profile_label": "Streamer 1",
            "profiles": [{"id": "streamer1", "label": "Streamer 1"}],
            "overlay_url": "",
            "config": {
                "enabled_general": True,
                "enabled_daily": True,
                "enabled_queue": True,
                "layout": "horizontal",
                "font_family": "impact",
                "animation": "slide",
                "refresh_ms": 2500,
                "switch_seconds": 10,
                "gap": 14,
                "wrap_padding": 8,
                "panel_width": 360,
                "panel_bg_enabled": True,
                "panel_bg_color": "#05070D",
                "panel_bg_opacity": 48,
                "panel_radius": 10,
                "row_bg_color": "#000000",
                "row_bg_opacity": 28,
                "accent_width": 4,
                "title_size": 30,
                "row_size": 22,
                "value_size": 24,
                "row_height": 40,
                "limit_general": 10,
                "limit_daily": 10,
                "limit_queue": 8,
                "general": {
                    "title": "TOP KILLS GERAL",
                    "title_color": "#FFD54A",
                    "rank_color": "#FFD54A",
                    "name_color": "#FFFFFF",
                    "value_color": "#66FF99",
                    "accent_color": "#FF4655",
                },
                "daily": {
                    "title": "TOP KILLS DIA",
                    "title_color": "#66FF99",
                    "rank_color": "#66FF99",
                    "name_color": "#FFFFFF",
                    "value_color": "#FFD54A",
                    "accent_color": "#24D17E",
                },
                "queue": {
                    "title": "FILA FF",
                    "title_color": "#7AD7FF",
                    "rank_color": "#7AD7FF",
                    "name_color": "#FFFFFF",
                    "value_color": "#FFD54A",
                    "accent_color": "#3BA7FF",
                },
            },
        },
        "tikfinity": {
            "config": {"enabled": True, "coins_per_room": 50, "token_configured": True},
            "mappings": [],
            "users": [
                {
                    "user_id": "mock-user",
                    "social_user": "aizen",
                    "display_name": "Aizen",
                    "total_coins": 150,
                    "pending_coins": 0,
                    "rooms_added": 3,
                }
            ],
            "history": [{"social_user": "aizen", "display_name": "Aizen", "coins_added": 150, "ff_room_credits_added": 3}],
            "profile": "streamer1",
            "webhook_url": "",
        },
        "debug": {"kills_actions": []},
    }
    headers_seen: dict[str, dict[str, str]] = {
        "kills": {},
        "kills_style": {},
        "queue": {},
        "overlay": {},
        "overlay_config": {},
        "tikfinity": {},
    }

    def log_message(self, *_args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
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
            action = str(payload.get("action") or "")
            scope = str(payload.get("scope") or "both").strip().lower()
            if scope not in {"general", "daily", "both"}:
                scope = "both"
            self.state.setdefault("debug", {}).setdefault("kills_actions", []).append(action)
            if action == "replace" and self.state.get("debug", {}).get("reject_snapshot"):
                self._send_json({"ok": False, "error": "snapshot unsupported in mock"}, status=422)
                return

            def clean_key(value: Any) -> str:
                return " ".join(str(value or "").strip().casefold().split())

            def player_row(item: PlayerKill) -> dict[str, Any]:
                return {
                    "name": item.name,
                    "kills": int(item.kills),
                    "key": item.key or clean_key(item.name),
                    "ff_player_id": item.ff_player_id,
                    "entries": int(item.entries or 0),
                }

            parsed_state = parse_realtime_state(self.state.get("kills") or {})
            ranking_rows = [player_row(player) for player in (parsed_state.global_ranking or parsed_state.players or [])]
            daily_rows = [player_row(player) for player in (parsed_state.daily_ranking or [])]
            ignored_rows = {
                (item.key or clean_key(item.name)): {"name": item.name, "key": item.key or clean_key(item.name)}
                for item in (parsed_state.ignored_players or [])
            }

            def sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
                return sorted(rows, key=lambda row: (-int(row.get("kills") or 0), clean_key(row.get("name"))))

            def find_row(rows: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
                for row in rows:
                    if key and key in {clean_key(row.get("key")), clean_key(row.get("name"))}:
                        return row
                return None

            def target_rows() -> list[tuple[str, list[dict[str, Any]]]]:
                targets: list[tuple[str, list[dict[str, Any]]]] = []
                if scope in {"general", "both"}:
                    targets.append(("general", ranking_rows))
                if scope in {"daily", "both"}:
                    targets.append(("daily", daily_rows))
                return targets

            def save_kills_state(**extra: Any) -> None:
                self.state["kills"] = {
                    "ranking": sort_rows(ranking_rows),
                    "daily_ranking": sort_rows(daily_rows),
                    "ignored": ignored_rows,
                    "total_visible_players": len(ranking_rows),
                    "daily_total_visible_players": len(daily_rows),
                    "total_kills": sum(int(row.get("kills") or 0) for row in ranking_rows),
                    "daily_total_kills": sum(int(row.get("kills") or 0) for row in daily_rows),
                }
                self.state["kills"].update(extra)

            if action == "reset":
                ranking_rows.clear()
                daily_rows.clear()
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "reset_daily":
                daily_rows.clear()
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "reset_general":
                ranking_rows.clear()
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return

            player_name = str(payload.get("name") or payload.get("display_name") or payload.get("key") or "AizenVerify").strip()
            player_key = clean_key(payload.get("key") or player_name)
            player_kills = int(payload.get("kills") or payload.get("amount") or 0)
            ff_player_id = str(payload.get("ff_player_id") or "")

            if action == "ignore":
                ignored_rows[player_key] = {"name": player_name, "key": player_key}
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "unignore":
                ignored_rows.pop(player_key, None)
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "delete":
                for _target_name, rows in target_rows():
                    rows[:] = [row for row in rows if clean_key(row.get("key") or row.get("name")) != player_key]
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "set_name":
                new_name = str(payload.get("new_name") or payload.get("display_name") or player_name).strip()
                for rows in (ranking_rows, daily_rows):
                    row = find_row(rows, player_key)
                    if row is not None:
                        row["name"] = new_name
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return
            if action == "set_ff_id":
                for rows in (ranking_rows, daily_rows):
                    row = find_row(rows, player_key)
                    if row is not None:
                        row["ff_player_id"] = ff_player_id
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return

            if action in {"add", "remove", "set"}:
                for _target_name, rows in target_rows():
                    row = find_row(rows, player_key)
                    if row is None:
                        row = {
                            "name": player_name,
                            "kills": 0,
                            "key": player_key,
                            "ff_player_id": ff_player_id,
                            "entries": 0,
                        }
                        rows.append(row)
                    if ff_player_id:
                        row["ff_player_id"] = ff_player_id
                    current = int(row.get("kills") or 0)
                    if action == "add":
                        row["kills"] = max(0, current + abs(player_kills))
                    elif action == "remove":
                        row["kills"] = max(0, current - abs(player_kills))
                    else:
                        row["kills"] = max(0, player_kills)
                    ignored_rows.pop(player_key, None)
                save_kills_state(action=action)
                self._send_json({"ok": True, **self.state["kills"]})
                return

            save_kills_state(action=action)
            self._send_json({"ok": True, **self.state["kills"]})
            return
        if self.path.rstrip("/").endswith("/freefire-kills/style"):
            self.headers_seen["kills_style"] = {key: value for key, value in self.headers.items()}
            style_payload = payload.get("style") if isinstance(payload.get("style"), dict) else payload
            current_style = dict(self.state["kills_style"].get("style") or {})
            current_style.update(dict(style_payload or {}))
            self.state["kills_style"] = {"style": current_style}
            self._send_json({"ok": True, **self.state["kills_style"]})
            return
        if self.path.rstrip("/").endswith("/freefire-queue/action"):
            self.headers_seen["queue"] = {key: value for key, value in self.headers.items()}
            action = str(payload.get("action") or "")
            current_entries = parse_ff_queue_state(self.state.get("queue") or {}).entries

            def queue_to_payload(entries: list[FFQueueEntry], **extra: Any) -> dict[str, Any]:
                queue_payload = [
                    {
                        "name": entry.name,
                        "rooms": entry.rooms,
                        "credits": entry.rooms,
                        "user_id": entry.user_id,
                        "panel_user_id": entry.panel_user_id or entry.user_id,
                        "ff_player_id": entry.ff_player_id,
                    }
                    for entry in entries
                ]
                result = {
                    "mode": "ff_queue",
                    "room": payload.get("room"),
                    "queue": queue_payload,
                    "summary": {
                        "total_members": len(queue_payload),
                        "total_credits": sum(int(item.get("credits") or 0) for item in queue_payload),
                    },
                }
                result.update(extra)
                return result

            def incoming_user_id() -> str:
                return str(payload.get("user_id") or payload.get("panel_user_id") or "mock-user").strip()

            def find_index(entries: list[FFQueueEntry], user_id: str) -> int:
                for idx, entry in enumerate(entries):
                    if user_id and user_id in {entry.user_id, entry.panel_user_id}:
                        return idx
                return -1

            user_id = incoming_user_id()
            idx = find_index(current_entries, user_id)

            if action == "sync":
                self.state["queue"] = queue_to_payload(current_entries)
                self._send_json({"ok": True, **self.state["queue"]})
                return
            if action == "serve_next":
                next_entries, served, remaining = serve_next_queue_entries(current_entries)
                self.state["queue"] = queue_to_payload(
                    next_entries,
                    served_user_id=served.user_id if served else "",
                    remaining=remaining,
                )
                self._send_json({"ok": True, **self.state["queue"]})
                return
            if action == "clear_queue":
                self.state["queue"] = queue_to_payload([], cleared_credits=sum(entry.rooms for entry in current_entries))
                self._send_json({"ok": True, **self.state["queue"]})
                return
            if action == "add_member":
                player_name = str(payload.get("name") or payload.get("display_name") or "AizenVerify")
                rooms = max(1, int(payload.get("rooms") or payload.get("credits") or 1))
                ff_player_id = str(payload.get("ff_player_id") or "")
                if idx >= 0:
                    current_entries[idx].name = player_name
                    current_entries[idx].rooms = rooms
                    current_entries[idx].ff_player_id = ff_player_id
                else:
                    current_entries.append(
                        FFQueueEntry(
                            player_name,
                            rooms=rooms,
                            user_id=user_id,
                            panel_user_id=user_id,
                            ff_player_id=ff_player_id,
                        )
                    )
                self.state["queue"] = queue_to_payload(current_entries)
                self._send_json({"ok": True, **self.state["queue"]})
                return

            if idx < 0:
                current_entries.append(FFQueueEntry("AizenVerify", rooms=0, user_id=user_id, panel_user_id=user_id))
                idx = len(current_entries) - 1

            entry = current_entries[idx]
            if action == "set_name":
                entry.name = str(payload.get("display_name") or payload.get("name") or entry.name)
            elif action == "set_ff_id":
                entry.ff_player_id = str(payload.get("ff_player_id") or "")
            elif action == "add_credit":
                entry.rooms = max(0, entry.rooms + max(1, int(payload.get("credits") or payload.get("rooms") or 1)))
            elif action == "remove_credit":
                entry.rooms = max(0, entry.rooms - max(1, int(payload.get("credits") or payload.get("rooms") or 1)))
            elif action == "set_credit":
                entry.rooms = max(0, int(payload.get("credits") or payload.get("rooms") or 0))
            elif action == "remove_member":
                current_entries.pop(idx)
            elif action == "move_top" and idx >= 0:
                current_entries.insert(0, current_entries.pop(idx))
            elif action == "move_bottom" and idx >= 0:
                current_entries.append(current_entries.pop(idx))
            elif action == "move_up" and idx > 0:
                current_entries[idx - 1], current_entries[idx] = current_entries[idx], current_entries[idx - 1]
            elif action == "move_down" and idx < len(current_entries) - 1:
                current_entries[idx + 1], current_entries[idx] = current_entries[idx], current_entries[idx + 1]
            self.state["queue"] = {
                "mode": "ff_queue",
                "room": payload.get("room"),
                "queue": [
                    {
                        "name": entry.name,
                        "rooms": entry.rooms,
                        "credits": entry.rooms,
                        "user_id": entry.user_id,
                        "panel_user_id": entry.panel_user_id or entry.user_id,
                        "ff_player_id": entry.ff_player_id,
                    }
                    for entry in current_entries
                    if entry.rooms > 0 or action not in {"remove_credit", "set_credit"}
                ],
            }
            self.state["queue"]["summary"] = {
                "total_members": len(self.state["queue"]["queue"]),
                "total_credits": sum(int(item.get("credits") or 0) for item in self.state["queue"]["queue"]),
            }
            self._send_json({"ok": True, **self.state["queue"]})
            return
        if self.path.rstrip("/").endswith("/tikfinity/ff-gifts"):
            self.headers_seen["tikfinity"] = {key: value for key, value in self.headers.items()}
            action = str(payload.get("action") or "save_config")
            mappings = self.state["tikfinity"].setdefault("mappings", [])
            users = self.state["tikfinity"].setdefault("users", [])
            if action == "save_config":
                self.state["tikfinity"]["config"] = {
                    "enabled": bool(payload.get("enabled", True)),
                    "coins_per_room": int(payload.get("coins_per_room") or 50),
                    "token_configured": bool(payload.get("token")),
                }
            elif action == "add_mapping":
                social_user = str(payload.get("social_user") or payload.get("handle") or "").strip().lstrip("@").casefold()
                mappings[:] = [item for item in mappings if str(item.get("social_user") or "").casefold() != social_user]
                mappings.append(
                    {
                        "social_user": social_user,
                        "user_id": str(payload.get("user_id") or ""),
                        "display_name": str(payload.get("display_name") or ""),
                        "ff_player_id": str(payload.get("ff_player_id") or ""),
                    }
                )
            elif action == "remove_mapping":
                social_user = str(payload.get("social_user") or payload.get("handle") or "").strip().lstrip("@").casefold()
                mappings[:] = [item for item in mappings if str(item.get("social_user") or "").casefold() != social_user]
            elif action == "reset_user":
                uid = str(payload.get("user_id") or "").strip()
                users[:] = [item for item in users if str(item.get("user_id") or "") != uid]
            elif action == "clear_events":
                self.state["tikfinity"]["events"] = {}
                self.state["tikfinity"]["recent"] = []
                self.state["tikfinity"]["history"] = []
            elif action == "clear_history":
                self.state["tikfinity"]["recent"] = []
                self.state["tikfinity"]["history"] = []
            self.state["tikfinity"]["profile"] = str(payload.get("profile") or "streamer1")
            self.state["tikfinity"]["webhook_url"] = f"http://{self.headers.get('host')}/api/tikfinity/gift?profile={self.state['tikfinity']['profile']}"
            self._send_json({"ok": True, **self.state["tikfinity"]})
            return
        if self.path.rstrip("/").endswith("/freefire-overlay/config"):
            self.headers_seen["overlay_config"] = {key: value for key, value in self.headers.items()}
            action = str(payload.get("action") or "save_config")
            if action == "create_profile":
                label = str(payload.get("label") or "Perfil Teste")
                self.state["overlay_config"]["profile"] = "perfil-teste"
                self.state["overlay_config"]["profile_label"] = label
                self.state["overlay_config"]["profiles"] = [{"id": "perfil-teste", "label": label}]
            else:
                config_payload = payload.get("config") if isinstance(payload.get("config"), dict) else payload
                self.state["overlay_config"]["config"] = dict(config_payload)
            profile = str(self.state["overlay_config"].get("profile") or "streamer1")
            self.state["overlay_config"]["overlay_url"] = f"http://{self.headers.get('host')}/freefire/overlay?profile={profile}"
            self._send_json({"ok": True, **self.state["overlay_config"]})
            return
        if mode == "ff_queue":
            self.state["queue"] = payload
            self.headers_seen["queue"] = {key: value for key, value in self.headers.items()}
        elif mode == "ff_overlay":
            self.state["overlay"] = payload
            self.headers_seen["overlay"] = {key: value for key, value in self.headers.items()}
        else:
            if mode == "kills_snapshot" and self.state.get("debug", {}).get("reject_snapshot"):
                self._send_json({"ok": False, "error": "snapshot unsupported in mock"}, status=422)
                return
            if mode == "kills_snapshot" and self.state.get("debug", {}).get("weak_snapshot_ack"):
                self.headers_seen["kills"] = {key: value for key, value in self.headers.items()}
                self._send_json({"ok": True, "status": "saved"})
                return
            self.state["kills"] = payload
            self.headers_seen["kills"] = {key: value for key, value in self.headers.items()}
        self._send_json({"ok": True})

    def do_GET(self) -> None:
        if "freefire-overlay/config" in self.path:
            self.headers_seen["overlay_config"] = {key: value for key, value in self.headers.items()}
            profile = "streamer1"
            if "profile=perfil-teste" in self.path:
                profile = "perfil-teste"
            self.state["overlay_config"]["profile"] = profile
            self.state["overlay_config"]["overlay_url"] = f"http://{self.headers.get('host')}/freefire/overlay?profile={profile}"
            self._send_json({"ok": True, **self.state["overlay_config"]})
        elif "freefire-overlay" in self.path or "mode=ff_overlay" in self.path:
            self._send_json(self.state["overlay"])
        elif "freefire-queue" in self.path or "mode=ff_queue" in self.path:
            self._send_json(self.state["queue"])
        elif "tikfinity/ff-gifts" in self.path:
            self.headers_seen["tikfinity"] = {key: value for key, value in self.headers.items()}
            self._send_json({"ok": True, **self.state["tikfinity"]})
        elif "freefire-kills/rank" in self.path:
            payload = self.state.get("kills_rank") or self.state["kills"]
            self._send_json({"ok": True, **payload})
        elif "freefire-kills/style" in self.path:
            self.headers_seen["kills_style"] = {key: value for key, value in self.headers.items()}
            self._send_json({"ok": True, **self.state["kills_style"]})
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
    if derive_kills_rank_endpoint(expected_endpoints["kills"]) != "https://jarvis.squareweb.app/api/freefire-kills/rank":
        raise RuntimeError("Derivacao do rank Kills FF falhou.")
    if derive_kills_rank_endpoint("https://jarvis.squareweb.app/api/freefire-kills/action") != "https://jarvis.squareweb.app/api/freefire-kills/rank":
        raise RuntimeError("Derivacao do rank Kills FF por action falhou.")
    if derive_kills_rank_endpoint("https://jarvis.squareweb.app/freefire-kills/obs") != "https://jarvis.squareweb.app/api/freefire-kills/rank":
        raise RuntimeError("Derivacao do rank Kills FF por OBS falhou.")
    if derive_kills_style_endpoint(expected_endpoints["kills"]) != "https://jarvis.squareweb.app/api/freefire-kills/style":
        raise RuntimeError("Derivacao do estilo Kills FF falhou.")
    if derive_kills_style_endpoint("https://jarvis.squareweb.app/freefire-kills/obs") != "https://jarvis.squareweb.app/api/freefire-kills/style":
        raise RuntimeError("Derivacao do estilo Kills FF por URL OBS falhou.")
    if derive_ff_queue_action_endpoint(expected_endpoints["queue"]) != "https://jarvis.squareweb.app/api/freefire-queue/action":
        raise RuntimeError("Derivacao da action Fila FF falhou.")
    if derive_tikfinity_ff_gifts_endpoint(expected_endpoints["queue"]) != "https://jarvis.squareweb.app/api/tikfinity/ff-gifts":
        raise RuntimeError("Derivacao TikFinity FF falhou.")
    scope_checks = {
        "Ambos": ("both", "Ambos"),
        "Diario": ("daily", "Diario"),
        "Somente dia": ("daily", "Diario"),
        "Geral": ("general", "Geral"),
        "general": ("general", "Geral"),
    }
    for raw_scope, (expected_scope, expected_label) in scope_checks.items():
        if normalize_kills_scope_value(raw_scope) != expected_scope:
            raise RuntimeError(f"Escopo Kills FF divergente: {raw_scope!r}")
        if kills_scope_label(raw_scope) != expected_label:
            raise RuntimeError(f"Rotulo de escopo Kills FF divergente: {raw_scope!r}")

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
    snake_name_state = parse_realtime_state(
        {
            "ranking": [
                {"display_name": "Nome Snake", "kills": 8},
                {"player_name": "Nome Player", "total": 6},
            ],
        }
    )
    if [(item.name, item.kills) for item in snake_name_state.players] != [("Nome Snake", 8), ("Nome Player", 6)]:
        raise RuntimeError(f"Parser Kills FF nao leu nomes snake_case: {snake_name_state.players!r}")
    nested_name_state = parse_realtime_state(
        {
            "ranking": [
                {"user": {"nickname": "Nick Aninhado"}, "kills": 10},
                {"title": "Nome Titulo", "value": 3},
            ],
        }
    )
    if [(item.name, item.kills) for item in nested_name_state.players] != [("Nick Aninhado", 10), ("Nome Titulo", 3)]:
        raise RuntimeError(f"Parser Kills FF nao leu nomes alternativos: {nested_name_state.players!r}")
    split_rank_state = parse_realtime_state(
        {
            "ranking": [{"name": "Fallback", "kills": 1}],
            "daily_ranking": [{"name": "Dia", "kills": 7}],
            "general_ranking": [{"name": "Geral", "kills": 21}],
        }
    )
    if [(item.name, item.kills) for item in split_rank_state.daily_ranking] != [("Dia", 7)]:
        raise RuntimeError(f"Rank diario separado divergente: {split_rank_state.daily_ranking!r}")
    if [(item.name, item.kills) for item in split_rank_state.global_ranking] != [("Geral", 21)]:
        raise RuntimeError(f"Rank geral separado divergente: {split_rank_state.global_ranking!r}")
    overlay_rank = overlay_rank_players(
        split_rank_state.daily_ranking,
        split_rank_state.global_ranking,
        [PlayerKill("Manual", 99)],
    )
    if [(item.name, item.kills) for item in overlay_rank] != [("Dia", 7)]:
        raise RuntimeError(f"Overlay FF nao priorizou o rank diario: {overlay_rank!r}")
    overlay_global_fallback = overlay_rank_players([], split_rank_state.global_ranking, [PlayerKill("Manual", 99)])
    if [(item.name, item.kills) for item in overlay_global_fallback] != [("Geral", 21)]:
        raise RuntimeError(f"Overlay FF nao usou fallback do rank geral: {overlay_global_fallback!r}")
    recovered_manual_names = complete_player_names_from_references(
        [PlayerKill("", 48), PlayerKill("", 30), PlayerKill("", 29)],
        [PlayerKill("Xiom TTK", 48), PlayerKill("Emy", 30), PlayerKill("!Souza", 29)],
    )
    if [(item.name, item.kills) for item in recovered_manual_names] != [("Xiom TTK", 48), ("Emy", 30), ("!Souza", 29)]:
        raise RuntimeError(f"Recuperacao de nicks Kills FF divergente: {recovered_manual_names!r}")
    mixed_reference_names = complete_player_names_from_references(
        [PlayerKill("", 48), PlayerKill("", 30), PlayerKill("Novo", 7)],
        [PlayerKill("Xiom TTK", 48), PlayerKill("Emy", 30), PlayerKill("!Souza", 29)],
    )
    if [(item.name, item.kills) for item in mixed_reference_names] != [("Xiom TTK", 48), ("Emy", 30), ("Novo", 7)]:
        raise RuntimeError(f"Recuperacao parcial de nicks Kills FF divergente: {mixed_reference_names!r}")
    wire_player = player_wire_payload([PlayerKill("Xiom TTK", 48, key="xiom ttk", ff_player_id="123456789")])[0]
    for expected_key in ("name", "nick", "nickname", "player_name", "playerName", "display_name", "displayName", "username"):
        if wire_player.get(expected_key) != "Xiom TTK":
            raise RuntimeError(f"Payload Kills FF sem alias de nick {expected_key!r}: {wire_player!r}")
    ack_samples = (
        '{"status":"stored","message":"Ranking salvo com sucesso"}',
        '{"data":{"success":true,"message":"snapshot accepted"}}',
        "Ranking sincronizado com sucesso",
    )
    if not all(response_acknowledges_kills_snapshot(sample) for sample in ack_samples):
        raise RuntimeError("ACK positivo de snapshot Kills FF nao foi reconhecido.")
    reject_samples = (
        '{"ok":false,"error":"snapshot unsupported"}',
        '{"status":"error","message":"falha ao salvar"}',
        '{"data":{"success":false,"message":"invalid request"}}',
    )
    if any(response_acknowledges_kills_snapshot(sample) for sample in reject_samples):
        raise RuntimeError("ACK negativo de snapshot Kills FF foi aceito por engano.")
    with tempfile.TemporaryDirectory(prefix="aizen_mei_cleanup_") as tmpdir:
        base = Path(tmpdir)
        old_mei = base / "_MEI100001"
        fresh_mei = base / "_MEI100002"
        similar_name = base / "_MEIabc"
        for path in (old_mei, fresh_mei, similar_name):
            path.mkdir()
        old_time = time.time() - (48 * 60 * 60)
        os.utime(old_mei, (old_time, old_time))
        removed_mei = cleanup_stale_pyinstaller_dirs(base, min_age_seconds=24 * 60 * 60, max_dirs=4)
        if removed_mei != 1 or old_mei.exists() or not fresh_mei.exists() or not similar_name.exists():
            raise RuntimeError("Limpeza _MEI antiga removeu pasta errada ou deixou lixo antigo.")
    with tempfile.TemporaryDirectory(prefix="aizen_write_lock_") as tmpdir:
        output = Path(tmpdir) / "config.json"
        errors: list[str] = []

        def write_config(index: int) -> None:
            try:
                write_text_if_changed(output, json.dumps({"index": index, "items": list(range(10))}, ensure_ascii=False))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=write_config, args=(index,)) for index in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            raise RuntimeError(f"Escrita concorrente de config falhou: {errors!r}")
        written = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(written.get("index"), int) or list(Path(tmpdir).glob("*.tmp")):
            raise RuntimeError("Escrita concorrente deixou config invalido ou tmp sobrando.")

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
    queue_summary_state = parse_ff_queue_state(
        {
            "queue": {
                "entries": [
                    {"name": "Aizen", "credits": 4, "panel_user_id": "u-public", "ff_player_id": "123456"},
                    {"name": "Jarvis", "credits": 2, "user_id": "member-2"},
                ],
                "total_members": 2,
                "total_credits": 6,
            },
            "updated_by": "Jarvis Fila FF",
        }
    )
    if queue_summary_state.total_members != 2 or queue_summary_state.total_credits != 6:
        raise RuntimeError(f"Totais Fila FF nao foram lidos: {queue_summary_state!r}")
    if [(item.name, item.rooms, item.panel_user_id, item.ff_player_id) for item in queue_summary_state.entries] != [
        ("Aizen", 4, "u-public", "123456"),
        ("Jarvis", 2, "", ""),
    ]:
        raise RuntimeError(f"Parser Fila FF queue.entries divergente: {queue_summary_state.entries!r}")
    merged_queue = merge_ff_queue_entries(
        [
            FFQueueEntry("Aizen", rooms=1, ff_player_id="123456"),
            FFQueueEntry("Aizen OFC", rooms=2, ff_player_id="123456"),
            FFQueueEntry("Jarvis", rooms=1, user_id="member-1"),
            FFQueueEntry("Jarvis Bot", rooms=3, user_id="member-1"),
        ]
    )
    merged_signature = [(item.name, item.rooms, item.user_id, item.ff_player_id) for item in merged_queue]
    if merged_signature != [("Aizen", 3, "", "123456"), ("Jarvis", 4, "member-1", "")]:
        raise RuntimeError(f"Merge Fila FF por identidade divergente: {merged_signature!r}")
    served_queue, served_player, remaining_rooms = serve_next_queue_entries(
        [
            FFQueueEntry("Aizen", rooms=2, user_id="member-a"),
            FFQueueEntry("Jarvis", rooms=1, user_id="member-b"),
        ]
    )
    served_signature = [(item.name, item.rooms, item.user_id) for item in served_queue]
    if not served_player or served_player.name != "Aizen" or remaining_rooms != 1:
        raise RuntimeError(f"Serve next Fila FF nao atendeu o primeiro jogador: {served_player!r}")
    if served_signature != [("Jarvis", 1, "member-b"), ("Aizen", 1, "member-a")]:
        raise RuntimeError(f"Serve next Fila FF nao reordenou como o site: {served_signature!r}")

    overlay_kills = parse_realtime_state({"players": [{"username": "Overlay", "total": 9}]})
    overlay_queue = parse_ff_queue_state({"queue": [{"participant": "Overlay", "phase": "waiting"}]})
    if [(item.name, item.kills) for item in overlay_kills.players] != [("Overlay", 9)]:
        raise RuntimeError(f"Parser Overlay/Kills divergente: {overlay_kills.players!r}")
    if [(item.name, item.status, item.rooms) for item in overlay_queue.entries] != [("Overlay", "Na fila", 1)]:
        raise RuntimeError(f"Parser Overlay/Fila divergente: {overlay_queue.entries!r}")

    text_chat = {"event": "chat", "data": {"nickname": "Teste", "comment": "boa noite"}}
    emote_chat = {
        "event": "chat",
        "data": {
            "user": {"uniqueId": "pedro", "nickname": "Pedro"},
            "emotes": [{"emoteId": "1", "emoteImageUrl": "https://example.test/emote.webp"}],
        },
    }
    command_chat = {"event": "chat", "data": {"userDetails": {"username": "maria"}, "messageText": "!teste"}}
    like_event = {"event": "like", "data": {"nickname": "Teste", "likeCount": 1}}
    parsed_text_chat = normalize_live_chat_payload(text_chat, "TikFinity WebSocket")
    parsed_emote_chat = normalize_live_chat_payload(emote_chat, "TikFinity WebSocket")
    parsed_command_chat = normalize_live_chat_payload(command_chat, "TikFinity WebSocket")
    if not is_live_chat_event_payload(text_chat) or not parsed_text_chat or parsed_text_chat.comment != "boa noite":
        raise RuntimeError(f"Chat TikFinity com texto nao foi reconhecido: {parsed_text_chat!r}")
    if not is_live_chat_event_payload(emote_chat) or not parsed_emote_chat or parsed_emote_chat.comment != "[emote]":
        raise RuntimeError(f"Chat TikFinity com emote nao foi reconhecido: {parsed_emote_chat!r}")
    if not is_live_chat_event_payload(command_chat) or not parsed_command_chat or parsed_command_chat.comment != "!teste":
        raise RuntimeError(f"Comando TikFinity em messageText nao foi reconhecido: {parsed_command_chat!r}")
    if is_live_chat_event_payload(like_event) or normalize_live_chat_payload(like_event, "TikFinity WebSocket") is not None:
        raise RuntimeError("Evento de like do TikFinity foi tratado como chat.")
    command_checks = {
        "!pix": ("!pix", ""),
        "!PIX agora": ("!pix", "agora"),
        "\u200b!pix chave": ("!pix", "chave"),
        "！pix chave": ("!pix", "chave"),
        "@Aizen !pix chave": ("!pix", "chave"),
        "!pix, chave": ("!pix", "chave"),
        "boa !pix": ("", ""),
    }
    for raw_message, expected in command_checks.items():
        actual = chat_command_token(raw_message)
        if actual != expected:
            raise RuntimeError(f"Parser de comando TikFinity divergente: {raw_message!r} -> {actual!r}")
    if normalize_chat_command("pix,") != "!pix" or normalize_chat_command("！PIX") != "!pix":
        raise RuntimeError("Normalizacao de comando da aba Comandos falhou.")

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
        MockJarvisHandler.state["kills_rank"] = {
            "ranking": [{"name": "Geral Rank", "kills": 128}],
            "daily_ranking": [{"name": "Dia Rank", "kills": 54}],
        }
        rank_fallback_state = fetch_kills_realtime(kills_url, device_id, device_name, room, token)
        if [(item.name, item.kills) for item in rank_fallback_state.daily_ranking] != [("Dia Rank", 54)]:
            raise RuntimeError(f"Fallback /rank nao carregou rank diario: {rank_fallback_state.daily_ranking!r}")
        if [(item.name, item.kills) for item in rank_fallback_state.global_ranking] != [("Geral Rank", 128)]:
            raise RuntimeError(f"Fallback /rank nao carregou rank geral: {rank_fallback_state.global_ranking!r}")
        MockJarvisHandler.state["kills_rank"] = {}
        saved_style = send_kills_style_update(
            kills_url,
            {"title_text": "TOP TESTE", "row_size": 31, "accent_enabled": True},
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        if saved_style.get("title_text") != "TOP TESTE" or int(saved_style.get("row_size") or 0) != 31:
            raise RuntimeError(f"Style Kills FF divergente no POST: {saved_style!r}")
        fetched_style = fetch_kills_style(kills_url, device_id=device_id, device_name=device_name, token=token)
        if fetched_style.get("title_text") != "TOP TESTE" or not fetched_style.get("accent_enabled"):
            raise RuntimeError(f"Style Kills FF divergente no GET: {fetched_style!r}")
        action_state = send_kills_action_update(
            kills_url,
            "set",
            PlayerKill("AizenVerify", 18, key="aizenverify"),
            kills=18,
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not action_state.daily_ranking or not action_state.global_ranking:
            raise RuntimeError(f"Set Kills FF nao criou os dois rankings: {action_state!r}")
        if action_state.daily_ranking[0].kills != 18 or action_state.global_ranking[0].kills != 18:
            raise RuntimeError(f"Set Kills FF divergente: {action_state!r}")
        added_kills = send_kills_action_update(
            kills_url,
            "add",
            PlayerKill("AizenVerify", 18, key="aizenverify"),
            kills=2,
            scope="general",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not added_kills.global_ranking or added_kills.global_ranking[0].kills != 20:
            raise RuntimeError(f"Add Kills FF geral divergente: {added_kills.global_ranking!r}")
        removed_kills = send_kills_action_update(
            kills_url,
            "remove",
            PlayerKill("AizenVerify", 18, key="aizenverify"),
            kills=3,
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not removed_kills.daily_ranking or removed_kills.daily_ranking[0].kills != 15:
            raise RuntimeError(f"Remove Kills FF diario divergente: {removed_kills.daily_ranking!r}")
        renamed_kills = send_kills_action_update(
            kills_url,
            "set_name",
            PlayerKill("AizenVerify", 0, key="aizenverify"),
            new_name="AizenRenamed",
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        renamed_names = {item.name for item in renamed_kills.global_ranking + renamed_kills.daily_ranking}
        if "AizenRenamed" not in renamed_names or "AizenVerify" in renamed_names:
            raise RuntimeError(f"Set name Kills FF divergente: {renamed_kills!r}")
        id_kills = send_kills_action_update(
            kills_url,
            "set_ff_id",
            PlayerKill("AizenRenamed", 0, key="aizenverify"),
            ff_player_id="123456789",
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        selected_ids = {
            item.ff_player_id
            for item in id_kills.global_ranking + id_kills.daily_ranking
            if item.key == "aizenverify" or item.name == "AizenRenamed"
        }
        if selected_ids != {"123456789"}:
            raise RuntimeError(f"Set ID FF Kills FF divergente: {id_kills!r}")
        ignored_kills = send_kills_action_update(
            kills_url,
            "ignore",
            PlayerKill("AizenRenamed", 0, key="aizenverify"),
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not ignored_kills.ignored_players:
            raise RuntimeError(f"Ignore Kills FF divergente: {ignored_kills.ignored_players!r}")
        unignored_kills = send_kills_action_update(
            kills_url,
            "unignore",
            PlayerKill("AizenRenamed", 0, key="aizenverify"),
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if unignored_kills.ignored_players:
            raise RuntimeError(f"Unignore Kills FF divergente: {unignored_kills.ignored_players!r}")
        deleted_daily = send_kills_action_update(
            kills_url,
            "delete",
            PlayerKill("AizenRenamed", 0, key="aizenverify"),
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if deleted_daily.daily_ranking or not deleted_daily.global_ranking:
            raise RuntimeError(f"Delete diario Kills FF divergente: {deleted_daily!r}")
        daily_again = send_kills_action_update(
            kills_url,
            "set",
            PlayerKill("DailyVerify", 7, key="dailyverify"),
            kills=7,
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not daily_again.daily_ranking:
            raise RuntimeError(f"Set diario Kills FF divergente: {daily_again!r}")
        reset_daily = send_kills_action_update(
            kills_url,
            "reset_daily",
            PlayerKill("", 0),
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if reset_daily.daily_ranking or not reset_daily.global_ranking:
            raise RuntimeError(f"Reset diario Kills FF divergente: {reset_daily!r}")
        reset_general = send_kills_action_update(
            kills_url,
            "reset_general",
            PlayerKill("", 0),
            scope="general",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if reset_general.global_ranking:
            raise RuntimeError(f"Reset geral Kills FF divergente: {reset_general!r}")
        final_kills = send_kills_action_update(
            kills_url,
            "set",
            PlayerKill("FinalVerify", 3, key="finalverify"),
            kills=3,
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not final_kills.daily_ranking or not final_kills.global_ranking:
            raise RuntimeError(f"Set final Kills FF divergente: {final_kills!r}")
        reset_state = send_kills_action_update(
            kills_url,
            "reset",
            PlayerKill("", 0),
            scope="both",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if reset_state.daily_ranking or reset_state.global_ranking:
            raise RuntimeError(f"Reset total Kills FF divergente: {reset_state!r}")
        snapshot_state = send_kills_snapshot_update(
            kills_url,
            [PlayerKill("Pedro", 2), PlayerKill("pedro", 3), PlayerKill("Ana", 1)],
            [PlayerKill("Pedro", 5)],
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        daily_snapshot = {item.name.casefold(): item.kills for item in snapshot_state.daily_ranking or []}
        global_snapshot = {item.name.casefold(): item.kills for item in snapshot_state.global_ranking or []}
        if daily_snapshot != {"pedro": 5, "ana": 1} or global_snapshot != {"pedro": 5}:
            raise RuntimeError(f"Snapshot Kills FF nao substituiu corretamente: {snapshot_state!r}")
        persisted_snapshot = fetch_kills_realtime(kills_url, device_id=device_id, device_name=device_name, room=room, token=token)
        persisted_daily = {item.name.casefold(): item.kills for item in persisted_snapshot.daily_ranking or []}
        persisted_global = {item.name.casefold(): item.kills for item in persisted_snapshot.global_ranking or []}
        if persisted_daily != {"pedro": 5, "ana": 1} or persisted_global != {"pedro": 5}:
            raise RuntimeError(f"Snapshot Kills FF retornou sucesso, mas nao persistiu no Jarvis: {persisted_snapshot!r}")
        replaced_snapshot = send_kills_snapshot_update(
            kills_url,
            [PlayerKill("Pedro", 1)],
            [],
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        replaced_daily = {item.name.casefold(): item.kills for item in replaced_snapshot.daily_ranking or []}
        replaced_global = {item.name.casefold(): item.kills for item in replaced_snapshot.global_ranking or []}
        if replaced_daily != {"pedro": 1} or replaced_global:
            raise RuntimeError(f"Snapshot Kills FF somou ou manteve dados antigos: {replaced_snapshot!r}")
        persisted_replaced = fetch_kills_realtime(kills_url, device_id=device_id, device_name=device_name, room=room, token=token)
        persisted_replaced_daily = {item.name.casefold(): item.kills for item in persisted_replaced.daily_ranking or []}
        persisted_replaced_global = {item.name.casefold(): item.kills for item in persisted_replaced.global_ranking or []}
        if persisted_replaced_daily != {"pedro": 1} or persisted_replaced_global:
            raise RuntimeError(f"Snapshot Kills FF nao substituiu o diario persistido: {persisted_replaced!r}")
        MockJarvisHandler.state["kills"] = {"ranking": [], "daily_ranking": [], "ignored": {}}
        MockJarvisHandler.state["kills_rank"] = {}
        MockJarvisHandler.state["debug"] = {"kills_actions": [], "weak_snapshot_ack": True}
        weak_ack_snapshot = send_kills_snapshot_update(
            kills_url,
            [PlayerKill("DiarioOk", 7)],
            [PlayerKill("GeralOk", 9)],
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        weak_ack_daily = {item.name.casefold(): item.kills for item in weak_ack_snapshot.daily_ranking or []}
        weak_ack_global = {item.name.casefold(): item.kills for item in weak_ack_snapshot.global_ranking or []}
        weak_ack_actions = MockJarvisHandler.state.get("debug", {}).get("kills_actions", [])
        if weak_ack_daily != {"diariook": 7} or weak_ack_global != {"geralok": 9}:
            raise RuntimeError(f"Snapshot Kills FF com ack fraco nao caiu para fallback: {weak_ack_snapshot!r}")
        if weak_ack_actions.count("set") < 2:
            raise RuntimeError(f"Fallback do Snapshot Kills FF nao gravou diario e geral: {weak_ack_actions!r}")
        MockJarvisHandler.state["kills"] = {
            "daily_ranking": [{"name": "AizenDelta", "kills": 10}, {"name": "JarvisDelta", "kills": 2}],
            "ranking": [{"name": "AizenDelta", "kills": 20}, {"name": "JarvisDelta", "kills": 4}],
            "ignored": {},
        }
        MockJarvisHandler.state["kills_rank"] = {}
        MockJarvisHandler.state["debug"] = {"kills_actions": [], "reject_snapshot": True}
        delta_snapshot = send_kills_snapshot_update(
            kills_url,
            [PlayerKill("AizenDelta", 11), PlayerKill("JarvisDelta", 2)],
            [PlayerKill("AizenDelta", 20), PlayerKill("JarvisDelta", 4)],
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        delta_daily = {item.name.casefold(): item.kills for item in delta_snapshot.daily_ranking or []}
        delta_global = {item.name.casefold(): item.kills for item in delta_snapshot.global_ranking or []}
        delta_actions = MockJarvisHandler.state.get("debug", {}).get("kills_actions", [])
        if delta_daily != {"aizendelta": 11, "jarvisdelta": 2} or delta_global != {"aizendelta": 20, "jarvisdelta": 4}:
            raise RuntimeError(f"Delta Kills FF divergente: {delta_snapshot!r}")
        if "reset_daily" in delta_actions or "reset_general" in delta_actions or delta_actions.count("set") != 1:
            raise RuntimeError(f"Delta Kills FF fez acoes demais: {delta_actions!r}")
        MockJarvisHandler.state["debug"] = {"kills_actions": []}

    send_ff_queue_realtime_update(queue_url, queue, device_id, device_name, room, token)
    if queue_url.startswith("http://127.0.0.1:"):
        assert_mock_write_contract("queue", "ff_queue", room, device_id, device_name, token)
    fetched_queue = fetch_ff_queue_realtime(queue_url, device_id, device_name, room, token)
    if [(item.name, item.note, item.status, item.rooms) for item in fetched_queue.entries] != [
        (item.name, item.note, item.status, item.rooms) for item in queue
    ]:
        raise RuntimeError(f"Fila FF divergente: {fetched_queue.entries!r}")
    if queue_url.startswith("http://127.0.0.1:"):
        cleared_queue = send_ff_queue_action_update(
            queue_url,
            "clear_queue",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if cleared_queue.entries or cleared_queue.total_members not in (0, None):
            raise RuntimeError(f"Clear Fila FF divergente: {cleared_queue!r}")
        added_queue = send_ff_queue_action_update(
            queue_url,
            "add_member",
            FFQueueEntry("ManualVerify", rooms=4, user_id="member-123", ff_player_id="123456789"),
            credits=4,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not added_queue.entries or added_queue.entries[0].user_id != "member-123" or added_queue.entries[0].ff_player_id != "123456789":
            raise RuntimeError(f"Add member Fila FF divergente: {added_queue.entries!r}")
        renamed_queue = send_ff_queue_action_update(
            queue_url,
            "set_name",
            FFQueueEntry("ManualRenamed", rooms=4, user_id="member-123", ff_player_id="123456789"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not renamed_queue.entries or renamed_queue.entries[0].name != "ManualRenamed":
            raise RuntimeError(f"Set name Fila FF divergente: {renamed_queue.entries!r}")
        id_queue = send_ff_queue_action_update(
            queue_url,
            "set_ff_id",
            FFQueueEntry("ManualRenamed", rooms=4, user_id="member-123", ff_player_id="987654321"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not id_queue.entries or id_queue.entries[0].ff_player_id != "987654321":
            raise RuntimeError(f"Set ID FF Fila FF divergente: {id_queue.entries!r}")
        plus_queue = send_ff_queue_action_update(
            queue_url,
            "add_credit",
            FFQueueEntry("ManualRenamed", rooms=4, user_id="member-123", ff_player_id="987654321"),
            credits=2,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not plus_queue.entries or plus_queue.entries[0].rooms != 6:
            raise RuntimeError(f"Add credit Fila FF divergente: {plus_queue.entries!r}")
        minus_queue = send_ff_queue_action_update(
            queue_url,
            "remove_credit",
            FFQueueEntry("ManualRenamed", rooms=6, user_id="member-123", ff_player_id="987654321"),
            credits=1,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not minus_queue.entries or minus_queue.entries[0].rooms != 5:
            raise RuntimeError(f"Remove credit Fila FF divergente: {minus_queue.entries!r}")
        action_queue = send_ff_queue_action_update(
            queue_url,
            "set_credit",
            FFQueueEntry("ManualRenamed", rooms=5, user_id="member-123", ff_player_id="987654321"),
            credits=3,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not action_queue.entries or action_queue.entries[0].rooms != 3:
            raise RuntimeError(f"Set credit Fila FF divergente: {action_queue.entries!r}")
        if action_queue.total_members != 1 or action_queue.total_credits != 3:
            raise RuntimeError(f"Resumo Action Fila FF divergente: {action_queue!r}")
        added_second_queue = send_ff_queue_action_update(
            queue_url,
            "add_member",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999", ff_player_id="555555555"),
            credits=1,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if len(added_second_queue.entries) != 2:
            raise RuntimeError(f"Segundo membro Fila FF divergente: {added_second_queue.entries!r}")
        reordered_queue = send_ff_queue_action_update(
            queue_url,
            "move_top",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not reordered_queue.entries or reordered_queue.entries[0].user_id != "member-999":
            raise RuntimeError(f"Move top Fila FF divergente: {reordered_queue.entries!r}")
        moved_down_queue = send_ff_queue_action_update(
            queue_url,
            "move_down",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not moved_down_queue.entries or moved_down_queue.entries[-1].user_id != "member-999":
            raise RuntimeError(f"Move down Fila FF divergente: {moved_down_queue.entries!r}")
        moved_up_queue = send_ff_queue_action_update(
            queue_url,
            "move_up",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not moved_up_queue.entries or moved_up_queue.entries[0].user_id != "member-999":
            raise RuntimeError(f"Move up Fila FF divergente: {moved_up_queue.entries!r}")
        moved_bottom_queue = send_ff_queue_action_update(
            queue_url,
            "move_bottom",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if not moved_bottom_queue.entries or moved_bottom_queue.entries[-1].user_id != "member-999":
            raise RuntimeError(f"Move bottom Fila FF divergente: {moved_bottom_queue.entries!r}")
        synced_queue = send_ff_queue_action_update(
            queue_url,
            "sync",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if [(entry.user_id, entry.rooms) for entry in synced_queue.entries] != [("member-123", 3), ("member-999", 1)]:
            raise RuntimeError(f"Sync Fila FF divergente: {synced_queue.entries!r}")
        served_queue = send_ff_queue_action_update(
            queue_url,
            "serve_next",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        served_signature = [(entry.user_id, entry.rooms) for entry in served_queue.entries]
        if served_signature != [("member-999", 1), ("member-123", 2)]:
            raise RuntimeError(f"Serve next Fila FF divergente: {served_queue.entries!r}")
        removed_queue = send_ff_queue_action_update(
            queue_url,
            "remove_member",
            FFQueueEntry("SecondVerify", rooms=1, user_id="member-999"),
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if [(entry.user_id, entry.rooms) for entry in removed_queue.entries] != [("member-123", 2)]:
            raise RuntimeError(f"Remove member Fila FF divergente: {removed_queue.entries!r}")
        tikfinity_url = derive_tikfinity_ff_gifts_endpoint(queue_url)
        saved_tikfinity = send_tikfinity_ff_gifts_action(
            tikfinity_url,
            "save_config",
            {"enabled": False, "coins_per_room": 75, "token": "secret-test"},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        saved_config = saved_tikfinity.get("config") if isinstance(saved_tikfinity.get("config"), dict) else {}
        if saved_config.get("enabled") is not False or int(saved_config.get("coins_per_room") or 0) != 75:
            raise RuntimeError(f"Save config TikFinity FF divergente: {saved_tikfinity!r}")
        tikfinity_state = send_tikfinity_ff_gifts_action(
            tikfinity_url,
            "add_mapping",
            {"social_user": "aizen", "user_id": "mock-user", "display_name": "Aizen", "ff_player_id": "123456"},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        if not tikfinity_state.get("mappings"):
            raise RuntimeError(f"Action TikFinity FF divergente: {tikfinity_state!r}")
        removed_mapping = send_tikfinity_ff_gifts_action(
            tikfinity_url,
            "remove_mapping",
            {"social_user": "aizen"},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        if removed_mapping.get("mappings"):
            raise RuntimeError(f"Remove mapping TikFinity FF divergente: {removed_mapping!r}")
        reset_user = send_tikfinity_ff_gifts_action(
            tikfinity_url,
            "reset_user",
            {"user_id": "mock-user"},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        if reset_user.get("users"):
            raise RuntimeError(f"Reset user TikFinity FF divergente: {reset_user!r}")
        cleared_history = send_tikfinity_ff_gifts_action(
            tikfinity_url,
            "clear_history",
            {},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        if cleared_history.get("history"):
            raise RuntimeError(f"Clear history TikFinity FF divergente: {cleared_history!r}")
        fetched_tikfinity = fetch_tikfinity_ff_gifts(tikfinity_url, "streamer1", device_id, device_name, token)
        fetched_config = fetched_tikfinity.get("config") if isinstance(fetched_tikfinity.get("config"), dict) else {}
        if int(fetched_config.get("coins_per_room") or 0) != 75:
            raise RuntimeError(f"GET TikFinity FF divergente: {fetched_tikfinity!r}")

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
        overlay_config = {
            "enabled_general": True,
            "enabled_daily": True,
            "enabled_queue": True,
            "layout": "grid",
            "font_family": "impact",
            "animation": "pop",
            "refresh_ms": 3000,
            "switch_seconds": 11,
            "limit_general": 7,
            "limit_daily": 6,
            "limit_queue": 5,
            "panel_width": 420,
            "gap": 18,
            "wrap_padding": 12,
            "title_size": 32,
            "row_size": 24,
            "value_size": 28,
            "row_height": 44,
            "panel_bg_color": "#101820",
            "panel_bg_opacity": 55,
            "panel_radius": 14,
            "row_bg_color": "#050505",
            "row_bg_opacity": 34,
            "accent_width": 6,
            "panel_bg_enabled": True,
            "show_rank_prefix": True,
            "show_medals": True,
            "general": {
                "title": "GERAL TESTE",
                "title_color": "#FFD54A",
                "rank_color": "#FFD54A",
                "name_color": "#FFFFFF",
                "value_color": "#66FF99",
                "accent_color": "#FF4655",
            },
            "daily": {
                "title": "DIA TESTE",
                "title_color": "#66FF99",
                "rank_color": "#66FF99",
                "name_color": "#FFFFFF",
                "value_color": "#FFD54A",
                "accent_color": "#24D17E",
            },
            "queue": {
                "title": "FILA TESTE",
                "title_color": "#7AD7FF",
                "rank_color": "#7AD7FF",
                "name_color": "#FFFFFF",
                "value_color": "#FFD54A",
                "accent_color": "#3BA7FF",
            },
        }
        saved_overlay_config = send_ff_overlay_config_action(
            overlay_url,
            "save_config",
            {"config": overlay_config, "label": "Perfil Teste"},
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        saved_config = saved_overlay_config.get("config") if isinstance(saved_overlay_config.get("config"), dict) else {}
        if int(saved_config.get("gap") or 0) != 18 or saved_config.get("queue", {}).get("title") != "FILA TESTE":
            raise RuntimeError(f"Config Overlay FF divergente no POST: {saved_overlay_config!r}")
        fetched_overlay_config = fetch_ff_overlay_config(
            overlay_url,
            profile="streamer1",
            device_id=device_id,
            device_name=device_name,
            token=token,
        )
        fetched_config = fetched_overlay_config.get("config") if isinstance(fetched_overlay_config.get("config"), dict) else {}
        if int(fetched_config.get("row_height") or 0) != 44 or fetched_config.get("general", {}).get("accent_color") != "#FF4655":
            raise RuntimeError(f"Config Overlay FF divergente no GET: {fetched_overlay_config!r}")
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
