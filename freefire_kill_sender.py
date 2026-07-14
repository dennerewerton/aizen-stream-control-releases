from __future__ import annotations

import argparse
import base64
import ctypes
import ctypes.wintypes
import errno
import hashlib
import html
import json
import os
import platform
import queue
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import uuid
import webbrowser
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, quote, urlparse

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

cv2: Any | None = None
np: Any | None = None
ImageGrab: Any | None = None


def ensure_image_processing_modules() -> tuple[Any, Any]:
    global cv2, np
    if cv2 is None or np is None:
        try:
            import cv2 as cv2_module
            import numpy as numpy_module
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Captura/OCR automatico antigo nao esta incluido nesta versao leve. "
                "Use o painel Kills FF manual para lancar as kills."
            ) from exc

        cv2 = cv2_module
        np = numpy_module
    return cv2, np


def ensure_image_grab_module() -> Any:
    global ImageGrab
    if ImageGrab is None:
        from PIL import ImageGrab as image_grab_module

        ImageGrab = image_grab_module
    return ImageGrab


IS_FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
ASSET_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ROOT = APP_DIR
DEFAULT_CONFIG = APP_DIR / "config.json"
CONFIG_EXAMPLE = ASSET_DIR / "config.example.json"
OCR_SCRIPT = ASSET_DIR / "scripts" / "windows_ocr.ps1"
APP_LOGO = ASSET_DIR / "assets" / "app_logo.png"
APP_ICON = ASSET_DIR / "assets" / "app_icon.ico"
APP_NAME = "Aizen Stream Control"
APP_EXE_NAME = "AizenStreamControl.exe"
APP_VERSION = "2.6.256"
DEFAULT_UPDATES_MANIFEST_URL = (
    "https://github.com/dennerewerton/aizen-stream-control-releases/releases/latest/download/updates.json"
)
TIKFINITY_DIRECT_FALLBACK_PORTS = (8080, 8081, 8082, 8090, 18080)
UPDATE_DOWNLOAD_ATTEMPTS = 3
UPDATE_DOWNLOAD_CHUNK_BYTES = 256 * 1024
UPDATE_MANIFEST_TIMEOUT_SECONDS = 4
UPDATE_DOWNLOAD_CONNECT_TIMEOUT_SECONDS = 12
UPDATE_DOWNLOAD_READ_TIMEOUT_SECONDS = 18
LOG_QUEUE_SOFT_LIMIT = 1500
LOG_QUEUE_HARD_LIMIT = 2200
LOG_TEXT_MAX_LINES = 1200
LOG_PUMP_BATCH_LIMIT = 60
LOG_FULL_RENDER_CHUNK_LINES = 160
LOG_INACTIVE_IDLE_PUMP_MS = 8000
CHAT_USER_CACHE_LIMIT = 600
CHAT_EVENT_QUEUE_LIMIT = 800
CHAT_EVENT_BATCH_LIMIT = 32
CHAT_EVENT_BUSY_PUMP_MS = 20
CHAT_EVENT_IDLE_PUMP_MS = 180
CHAT_EVENT_QUIET_PUMP_MS = 500
CHAT_EVENT_BACKGROUND_QUIET_PUMP_MS = 900
CHAT_RENDER_INCREMENTAL_THRESHOLD = 48
CHAT_RENDER_CHUNK_SIZE = 18
CHAT_RENDER_CHUNK_DELAY_MS = 16
SYNC_QUEUE_LIMIT = 240
FF_QUEUE_SYNC_QUEUE_LIMIT = 180
LIVEPIX_QUEUE_LIMIT = 600
LIVEPIX_INACTIVE_IDLE_PUMP_MS = 8000
BOT_REPLY_QUEUE_LIMIT = 80
BOT_RESULT_QUEUE_LIMIT = 120
AVATAR_RESULT_QUEUE_LIMIT = 180
AVATAR_IMAGE_CACHE_LIMIT = 240
AVATAR_PENDING_LIMIT = 120
AVATAR_DOWNLOAD_WORKERS = 3
AVATAR_RESULT_BATCH_LIMIT = 8
RAFFLE_SEEN_MESSAGES_LIMIT = 2500
RAFFLE_PARTICIPANT_RENDER_THRESHOLD = 60
RAFFLE_PARTICIPANT_RENDER_CHUNK_SIZE = 20
RAFFLE_PARTICIPANT_RENDER_CHUNK_DELAY_MS = 18
LIVEPIX_EVENT_STORAGE_LIMIT = 1000
LIVEPIX_HISTORY_RENDER_LIMIT = 30
LIVEPIX_HISTORY_RENDER_CHUNK_SIZE = 8
LIVEPIX_STARTUP_SYNC_DELAY_MS = 3500
LIVEPIX_STARTUP_HISTORY_DELAY_MS = 5200
LIVEPIX_DASHBOARD_REFRESH_DELAY_MS = 180
LIVEPIX_LIGHT_COLLECTION_LIMIT = 30
LIVEPIX_LIGHT_COLLECTION_MAX_PAGES = 1
LIVEPIX_FULL_COLLECTION_LIMIT = 100
LIVEPIX_FULL_COLLECTION_MAX_PAGES = 12
KILLS_VISUAL_REFRESH_DELAY_MS = 220
KILLS_RANK_RENDER_LIMIT = 100
KILLS_OVERLAY_RENDER_LIMIT = 50
KILLS_RANK_INCREMENTAL_THRESHOLD = 36
KILLS_RANK_RENDER_CHUNK_SIZE = 16
KILLS_RANK_RENDER_CHUNK_DELAY_MS = 12
MANUAL_TABLE_INCREMENTAL_THRESHOLD = 18
MANUAL_TABLE_RENDER_CHUNK_SIZE = 10
MANUAL_TABLE_RENDER_CHUNK_DELAY_MS = 15
KILLS_POST_TIMEOUT_SECONDS = 10
KILLS_GET_TIMEOUT_SECONDS = 8
KILLS_CONFIRM_GET_TIMEOUT_SECONDS = 3
KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS = (0.0, 0.2)
KILLS_RANK_CONFIRM_DELAYS_SECONDS = (0.0, 0.35, 0.85)
STARTUP_IDLE_TASK_DELAY_MS = 650
STARTUP_MAINTENANCE_DELAY_MS = 30000
BACKGROUND_IDLE_PUMP_MS = 2000
SYNC_QUEUE_IDLE_PUMP_MS = 1200
SYNC_QUEUE_PROCESSED_PUMP_MS = 140
BACKGROUND_DISABLED_PUMP_MS = 8000
DEFERRED_RENDER_IDLE_PUMP_MS = 8000
DEFERRED_RENDER_ACTIVE_IDLE_PUMP_MS = 1500
UI_PUMP_TIME_BUDGET_SECONDS = 0.035
SYNC_WORKER_MAX_THREADS = 3
FF_QUEUE_WORKER_MAX_THREADS = 2
LIVEPIX_WORKER_MAX_THREADS = 3
BOT_WORKER_MAX_THREADS = 1
STALE_MEI_MIN_AGE_SECONDS = 24 * 60 * 60
STALE_MEI_CLEANUP_LIMIT = 3
WRITE_TEXT_CACHE: dict[Path, tuple[tuple[int, int], str]] = {}
WRITE_TEXT_CACHE_LOCK = threading.Lock()
WRITE_TEXT_IO_LOCK = threading.Lock()
KILLS_SNAPSHOT_ENDPOINT_CACHE: dict[str, str] = {}
KILLS_SNAPSHOT_ENDPOINT_CACHE_LOCK = threading.Lock()
DEFAULT_TIKFINITY_WEBSOCKET_URL = "ws://127.0.0.1:21213/"
DEFAULT_STREAMERBOT_WEBSOCKET_URL = "ws://127.0.0.1:8080/"
DEFAULT_STREAMERBOT_HTTP_URL = "http://127.0.0.1:7474"
WINSOCK_CLEAN_RESTART_ENV = "AIZEN_WINSOCK_CLEAN_RESTARTED"
TIKFINITY_DIRECT_SEND_WAIT_SECONDS = 12.0
TIKFINITY_DIRECT_CHATBOT_HINT = (
    "Se nao aparecer na live, confirme no TikFinity: Chatbot > Settings > "
    "Allow Streamer.bot to push messages to TikFinity. Se ja estiver ativo, desconecte e conecte "
    "novamente a conexao Streamer.bot no TikFinity."
)
BOT_DELIVERY_TIKFINITY_DIRECT = "tikfinity_direct"
BOT_DELIVERY_STREAMERBOT_WEBSOCKET = "streamerbot_websocket"
BOT_DELIVERY_STREAMERBOT_HTTP = "streamerbot_http"
LIVE_CHAT_EVENT_NAMES = {"chat", "comment", "message", "command", "chatmessage", "livechat"}
LIVE_CHAT_TEXT_FIELDS = (
    "comment",
    "chatmessage",
    "message",
    "msg",
    "text",
    "content",
    "commentText",
    "messageText",
    "commandParams",
    "command",
)


def live_chat_emote_comment(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    emotes = payload.get("emotes")
    if not isinstance(emotes, list):
        emotes = data.get("emotes")
    if not isinstance(emotes, list) or not emotes:
        return ""
    visible = []
    for item in emotes[:8]:
        if isinstance(item, dict):
            visible.append(_first_text(item.get("name"), item.get("emoteName"), item.get("shortCode"), item.get("code")) or "[emote]")
        else:
            visible.append(str(item) or "[emote]")
    if len(emotes) > len(visible):
        visible.append(f"+{len(emotes) - len(visible)}")
    return " ".join(visible) or "[emote]"

THEME_SCHEMA_VERSION = "2026.2"
LEGACY_AIZEN_RED_THEME = {
    "canvas_bg": "#050506",
    "bg": "#0b0b0e",
    "panel": "#111116",
    "panel_alt": "#181014",
    "field": "#07080b",
    "border": "#3a1518",
    "fg": "#f8f2f1",
    "muted": "#b8a6a5",
    "accent": "#ff1717",
    "accent_hover": "#ff3b32",
    "teal": "#ff4d4d",
    "blue": "#c91d1d",
    "danger": "#9d252d",
}


THEME_PRESETS: dict[str, dict[str, str]] = {
    "Aizen Red": {
        "canvas_bg": "#050506",
        "bg": "#08090d",
        "panel": "#101116",
        "panel_alt": "#171217",
        "field": "#090a0f",
        "border": "#332025",
        "fg": "#f8f3f2",
        "muted": "#ad9da0",
        "accent": "#ff2633",
        "accent_hover": "#ff5a4d",
        "teal": "#35d6a5",
        "blue": "#8bb0ff",
        "danger": "#d84855",
    },
    "Obsidian Gold": {
        "canvas_bg": "#050504",
        "bg": "#0b0a08",
        "panel": "#12110d",
        "panel_alt": "#18150d",
        "field": "#070706",
        "border": "#4b3412",
        "fg": "#fff8e6",
        "muted": "#c4b99e",
        "accent": "#f5b82e",
        "accent_hover": "#ffd166",
        "teal": "#49d6b3",
        "blue": "#c78b20",
        "danger": "#9d252d",
    },
    "Neon Cyan": {
        "canvas_bg": "#03070a",
        "bg": "#071014",
        "panel": "#0d171b",
        "panel_alt": "#101b22",
        "field": "#041014",
        "border": "#16414a",
        "fg": "#eefcff",
        "muted": "#a8c4ca",
        "accent": "#16e0d6",
        "accent_hover": "#43fff3",
        "teal": "#5ef3a3",
        "blue": "#2c9cff",
        "danger": "#c43f54",
    },
    "Graphite Pro": {
        "canvas_bg": "#060709",
        "bg": "#0d0f13",
        "panel": "#14171d",
        "panel_alt": "#191b22",
        "field": "#080a0e",
        "border": "#303744",
        "fg": "#f4f6f8",
        "muted": "#aab2bd",
        "accent": "#e5edf7",
        "accent_hover": "#ffffff",
        "teal": "#72e0c2",
        "blue": "#79a7ff",
        "danger": "#d14b5c",
    },
}

DEFAULT_THEME_NAME = "Aizen Red"
THEME_COLOR_KEYS = [
    "canvas_bg",
    "bg",
    "panel",
    "panel_alt",
    "field",
    "border",
    "fg",
    "muted",
    "accent",
    "accent_hover",
    "teal",
    "blue",
    "danger",
]


VK_CODES = {
    **{f"F{i}": 0x70 + i - 1 for i in range(1, 25)},
    **{chr(i): i for i in range(ord("A"), ord("Z") + 1)},
    **{str(i): ord(str(i)) for i in range(10)},
    "SPACE": 0x20,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
}

MODIFIERS = {
    "ALT": 0x0001,
    "CTRL": 0x0002,
    "CONTROL": 0x0002,
    "SHIFT": 0x0004,
    "WIN": 0x0008,
    "WINDOWS": 0x0008,
}


@dataclass
class PlayerKill:
    name: str
    kills: int
    key: str = ""
    ff_player_id: str = ""
    entries: int = 0


@dataclass
class IgnoredKillPlayer:
    name: str
    key: str = ""
    ignored_at: float = 0.0


@dataclass
class FFQueueEntry:
    name: str
    note: str = ""
    status: str = "Na fila"
    rooms: int = 1
    user_id: str = ""
    panel_user_id: str = ""
    ff_player_id: str = ""


@dataclass
class RaffleWinner:
    key: str
    name: str
    avatar_url: str = ""
    platform: str = ""
    supporter_tier: str = "normal"
    entries: int = 1
    bonus_reason: str = "seguidor"


@dataclass
class RaffleParticipant:
    key: str
    name: str
    avatar_url: str = ""
    platform: str = ""
    supporter_tier: str = "normal"
    entries: int = 1
    bonus_reason: str = "seguidor"
    joined_at: str = ""


@dataclass
class LiveChatMessage:
    username: str
    comment: str
    user_id: str = ""
    avatar_url: str = ""
    platform: str = "TikTok"
    message_id: str = ""
    source: str = ""
    received_at: str = ""
    supporter_tier: str = "normal"


@dataclass
class ChatCommand:
    command: str
    response: str
    enabled: bool = True
    cooldown_seconds: int = 30


@dataclass
class ChatTimer:
    name: str
    message: str
    enabled: bool = True
    interval_seconds: int = 600
    min_chat_messages: int = 5


@dataclass
class RealtimeState:
    players: list[PlayerKill]
    updated_by: str = ""
    updated_at: str = ""
    devices: list[dict[str, Any]] | None = None
    daily_ranking: list[PlayerKill] | None = None
    global_ranking: list[PlayerKill] | None = None
    ignored_players: list[IgnoredKillPlayer] | None = None
    total_players: int | None = None
    total_kills: int | None = None
    visible_players: int | None = None
    daily_players: int | None = None
    daily_kills: int | None = None
    daily_visible_players: int | None = None


@dataclass
class FFQueueState:
    entries: list[FFQueueEntry]
    updated_by: str = ""
    updated_at: str = ""
    devices: list[dict[str, Any]] | None = None
    total_members: int | None = None
    total_credits: int | None = None


@dataclass
class LivepixEvent:
    event_id: str
    kind: str
    reference: str = ""
    username: str = ""
    message: str = ""
    amount: int = 0
    currency: str = "BRL"
    proof: str = ""
    flagged: bool = False
    created_at: str = ""
    source: str = "api"


def default_device_name() -> str:
    return os.environ.get("COMPUTERNAME") or socket.gethostname() or "PC da live"


def is_hex_color(value: Any) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"#[0-9a-fA-F]{6}", value.strip()))


def normalize_hex_color(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"[0-9a-fA-F]{6}", text):
        text = f"#{text}"
    return text.lower() if is_hex_color(text) else fallback


def default_ui_theme() -> dict[str, str]:
    theme = dict(THEME_PRESETS[DEFAULT_THEME_NAME])
    theme["preset"] = DEFAULT_THEME_NAME
    theme["logo_path"] = ""
    theme["theme_schema_version"] = THEME_SCHEMA_VERSION
    return theme


def is_legacy_default_theme(raw: dict[str, Any]) -> bool:
    if str(raw.get("preset") or DEFAULT_THEME_NAME) != DEFAULT_THEME_NAME:
        return False
    for key, legacy_value in LEGACY_AIZEN_RED_THEME.items():
        if key not in raw:
            continue
        if normalize_hex_color(raw.get(key), legacy_value) != legacy_value.lower():
            return False
    return str(raw.get("theme_schema_version") or "") != THEME_SCHEMA_VERSION


def resolve_ui_theme(config: dict[str, Any]) -> dict[str, str]:
    base = default_ui_theme()
    raw = config.get("ui_theme", {})
    if not isinstance(raw, dict):
        return base

    preset = str(raw.get("preset") or DEFAULT_THEME_NAME)
    if preset in THEME_PRESETS:
        base.update(THEME_PRESETS[preset])
        base["preset"] = preset

    if not is_legacy_default_theme(raw):
        for key in THEME_COLOR_KEYS:
            base[key] = normalize_hex_color(raw.get(key), base[key])
    base["logo_path"] = str(raw.get("logo_path") or "").strip()
    base["theme_schema_version"] = THEME_SCHEMA_VERSION
    return base


def resolve_logo_path(theme: dict[str, str]) -> Path:
    raw_path = theme.get("logo_path", "").strip()
    if raw_path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        if path.exists():
            return path
    return APP_LOGO


def apply_theme_defaults(config: dict[str, Any]) -> None:
    config["ui_theme"] = resolve_ui_theme(config)


def load_config(path: Path) -> dict[str, Any]:
    defaults: dict[str, Any] = {}
    if CONFIG_EXAMPLE.exists():
        defaults = json.loads(CONFIG_EXAMPLE.read_text(encoding="utf-8-sig"))

    if not path.exists():
        if defaults:
            path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2), encoding="utf-8")
        else:
            raise FileNotFoundError(f"Config nao encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8-sig"))
    data = merge_defaults(data, defaults)
    data.setdefault("captures_dir", "captures")
    data.setdefault("debug_dir", "debug")
    data.setdefault("attach_screenshot", True)
    data.setdefault("capture_target", "primary")
    data.setdefault("ignored_players", [])
    data.setdefault("jarvis_api_token", "")
    data.setdefault("manual_kills", [])
    data.setdefault("kills_manual_scope", "daily")
    data.setdefault("kills_realtime_url", data.get("jarvis_endpoint_url", ""))
    data.setdefault("kills_realtime_auto_sync", False)
    data["kills_realtime_auto_sync"] = False
    data.setdefault("kills_realtime_poll_seconds", 15)
    data.setdefault("kills_sync_room", "principal")
    data.setdefault("freefire_kills_style_url", "")
    data.setdefault("ff_queue_realtime_url", data.get("jarvis_endpoint_url", ""))
    data.setdefault("ff_queue_auto_sync", True)
    data.setdefault("ff_queue_poll_seconds", 15)
    data.setdefault("ff_queue_room", "principal")
    data.setdefault("ff_queue_items", [])
    data.setdefault("tikfinity_ff_gifts_url", "")
    data.setdefault("tikfinity_ff_profile", "streamer1")
    data.setdefault("tikfinity_ff_enabled", True)
    data.setdefault("tikfinity_ff_coins_per_room", 50)
    data.setdefault("tikfinity_ff_token", "")
    data.setdefault("jarvis_base_url", "")
    data.setdefault("ff_overlay_realtime_url", "")
    data.setdefault("ff_overlay_auto_sync", True)
    data.setdefault("ff_overlay_config_url", "")
    data.setdefault("ff_overlay_profile", "streamer1")
    if not str(data.get("device_name", "")).strip():
        data["device_name"] = default_device_name()
    if not str(data.get("device_id", "")).strip():
        data["device_id"] = uuid.uuid4().hex
    data.setdefault("auto_update_enabled", True)
    if not str(data.get("updates_manifest_url", "")).strip():
        data["updates_manifest_url"] = DEFAULT_UPDATES_MANIFEST_URL
    apply_theme_defaults(data)
    data.setdefault("tikfinity_chat_url", "")
    data.setdefault("chat_event_source", "websocket")
    data.setdefault("chat_webhook_host", "127.0.0.1")
    data.setdefault("chat_webhook_port", 8765)
    data.setdefault("chat_webhook_token", "")
    data.setdefault("chat_websocket_url", DEFAULT_TIKFINITY_WEBSOCKET_URL)
    if not str(data.get("chat_websocket_url", "")).strip():
        data["chat_websocket_url"] = DEFAULT_TIKFINITY_WEBSOCKET_URL
    if (
        data.get("chat_event_source") == "webhook"
        and str(data.get("chat_webhook_host", "127.0.0.1")).strip() in {"", "127.0.0.1", "localhost"}
        and str(data.get("chat_webhook_port", 8765)).strip() in {"", "8765"}
        and not str(data.get("chat_webhook_token", "")).strip()
    ):
        data["chat_event_source"] = "websocket"
    data.setdefault("chat_max_messages", 250)
    data.setdefault("raffle_source_mode", "events")
    data.setdefault("raffle_command", "!sorteio")
    data.setdefault("raffle_duration_seconds", 600)
    data.setdefault("raffle_entries_normal", 1)
    data.setdefault("raffle_entries_fan", 2)
    data.setdefault("raffle_entries_super_fan", 3)
    data.setdefault("raffle_entries_gift", 5)
    data.setdefault("raffle_entries_sub", 10)
    data.setdefault("raffle_user_cooldown_seconds", 8)
    data.setdefault("raffle_include_moderators", True)
    data.setdefault("raffle_history_file", "raffle_history.json")
    data.setdefault("chat_commands_enabled", False)
    data.setdefault("chat_commands", [])
    data.setdefault("chat_timers_enabled", False)
    data.setdefault("chat_timers", [])
    data.setdefault("bot_safe_delay_seconds", 15)
    data.setdefault("bot_default_command_cooldown_seconds", 30)
    data.setdefault("bot_default_timer_interval_seconds", 600)
    data.setdefault("bot_default_timer_min_messages", 5)
    data.setdefault("bot_delivery_method", BOT_DELIVERY_TIKFINITY_DIRECT)
    data.setdefault("bot_streamerbot_ws_url", DEFAULT_STREAMERBOT_WEBSOCKET_URL)
    data.setdefault("bot_streamerbot_http_url", DEFAULT_STREAMERBOT_HTTP_URL)
    data.setdefault("bot_streamerbot_password", "")
    data.setdefault("bot_streamerbot_action_name", "Aizen TikFinity Chatbot")
    data.setdefault("bot_streamerbot_action_id", "")
    if (
        data.get("bot_delivery_method") == BOT_DELIVERY_STREAMERBOT_WEBSOCKET
        and str(data.get("bot_streamerbot_action_name", "")).strip() in {"", "Aizen TikFinity Chatbot"}
        and not str(data.get("bot_streamerbot_action_id", "")).strip()
    ):
        data["bot_delivery_method"] = BOT_DELIVERY_TIKFINITY_DIRECT
    data.setdefault("bot_ignore_usernames", "")
    data.setdefault("livepix_enabled", False)
    data.setdefault("livepix_client_id", "")
    data.setdefault("livepix_client_secret", "")
    data.setdefault(
        "livepix_scopes",
        "account:read wallet:read payments:read payments:write messages:read messages:write subscriptions:read rewards:read webhooks controls currencies:read",
    )
    data.setdefault("livepix_webhook_host", "127.0.0.1")
    data.setdefault("livepix_webhook_port", 8787)
    data.setdefault("livepix_webhook_token", "")
    data.setdefault("livepix_redirect_url", "https://livepix.gg")
    data.setdefault("livepix_goal_amount", 50000)
    data.setdefault("livepix_goal_label", "Meta da live")
    data.setdefault("livepix_currency", "BRL")
    data.setdefault("livepix_checkout_amount", 1000)
    data.setdefault("livepix_checkout_user", "Apoiador")
    data.setdefault("livepix_checkout_message", "Apoio para a live!")
    data.setdefault("livepix_plan_id", "")
    data.setdefault("livepix_plan_slug", "vip-live")
    data.setdefault("livepix_plan_name", "VIP da live")
    data.setdefault("livepix_plan_description", "Acesso aos benefícios de apoiador da live.")
    data.setdefault("livepix_subscription_recurrence", "monthly")
    data.setdefault("livepix_subscriber_email", "")
    data.setdefault("livepix_announce_in_chat", True)
    data.setdefault("livepix_public_page_file", "livepix_public.html")
    data.setdefault("ui_layout", {})
    if isinstance(data["ui_layout"], dict):
        data["ui_layout"].setdefault("participants_height", 560)
        data["ui_layout"].setdefault("events_height", 170)
        data["ui_layout"].setdefault("winner_width", 360)
        data["ui_layout"].setdefault("raffle_font_size", 13)
        data["ui_layout"].setdefault("chat_overlay_opacity", 84)
        data["ui_layout"].setdefault("chat_overlay_font_size", 14)
        data["ui_layout"].setdefault("chat_overlay_width", 430)
        data["ui_layout"].setdefault("chat_overlay_height", 640)
        data["ui_layout"].setdefault("chat_overlay_compact", True)
        data["ui_layout"].setdefault("chat_overlay_controls", True)
        data["ui_layout"].setdefault("chat_overlay_clickthrough", False)
        data["ui_layout"].setdefault("ff_overlay_opacity", 92)
        data["ui_layout"].setdefault("ff_overlay_width", 760)
        data["ui_layout"].setdefault("ff_overlay_height", 420)
        data["ui_layout"].setdefault("ff_overlay_compact", False)
        data["ui_layout"].setdefault("ff_overlay_show_queue", True)
        data["ui_layout"].setdefault("ff_overlay_show_kills", True)
    data.setdefault("name_corrections", {})
    save_config(path, data)
    return data


def merge_defaults(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(defaults)) if defaults else {}
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_defaults(value, merged[key])
        else:
            merged[key] = value
    return merged


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


def write_text_if_changed(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with WRITE_TEXT_IO_LOCK:
        try:
            cache_key = path.resolve()
        except OSError:
            cache_key = path

        signature = file_signature(path)
        if signature is not None:
            with WRITE_TEXT_CACHE_LOCK:
                cached = WRITE_TEXT_CACHE.get(cache_key)
            if cached == (signature, content):
                return

        try:
            if path.exists():
                existing = path.read_text(encoding="utf-8")
                if existing == content:
                    current_signature = file_signature(path) or signature
                    if current_signature is not None:
                        with WRITE_TEXT_CACHE_LOCK:
                            WRITE_TEXT_CACHE[cache_key] = (current_signature, content)
                    return
        except Exception:
            pass

        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(path)
        current_signature = file_signature(path)
        if current_signature is not None:
            with WRITE_TEXT_CACHE_LOCK:
                WRITE_TEXT_CACHE[cache_key] = (current_signature, content)


def save_config(path: Path, config: dict[str, Any]) -> None:
    write_text_if_changed(path, json.dumps(config, ensure_ascii=False, indent=2))


def save_config_compact(path: Path, config: dict[str, Any]) -> None:
    write_text_if_changed(path, json.dumps(config, ensure_ascii=False, separators=(",", ":")))


def append_raffle_history(path: Path, record: dict[str, Any]) -> None:
    history: list[dict[str, Any]] = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, list):
                history = loaded
        except json.JSONDecodeError:
            backup = path.with_suffix(f".invalid_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            path.replace(backup)

    history.append(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")


def _dict_value(data: Any, *path: str) -> Any:
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        if text and not (text.startswith("%") and text.endswith("%")):
            return text
    return ""


def _chat_payload_candidates(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    candidates = [payload]
    for key in ("data", "payload", "eventData", "chat", "message", "commentData", "commentInfo"):
        value = payload.get(key)
        if isinstance(value, dict):
            candidates.append(value)
            nested = value.get("data")
            if isinstance(nested, dict):
                candidates.append(nested)
    return candidates


def live_chat_event_name(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return _first_text(payload.get("event"), payload.get("type"), data.get("event"), data.get("type")).casefold()


def is_live_chat_event_payload(payload: Any) -> bool:
    event_name = live_chat_event_name(payload)
    if event_name in LIVE_CHAT_EVENT_NAMES:
        return True
    for candidate in _chat_payload_candidates(payload):
        if any(_first_text(candidate.get(field)) for field in LIVE_CHAT_TEXT_FIELDS):
            return True
        emotes = candidate.get("emotes")
        if isinstance(emotes, list) and emotes:
            return True
    return False


def compact_json_preview(payload: Any, limit: int = 700) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = str(payload)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def _fold_raffle_text(value: Any) -> str:
    text = str(value or "").casefold()
    replacements = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"[^a-z0-9_ -]+", " ", text)


def _extract_raffle_badge_texts(value: Any, parent_key: str = "") -> list[str]:
    texts: list[str] = []
    parent = _fold_raffle_text(parent_key)
    relevant_parent = any(
        marker in parent
        for marker in ("badge", "fan", "member", "sub", "support", "viewer", "role", "level")
    )
    if isinstance(value, dict):
        for key, item in value.items():
            folded_key = _fold_raffle_text(key)
            if isinstance(item, bool) and item:
                texts.append(f"{folded_key}=true")
            elif isinstance(item, (str, int, float)) and (relevant_parent or any(marker in folded_key for marker in ("badge", "fan", "member", "sub", "support", "viewer", "role", "level"))):
                texts.append(f"{folded_key} {item}")
            elif isinstance(item, (dict, list, tuple)):
                texts.extend(_extract_raffle_badge_texts(item, folded_key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            texts.extend(_extract_raffle_badge_texts(item, parent_key))
    elif relevant_parent and value is not None:
        texts.append(str(value))
    return texts


def detect_supporter_tier(payload: Any) -> str:
    if not isinstance(payload, dict):
        return "normal"

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    user = (
        data.get("user")
        if isinstance(data.get("user"), dict)
        else payload.get("user")
        if isinstance(payload.get("user"), dict)
        else {}
    )
    texts = _extract_raffle_badge_texts(payload)
    texts.extend(_extract_raffle_badge_texts(data))
    texts.extend(_extract_raffle_badge_texts(user))
    folded = " ".join(_fold_raffle_text(text) for text in texts)

    if re.search(r"\bsuper[_ -]?fan\b|\bsuper[_ -]?fa\b|\bsuper[_ -]?viewer\b|issuperfan true|is_super_fan true", folded):
        return "super_fan"
    if re.search(r"\bsubscriber true\b|\bissubscriber true\b|\bis_subscriber true\b|\bsubscribed true\b", folded):
        return "super_fan"
    if re.search(r"\bfan\b|\bfa\b|isfan true|is_fan true|\bfanbadge\b", folded):
        return "fan"
    return "normal"


def normalize_live_chat_payload(payload: Any, source: str = "") -> LiveChatMessage | None:
    if not isinstance(payload, dict):
        return None

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    candidates = _chat_payload_candidates(payload)

    def candidate_values(*fields: str) -> list[Any]:
        return [candidate.get(field) for candidate in candidates for field in fields]

    def first_candidate_dict(*fields: str) -> dict[str, Any]:
        for candidate in candidates:
            for field in fields:
                value = candidate.get(field)
                if isinstance(value, dict):
                    return value
        return {}

    author = data.get("authorMeta") if isinstance(data.get("authorMeta"), dict) else {}
    user_details = data.get("userDetails") if isinstance(data.get("userDetails"), dict) else {}
    user = (
        data.get("user")
        if isinstance(data.get("user"), dict)
        else payload.get("user")
        if isinstance(payload.get("user"), dict)
        else {}
    )
    author = author or first_candidate_dict("authorMeta")
    user_details = user_details or first_candidate_dict("userDetails", "userInfo")
    user = user or first_candidate_dict("user", "author", "sender")
    event_name = _first_text(payload.get("event"), payload.get("type"), data.get("event"), data.get("type"))
    lower_event = event_name.casefold()
    if lower_event and lower_event not in LIVE_CHAT_EVENT_NAMES:
        has_comment = any(
            _first_text(value)
            for value in (
                *candidate_values("comment", "chatmessage", "message", "msg", "text", "content", "commandParams"),
                live_chat_emote_comment(payload),
            )
        )
        if not has_comment:
            return None

    comment = _first_text(
        *candidate_values(*LIVE_CHAT_TEXT_FIELDS),
    )
    if not comment:
        comment = live_chat_emote_comment(payload)
    username = _first_text(
        *candidate_values(
            "nickname",
            "displayName",
            "chatname",
            "name",
            "username",
            "uniqueId",
            "unique_id",
            "userName",
        ),
        user.get("nickname"),
        user.get("displayName"),
        user.get("name"),
        user.get("username"),
        user.get("uniqueId"),
        user.get("unique_id"),
        author.get("nickname"),
        author.get("nickName"),
        author.get("name"),
        author.get("uniqueId"),
        author.get("unique_id"),
        user_details.get("nickname"),
        user_details.get("displayName"),
        user_details.get("username"),
        user_details.get("uniqueId"),
    )
    if not comment:
        return None
    if not username:
        username = _first_text(
            *candidate_values("userId", "userid", "user_id"),
            user.get("userId"),
            user.get("userid"),
            user.get("id"),
            author.get("userId"),
            author.get("id"),
            user_details.get("userId"),
            user_details.get("id"),
            "TikTok",
        )

    user_id = _first_text(
        *candidate_values("userId", "userid", "user_id", "id"),
        user.get("userId"),
        user.get("userid"),
        user.get("id"),
        author.get("userId"),
        author.get("id"),
        user_details.get("userId"),
        user_details.get("id"),
    )
    avatar_url = _first_text(
        *candidate_values(
            "profilePicturUrl",
            "profilePictureUrl",
            "profilePicture",
            "profileImageUrl",
            "avatarUrl",
            "avatar",
            "imageUrl",
            "image",
            "photo",
        ),
        user.get("profilePicturUrl"),
        user.get("profilePictureUrl"),
        user.get("profilePicture"),
        user.get("profileImageUrl"),
        user.get("avatarUrl"),
        user.get("avatar"),
        author.get("profilePictureUrl"),
        author.get("avatar"),
        author.get("image"),
        user_details.get("profilePictureUrl"),
        user_details.get("avatar"),
    )
    platform = _first_text(
        *candidate_values("platform", "source", "network"),
        event_name if event_name and "tiktok" in source.casefold() else "",
    )
    message_id = _first_text(
        *candidate_values("messageId", "msgId", "mid", "id", "timestamp", "ts"),
    )
    return LiveChatMessage(
        username=username,
        comment=comment,
        user_id=user_id,
        avatar_url=avatar_url,
        platform=platform or "TikTok",
        message_id=message_id,
        source=source,
        received_at=datetime.now().strftime("%H:%M:%S"),
        supporter_tier=detect_supporter_tier(payload),
    )


class LocalChatWebhookServer:
    def __init__(self, host: str, port: int, token: str, callback: callable, log: callable):
        self.host = host or "127.0.0.1"
        self.port = int(port)
        self.token = token.strip()
        self.callback = callback
        self.log = log
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.server:
            return

        parent = self

        class ReusableServer(ThreadingHTTPServer):
            allow_reuse_address = True

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def _write_json(self, status: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aizen-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _authorized(self) -> bool:
                if not parent.token:
                    return True
                parsed = urlparse(self.path)
                query_token = parse_qs(parsed.query).get("token", [""])[0]
                header_token = self.headers.get("X-Aizen-Token", "")
                provided = header_token or query_token
                return secrets.compare_digest(provided, parent.token)

            def do_OPTIONS(self) -> None:
                self._write_json(200, {"ok": True})

            def do_GET(self) -> None:
                self._write_json(200, {"ok": True, "app": APP_NAME, "version": APP_VERSION})

            def do_POST(self) -> None:
                if not self._authorized():
                    self._write_json(401, {"ok": False, "error": "unauthorized"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                raw_body = self.rfile.read(max(0, min(length, 2_000_000)))
                if not raw_body:
                    self._write_json(400, {"ok": False, "error": "empty_body"})
                    return
                try:
                    parsed = json.loads(raw_body.decode("utf-8-sig"))
                except Exception as exc:
                    self._write_json(400, {"ok": False, "error": f"invalid_json: {exc}"})
                    return
                events = parsed if isinstance(parsed, list) else [parsed]
                accepted = 0
                for event in events:
                    if isinstance(event, dict):
                        parent.callback(event, "TikFinity Webhook")
                        accepted += 1
                self._write_json(200, {"ok": True, "accepted": accepted})

        self.server = ReusableServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="AizenChatWebhook", daemon=True)
        self.thread.start()
        self.log(f"Webhook de chat ouvindo em http://{self.host}:{self.port}/api/chat-event")

    def stop(self) -> None:
        if not self.server:
            return
        try:
            self.server.shutdown()
            self.server.server_close()
        finally:
            self.server = None
            self.thread = None


def livepix_events_path(config_path: Path) -> Path:
    return config_path.with_name("livepix_events.json")


def livepix_events_to_payload(events: list[LivepixEvent]) -> list[dict[str, Any]]:
    return [
        {
            "event_id": event.event_id,
            "kind": event.kind,
            "reference": event.reference,
            "username": event.username,
            "message": event.message,
            "amount": event.amount,
            "currency": event.currency,
            "proof": event.proof,
            "flagged": event.flagged,
            "created_at": event.created_at,
            "source": event.source,
        }
        for event in events
    ]


LIVEPIX_MONTH_NAMES = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)


def livepix_first_value(mapping: Any, paths: tuple[tuple[str, ...], ...], default: Any = None) -> Any:
    if not isinstance(mapping, dict):
        return default
    for path in paths:
        current: Any = mapping
        for key in path:
            if not isinstance(current, dict) or key not in current:
                current = None
                break
            current = current.get(key)
        if current not in (None, ""):
            return current
    return default


def livepix_text_value(value: Any) -> str:
    if isinstance(value, dict):
        value = livepix_first_value(
            value,
            (
                ("displayName",),
                ("username",),
                ("name",),
                ("nickname",),
                ("email",),
                ("message",),
                ("text",),
                ("content",),
                ("comment",),
                ("description",),
            ),
        )
    if isinstance(value, (list, tuple, set)):
        return ""
    return _first_text(value)


def livepix_first_text_from(mapping: Any, paths: tuple[tuple[str, ...], ...]) -> str:
    values = []
    for path in paths:
        values.append(livepix_first_value(mapping, (path,)))
    return _first_text(*(livepix_text_value(value) for value in values))


def livepix_amount_cents(value: Any) -> int:
    if isinstance(value, dict):
        value = livepix_first_value(
            value,
            (
                ("amount",),
                ("amountCents",),
                ("value",),
                ("valueCents",),
                ("total",),
                ("totalAmount",),
                ("grossAmount",),
                ("netAmount",),
                ("balance",),
            ),
        )
    if value in (None, ""):
        return 0
    try:
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return 0
            has_decimal_marker = bool(re.search(r"\d[,.]\d{1,2}\b", text)) or any(mark in text for mark in ("R$", "$", "BRL"))
            cleaned = re.sub(r"[^0-9,.-]", "", text)
            if has_decimal_marker:
                if "," in cleaned and "." in cleaned:
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                elif "," in cleaned:
                    cleaned = cleaned.replace(",", ".")
                return max(0, int(round(float(cleaned) * 100)))
            return max(0, int(float(cleaned)))
        if isinstance(value, float):
            return max(0, int(round(value * 100 if abs(value) < 1000 and not value.is_integer() else value)))
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def livepix_parse_datetime(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now()
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        try:
            timestamp = float(text)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp)
        except (OSError, OverflowError, ValueError):
            return datetime.now()
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    except ValueError:
        for pattern in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
            try:
                return datetime.strptime(text, pattern)
            except ValueError:
                continue
    return datetime.now()


def format_livepix_date_label(value: Any) -> str:
    parsed = livepix_parse_datetime(value)
    month = LIVEPIX_MONTH_NAMES[parsed.month - 1]
    return f"{parsed.day} de {month} de {parsed.year}"


def format_livepix_time_label(value: Any) -> str:
    return livepix_parse_datetime(value).strftime("%H:%M")


def parse_livepix_event(payload: Any, kind_hint: str = "payment", source: str = "api") -> LivepixEvent | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    resource = data.get("resource") if isinstance(data.get("resource"), dict) else {}
    user = livepix_first_value(data, (("user",), ("payer",), ("donor",), ("customer",), ("subscriber",), ("supporter",)), {})
    message = livepix_first_value(data, (("message",), ("comment",), ("description",), ("text",), ("content",)), {})
    kind = livepix_first_text_from(
        data,
        (
            ("kind",),
            ("type",),
            ("event",),
            ("resource", "type"),
            ("transaction", "type"),
        ),
    ) or kind_hint or "payment"
    kind = kind.strip().lower()
    event_id = livepix_first_text_from(
        data,
        (
            ("event_id",),
            ("eventId",),
            ("id",),
            ("uuid",),
            ("resource", "id"),
            ("payment", "id"),
            ("message", "id"),
            ("subscription", "id"),
            ("transaction", "id"),
            ("reference",),
            ("resource", "reference"),
        ),
    )
    reference = livepix_first_text_from(data, (("reference",), ("resource", "reference"), ("txid",), ("transaction", "id"))) or event_id
    if not event_id and not reference:
        return None
    amount = livepix_amount_cents(
        livepix_first_value(
            data,
            (
                ("amount",),
                ("amountCents",),
                ("value",),
                ("valueCents",),
                ("total",),
                ("totalAmount",),
                ("grossAmount",),
                ("netAmount",),
                ("resource", "amount"),
                ("payment", "amount"),
                ("message", "amount"),
                ("subscription", "amount"),
                ("plan", "amount"),
                ("transaction", "amount"),
                ("receivable", "amount"),
            ),
        )
    )
    username = livepix_first_text_from(
        data,
        (
            ("username",),
            ("displayName",),
            ("name",),
            ("nickname",),
            ("payer", "username"),
            ("payer", "displayName"),
            ("payer", "name"),
            ("donor", "username"),
            ("donor", "displayName"),
            ("donor", "name"),
            ("customer", "username"),
            ("customer", "displayName"),
            ("customer", "name"),
            ("user", "username"),
            ("user", "displayName"),
            ("user", "name"),
            ("subscriber", "username"),
            ("subscriber", "displayName"),
            ("subscriber", "name"),
        ),
    ) or livepix_text_value(user)
    event_message = livepix_first_text_from(
        data,
        (
            ("message", "message"),
            ("message", "text"),
            ("message", "content"),
            ("comment",),
            ("description",),
            ("text",),
            ("content",),
            ("payment", "message"),
            ("subscription", "message"),
        ),
    ) or livepix_text_value(message)
    created_at = livepix_first_text_from(
        data,
        (
            ("createdAt",),
            ("created_at",),
            ("paidAt",),
            ("paid_at",),
            ("updatedAt",),
            ("timestamp",),
            ("date",),
            ("resource", "createdAt"),
            ("transaction", "createdAt"),
        ),
    ) or datetime.now().isoformat(timespec="seconds")
    return LivepixEvent(
        event_id=event_id or reference,
        kind=kind,
        reference=reference,
        username=username,
        message=event_message,
        amount=max(0, amount),
        currency=(livepix_first_text_from(data, (("currency",), ("resource", "currency"), ("payment", "currency"), ("message", "currency"), ("wallet", "currency"))) or "BRL").upper(),
        proof=livepix_first_text_from(data, (("proof",), ("proofUrl",), ("url",), ("redirectUrl",))),
        flagged=bool(data.get("flagged", False)),
        created_at=created_at,
        source=source,
    )


def load_livepix_events(path: Path) -> list[LivepixEvent]:
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    if not isinstance(raw, list):
        return []
    events: list[LivepixEvent] = []
    for item in raw:
        event = parse_livepix_event(item, source=str(item.get("source", "local")) if isinstance(item, dict) else "local")
        if event is not None:
            events.append(event)
    events.sort(key=lambda item: item.created_at or "", reverse=True)
    return events


def save_livepix_events(path: Path, events: list[LivepixEvent]) -> None:
    payload = livepix_events_to_payload(events[:LIVEPIX_EVENT_STORAGE_LIMIT])
    write_text_if_changed(path, json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def format_livepix_amount(amount: int, currency: str = "BRL") -> str:
    value = max(0, int(amount or 0)) / 100
    symbol = "R$" if str(currency).upper() == "BRL" else str(currency).upper()
    if symbol == "R$":
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:.2f} {symbol}"


LIVEPIX_DNS_FALLBACK_IPS = {
    "oauth.livepix.gg": ("104.20.20.235", "172.66.174.70"),
    "api.livepix.gg": ("104.20.20.235", "172.66.174.70"),
}
LIVEPIX_DNS_FALLBACK_LOCK = threading.Lock()


def livepix_is_dns_error(exc: Exception) -> bool:
    error_text = str(exc)
    return (
        "NameResolutionError" in error_text
        or "Failed to resolve" in error_text
        or "getaddrinfo failed" in error_text
    )


def livepix_request_with_dns_fallback(
    method: str,
    url: str,
    log: callable | None = None,
    **kwargs: Any,
) -> requests.Response:
    kwargs.setdefault("timeout", 18)
    try:
        return requests.request(method, url, **kwargs)
    except requests.ConnectionError as exc:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        fallback_ips = LIVEPIX_DNS_FALLBACK_IPS.get(host)
        if not fallback_ips or not livepix_is_dns_error(exc):
            raise
        if log is not None:
            log(f"Livepix DNS local falhou para {host}; usando fallback interno.")
        original_getaddrinfo = socket.getaddrinfo

        def fallback_getaddrinfo(
            query_host: Any,
            port: Any,
            family: int = 0,
            socktype: int = 0,
            proto: int = 0,
            flags: int = 0,
        ) -> list[Any]:
            clean_host = str(query_host).strip("[]").lower()
            if clean_host == host:
                resolved_socktype = socktype or socket.SOCK_STREAM
                resolved_proto = proto or socket.IPPROTO_TCP
                return [
                    (socket.AF_INET, resolved_socktype, resolved_proto, "", (ip_address, int(port or 443)))
                    for ip_address in fallback_ips
                ]
            return original_getaddrinfo(query_host, port, family, socktype, proto, flags)

        with LIVEPIX_DNS_FALLBACK_LOCK:
            socket.getaddrinfo = fallback_getaddrinfo
            try:
                return requests.request(method, url, **kwargs)
            finally:
                socket.getaddrinfo = original_getaddrinfo


class LivepixApiClient:
    api_base_url = "https://api.livepix.gg/v2"
    token_url = "https://oauth.livepix.gg/oauth2/token"

    def __init__(self, client_id: str, client_secret: str, scopes: str, log: callable | None = None):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.scopes = scopes.strip()
        self.log = log
        self.access_token = ""
        self.expires_at = 0.0

    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def token(self) -> str:
        if not self.enabled():
            raise ValueError("Informe client_id e client_secret da Livepix.")
        if self.access_token and time.time() < self.expires_at - 60:
            return self.access_token
        token_payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": self.scopes,
        }
        response: requests.Response | None = None
        for attempt in range(3):
            try:
                response = livepix_request_with_dns_fallback(
                    "POST",
                    self.token_url,
                    log=self.log,
                    data=token_payload,
                    headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
                    timeout=20,
                )
                break
            except (requests.ConnectionError, requests.Timeout) as exc:
                if attempt >= 2:
                    raise
                if self.log is not None:
                    self.log(f"Livepix rede instavel ao gerar token; tentando novamente ({attempt + 2}/3): {exc}")
                time.sleep(1.5 * (attempt + 1))
        if response is None:
            raise RuntimeError("Livepix nao retornou resposta ao gerar token.")
        response.raise_for_status()
        payload = response.json()
        self.access_token = str(payload.get("access_token", ""))
        self.expires_at = time.time() + int(payload.get("expires_in", 3600) or 3600)
        if not self.access_token:
            raise ValueError("Livepix nao retornou access_token.")
        return self.access_token

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self.token()}"
        headers["User-Agent"] = f"{APP_NAME}/{APP_VERSION}"
        response = livepix_request_with_dns_fallback(
            method,
            f"{self.api_base_url}{path}",
            log=self.log,
            headers=headers,
            timeout=25,
            **kwargs,
        )
        response.raise_for_status()
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()

    def account(self) -> dict[str, Any]:
        return self.request("GET", "/account").get("data", {})

    def payments(self, limit: int = 50) -> list[LivepixEvent]:
        payload = self.request("GET", "/payments", params={"limit": limit})
        return [event for item in payload.get("data", []) if (event := parse_livepix_event(item, "payment", "api"))]

    def payment(self, payment_id: str) -> LivepixEvent | None:
        payload = self.request("GET", f"/payments/{payment_id}")
        return parse_livepix_event(payload.get("data", {}), "payment", "api")

    def messages(self, limit: int = 50) -> list[LivepixEvent]:
        payload = self.request("GET", "/messages", params={"limit": limit})
        return [event for item in payload.get("data", []) if (event := parse_livepix_event(item, "message", "api"))]

    def message(self, message_id: str) -> LivepixEvent | None:
        payload = self.request("GET", f"/messages/{message_id}")
        return parse_livepix_event(payload.get("data", {}), "message", "api")

    def wallet(self) -> list[dict[str, Any]]:
        data = self.request("GET", "/wallet").get("data", [])
        return data if isinstance(data, list) else []

    def wallet_transactions(self, currency: str, limit: int = 30) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/wallet/{currency}/transactions", params={"limit": limit})
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def wallet_receivables(self, currency: str, limit: int = 30) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/wallet/{currency}/receivables", params={"limit": limit})
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def currencies(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/currencies")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def plans(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/subscriptions/plans")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def create_plan(self, slug: str, name: str, description: str, amount: int) -> dict[str, Any]:
        return self.request(
            "POST",
            "/subscriptions/plans",
            json={
                "slug": slug,
                "name": name,
                "description": description,
                "amount": amount,
            },
        ).get("data", {})

    def subscriptions(self, limit: int = 50) -> list[dict[str, Any]]:
        payload = self.request("GET", "/subscriptions", params={"limit": limit})
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def create_subscription(
        self,
        plan_id: str,
        recurrence: str,
        username: str,
        email: str,
        redirect_url: str,
    ) -> dict[str, Any]:
        subscriber = {"username": username}
        if email.strip():
            subscriber["email"] = email.strip()
        return self.request(
            "POST",
            "/subscriptions",
            json={
                "planId": plan_id,
                "recurrence": recurrence,
                "subscriber": subscriber,
                "redirectUrl": redirect_url,
            },
        ).get("data", {})

    def subscription(self, subscription_id: str) -> LivepixEvent | None:
        payload = self.request("GET", f"/subscriptions/{subscription_id}")
        return parse_livepix_event(payload.get("data", {}), "subscription", "api")

    def rewards(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/rewards")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def reward_grants(self, reward_id: str) -> list[dict[str, Any]]:
        payload = self.request("GET", f"/rewards/{reward_id}/grants")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def controls(self) -> dict[str, Any]:
        return self.request("GET", "/controls").get("data", {})

    def set_autoplay(self, enabled: bool) -> None:
        self.request("PATCH", "/controls", json={"autoPlay": bool(enabled)})

    def skip_alert(self) -> None:
        self.request("POST", "/controls/skip")

    def replay_alert(self) -> None:
        self.request("POST", "/controls/replay")

    def create_payment(self, amount: int, currency: str, redirect_url: str) -> dict[str, Any]:
        return self.request("POST", "/payments", json={"amount": amount, "currency": currency, "redirectUrl": redirect_url}).get("data", {})

    def create_message(self, username: str, message: str, amount: int, currency: str, redirect_url: str) -> dict[str, Any]:
        return self.request(
            "POST",
            "/messages",
            json={
                "username": username,
                "message": message,
                "amount": amount,
                "currency": currency,
                "redirectUrl": redirect_url,
            },
        ).get("data", {})

    def webhooks(self) -> list[dict[str, Any]]:
        payload = self.request("GET", "/webhooks")
        data = payload.get("data", [])
        return data if isinstance(data, list) else []

    def create_webhook(self, url: str) -> dict[str, Any]:
        return self.request("POST", "/webhooks", json={"url": url}).get("data", {})


class LocalLivepixWebhookServer:
    def __init__(self, host: str, port: int, token: str, callback: callable, log: callable):
        self.host = host or "127.0.0.1"
        self.port = int(port)
        self.token = token.strip()
        self.callback = callback
        self.log = log
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.server:
            return
        parent = self

        class ReusableServer(ThreadingHTTPServer):
            allow_reuse_address = True

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def _write_json(self, status: int, payload: dict[str, Any]) -> None:
                raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Aizen-Token")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def _authorized(self) -> bool:
                if not parent.token:
                    return True
                parsed = urlparse(self.path)
                query_token = parse_qs(parsed.query).get("token", [""])[0]
                provided = self.headers.get("X-Aizen-Token", "") or query_token
                return secrets.compare_digest(provided, parent.token)

            def do_OPTIONS(self) -> None:
                self._write_json(200, {"ok": True})

            def do_GET(self) -> None:
                self._write_json(200, {"ok": True, "app": APP_NAME, "endpoint": "livepix"})

            def do_POST(self) -> None:
                if not self._authorized():
                    self._write_json(401, {"ok": False, "error": "unauthorized"})
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                raw_body = self.rfile.read(max(0, min(length, 2_000_000)))
                try:
                    payload = json.loads(raw_body.decode("utf-8-sig"))
                except Exception as exc:
                    self._write_json(400, {"ok": False, "error": f"invalid_json: {exc}"})
                    return
                parent.callback(payload)
                self._write_json(200, {"ok": True})

        self.server = ReusableServer((self.host, self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, name="AizenLivepixWebhook", daemon=True)
        self.thread.start()
        self.log(f"Webhook Livepix ouvindo em http://{self.host}:{self.port}/api/livepix")

    def stop(self) -> None:
        if not self.server:
            return
        try:
            self.server.shutdown()
            self.server.server_close()
        finally:
            self.server = None
            self.thread = None


def normalize_tikfinity_websocket_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return DEFAULT_TIKFINITY_WEBSOCKET_URL
    if "tikfinity.zerody.one/widget" in text or "socialstream.ninja" in text:
        raise ValueError(
            "Esse campo precisa da URL Event API do TikFinity, nao da URL do widget/chat. "
            f"Use {DEFAULT_TIKFINITY_WEBSOCKET_URL}"
        )
    if "://" not in text:
        text = f"ws://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise ValueError(f"URL WebSocket invalida. Use {DEFAULT_TIKFINITY_WEBSOCKET_URL}")
    if parsed.hostname.casefold() == "localhost":
        netloc = "127.0.0.1"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        parsed = parsed._replace(netloc=netloc)
    if not parsed.path:
        parsed = parsed._replace(path="/")
    return parsed.geturl()


def normalize_streamerbot_websocket_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return DEFAULT_STREAMERBOT_WEBSOCKET_URL
    if "://" not in text:
        text = f"ws://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise ValueError(f"URL WebSocket do Streamer.bot invalida. Use {DEFAULT_STREAMERBOT_WEBSOCKET_URL}")
    if not parsed.path:
        parsed = parsed._replace(path="/")
    return parsed.geturl()


def is_address_in_use_error(exc: BaseException) -> bool:
    return (
        getattr(exc, "errno", None) == errno.EADDRINUSE
        or getattr(exc, "errno", None) == errno.EACCES
        or getattr(exc, "winerror", None) == 10048
        or getattr(exc, "winerror", None) == 10013
        or getattr(exc, "errno", None) == 10048
        or getattr(exc, "errno", None) == 10013
    )


def streamerbot_websocket_url_with_port(url: str, port: int) -> str:
    parsed = urlparse(normalize_streamerbot_websocket_url(url))
    host = parsed.hostname or "127.0.0.1"
    if host.casefold() in {"localhost", "::1"}:
        host = "127.0.0.1"
    netloc = f"{host}:{port}"
    return parsed._replace(netloc=netloc, path=parsed.path or "/").geturl()


def tikfinity_direct_bridge_url_candidates(url: str) -> list[str]:
    normalized = normalize_streamerbot_websocket_url(url)
    parsed = urlparse(normalized)
    preferred_port = parsed.port or 8080
    ports = [preferred_port]
    for fallback_port in TIKFINITY_DIRECT_FALLBACK_PORTS:
        if fallback_port not in ports:
            ports.append(fallback_port)
    candidates: list[str] = []
    for port in ports:
        candidate = streamerbot_websocket_url_with_port(normalized, port)
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def normalize_streamerbot_http_url(url: str) -> str:
    text = str(url or "").strip()
    if not text:
        return DEFAULT_STREAMERBOT_HTTP_URL
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError(f"URL HTTP do Streamer.bot invalida. Use {DEFAULT_STREAMERBOT_HTTP_URL}")
    return text.rstrip("/")


BOT_DELIVERY_METHOD_LABELS = {
    BOT_DELIVERY_TIKFINITY_DIRECT: "TikFinity direto",
    BOT_DELIVERY_STREAMERBOT_WEBSOCKET: "Streamer.bot WebSocket",
    BOT_DELIVERY_STREAMERBOT_HTTP: "Streamer.bot HTTP",
}
BOT_DELIVERY_METHOD_OPTIONS = [
    BOT_DELIVERY_METHOD_LABELS[BOT_DELIVERY_TIKFINITY_DIRECT],
    BOT_DELIVERY_METHOD_LABELS[BOT_DELIVERY_STREAMERBOT_WEBSOCKET],
    BOT_DELIVERY_METHOD_LABELS[BOT_DELIVERY_STREAMERBOT_HTTP],
]


def bot_delivery_method_label(method: Any) -> str:
    return BOT_DELIVERY_METHOD_LABELS.get(str(method or ""), BOT_DELIVERY_METHOD_LABELS[BOT_DELIVERY_TIKFINITY_DIRECT])


def bot_delivery_method_from_label(label: Any) -> str:
    text = str(label or "").strip()
    for key, value in BOT_DELIVERY_METHOD_LABELS.items():
        if value == text:
            return key
    return BOT_DELIVERY_TIKFINITY_DIRECT


def parse_chat_commands_payload(payload: Any) -> list[ChatCommand]:
    commands: list[ChatCommand] = []
    if not isinstance(payload, list):
        return commands
    for item in payload:
        if not isinstance(item, dict):
            continue
        command = normalize_chat_command(item.get("command", ""))
        response = str(item.get("response", "")).strip()
        if not command or not response:
            continue
        try:
            cooldown = int(float(str(item.get("cooldown_seconds", 30)).replace(",", ".")))
        except ValueError:
            cooldown = 30
        commands.append(
            ChatCommand(
                command=command,
                response=response,
                enabled=bool(item.get("enabled", True)),
                cooldown_seconds=max(0, cooldown),
            )
        )
    return commands


def clean_chat_command_text(value: Any) -> str:
    text = str(value or "")
    replacements = {
        "\ufeff": "",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\u2060": "",
        "\uff01": "!",
        "\ufe57": "!",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r"\s+", " ", text).strip()


def normalize_chat_command(command: Any) -> str:
    text = clean_chat_command_text(command)
    if not text:
        return ""
    text = text.split(maxsplit=1)[0].lstrip("`'\"“”‘’([{")
    if not text.startswith("!"):
        text = f"!{text}"
    match = re.match(r"!([^\s,;:!?]+)", text)
    if not match:
        return ""
    return f"!{match.group(1)}".casefold()


def chat_command_payload(commands: list[ChatCommand]) -> list[dict[str, Any]]:
    return [
        {
            "command": command.command,
            "response": command.response,
            "enabled": bool(command.enabled),
            "cooldown_seconds": int(command.cooldown_seconds),
        }
        for command in commands
        if command.command and command.response
    ]


def parse_chat_timers_payload(payload: Any) -> list[ChatTimer]:
    timers: list[ChatTimer] = []
    if not isinstance(payload, list):
        return timers
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = re.sub(r"\s+", " ", str(item.get("name", "")).strip())
        message = re.sub(r"\s+", " ", str(item.get("message", "")).strip())
        if not name or not message:
            continue
        try:
            interval = int(float(str(item.get("interval_seconds", 600)).replace(",", ".")))
        except ValueError:
            interval = 600
        try:
            min_messages = int(float(str(item.get("min_chat_messages", 5)).replace(",", ".")))
        except ValueError:
            min_messages = 5
        timers.append(
            ChatTimer(
                name=name[:80],
                message=message,
                enabled=bool(item.get("enabled", True)),
                interval_seconds=max(60, interval),
                min_chat_messages=max(0, min_messages),
            )
        )
    return timers


def chat_timer_payload(timers: list[ChatTimer]) -> list[dict[str, Any]]:
    return [
        {
            "name": timer.name,
            "message": timer.message,
            "enabled": bool(timer.enabled),
            "interval_seconds": int(timer.interval_seconds),
            "min_chat_messages": int(timer.min_chat_messages),
        }
        for timer in timers
        if timer.name and timer.message
    ]


def chat_command_token(message_text: str) -> tuple[str, str]:
    text = clean_chat_command_text(message_text)
    if not text:
        return "", ""
    for token_match in re.finditer(r"\S+", text):
        raw_token = token_match.group(0)
        clean_token = raw_token.lstrip("`'\"“”‘’([{")
        if clean_token.startswith("@"):
            continue
        if not clean_token.startswith("!"):
            return "", ""
        segment = text[token_match.start():]
        command_match = re.match(r"[`'\"“”‘’([{]*!(?P<name>[^\s,;:!?]+)[,;:!?]*", segment)
        if not command_match:
            return "", ""
        token = normalize_chat_command(f"!{command_match.group('name')}")
        args = segment[command_match.end():].strip()
        return token, args
    return "", ""


def render_chat_command_response(template: str, message: LiveChatMessage, command: str, args: str) -> str:
    replacements = {
        "{user}": message.username,
        "{username}": message.username,
        "{nick}": message.username,
        "{command}": command,
        "{args}": args,
        "{message}": message.comment,
        "{platform}": message.platform or "Live",
        "{time}": datetime.now().strftime("%H:%M:%S"),
    }
    output = str(template or "")
    for marker, value in replacements.items():
        output = output.replace(marker, str(value))
    return re.sub(r"\s+", " ", output).strip()


WEBSOCKET_ACCEPT_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def websocket_accept_value(key: str) -> str:
    digest = hashlib.sha1((key + WEBSOCKET_ACCEPT_GUID).encode("ascii")).digest()
    return base64.b64encode(digest).decode("ascii")


def websocket_frame(opcode: int, payload: bytes | str = b"", mask: bool = False) -> bytes:
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    payload_length = len(payload)
    first_byte = 0x80 | (opcode & 0x0F)
    mask_bit = 0x80 if mask else 0
    if payload_length < 126:
        header = bytes([first_byte, mask_bit | payload_length])
    elif payload_length <= 0xFFFF:
        header = bytes([first_byte, mask_bit | 126]) + payload_length.to_bytes(2, "big")
    else:
        header = bytes([first_byte, mask_bit | 127]) + payload_length.to_bytes(8, "big")
    if not mask:
        return header + payload
    mask_key = secrets.token_bytes(4)
    masked_payload = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
    return header + mask_key + masked_payload


def recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = sock.recv(remaining)
        if not chunk:
            raise ConnectionError("Conexao WebSocket encerrada.")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_websocket_frame(sock: socket.socket) -> tuple[int, bytes]:
    first_byte, second_byte = recv_exact(sock, 2)
    opcode = first_byte & 0x0F
    payload_length = second_byte & 0x7F
    if payload_length == 126:
        payload_length = int.from_bytes(recv_exact(sock, 2), "big")
    elif payload_length == 127:
        payload_length = int.from_bytes(recv_exact(sock, 8), "big")
    mask = recv_exact(sock, 4) if second_byte & 0x80 else b""
    payload = recv_exact(sock, payload_length) if payload_length else b""
    if mask:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, payload


def is_local_websocket_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").casefold()
    return parsed.scheme == "ws" and host in {"127.0.0.1", "localhost", "::1"}


def is_winsock_provider_error(error: Any) -> bool:
    text = str(error).casefold()
    return (
        "10106" in text
        or "provedor de serviços" in text
        or "winsock" in text and "recus" in text
        or "provider" in text and ("load" in text or "initialized" in text)
    )


def is_windows_powershell_loader_error(error: Any) -> bool:
    text = str(error).casefold()
    normalized = re.sub(r"\s+", " ", text)
    compact = re.sub(r"[\s\x00]+", "", text)
    return (
        "80090010" in normalized
        or "80090010" in compact
        or "erro interno do windows powershell" in normalized
        or "falha no carregamento do windows powershell" in normalized
        or "errointernodowindowspowershell" in compact
        or "falhanocarregamentodowindowspowershell" in compact
        or "windowspowershell" in compact and "falhanocarregamento" in compact
    )


def clean_pyinstaller_subprocess_env() -> dict[str, str]:
    clean_env = os.environ.copy()
    for key in list(clean_env):
        if key.startswith("_PYI") or key in {"PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY"}:
            clean_env.pop(key, None)
    clean_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if clean_env.get("PATH"):
        clean_env["PATH"] = ";".join(
            part for part in clean_env["PATH"].split(";") if part and not re.search(r"_MEI\d+", part, re.IGNORECASE)
        )
    return clean_env


def current_pyinstaller_temp_dir() -> Path | None:
    raw_path = str(getattr(sys, "_MEIPASS", "") or "").strip()
    if not raw_path:
        return None
    try:
        return Path(raw_path).resolve(strict=False)
    except OSError:
        return None


def cleanup_stale_pyinstaller_dirs(
    base_dir: Path | None = None,
    min_age_seconds: int = STALE_MEI_MIN_AGE_SECONDS,
    max_dirs: int = STALE_MEI_CLEANUP_LIMIT,
) -> int:
    if max_dirs <= 0:
        return 0
    try:
        base = Path(base_dir or APP_DIR).resolve(strict=False)
    except OSError:
        return 0
    current_temp_dir = current_pyinstaller_temp_dir()
    now = time.time()
    candidates: list[tuple[float, Path]] = []
    try:
        children = list(base.iterdir())
    except OSError:
        return 0
    for child in children:
        if not re.fullmatch(r"_MEI\d+", child.name, re.IGNORECASE):
            continue
        try:
            resolved = child.resolve(strict=False)
        except OSError:
            continue
        if resolved.parent != base or not child.is_dir():
            continue
        if current_temp_dir is not None and resolved == current_temp_dir:
            continue
        try:
            modified_at = child.stat().st_mtime
        except OSError:
            continue
        if now - modified_at < max(0, min_age_seconds):
            continue
        candidates.append((modified_at, resolved))

    removed = 0
    for _, target in sorted(candidates, key=lambda item: item[0])[:max_dirs]:
        try:
            resolved = target.resolve(strict=False)
        except OSError:
            continue
        if resolved.parent != base or not re.fullmatch(r"_MEI\d+", resolved.name, re.IGNORECASE):
            continue
        try:
            shutil.rmtree(resolved)
            removed += 1
        except OSError:
            continue
    return removed


def connect_plain_websocket_client(url: str, timeout: float = 8.0) -> socket.socket:
    parsed = urlparse(url)
    if parsed.scheme != "ws":
        raise ValueError("Cliente WebSocket interno aceita apenas ws://.")
    host = parsed.hostname or "127.0.0.1"
    if host.casefold() in {"localhost", "::1"}:
        host = "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    websocket_key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        host_header = f"{host}:{port}" if port != 80 else host
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {websocket_key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            f"User-Agent: {APP_NAME}/{APP_VERSION}\r\n"
            "\r\n"
        )
        sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response and len(response) < 16384:
            chunk = sock.recv(2048)
            if not chunk:
                raise ConnectionError("Handshake WebSocket vazio.")
            response += chunk
        response_text = response.decode("iso-8859-1", errors="replace")
        status_line = response_text.split("\r\n", 1)[0]
        if " 101 " not in f" {status_line} ":
            raise ConnectionError(f"Handshake WebSocket recusado: {status_line}")
        headers: dict[str, str] = {}
        for line in response_text.split("\r\n")[1:]:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().casefold()] = value.strip()
        expected_accept = websocket_accept_value(websocket_key)
        if headers.get("sec-websocket-accept", "") != expected_accept:
            raise ConnectionError("Handshake WebSocket com chave invalida.")
        sock.settimeout(1.0)
        return sock
    except Exception:
        try:
            sock.close()
        except OSError:
            pass
        raise


class TikfinityBridgePortInUseError(RuntimeError):
    pass


class TikfinityDirectBridgeServer:
    def __init__(self, websocket_url: str, log: callable | None = None):
        url = normalize_streamerbot_websocket_url(websocket_url)
        parsed = urlparse(url)
        if parsed.scheme != "ws":
            raise ValueError("A ponte direta do TikFinity usa ws:// local, nao wss://.")
        host = parsed.hostname or "127.0.0.1"
        if host.casefold() in {"localhost", "::1"}:
            host = "127.0.0.1"
        self.host = host
        self.port = parsed.port or 8080
        self.path = parsed.path or "/"
        self.url = f"ws://{self.host}:{self.port}{self.path}"
        self.log = log
        self.stop_event = threading.Event()
        self.server_socket: socket.socket | None = None
        self.thread: threading.Thread | None = None
        self.clients: set[socket.socket] = set()
        self.clients_lock = threading.Lock()

    def start(self) -> None:
        if self.is_running():
            return
        self.stop_event.clear()
        server_socket: socket.socket | None = None
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(8)
            server_socket.settimeout(1.0)
        except OSError as exc:
            if server_socket is not None:
                try:
                    server_socket.close()
                except OSError:
                    pass
            if is_winsock_provider_error(exc):
                raise RuntimeError(
                    "Windows/Winsock recusou abrir a ponte local do TikFinity neste processo. "
                    "Feche e abra o app novamente pelo atalho; se continuar, reinicie o Windows ou repare o Winsock."
                ) from exc
            if is_address_in_use_error(exc):
                raise TikfinityBridgePortInUseError(
                    f"A porta {self.port} ja esta ocupada para a ponte direta do TikFinity."
                ) from exc
            raise RuntimeError(
                f"Nao consegui abrir a ponte direta em {self.url}. "
                "Feche o programa usando essa porta, ou mude a porta no TikFinity e no app."
            ) from exc
        self.server_socket = server_socket
        self.thread = threading.Thread(target=self._accept_loop, name="AizenTikFinityBridge", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        server_socket = self.server_socket
        self.server_socket = None
        if server_socket is not None:
            try:
                server_socket.close()
            except OSError:
                pass
        with self.clients_lock:
            clients = list(self.clients)
            self.clients.clear()
        for client in clients:
            try:
                client.close()
            except OSError:
                pass

    def is_running(self) -> bool:
        return self.server_socket is not None and self.thread is not None and self.thread.is_alive()

    def client_count(self) -> int:
        with self.clients_lock:
            return len(self.clients)

    def send_json_to_client(self, client: socket.socket, payload: dict[str, Any]) -> None:
        client.sendall(websocket_frame(0x1, json.dumps(payload, ensure_ascii=False)))

    def streamerbot_info_payload(self) -> dict[str, Any]:
        return {
            "instanceId": "aizen-tikfinity-direct",
            "name": APP_NAME,
            "os": "windows" if os.name == "nt" else sys.platform,
            "osVersion": platform.version(),
            "version": "0.2.5",
            "source": "websocketServer",
        }

    def streamerbot_hello_payload(self) -> dict[str, Any]:
        return {
            "request": "Hello",
            "info": self.streamerbot_info_payload(),
        }

    def streamerbot_supported_events(self) -> dict[str, list[str]]:
        return {
            "General": ["Custom"],
            "Custom": ["Event", "CodeEvent"],
            "Raw": ["Action", "SubAction", "ActionCompleted"],
            "WebsocketClient": ["Open", "Close", "Message"],
            "YouTube": ["Message", "MessageDeleted", "FirstWords", "PresentViewers"],
            "Twitch": ["ChatMessage", "ChatMessageDeleted", "FirstWord", "PresentViewers"],
            "Kick": ["ChatMessage", "FirstWords", "PresentViewers"],
        }

    def streamerbot_response_for_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = str(message.get("id") or message.get("requestId") or "")
        request = str(message.get("request") or message.get("event") or message.get("action") or "").strip()
        request_key = request.casefold()
        response: dict[str, Any] = {"id": request_id, "status": "ok"}
        if request_key in {"getinfo", "getinforequest", "hello"}:
            response["info"] = self.streamerbot_info_payload()
        elif request_key == "getevents":
            response["events"] = self.streamerbot_supported_events()
        elif request_key == "getactions":
            response["actions"] = []
            response["count"] = 0
        elif request_key in {"subscribe", "unsubscribe"}:
            response["events"] = message.get("events") or {}
        elif request_key == "authenticate":
            pass
        elif request_key == "sendmessage":
            response["message"] = message.get("message") or ""
        return response

    def broadcast_json(self, payload: dict[str, Any]) -> int:
        message = json.dumps(payload, ensure_ascii=False)
        frame = websocket_frame(0x1, message)
        with self.clients_lock:
            clients = list(self.clients)
        delivered = 0
        stale_clients: list[socket.socket] = []
        for client in clients:
            try:
                client.sendall(frame)
                delivered += 1
            except OSError:
                stale_clients.append(client)
        if stale_clients:
            with self.clients_lock:
                for client in stale_clients:
                    self.clients.discard(client)
            for client in stale_clients:
                try:
                    client.close()
                except OSError:
                    pass
        return delivered

    def _accept_loop(self) -> None:
        while not self.stop_event.is_set():
            server_socket = self.server_socket
            if server_socket is None:
                break
            try:
                client, _address = server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_client, args=(client,), name="AizenTikFinityBridgeClient", daemon=True).start()

    def _handle_client(self, client: socket.socket) -> None:
        connected = False
        connected_at = time.time()
        received_messages = 0
        try:
            client.settimeout(5.0)
            self._perform_handshake(client)
            client.settimeout(1.0)
            with self.clients_lock:
                self.clients.add(client)
                client_total = len(self.clients)
            connected = True
            self._log(f"TikFinity conectado na ponte direta ({client_total} conexao).")
            try:
                self.send_json_to_client(client, self.streamerbot_hello_payload())
            except OSError:
                return
            while not self.stop_event.is_set():
                try:
                    opcode, payload = read_websocket_frame(client)
                except socket.timeout:
                    continue
                except (ConnectionError, OSError):
                    break
                if opcode == 0x8:
                    try:
                        client.sendall(websocket_frame(0x8, payload[:125]))
                    except OSError:
                        pass
                    break
                if opcode == 0x9:
                    try:
                        client.sendall(websocket_frame(0xA, payload[:125]))
                    except OSError:
                        break
                if opcode == 0x1:
                    received_messages += 1
                    self._handle_client_text_message(client, payload)
        finally:
            if connected:
                with self.clients_lock:
                    self.clients.discard(client)
                lifetime = time.time() - connected_at
                if lifetime < 8 and received_messages == 0:
                    self._log(
                        "TikFinity encerrou a ponte apos um teste rapido. "
                        "Para envio automatico, ative Chatbot > Streamer.bot Messages no TikFinity."
                    )
                else:
                    self._log("TikFinity desconectou da ponte direta.")
            try:
                client.close()
            except OSError:
                pass

    def _handle_client_text_message(self, client: socket.socket, payload: bytes) -> None:
        try:
            message = json.loads(payload.decode("utf-8", errors="replace"))
        except Exception:
            return
        if not isinstance(message, dict):
            return
        request_id = str(message.get("id") or message.get("requestId") or "")
        request = str(message.get("request") or message.get("event") or message.get("action") or "").strip()
        if request:
            self._log(f"TikFinity ponte recebeu request Streamer.bot: {request}.")
            if request.casefold() == "subscribe":
                self._log(f"TikFinity assinou eventos Streamer.bot: {compact_json_preview(message.get('events') or message, 260)}")
        if request_id:
            try:
                self.send_json_to_client(client, self.streamerbot_response_for_request(message))
            except OSError:
                pass

    def _perform_handshake(self, client: socket.socket) -> None:
        data = b""
        while b"\r\n\r\n" not in data and len(data) < 16384:
            chunk = client.recv(2048)
            if not chunk:
                raise ConnectionError("Handshake WebSocket vazio.")
            data += chunk
        request_text = data.decode("iso-8859-1", errors="replace")
        headers: dict[str, str] = {}
        for line in request_text.split("\r\n")[1:]:
            if ":" not in line:
                continue
            name, value = line.split(":", 1)
            headers[name.strip().casefold()] = value.strip()
        websocket_key = headers.get("sec-websocket-key", "")
        if not websocket_key:
            raise ConnectionError("Handshake WebSocket sem chave.")
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {websocket_accept_value(websocket_key)}\r\n"
            "\r\n"
        )
        client.sendall(response.encode("ascii"))

    def _log(self, message: str) -> None:
        if self.log is None:
            return
        try:
            self.log(message)
        except Exception:
            pass


def streamerbot_authentication(password: str, salt: str, challenge: str) -> str:
    secret_hash = hashlib.sha256((password + salt).encode("utf-8")).digest()
    secret = base64.b64encode(secret_hash).decode("ascii")
    auth_hash = hashlib.sha256((secret + challenge).encode("utf-8")).digest()
    return base64.b64encode(auth_hash).decode("ascii")


def streamerbot_action_payload(action_name: str, action_id: str, args: dict[str, Any]) -> dict[str, Any]:
    action: dict[str, str] = {}
    if action_id.strip():
        action["id"] = action_id.strip()
    if action_name.strip():
        action["name"] = action_name.strip()
    if not action:
        raise ValueError("Configure o nome ou ID da action do Streamer.bot.")
    return {"action": action, "args": args}


def send_streamerbot_action_http(
    http_url: str,
    action_name: str,
    action_id: str,
    args: dict[str, Any],
) -> str:
    base_url = normalize_streamerbot_http_url(http_url)
    payload = streamerbot_action_payload(action_name, action_id, args)
    try:
        response = requests.post(f"{base_url}/DoAction", json=payload, timeout=8)
    except requests.ConnectionError as exc:
        raise RuntimeError(
            f"Nao consegui conectar no Streamer.bot HTTP em {base_url}. "
            "Abra o Streamer.bot e ative o HTTP Server nessa porta."
        ) from exc
    except requests.Timeout as exc:
        raise RuntimeError(f"Streamer.bot HTTP em {base_url} nao respondeu a tempo.") from exc
    if response.status_code not in {200, 202, 204}:
        raise RuntimeError(f"Streamer.bot HTTP respondeu {response.status_code}: {response.text[:180]}")
    return "Streamer.bot HTTP OK"


def send_streamerbot_action_websocket(
    websocket_url: str,
    password: str,
    action_name: str,
    action_id: str,
    args: dict[str, Any],
) -> str:
    try:
        import websocket
    except Exception as exc:
        raise RuntimeError(f"WebSocket indisponivel. Instale websocket-client: {exc}") from exc

    url = normalize_streamerbot_websocket_url(websocket_url)
    request_id = f"aizen-{uuid.uuid4().hex}"
    payload = streamerbot_action_payload(action_name, action_id, args)
    request_payload = {
        "request": "DoAction",
        "id": request_id,
        "action": payload["action"],
        "args": payload["args"],
    }
    try:
        ws = websocket.create_connection(url, timeout=8, http_no_proxy=["localhost", "127.0.0.1", "::1"])
    except Exception as exc:
        raise RuntimeError(
            f"Nao consegui conectar no Streamer.bot WebSocket em {url}. "
            "Abra o Streamer.bot e confirme Servers > WebSocket Server na porta 8080."
        ) from exc
    try:
        try:
            hello_raw = ws.recv()
            hello = json.loads(hello_raw) if hello_raw else {}
        except Exception:
            hello = {}
        authentication = hello.get("authentication") if isinstance(hello, dict) else None
        if isinstance(authentication, dict):
            if not password:
                raise RuntimeError("Streamer.bot pediu senha. Configure a senha WebSocket na aba Comandos.")
            auth_id = f"aizen-auth-{uuid.uuid4().hex}"
            auth_request = {
                "request": "Authenticate",
                "id": auth_id,
                "authentication": streamerbot_authentication(
                    password,
                    str(authentication.get("salt", "")),
                    str(authentication.get("challenge", "")),
                ),
            }
            ws.send(json.dumps(auth_request, ensure_ascii=False))
            while True:
                raw_response = ws.recv()
                auth_response = json.loads(raw_response)
                if auth_response.get("id") == auth_id:
                    if auth_response.get("status") != "ok":
                        raise RuntimeError(f"Falha ao autenticar no Streamer.bot: {compact_json_preview(auth_response)}")
                    break

        ws.send(json.dumps(request_payload, ensure_ascii=False))
        while True:
            raw_response = ws.recv()
            response = json.loads(raw_response)
            if response.get("id") != request_id:
                continue
            if response.get("status") != "ok":
                raise RuntimeError(f"Streamer.bot recusou a action: {compact_json_preview(response)}")
            return "Streamer.bot WebSocket OK"
    finally:
        try:
            ws.close()
        except Exception:
            pass


def send_tikfinity_direct_message(bridge_server: Any, args: dict[str, Any]) -> str:
    if bridge_server is None:
        raise RuntimeError("A ponte direta do TikFinity nao foi iniciada.")
    message = re.sub(r"\s+", " ", str(args.get("message") or args.get("text") or "")).strip()
    username = str(args.get("username") or args.get("user") or "Aizen").strip() or "Aizen"
    event_name = str(args.get("eventName") or "sendChatbotMessage").strip() or "sendChatbotMessage"
    event_data = dict(args)
    event_arguments = {
        "message": message,
        "text": message,
        "content": message,
        "chatMessage": message,
        "username": username,
        "user": username,
        "nick": username,
        "source": APP_NAME,
        "deliveryId": str(args.get("deliveryId") or ""),
    }
    event_arguments.update(args)
    event_data.update(
        {
            "name": event_name,
            "eventName": event_name,
            "action": event_name,
            "message": message,
            "text": message,
            "content": message,
            "chatMessage": message,
            "username": username,
            "user": username,
            "nick": username,
            "args": event_arguments,
            "arguments": event_arguments,
        }
    )
    payload = {
        "timeStamp": datetime.now().isoformat(timespec="milliseconds"),
        "event": {"source": "General", "type": "Custom"},
        "source": "General",
        "type": "Custom",
        "action": event_name,
        "request": event_name,
        "message": message,
        "text": message,
        "content": message,
        "args": event_arguments,
        "arguments": event_arguments,
        "data": event_data,
    }
    delivered = bridge_server.broadcast_json(payload)
    deadline = time.time() + TIKFINITY_DIRECT_SEND_WAIT_SECONDS
    while delivered <= 0 and time.time() < deadline:
        time.sleep(0.25)
        delivered = bridge_server.broadcast_json(payload)
    if delivered <= 0:
        bridge_url = getattr(bridge_server, "url", DEFAULT_STREAMERBOT_WEBSOCKET_URL)
        raise RuntimeError(
            f"TikFinity ainda nao conectou na ponte direta em {bridge_url}. "
            "A ponte esta aberta, mas o TikFinity nao manteve a conexao a tempo; "
            "no TikFinity, confira Setup > Streamer.bot Connection apontando para esse endereco."
        )
    suffix = "conexao" if delivered == 1 else "conexoes"
    return f"TikFinity recebeu pacote do bot ({delivered} {suffix}). {TIKFINITY_DIRECT_CHATBOT_HINT}"


def send_chatbot_message_via_streamerbot(settings: dict[str, Any], args: dict[str, Any]) -> str:
    method = str(settings.get("method") or BOT_DELIVERY_TIKFINITY_DIRECT)
    if method == BOT_DELIVERY_TIKFINITY_DIRECT:
        return send_tikfinity_direct_message(settings.get("bridge_server"), args)
    action_name = str(settings.get("action_name") or "")
    action_id = str(settings.get("action_id") or "")
    if method == BOT_DELIVERY_STREAMERBOT_HTTP:
        return send_streamerbot_action_http(str(settings.get("http_url") or ""), action_name, action_id, args)
    return send_streamerbot_action_websocket(
        str(settings.get("websocket_url") or ""),
        str(settings.get("password") or ""),
        action_name,
        action_id,
        args,
    )


class ChatWebSocketWorker:
    def __init__(self, url: str, callback: callable, log: callable):
        self.url = normalize_tikfinity_websocket_url(url)
        self.callback = callback
        self.log = log
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.ws_app: Any | None = None
        self.ws_socket: socket.socket | None = None
        self.ws_process: subprocess.Popen | None = None
        self.chat_event_count = 0
        self.other_event_count = 0
        self.config_event_logged = False
        self.last_chat_at = 0.0
        self.opened_at = 0.0
        self.windows_helper_unavailable_reason = ""

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.chat_event_count = 0
        self.other_event_count = 0
        self.config_event_logged = False
        self.last_chat_at = 0.0
        self.opened_at = 0.0
        self.thread = threading.Thread(target=self._run, name="AizenChatWebSocket", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.ws_app is not None:
            try:
                self.ws_app.close()
            except Exception:
                pass
        if self.ws_socket is not None:
            try:
                self.ws_socket.close()
            except OSError:
                pass
        if self.ws_process is not None:
            try:
                self.ws_process.terminate()
            except Exception:
                pass

    def _run(self) -> None:
        use_internal_client = is_local_websocket_url(self.url)
        websocket_module: Any | None = None
        if not use_internal_client:
            try:
                import websocket as websocket_module
            except Exception as exc:
                self.log(f"WebSocket indisponivel. Instale websocket-client: {exc}")
                return

        while not self.stop_event.is_set():
            try:
                def on_open(_ws: Any) -> None:
                    if self.stop_event.is_set():
                        return
                    self.chat_event_count = 0
                    self.other_event_count = 0
                    self.config_event_logged = False
                    self.last_chat_at = 0.0
                    self.opened_at = time.time()
                    self.log("WebSocket do TikFinity conectado. Aguardando mensagens do chat.")

                    def warn_if_no_chat() -> None:
                        time.sleep(15)
                        if not self.stop_event.is_set() and self.chat_event_count == 0:
                            self.log(
                                "WebSocket conectado, mas nenhum evento de chat chegou ainda. "
                                "Confirme que o TikFinity esta conectado na live e envie uma mensagem de teste."
                            )

                    threading.Thread(target=warn_if_no_chat, name="AizenChatWebSocketWatch", daemon=True).start()

                def on_message(_ws: Any, raw_message: str) -> None:
                    if self.stop_event.is_set():
                        return
                    try:
                        parsed = json.loads(raw_message)
                    except Exception:
                        return
                    events = parsed if isinstance(parsed, list) else [parsed]
                    for event in events:
                        if self.stop_event.is_set():
                            return
                        if isinstance(event, dict):
                            event_name = live_chat_event_name(event)
                            if event_name == "config" and not self.config_event_logged:
                                self.config_event_logged = True
                                self.log("TikFinity Event API respondeu configuracao. Conexao OK; aguardando evento chat.")
                                continue
                            if not is_live_chat_event_payload(event):
                                self.other_event_count += 1
                                connected_for = time.time() - self.opened_at if self.opened_at else 0.0
                                quiet_for = time.time() - self.last_chat_at if self.last_chat_at else 0.0
                                if self.chat_event_count == 0 and (
                                    self.other_event_count == 1
                                    or (self.other_event_count in {200, 1000} and connected_for >= 60)
                                ):
                                    self.log(
                                        "TikFinity conectado; eventos da live chegaram, mas nenhum chat legivel ainda. "
                                        "Envie uma mensagem de teste se os comandos nao responderem."
                                    )
                                elif self.chat_event_count > 0 and quiet_for >= 120 and self.other_event_count in {500, 1500}:
                                    self.log(
                                        "TikFinity segue conectado; eventos da live continuam chegando, "
                                        "mas nao houve chat novo nos ultimos minutos."
                                    )
                                continue

                            was_waiting_for_first_chat = self.chat_event_count == 0
                            self.chat_event_count += 1
                            self.other_event_count = 0
                            self.last_chat_at = time.time()
                            message = normalize_live_chat_payload(event, "TikFinity WebSocket")
                            if message is None:
                                self.log(
                                    "Evento de chat recebido, mas o app ainda nao reconheceu o formato: "
                                    f"{compact_json_preview(event)}"
                                )
                                self.callback(event, "TikFinity WebSocket")
                                continue
                            if was_waiting_for_first_chat:
                                self.log(f"Chat TikFinity reconhecido: {message.username}: {message.comment[:80]}")
                            elif self.chat_event_count <= 3:
                                self.log(f"Chat TikFinity recebido: {message.username}: {message.comment[:80]}")
                            self.callback(message, "TikFinity WebSocket")

                def on_error(_ws: Any, error: Any) -> None:
                    if not self.stop_event.is_set():
                        error_text = str(error)
                        if "getaddrinfo failed" in error_text:
                            self.log(
                                "Erro no WebSocket do TikFinity: endereco invalido ou TikFinity Event API offline. "
                                f"Use {DEFAULT_TIKFINITY_WEBSOCKET_URL} e deixe o TikFinity aberto."
                            )
                        elif "Connection refused" in error_text or "10061" in error_text:
                            self.log(
                                "Erro no WebSocket do TikFinity: conexao recusada. "
                                "Abra o TikFinity e ative a Event API antes de iniciar o chat."
                            )
                        elif is_winsock_provider_error(error):
                            self.log(
                                "Erro no WebSocket do TikFinity: Windows/Winsock recusou a conexao local. "
                                "Tentando leitor auxiliar do Windows."
                            )
                        else:
                            self.log(f"Erro no WebSocket do TikFinity: {error}")

                def on_close(_ws: Any, _code: Any, _reason: Any) -> None:
                    if not self.stop_event.is_set():
                        self.log("WebSocket do TikFinity desconectado. Tentando reconectar...")

                if use_internal_client:
                    try:
                        self._run_internal_websocket_client(on_open, on_message, on_close)
                    except Exception as exc:
                        if not is_winsock_provider_error(exc):
                            raise
                        if self.windows_helper_unavailable_reason:
                            self.log(
                                "Erro no WebSocket do TikFinity: Windows/Winsock recusou a conexao local. "
                                f"{self.windows_helper_unavailable_reason}"
                            )
                            self.stop_event.wait(15)
                            continue
                        on_error(None, exc)
                        try:
                            self._run_windows_websocket_helper(on_open, on_message, on_close)
                        except Exception as helper_exc:
                            if is_windows_powershell_loader_error(helper_exc):
                                self.windows_helper_unavailable_reason = (
                                    "Leitor auxiliar desativado porque o Windows PowerShell falhou com erro 80090010. "
                                    "Reinicie o Windows ou repare o Winsock/PowerShell para liberar conexoes locais."
                                )
                            raise
                else:
                    self.ws_app = websocket_module.WebSocketApp(
                        self.url,
                        on_open=on_open,
                        on_message=on_message,
                        on_error=on_error,
                        on_close=on_close,
                    )
                    self.ws_app.run_forever(
                        ping_interval=20,
                        ping_timeout=10,
                        http_no_proxy=["localhost", "127.0.0.1", "::1"],
                        http_proxy_host=None,
                        http_proxy_port=None,
                        proxy_type=None,
                    )
            except Exception as exc:
                if not self.stop_event.is_set():
                    on_error(None, exc)
            finally:
                self.ws_app = None
                self.ws_socket = None
                self.ws_process = None
            if not self.stop_event.is_set():
                time.sleep(3)

    def _run_internal_websocket_client(self, on_open: callable, on_message: callable, on_close: callable) -> None:
        sock = connect_plain_websocket_client(self.url, timeout=8)
        self.ws_socket = sock
        on_open(None)
        try:
            while not self.stop_event.is_set():
                try:
                    opcode, payload = read_websocket_frame(sock)
                except socket.timeout:
                    continue
                if opcode == 0x1:
                    on_message(None, payload.decode("utf-8", errors="replace"))
                elif opcode == 0x8:
                    break
                elif opcode == 0x9:
                    sock.sendall(websocket_frame(0xA, payload[:125], mask=True))
        finally:
            try:
                sock.close()
            except OSError:
                pass
            self.ws_socket = None
            if not self.stop_event.is_set():
                on_close(None, None, None)

    def _run_windows_websocket_helper(self, on_open: callable, on_message: callable, on_close: callable) -> None:
        if os.name != "nt":
            raise RuntimeError("Leitor auxiliar do Windows disponivel apenas no Windows.")
        powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        powershell_cmd = str(powershell) if powershell.exists() else "powershell.exe"
        safe_url = self.url.replace("'", "''")
        script = f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try {{
  $uri = [Uri]'{safe_url}'
  $ws = [System.Net.WebSockets.ClientWebSocket]::new()
  $ct = [Threading.CancellationToken]::None
  [void]$ws.ConnectAsync($uri, $ct).GetAwaiter().GetResult()
  [Console]::Out.WriteLine('OPEN')
  [Console]::Out.Flush()
  $buffer = New-Object byte[] 65536
  while ($ws.State -eq [System.Net.WebSockets.WebSocketState]::Open) {{
    $memory = [System.IO.MemoryStream]::new()
    try {{
      do {{
        $segment = [ArraySegment[byte]]::new($buffer)
        $result = $ws.ReceiveAsync($segment, $ct).GetAwaiter().GetResult()
        if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) {{
          exit 0
        }}
        if ($result.Count -gt 0) {{
          $memory.Write($buffer, 0, $result.Count)
        }}
      }} while (-not $result.EndOfMessage)
      if ($result.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Text) {{
        [Console]::Out.WriteLine('MSG ' + [Convert]::ToBase64String($memory.ToArray()))
        [Console]::Out.Flush()
      }}
    }} finally {{
      $memory.Dispose()
    }}
  }}
}} catch {{
  $message = $_.Exception.ToString()
  [Console]::Out.WriteLine('ERR ' + [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($message)))
  [Console]::Out.Flush()
  exit 1
}}
"""
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        process = subprocess.Popen(
            [powershell_cmd, "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            env=clean_pyinstaller_subprocess_env(),
        )
        self.ws_process = process
        opened = False
        helper_messages = 0
        self.log("Leitor auxiliar do Windows iniciado para o WebSocket local do TikFinity.")
        try:
            assert process.stdout is not None
            while not self.stop_event.is_set():
                line = process.stdout.readline()
                if line == "":
                    if process.poll() is not None:
                        break
                    time.sleep(0.05)
                    continue
                line = line.strip()
                if not line:
                    continue
                if line == "OPEN":
                    opened = True
                    on_open(None)
                    continue
                if line.startswith("MSG "):
                    try:
                        raw_message = base64.b64decode(line[4:].strip()).decode("utf-8", errors="replace")
                    except Exception as exc:
                        self.log(f"Leitor auxiliar do TikFinity recebeu mensagem invalida: {exc}")
                        continue
                    helper_messages += 1
                    on_message(None, raw_message)
                    continue
                if line.startswith("ERR "):
                    try:
                        error_message = base64.b64decode(line[4:].strip()).decode("utf-8", errors="replace")
                    except Exception:
                        error_message = line[4:].strip()
                    raise RuntimeError(f"Leitor auxiliar do TikFinity falhou: {error_message[:420]}")
                if not opened:
                    raise RuntimeError(f"Leitor auxiliar do TikFinity falhou: {line[:220]}")
                if helper_messages < 3:
                    self.log(f"Leitor auxiliar do TikFinity: {line[:180]}")
            if process.poll() not in {None, 0} and not self.stop_event.is_set():
                raise RuntimeError(f"Leitor auxiliar do TikFinity encerrou com codigo {process.returncode}.")
        finally:
            try:
                process.terminate()
            except Exception:
                pass
            self.ws_process = None
            if opened and not self.stop_event.is_set():
                on_close(None, None, None)


def parse_hotkey(hotkey: str) -> tuple[int, int]:
    modifiers = 0
    key = None
    for raw_part in re.split(r"[+\s]+", hotkey.upper().strip()):
        part = raw_part.strip()
        if not part:
            continue
        if part in MODIFIERS:
            modifiers |= MODIFIERS[part]
        elif part in VK_CODES:
            key = VK_CODES[part]
        else:
            raise ValueError(f"Tecla nao suportada no atalho: {raw_part}")

    if key is None:
        raise ValueError(f"Atalho sem tecla principal: {hotkey}")
    return modifiers, key


def scale_box(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    image_size: tuple[int, int],
    reference_size: list[int],
) -> tuple[int, int, int, int]:
    width, height = image_size
    ref_width, ref_height = reference_size
    sx = width / ref_width
    sy = height / ref_height
    return (
        round(x1 * sx),
        round(y1 * sy),
        round(x2 * sx),
        round(y2 * sy),
    )


def clean_name(text: str, corrections: dict[str, str]) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("’", "'").replace("`", "'").replace("´", "'")
    text = re.sub(r"[^\wÀ-ÿ_.' @+!&$-]", "", text, flags=re.UNICODE).strip(" -")

    normalized = text.casefold()
    for wrong, right in corrections.items():
        if normalized == wrong.casefold():
            return right
    for wrong, right in corrections.items():
        wrong_key = wrong.casefold().strip()
        if len(wrong_key) >= 4 and wrong_key in normalized:
            return right
    return text


@lru_cache(maxsize=8192)
def _normalize_player_key_cached(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip().casefold()
    return name


def normalize_player_key(name: str) -> str:
    return _normalize_player_key_cached(name)


def parse_player_list(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif isinstance(value, str):
        raw_items = re.split(r"[\n,;]+", value)
    else:
        raw_items = []
    return [str(item).strip() for item in raw_items if str(item).strip()]


def filter_ignored_players(players: list[PlayerKill], ignored_players: Any) -> list[PlayerKill]:
    ignored = {normalize_player_key(name) for name in parse_player_list(ignored_players)}
    if not ignored:
        return players
    return [player for player in players if normalize_player_key(player.name) not in ignored]


def prepare_name_crops(image: Image.Image, box: tuple[int, int, int, int]) -> list[tuple[str, Image.Image]]:
    ensure_image_processing_modules()
    crop = image.crop(box).convert("RGB")
    resized = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.LANCZOS)
    resized_5x = crop.resize((crop.width * 5, crop.height * 5), Image.Resampling.LANCZOS)
    sharp = ImageEnhance.Sharpness(resized).enhance(2.0)
    sharp_strong = ImageEnhance.Sharpness(resized).enhance(2.8)
    gray = ImageEnhance.Contrast(ImageOps.grayscale(resized)).enhance(2.0)
    bw = gray.point(lambda pixel: 0 if pixel < 140 else 255)

    arr = np.array(resized)
    hsv = cv2.cvtColor(arr, cv2.COLOR_RGB2HSV)
    white_mask = np.where((hsv[:, :, 2] > 145) & (hsv[:, :, 1] < 95), 0, 255).astype(np.uint8)
    white = Image.fromarray(white_mask)

    return [
        ("white", white),
        ("sharp", sharp),
        ("sharp_strong", sharp_strong),
        ("color", resized),
        ("color5x", resized_5x),
        ("gray", gray),
        ("bw", bw),
    ]


def run_windows_ocr(paths: list[Path]) -> dict[str, list[str]]:
    if not paths:
        return {}
    if not OCR_SCRIPT.exists():
        raise FileNotFoundError(f"Script OCR nao encontrado: {OCR_SCRIPT}")

    command = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(OCR_SCRIPT),
        *[str(path) for path in paths],
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    raw = completed.stdout.strip()
    if not raw:
        return {str(path): [] for path in paths}

    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    return {item["path"]: item.get("lines", []) for item in parsed}


def digit_templates() -> list[tuple[int, np.ndarray]]:
    ensure_image_processing_modules()
    font_candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "bahnschrift.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "seguisb.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibrib.ttf",
    ]
    templates: list[tuple[int, np.ndarray]] = []
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        font = ImageFont.truetype(str(font_path), 48)
        for digit in range(10):
            canvas = Image.new("L", (90, 90), 255)
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), str(digit), font=font)
            draw.text((8 - bbox[0], 8 - bbox[1]), str(digit), font=font, fill=0)
            arr = np.array(canvas)
            mask = np.where(arr < 128, 255, 0).astype(np.uint8)
            normalized = normalize_digit_mask(mask)
            if normalized is not None:
                templates.append((digit, normalized))
    return templates


def symbol_templates(symbols: tuple[str, ...] = ("/",)) -> list[tuple[str, np.ndarray]]:
    ensure_image_processing_modules()
    font_candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "bahnschrift.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "seguisb.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arialbd.ttf",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "calibrib.ttf",
    ]
    templates: list[tuple[str, np.ndarray]] = []
    for font_path in font_candidates:
        if not font_path.exists():
            continue
        font = ImageFont.truetype(str(font_path), 48)
        for symbol in symbols:
            canvas = Image.new("L", (90, 90), 255)
            draw = ImageDraw.Draw(canvas)
            bbox = draw.textbbox((0, 0), symbol, font=font)
            draw.text((8 - bbox[0], 8 - bbox[1]), symbol, font=font, fill=0)
            arr = np.array(canvas)
            mask = np.where(arr < 128, 255, 0).astype(np.uint8)
            normalized = normalize_digit_mask(mask)
            if normalized is not None:
                templates.append((symbol, normalized))
    return templates


def normalize_digit_mask(mask: np.ndarray) -> np.ndarray | None:
    ensure_image_processing_modules()
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    cut = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    return cv2.resize(cut, (32, 48), interpolation=cv2.INTER_NEAREST)


def template_score(sample: np.ndarray, template: np.ndarray) -> float:
    ensure_image_processing_modules()
    best = 0.0
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            matrix = np.float32([[1, 0, dx], [0, 1, dy]])
            shifted = cv2.warpAffine(template, matrix, (32, 48), borderValue=0)
            inter = np.logical_and(sample > 0, shifted > 0).sum()
            union = np.logical_or(sample > 0, shifted > 0).sum()
            if union:
                best = max(best, inter / union)
    return best


def read_kills(image: Image.Image, box: tuple[int, int, int, int], templates: list[tuple[int, np.ndarray]]) -> int:
    ensure_image_processing_modules()
    crop = np.array(image.crop(box).convert("RGB"))
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    mask = cv2.inRange(gray, 180, 255)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components: list[tuple[int, int, int, int]] = []
    for label in range(1, count):
        x, y, width, height, area = stats[label]
        if area >= 15 and height >= 14 and width >= 3:
            components.append((int(x), int(y), int(width), int(height)))

    if not components:
        return 0

    digits = []
    for x, y, width, height in sorted(components, key=lambda item: item[0]):
        pad = 3
        x1 = max(0, x - pad)
        y1 = max(0, y - pad)
        x2 = min(mask.shape[1], x + width + pad)
        y2 = min(mask.shape[0], y + height + pad)
        sample = normalize_digit_mask(mask[y1:y2, x1:x2])
        if sample is None:
            continue

        best_digit = 0
        best_score = -1.0
        for digit, template in templates:
            score = template_score(sample, template)
            if score > best_score:
                best_score = score
                best_digit = digit
        digits.append(str(best_digit))

    return int("".join(digits)) if digits else 0


def read_kda_kills(
    image: Image.Image,
    box: tuple[int, int, int, int],
    templates: list[tuple[int, np.ndarray]],
    separators: list[tuple[str, np.ndarray]],
) -> int:
    ensure_image_processing_modules()
    crop = np.array(image.crop(box).convert("RGB"))
    gray = cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)
    mask = cv2.inRange(gray, 150, 255)

    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    components: list[tuple[int, int, int, int, int]] = []
    for label in range(1, count):
        x, y, width, height, area = stats[label]
        # Ignore table borders and icons that touch the crop edge.
        if x <= 2 or x + width >= mask.shape[1] - 2:
            continue
        if area >= 10 and height >= 10 and width >= 2:
            components.append((int(x), int(y), int(width), int(height), int(area)))

    digits: list[str] = []
    for x, y, width, height, _ in sorted(components, key=lambda item: item[0]):
        sample = normalize_digit_mask(mask[y : y + height, x : x + width])
        if sample is None:
            continue

        best_label = ""
        best_score = -1.0
        for digit, template in templates:
            score = template_score(sample, template)
            if score > best_score:
                best_score = score
                best_label = str(digit)
        for symbol, template in separators:
            score = template_score(sample, template)
            if score > best_score:
                best_score = score
                best_label = symbol

        if best_label == "/" and digits:
            break
        if best_label.isdigit():
            digits.append(best_label)

    return int("".join(digits)) if digits else 0


def choose_name(candidate_lines: list[list[str]], corrections: dict[str, str], fallback: str) -> str:
    candidates: list[tuple[int, str]] = []
    seen_counts: dict[str, int] = {}
    candidate_names: list[str] = []
    correction_values = {normalize_player_key(value) for value in corrections.values()}
    for lines in candidate_lines:
        if not lines:
            continue
        # The second OCR line is usually clan/title text under the nickname.
        name = clean_name(lines[0], corrections)
        significant = re.sub(r"[^\wÀ-ÿ]", "", name, flags=re.UNICODE)
        if len(significant) < 2:
            continue
        candidate_names.append(name)
        key = normalize_player_key(name)
        seen_counts[key] = seen_counts.get(key, 0) + 1

    for name in candidate_names:
        significant = re.sub(r"[^\wÀ-ÿ]", "", name, flags=re.UNICODE)

        digit_only = significant.isdigit()
        letter_count = len(re.findall(r"[^\W\d_]", significant, flags=re.UNICODE))
        digit_count = len(re.findall(r"\d", significant))
        score = len(significant) * 10 + len(name)
        score += seen_counts.get(normalize_player_key(name), 0) * 60
        if normalize_player_key(name) in correction_values:
            score += 1000
        if re.search(r"\d{2,}[A-Za-zÀ-ÿ]$", name):
            score -= 120
        if digit_only:
            score -= 40
        elif letter_count <= 2 and digit_count >= 2:
            score -= 80
        if name.startswith("Jogador "):
            score -= 100
        candidates.append((score, name))

    if candidates:
        return max(candidates, key=lambda item: item[0])[1]
    return fallback


def prepare_kda_crop(image: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    crop = image.crop(box).convert("RGB")
    crop = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.LANCZOS)
    return ImageEnhance.Contrast(ImageOps.grayscale(crop)).enhance(2.2)


def parse_kda_ocr(lines: list[str]) -> int | None:
    for line in lines:
        compact = line.replace(" ", "")
        match = re.search(r"(\d{1,2})[/|](\d{1,2})[/|](\d{1,2})", compact)
        if match:
            return int(match.group(1))
    return None


def detect_layout(image: Image.Image, config: dict[str, Any]) -> dict[str, Any]:
    final_layout = config.get("final_layout")
    if not final_layout:
        return config["layout"]

    reference_size = config["reference_size"]
    header = final_layout.get("header_detection", [350, 400, 2050, 480])
    header_box = scale_box(*header, image.size, reference_size)

    with tempfile.TemporaryDirectory(prefix="freefire_layout_") as tmpdir:
        crop = image.crop(header_box)
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.Resampling.LANCZOS)
        crop = ImageEnhance.Contrast(ImageOps.grayscale(crop)).enhance(2.0)
        path = Path(tmpdir) / "header.png"
        crop.save(path)
        lines = run_windows_ocr([path]).get(str(path), [])

    text = " ".join(lines).upper().replace(" ", "")
    if "APELIDO" in text or "K/D/A" in text or "K/ D/ A" in text:
        return final_layout
    return config["layout"]


def extract_players(image_path: Path, config: dict[str, Any], keep_debug: bool = False) -> list[PlayerKill]:
    image = Image.open(image_path).convert("RGB")
    reference_size = config["reference_size"]
    layout = detect_layout(image, config)
    corrections = config.get("name_corrections", {})
    templates = digit_templates()
    separators = symbol_templates()
    name_height = int(layout.get("name_height", 46))
    name_box_variants = layout.get("name_box_variants", [[0, 0, 0, 0]])
    kill_mode = layout.get("kill_mode", "single_column")

    with tempfile.TemporaryDirectory(prefix="freefire_ocr_") as tmpdir:
        tmp_path = Path(tmpdir)
        ocr_paths: list[Path] = []
        slots: list[tuple[str, int, list[Path], Path | None, tuple[int, int, int, int]]] = []

        for side_name, side in (("left", layout["left"]), ("right", layout["right"])):
            for row_index, row in enumerate(layout["rows"], start=1):
                y1, _ = row
                name_x1, name_x2 = side["name"]
                # OCR only the first name line; clan/title text below the nick is noise.
                crop_paths = []
                name_box = scale_box(name_x1, y1, name_x2, y1 + name_height, image.size, reference_size)
                for box_index, offsets in enumerate(name_box_variants):
                    dx1, dy1, dx2, dy2 = offsets
                    variant_box = scale_box(
                        name_x1 + dx1,
                        y1 + dy1,
                        name_x2 + dx2,
                        y1 + name_height + dy2,
                        image.size,
                        reference_size,
                    )
                    for variant, name_crop in prepare_name_crops(image, variant_box):
                        crop_path = tmp_path / f"{side_name}_{row_index}_name_b{box_index}_{variant}.png"
                        name_crop.save(crop_path)
                        ocr_paths.append(crop_path)
                        crop_paths.append(crop_path)

                        if keep_debug:
                            debug_dir = ROOT / config.get("debug_dir", "debug")
                            debug_dir.mkdir(exist_ok=True)
                            name_crop.save(debug_dir / crop_path.name)

                kda_path = None
                if kill_mode == "kda":
                    kill_x1, kill_x2 = side["kills"]
                    kill_box = scale_box(kill_x1, y1, kill_x2, row[1], image.size, reference_size)
                    kda_path = tmp_path / f"{side_name}_{row_index}_kda.png"
                    kda_crop = prepare_kda_crop(image, kill_box)
                    kda_crop.save(kda_path)
                    ocr_paths.append(kda_path)

                    if keep_debug:
                        debug_dir = ROOT / config.get("debug_dir", "debug")
                        debug_dir.mkdir(exist_ok=True)
                        kda_crop.save(debug_dir / kda_path.name)

                slots.append((side_name, row_index, crop_paths, kda_path, name_box))

        ocr_result = run_windows_ocr(ocr_paths)

        players: list[PlayerKill] = []
        for side_name, row_index, crop_paths, kda_path, _ in slots:
            side = layout[side_name]
            row = layout["rows"][row_index - 1]
            y1, y2 = row
            kill_x1, kill_x2 = side["kills"]
            kill_box = scale_box(kill_x1, y1, kill_x2, y2, image.size, reference_size)

            candidate_lines = [
                [line for line in ocr_result.get(str(crop_path), []) if line.strip()]
                for crop_path in crop_paths
            ]
            name = choose_name(candidate_lines, corrections, f"Jogador {side_name}-{row_index}")
            if kill_mode == "kda":
                ocr_kills = parse_kda_ocr(ocr_result.get(str(kda_path), []) if kda_path else [])
                kills = ocr_kills if ocr_kills is not None else read_kda_kills(image, kill_box, templates, separators)
            else:
                kills = read_kills(image, kill_box, templates)
            players.append(PlayerKill(name=name, kills=kills))

    return players


def format_message(players: list[PlayerKill], title: str) -> str:
    lines = [title, ""]
    lines.extend(f"({player.name}, {player.kills})" for player in players)
    return "\n".join(lines)


def player_payload(players: list[PlayerKill]) -> list[dict[str, Any]]:
    return [{"name": player.name, "kills": int(player.kills)} for player in players]


def player_wire_payload(players: list[PlayerKill]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for player in players:
        name = str(player.name or "").strip()
        if not name:
            continue
        key = str(player.key or "").strip() or normalize_player_key(name)
        item: dict[str, Any] = {
            "name": name,
            "nick": name,
            "nickname": name,
            "username": name,
            "nome": name,
            "apelido": name,
            "player_name": name,
            "playerName": name,
            "display_name": name,
            "displayName": name,
            "jogador": name,
            "kills": int(normalize_kill_value(player.kills)),
            "key": key,
            "player_key": key,
            "playerKey": key,
        }
        ff_player_id = re.sub(r"\D+", "", str(player.ff_player_id or ""))
        if ff_player_id:
            item["ff_player_id"] = ff_player_id
            item["ffPlayerId"] = ff_player_id
            item["freefire_id"] = ff_player_id
            item["freeFireId"] = ff_player_id
        payload.append(item)
    return payload


def merged_player_kills(players: list[PlayerKill]) -> list[PlayerKill]:
    merged: dict[str, PlayerKill] = {}
    order: list[str] = []
    for player in players:
        name = player.name.strip()
        if not name:
            continue
        key = normalize_player_key(name)
        if key not in merged:
            merged[key] = PlayerKill(
                name=name,
                kills=max(0, normalize_kill_value(player.kills)),
                key=player.key,
                ff_player_id=player.ff_player_id,
                entries=normalize_kill_value(player.entries),
            )
            order.append(key)
            continue
        merged[key].kills += max(0, normalize_kill_value(player.kills))
        if player.key and not merged[key].key:
            merged[key].key = player.key
        if player.ff_player_id and not merged[key].ff_player_id:
            merged[key].ff_player_id = player.ff_player_id
        merged[key].entries = max(merged[key].entries, normalize_kill_value(player.entries))
    return [merged[key] for key in order]


def sorted_player_kills(players: list[PlayerKill]) -> list[PlayerKill]:
    return sorted(merged_player_kills(players), key=lambda item: (-item.kills, normalize_player_key(item.name)))


def complete_player_names_from_references(players: list[PlayerKill], references: list[PlayerKill] | None) -> list[PlayerKill]:
    if all(str(player.name or "").strip() or normalize_kill_value(player.kills) <= 0 for player in players):
        return [
            PlayerKill(
                name=str(player.name or "").strip(),
                kills=normalize_kill_value(player.kills),
                key=str(player.key or "").strip(),
                ff_player_id=re.sub(r"\D+", "", str(player.ff_player_id or "")),
                entries=normalize_kill_value(player.entries),
            )
            for player in players
        ]

    source_players = sorted_player_kills(list(references or []))
    if not source_players:
        return [
            PlayerKill(
                name=str(player.name or "").strip(),
                kills=normalize_kill_value(player.kills),
                key=str(player.key or "").strip(),
                ff_player_id=re.sub(r"\D+", "", str(player.ff_player_id or "")),
                entries=normalize_kill_value(player.entries),
            )
            for player in players
        ]

    named_input_count = sum(1 for player in players if str(player.name or "").strip())
    used_keys = {
        normalize_player_key(player.name)
        for player in players
        if str(player.name or "").strip()
    }
    source_by_key: dict[str, PlayerKill] = {}
    source_by_ff_id: dict[str, PlayerKill] = {}
    source_by_kills: dict[int, list[PlayerKill]] = {}
    for source_player in source_players:
        source_name = str(source_player.name or "").strip()
        if not source_name:
            continue
        source_key = normalize_player_key(source_player.key or source_name)
        source_ff_id = re.sub(r"\D+", "", str(source_player.ff_player_id or ""))
        source_kills = normalize_kill_value(source_player.kills)
        if source_key:
            source_by_key.setdefault(source_key, source_player)
        if source_ff_id:
            source_by_ff_id.setdefault(source_ff_id, source_player)
        source_by_kills.setdefault(source_kills, []).append(source_player)

    completed: list[PlayerKill] = []
    for index, player in enumerate(players):
        name = str(player.name or "").strip()
        kills = normalize_kill_value(player.kills)
        player_key = str(player.key or "").strip()
        player_lookup_key = normalize_player_key(player_key)
        ff_player_id = re.sub(r"\D+", "", str(player.ff_player_id or ""))
        entries = normalize_kill_value(player.entries)
        if name or kills <= 0:
            completed.append(
                PlayerKill(
                    name=name,
                    kills=kills,
                    key=player_key,
                    ff_player_id=ff_player_id,
                    entries=entries,
                )
            )
            continue

        candidate: PlayerKill | None = None
        if player_lookup_key:
            candidate = source_by_key.get(player_lookup_key)
        if candidate is None and ff_player_id:
            candidate = source_by_ff_id.get(ff_player_id)
        if candidate is None and index < len(source_players):
            indexed_candidate = source_players[index]
            indexed_key = normalize_player_key(indexed_candidate.name)
            indexed_kills = normalize_kill_value(indexed_candidate.kills)
            if (
                indexed_candidate.name.strip()
                and indexed_key not in used_keys
                and (indexed_kills == kills or named_input_count == 0)
            ):
                candidate = indexed_candidate
        if candidate is None:
            for kill_candidate in source_by_kills.get(kills, []):
                candidate_key = normalize_player_key(kill_candidate.name)
                if candidate_key not in used_keys:
                    candidate = kill_candidate
                    break

        if candidate is None:
            completed.append(PlayerKill(name=name, kills=kills, key=player_key, ff_player_id=ff_player_id, entries=entries))
            continue

        candidate_key = normalize_player_key(candidate.name)
        used_keys.add(candidate_key)
        completed.append(
            PlayerKill(
                name=candidate.name,
                kills=kills,
                key=player_key or candidate.key,
                ff_player_id=ff_player_id or candidate.ff_player_id,
                entries=max(entries, normalize_kill_value(candidate.entries)),
            )
        )
    return completed


def overlay_rank_players(
    daily_ranking: list[PlayerKill] | None,
    global_ranking: list[PlayerKill] | None,
    manual_players: list[PlayerKill] | None = None,
) -> list[PlayerKill]:
    source = list(daily_ranking or global_ranking or manual_players or [])
    return sorted(source, key=lambda item: (-normalize_kill_value(item.kills), normalize_player_key(item.name)))


def normalize_kills_scope_value(value: Any) -> str:
    text = str(value or "").strip().casefold()
    folded = unicodedata.normalize("NFKD", text)
    folded = "".join(character for character in folded if not unicodedata.combining(character))
    folded = re.sub(r"[^a-z0-9]+", " ", folded).strip()
    if folded in {"daily", "diario", "dia", "somente dia", "rank dia", "ranking dia"}:
        return "daily"
    if folded in {"general", "geral", "global", "somente geral", "rank geral", "ranking geral"}:
        return "general"
    return "both"


def kills_scope_label(value: Any) -> str:
    scope = normalize_kills_scope_value(value)
    if scope == "daily":
        return "Diario"
    if scope == "general":
        return "Geral"
    return "Ambos"


def kills_scope_payload_fields(value: Any) -> dict[str, Any]:
    scope = normalize_kills_scope_value(value)
    if scope not in {"daily", "general", "both"}:
        scope = "both"
    label = kills_scope_label(scope)
    slug = "diario" if scope == "daily" else "geral" if scope == "general" else "ambos"
    applies_daily = scope in {"daily", "both"}
    applies_general = scope in {"general", "both"}
    return {
        "scope": scope,
        "scope_label": label,
        "scopeLabel": label,
        "scope_slug": slug,
        "scopeSlug": slug,
        "scope_alias": slug,
        "scopeAlias": slug,
        "scope_pt": slug,
        "scopePt": slug,
        "scope_name": slug,
        "scopeName": slug,
        "scope_code": scope,
        "scopeCode": scope,
        "rank_scope": scope,
        "rankScope": scope,
        "ranking_scope": scope,
        "rankingScope": scope,
        "rank": scope,
        "rank_type": scope,
        "rankType": scope,
        "ranking_type": scope,
        "rankingType": scope,
        "rank_slug": slug,
        "rankSlug": slug,
        "target": scope,
        "target_scope": scope,
        "targetScope": scope,
        "target_rank": scope,
        "targetRank": scope,
        "target_rank_slug": slug,
        "targetRankSlug": slug,
        "target_period": scope,
        "targetPeriod": scope,
        "target_period_slug": slug,
        "targetPeriodSlug": slug,
        "period": scope,
        "period_slug": slug,
        "periodSlug": slug,
        "periodo": slug,
        "period_label": label,
        "periodLabel": label,
        "tipo": slug,
        "modo": slug,
        "scopes": ["daily", "general"] if scope == "both" else [scope],
        "applies_daily": applies_daily,
        "appliesDaily": applies_daily,
        "aplicar_diario": applies_daily,
        "apply_daily": applies_daily,
        "applyDaily": applies_daily,
        "target_daily": applies_daily,
        "targetDaily": applies_daily,
        "is_daily": scope == "daily",
        "isDaily": scope == "daily",
        "daily_scope": scope == "daily",
        "dailyScope": scope == "daily",
        "applies_general": applies_general,
        "appliesGeneral": applies_general,
        "aplicar_geral": applies_general,
        "apply_general": applies_general,
        "applyGeneral": applies_general,
        "target_general": applies_general,
        "targetGeneral": applies_general,
        "is_general": scope == "general",
        "isGeneral": scope == "general",
        "general_scope": scope == "general",
        "generalScope": scope == "general",
        "is_global": scope == "general",
        "isGlobal": scope == "general",
    }


def kills_scope_description(value: Any) -> str:
    scope = normalize_kills_scope_value(value)
    if scope == "daily":
        return "somente no rank do dia"
    if scope == "general":
        return "somente no rank geral"
    return "no rank do dia e no geral"


def manual_kills_scopes_to_save(
    active_scope: Any,
    dirty_scopes: Iterable[Any],
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
) -> list[str]:
    clean_active = normalize_kills_scope_value(active_scope)
    if clean_active not in {"daily", "general"}:
        clean_active = "daily"
    dirty = {
        clean_scope
        for scope in dirty_scopes
        if (clean_scope := normalize_kills_scope_value(scope)) in {"daily", "general"}
    }
    players_by_scope = {
        "daily": daily_players,
        "general": general_players,
    }
    scopes: list[str] = []
    for scope in (clean_active, "daily", "general"):
        if scope in scopes:
            continue
        has_players = bool(players_by_scope.get(scope))
        if scope != clean_active and scope not in dirty and not has_players:
            continue
        if scope != clean_active and not has_players:
            continue
        scopes.append(scope)
    return scopes or [clean_active]


def manual_kills_should_send_snapshot(scopes_to_save: Iterable[Any]) -> bool:
    clean_scopes = {
        clean_scope
        for scope in scopes_to_save
        if (clean_scope := normalize_kills_scope_value(scope)) in {"daily", "general"}
    }
    return clean_scopes == {"daily", "general"}


FF_QUEUE_STATUSES = ["Na fila", "Chamado", "Jogando", "Concluido"]


def normalize_queue_status(value: Any) -> str:
    if isinstance(value, bool):
        return "Jogando" if value else "Na fila"
    text = str(value or "").strip()
    folded = text.casefold()
    aliases = {
        "fila": "Na fila",
        "na fila": "Na fila",
        "waiting": "Na fila",
        "wait": "Na fila",
        "pending": "Na fila",
        "queued": "Na fila",
        "queue": "Na fila",
        "aguardando": "Na fila",
        "chamado": "Chamado",
        "chamada": "Chamado",
        "called": "Chamado",
        "calling": "Chamado",
        "convocado": "Chamado",
        "convocada": "Chamado",
        "jogando": "Jogando",
        "em partida": "Jogando",
        "playing": "Jogando",
        "in_game": "Jogando",
        "ingame": "Jogando",
        "active": "Jogando",
        "concluido": "Concluido",
        "concluído": "Concluido",
        "finalizado": "Concluido",
        "finalizada": "Concluido",
        "done": "Concluido",
        "finished": "Concluido",
        "complete": "Concluido",
        "completed": "Concluido",
    }
    return aliases.get(folded, text if text in FF_QUEUE_STATUSES else "Na fila")


def first_present(mapping: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
    for key in keys:
        if key in mapping and mapping.get(key) not in (None, ""):
            return mapping.get(key)
    return default


PLAYER_NAME_FIELDS = (
    "name",
    "nick",
    "nickname",
    "username",
    "user",
    "participant",
    "participant_name",
    "participantName",
    "player",
    "player_name",
    "playerName",
    "jogador",
    "apelido",
    "display_name",
    "displayName",
    "user_name",
    "userName",
    "social_user",
    "socialUser",
    "screen_name",
    "screenName",
    "unique_id",
    "uniqueId",
    "title",
    "label",
    "author",
    "sender",
    "account",
    "account_name",
    "accountName",
)
PLAYER_NAME_CONTAINER_FIELDS = ("user", "author", "sender", "account", "profile", "member", "participant", "player")


def player_name_from_mapping(mapping: dict[str, Any], default: Any = "") -> Any:
    raw_name = first_present(mapping, PLAYER_NAME_FIELDS)
    if isinstance(raw_name, dict):
        nested_name = player_name_from_mapping(raw_name, "")
        if str(nested_name or "").strip():
            return nested_name
        raw_name = ""
    if raw_name not in (None, ""):
        return raw_name
    for container_key in PLAYER_NAME_CONTAINER_FIELDS:
        nested = mapping.get(container_key)
        if isinstance(nested, dict):
            nested_name = player_name_from_mapping(nested, "")
            if str(nested_name or "").strip():
                return nested_name
    return default


def ff_queue_payload(entries: list[FFQueueEntry]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for index, entry in enumerate(merge_ff_queue_entries(entries), start=1):
        if not entry.name.strip():
            continue
        item = {
            "position": index,
            "name": entry.name,
            "note": entry.note,
            "status": normalize_queue_status(entry.status),
            "rooms": max(1, normalize_kill_value(entry.rooms)),
            "credits": max(1, normalize_kill_value(entry.rooms)),
        }
        if entry.user_id:
            item["user_id"] = entry.user_id
        if entry.panel_user_id:
            item["panel_user_id"] = entry.panel_user_id
        if entry.ff_player_id:
            item["ff_player_id"] = entry.ff_player_id
        payload.append(item)
    return payload


def is_auto_room_note(note: str) -> bool:
    return bool(re.fullmatch(r"\d+\s*sala(?:s)?", re.sub(r"\s+", " ", str(note or "").strip()), re.IGNORECASE))


def ff_queue_merge_key(entry: FFQueueEntry) -> str:
    identity = str(entry.panel_user_id or entry.user_id or "").strip()
    if identity:
        return f"user:{identity.lower()}"
    ff_id = re.sub(r"\D+", "", str(entry.ff_player_id or ""))
    if ff_id:
        return f"ff:{ff_id}"
    normalized_name = unicodedata.normalize("NFKD", normalize_player_key(entry.name))
    name_key = "".join(character for character in normalized_name if not unicodedata.combining(character))
    name_key = re.sub(r"\s+", " ", name_key).strip()
    if name_key:
        return f"name:{name_key}"
    return "unknown"


def ff_queue_status_rank(status: str) -> int:
    normalized = normalize_queue_status(status)
    return {"Jogando": 3, "Chamado": 2, "Na fila": 1, "Concluido": 0}.get(normalized, 1)


def merge_ff_queue_entries(entries: list[FFQueueEntry]) -> list[FFQueueEntry]:
    grouped: dict[str, FFQueueEntry] = {}
    order: list[str] = []
    for entry in entries:
        name = entry.name.strip()
        status = normalize_queue_status(entry.status)
        if not name:
            continue
        key = ff_queue_merge_key(entry)
        rooms = max(1, normalize_kill_value(entry.rooms))
        note = "" if is_auto_room_note(entry.note) else entry.note.strip()
        if key not in grouped:
            grouped[key] = FFQueueEntry(
                name=name,
                note=note,
                status=status,
                rooms=rooms,
                user_id=str(entry.user_id or "").strip(),
                panel_user_id=str(entry.panel_user_id or "").strip(),
                ff_player_id=str(entry.ff_player_id or "").strip(),
            )
            order.append(key)
            continue
        grouped[key].rooms += rooms
        if ff_queue_status_rank(status) > ff_queue_status_rank(grouped[key].status):
            grouped[key].status = status
        if entry.ff_player_id and not grouped[key].ff_player_id:
            grouped[key].ff_player_id = str(entry.ff_player_id).strip()
        if entry.user_id and not grouped[key].user_id:
            grouped[key].user_id = str(entry.user_id).strip()
        if entry.panel_user_id and not grouped[key].panel_user_id:
            grouped[key].panel_user_id = str(entry.panel_user_id).strip()
        if note and note not in grouped[key].note:
            grouped[key].note = f"{grouped[key].note} | {note}" if grouped[key].note else note
    return [grouped[key] for key in order]


def serve_next_queue_entries(entries: list[FFQueueEntry]) -> tuple[list[FFQueueEntry], FFQueueEntry | None, int]:
    current = merge_ff_queue_entries(entries)
    target_index = -1
    for index, entry in enumerate(current):
        if entry.name.strip() and normalize_queue_status(entry.status) == "Na fila":
            target_index = index
            break
    if target_index < 0:
        return current, None, 0

    served = current.pop(target_index)
    remaining = max(0, normalize_kill_value(served.rooms) - 1)
    if remaining > 0:
        current.append(
            FFQueueEntry(
                name=served.name,
                note=served.note,
                status="Na fila",
                rooms=remaining,
                user_id=served.user_id,
                panel_user_id=served.panel_user_id,
                ff_player_id=served.ff_player_id,
            )
        )
    return current, served, remaining


def parse_ff_queue_payload(payload: Any) -> list[FFQueueEntry]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []

    candidates = payload
    if isinstance(payload, dict):
        for key in ("queue", "fila", "ff_queue", "ffQueue", "items", "data", "players"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
            if isinstance(value, dict):
                for nested_key in ("entries", "queue", "items", "players", "data"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        candidates = nested_value
                        break
                if isinstance(candidates, list):
                    break

    if not isinstance(candidates, list):
        return []

    entries: list[FFQueueEntry] = []
    for item in candidates:
        if isinstance(item, dict):
            name = first_present(
                item,
                (
                    "name",
                    "nick",
                    "nickname",
                    "username",
                    "user",
                    "participant",
                    "participant_name",
                    "participantName",
                    "player",
                    "player_name",
                    "playerName",
                    "jogador",
                    "apelido",
                    "display_name",
                    "displayName",
                    "user_name",
                    "userName",
                    "social_user",
                    "socialUser",
                    "screen_name",
                    "screenName",
                    "unique_id",
                    "uniqueId",
                ),
            )
            note = first_present(item, ("note", "notes", "obs", "observacao", "observação", "room", "sala"), "")
            status = first_present(item, ("status", "state", "estado", "phase", "situacao", "situação"), "")
            user_id = first_present(item, ("user_id", "userId", "uid", "id", "jarvis_user_id", "jarvisUserId"), "")
            panel_user_id = first_present(item, ("panel_user_id", "panelUserId", "public_user_id", "publicUserId"), "")
            ff_player_id = first_present(
                item,
                ("ff_player_id", "ffPlayerId", "freefire_id", "freeFireId", "player_id", "playerId", "id_ff", "idFF"),
                "",
            )
            if not status:
                if item.get("playing") or item.get("isPlaying") or item.get("inGame"):
                    status = "Jogando"
                elif item.get("called") or item.get("isCalled"):
                    status = "Chamado"
                elif item.get("done") or item.get("finished") or item.get("completed"):
                    status = "Concluido"
                else:
                    status = "Na fila"
            rooms = normalize_kill_value(
                first_present(
                    item,
                    (
                        "rooms",
                        "credits",
                        "room_count",
                        "roomCount",
                        "salas",
                        "quantidade_salas",
                        "qtd_salas",
                        "quantity",
                        "qty",
                        "count",
                        "amount",
                    ),
                    1,
                )
            )
        elif isinstance(item, (list, tuple)) and item:
            name = item[0]
            note = item[1] if len(item) > 1 else ""
            status = item[2] if len(item) > 2 else "Na fila"
            rooms = 1
            user_id = ""
            panel_user_id = ""
            ff_player_id = ""
        else:
            continue

        clean = str(name or "").strip()
        if clean:
            entries.append(
                FFQueueEntry(
                    clean,
                    str(note or "").strip(),
                    normalize_queue_status(status),
                    max(1, rooms),
                    str(user_id or "").strip(),
                    str(panel_user_id or "").strip(),
                    re.sub(r"\D+", "", str(ff_player_id or "")),
                )
            )
    return merge_ff_queue_entries(entries)


def normalize_kill_value(value: Any) -> int:
    try:
        if isinstance(value, str):
            value = re.sub(r"[^\d-]", "", value.strip())
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def optional_int_value(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, str):
            value = re.sub(r"[^\d-]", "", value.strip())
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


PLAYER_MAP_METADATA_KEYS = {
    "ok",
    "success",
    "status",
    "state",
    "message",
    "mensagem",
    "detail",
    "result",
    "resultado",
    "accepted",
    "count",
    "total_count",
    "created",
    "updated",
    "saved",
    "synced",
    "error",
    "errors",
    "erro",
    "erros",
    "action",
    "mode",
    "source",
    "room",
    "app",
    "app_version",
    "version",
    "sync_version",
    "client_id",
    "client_name",
    "updated_by",
    "updated_at",
    "timestamp",
    "revision",
    "device",
    "devices",
    "summary",
    "stats",
    "totals",
    "total",
    "total_players",
    "total_kills",
    "daily_total_players",
    "daily_total_kills",
    "ignored",
    "ignored_players",
}


def is_player_map_metadata_key(value: Any) -> bool:
    key = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().casefold()).strip("_")
    return key in PLAYER_MAP_METADATA_KEYS


def parse_players_payload(payload: Any) -> list[PlayerKill]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []

    candidates = payload
    if isinstance(payload, dict):
        for key in ("players", "kills", "data", "ranking", "global_ranking", "daily_ranking", "rank", "items"):
            value = payload.get(key)
            if isinstance(value, (list, dict)):
                candidates = value
                break

    players: list[PlayerKill] = []
    if isinstance(candidates, dict):
        iterable = candidates.items()
        for name, kills in iterable:
            key = ""
            ff_player_id = ""
            entries = 0
            if is_player_map_metadata_key(name):
                continue
            if isinstance(kills, dict):
                item = kills
                row_name = player_name_from_mapping(item, name)
                kills = first_present(item, ("kills", "kill", "k", "abates", "score", "points", "value", "total"), 0)
                key = str(first_present(item, ("key", "player_key", "playerKey", "id", "uid"), "") or "").strip()
                ff_player_id = re.sub(
                    r"\D+",
                    "",
                    str(first_present(item, ("ff_player_id", "ffPlayerId", "freefire_id", "freeFireId", "player_id", "playerId"), "") or ""),
                )
                entries = normalize_kill_value(first_present(item, ("entries", "partidas", "matches", "games"), 0))
            else:
                if isinstance(kills, bool):
                    continue
                row_name = name
            clean = str(row_name or "").strip()
            if clean:
                players.append(PlayerKill(clean, normalize_kill_value(kills), key, ff_player_id, entries))
        return players

    if not isinstance(candidates, list):
        return []

    for item in candidates:
        if isinstance(item, dict):
            name = player_name_from_mapping(item)
            kills = first_present(item, ("kills", "kill", "k", "abates", "score", "points", "value", "total"), 0)
            key = first_present(item, ("key", "player_key", "playerKey", "id", "uid"), "")
            ff_player_id = first_present(item, ("ff_player_id", "ffPlayerId", "freefire_id", "freeFireId", "player_id", "playerId"), "")
            entries = first_present(item, ("entries", "partidas", "matches", "games"), 0)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            name, kills = item[0], item[1]
            key = ""
            ff_player_id = ""
            entries = 0
        else:
            continue
        clean = str(name or "").strip()
        if clean:
            players.append(
                PlayerKill(
                    clean,
                    normalize_kill_value(kills),
                    str(key or "").strip(),
                    re.sub(r"\D+", "", str(ff_player_id or "")),
                    normalize_kill_value(entries),
                )
            )
    return players


def ranking_payload_from(payload: dict[str, Any], direct_keys: tuple[str, ...], container_keys: tuple[str, ...] = ()) -> Any:
    direct_value = first_present(payload, direct_keys)
    if direct_value is not None:
        return direct_value

    for container_key in container_keys:
        nested = payload.get(container_key)
        if isinstance(nested, dict):
            nested_value = first_present(nested, ("ranking", "rank", "players", "kills", "items", "data"))
            if nested_value is not None:
                return nested_value
        elif isinstance(nested, list):
            return nested
    return None


def parse_ignored_kills_payload(payload: Any) -> list[IgnoredKillPlayer]:
    if not payload:
        return []
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = [payload]

    items: list[Any]
    if isinstance(payload, dict):
        items = []
        for key, value in payload.items():
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("key", key)
                items.append(row)
            else:
                items.append({"key": key, "name": value or key})
    elif isinstance(payload, list):
        items = payload
    else:
        return []

    ignored: list[IgnoredKillPlayer] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("nick") or item.get("player") or item.get("key") or "").strip()
            key = str(item.get("key") or normalize_player_key(name)).strip()
            ignored_at = 0.0
            try:
                ignored_at = float(item.get("ignored_at") or item.get("ignoredAt") or 0)
            except (TypeError, ValueError):
                ignored_at = 0.0
        else:
            name = str(item or "").strip()
            key = normalize_player_key(name)
            ignored_at = 0.0
        if not name and not key:
            continue
        identity = key or normalize_player_key(name)
        if identity in seen:
            continue
        seen.add(identity)
        ignored.append(IgnoredKillPlayer(name=name or key, key=key, ignored_at=ignored_at))
    ignored.sort(key=lambda item: normalize_player_key(item.name))
    return ignored


def parse_realtime_state(payload: Any) -> RealtimeState:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return RealtimeState(players=[])

    players = parse_players_payload(payload)
    updated_by = ""
    updated_at = ""
    devices: list[dict[str, Any]] | None = None
    daily_ranking: list[PlayerKill] = []
    global_ranking: list[PlayerKill] = []
    ignored_players: list[IgnoredKillPlayer] = []
    total_players: int | None = None
    total_kills: int | None = None
    visible_players: int | None = None
    daily_players: int | None = None
    daily_kills: int | None = None
    daily_visible_players: int | None = None

    if isinstance(payload, dict):
        daily_source = ranking_payload_from(
            payload,
            (
                "daily_ranking",
                "dailyRanking",
                "daily_rank",
                "dailyRank",
                "day_ranking",
                "dayRanking",
                "dia_ranking",
                "diaRanking",
                "rank_daily",
                "rankDaily",
                "rank_dia",
                "rankDia",
                "ranking_daily",
                "rankingDaily",
            ),
            ("daily", "day", "dia", "daily_stats", "dailyStats", "rank_daily", "rankDaily"),
        )
        global_source = ranking_payload_from(
            payload,
            (
                "general_ranking",
                "generalRanking",
                "general_rank",
                "generalRank",
                "geral_ranking",
                "geralRanking",
                "geral_rank",
                "geralRank",
                "global_ranking",
                "globalRanking",
                "global_rank",
                "globalRank",
                "overall_ranking",
                "overallRanking",
                "overall_rank",
                "overallRank",
                "all_time_ranking",
                "allTimeRanking",
                "ranking_general",
                "rankingGeneral",
            ),
            ("general", "geral", "global", "overall", "all_time", "allTime", "rank_general", "rankGeneral"),
        )
        daily_ranking = parse_players_payload(daily_source or [])
        if global_source is None:
            global_source = first_present(payload, ("ranking",), [])
        global_ranking = parse_players_payload(global_source or [])
        ignored_players = parse_ignored_kills_payload(payload.get("ignored") or payload.get("ignored_players") or payload.get("ignoredPlayers") or [])
        if not players and global_ranking:
            players = global_ranking
        totals_source = payload
        summary = payload.get("summary") or payload.get("stats") or payload.get("totals")
        if isinstance(summary, dict):
            totals_source = {**summary, **payload}
        total_players = optional_int_value(
            first_present(
                totals_source,
                ("total_players", "totalPlayers", "players_total", "playersTotal", "players_count", "playersCount", "player_count"),
            )
        )
        total_kills = optional_int_value(
            first_present(totals_source, ("total_kills", "totalKills", "kills_total", "killsTotal", "kills_count", "killsCount"))
        )
        visible_players = optional_int_value(
            first_present(totals_source, ("total_visible_players", "totalVisiblePlayers", "visible_players", "visiblePlayers"))
        )
        daily_players = optional_int_value(
            first_present(totals_source, ("daily_total_players", "dailyTotalPlayers", "daily_players", "dailyPlayers"))
        )
        daily_kills = optional_int_value(first_present(totals_source, ("daily_total_kills", "dailyTotalKills", "daily_kills", "dailyKills")))
        daily_visible_players = optional_int_value(
            first_present(totals_source, ("daily_total_visible_players", "dailyTotalVisiblePlayers", "daily_visible_players", "dailyVisiblePlayers"))
        )
        updated_by = str(
            payload.get("updated_by")
            or payload.get("updatedBy")
            or payload.get("source")
            or payload.get("sourceName")
            or payload.get("lastUpdatedBy")
            or payload.get("client_name")
            or payload.get("clientName")
            or payload.get("device_name")
            or payload.get("deviceName")
            or ""
        ).strip()
        updated_at = str(payload.get("updated_at") or payload.get("updatedAt") or payload.get("timestamp") or payload.get("ts") or "").strip()
        device = payload.get("device")
        if not updated_by and isinstance(device, dict):
            updated_by = str(device.get("name") or device.get("device_name") or "").strip()
        if not updated_by and ("ranking" in payload or "daily_ranking" in payload):
            updated_by = "Jarvis Kills FF"
        raw_devices = payload.get("devices") or payload.get("clients") or payload.get("online_devices") or payload.get("onlineDevices")
        if isinstance(raw_devices, list):
            devices = [item for item in raw_devices if isinstance(item, dict)]

    return RealtimeState(
        players=players,
        updated_by=updated_by,
        updated_at=updated_at,
        devices=devices,
        daily_ranking=daily_ranking,
        global_ranking=global_ranking,
        ignored_players=ignored_players,
        total_players=total_players,
        total_kills=total_kills,
        visible_players=visible_players,
        daily_players=daily_players,
        daily_kills=daily_kills,
        daily_visible_players=daily_visible_players,
    )


def parse_ff_queue_state(payload: Any) -> FFQueueState:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return FFQueueState(entries=[])

    entries = parse_ff_queue_payload(payload)
    updated_by = ""
    updated_at = ""
    devices: list[dict[str, Any]] | None = None
    total_members: int | None = None
    total_credits: int | None = None

    if isinstance(payload, dict):
        updated_by = str(
            payload.get("updated_by")
            or payload.get("updatedBy")
            or payload.get("source")
            or payload.get("sourceName")
            or payload.get("lastUpdatedBy")
            or payload.get("client_name")
            or payload.get("clientName")
            or payload.get("device_name")
            or payload.get("deviceName")
            or ""
        ).strip()
        updated_at = str(payload.get("updated_at") or payload.get("updatedAt") or payload.get("timestamp") or payload.get("ts") or "").strip()
        device = payload.get("device")
        if not updated_by and isinstance(device, dict):
            updated_by = str(device.get("name") or device.get("device_name") or "").strip()
        raw_devices = payload.get("devices") or payload.get("clients") or payload.get("online_devices") or payload.get("onlineDevices")
        if isinstance(raw_devices, list):
            devices = [item for item in raw_devices if isinstance(item, dict)]
        summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        queue_info = payload.get("queue") if isinstance(payload.get("queue"), dict) else {}
        total_members = optional_int_value(
            first_present(
                {**queue_info, **summary, **payload},
                ("total_members", "totalMembers", "members", "member_count", "memberCount"),
            )
        )
        total_credits = optional_int_value(
            first_present(
                {**queue_info, **summary, **payload},
                ("total_credits", "totalCredits", "credits", "rooms", "salas", "room_count", "roomCount"),
            )
        )

    return FFQueueState(
        entries=entries,
        updated_by=updated_by,
        updated_at=updated_at,
        devices=devices,
        total_members=total_members,
        total_credits=total_credits,
    )


def send_kills_realtime_update(
    endpoint_url: str,
    title: str,
    players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    payload = {
        "source": "aizen-stream-control",
        "mode": "manual",
        "app_version": APP_VERSION,
        "sync_version": 2,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": now,
        "revision": int(time.time() * 1000),
        "device": {
            "id": device_id,
            "name": device_name,
            "app": APP_NAME,
            "version": APP_VERSION,
        },
        "content": format_message(players, title),
        "players": player_wire_payload(players),
    }
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        normalize_endpoint_url(endpoint_url),
        json=payload,
        headers=headers,
        timeout=KILLS_POST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return response.text.strip()


def fetch_kills_realtime(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    timeout: float = KILLS_GET_TIMEOUT_SECONDS,
) -> RealtimeState:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if room:
        headers["X-Aizen-Room"] = room
    if token:
        headers["X-Aizen-Token"] = token
    params = {
        "client_id": device_id,
        "client_name": device_name,
        "app_version": APP_VERSION,
    }
    if room:
        params["room"] = room
    base_url = normalize_endpoint_url(endpoint_url)
    http_session = session or requests
    response = http_session.get(
        base_url,
        params=params,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    state = parse_realtime_state(response.text)
    if state.daily_ranking or state.global_ranking:
        return state

    rank_url = derive_kills_rank_endpoint(endpoint_url)
    if rank_url == base_url:
        return state
    rank_params = dict(params)
    rank_params["limit"] = 200
    try:
        rank_response = http_session.get(
            rank_url,
            params=rank_params,
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
        if 300 <= rank_response.status_code < 400:
            return state
        if rank_response.status_code in {404, 405}:
            return state
        rank_response.raise_for_status()
    except requests.RequestException:
        return state
    rank_state = parse_realtime_state(rank_response.text)
    if rank_state.daily_ranking or rank_state.global_ranking:
        return rank_state
    return state


def fetch_kills_rank_realtime(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    timeout: float = KILLS_GET_TIMEOUT_SECONDS,
) -> RealtimeState:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if room:
        headers["X-Aizen-Room"] = room
    if token:
        headers["X-Aizen-Token"] = token
    params = {
        "client_id": device_id,
        "client_name": device_name,
        "app_version": APP_VERSION,
        "limit": 200,
    }
    if room:
        params["room"] = room
    http_client = session or requests
    response = http_client.get(
        derive_kills_rank_endpoint(endpoint_url),
        params=params,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return parse_realtime_state(response.text)


def fetch_kills_snapshot_realtime(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    timeout: float = KILLS_GET_TIMEOUT_SECONDS,
) -> RealtimeState:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if room:
        headers["X-Aizen-Room"] = room
    if token:
        headers["X-Aizen-Token"] = token
    params = {
        "client_id": device_id,
        "client_name": device_name,
        "app_version": APP_VERSION,
    }
    if room:
        params["room"] = room
    http_client = session or requests
    response = http_client.get(
        derive_kills_snapshot_endpoint(endpoint_url),
        params=params,
        headers=headers,
        timeout=timeout,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return parse_realtime_state(response.text)


def derive_kills_rank_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-kills/rank"):
        next_path = path
    elif path.endswith("/api/freefire-kills/style"):
        next_path = path[: -len("/style")] + "/rank"
    elif path.endswith("/api/freefire-kills/action"):
        next_path = path[: -len("/action")] + "/rank"
    elif path.endswith("/api/freefire-kills"):
        next_path = f"{path}/rank"
    elif path.endswith("/freefire-kills/obs") or path.endswith("/freefire-kills"):
        next_path = "/api/freefire-kills/rank"
    else:
        next_path = "/api/freefire-kills/rank"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def derive_kills_action_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-kills/action"):
        next_path = path
    elif path.endswith("/api/freefire-kills/rank"):
        next_path = path[: -len("/rank")] + "/action"
    elif path.endswith("/api/freefire-kills/style"):
        next_path = path[: -len("/style")] + "/action"
    elif path.endswith("/api/freefire-kills"):
        next_path = f"{path}/action"
    elif path.endswith("/freefire-kills/obs") or path.endswith("/freefire-kills"):
        next_path = "/api/freefire-kills/action"
    else:
        next_path = f"{path}/action"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def derive_kills_snapshot_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-kills/action"):
        next_path = path[: -len("/action")]
    elif path.endswith("/api/freefire-kills/rank"):
        next_path = path[: -len("/rank")]
    elif path.endswith("/api/freefire-kills/style"):
        next_path = path[: -len("/style")]
    elif path.endswith("/api/freefire-kills"):
        next_path = path
    elif path.endswith("/freefire-kills/obs") or path.endswith("/freefire-kills"):
        next_path = "/api/freefire-kills"
    else:
        next_path = path or "/api/freefire-kills"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def derive_kills_style_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-kills/style"):
        next_path = path
    elif path.endswith("/api/freefire-kills/action"):
        next_path = path[: -len("/action")] + "/style"
    elif path.endswith("/api/freefire-kills"):
        next_path = f"{path}/style"
    elif path.endswith("/freefire-kills/obs") or path.endswith("/freefire-kills"):
        next_path = "/api/freefire-kills/style"
    else:
        next_path = "/api/freefire-kills/style"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def derive_kills_obs_url(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/freefire-kills/obs"):
        next_path = path
    else:
        next_path = "/freefire-kills/obs"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def fetch_kills_style(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.get(
        derive_kills_style_endpoint(endpoint_url),
        params={"client_id": device_id, "client_name": device_name, "app_version": APP_VERSION},
        headers=headers,
        timeout=12,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Resposta de estilo Kills FF invalida.")
    style = payload.get("style") if isinstance(payload.get("style"), dict) else payload
    return dict(style)


def send_kills_style_update(
    endpoint_url: str,
    style: dict[str, Any],
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    payload = {
        "source": "aizen-stream-control",
        "app_version": APP_VERSION,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "style": dict(style or {}),
    }
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        derive_kills_style_endpoint(endpoint_url),
        json=payload,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Resposta de estilo Kills FF invalida.")
    style_payload = result.get("style") if isinstance(result.get("style"), dict) else result
    return dict(style_payload)


def send_kills_action_update(
    endpoint_url: str,
    action: str,
    player: PlayerKill | None = None,
    kills: int | None = None,
    scope: str = "both",
    new_name: str = "",
    ff_player_id: str = "",
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    parse_response: bool = True,
) -> RealtimeState:
    clean_scope = normalize_kills_scope_value(scope)
    scope_payload = clean_scope if clean_scope in {"daily", "general", "both"} else "both"
    payload: dict[str, Any] = {
        "source": "aizen-stream-control",
        "mode": "kills_action",
        "app_version": APP_VERSION,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "action": action,
        **kills_scope_payload_fields(scope_payload),
    }
    if player is not None:
        payload.update(
            {
                "key": player.key or normalize_player_key(player.name),
                "name": player.name,
                "nick": player.name,
                "nickname": player.name,
                "username": player.name,
                "nome": player.name,
                "apelido": player.name,
                "player_name": player.name,
                "playerName": player.name,
                "display_name": player.name,
                "displayName": player.name,
                "jogador": player.name,
                "ff_player_id": player.ff_player_id,
            }
        )
    if kills is not None:
        payload["kills"] = normalize_kill_value(kills)
    if new_name:
        payload["new_name"] = new_name
        payload["display_name"] = new_name
    if action == "set_ff_id" or ff_player_id:
        payload["ff_player_id"] = re.sub(r"\D+", "", str(ff_player_id))

    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "kills_action",
    }
    if token:
        headers["X-Aizen-Token"] = token
    http_client = session or requests
    response = http_client.post(
        derive_kills_action_endpoint(endpoint_url),
        json=payload,
        headers=headers,
        timeout=KILLS_POST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    if not parse_response:
        return RealtimeState(players=[])
    return parse_realtime_state(response.text)


def player_kill_map(players: list[PlayerKill]) -> dict[str, int]:
    result: dict[str, int] = {}
    for player in players:
        name = player.name.strip()
        if not name:
            continue
        key = normalize_player_key(name)
        result[key] = result.get(key, 0) + normalize_kill_value(player.kills)
    return result


def player_kill_detail_map(players: list[PlayerKill]) -> dict[str, PlayerKill]:
    return {normalize_player_key(player.name): player for player in sorted_player_kills(players) if player.name.strip()}


def kills_snapshot_matches_state(
    state: RealtimeState,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
) -> bool:
    expected_daily = player_kill_map(daily_players)
    expected_general = player_kill_map(general_players)
    actual_daily = player_kill_map(state.daily_ranking or [])
    actual_general = player_kill_map(state.global_ranking or state.players or [])
    return actual_daily == expected_daily and actual_general == expected_general


def kills_scope_matches_state(state: RealtimeState, scope: str, players: list[PlayerKill]) -> bool:
    clean_scope = normalize_kills_scope_value(scope)
    expected = player_kill_map(players)
    if clean_scope == "general":
        actual_players = state.global_ranking or ([] if state.daily_ranking else state.players or [])
    else:
        actual_players = state.daily_ranking or []
    return player_kill_map(actual_players) == expected


def kills_scope_players_from_state(state: RealtimeState, scope: str) -> list[PlayerKill]:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope == "general":
        return sorted_player_kills(state.global_ranking or ([] if state.daily_ranking else state.players or []))
    return sorted_player_kills(state.daily_ranking or [])


def fetch_kills_rank_confirmation(
    endpoint_url: str,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    delays: tuple[float, ...] = KILLS_RANK_CONFIRM_DELAYS_SECONDS,
    timeout: float = KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
) -> tuple[RealtimeState | None, RealtimeState | None]:
    last_state: RealtimeState | None = None
    for delay_seconds in delays:
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        try:
            state = fetch_kills_rank_realtime(
                endpoint_url,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                timeout=timeout,
            )
        except Exception:
            continue
        last_state = state
        if kills_snapshot_matches_state(state, daily_players, general_players):
            return state, state
    return None, last_state


def fetch_confirmed_kills_rank_state(
    endpoint_url: str,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    delays: tuple[float, ...] = KILLS_RANK_CONFIRM_DELAYS_SECONDS,
    timeout: float = KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
) -> RealtimeState | None:
    confirmed_state, _last_state = fetch_kills_rank_confirmation(
        endpoint_url,
        daily_players,
        general_players,
        device_id=device_id,
        device_name=device_name,
        room=room,
        token=token,
        session=session,
        delays=delays,
        timeout=timeout,
    )
    return confirmed_state


def fetch_confirmed_kills_scope_state(
    endpoint_url: str,
    scope: str,
    players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    delays: tuple[float, ...] = KILLS_RANK_CONFIRM_DELAYS_SECONDS,
    timeout: float = KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
) -> RealtimeState | None:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope not in {"daily", "general"}:
        clean_scope = "daily"
    for delay_seconds in delays:
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        try:
            state = fetch_kills_rank_realtime(
                endpoint_url,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                timeout=timeout,
            )
        except Exception:
            continue
        if kills_scope_matches_state(state, clean_scope, players):
            return state
    return None


def fetch_confirmed_kills_snapshot_endpoint_state(
    endpoint_url: str,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
    delays: tuple[float, ...] = KILLS_RANK_CONFIRM_DELAYS_SECONDS,
    timeout: float = KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
) -> RealtimeState | None:
    for delay_seconds in delays:
        if delay_seconds > 0:
            time.sleep(delay_seconds)
        try:
            state = fetch_kills_snapshot_realtime(
                endpoint_url,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                timeout=timeout,
            )
        except Exception:
            continue
        if kills_snapshot_matches_state(state, daily_players, general_players):
            return state
    return None


def clone_player_kills(players: list[PlayerKill]) -> list[PlayerKill]:
    return [
        PlayerKill(
            name=player.name,
            kills=normalize_kill_value(player.kills),
            key=player.key,
            ff_player_id=player.ff_player_id,
            entries=normalize_kill_value(player.entries),
        )
        for player in players
    ]


def local_kills_snapshot_state(
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    updated_by: str = "",
) -> RealtimeState:
    return RealtimeState(
        players=clone_player_kills(general_players),
        daily_ranking=clone_player_kills(daily_players),
        global_ranking=clone_player_kills(general_players),
        updated_by=updated_by,
        total_players=len(general_players),
        total_kills=sum(player.kills for player in general_players),
        daily_players=len(daily_players),
        daily_kills=sum(player.kills for player in daily_players),
    )


def response_acknowledges_kills_snapshot(response_text: str) -> bool:
    clean_text = str(response_text or "").strip()
    if not clean_text:
        return True

    def ack_text(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
        return "".join(character for character in normalized if not unicodedata.combining(character)).strip()

    positive_values = {
        "1",
        "true",
        "ok",
        "success",
        "saved",
        "updated",
        "stored",
        "accepted",
        "received",
        "persisted",
        "synced",
        "synchronized",
        "created",
        "done",
        "salvo",
        "salva",
        "atualizado",
        "atualizada",
        "sincronizado",
        "sincronizada",
        "recebido",
        "recebida",
        "gravado",
        "gravada",
        "concluido",
        "concluida",
    }
    positive_fragments = (
        "salvo",
        "salva",
        "sucesso",
        "atualizado",
        "atualizada",
        "sincronizado",
        "sincronizada",
        "recebido",
        "recebida",
        "gravado",
        "gravada",
        "concluido",
        "concluida",
        "stored",
        "accepted",
        "received",
        "persisted",
        "synced",
        "synchronized",
        "created",
        "updated",
        "saved",
        "success",
    )
    negative_values = {"0", "false", "error", "erro", "failed", "failure", "falha", "invalid", "unsupported", "rejected"}
    negative_fragments = ("erro", "error", "falh", "failed", "failure", "invalid", "invalido", "unsupported", "nao suport", "rejeitad")
    bool_keys = {"ok", "success", "saved", "updated", "synced", "accepted", "received", "persisted"}
    text_keys = {"status", "state", "message", "detail", "result", "resultado", "mensagem"}
    error_keys = {"error", "errors", "erro", "erros", "failure", "failed", "falha"}

    def text_is_positive(value: Any) -> bool:
        text = ack_text(value)
        return text in positive_values or any(fragment in text for fragment in positive_fragments)

    def text_is_negative(value: Any) -> bool:
        text = ack_text(value)
        return text in negative_values or any(fragment in text for fragment in negative_fragments)

    clean_status = ack_text(clean_text)
    looks_like_json = clean_text.startswith("{") or clean_text.startswith("[")
    if clean_status in positive_values or (not looks_like_json and text_is_positive(clean_status)):
        return True
    try:
        payload = json.loads(clean_text)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False

    def has_negative_ack(value: Any) -> bool:
        if isinstance(value, dict):
            for raw_key, raw_value in value.items():
                key = ack_text(raw_key)
                if key in bool_keys and raw_value is False:
                    return True
                if key in error_keys and raw_value not in (None, "", False, [], {}):
                    return True
                if key in text_keys and isinstance(raw_value, str) and text_is_negative(raw_value):
                    return True
                if has_negative_ack(raw_value):
                    return True
        elif isinstance(value, list):
            return any(has_negative_ack(item) for item in value)
        return False

    def has_positive_ack(value: Any) -> bool:
        if isinstance(value, dict):
            for raw_key, raw_value in value.items():
                key = ack_text(raw_key)
                if key in bool_keys and raw_value is True:
                    return True
                if key in text_keys and isinstance(raw_value, str) and text_is_positive(raw_value):
                    return True
                if has_positive_ack(raw_value):
                    return True
        elif isinstance(value, list):
            return any(has_positive_ack(item) for item in value)
        return False

    if has_negative_ack(payload):
        return False
    return has_positive_ack(payload)


def response_confirms_persisted_kills_snapshot(
    response_text: str,
    state: RealtimeState,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
) -> bool:
    if not kills_snapshot_matches_state(state, daily_players, general_players):
        return False
    try:
        payload = json.loads(str(response_text or "").strip())
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    mode = str(payload.get("mode") or "").strip().casefold()
    if mode and mode not in {"kills_snapshot", "rank_snapshot", "snapshot", "replace"}:
        return False
    if "accepted" in payload:
        try:
            accepted = int(float(str(payload.get("accepted") or 0).replace(",", ".")))
        except (TypeError, ValueError):
            accepted = 0
        if accepted < len(daily_players) + len(general_players):
            return False
    persisted_markers = (
        "persisted",
        "confirmed",
        "panel_confirmed",
        "panelConfirmed",
        "snapshot_confirmed",
        "snapshotConfirmed",
        "saved_to_panel",
        "savedToPanel",
        "panel_synced",
        "panelSynced",
    )
    if not any(payload.get(key) is True for key in persisted_markers):
        return False
    has_daily_payload = any(key in payload for key in ("daily_ranking", "dailyRanking", "daily", "dia_ranking"))
    has_general_payload = any(
        key in payload
        for key in ("players", "ranking", "global_ranking", "globalRanking", "general_ranking", "generalRanking")
    )
    return has_daily_payload and has_general_payload and response_acknowledges_kills_snapshot(response_text)


def kills_delta_actions(
    current_players: list[PlayerKill],
    expected_players: list[PlayerKill],
    scope: str,
) -> list[tuple[str, PlayerKill, int | None, str]]:
    current_map = player_kill_detail_map(current_players)
    expected_map = player_kill_detail_map(expected_players)
    actions: list[tuple[str, PlayerKill, int | None, str]] = []
    for key, current_player in current_map.items():
        if key not in expected_map:
            actions.append(("delete", current_player, None, scope))
    for key, expected_player in expected_map.items():
        current_player = current_map.get(key)
        if current_player is None or normalize_kill_value(current_player.kills) != normalize_kill_value(expected_player.kills):
            actions.append(("set", expected_player, normalize_kill_value(expected_player.kills), scope))
    return actions


def kills_snapshot_url_candidates(endpoint_url: str) -> tuple[str, list[str]]:
    cache_key = normalize_endpoint_url(endpoint_url)
    snapshot_url = derive_kills_snapshot_endpoint(cache_key)
    action_url = derive_kills_action_endpoint(cache_key)
    snapshot_urls: list[str] = []
    with KILLS_SNAPSHOT_ENDPOINT_CACHE_LOCK:
        preferred_url = KILLS_SNAPSHOT_ENDPOINT_CACHE.get(cache_key, "")
    for candidate_url in (preferred_url, snapshot_url, cache_key, action_url):
        if candidate_url and candidate_url not in snapshot_urls:
            snapshot_urls.append(candidate_url)
    return cache_key, snapshot_urls


def remember_kills_snapshot_endpoint(cache_key: str, snapshot_url: str) -> None:
    if not cache_key or not snapshot_url:
        return
    with KILLS_SNAPSHOT_ENDPOINT_CACHE_LOCK:
        KILLS_SNAPSHOT_ENDPOINT_CACHE[cache_key] = snapshot_url


def forget_kills_snapshot_endpoint(cache_key: str, snapshot_url: str) -> None:
    if not cache_key or not snapshot_url:
        return
    with KILLS_SNAPSHOT_ENDPOINT_CACHE_LOCK:
        if KILLS_SNAPSHOT_ENDPOINT_CACHE.get(cache_key) == snapshot_url:
            KILLS_SNAPSHOT_ENDPOINT_CACHE.pop(cache_key, None)


def send_kills_snapshot_update(
    endpoint_url: str,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> RealtimeState:
    daily_players = sorted_player_kills(daily_players)
    general_players = sorted_player_kills(general_players)
    daily_payload = player_wire_payload(daily_players)
    general_payload = player_wire_payload(general_players)
    daily_count = len(daily_players)
    general_count = len(general_players)
    daily_kills_total = sum(player.kills for player in daily_players)
    general_kills_total = sum(player.kills for player in general_players)
    now = datetime.now().isoformat(timespec="seconds")
    base_payload: dict[str, Any] = {
        "source": "aizen-stream-control",
        "mode": "kills_snapshot",
        "app_version": APP_VERSION,
        "sync_version": 3,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": now,
        "revision": int(time.time() * 1000),
        "action": "replace",
        "scope": "both",
        "replace": True,
        "return_state": True,
        "return_persisted": True,
        "confirm_persisted": True,
        "players": general_payload,
        "ranking": general_payload,
        "daily_ranking": daily_payload,
        "dailyRanking": daily_payload,
        "daily_rank": daily_payload,
        "dailyRank": daily_payload,
        "day_ranking": daily_payload,
        "dayRanking": daily_payload,
        "dia_ranking": daily_payload,
        "diaRanking": daily_payload,
        "rank_daily": daily_payload,
        "rankDaily": daily_payload,
        "rank_dia": daily_payload,
        "rankDia": daily_payload,
        "ranking_daily": daily_payload,
        "rankingDaily": daily_payload,
        "global_ranking": general_payload,
        "globalRanking": general_payload,
        "general_ranking": general_payload,
        "generalRanking": general_payload,
        "geral_ranking": general_payload,
        "geralRanking": general_payload,
        "scopes": ["daily", "general"],
        "replace_daily": True,
        "replace_general": True,
        "total_players": general_count,
        "total_kills": general_kills_total,
        "daily_total_players": daily_count,
        "daily_total_kills": daily_kills_total,
        "daily_player_count": daily_count,
        "dailyPlayerCount": daily_count,
        "daily_players": daily_payload,
        "dailyPlayers": daily_payload,
        "daily_kills": daily_kills_total,
        "totals": {
            "total_players": general_count,
            "total_kills": general_kills_total,
            "daily_total_players": daily_count,
            "daily_total_kills": daily_kills_total,
        },
    }
    legacy_payload: dict[str, Any] = {
        **base_payload,
        "ranking": general_payload,
        "global_ranking": general_payload,
        "globalRanking": general_payload,
        "general_ranking": general_payload,
        "generalRanking": general_payload,
        "geral_ranking": general_payload,
        "dailyRanking": daily_payload,
        "dia_ranking": daily_payload,
        "daily": daily_payload,
        "general": general_payload,
        "replaceDaily": True,
        "replaceGeneral": True,
        "rankings": {
            "daily": daily_payload,
            "daily_ranking": daily_payload,
            "dailyRanking": daily_payload,
            "dia": daily_payload,
            "dia_ranking": daily_payload,
            "diaRanking": daily_payload,
            "rank_daily": daily_payload,
            "rankDaily": daily_payload,
            "global": general_payload,
            "general": general_payload,
            "general_ranking": general_payload,
            "generalRanking": general_payload,
            "geral": general_payload,
            "geral_ranking": general_payload,
            "geralRanking": general_payload,
        },
        "ranking_by_scope": {
            "daily": daily_payload,
            "diario": daily_payload,
            "dia": daily_payload,
            "general": general_payload,
            "geral": general_payload,
            "global": general_payload,
        },
        "rankingByScope": {
            "daily": daily_payload,
            "diario": daily_payload,
            "dia": daily_payload,
            "general": general_payload,
            "geral": general_payload,
            "global": general_payload,
        },
    }
    payload_candidates: tuple[dict[str, Any], ...] = (base_payload, legacy_payload)
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "kills_snapshot",
    }
    if token:
        headers["X-Aizen-Token"] = token

    snapshot_cache_key, snapshot_urls = kills_snapshot_url_candidates(endpoint_url)
    with requests.Session() as session:
        def confirmed_persisted_snapshot_state(
            delays: tuple[float, ...] = KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
        ) -> RealtimeState | None:
            try:
                return fetch_confirmed_kills_snapshot_endpoint_state(
                    endpoint_url,
                    daily_players,
                    general_players,
                    device_id=device_id,
                    device_name=device_name,
                    room=room,
                    token=token,
                    session=session,
                    delays=delays,
                )
            except Exception:
                return None

        def remember_persisted_snapshot_url(snapshot_url: str) -> None:
            if snapshot_url.rstrip("/").endswith("/action"):
                return
            remember_kills_snapshot_endpoint(snapshot_cache_key, snapshot_url)

        final_state: RealtimeState | None = None
        latest_rank_state: RealtimeState | None = None
        weak_snapshot_ack_seen = False
        for snapshot_url in snapshot_urls:
            for payload in payload_candidates:
                try:
                    response = session.post(
                        snapshot_url,
                        json=payload,
                        headers=headers,
                        timeout=KILLS_POST_TIMEOUT_SECONDS,
                        allow_redirects=False,
                    )
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("Location", "")
                        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
                    response.raise_for_status()
                    state = parse_realtime_state(response.text)
                    response_acknowledged = response_acknowledges_kills_snapshot(response.text)
                    if response_confirms_persisted_kills_snapshot(response.text, state, daily_players, general_players):
                        response_acknowledged = True
                    confirmation_checked = False
                    if kills_snapshot_matches_state(state, daily_players, general_players):
                        confirmation_checked = True
                        try:
                            confirmed_state, latest_rank_state = fetch_kills_rank_confirmation(
                                endpoint_url,
                                daily_players,
                                general_players,
                                device_id=device_id,
                                device_name=device_name,
                                room=room,
                                token=token,
                                session=session,
                                delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
                            )
                        except Exception:
                            confirmed_state = None
                        if confirmed_state is not None:
                            persisted_state = confirmed_persisted_snapshot_state()
                            if persisted_state is not None:
                                remember_persisted_snapshot_url(snapshot_url)
                                return persisted_state
                            latest_rank_state = confirmed_state
                    if not confirmation_checked and not response_acknowledged:
                        try:
                            confirmed_state, latest_rank_state = fetch_kills_rank_confirmation(
                                endpoint_url,
                                daily_players,
                                general_players,
                                device_id=device_id,
                                device_name=device_name,
                                room=room,
                                token=token,
                                session=session,
                                delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
                            )
                            if confirmed_state is not None:
                                persisted_state = confirmed_persisted_snapshot_state()
                                if persisted_state is not None:
                                    remember_persisted_snapshot_url(snapshot_url)
                                    return persisted_state
                                latest_rank_state = confirmed_state
                        except Exception:
                            pass
                    if response_acknowledged:
                        weak_snapshot_ack_seen = True
                        persisted_state = confirmed_persisted_snapshot_state(delays=(0.0,))
                        if persisted_state is not None:
                            try:
                                confirmed_rank_state, latest_rank_state = fetch_kills_rank_confirmation(
                                    endpoint_url,
                                    daily_players,
                                    general_players,
                                    device_id=device_id,
                                    device_name=device_name,
                                    room=room,
                                    token=token,
                                    session=session,
                                    delays=(0.0,),
                                )
                            except Exception:
                                confirmed_rank_state = None
                            if confirmed_rank_state is not None:
                                remember_persisted_snapshot_url(snapshot_url)
                                return persisted_state
                        continue
                except requests.HTTPError as exc:
                    status_code = exc.response.status_code if exc.response is not None else 0
                    if status_code in {400, 404, 405, 409, 422}:
                        forget_kills_snapshot_endpoint(snapshot_cache_key, snapshot_url)
                        continue
                    raise
                except requests.RequestException:
                    raise
                except Exception:
                    continue
            if weak_snapshot_ack_seen:
                persisted_state = confirmed_persisted_snapshot_state()
                if persisted_state is not None:
                    try:
                        confirmed_rank_state, latest_rank_state = fetch_kills_rank_confirmation(
                            endpoint_url,
                            daily_players,
                            general_players,
                            device_id=device_id,
                            device_name=device_name,
                            room=room,
                            token=token,
                            session=session,
                            delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
                        )
                    except Exception:
                        confirmed_rank_state = None
                    if confirmed_rank_state is not None:
                        remember_persisted_snapshot_url(snapshot_url)
                        return persisted_state
                continue

        persisted_state = confirmed_persisted_snapshot_state()
        if persisted_state is not None:
            rank_ready = latest_rank_state is not None and kills_snapshot_matches_state(
                latest_rank_state,
                daily_players,
                general_players,
            )
            if not rank_ready:
                try:
                    confirmed_rank_state, latest_rank_state = fetch_kills_rank_confirmation(
                        endpoint_url,
                        daily_players,
                        general_players,
                        device_id=device_id,
                        device_name=device_name,
                        room=room,
                        token=token,
                        session=session,
                        delays=(0.0,),
                    )
                    rank_ready = confirmed_rank_state is not None
                except Exception:
                    rank_ready = False
            if rank_ready:
                return persisted_state

        try:
            current_state = latest_rank_state
            if current_state is None:
                current_state = fetch_kills_rank_realtime(
                    endpoint_url,
                    device_id=device_id,
                    device_name=device_name,
                    room=room,
                    token=token,
                    session=session,
                )
            if kills_snapshot_matches_state(current_state, daily_players, general_players):
                persisted_state = confirmed_persisted_snapshot_state()
                if persisted_state is not None:
                    return persisted_state
            current_daily = sorted_player_kills(current_state.daily_ranking or [])
            current_general = sorted_player_kills(
                current_state.global_ranking
                or ([] if current_state.daily_ranking else current_state.players or [])
            )
            delta_actions = (
                kills_delta_actions(current_daily, daily_players, "daily")
                + kills_delta_actions(current_general, general_players, "general")
            )
            reset_replace_count = 2 + len(daily_players) + len(general_players)
            if delta_actions and len(delta_actions) < reset_replace_count:
                for action, player, kill_value, action_scope in delta_actions:
                    final_state = send_kills_action_update(
                        endpoint_url,
                        action,
                        player=player,
                        kills=kill_value,
                        scope=action_scope,
                        device_id=device_id,
                        device_name=device_name,
                        room=room,
                        token=token,
                        session=session,
                        parse_response=False,
                    )
                try:
                    fetched_state = fetch_confirmed_kills_rank_state(
                        endpoint_url,
                        daily_players,
                        general_players,
                        device_id=device_id,
                        device_name=device_name,
                        room=room,
                        token=token,
                        session=session,
                    )
                    if fetched_state is not None:
                        persisted_state = confirmed_persisted_snapshot_state()
                        if persisted_state is not None:
                            return persisted_state
                except Exception:
                    pass
        except Exception:
            pass

        final_state = send_kills_action_update(
            endpoint_url,
            "reset_daily",
            scope="daily",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=session,
            parse_response=False,
        )
        final_state = send_kills_action_update(
            endpoint_url,
            "reset_general",
            scope="general",
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=session,
            parse_response=False,
        )
        for player in daily_players:
            final_state = send_kills_action_update(
                endpoint_url,
                "set",
                player=player,
                kills=player.kills,
                scope="daily",
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                parse_response=False,
            )
        for player in general_players:
            final_state = send_kills_action_update(
                endpoint_url,
                "set",
                player=player,
                kills=player.kills,
                scope="general",
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                parse_response=False,
            )
    try:
        fetched_state = fetch_confirmed_kills_rank_state(
            endpoint_url,
            daily_players,
            general_players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        if fetched_state is not None:
            persisted_state = fetch_confirmed_kills_snapshot_endpoint_state(
                endpoint_url,
                daily_players,
                general_players,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
            )
            if persisted_state is not None:
                return persisted_state
    except Exception:
        pass
    raise RuntimeError(
        "Jarvis respondeu, mas o painel principal nao confirmou o ranking diario/geral enviado. "
        "Clique em Atualizar rank e tente Salvar de novo."
    )


def post_kills_snapshot_once(
    endpoint_url: str,
    daily_players: list[PlayerKill],
    general_players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
) -> RealtimeState | None:
    daily_players = sorted_player_kills(daily_players)
    general_players = sorted_player_kills(general_players)
    daily_payload = player_wire_payload(daily_players)
    general_payload = player_wire_payload(general_players)
    daily_count = len(daily_players)
    general_count = len(general_players)
    daily_kills_total = sum(player.kills for player in daily_players)
    general_kills_total = sum(player.kills for player in general_players)
    payload = {
        "source": "aizen-stream-control",
        "mode": "kills_snapshot",
        "app_version": APP_VERSION,
        "sync_version": 4,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "revision": int(time.time() * 1000),
        "action": "replace",
        "replace": True,
        "return_state": True,
        "return_persisted": True,
        "confirm_persisted": True,
        "scope": "both",
        "scopes": ["daily", "general"],
        "replace_daily": True,
        "replaceDaily": True,
        "replace_general": True,
        "replaceGeneral": True,
        "players": general_payload,
        "ranking": general_payload,
        "global_ranking": general_payload,
        "globalRanking": general_payload,
        "general_ranking": general_payload,
        "generalRanking": general_payload,
        "geral_ranking": general_payload,
        "geralRanking": general_payload,
        "global": general_payload,
        "daily_ranking": daily_payload,
        "dailyRanking": daily_payload,
        "daily_rank": daily_payload,
        "dailyRank": daily_payload,
        "day_ranking": daily_payload,
        "dayRanking": daily_payload,
        "dia_ranking": daily_payload,
        "diaRanking": daily_payload,
        "rank_daily": daily_payload,
        "rankDaily": daily_payload,
        "rank_dia": daily_payload,
        "rankDia": daily_payload,
        "ranking_daily": daily_payload,
        "rankingDaily": daily_payload,
        "daily": daily_payload,
        "day": daily_payload,
        "dia": daily_payload,
        "general": general_payload,
        "geral": general_payload,
        "rankings": {
            "daily": daily_payload,
            "daily_ranking": daily_payload,
            "dailyRanking": daily_payload,
            "day": daily_payload,
            "dia": daily_payload,
            "dia_ranking": daily_payload,
            "diaRanking": daily_payload,
            "rank_daily": daily_payload,
            "rankDaily": daily_payload,
            "global": general_payload,
            "general": general_payload,
            "general_ranking": general_payload,
            "generalRanking": general_payload,
            "geral": general_payload,
            "geral_ranking": general_payload,
            "geralRanking": general_payload,
        },
        "ranking_by_scope": {
            "daily": daily_payload,
            "diario": daily_payload,
            "dia": daily_payload,
            "general": general_payload,
            "geral": general_payload,
            "global": general_payload,
        },
        "rankingByScope": {
            "daily": daily_payload,
            "diario": daily_payload,
            "dia": daily_payload,
            "general": general_payload,
            "geral": general_payload,
            "global": general_payload,
        },
        "total_players": general_count,
        "total_kills": general_kills_total,
        "daily_total_players": daily_count,
        "daily_total_kills": daily_kills_total,
        "totals": {
            "total_players": general_count,
            "total_kills": general_kills_total,
            "daily_total_players": daily_count,
            "daily_total_kills": daily_kills_total,
        },
    }
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "kills_snapshot",
    }
    if token:
        headers["X-Aizen-Token"] = token
    http_session = session or requests
    response = http_session.post(
        derive_kills_snapshot_endpoint(endpoint_url),
        json=payload,
        headers=headers,
        timeout=KILLS_POST_TIMEOUT_SECONDS,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    response_state = parse_realtime_state(response.text)
    if response_confirms_persisted_kills_snapshot(response.text, response_state, daily_players, general_players):
        return response_state
    if not response_acknowledges_kills_snapshot(response.text):
        raise RuntimeError("Jarvis nao confirmou o snapshot leve.")
    return None


def sync_kills_snapshot_after_scope_save(
    endpoint_url: str,
    confirmed_state: RealtimeState,
    scope: str,
    players: list[PlayerKill],
    preserve_players: list[PlayerKill] | None = None,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> RealtimeState:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope not in {"daily", "general"}:
        return confirmed_state
    daily_players = kills_scope_players_from_state(confirmed_state, "daily")
    general_players = kills_scope_players_from_state(confirmed_state, "general")
    if clean_scope == "daily" and not kills_scope_matches_state(confirmed_state, "daily", players):
        daily_players = sorted_player_kills(players)
    if clean_scope == "general" and not kills_scope_matches_state(confirmed_state, "general", players):
        general_players = sorted_player_kills(players)
    if clean_scope == "daily" and not daily_players and players:
        daily_players = sorted_player_kills(players)
    if clean_scope == "general" and not general_players and players:
        general_players = sorted_player_kills(players)
    if preserve_players is not None:
        preserved_players = sorted_player_kills(preserve_players)
        if clean_scope == "daily" and not general_players:
            general_players = preserved_players
        if clean_scope == "general" and not daily_players:
            daily_players = preserved_players
    if not (daily_players or general_players):
        return confirmed_state
    post_error_message = ""
    with requests.Session() as session:
        try:
            posted_state = post_kills_snapshot_once(
                endpoint_url,
                daily_players,
                general_players,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
            )
            if posted_state is not None:
                snapshot_state = fetch_confirmed_kills_snapshot_endpoint_state(
                    endpoint_url,
                    daily_players,
                    general_players,
                    device_id=device_id,
                    device_name=device_name,
                    room=room,
                    token=token,
                    session=session,
                    delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
                )
                if snapshot_state is not None:
                    return snapshot_state
        except Exception as exc:
            post_error_message = str(exc)
        snapshot_state = fetch_confirmed_kills_snapshot_endpoint_state(
            endpoint_url,
            daily_players,
            general_players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=session,
            delays=KILLS_RANK_CONFIRM_DELAYS_SECONDS,
        )
    if snapshot_state is not None:
        return snapshot_state
    try:
        forced_state = send_kills_snapshot_update(
            endpoint_url,
            daily_players,
            general_players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
        return forced_state
    except Exception as exc:
        if not post_error_message:
            post_error_message = str(exc)
    if post_error_message:
        raise RuntimeError(
            "Jarvis confirmou o /rank, mas nao consegui atualizar o painel principal: "
            f"{post_error_message}"
        )
    raise RuntimeError(
        "Jarvis confirmou o /rank, mas o painel principal ainda nao retornou o ranking salvo. "
        "Aguarde alguns segundos, clique em Atualizar rank e tente Salvar novamente."
    )


def send_kills_scope_replace_update(
    endpoint_url: str,
    scope: str,
    players: list[PlayerKill],
    preserve_players: list[PlayerKill] | None = None,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> RealtimeState:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope not in {"daily", "general"}:
        clean_scope = "daily"
    try:
        state = send_kills_scope_bulk_action_update(
            endpoint_url,
            clean_scope,
            players,
            preserve_players=preserve_players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
    except Exception:
        state = send_kills_scope_action_replace_update(
            endpoint_url,
            clean_scope,
            players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
        )
    return sync_kills_snapshot_after_scope_save(
        endpoint_url,
        state,
        clean_scope,
        players,
        preserve_players=preserve_players,
        device_id=device_id,
        device_name=device_name,
        room=room,
        token=token,
    )


def send_kills_scope_bulk_action_update(
    endpoint_url: str,
    scope: str,
    players: list[PlayerKill],
    preserve_players: list[PlayerKill] | None = None,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> RealtimeState:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope not in {"daily", "general"}:
        clean_scope = "daily"
    players = sorted_player_kills(players)
    payload_players = player_wire_payload(players)
    players_count = len(players)
    kills_total = sum(player.kills for player in players)
    preserve_scope = "general" if clean_scope == "daily" else "daily"
    preserve_players_snapshot = sorted_player_kills(preserve_players or []) if preserve_players is not None else None
    payload: dict[str, Any] = {
        "source": "aizen-stream-control",
        "mode": "kills_action",
        "app_version": APP_VERSION,
        "sync_version": 4,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "revision": int(time.time() * 1000),
        "action": "replace",
        **kills_scope_payload_fields(clean_scope),
        "replace": True,
        "replace_scope": clean_scope,
        "replaceScope": clean_scope,
        "replace_daily": clean_scope == "daily",
        "replaceDaily": clean_scope == "daily",
        "replace_general": clean_scope == "general",
        "replaceGeneral": clean_scope == "general",
        "scopes": [clean_scope],
        "items": payload_players,
        "data": payload_players,
        "total_players": players_count,
        "total_kills": kills_total,
        "totals": {
            "total_players": players_count,
            "total_kills": kills_total,
        },
    }
    if clean_scope == "daily":
        payload.update(
            {
                "daily_ranking": payload_players,
                "dailyRanking": payload_players,
                "daily_rank": payload_players,
                "dailyRank": payload_players,
                "dia_ranking": payload_players,
                "diaRanking": payload_players,
                "daily": payload_players,
                "dia": payload_players,
                "daily_players": payload_players,
                "dailyPlayers": payload_players,
                "daily_player_count": players_count,
                "dailyPlayerCount": players_count,
                "daily_total_players": players_count,
                "dailyTotalPlayers": players_count,
                "daily_total_kills": kills_total,
                "dailyTotalKills": kills_total,
                "daily_kills": kills_total,
                "dailyKills": kills_total,
            }
        )
    else:
        payload.update(
            {
                "players": payload_players,
                "ranking": payload_players,
                "global_ranking": payload_players,
                "globalRanking": payload_players,
                "general_ranking": payload_players,
                "generalRanking": payload_players,
                "geral_ranking": payload_players,
                "geralRanking": payload_players,
                "general": payload_players,
                "geral": payload_players,
            }
        )
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "kills_action",
    }
    if token:
        headers["X-Aizen-Token"] = token
    with requests.Session() as session:
        if preserve_players_snapshot is None:
            previous_state = fetch_kills_rank_realtime(
                endpoint_url,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
                timeout=KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
            )
            if not (previous_state.daily_ranking or previous_state.global_ranking or previous_state.players):
                try:
                    base_previous_state = fetch_kills_realtime(
                        endpoint_url,
                        device_id=device_id,
                        device_name=device_name,
                        room=room,
                        token=token,
                        session=session,
                        timeout=KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
                    )
                    if base_previous_state.daily_ranking or base_previous_state.global_ranking or base_previous_state.players:
                        previous_state = base_previous_state
                except Exception:
                    pass
            preserve_players_snapshot = kills_scope_players_from_state(previous_state, preserve_scope)
        response = session.post(
            derive_kills_action_endpoint(endpoint_url),
            json=payload,
            headers=headers,
            timeout=KILLS_POST_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if 300 <= response.status_code < 400:
            location = response.headers.get("Location", "")
            raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
        response.raise_for_status()
        response_state = parse_realtime_state(response.text)
        if not response_acknowledges_kills_snapshot(response.text) and not kills_scope_matches_state(response_state, clean_scope, players):
            raise RuntimeError("Jarvis nao confirmou o replace em lote.")
        confirmed_state = fetch_confirmed_kills_scope_state(
            endpoint_url,
            clean_scope,
            players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=session,
            delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
        )
        if confirmed_state is None:
            raise RuntimeError("Jarvis nao confirmou o ranking no /rank apos replace em lote.")
        if not kills_scope_matches_state(confirmed_state, preserve_scope, preserve_players_snapshot):
            restored_state = send_kills_scope_action_replace_update(
                endpoint_url,
                preserve_scope,
                preserve_players_snapshot,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=session,
            )
            if not kills_scope_matches_state(restored_state, clean_scope, players):
                confirmed_state = fetch_confirmed_kills_scope_state(
                    endpoint_url,
                    clean_scope,
                    players,
                    device_id=device_id,
                    device_name=device_name,
                    room=room,
                    token=token,
                    session=session,
                    delays=KILLS_RANK_FAST_CONFIRM_DELAYS_SECONDS,
                )
                if confirmed_state is None:
                    raise RuntimeError("Jarvis alterou outro ranking durante o replace em lote.")
            else:
                confirmed_state = restored_state
        return confirmed_state


def send_kills_scope_action_replace_update(
    endpoint_url: str,
    scope: str,
    players: list[PlayerKill],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
    session: requests.Session | None = None,
) -> RealtimeState:
    clean_scope = normalize_kills_scope_value(scope)
    if clean_scope not in {"daily", "general"}:
        clean_scope = "daily"
    players = sorted_player_kills(players)
    reset_action = "reset_general" if clean_scope == "general" else "reset_daily"
    http_session = session or requests.Session()
    close_session = session is None
    try:
        send_kills_action_update(
            endpoint_url,
            reset_action,
            scope=clean_scope,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=http_session,
            parse_response=False,
        )
        for player in players:
            send_kills_action_update(
                endpoint_url,
                "set",
                player=player,
                kills=player.kills,
                scope=clean_scope,
                device_id=device_id,
                device_name=device_name,
                room=room,
                token=token,
                session=http_session,
                parse_response=False,
            )
        confirmed_state = fetch_confirmed_kills_scope_state(
            endpoint_url,
            clean_scope,
            players,
            device_id=device_id,
            device_name=device_name,
            room=room,
            token=token,
            session=http_session,
        )
        if confirmed_state is not None:
            return confirmed_state
    finally:
        if close_session:
            http_session.close()
    raise RuntimeError(
        f"Jarvis respondeu, mas o endpoint /rank nao confirmou o ranking {kills_scope_label(clean_scope).lower()} enviado. "
        "Clique em Atualizar rank e tente Salvar de novo."
    )


def send_ff_queue_realtime_update(
    endpoint_url: str,
    entries: list[FFQueueEntry],
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    payload_entries = ff_queue_payload(entries)
    payload = {
        "source": "aizen-stream-control",
        "mode": "ff_queue",
        "app_version": APP_VERSION,
        "sync_version": 2,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": now,
        "revision": int(time.time() * 1000),
        "device": {
            "id": device_id,
            "name": device_name,
            "app": APP_NAME,
            "version": APP_VERSION,
        },
        "queue": payload_entries,
        "items": payload_entries,
    }
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "ff_queue",
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        normalize_endpoint_url(endpoint_url),
        json=payload,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return response.text.strip()


def fetch_ff_queue_realtime(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> FFQueueState:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "ff_queue",
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.get(
        normalize_endpoint_url(endpoint_url),
        params={
            "mode": "ff_queue",
            "room": room,
            "client_id": device_id,
            "client_name": device_name,
            "app_version": APP_VERSION,
        },
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    return parse_ff_queue_state(response.text)


def derive_ff_queue_action_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-queue"):
        path = f"{path}/action"
    elif path.endswith("/freefire-queue"):
        path = f"{path}/action"
    elif path.endswith("/action"):
        path = path
    else:
        path = f"{path}/action"
    return parsed._replace(path=path, query="", fragment="").geturl()


def derive_tikfinity_ff_gifts_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/tikfinity/ff-gifts"):
        next_path = path
    else:
        next_path = "/api/tikfinity/ff-gifts"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def fetch_tikfinity_ff_gifts(
    endpoint_url: str,
    profile: str = "streamer1",
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.get(
        derive_tikfinity_ff_gifts_endpoint(endpoint_url),
        params={"profile": profile, "client_id": device_id, "client_name": device_name, "app_version": APP_VERSION},
        headers=headers,
        timeout=12,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Resposta TikFinity FF invalida.")
    return payload


def send_tikfinity_ff_gifts_action(
    endpoint_url: str,
    action: str,
    payload: dict[str, Any] | None = None,
    profile: str = "streamer1",
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = dict(payload or {})
    body.update(
        {
            "source": "aizen-stream-control",
            "app_version": APP_VERSION,
            "profile": profile,
            "client_id": device_id,
            "client_name": device_name,
            "updated_by": device_name,
            "action": action,
        }
    )
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        derive_tikfinity_ff_gifts_endpoint(endpoint_url),
        json=body,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Resposta TikFinity FF invalida.")
    return result


def send_ff_queue_action_update(
    endpoint_url: str,
    action: str,
    entry: FFQueueEntry | None = None,
    credits: int | None = None,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> FFQueueState:
    payload: dict[str, Any] = {
        "source": "aizen-stream-control",
        "mode": "ff_queue",
        "app_version": APP_VERSION,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "action": action,
    }
    if entry is not None:
        payload.update(
            {
                "user_id": entry.user_id or entry.panel_user_id,
                "panel_user_id": entry.panel_user_id,
                "display_name": entry.name,
                "name": entry.name,
                "ff_player_id": entry.ff_player_id,
                "credits": max(0, normalize_kill_value(entry.rooms)),
                "rooms": max(0, normalize_kill_value(entry.rooms)),
            }
        )
    if credits is not None:
        payload["credits"] = max(0, normalize_kill_value(credits))
        payload["rooms"] = max(0, normalize_kill_value(credits))

    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "ff_queue",
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        derive_ff_queue_action_endpoint(endpoint_url),
        json=payload,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return parse_ff_queue_state(response.text)


def overlay_payload(
    players: list[PlayerKill],
    entries: list[FFQueueEntry],
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload_players = player_wire_payload(players)
    payload_queue = ff_queue_payload(entries)
    active_queue = [item for item in payload_queue if item.get("status") != "Concluido"]
    return {
        "players": payload_players,
        "queue": payload_queue,
        "summary": {
            "players_count": len(payload_players),
            "total_kills": sum(int(item.get("kills", 0)) for item in payload_players),
            "queue_active_count": len(active_queue),
            "queue_playing_count": sum(1 for item in active_queue if item.get("status") == "Jogando"),
        },
        "options": options or {},
    }


def send_ff_overlay_realtime_update(
    endpoint_url: str,
    players: list[PlayerKill],
    entries: list[FFQueueEntry],
    options: dict[str, Any] | None = None,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> str:
    now = datetime.now().isoformat(timespec="seconds")
    payload = {
        "source": "aizen-stream-control",
        "mode": "ff_overlay",
        "app_version": APP_VERSION,
        "sync_version": 2,
        "room": room,
        "client_id": device_id,
        "client_name": device_name,
        "updated_by": device_name,
        "updated_at": now,
        "revision": int(time.time() * 1000),
        "device": {
            "id": device_id,
            "name": device_name,
            "app": APP_NAME,
            "version": APP_VERSION,
        },
        **overlay_payload(players, entries, options),
    }
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "ff_overlay",
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        normalize_endpoint_url(endpoint_url),
        json=payload,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return response.text.strip()


def fetch_ff_overlay_realtime(
    endpoint_url: str,
    device_id: str = "",
    device_name: str = "",
    room: str = "principal",
    token: str = "",
) -> tuple[RealtimeState, FFQueueState]:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-Room": room,
        "X-Aizen-App-Version": APP_VERSION,
        "X-Aizen-Mode": "ff_overlay",
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.get(
        normalize_endpoint_url(endpoint_url),
        params={
            "mode": "ff_overlay",
            "room": room,
            "client_id": device_id,
            "client_name": device_name,
            "app_version": APP_VERSION,
        },
        headers=headers,
        timeout=12,
    )
    response.raise_for_status()
    return parse_realtime_state(response.text), parse_ff_queue_state(response.text)


def derive_ff_overlay_config_endpoint(endpoint_url: str) -> str:
    clean = normalize_endpoint_url(endpoint_url)
    parsed = urlparse(clean)
    path = parsed.path.rstrip("/")
    if path.endswith("/api/freefire-overlay/config"):
        next_path = path
    elif path.endswith("/api/freefire-overlay/data"):
        next_path = path[: -len("/data")] + "/config"
    elif path.endswith("/api/freefire-overlay"):
        next_path = f"{path}/config"
    elif path.endswith("/freefire/overlay"):
        next_path = "/api/freefire-overlay/config"
    else:
        next_path = "/api/freefire-overlay/config"
    return parsed._replace(path=next_path, query="", fragment="").geturl()


def fetch_ff_overlay_config(
    endpoint_url: str,
    profile: str = "streamer1",
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.get(
        derive_ff_overlay_config_endpoint(endpoint_url),
        params={"profile": profile, "client_id": device_id, "client_name": device_name, "app_version": APP_VERSION},
        headers=headers,
        timeout=12,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("Resposta de configuracao do Overlay FF invalida.")
    return payload


def send_ff_overlay_config_action(
    endpoint_url: str,
    action: str,
    payload: dict[str, Any] | None = None,
    profile: str = "streamer1",
    device_id: str = "",
    device_name: str = "",
    token: str = "",
) -> dict[str, Any]:
    body: dict[str, Any] = dict(payload or {})
    body.update(
        {
            "source": "aizen-stream-control",
            "app_version": APP_VERSION,
            "profile": profile,
            "client_id": device_id,
            "client_name": device_name,
            "updated_by": device_name,
            "action": action,
        }
    )
    headers = {
        "X-Aizen-Client-Id": device_id,
        "X-Aizen-Client-Name": device_name,
        "X-Aizen-App-Version": APP_VERSION,
    }
    if token:
        headers["X-Aizen-Token"] = token
    response = requests.post(
        derive_ff_overlay_config_endpoint(endpoint_url),
        json=body,
        headers=headers,
        timeout=20,
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict):
        raise RuntimeError("Resposta de configuracao do Overlay FF invalida.")
    return result


def send_to_discord(webhook_url: str, content: str, screenshot: Path | None) -> None:
    if not webhook_url or webhook_url == "COLE_AQUI_O_WEBHOOK_DO_DISCORD":
        raise ValueError("Configure discord_webhook_url em config.json.")

    data = {"content": content}
    files = None
    handle = None
    try:
        if screenshot is not None:
            handle = screenshot.open("rb")
            files = {"file": (screenshot.name, handle, "image/png")}
        response = requests.post(webhook_url, data=data, files=files, timeout=20)
        response.raise_for_status()
    finally:
        if handle:
            handle.close()


def normalize_endpoint_url(endpoint_url: str) -> str:
    endpoint_url = endpoint_url.strip()
    if endpoint_url.startswith("http://"):
        host = (urlparse(endpoint_url).hostname or "").lower()
        if host.endswith("squareweb.app"):
            return "https://" + endpoint_url[len("http://") :]
    return endpoint_url


def derive_jarvis_endpoint(base_url: str, panel: str) -> str:
    base_url = normalize_endpoint_url(base_url).rstrip("/")
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    path = parsed.path.rstrip("/")
    origin = parsed._replace(path="", params="", query="", fragment="").geturl().rstrip("/")
    if path.endswith(("/api/freefire-kills", "/api/freefire-queue", "/api/freefire-overlay")):
        root_path = path.rsplit("/", 1)[0]
        root = parsed._replace(path=root_path, params="", query="", fragment="").geturl().rstrip("/")
    else:
        path_parts = [part for part in path.split("/") if part]
        if "api" in path_parts:
            api_index = path_parts.index("api")
            root_path = "/" + "/".join(path_parts[: api_index + 1])
        else:
            root_path = "/api"
        root = f"{origin}{root_path}".rstrip("/")
    suffix = {
        "queue": "freefire-queue",
        "overlay": "freefire-overlay",
    }.get(panel, "freefire-kills")
    return f"{root}/{suffix}"


def version_tuple(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version)
    return tuple(int(number) for number in numbers[:4]) or (0,)


def is_newer_version(remote_version: str, current_version: str = APP_VERSION) -> bool:
    remote = list(version_tuple(remote_version))
    current = list(version_tuple(current_version))
    length = max(len(remote), len(current))
    remote.extend([0] * (length - len(remote)))
    current.extend([0] * (length - len(current)))
    return tuple(remote) > tuple(current)


def update_log_path() -> Path:
    return APP_DIR / "update.log"


def update_workspace_dir() -> Path:
    workspace = APP_DIR / "updates"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def write_update_log(message: str) -> None:
    try:
        with update_log_path().open("a", encoding="utf-8") as handle:
            handle.write(f"[{datetime.now().isoformat(timespec='seconds')}] {message}\n")
    except OSError:
        pass


class UpdateStatusWindow:
    def __init__(self) -> None:
        import tkinter as update_tk
        from tkinter import ttk

        self.tk = update_tk
        self.root = update_tk.Tk()
        self.root.title("Aizen Stream Control")
        self.root.geometry("460x190")
        self.root.resizable(False, False)
        self.root.configure(bg="#050506")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        try:
            if APP_ICON.exists():
                self.root.iconbitmap(str(APP_ICON))
        except update_tk.TclError:
            pass

        self.root.update_idletasks()
        width = 460
        height = 190
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        shell = update_tk.Frame(self.root, bg="#050506")
        shell.pack(fill=update_tk.BOTH, expand=True, padx=26, pady=22)
        update_tk.Label(
            shell,
            text=APP_NAME,
            fg="#f8f2f1",
            bg="#050506",
            font=("Segoe UI Semibold", 18),
        ).pack(anchor="w")
        self.title_var = update_tk.StringVar(value="Buscando atualizações...")
        self.detail_var = update_tk.StringVar(value="Verificando manifesto remoto.")
        update_tk.Label(
            shell,
            textvariable=self.title_var,
            fg="#ff4d4d",
            bg="#050506",
            font=("Segoe UI Semibold", 12),
        ).pack(anchor="w", pady=(18, 2))
        update_tk.Label(
            shell,
            textvariable=self.detail_var,
            fg="#b8a6a5",
            bg="#050506",
            font=("Segoe UI", 10),
            wraplength=400,
            justify="left",
        ).pack(anchor="w")
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except update_tk.TclError:
            pass
        style.configure(
            "Aizen.Horizontal.TProgressbar",
            troughcolor="#171014",
            background="#ff1717",
            bordercolor="#3a1518",
            lightcolor="#ff4d4d",
            darkcolor="#b10f17",
        )
        self.progress = ttk.Progressbar(
            shell,
            mode="indeterminate",
            length=400,
            style="Aizen.Horizontal.TProgressbar",
        )
        self.progress.pack(fill=update_tk.X, pady=(18, 0))
        self.progress.start(12)
        self.is_determinate = False
        self.pump()

    def pump(self) -> None:
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def set_status(self, title: str, detail: str = "", percent: int | None = None) -> None:
        try:
            self.title_var.set(title)
            self.detail_var.set(detail)
            if percent is not None:
                if not self.is_determinate:
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=100)
                    self.is_determinate = True
                self.progress["value"] = max(0, min(100, percent))
            elif self.is_determinate:
                self.progress.configure(mode="indeterminate")
                self.progress.start(12)
                self.is_determinate = False
            self.pump()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self.progress.stop()
            self.root.destroy()
        except Exception:
            pass


def cache_busted_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_={int(time.time())}"


def read_update_manifest(manifest_url: str) -> dict[str, Any]:
    response = requests.get(
        cache_busted_url(manifest_url.strip()),
        timeout=UPDATE_MANIFEST_TIMEOUT_SECONDS,
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
        },
    )
    response.raise_for_status()
    data = json.loads(response.content.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Manifesto de atualizacao invalido.")
    return data


def update_asset_from_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    windows = manifest.get("windows") if isinstance(manifest.get("windows"), dict) else {}
    source = windows or manifest
    version = str(source.get("version") or manifest.get("version") or "").strip()
    url = str(
        source.get("portable_url")
        or source.get("exe_url")
        or source.get("download_url")
        or source.get("url")
        or ""
    ).strip()
    sha256 = str(source.get("sha256") or manifest.get("sha256") or "").strip().lower()
    notes = str(source.get("notes") or manifest.get("notes") or "").strip()
    if not version or not url:
        raise ValueError("Manifesto precisa ter version e url/exe_url/portable_url.")
    return {"version": version, "url": url, "sha256": sha256, "notes": notes}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_update_asset(url: str, sha256: str = "", progress_callback: Any | None = None) -> Path:
    suffix = Path(urlparse(url).path).suffix or ".bin"
    last_error: Exception | None = None

    def report_progress(percent: int, detail: str = "") -> None:
        if not progress_callback:
            return
        try:
            progress_callback(max(0, min(100, percent)), detail)
        except TypeError:
            progress_callback(max(0, min(100, percent)))
        except Exception:
            pass

    for attempt in range(1, UPDATE_DOWNLOAD_ATTEMPTS + 1):
        target_dir = update_workspace_dir() / f"aizen_update_{int(time.time())}_{secrets.token_hex(4)}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"update{suffix}"
        downloaded = 0
        total = 0
        try:
            report_progress(0, f"Iniciando download (tentativa {attempt}/{UPDATE_DOWNLOAD_ATTEMPTS}).")
            with requests.get(
                url,
                timeout=(UPDATE_DOWNLOAD_CONNECT_TIMEOUT_SECONDS, UPDATE_DOWNLOAD_READ_TIMEOUT_SECONDS),
                stream=True,
                headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"},
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length") or 0)
                last_percent = -1
                last_report_at = 0.0
                with target.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=UPDATE_DOWNLOAD_CHUNK_BYTES):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            percent = min(99, int(downloaded * 100 / total))
                            now = time.monotonic()
                            if percent != last_percent or now - last_report_at >= 1.0:
                                downloaded_mb = downloaded / (1024 * 1024)
                                total_mb = total / (1024 * 1024)
                                report_progress(
                                    percent,
                                    f"Baixando {downloaded_mb:.1f}/{total_mb:.1f} MB "
                                    f"(tentativa {attempt}/{UPDATE_DOWNLOAD_ATTEMPTS}).",
                                )
                                last_percent = percent
                                last_report_at = now
                        else:
                            downloaded_mb = downloaded / (1024 * 1024)
                            report_progress(
                                min(95, 10 + int(downloaded_mb)),
                                f"Baixando {downloaded_mb:.1f} MB (tentativa {attempt}/{UPDATE_DOWNLOAD_ATTEMPTS}).",
                            )
            if total and downloaded < total:
                raise RuntimeError(f"Download incompleto: {downloaded} de {total} bytes recebidos.")
            if sha256:
                report_progress(99, "Conferindo arquivo baixado.")
                actual = sha256_file(target)
                if actual.lower() != sha256.lower():
                    raise RuntimeError(f"SHA256 da atualizacao nao confere. Esperado {sha256}, obtido {actual}.")
            report_progress(100, "Download concluido.")
            return target
        except Exception as exc:
            last_error = exc
            write_update_log(
                "Download da atualizacao falhou "
                f"(tentativa {attempt}/{UPDATE_DOWNLOAD_ATTEMPTS}, bytes={downloaded}/{total or '?'})"
                f": {exc}"
            )
            try:
                shutil.rmtree(target_dir, ignore_errors=True)
            except OSError:
                pass
            if attempt >= UPDATE_DOWNLOAD_ATTEMPTS:
                break
            report_progress(
                min(99, max(0, int(downloaded * 100 / total)) if total else 0),
                f"Rede oscilou; tentando novamente ({attempt + 1}/{UPDATE_DOWNLOAD_ATTEMPTS}).",
            )
            time.sleep(1.5 * attempt)
    raise RuntimeError(f"Download da atualizacao falhou apos {UPDATE_DOWNLOAD_ATTEMPTS} tentativas: {last_error}")


def resolve_downloaded_exe(downloaded: Path) -> Path:
    if downloaded.suffix.lower() == ".zip":
        extract_dir = downloaded.parent / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(downloaded) as archive:
            archive.extractall(extract_dir)
        preferred = list(extract_dir.rglob(APP_EXE_NAME))
        candidates = preferred or list(extract_dir.rglob("*.exe"))
        if not candidates:
            raise RuntimeError("ZIP da atualizacao nao contem executavel.")
        return candidates[0]
    if downloaded.suffix.lower() != ".exe":
        raise RuntimeError("Atualizacao precisa ser um .exe ou .zip contendo o .exe.")
    return downloaded


def launch_self_replacement(new_exe: Path) -> None:
    current_exe = Path(sys.executable).resolve()
    staged_exe = new_exe.parent / APP_EXE_NAME
    if new_exe.resolve() != staged_exe.resolve():
        shutil.copy2(new_exe, staged_exe)

    def ps_literal(value: Path | str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    expected_size = staged_exe.stat().st_size
    expected_hash = sha256_file(staged_exe)
    log_path = update_log_path()
    script = new_exe.parent / "apply_update.ps1"
    script.write_text(
        "\n".join(
            [
                "$ErrorActionPreference = 'SilentlyContinue'",
                f"$Source = {ps_literal(staged_exe)}",
                f"$Target = {ps_literal(current_exe)}",
                f"$TargetDir = {ps_literal(current_exe.parent)}",
                f"$LogPath = {ps_literal(log_path)}",
                f"$ExpectedSize = {expected_size}",
                f"$ExpectedHash = '{expected_hash}'",
                "function Write-AizenLog($Message) {",
                "  try { Add-Content -LiteralPath $LogPath -Value ('[' + (Get-Date -Format s) + '] ' + $Message) -Encoding UTF8 } catch { }",
                "}",
                "Write-AizenLog 'Aplicador de update iniciado.'",
                "$copied = $false",
                "for ($try = 0; $try -lt 45; $try++) {",
                "  Start-Sleep -Milliseconds 800",
                "  try {",
                "    Copy-Item -LiteralPath $Source -Destination $Target -Force -ErrorAction Stop",
                "    $item = Get-Item -LiteralPath $Target -ErrorAction Stop",
                "    if ($item.Length -ge $ExpectedSize) {",
                "      $hash = (Get-FileHash -LiteralPath $Target -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()",
                "      if ($hash -eq $ExpectedHash.ToLowerInvariant()) { $copied = $true; break }",
                "    }",
                "  } catch { }",
                "}",
                "if (-not $copied) { Write-AizenLog 'Falha ao copiar/verificar update.'; exit 1 }",
                "Write-AizenLog 'Executavel atualizado e hash verificado. Aguardando limpeza do runtime antigo.'",
                "Start-Sleep -Seconds 12",
                "try { Get-ChildItem -LiteralPath $TargetDir -Directory -Filter '_MEI*' -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue } catch { }",
                "Get-ChildItem Env: | Where-Object { $_.Name -like '_PYI*' } | ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) -ErrorAction SilentlyContinue }",
                "$env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
                "Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue",
                "Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue",
                "Remove-Item Env:TCL_LIBRARY -ErrorAction SilentlyContinue",
                "Remove-Item Env:TK_LIBRARY -ErrorAction SilentlyContinue",
                "if ($env:PATH) {",
                "  $env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and ($_ -notmatch '_MEI\\d+') }) -join ';'",
                "}",
                "$started = $false",
                "try {",
                "  Start-Process -FilePath $Target -WorkingDirectory $TargetDir -UseNewEnvironment -ErrorAction Stop",
                "  $started = $true",
                "  Write-AizenLog 'App reiniciado com UseNewEnvironment.'",
                "} catch { Write-AizenLog ('Falha UseNewEnvironment: ' + $_.Exception.Message) }",
                "if (-not $started) {",
                "  try {",
                "    Start-Process -FilePath $Target -WorkingDirectory $TargetDir -ErrorAction Stop",
                "    $started = $true",
                "    Write-AizenLog 'App reiniciado por Start-Process padrao.'",
                "  } catch { Write-AizenLog ('Falha Start-Process padrao: ' + $_.Exception.Message) }",
                "}",
                "if (-not $started) {",
                "  try { Start-Process -FilePath (Join-Path $env:WINDIR 'explorer.exe') -ArgumentList ('\"' + $Target + '\"') -ErrorAction Stop; Write-AizenLog 'App reiniciado via explorer.exe.' } catch { Write-AizenLog ('Falha final explorer.exe: ' + $_.Exception.Message) }",
                "}",
                "Start-Sleep -Seconds 3",
                "Remove-Item -LiteralPath $Source -Force -ErrorAction SilentlyContinue",
                "Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue",
                "",
            ]
        ),
        encoding="utf-8",
    )
    creationflags = 0x08000000 if os.name == "nt" else 0
    clean_env = os.environ.copy()
    for key in list(clean_env):
        if key.startswith("_PYI") or key in {"PYTHONHOME", "PYTHONPATH", "TCL_LIBRARY", "TK_LIBRARY"}:
            clean_env.pop(key, None)
    clean_env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    if clean_env.get("PATH"):
        clean_env["PATH"] = ";".join(
            part for part in clean_env["PATH"].split(";") if part and not re.search(r"_MEI\d+", part, re.IGNORECASE)
        )
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(script),
        ],
        cwd=str(new_exe.parent),
        creationflags=creationflags,
        env=clean_env,
    )


def maybe_apply_auto_update(config_path: Path) -> bool:
    if not IS_FROZEN:
        return False
    status_window: UpdateStatusWindow | None = None
    try:
        config = load_config(config_path)
        if not bool(config.get("auto_update_enabled", True)):
            return False
        manifest_url = str(config.get("updates_manifest_url", "")).strip()
        if not manifest_url:
            return False
        asset = update_asset_from_manifest(read_update_manifest(manifest_url))
        if not is_newer_version(asset["version"]):
            return False
        write_update_log(f"Atualizacao encontrada: {APP_VERSION} -> {asset['version']}")
        status_window = UpdateStatusWindow()
        status_window.set_status(
            "Atualização encontrada",
            f"Baixando versão {asset['version']}...",
        )
        def update_download_progress(percent: int, detail: str = "") -> None:
            status_window.set_status(
                "Baixando atualização",
                detail or f"Recebendo versão {asset['version']}...",
                percent,
            )

        downloaded = download_update_asset(
            asset["url"],
            asset.get("sha256", ""),
            update_download_progress,
        )
        status_window.set_status("Validando atualização", "Conferindo arquivo baixado...", 100)
        new_exe = resolve_downloaded_exe(downloaded)
        status_window.set_status("Aplicando atualização", "O app será reiniciado automaticamente.", 100)
        launch_self_replacement(new_exe)
        write_update_log("Atualizacao baixada; reiniciando para aplicar.")
        time.sleep(1.2)
        return True
    except Exception as exc:
        write_update_log(f"Falha ao atualizar: {exc}")
        if status_window is not None:
            status_window.set_status("Não foi possível atualizar", "Abrindo a versão atual do app.")
            time.sleep(1.0)
        return False
    finally:
        if status_window is not None:
            status_window.close()


def send_to_jarvis_endpoint(endpoint_url: str, content: str, players: list[PlayerKill]) -> str:
    payload = {
        "source": "aizen-stream-control",
        "mode": "manual",
        "app_version": APP_VERSION,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "content": content,
        "players": player_wire_payload(players),
    }
    response = requests.post(normalize_endpoint_url(endpoint_url), json=payload, timeout=20, allow_redirects=False)
    if 300 <= response.status_code < 400:
        location = response.headers.get("Location", "")
        raise RuntimeError(f"Endpoint redirecionou para {location}. Use a URL final HTTPS.")
    response.raise_for_status()
    return response.text.strip()


def foreground_window_box() -> tuple[int, int, int, int] | None:
    if os.name != "nt":
        return None
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None

    rect = ctypes.wintypes.RECT()
    if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    if rect.right <= rect.left or rect.bottom <= rect.top:
        return None
    return (rect.left, rect.top, rect.right, rect.bottom)


def active_monitor_box() -> tuple[int, int, int, int] | None:
    window_box = foreground_window_box()
    if not window_box or os.name != "nt":
        return None

    left, top, right, bottom = window_box
    center_x = (left + right) // 2
    center_y = (top + bottom) // 2
    monitors: list[tuple[int, int, int, int]] = []

    monitor_enum_proc = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.wintypes.RECT),
        ctypes.c_double,
    )

    def callback(_monitor: int, _dc: int, rect: ctypes.wintypes.RECT, _data: float) -> int:
        monitors.append((rect.contents.left, rect.contents.top, rect.contents.right, rect.contents.bottom))
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(0, 0, monitor_enum_proc(callback), 0)
    for monitor in monitors:
        x1, y1, x2, y2 = monitor
        if x1 <= center_x < x2 and y1 <= center_y < y2:
            return monitor
    return None


def capture_screen(captures_dir: Path, capture_target: str = "primary") -> Path:
    captures_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = captures_dir / f"freefire_{stamp}.png"

    image_grab = ensure_image_grab_module()
    target = (capture_target or "primary").strip().lower()
    if target == "all":
        image = image_grab.grab(all_screens=True)
    elif target == "active_monitor":
        box = active_monitor_box()
        image = image_grab.grab(bbox=box) if box else image_grab.grab()
    elif target == "foreground":
        box = foreground_window_box()
        image = image_grab.grab(bbox=box) if box else image_grab.grab()
    else:
        image = image_grab.grab()

    image.save(path)
    return path


def process_image(
    image_path: Path,
    config: dict[str, Any],
    dry_run: bool,
    keep_debug: bool,
    log: callable | None = None,
) -> list[PlayerKill]:
    def emit(message: str) -> None:
        if log:
            log(message)
        else:
            print(message)

    players = extract_players(image_path, config, keep_debug=keep_debug)
    players = filter_ignored_players(players, config.get("ignored_players", []))
    message = format_message(players, config.get("message_title", "Kills da partida"))
    emit(message)

    if not dry_run:
        jarvis_endpoint_url = config.get("jarvis_endpoint_url", "").strip()
        if jarvis_endpoint_url:
            response_text = send_to_jarvis_endpoint(jarvis_endpoint_url, message, players)
            if response_text:
                emit(f"Enviado para o endpoint do Jarvis Bot. Resposta: {response_text[:300]}")
            else:
                emit("Enviado para o endpoint do Jarvis Bot.")
        else:
            screenshot = image_path if config.get("attach_screenshot", True) else None
            send_to_discord(config["discord_webhook_url"], message, screenshot)
            emit("Enviado para o Discord.")
    return players


def hotkey_loop(config: dict[str, Any], dry_run: bool, keep_debug: bool, log: callable | None = None) -> None:
    def emit(message: str) -> None:
        if log:
            log(message)
        else:
            print(message)

    modifiers, key = parse_hotkey(config.get("hotkey", "CTRL+SHIFT+F12"))
    user32 = ctypes.windll.user32
    hotkey_id = 1

    if not user32.RegisterHotKey(None, hotkey_id, modifiers, key):
        raise RuntimeError("Nao consegui registrar o atalho. Tente outro atalho ou execute como administrador.")

    captures_dir = ROOT / config.get("captures_dir", "captures")
    emit(f"Rodando. Aperte {config.get('hotkey')} para capturar e enviar.")
    try:
        msg = ctypes.wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312 and msg.wParam == hotkey_id:
                try:
                    image_path = capture_screen(captures_dir, config.get("capture_target", "primary"))
                    emit(f"Captura salva: {image_path}")
                    process_image(image_path, config, dry_run=dry_run, keep_debug=keep_debug, log=log)
                except Exception as exc:
                    emit(f"Erro ao processar captura: {exc}")
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
    finally:
        user32.UnregisterHotKey(None, hotkey_id)


class HotkeyWorker:
    def __init__(self, config: dict[str, Any], dry_run: bool, keep_debug: bool, log: callable):
        self.config = json.loads(json.dumps(config))
        self.dry_run = dry_run
        self.keep_debug = keep_debug
        self.log = log
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            raise RuntimeError("O monitor ja esta rodando.")
        self.thread = threading.Thread(target=self._run, name="FreeFireHotkey", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        try:
            hotkey_loop(self.config, self.dry_run, self.keep_debug, log=self.log)
        except Exception as exc:
            self.log(f"Erro no monitor: {exc}")


class TikfinityRaffleWorker:
    def __init__(
        self,
        chat_url: str,
        command: str,
        duration_seconds: int,
        log: callable,
        source_mode: str = "browser",
        entries_normal: int = 1,
        entries_fan: int = 2,
        entries_super_fan: int = 3,
        entries_gift: int = 5,
        entries_sub: int = 10,
        user_cooldown_seconds: int = 8,
        include_moderators: bool = True,
    ):
        self.chat_url = chat_url.strip()
        self.command = command.strip().lower()
        self.duration_seconds = duration_seconds
        self.log = log
        self.source_mode = source_mode
        self.entries_by_tier = {
            "normal": max(1, int(entries_normal)),
            "fan": max(1, int(entries_fan)),
            "super_fan": max(1, int(entries_super_fan)),
            "gift": max(1, int(entries_gift)),
            "sub": max(1, int(entries_sub)),
        }
        self.user_cooldown_seconds = max(0, int(user_cooldown_seconds))
        self.include_moderators = include_moderators
        self.thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.finished_event = threading.Event()
        self.lock = threading.Lock()
        self.participants_by_key: dict[str, RaffleParticipant] = {}
        self.participant_names_seen: dict[str, str] = {}
        self.user_command_times: dict[str, float] = {}
        self.seen_messages: set[str] = set()
        self.seen_message_order: list[str] = []
        self.blocked_attempts: list[dict[str, Any]] = []
        self.current_winner: RaffleWinner | None = None
        self.drawn_winners: list[RaffleWinner] = []
        self.winner_messages: list[dict[str, str]] = []

    def start(self) -> None:
        if self.source_mode == "browser" and not self.chat_url:
            raise ValueError("Configure a URL do chat.")
        if not self.command:
            raise ValueError("Configure o comando do sorteio.")
        if self.duration_seconds <= 0:
            raise ValueError("A duracao do sorteio precisa ser maior que zero.")
        if self.thread and self.thread.is_alive():
            raise RuntimeError("O sorteio ja esta rodando.")

        self.stop_event.clear()
        self.finished_event.clear()
        target = self._run_external_events if self.source_mode == "events" else self._run
        self.thread = threading.Thread(target=target, name="TikfinityRaffle", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()

    def is_running(self) -> bool:
        return bool(self.thread and self.thread.is_alive() and not self.finished_event.is_set())

    def is_finished(self) -> bool:
        return self.finished_event.is_set()

    def participant_names(self) -> list[str]:
        with self.lock:
            return [participant.name for participant in self.participants_by_key.values()]

    def participant_items(self) -> list[RaffleParticipant]:
        with self.lock:
            return list(self.participants_by_key.values())

    def participant_count(self) -> int:
        with self.lock:
            return len(self.participants_by_key)

    def total_entries(self) -> int:
        with self.lock:
            return sum(max(1, int(participant.entries)) for participant in self.participants_by_key.values())

    def participant_history_items(self) -> list[dict[str, Any]]:
        with self.lock:
            return [
                {
                    "name": participant.name,
                    "key": participant.key,
                    "platform": participant.platform,
                    "avatar_url": participant.avatar_url,
                    "supporter_tier": participant.supporter_tier,
                    "entries": participant.entries,
                    "bonus_reason": participant.bonus_reason,
                    "joined_at": participant.joined_at,
                }
                for participant in self.participants_by_key.values()
            ]

    def blocked_history_items(self) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.blocked_attempts)

    def winner_message_items(self) -> list[dict[str, str]]:
        with self.lock:
            return list(self.winner_messages)

    def drawn_winner_names(self) -> list[str]:
        with self.lock:
            return [winner.name for winner in self.drawn_winners]

    def draw_winner(self) -> RaffleWinner | None:
        with self.lock:
            blocked = {winner.key for winner in self.drawn_winners}
            weighted_candidates = [
                RaffleWinner(
                    key=participant.key,
                    name=participant.name,
                    avatar_url=participant.avatar_url,
                    platform=participant.platform,
                    supporter_tier=participant.supporter_tier,
                    entries=participant.entries,
                    bonus_reason=participant.bonus_reason,
                )
                for participant in self.participants_by_key.values()
                if participant.key not in blocked
                for _ in range(max(1, int(participant.entries)))
            ]
        if not weighted_candidates:
            return None
        winner = secrets.choice(weighted_candidates)
        self.set_current_winner(winner)
        return winner

    def set_current_winner(self, winner: RaffleWinner) -> None:
        with self.lock:
            self.current_winner = winner
            self.drawn_winners.append(winner)
            self.winner_messages = []

    def has_remaining_winners(self) -> bool:
        with self.lock:
            return len(self.drawn_winners) < len(self.participants_by_key)

    def handle_live_chat_event(self, event: LiveChatMessage) -> None:
        self._handle_message(
            {
                "username": event.username,
                "comment": event.comment,
                "userId": event.user_id,
                "platform": event.platform,
                "avatar": event.avatar_url,
                "supporterTier": event.supporter_tier,
                "raw": event.__dict__,
                "ts": event.message_id or event.received_at,
            }
        )

    def _run_external_events(self) -> None:
        try:
            self.log("Sorteio conectado aos eventos do app. Aguardando comando no chat.")
            end_at = time.monotonic() + self.duration_seconds
            while not self.stop_event.is_set():
                if not self.finished_event.is_set() and time.monotonic() >= end_at:
                    self.finished_event.set()
                    self.log("Tempo do sorteio encerrado. Clique em Sortear vencedor.")
                    return
                time.sleep(0.2)
        finally:
            self.finished_event.set()

    def _run(self) -> None:
        driver = None
        try:
            driver = self._create_driver()
            driver.get(self.chat_url)
            self.log("Leitor do chat conectado. Aguardando comando do sorteio.")

            end_at = time.monotonic() + self.duration_seconds
            hook_installed = False
            while not self.stop_event.is_set():
                if not hook_installed:
                    hook_installed = self._install_chat_hook(driver)

                for message in self._read_chat_messages(driver):
                    self._handle_message(message)

                if not self.finished_event.is_set() and time.monotonic() >= end_at:
                    self.finished_event.set()
                    self.log("Tempo do sorteio encerrado. Clique em Sortear vencedor.")
                time.sleep(0.5)
        except Exception as exc:
            self.log(f"Erro no leitor do chat: {exc}")
        finally:
            self.finished_event.set()
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _create_driver(self):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions

        errors = []
        for browser_name, driver_factory, options_factory in (
            ("Edge", webdriver.Edge, EdgeOptions),
            ("Chrome", webdriver.Chrome, ChromeOptions),
        ):
            try:
                options = options_factory()
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--log-level=3")
                options.add_argument("--mute-audio")
                options.add_argument("--window-size=900,700")
                driver = driver_factory(options=options)
                self.log(f"Navegador usado no sorteio: {browser_name} em segundo plano.")
                return driver
            except Exception as exc:
                errors.append(f"{browser_name}: {exc}")

        raise RuntimeError("Nao consegui abrir Edge nem Chrome para ler o chat. " + " | ".join(errors))

    def _install_chat_hook(self, driver) -> bool:
        try:
            return bool(
                driver.execute_script(
                    """
                    window.__freeFireRaffleMessages = window.__freeFireRaffleMessages || [];
                    window.__freeFirePushRaffleMessage = window.__freeFirePushRaffleMessage || function(source) {
                        source = source || {};
                        const div = document.createElement("div");
                        const rawComment = source.comment || source.chatmessage || source.message || source.text || "";
                        div.innerHTML = String(rawComment);
                        const comment = (div.innerText || div.textContent || String(rawComment)).trim();
                        const username = String(source.nickname || source.uniqueId || source.chatname || source.name || source.username || "").trim();
                        if (!username || !comment) return;
                        window.__freeFireRaffleMessages.push({
                            username: username,
                            comment: comment,
                            userId: source.userId || source.userid || source.channelid || source.id || "",
                            platform: source.type || source.source || source.platform || "",
                            supporterTier: source.supporterTier || source.supporter_tier || source.memberLevel ||
                                source.membership || source.badge || source.badges || source.userBadges || "",
                            gift: source.gift || source.giftName || source.giftId || source.diamondCount || source.coins || "",
                            sub: source.sub || source.subscription || source.subscribe || source.isSubscriber || "",
                            moderator: source.moderator || source.isModerator || source.mod || "",
                            avatar: source.profilePictureUrl || source.profilePicture || source.profileImageUrl ||
                                source.avatar || source.avatarUrl || source.image || source.imageUrl ||
                                source.chatimg || source.chatImg || source.photo || "",
                            ts: source.timestamp || source.ts || source.mid || source.id || Date.now()
                        });
                        if (window.__freeFireRaffleMessages.length > 500) {
                            window.__freeFireRaffleMessages.splice(0, 250);
                        }
                    };
                    if (!window.__freeFireRaffleHooked && window.io && typeof window.io.on === "function") {
                        window.io.on("chat", function(message) {
                            window.__freeFirePushRaffleMessage(message);
                        });
                        window.__freeFireRaffleHooked = true;
                    }
                    if (!window.__freeFireSocialStreamHooked && typeof window.processData === "function") {
                        const originalProcessData = window.processData;
                        window.processData = function(data) {
                            try {
                                window.__freeFirePushRaffleMessage((data && data.contents) || data || {});
                            } catch (error) {}
                            return originalProcessData.apply(this, arguments);
                        };
                        window.__freeFireSocialStreamHooked = true;
                    }
                    return !!window.__freeFireRaffleHooked || !!window.__freeFireSocialStreamHooked;
                    """
                )
            )
        except Exception:
            return False

    def _read_chat_messages(self, driver) -> list[dict[str, str]]:
        try:
            messages = driver.execute_script(
                """
                const hooked = window.__freeFireRaffleMessages || [];
                window.__freeFireRaffleMessages = [];
                function htmlToText(value) {
                    const div = document.createElement("div");
                    div.innerHTML = String(value || "");
                    return (div.innerText || div.textContent || String(value || "")).trim();
                }
                function firstImage(root) {
                    const img = root?.querySelector?.("img");
                    return img?.currentSrc || img?.src || "";
                }
                const domMessages = Array.from(document.querySelectorAll(".chatMessage")).map((el) => ({
                    username: (el.querySelector(".username")?.textContent || "").trim(),
                    comment: (el.querySelector(".comment")?.textContent || "").trim(),
                    userId: "",
                    platform: "",
                    avatar: firstImage(el),
                    ts: el.getAttribute("data-ts") || ""
                }));
                const socialMessages = Array.from(document.querySelectorAll("[data-mid], .highlight-chat, .hl-message")).map((el) => {
                    const root = el.matches(".hl-message") ? (el.closest("[data-mid], .highlight-chat") || el.parentElement) : el;
                    const raw = root?.rawContents || {};
                    const username = String(
                        raw.chatname || raw.name || raw.username ||
                        root?.querySelector(".hl-name, .name, .username, [data-name]")?.textContent ||
                        ""
                    ).trim();
                    const comment = String(
                        raw.chatmessage ? htmlToText(raw.chatmessage) :
                        root?.querySelector(".hl-message, .message, .comment")?.textContent ||
                        ""
                    ).trim();
                    return {
                        username: username,
                        comment: comment,
                        userId: raw.userid || raw.userId || raw.channelid || raw.id || "",
                        platform: raw.type || raw.source || raw.platform || "",
                        supporterTier: raw.supporterTier || raw.supporter_tier || raw.memberLevel ||
                            raw.membership || raw.badge || raw.badges || raw.userBadges || "",
                        gift: raw.gift || raw.giftName || raw.giftId || raw.diamondCount || raw.coins || "",
                        sub: raw.sub || raw.subscription || raw.subscribe || raw.isSubscriber || "",
                        moderator: raw.moderator || raw.isModerator || raw.mod || "",
                        avatar: raw.profilePictureUrl || raw.profilePicture || raw.profileImageUrl ||
                            raw.avatar || raw.avatarUrl || raw.image || raw.imageUrl ||
                            raw.chatimg || raw.chatImg || firstImage(root) || "",
                        ts: raw.timestamp || raw.ts || raw.mid || raw.id || root?.getAttribute("data-mid") || ""
                    };
                }).filter((message) => message.username && message.comment);
                return hooked.concat(domMessages).concat(socialMessages);
                """
            )
        except Exception:
            return []

        if not isinstance(messages, list):
            return []
        return [message for message in messages if isinstance(message, dict)]

    def _handle_message(self, message: dict[str, Any]) -> None:
        username = str(message.get("username") or "").strip()
        comment = str(message.get("comment") or "").strip()
        user_id = str(message.get("userId") or "").strip()
        avatar_url = str(message.get("avatar") or "").strip()
        platform = str(message.get("platform") or "").strip()
        supporter_tier = self._normalize_supporter_tier(str(message.get("supporterTier") or message.get("supporter_tier") or ""))
        if supporter_tier == "normal":
            supporter_tier = detect_supporter_tier(message)
        supporter_tier, entries, bonus_reason = self._entry_profile(message, supporter_tier)
        ts = str(message.get("ts") or "").strip()
        if not username or not comment:
            return

        message_id = f"{user_id}|{username}|{comment}|{ts}"
        with self.lock:
            if message_id in self.seen_messages:
                return
            self.seen_messages.add(message_id)
            self.seen_message_order.append(message_id)
            if len(self.seen_message_order) > RAFFLE_SEEN_MESSAGES_LIMIT:
                stale_messages = self.seen_message_order[: len(self.seen_message_order) - RAFFLE_SEEN_MESSAGES_LIMIT]
                del self.seen_message_order[: len(self.seen_message_order) - RAFFLE_SEEN_MESSAGES_LIMIT]
                for stale_message_id in stale_messages:
                    self.seen_messages.discard(stale_message_id)

        participant_key = self._participant_key(username, user_id)
        with self.lock:
            current_winner = self.current_winner
            winner_match = bool(
                current_winner
                and (
                    participant_key == current_winner.key
                    or normalize_player_key(username) == normalize_player_key(current_winner.name)
                )
            )
            if winner_match:
                self.winner_messages.append(
                    {
                        "time": datetime.now().strftime("%H:%M:%S"),
                        "username": username,
                        "comment": comment,
                    }
                )
                self.winner_messages = self.winner_messages[-200:]

            if self.finished_event.is_set():
                return

            if comment.lower() != self.command:
                return

            now = time.monotonic()
            name_key = normalize_player_key(username)
            user_key = self._participant_key(username, user_id)
            if self._is_moderator(message) and not self.include_moderators:
                self._record_blocked_locked(username, user_id, "moderador ignorado")
                return
            last_command_at = self.user_command_times.get(user_key, 0.0)
            if self.user_cooldown_seconds and now - last_command_at < self.user_cooldown_seconds:
                self._record_blocked_locked(username, user_id, "cooldown anti-spam")
                return
            self.user_command_times[user_key] = now
            existing_name_key = self.participant_names_seen.get(name_key)
            if existing_name_key and existing_name_key != participant_key:
                self._record_blocked_locked(username, user_id, "nome duplicado")
                return

            if participant_key in self.participants_by_key:
                participant = self.participants_by_key[participant_key]
                if avatar_url and not participant.avatar_url:
                    participant.avatar_url = avatar_url
                if platform and not participant.platform:
                    participant.platform = platform
                if self._tier_rank(supporter_tier) > self._tier_rank(participant.supporter_tier):
                    participant.supporter_tier = supporter_tier
                    participant.entries = entries
                    participant.bonus_reason = bonus_reason
                return
            self.participants_by_key[participant_key] = RaffleParticipant(
                key=participant_key,
                name=username,
                avatar_url=avatar_url,
                platform=platform,
                supporter_tier=supporter_tier,
                entries=entries,
                bonus_reason=bonus_reason,
                joined_at=datetime.now().isoformat(timespec="seconds"),
            )
            self.participant_names_seen[name_key] = participant_key
            count = len(self.participants_by_key)
        tier_label = self._supporter_tier_label(supporter_tier)
        self.log(f"Entrou no sorteio: {username} - {entries} entrada(s) ({tier_label}) | {count} participante(s)")

    def _record_blocked_locked(self, username: str, user_id: str, reason: str) -> None:
        self.blocked_attempts.append(
            {
                "time": datetime.now().isoformat(timespec="seconds"),
                "username": username,
                "user_id": user_id,
                "reason": reason,
            }
        )
        self.blocked_attempts = self.blocked_attempts[-500:]

    def _participant_key(self, username: str, user_id: str = "") -> str:
        return user_id or re.sub(r"\s+", " ", username.casefold()).strip()

    def _normalize_supporter_tier(self, value: str) -> str:
        folded = _fold_raffle_text(value)
        if "super" in folded and ("fan" in folded or "fa" in folded):
            return "super_fan"
        if "subscriber" in folded or "subscribed" in folded:
            return "sub"
        if "sub" in folded or "assinante" in folded:
            return "sub"
        if "fan" in folded or re.search(r"\bfa\b", folded):
            return "fan"
        return "normal"

    def _supporter_tier_label(self, tier: str) -> str:
        return {"fan": "Fã", "super_fan": "Super fã", "gift": "Gift", "sub": "Sub"}.get(tier, "Seguidor")

    def _tier_rank(self, tier: str) -> int:
        return {"normal": 0, "fan": 1, "super_fan": 2, "gift": 3, "sub": 4}.get(tier, 0)

    def _entry_profile(self, message: dict[str, Any], supporter_tier: str) -> tuple[str, int, str]:
        folded = _fold_raffle_text(message)
        tier = supporter_tier
        if re.search(r"\bgift\b|\bpresente\b|\bdiamond\b|\bcoin\b|\brose\b", folded):
            tier = "gift"
        if re.search(r"\bsub\b|\bsubscriber\b|\bsubscription\b|\bassinante\b|\binscrito\b", folded):
            tier = "sub"
        return tier, self.entries_by_tier.get(tier, self.entries_by_tier["normal"]), self._supporter_tier_label(tier)

    def _is_moderator(self, message: dict[str, Any]) -> bool:
        folded = _fold_raffle_text(message)
        return bool(re.search(r"\bmoderator\b|\bmoderador\b|\bis_moderator true\b|\bismod true\b|\bmod true\b", folded))


def run_gui(config_path: Path) -> int:
    import tkinter as tk
    from tkinter import colorchooser, filedialog, messagebox, simpledialog

    import customtkinter as ctk

    ui_thread_id = threading.get_ident()
    config = load_config(config_path)
    theme_config = resolve_ui_theme(config)
    log_queue: queue.Queue[str] = queue.Queue(maxsize=LOG_QUEUE_HARD_LIMIT)
    sync_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=SYNC_QUEUE_LIMIT)
    ff_queue_sync_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=FF_QUEUE_SYNC_QUEUE_LIMIT)
    chat_event_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=CHAT_EVENT_QUEUE_LIMIT)
    livepix_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=LIVEPIX_QUEUE_LIMIT)
    log_render_buffer: list[str] = []
    log_rendered_count = 0
    log_needs_full_render = True
    log_full_render_cursor = 0
    chat_webhook_server: LocalChatWebhookServer | None = None
    livepix_webhook_server: LocalLivepixWebhookServer | None = None
    chat_websocket_worker: ChatWebSocketWorker | None = None
    bot_bridge_server: TikfinityDirectBridgeServer | None = None
    raffle_worker: TikfinityRaffleWorker | None = None
    raffle_end_at = 0.0
    raffle_animating = False
    raffle_started_at: datetime | None = None
    raffle_participant_render_pending = False
    raffle_participant_pending_items: list[Any] = []
    raffle_participant_render_after_id: str | None = None
    raffle_participant_render_generation = 0
    participant_widgets: list[Any] = []
    chat_widgets: list[Any] = []
    chat_monitor_widgets: list[Any] = []
    chat_render_after_ids: dict[int, str] = {}
    chat_render_generations: dict[int, int] = {}
    chat_monitor_window: Any | None = None
    chat_monitor_messages_frame: Any | None = None
    chat_monitor_always_on_top_var: tk.BooleanVar | None = None
    chat_actions: Any | None = None
    chat_messages_frame: Any | None = None
    chat_overlay_widgets: list[Any] = []
    chat_overlay_window: Any | None = None
    chat_overlay_messages_frame: Any | None = None
    chat_overlay_controls_frame: Any | None = None
    ff_overlay_window: Any | None = None
    ff_overlay_content_frame: Any | None = None
    ff_overlay_controls_frame: Any | None = None
    ff_overlay_widgets: list[Any] = []
    chat_messages: list[LiveChatMessage] = []
    chat_users: dict[str, LiveChatMessage] = {}
    chat_seen_messages: set[str] = set()
    avatar_request_queue: queue.Queue[tuple[str, int]] = queue.Queue(maxsize=AVATAR_PENDING_LIMIT)
    avatar_result_queue: queue.Queue[tuple[str, int, Image.Image | None]] = queue.Queue(maxsize=AVATAR_RESULT_QUEUE_LIMIT)
    avatar_image_cache: dict[tuple[str, int], Any] = {}
    avatar_pending: set[tuple[str, int]] = set()
    avatar_workers_started = False
    avatar_result_after_id: str | None = None
    winner_avatar_current: tuple[str, str] = ("", "-")
    manual_rows: list[dict[str, Any]] = []
    manual_suggestion_after_ids: dict[int, str] = {}
    manual_scope_buffers: dict[str, list[PlayerKill]] = {"daily": [], "general": []}
    manual_scope_dirty: set[str] = set()
    manual_reference_cache: dict[str, tuple[str, list[PlayerKill]]] = {}
    manual_reference_cache_generation = 0
    manual_table_render_pending = False
    manual_table_render_scope = ""
    manual_table_render_after_id: str | None = None
    manual_table_render_generation = 0
    manual_table_render_signature: tuple[str, str, int] | None = None
    manual_active_scope = normalize_kills_scope_value(config.get("kills_manual_scope", "daily"))
    if manual_active_scope not in {"daily", "general"}:
        manual_active_scope = "daily"
    kills_daily_rank_rows: list[Any] = []
    kills_global_rank_rows: list[Any] = []
    kills_ignored_rows: list[Any] = []
    kills_daily_ranking: list[PlayerKill] = []
    kills_global_ranking: list[PlayerKill] = []
    kills_ignored_players: list[IgnoredKillPlayer] = []
    kills_rank_cache_pending = False
    kills_rank_cache_signature = ""
    kills_rank_render_pending = False
    kills_ignored_render_pending = False
    ff_queue_actions: Any | None = None
    ff_queue_card: Any | None = None
    ff_queue_summary_frame: Any | None = None
    ff_queue_table_frame: Any | None = None
    ff_queue_summary_widgets: list[Any] = []
    ff_overlay_actions: Any | None = None
    ff_overlay_site_actions: Any | None = None
    ff_overlay_preview_frame: Any | None = None
    tikfinity_ff_mappings_frame: Any | None = None
    tikfinity_ff_users_frame: Any | None = None
    tikfinity_ff_history_frame: Any | None = None
    manual_sync_after_id: str | None = None
    manual_poll_after_id: str | None = None
    manual_visual_after_id: str | None = None
    manual_visual_sort_pending = False
    manual_config_after_id: str | None = None
    manual_config_signature = ""
    kills_visual_after_id: str | None = None
    manual_fetching = False
    manual_sending = False
    manual_applying_remote = False
    manual_bulk_updating = False
    manual_last_local_edit_at = 0.0
    manual_last_signature = ""
    manual_last_remote_signature = ""
    manual_last_rank_signature = ""
    manual_poll_quiet_cycles = 0
    manual_remote_count_override: int | None = None
    manual_remote_total_override: int | None = None
    manual_last_fetch_error = ""
    manual_dns_retry_after_id: str | None = None
    ff_queue_rows: list[dict[str, Any]] = []
    ff_queue_sync_after_id: str | None = None
    ff_queue_poll_after_id: str | None = None
    ff_queue_fetching = False
    ff_queue_sending = False
    ff_queue_applying_remote = False
    ff_queue_remote_count_override: int | None = None
    ff_queue_remote_rooms_override: int | None = None
    ff_queue_last_local_edit_at = 0.0
    ff_queue_last_signature = ""
    ff_queue_poll_quiet_cycles = 0
    ff_queue_last_fetch_error = ""
    ff_queue_cached_entries: list[FFQueueEntry] = []
    ff_queue_render_pending = False
    ff_queue_render_minimum_rows = 0
    tikfinity_ff_widgets: list[Any] = []
    tikfinity_ff_user_widgets: list[Any] = []
    tikfinity_ff_history_widgets: list[Any] = []
    tikfinity_ff_profiles: list[dict[str, Any]] = []
    ff_overlay_sending = False
    ff_overlay_fetching = False
    ff_overlay_last_signature = ""
    ff_overlay_last_remote_signature = ""
    ff_overlay_poll_quiet_cycles = 0
    ff_overlay_site_profiles: list[dict[str, Any]] = []
    ff_overlay_site_last_config: dict[str, Any] = {}
    ff_overlay_sync_after_id: str | None = None
    ff_overlay_poll_after_id: str | None = None
    ff_overlay_applying_remote = False
    custom_command_rows: list[dict[str, Any]] = []
    custom_command_cache: list[ChatCommand] = []
    custom_command_lookup_cache: dict[str, ChatCommand] = {}
    custom_command_cache_dirty = True
    custom_command_rows_loaded = False
    chat_timer_rows: list[dict[str, Any]] = []
    chat_timer_cache: list[ChatTimer] = []
    chat_timer_rows_loaded = False
    custom_command_bulk_loading = False
    chat_timer_bulk_loading = False
    chat_timer_runtime: dict[str, dict[str, Any]] = {}
    bot_reply_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=BOT_REPLY_QUEUE_LIMIT)
    bot_send_result_queue: queue.Queue[tuple[bool, str, dict[str, Any]]] = queue.Queue(maxsize=BOT_RESULT_QUEUE_LIMIT)
    chat_event_quiet_cycles = 0
    bot_command_last_sent: dict[str, float] = {}
    bot_command_last_missed: dict[str, float] = {}
    bot_pending_confirmations: dict[str, dict[str, Any]] = {}
    queue_drop_counts: dict[str, int] = {}
    queue_drop_last_log_at: dict[str, float] = {}
    bot_sending = False
    bot_next_allowed_at = 0.0
    sync_workers_active = 0
    ff_queue_workers_active = 0
    livepix_workers_active = 0
    sync_executor = ThreadPoolExecutor(max_workers=SYNC_WORKER_MAX_THREADS, thread_name_prefix="AizenSync")
    ff_queue_executor = ThreadPoolExecutor(max_workers=FF_QUEUE_WORKER_MAX_THREADS, thread_name_prefix="AizenFFQueue")
    livepix_executor = ThreadPoolExecutor(max_workers=LIVEPIX_WORKER_MAX_THREADS, thread_name_prefix="AizenLivepix")
    bot_executor = ThreadPoolExecutor(max_workers=BOT_WORKER_MAX_THREADS, thread_name_prefix="AizenBot")
    sync_pump_after_id: str | None = None
    ff_queue_pump_after_id: str | None = None
    chat_event_pump_after_id: str | None = None
    bot_pump_after_id: str | None = None
    chat_timer_after_id: str | None = None
    livepix_pump_after_id: str | None = None
    deferred_render_after_id: str | None = None
    app_closing = False
    hidden_main_tabs = {"Fila FF", "Overlay FF", "Chat Ao Vivo"}
    kills_ff_site_sync_hidden = "Kills FF" in hidden_main_tabs
    ff_queue_site_sync_hidden = "Fila FF" in hidden_main_tabs
    chat_tab_hidden = "Chat Ao Vivo" in hidden_main_tabs
    chat_listener_hidden = False
    ff_overlay_site_sync_hidden = "Overlay FF" in hidden_main_tabs or (kills_ff_site_sync_hidden and ff_queue_site_sync_hidden)
    config_auto_save_after_id: str | None = None
    config_auto_save_running = False
    config_auto_save_write_generation = 0
    config_auto_save_worker_started = False
    config_auto_save_lock = threading.Lock()
    config_auto_save_event = threading.Event()
    config_auto_save_pending: tuple[int, Path, str | dict[str, Any], bool, str] | None = None
    livepix_events: list[LivepixEvent] = []
    livepix_events_loaded = False
    livepix_events_loading = False
    livepix_history_load_generation = 0
    livepix_dashboard_state: dict[str, Any] = {}
    livepix_sync_running = False
    livepix_full_sync_pending = False
    livepix_overlay_window: Any | None = None
    livepix_overlay_frame: Any | None = None
    livepix_widgets: list[Any] = []
    livepix_history_render_pending = False
    livepix_render_after_id: str | None = None
    livepix_render_generation = 0
    livepix_dashboard_after_id: str | None = None
    appearance_preview_pending = True

    def drop_old_log_queue_items(target_size: int) -> int:
        dropped = 0
        try:
            while log_queue.qsize() > target_size:
                log_queue.get_nowait()
                dropped += 1
        except (queue.Empty, NotImplementedError):
            pass
        return dropped

    def enqueue_log_line(line: str) -> None:
        try:
            log_queue.put_nowait(line)
            return
        except queue.Full:
            pass
        drop_old_log_queue_items(LOG_QUEUE_SOFT_LIMIT // 2)
        try:
            log_queue.put_nowait(line)
        except queue.Full:
            try:
                log_queue.get_nowait()
                log_queue.put_nowait(line)
            except queue.Empty:
                pass
            except queue.Full:
                pass

    def log(message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        dropped = 0
        try:
            if log_queue.qsize() > LOG_QUEUE_SOFT_LIMIT:
                dropped = drop_old_log_queue_items(LOG_QUEUE_SOFT_LIMIT // 2)
        except NotImplementedError:
            pass
        if dropped:
            enqueue_log_line(f"[{stamp}] {dropped} log(s) antigos omitidos para manter o app leve.")
        enqueue_log_line(f"[{stamp}] {message}")

    def note_queue_drop(key: str, label: str, count: int = 1) -> None:
        queue_drop_counts[key] = queue_drop_counts.get(key, 0) + max(1, count)
        now = time.monotonic()
        if now - queue_drop_last_log_at.get(key, 0.0) >= 8.0:
            dropped = queue_drop_counts.get(key, 0)
            log(f"{label}: {dropped} item(ns) antigo(s) omitido(s) para manter o app leve.")
            queue_drop_counts[key] = 0
            queue_drop_last_log_at[key] = now

    def is_worker_done_queue_item(item: Any) -> bool:
        return isinstance(item, tuple) and len(item) >= 1 and item[0] == "__worker_done"

    def enqueue_limited_queue(
        target_queue: queue.Queue[Any],
        item: Any,
        key: str,
        label: str,
    ) -> bool:
        try:
            target_queue.put_nowait(item)
            return True
        except queue.Full:
            pass
        try:
            dropped_item = target_queue.get_nowait()
            if is_worker_done_queue_item(dropped_item) and not is_worker_done_queue_item(item):
                try:
                    target_queue.put_nowait(dropped_item)
                except queue.Full:
                    pass
                note_queue_drop(key, label)
                return False
            note_queue_drop(key, label)
        except queue.Empty:
            pass
        try:
            target_queue.put_nowait(item)
            return True
        except queue.Full:
            note_queue_drop(key, label)
            return False

    def enqueue_worker_done_event(target_queue: queue.Queue[Any], key: str, label: str) -> bool:
        item = ("__worker_done", None)
        try:
            target_queue.put_nowait(item)
            return True
        except queue.Full:
            pass
        if threading.get_ident() != ui_thread_id:
            try:
                target_queue.put(item, timeout=0.5)
                return True
            except queue.Full:
                pass

        buffered_items: list[Any] = []
        dropped_regular_item = False
        try:
            while True:
                candidate = target_queue.get_nowait()
                if not dropped_regular_item and not is_worker_done_queue_item(candidate):
                    dropped_regular_item = True
                    note_queue_drop(key, label)
                    break
                buffered_items.append(candidate)
        except queue.Empty:
            pass
        for candidate in buffered_items:
            try:
                target_queue.put_nowait(candidate)
            except queue.Full:
                note_queue_drop(key, label)
                break
        if dropped_regular_item:
            try:
                target_queue.put_nowait(item)
                return True
            except queue.Full:
                pass
        note_queue_drop(key, label)
        return False

    def in_ui_thread() -> bool:
        return threading.get_ident() == ui_thread_id

    def enqueue_sync_event(kind: str, payload: Any) -> bool:
        queued = enqueue_limited_queue(sync_queue, (kind, payload), "sync", "Fila Jarvis cheia")
        if queued and sync_pump_after_id is None and in_ui_thread():
            try:
                schedule_sync_queue_pump(0)
            except NameError:
                pass
        return queued

    def enqueue_ff_queue_event(kind: str, payload: Any) -> bool:
        queued = enqueue_limited_queue(ff_queue_sync_queue, (kind, payload), "ff_queue", "Fila FF cheia")
        if queued and ff_queue_pump_after_id is None and in_ui_thread():
            try:
                schedule_ff_queue_sync_pump(0)
            except NameError:
                pass
        return queued

    def enqueue_livepix_event(kind: str, payload: Any) -> bool:
        queued = enqueue_limited_queue(livepix_queue, (kind, payload), "livepix", "Fila Livepix cheia")
        if queued and livepix_pump_after_id is None and in_ui_thread():
            try:
                schedule_livepix_queue_pump(0)
            except NameError:
                pass
        return queued

    def enqueue_chat_event(kind: str, payload: Any) -> bool:
        queued = enqueue_limited_queue(chat_event_queue, (kind, payload), "chat_event", "Fila de chat cheia")
        if queued and chat_event_pump_after_id is None and in_ui_thread():
            try:
                schedule_chat_event_pump(0)
            except NameError:
                pass
        return queued

    def start_sync_worker(target: callable, name: str = "AizenSyncWorker") -> None:
        nonlocal sync_workers_active
        if app_closing:
            return
        sync_workers_active += 1
        schedule_sync_queue_pump(0)

        def wrapped() -> None:
            nonlocal sync_workers_active
            try:
                target()
            finally:
                if not enqueue_worker_done_event(sync_queue, "sync", "Fila Jarvis cheia"):
                    sync_workers_active = max(0, sync_workers_active - 1)

        try:
            sync_executor.submit(wrapped)
        except RuntimeError:
            sync_workers_active = max(0, sync_workers_active - 1)
            if not app_closing:
                log(f"Nao consegui iniciar worker {name}; app esta encerrando.")

    def start_ff_queue_worker(target: callable, name: str = "AizenFFQueueWorker") -> None:
        nonlocal ff_queue_workers_active
        if app_closing:
            return
        ff_queue_workers_active += 1
        schedule_ff_queue_sync_pump(0)

        def wrapped() -> None:
            nonlocal ff_queue_workers_active
            try:
                target()
            finally:
                if not enqueue_worker_done_event(ff_queue_sync_queue, "ff_queue", "Fila FF cheia"):
                    ff_queue_workers_active = max(0, ff_queue_workers_active - 1)

        try:
            ff_queue_executor.submit(wrapped)
        except RuntimeError:
            ff_queue_workers_active = max(0, ff_queue_workers_active - 1)
            if not app_closing:
                log(f"Nao consegui iniciar worker {name}; app esta encerrando.")

    def start_livepix_worker(target: callable, name: str = "AizenLivepixWorker") -> None:
        nonlocal livepix_workers_active
        if app_closing:
            return
        livepix_workers_active += 1
        schedule_livepix_queue_pump(0)

        def wrapped() -> None:
            nonlocal livepix_workers_active
            try:
                target()
            finally:
                if not enqueue_worker_done_event(livepix_queue, "livepix", "Fila Livepix cheia"):
                    livepix_workers_active = max(0, livepix_workers_active - 1)

        try:
            livepix_executor.submit(wrapped)
        except RuntimeError:
            livepix_workers_active = max(0, livepix_workers_active - 1)
            if not app_closing:
                log(f"Nao consegui iniciar worker {name}; app esta encerrando.")

    def enqueue_avatar_result(url: str, size: int, image: Image.Image | None) -> bool:
        return enqueue_limited_queue(
            avatar_result_queue,
            (url, size, image),
            "avatar_result",
            "Fila de avatares cheia",
        )

    def should_load_livepix_history(force: bool = False) -> bool:
        if force:
            return True
        try:
            if livepix_enabled_var.get():
                return True
        except NameError:
            pass
        if livepix_webhook_server is not None or livepix_overlay_frame is not None:
            return True
        try:
            return is_livepix_tab_active()
        except NameError:
            return False

    def start_livepix_history_load(force: bool = False) -> None:
        nonlocal livepix_events_loading, livepix_history_load_generation
        if app_closing or livepix_events_loaded or livepix_events_loading:
            return
        if not should_load_livepix_history(force):
            return
        livepix_events_loading = True
        livepix_history_load_generation += 1
        generation = livepix_history_load_generation
        history_path = livepix_events_path(config_path)

        def run() -> None:
            try:
                events = load_livepix_events(history_path)
                enqueue_livepix_event("history_loaded", {"generation": generation, "events": events})
            except Exception as exc:
                enqueue_livepix_event("history_load_error", str(exc))

        start_livepix_worker(run, name="AizenLivepixHistoryLoad")

    def set_text_var(var: tk.StringVar, value: Any) -> None:
        text = str(value)
        if var.get() != text:
            var.set(text)

    def adaptive_poll_seconds(base_seconds: int, quiet_cycles: int, max_seconds: int = 90) -> int:
        base = max(10, min(max_seconds, int(base_seconds)))
        multiplier = 2 ** min(max(0, quiet_cycles), 3)
        return max(10, min(max_seconds, base * multiplier))

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    root = ctk.CTk()
    root.title("Aizen Stream Control")
    root.geometry("1280x860")
    root.minsize(900, 600)
    if APP_ICON.exists():
        try:
            root.iconbitmap(str(APP_ICON))
        except tk.TclError:
            pass

    canvas_bg = theme_config["canvas_bg"]
    bg = theme_config["bg"]
    panel = theme_config["panel"]
    panel_alt = theme_config["panel_alt"]
    field = theme_config["field"]
    border = theme_config["border"]
    fg = theme_config["fg"]
    muted = theme_config["muted"]
    accent = theme_config["accent"]
    accent_hover = theme_config["accent_hover"]
    teal = theme_config["teal"]
    blue = theme_config["blue"]
    danger = theme_config["danger"]
    header_panel = panel_alt
    chip_bg = panel_alt
    chip_bg_alt = field
    table_header_bg = field

    root.configure(fg_color=canvas_bg)

    main = ctk.CTkFrame(root, fg_color=canvas_bg, corner_radius=0)
    main.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
    main.columnconfigure(0, weight=1)
    main.rowconfigure(1, weight=1)

    initial_sync_url = str(config.get("kills_realtime_url") or config.get("jarvis_endpoint_url", "")).strip()
    initial_ff_queue_url = str(config.get("ff_queue_realtime_url") or config.get("jarvis_endpoint_url", "")).strip()
    initial_jarvis_base_url = str(config.get("jarvis_base_url") or initial_sync_url or initial_ff_queue_url).strip()
    if initial_jarvis_base_url:
        if not initial_sync_url:
            initial_sync_url = derive_jarvis_endpoint(initial_jarvis_base_url, "kills")
        if not initial_ff_queue_url:
            initial_ff_queue_url = derive_jarvis_endpoint(initial_jarvis_base_url, "queue")
    if not initial_ff_queue_url and "freefire-kills" in initial_sync_url:
        initial_ff_queue_url = initial_sync_url.replace("freefire-kills", "freefire-queue")
    initial_ff_overlay_url = str(config.get("ff_overlay_realtime_url", "")).strip()
    if initial_jarvis_base_url and not initial_ff_overlay_url:
        initial_ff_overlay_url = derive_jarvis_endpoint(initial_jarvis_base_url, "overlay")
    if not initial_ff_overlay_url and "freefire-kills" in initial_sync_url:
        initial_ff_overlay_url = initial_sync_url.replace("freefire-kills", "freefire-overlay")
    if not initial_ff_overlay_url and "freefire-queue" in initial_ff_queue_url:
        initial_ff_overlay_url = initial_ff_queue_url.replace("freefire-queue", "freefire-overlay")
    initial_ff_overlay_config_url = str(config.get("ff_overlay_config_url", "")).strip()
    if not initial_ff_overlay_config_url and initial_ff_overlay_url:
        initial_ff_overlay_config_url = derive_ff_overlay_config_endpoint(initial_ff_overlay_url)
    if not initial_ff_overlay_config_url and initial_jarvis_base_url:
        initial_ff_overlay_config_url = derive_ff_overlay_config_endpoint(initial_jarvis_base_url)
    initial_tikfinity_ff_url = str(config.get("tikfinity_ff_gifts_url", "")).strip()
    if initial_jarvis_base_url and not initial_tikfinity_ff_url:
        initial_tikfinity_ff_url = derive_tikfinity_ff_gifts_endpoint(initial_jarvis_base_url)
    if initial_ff_queue_url and not initial_tikfinity_ff_url:
        initial_tikfinity_ff_url = derive_tikfinity_ff_gifts_endpoint(initial_ff_queue_url)
    sync_url_var = tk.StringVar(value=initial_sync_url)
    title_var = tk.StringVar(value=config.get("message_title", "Kills da partida"))
    initial_kills_style_source = initial_sync_url or initial_jarvis_base_url
    initial_kills_style_url = str(config.get("freefire_kills_style_url") or "").strip()
    if not initial_kills_style_url and initial_kills_style_source:
        initial_kills_style_url = derive_kills_style_endpoint(initial_kills_style_source)
    kills_style_url_var = tk.StringVar(value=initial_kills_style_url)
    kills_obs_url_var = tk.StringVar(value=derive_kills_obs_url(initial_kills_style_source) if initial_kills_style_source else "")
    kills_style_status_var = tk.StringVar(value="Não carregado")
    kills_style_title_var = tk.StringVar(value="TOP KILLS")
    kills_style_font_var = tk.StringVar(value="impact")
    kills_style_align_var = tk.StringVar(value="left")
    kills_style_title_align_var = tk.StringVar(value="left")
    kills_style_title_size_var = tk.StringVar(value="34")
    kills_style_row_size_var = tk.StringVar(value="26")
    kills_style_kills_size_var = tk.StringVar(value="28")
    kills_style_rank_size_var = tk.StringVar(value="24")
    kills_style_weight_var = tk.StringVar(value="900")
    kills_style_row_height_var = tk.StringVar(value="42")
    kills_style_row_gap_var = tk.StringVar(value="5")
    kills_style_row_max_width_var = tk.StringVar(value="0")
    kills_style_column_gap_var = tk.StringVar(value="10")
    kills_style_row_padding_var = tk.StringVar(value="10")
    kills_style_wrap_padding_var = tk.StringVar(value="8")
    kills_style_switch_seconds_var = tk.StringVar(value="10")
    kills_style_title_color_var = tk.StringVar(value="#FFD54A")
    kills_style_rank_color_var = tk.StringVar(value="#FFD54A")
    kills_style_name_color_var = tk.StringVar(value="#FFFFFF")
    kills_style_kills_color_var = tk.StringVar(value="#66FF99")
    kills_style_shadow_color_var = tk.StringVar(value="#000000")
    kills_style_shadow_blur_var = tk.StringVar(value="7")
    kills_style_row_bg_color_var = tk.StringVar(value="#000000")
    kills_style_row_bg_opacity_var = tk.StringVar(value="35")
    kills_style_accent_color_var = tk.StringVar(value="#FF4655")
    kills_style_accent_width_var = tk.StringVar(value="4")
    kills_style_row_radius_var = tk.StringVar(value="8")
    kills_style_show_title_var = tk.BooleanVar(value=True)
    kills_style_uppercase_var = tk.BooleanVar(value=True)
    kills_style_rank_prefix_var = tk.BooleanVar(value=True)
    kills_style_medals_var = tk.BooleanVar(value=True)
    kills_style_row_bg_var = tk.BooleanVar(value=False)
    kills_style_accent_var = tk.BooleanVar(value=False)
    sync_room_var = tk.StringVar(value=config.get("kills_sync_room", "principal"))
    ff_queue_url_var = tk.StringVar(value=initial_ff_queue_url)
    ff_overlay_url_var = tk.StringVar(value=initial_ff_overlay_url)
    ff_overlay_config_url_var = tk.StringVar(value=initial_ff_overlay_config_url)
    ff_overlay_site_profile_var = tk.StringVar(value=str(config.get("ff_overlay_profile", "streamer1") or "streamer1"))
    ff_overlay_site_label_var = tk.StringVar(value="")
    ff_overlay_site_obs_url_var = tk.StringVar(value="-")
    ff_overlay_site_status_var = tk.StringVar(value="Nao carregado")
    ff_overlay_site_enabled_general_var = tk.BooleanVar(value=True)
    ff_overlay_site_enabled_daily_var = tk.BooleanVar(value=True)
    ff_overlay_site_enabled_queue_var = tk.BooleanVar(value=True)
    ff_overlay_site_panel_bg_var = tk.BooleanVar(value=True)
    ff_overlay_site_rank_prefix_var = tk.BooleanVar(value=True)
    ff_overlay_site_medals_var = tk.BooleanVar(value=True)
    ff_overlay_site_layout_var = tk.StringVar(value="horizontal")
    ff_overlay_site_font_var = tk.StringVar(value="impact")
    ff_overlay_site_animation_var = tk.StringVar(value="slide")
    ff_overlay_site_refresh_var = tk.StringVar(value="2500")
    ff_overlay_site_switch_var = tk.StringVar(value="10")
    ff_overlay_site_limit_general_var = tk.StringVar(value="10")
    ff_overlay_site_limit_daily_var = tk.StringVar(value="10")
    ff_overlay_site_limit_queue_var = tk.StringVar(value="8")
    ff_overlay_site_panel_width_var = tk.StringVar(value="360")
    ff_overlay_site_gap_var = tk.StringVar(value="14")
    ff_overlay_site_padding_var = tk.StringVar(value="8")
    ff_overlay_site_title_size_var = tk.StringVar(value="30")
    ff_overlay_site_row_size_var = tk.StringVar(value="22")
    ff_overlay_site_value_size_var = tk.StringVar(value="24")
    ff_overlay_site_row_height_var = tk.StringVar(value="40")
    ff_overlay_site_panel_bg_color_var = tk.StringVar(value="#05070D")
    ff_overlay_site_panel_bg_opacity_var = tk.StringVar(value="48")
    ff_overlay_site_panel_radius_var = tk.StringVar(value="10")
    ff_overlay_site_row_bg_color_var = tk.StringVar(value="#000000")
    ff_overlay_site_row_bg_opacity_var = tk.StringVar(value="28")
    ff_overlay_site_accent_width_var = tk.StringVar(value="4")
    ff_overlay_site_panel_defaults = {
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
    }
    ff_overlay_site_panel_vars = {
        panel_key: {field_key: tk.StringVar(value=str(field_value)) for field_key, field_value in fields.items()}
        for panel_key, fields in ff_overlay_site_panel_defaults.items()
    }
    tikfinity_ff_url_var = tk.StringVar(value=initial_tikfinity_ff_url)
    tikfinity_ff_profile_var = tk.StringVar(value=str(config.get("tikfinity_ff_profile", "streamer1") or "streamer1"))
    tikfinity_ff_enabled_var = tk.BooleanVar(value=bool(config.get("tikfinity_ff_enabled", False)) and not ff_queue_site_sync_hidden)
    tikfinity_ff_coins_var = tk.StringVar(value=str(config.get("tikfinity_ff_coins_per_room", 50)))
    tikfinity_ff_token_var = tk.StringVar(value=str(config.get("tikfinity_ff_token", "")))
    tikfinity_ff_status_var = tk.StringVar(value="Não carregado")
    tikfinity_ff_webhook_var = tk.StringVar(value="-")
    tikfinity_ff_summary_var = tk.StringVar(value="0 vínculos | 0 usuários | 0 eventos")
    tikfinity_ff_map_handle_var = tk.StringVar(value="")
    tikfinity_ff_map_user_id_var = tk.StringVar(value="")
    tikfinity_ff_map_display_var = tk.StringVar(value="")
    tikfinity_ff_map_ff_id_var = tk.StringVar(value="")
    ff_queue_room_var = tk.StringVar(value=config.get("ff_queue_room", "principal"))
    jarvis_base_url_var = tk.StringVar(value=initial_jarvis_base_url)
    ff_queue_enabled_var = tk.BooleanVar(value=bool(config.get("ff_queue_auto_sync", True)) and not ff_queue_site_sync_hidden)
    ff_overlay_enabled_var = tk.BooleanVar(value=bool(config.get("ff_overlay_auto_sync", True)) and not ff_overlay_site_sync_hidden)
    ff_queue_poll_seconds_var = tk.StringVar(value=str(max(10, normalize_kill_value(config.get("ff_queue_poll_seconds", 15)))))
    ff_queue_status_var = tk.StringVar(value="Manual")
    ff_overlay_status_var = tk.StringVar(value="Local")
    ff_queue_count_var = tk.StringVar(value="0")
    ff_queue_playing_var = tk.StringVar(value="0")
    ff_queue_summary_count_var = tk.StringVar(value="0")
    ff_queue_summary_rooms_var = tk.StringVar(value="0")
    ff_queue_source_var = tk.StringVar(value=config.get("device_name", default_device_name()))
    ff_queue_manual_name_var = tk.StringVar(value="")
    ff_queue_manual_user_id_var = tk.StringVar(value="")
    ff_queue_manual_ff_id_var = tk.StringVar(value="")
    ff_queue_manual_rooms_var = tk.StringVar(value="1")
    device_name_var = tk.StringVar(value=config.get("device_name", default_device_name()))
    jarvis_token_var = tk.StringVar(value=str(config.get("jarvis_api_token", "")))
    poll_seconds_var = tk.StringVar(value=str(max(10, normalize_kill_value(config.get("kills_realtime_poll_seconds", 15)))))
    initial_manual_scope = manual_active_scope
    manual_scope_var = tk.StringVar(value="Geral" if initial_manual_scope == "general" else "Diario")
    auto_update_var = tk.BooleanVar(value=bool(config.get("auto_update_enabled", True)))
    general_update_state_var = tk.StringVar(value="Ativa" if auto_update_var.get() else "Desativada")
    updates_manifest_url_var = tk.StringVar(value=config.get("updates_manifest_url", ""))
    manual_status_var = tk.StringVar(value="Manual")
    manual_count_var = tk.StringVar(value="0")
    manual_total_var = tk.StringVar(value="0")
    manual_source_var = tk.StringVar(value=device_name_var.get())
    kills_rank_mode_var = tk.StringVar(value="Diario")
    kills_daily_rank_count_var = tk.StringVar(value="0")
    kills_daily_rank_total_var = tk.StringVar(value="0")
    kills_global_rank_count_var = tk.StringVar(value="0")
    kills_global_rank_total_var = tk.StringVar(value="0")
    kills_overlay_status_var = tk.StringVar(value="Aguardando leitura do Jarvis")
    kills_admin_name_var = tk.StringVar(value="")
    kills_admin_new_name_var = tk.StringVar(value="")
    kills_admin_ff_id_var = tk.StringVar(value="")
    kills_admin_kills_var = tk.StringVar(value="1")
    kills_admin_scope_var = tk.StringVar(value="Diario")
    kills_admin_key_var = tk.StringVar(value="")
    kills_ignored_count_var = tk.StringVar(value="0")
    tikfinity_url_var = tk.StringVar(value=config.get("tikfinity_chat_url", ""))
    chat_source_var = tk.StringVar(
        value="TikFinity WebSocket" if config.get("chat_event_source", "webhook") == "websocket" else "Webhook local"
    )
    chat_webhook_host_var = tk.StringVar(value=str(config.get("chat_webhook_host", "127.0.0.1")))
    chat_webhook_port_var = tk.StringVar(value=str(config.get("chat_webhook_port", 8765)))
    chat_webhook_token_var = tk.StringVar(value=str(config.get("chat_webhook_token", "")))
    chat_websocket_url_var = tk.StringVar(value=str(config.get("chat_websocket_url") or DEFAULT_TIKFINITY_WEBSOCKET_URL))
    chat_filter_var = tk.StringVar(value="")
    chat_status_var = tk.StringVar(value="Desligado")
    chat_message_count_var = tk.StringVar(value="0")
    chat_user_count_var = tk.StringVar(value="0")
    chat_platform_var = tk.StringVar(value="-")
    chat_endpoint_var = tk.StringVar(value="")
    chat_commands_enabled_var = tk.BooleanVar(value=bool(config.get("chat_commands_enabled", False)))
    bot_delivery_method_var = tk.StringVar(value=bot_delivery_method_label(config.get("bot_delivery_method")))
    bot_streamerbot_ws_url_var = tk.StringVar(
        value=str(config.get("bot_streamerbot_ws_url") or DEFAULT_STREAMERBOT_WEBSOCKET_URL)
    )
    bot_streamerbot_http_url_var = tk.StringVar(
        value=str(config.get("bot_streamerbot_http_url") or DEFAULT_STREAMERBOT_HTTP_URL)
    )
    bot_streamerbot_password_var = tk.StringVar(value=str(config.get("bot_streamerbot_password", "")))
    bot_streamerbot_action_name_var = tk.StringVar(
        value=str(config.get("bot_streamerbot_action_name", "Aizen TikFinity Chatbot"))
    )
    bot_streamerbot_action_id_var = tk.StringVar(value=str(config.get("bot_streamerbot_action_id", "")))
    bot_safe_delay_var = tk.StringVar(value=str(config.get("bot_safe_delay_seconds", 15)))
    bot_default_cooldown_var = tk.StringVar(value=str(config.get("bot_default_command_cooldown_seconds", 30)))
    chat_timers_enabled_var = tk.BooleanVar(value=bool(config.get("chat_timers_enabled", False)))
    bot_default_timer_interval_var = tk.StringVar(value=str(config.get("bot_default_timer_interval_seconds", 600)))
    bot_default_timer_min_messages_var = tk.StringVar(value=str(config.get("bot_default_timer_min_messages", 5)))
    timer_status_var = tk.StringVar(value="Desligado")
    timer_active_count_var = tk.StringVar(value="0")
    timer_next_send_var = tk.StringVar(value="-")
    bot_ignore_usernames_var = tk.StringVar(value=str(config.get("bot_ignore_usernames", "")))
    bot_status_var = tk.StringVar(value="Desligado")
    bot_queue_count_var = tk.StringVar(value="0")
    bot_last_sent_var = tk.StringVar(value="-")
    livepix_enabled_var = tk.BooleanVar(value=bool(config.get("livepix_enabled", False)))
    livepix_client_id_var = tk.StringVar(value=str(config.get("livepix_client_id", "")))
    livepix_client_secret_var = tk.StringVar(value=str(config.get("livepix_client_secret", "")))
    livepix_scopes_var = tk.StringVar(value=str(config.get("livepix_scopes", "")))
    livepix_webhook_host_var = tk.StringVar(value=str(config.get("livepix_webhook_host", "127.0.0.1")))
    livepix_webhook_port_var = tk.StringVar(value=str(config.get("livepix_webhook_port", 8787)))
    livepix_webhook_token_var = tk.StringVar(value=str(config.get("livepix_webhook_token", "")))
    livepix_redirect_url_var = tk.StringVar(value=str(config.get("livepix_redirect_url", "https://livepix.gg")))
    livepix_goal_amount_var = tk.StringVar(value=str(int(config.get("livepix_goal_amount", 50000)) / 100).replace(".", ","))
    livepix_goal_label_var = tk.StringVar(value=str(config.get("livepix_goal_label", "Meta da live")))
    livepix_currency_var = tk.StringVar(value=str(config.get("livepix_currency", "BRL")).upper())
    livepix_status_var = tk.StringVar(value="Desligado")
    livepix_account_var = tk.StringVar(value="-")
    livepix_total_var = tk.StringVar(value="R$ 0,00")
    livepix_goal_var = tk.StringVar(value="0%")
    livepix_count_var = tk.StringVar(value="0")
    livepix_balance_var = tk.StringVar(value="-")
    livepix_pending_var = tk.StringVar(value="-")
    livepix_top_var = tk.StringVar(value="-")
    livepix_wallet_var = tk.StringVar(value="-")
    livepix_extra_var = tk.StringVar(value="-")
    livepix_ranking_var = tk.StringVar(value="-")
    livepix_endpoint_var = tk.StringVar(value="")
    livepix_values_visible_var = tk.BooleanVar(value=False)
    livepix_account_display_var = tk.StringVar(value="-")
    livepix_total_display_var = tk.StringVar(value="••••")
    livepix_balance_display_var = tk.StringVar(value="••••")
    livepix_pending_display_var = tk.StringVar(value="••••")
    livepix_count_display_var = tk.StringVar(value="••••")
    livepix_checkout_amount_var = tk.StringVar(
        value=str(int(config.get("livepix_checkout_amount", 1000)) / 100).replace(".", ",")
    )
    livepix_checkout_user_var = tk.StringVar(value=str(config.get("livepix_checkout_user", "Apoiador")))
    livepix_checkout_message_var = tk.StringVar(value=str(config.get("livepix_checkout_message", "Apoio para a live!")))
    livepix_plan_id_var = tk.StringVar(value=str(config.get("livepix_plan_id", "")))
    livepix_plan_slug_var = tk.StringVar(value=str(config.get("livepix_plan_slug", "vip-live")))
    livepix_plan_name_var = tk.StringVar(value=str(config.get("livepix_plan_name", "VIP da live")))
    livepix_plan_description_var = tk.StringVar(value=str(config.get("livepix_plan_description", "Acesso aos benefícios de apoiador da live.")))
    livepix_subscription_recurrence_var = tk.StringVar(value=str(config.get("livepix_subscription_recurrence", "monthly")))
    livepix_subscriber_email_var = tk.StringVar(value=str(config.get("livepix_subscriber_email", "")))
    livepix_announce_in_chat_var = tk.BooleanVar(value=bool(config.get("livepix_announce_in_chat", True)))
    livepix_public_page_file_var = tk.StringVar(value=str(config.get("livepix_public_page_file", "livepix_public.html")))
    raffle_source_mode_var = tk.StringVar(
        value="URL do chat (legado)" if config.get("raffle_source_mode") == "browser" else "Eventos do app"
    )
    raffle_command_var = tk.StringVar(value=config.get("raffle_command", "!sorteio"))
    raffle_default_seconds = int(config.get("raffle_duration_seconds", 600))
    raffle_minutes_var = tk.StringVar(value=str(max(1, raffle_default_seconds // 60)))
    raffle_timer_var = tk.StringVar(value=f"{raffle_default_seconds // 60:02d}:{raffle_default_seconds % 60:02d}")
    raffle_count_var = tk.StringVar(value="0")
    raffle_entries_var = tk.StringVar(value="0")
    raffle_entries_normal_var = tk.StringVar(value=str(config.get("raffle_entries_normal", 1)))
    raffle_entries_fan_var = tk.StringVar(value=str(config.get("raffle_entries_fan", 2)))
    raffle_entries_super_fan_var = tk.StringVar(value=str(config.get("raffle_entries_super_fan", 3)))
    raffle_entries_gift_var = tk.StringVar(value=str(config.get("raffle_entries_gift", 5)))
    raffle_entries_sub_var = tk.StringVar(value=str(config.get("raffle_entries_sub", 10)))
    raffle_cooldown_var = tk.StringVar(value=str(config.get("raffle_user_cooldown_seconds", 8)))
    raffle_include_moderators_var = tk.BooleanVar(value=bool(config.get("raffle_include_moderators", True)))
    raffle_winner_var = tk.StringVar(value="-")
    raffle_state_var = tk.StringVar(value="Aguardando")
    ui_layout = config.get("ui_layout", {}) if isinstance(config.get("ui_layout"), dict) else {}
    participants_height_var = tk.IntVar(value=max(520, int(ui_layout.get("participants_height", 560))))
    events_height_var = tk.IntVar(value=int(ui_layout.get("events_height", 170)))
    winner_width_var = tk.IntVar(value=int(ui_layout.get("winner_width", 360)))
    raffle_font_size_var = tk.IntVar(value=int(ui_layout.get("raffle_font_size", 13)))
    chat_overlay_opacity_var = tk.IntVar(value=int(ui_layout.get("chat_overlay_opacity", 84)))
    chat_overlay_font_size_var = tk.IntVar(value=int(ui_layout.get("chat_overlay_font_size", 14)))
    chat_overlay_width_var = tk.IntVar(value=int(ui_layout.get("chat_overlay_width", 430)))
    chat_overlay_height_var = tk.IntVar(value=int(ui_layout.get("chat_overlay_height", 640)))
    chat_overlay_compact_var = tk.BooleanVar(value=bool(ui_layout.get("chat_overlay_compact", True)))
    chat_overlay_controls_var = tk.BooleanVar(value=bool(ui_layout.get("chat_overlay_controls", True)))
    chat_overlay_clickthrough_var = tk.BooleanVar(value=bool(ui_layout.get("chat_overlay_clickthrough", False)))
    ff_overlay_opacity_var = tk.IntVar(value=int(ui_layout.get("ff_overlay_opacity", 92)))
    ff_overlay_width_var = tk.IntVar(value=int(ui_layout.get("ff_overlay_width", 760)))
    ff_overlay_height_var = tk.IntVar(value=int(ui_layout.get("ff_overlay_height", 420)))
    ff_overlay_compact_var = tk.BooleanVar(value=bool(ui_layout.get("ff_overlay_compact", False)))
    ff_overlay_show_queue_var = tk.BooleanVar(value=bool(ui_layout.get("ff_overlay_show_queue", True)))
    ff_overlay_show_kills_var = tk.BooleanVar(value=bool(ui_layout.get("ff_overlay_show_kills", True)))
    queue_size_text = tk.StringVar(value="")
    event_size_text = tk.StringVar(value="")
    winner_size_text = tk.StringVar(value="")
    font_size_text = tk.StringVar(value="")
    chat_overlay_opacity_text = tk.StringVar(value="")
    chat_overlay_font_size_text = tk.StringVar(value="")
    ff_overlay_opacity_text = tk.StringVar(value="")
    ff_overlay_size_text = tk.StringVar(value="")
    status_var = manual_status_var
    appearance_preset_var = tk.StringVar(value=theme_config.get("preset", DEFAULT_THEME_NAME))
    logo_path_var = tk.StringVar(value=theme_config.get("logo_path", ""))
    theme_color_vars = {key: tk.StringVar(value=theme_config[key]) for key in THEME_COLOR_KEYS}

    def section_label(parent: Any, text: str, row: int, column: int = 0, **kwargs: Any) -> None:
        ctk.CTkLabel(parent, text=text, text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=row, column=column, sticky="w", pady=(10, 5), **kwargs
        )

    def card(parent: Any, title: str, subtitle: str | None = None) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(
            parent,
            fg_color=panel,
            corner_radius=8,
            border_width=1,
            border_color=border,
        )
        frame.columnconfigure(1, weight=1)
        title_bar = ctk.CTkFrame(frame, fg_color="transparent", corner_radius=0)
        title_bar.grid(row=0, column=0, columnspan=4, sticky="ew", padx=18, pady=(16, 0))
        ctk.CTkFrame(title_bar, fg_color=accent, width=4, height=22, corner_radius=99).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        ctk.CTkLabel(title_bar, text=title, text_color=fg, font=("Segoe UI Semibold", 15)).pack(side=tk.LEFT)
        if subtitle:
            ctk.CTkLabel(frame, text=subtitle, text_color=muted, font=("Segoe UI", 11)).grid(
                row=1, column=0, columnspan=4, sticky="w", padx=18, pady=(2, 10)
            )
        return frame

    def entry(parent: Any, variable: tk.StringVar, **kwargs: Any) -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent,
            textvariable=variable,
            height=40,
            fg_color=field,
            border_color=border,
            border_width=1,
            text_color=fg,
            placeholder_text_color="#7f7277",
            corner_radius=8,
            font=("Segoe UI", 12),
            **kwargs,
        )

    def combo(parent: Any, variable: tk.StringVar, values: list[str], width: int = 180) -> ctk.CTkComboBox:
        return ctk.CTkComboBox(
            parent,
            variable=variable,
            values=values,
            width=width,
            height=40,
            fg_color=field,
            border_color=border,
            button_color=chip_bg,
            button_hover_color="#2a171c",
            dropdown_fg_color=panel,
            dropdown_hover_color=chip_bg,
            text_color=fg,
            corner_radius=8,
            font=("Segoe UI", 12),
            dropdown_font=("Segoe UI", 12),
        )

    def button(
        parent: Any,
        text: str,
        command: callable,
        kind: str = "default",
        width: int | None = None,
    ) -> ctk.CTkButton:
        colors = {
            "default": (chip_bg, "#272129", fg),
            "accent": (accent, accent_hover, "#fff7f7"),
            "danger": ("#451b22", danger, fg),
            "ghost": ("#0d0f14", "#191d25", fg),
        }
        fg_color, hover_color, text_color = colors[kind]
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=width if width is not None else 140,
            height=40,
            corner_radius=8,
            border_width=1 if kind in {"default", "ghost"} else 0,
            border_color=border,
            fg_color=fg_color,
            hover_color=hover_color,
            text_color=text_color,
            font=("Segoe UI Semibold", 12),
        )

    def avatar_initials(name: str) -> str:
        words = [part for part in re.split(r"\s+", name.strip()) if part]
        if not words:
            return "?"
        if len(words) == 1:
            return words[0][:2].upper()
        return (words[0][:1] + words[-1][:1]).upper()

    def crop_avatar(image: Image.Image, size: int) -> Image.Image:
        image = image.convert("RGBA")
        side = min(image.size)
        left = (image.width - side) // 2
        top = (image.height - side) // 2
        image = image.crop((left, top, left + side, top + side)).resize((size, size), Image.Resampling.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size - 1, size - 1), fill=255)
        image.putalpha(mask)
        return image

    def ensure_avatar_workers() -> None:
        nonlocal avatar_workers_started
        if avatar_workers_started:
            return
        avatar_workers_started = True
        for index in range(AVATAR_DOWNLOAD_WORKERS):
            threading.Thread(target=avatar_download_worker, name=f"AizenAvatarLoad-{index + 1}", daemon=True).start()

    def schedule_avatar_result_pump(delay_ms: int = 0) -> None:
        nonlocal avatar_result_after_id
        if app_closing:
            return
        try:
            callback = pump_avatar_results
        except NameError:
            return
        if avatar_result_after_id is not None:
            try:
                root.after_cancel(avatar_result_after_id)
            except tk.TclError:
                pass
        avatar_result_after_id = root.after(max(0, delay_ms), callback)

    def avatar_download_worker() -> None:
        session = requests.Session()
        while True:
            if app_closing and avatar_request_queue.empty():
                return
            try:
                clean_url, size = avatar_request_queue.get(timeout=0.5)
            except queue.Empty:
                if app_closing:
                    return
                continue
            try:
                response = session.get(clean_url, timeout=6, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if content_type and "image" not in content_type:
                    raise ValueError("URL nao retornou imagem.")
                image = Image.open(BytesIO(response.content))
                enqueue_avatar_result(clean_url, size, crop_avatar(image, size))
            except Exception:
                enqueue_avatar_result(clean_url, size, None)
            finally:
                avatar_request_queue.task_done()

    def request_avatar_image(url: str, size: int) -> Any | None:
        clean_url = (url or "").strip()
        if not clean_url:
            return None
        key = (clean_url, size)
        if key in avatar_image_cache:
            return avatar_image_cache[key]
        if key not in avatar_pending and clean_url.lower().startswith(("http://", "https://")):
            if len(avatar_pending) >= AVATAR_PENDING_LIMIT or avatar_request_queue.full():
                return None
            avatar_pending.add(key)
            ensure_avatar_workers()
            try:
                avatar_request_queue.put_nowait(key)
                schedule_avatar_result_pump(120)
            except queue.Full:
                avatar_pending.discard(key)
        return None

    def prune_avatar_image_cache() -> None:
        while len(avatar_image_cache) > AVATAR_IMAGE_CACHE_LIMIT:
            try:
                oldest_key = next(iter(avatar_image_cache))
            except StopIteration:
                return
            avatar_image_cache.pop(oldest_key, None)

    def configure_avatar_label(label: Any, name: str, avatar_url: str, size: int) -> None:
        image = request_avatar_image(avatar_url, size)
        label.configure(
            image=image,
            text="" if image else avatar_initials(name),
        )
        label._avatar_url = (avatar_url or "").strip()  # type: ignore[attr-defined]
        label._avatar_size = size  # type: ignore[attr-defined]
        label._avatar_name = name  # type: ignore[attr-defined]
        label._avatar_image = image  # type: ignore[attr-defined]

    def make_avatar_label(parent: Any, name: str, avatar_url: str, size: int = 42) -> Any:
        label = ctk.CTkLabel(
            parent,
            text=avatar_initials(name),
            width=size,
            height=size,
            fg_color=field,
            text_color=accent,
            corner_radius=size // 2,
            font=("Segoe UI Semibold", max(10, size // 3)),
        )
        configure_avatar_label(label, name, avatar_url, size)
        return label

    header = ctk.CTkFrame(
        main,
        fg_color=header_panel,
        corner_radius=14,
        border_width=1,
        border_color=border,
    )
    header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    header.columnconfigure(2, weight=1)
    logo_image = None
    active_logo_path = resolve_logo_path(theme_config)
    if active_logo_path.exists():
        try:
            source_logo = Image.open(active_logo_path)
            logo_image = ctk.CTkImage(light_image=source_logo, dark_image=source_logo, size=(58, 58))
            root._app_logo_image = logo_image  # type: ignore[attr-defined]
        except Exception:
            logo_image = None

    logo_card = ctk.CTkFrame(
        header,
        fg_color=field,
        corner_radius=16,
        border_width=2,
        border_color=accent,
        width=66,
        height=66,
    )
    ctk.CTkFrame(header, fg_color=accent, width=4, corner_radius=99).grid(
        row=0, column=0, sticky="nsw", padx=(14, 0), pady=12
    )
    logo_card.grid(row=0, column=1, sticky="w", padx=(16, 16), pady=12)
    logo_card.grid_propagate(False)
    if logo_image:
        ctk.CTkLabel(logo_card, image=logo_image, text="").place(relx=0.5, rely=0.5, anchor="center")
    else:
        ctk.CTkLabel(logo_card, text="A", text_color=accent, font=("Segoe UI Semibold", 32)).place(relx=0.5, rely=0.5, anchor="center")

    title_stack = ctk.CTkFrame(header, fg_color="transparent", corner_radius=0)
    title_stack.grid(row=0, column=2, sticky="ew")
    ctk.CTkLabel(
        title_stack,
        text="Aizen Stream Control",
        text_color=fg,
        font=("Segoe UI Semibold", 26),
    ).pack(anchor="w")
    ctk.CTkLabel(
        title_stack,
        text="Live suite 2026 para Free Fire, chat, sorteios e automações em tempo real",
        text_color=muted,
        font=("Segoe UI", 11),
    ).pack(anchor="w", pady=(2, 0))
    badge_row = ctk.CTkFrame(header, fg_color="transparent", corner_radius=0)
    badge_row.grid(row=0, column=3, sticky="e", padx=14)
    ctk.CTkLabel(
        badge_row,
        text="AIZEN",
        text_color=fg,
        fg_color=chip_bg,
        corner_radius=999,
        font=("Segoe UI Semibold", 11),
        padx=14,
        pady=7,
    ).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkLabel(
        badge_row,
        text=f"v{APP_VERSION}",
        text_color=muted,
        fg_color=field,
        corner_radius=999,
        font=("Segoe UI Semibold", 11),
        padx=14,
        pady=7,
    ).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkLabel(
        badge_row,
        text="LIVE SUITE",
        text_color=blue,
        fg_color=chip_bg_alt,
        corner_radius=999,
        font=("Segoe UI Semibold", 11),
        padx=14,
        pady=7,
    ).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkLabel(
        badge_row,
        text="AUTO UPDATE",
        text_color=teal,
        fg_color="#0d1714",
        corner_radius=999,
        font=("Segoe UI Semibold", 11),
        padx=14,
        pady=7,
    ).pack(side=tk.LEFT)

    tabview = ctk.CTkTabview(
        main,
        fg_color=bg,
        segmented_button_fg_color=field,
        segmented_button_selected_color=accent,
        segmented_button_selected_hover_color=accent_hover,
        segmented_button_unselected_color=field,
        segmented_button_unselected_hover_color=chip_bg,
        text_color=fg,
        corner_radius=16,
        border_width=1,
        border_color=border,
    )
    tabview.grid(row=1, column=0, sticky="nsew")
    visible_tab_names = [
        "Geral",
        "Kills FF",
        "Fila FF",
        "Overlay FF",
        "Livepix",
        "Chat Ao Vivo",
        "Comandos",
        "Temporizador",
        "Sorteio Chat",
        "Logs",
        "Aparência",
    ]
    for tab_name in visible_tab_names:
        if tab_name not in hidden_main_tabs:
            tabview.add(tab_name)
    general_tab_root = tabview.tab("Geral")
    kills_tab_root = tabview.tab("Kills FF")
    ff_queue_tab_root = None if ff_queue_site_sync_hidden else tabview.tab("Fila FF")
    ff_overlay_tab_root = None if ff_overlay_site_sync_hidden else tabview.tab("Overlay FF")
    livepix_tab_root = tabview.tab("Livepix")
    live_chat_tab_root = None if chat_tab_hidden else tabview.tab("Chat Ao Vivo")
    commands_tab_root = tabview.tab("Comandos")
    timers_tab_root = tabview.tab("Temporizador")
    raffle_tab = tabview.tab("Sorteio Chat")
    events_tab_root = tabview.tab("Logs")
    appearance_tab = tabview.tab("Aparência")
    general_tab_root.configure(fg_color=bg)
    kills_tab_root.configure(fg_color=bg)
    if ff_queue_tab_root is not None:
        ff_queue_tab_root.configure(fg_color=bg)
    if ff_overlay_tab_root is not None:
        ff_overlay_tab_root.configure(fg_color=bg)
    livepix_tab_root.configure(fg_color=bg)
    if live_chat_tab_root is not None:
        live_chat_tab_root.configure(fg_color=bg)
    commands_tab_root.configure(fg_color=bg)
    timers_tab_root.configure(fg_color=bg)
    raffle_tab.configure(fg_color=bg)
    events_tab_root.configure(fg_color=bg)
    appearance_tab.configure(fg_color=bg)

    for tab_root in (
        general_tab_root,
        kills_tab_root,
        ff_queue_tab_root,
        ff_overlay_tab_root,
        livepix_tab_root,
        live_chat_tab_root,
        commands_tab_root,
        timers_tab_root,
        events_tab_root,
    ):
        if tab_root is None:
            continue
        tab_root.columnconfigure(0, weight=1)
        tab_root.rowconfigure(0, weight=1)

    general_tab = ctk.CTkScrollableFrame(
        general_tab_root,
        fg_color=bg,
        corner_radius=0,
        scrollbar_button_color=chip_bg,
        scrollbar_button_hover_color=accent,
    )
    general_tab.grid(row=0, column=0, sticky="nsew")
    kills_tab = ctk.CTkFrame(
        kills_tab_root,
        fg_color=bg,
        corner_radius=0,
    )
    kills_tab.grid(row=0, column=0, sticky="nsew")
    if ff_queue_tab_root is not None:
        ff_queue_tab = ctk.CTkFrame(
            ff_queue_tab_root,
            fg_color=bg,
            corner_radius=0,
        )
        ff_queue_tab.grid(row=0, column=0, sticky="nsew")
    if ff_overlay_tab_root is not None:
        ff_overlay_tab = ctk.CTkFrame(
            ff_overlay_tab_root,
            fg_color=bg,
            corner_radius=0,
        )
        ff_overlay_tab.grid(row=0, column=0, sticky="nsew")
    livepix_tab = ctk.CTkFrame(
        livepix_tab_root,
        fg_color=bg,
        corner_radius=0,
    )
    livepix_tab.grid(row=0, column=0, sticky="nsew")
    if live_chat_tab_root is not None:
        live_chat_tab = ctk.CTkScrollableFrame(
            live_chat_tab_root,
            fg_color=bg,
            corner_radius=0,
            scrollbar_button_color=chip_bg,
            scrollbar_button_hover_color=accent,
        )
        live_chat_tab.grid(row=0, column=0, sticky="nsew")
    commands_tab = ctk.CTkFrame(
        commands_tab_root,
        fg_color=bg,
        corner_radius=0,
    )
    commands_tab.grid(row=0, column=0, sticky="nsew")
    timers_tab = ctk.CTkFrame(
        timers_tab_root,
        fg_color=bg,
        corner_radius=0,
    )
    timers_tab.grid(row=0, column=0, sticky="nsew")
    events_tab = ctk.CTkFrame(
        events_tab_root,
        fg_color=bg,
        corner_radius=0,
    )
    events_tab.grid(row=0, column=0, sticky="nsew")

    general_tab.columnconfigure(0, weight=1)
    general_tab.columnconfigure(1, weight=1)
    general_tab.rowconfigure(0, weight=0)
    general_tab.rowconfigure(1, weight=1)
    kills_tab.columnconfigure(0, weight=3, minsize=360)
    kills_tab.columnconfigure(1, weight=2, minsize=320)
    kills_tab.rowconfigure(0, weight=1)
    if ff_queue_tab_root is not None:
        ff_queue_tab.columnconfigure(0, weight=3, minsize=560)
        ff_queue_tab.columnconfigure(1, weight=1, minsize=340)
        ff_queue_tab.rowconfigure(0, weight=1)
    if ff_overlay_tab_root is not None:
        ff_overlay_tab.columnconfigure(0, weight=1, minsize=360)
        ff_overlay_tab.columnconfigure(1, weight=2, minsize=520)
        ff_overlay_tab.rowconfigure(0, weight=1)
    livepix_tab.columnconfigure(0, weight=1, minsize=320)
    livepix_tab.columnconfigure(1, weight=2, minsize=420)
    livepix_tab.rowconfigure(0, weight=1)
    if live_chat_tab_root is not None:
        live_chat_tab.columnconfigure(0, weight=1)
        live_chat_tab.rowconfigure(0, weight=0)
        live_chat_tab.rowconfigure(1, weight=0)
        live_chat_tab.rowconfigure(2, weight=0)
        live_chat_tab.rowconfigure(3, weight=1)
    commands_tab.columnconfigure(0, weight=1, minsize=320)
    commands_tab.columnconfigure(1, weight=2, minsize=420)
    commands_tab.rowconfigure(0, weight=1)
    timers_tab.columnconfigure(0, weight=1, minsize=320)
    timers_tab.columnconfigure(1, weight=2, minsize=420)
    timers_tab.rowconfigure(0, weight=1)
    raffle_tab.columnconfigure(0, weight=1)
    raffle_tab.rowconfigure(0, weight=1)
    events_tab.columnconfigure(0, weight=1)
    events_tab.rowconfigure(0, weight=1)
    appearance_tab.columnconfigure(0, weight=1)
    appearance_tab.rowconfigure(0, weight=1)

    raffle_body = ctk.CTkFrame(
        raffle_tab,
        fg_color=bg,
        corner_radius=0,
    )
    raffle_body.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
    raffle_body.columnconfigure(0, weight=1, minsize=500)
    raffle_body.columnconfigure(1, weight=2, minsize=520)
    raffle_body.rowconfigure(0, weight=1)

    kills_left = ctk.CTkScrollableFrame(
        kills_tab,
        fg_color=bg,
        corner_radius=0,
        scrollbar_button_color=chip_bg,
        scrollbar_button_hover_color=accent,
    )
    kills_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
    kills_left.columnconfigure(0, weight=1)
    kills_left.columnconfigure(1, weight=1)
    kills_left.rowconfigure(0, weight=0)
    kills_left.rowconfigure(1, weight=0)
    kills_left.rowconfigure(2, weight=0)
    kills_left.rowconfigure(3, weight=1)
    kills_left.rowconfigure(4, weight=0)

    kills_right = ctk.CTkFrame(kills_tab, fg_color=bg, corner_radius=0)
    kills_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=0)
    kills_right.columnconfigure(0, weight=1)
    kills_right.rowconfigure(0, weight=1)

    kills_layout_state = {"mode": ""}

    def apply_kills_responsive_layout(event: Any | None = None) -> None:
        width = int(getattr(event, "width", 0) or kills_tab.winfo_width() or 1200)
        compact = width < 1040
        mode = "compact" if compact else "wide"
        if kills_layout_state["mode"] == mode:
            return
        kills_layout_state["mode"] = mode
        kills_left.grid_forget()
        kills_right.grid_forget()
        if compact:
            kills_tab.columnconfigure(0, weight=1, minsize=0)
            kills_tab.columnconfigure(1, weight=0, minsize=0)
            kills_tab.rowconfigure(0, weight=1)
            kills_tab.rowconfigure(1, weight=1)
            kills_left.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 8))
            kills_right.grid(row=1, column=0, sticky="nsew", padx=0, pady=(8, 0))
            return
        kills_tab.columnconfigure(0, weight=3, minsize=360)
        kills_tab.columnconfigure(1, weight=2, minsize=320)
        kills_tab.rowconfigure(0, weight=1)
        kills_tab.rowconfigure(1, weight=0)
        kills_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        kills_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=0)

    kills_tab.bind("<Configure>", apply_kills_responsive_layout)
    root.after(250, apply_kills_responsive_layout)

    general_card = card(
        general_tab,
        "Opções gerais",
        "Configurações que valem para o app inteiro: identificação deste PC e atualização automática.",
    )
    general_card.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
    section_label(general_card, "Nome deste PC", 2)
    entry(general_card, device_name_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(general_card, "Token Jarvis", 3)
    entry(general_card, jarvis_token_var, show="*").grid(row=3, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(general_card, "Manifesto de atualização", 4)
    general_update_row = ctk.CTkFrame(general_card, fg_color=panel, corner_radius=0)
    general_update_row.grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    general_update_row.columnconfigure(0, weight=1)
    entry(general_update_row, updates_manifest_url_var).grid(row=0, column=0, sticky="ew")
    ctk.CTkCheckBox(
        general_update_row,
        text="Atualizar ao abrir",
        variable=auto_update_var,
        fg_color=accent,
        hover_color=accent_hover,
        border_color=border,
        text_color=fg,
    ).grid(row=0, column=1, sticky="e", padx=(14, 0))

    jarvis_connection_card = card(
        general_tab,
        "Jarvis FF",
        "Configure uma URL base e preencha os endpoints usados por Kills FF e Fila FF.",
    )
    jarvis_connection_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
    jarvis_connection_card.columnconfigure(1, weight=1)
    section_label(jarvis_connection_card, "URL base do Jarvis", 2)
    entry(jarvis_connection_card, jarvis_base_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    jarvis_connection_actions = ctk.CTkFrame(jarvis_connection_card, fg_color=panel, corner_radius=0)
    jarvis_connection_actions.grid(row=3, column=0, columnspan=4, sticky="ew", padx=18, pady=(8, 18))
    button(jarvis_connection_actions, "Preencher endpoints", lambda: apply_jarvis_base_url(), "accent", width=150).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    button(jarvis_connection_actions, "Testar Jarvis", lambda: test_jarvis_connection(), "default", width=120).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    if kills_ff_site_sync_hidden and ff_queue_site_sync_hidden:
        jarvis_connection_card.grid_remove()
    ff_dashboard_card = ctk.CTkFrame(
        general_tab,
        fg_color=panel_alt,
        corner_radius=12,
        border_width=1,
        border_color=border,
    )
    ff_dashboard_card.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
    for column in range(2):
        ff_dashboard_card.columnconfigure(column, weight=1)
    ctk.CTkLabel(
        ff_dashboard_card,
        text="Painel FF",
        text_color=fg,
        font=("Segoe UI Semibold", 18),
        anchor="w",
    ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 2))
    ctk.CTkLabel(
        ff_dashboard_card,
        text="Atalhos dos paineis usados com o Jarvis.",
        text_color=muted,
        font=("Segoe UI", 11),
        anchor="w",
    ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 12))
    ff_dashboard_panels = [
        (title_text, metric_var, target_tab)
        for title_text, metric_var, target_tab in (
            ("Kills FF", manual_total_var, "Kills FF"),
            ("Fila FF", ff_queue_count_var, "Fila FF"),
        )
        if target_tab not in hidden_main_tabs
    ]
    for column, (title_text, metric_var, target_tab) in enumerate(ff_dashboard_panels):
        panel_frame = ctk.CTkFrame(ff_dashboard_card, fg_color=field, corner_radius=12, border_width=1, border_color=border)
        panel_frame.grid(row=2, column=column, sticky="nsew", padx=(18 if column == 0 else 6, 18 if column == 1 else 6), pady=(0, 18))
        panel_frame.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            panel_frame,
            text=title_text,
            text_color=accent,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            panel_frame,
            textvariable=metric_var,
            text_color=teal,
            font=("Segoe UI Semibold", 24),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 2))
        button(panel_frame, "Abrir", lambda tab_name=target_tab: tabview.set(tab_name), "ghost", width=84).grid(
            row=2, column=0, sticky="ew", padx=14, pady=(8, 14)
        )
    if not ff_dashboard_panels:
        ff_dashboard_card.grid_remove()

    general_info_card = ctk.CTkFrame(general_tab, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
    general_info_card.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
    for column in range(3):
        general_info_card.columnconfigure(column, weight=1)
    for col, label in enumerate(("Versão", "Pasta do app", "Atualização")):
        ctk.CTkLabel(general_info_card, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=18, pady=(14, 0)
        )
    ctk.CTkLabel(general_info_card, text=f"v{APP_VERSION}", text_color=teal, font=("Segoe UI Semibold", 24)).grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 14)
    )
    ctk.CTkLabel(
        general_info_card,
        text=str(APP_DIR),
        text_color=fg,
        font=("Segoe UI Semibold", 12),
        wraplength=520,
        justify="left",
    ).grid(row=1, column=1, sticky="w", padx=18, pady=(4, 14))
    ctk.CTkLabel(
        general_info_card,
        textvariable=general_update_state_var,
        text_color=accent,
        font=("Segoe UI Semibold", 14),
    ).grid(row=1, column=2, sticky="w", padx=18, pady=(4, 14))

    general_actions = ctk.CTkFrame(general_tab, fg_color=bg, corner_radius=0)
    general_actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 12))

    sync_card = card(general_tab, "Lançamento de Kills FF", "Digite as kills no app e lance manualmente no painel Jarvis quando a partida acabar.")
    sync_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=8)
    sync_card.columnconfigure(1, weight=1)
    sync_card.columnconfigure(3, weight=1)
    section_label(sync_card, "URL do painel/Jarvis", 2)
    entry(sync_card, sync_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(sync_card, "Titulo", 3)
    entry(sync_card, title_var).grid(row=3, column=1, sticky="ew", padx=18, pady=5)
    section_label(sync_card, "Sala", 3, column=2)
    entry(sync_card, sync_room_var, width=140).grid(row=3, column=3, sticky="ew", padx=18, pady=5)
    section_label(sync_card, "Sincronização", 4)
    poll_row = ctk.CTkFrame(sync_card, fg_color=panel, corner_radius=0)
    poll_row.grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=(5, 18))
    ctk.CTkLabel(
        poll_row,
        text="Modo manual: use Salvar para enviar as kills digitadas ao Jarvis e Atualizar para ler o ranking quando precisar.",
        text_color=muted,
        font=("Segoe UI", 11),
        anchor="w",
        wraplength=680,
        justify="left",
    ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    kill_metrics = ctk.CTkFrame(kills_left, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
    kill_metrics.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
    for column in range(2):
        kill_metrics.columnconfigure(column, weight=1)
    for col, label in enumerate(("Jogadores", "Total de kills")):
        ctk.CTkLabel(kill_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=18, pady=(14, 0)
        )
    ctk.CTkLabel(kill_metrics, textvariable=manual_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 14)
    )
    ctk.CTkLabel(kill_metrics, textvariable=manual_total_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
        row=1, column=1, sticky="w", padx=18, pady=(0, 14)
    )
    kills_admin_card = card(
        kills_left,
        "Administrar ranking Jarvis",
        "Aplique no Jarvis as mesmas acoes do site sem alterar a tabela visual da direita.",
    )
    kills_admin_card.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 12))
    kills_admin_card.columnconfigure(1, weight=1)
    kills_admin_card.columnconfigure(3, weight=1)
    section_label(kills_admin_card, "Jogador atual", 2)
    entry(kills_admin_card, kills_admin_name_var).grid(row=2, column=1, sticky="ew", padx=18, pady=5)
    section_label(kills_admin_card, "Novo nome", 2, column=2)
    entry(kills_admin_card, kills_admin_new_name_var).grid(row=2, column=3, sticky="ew", padx=18, pady=5)
    section_label(kills_admin_card, "ID FF", 3)
    entry(kills_admin_card, kills_admin_ff_id_var, width=160).grid(row=3, column=1, sticky="ew", padx=18, pady=5)
    section_label(kills_admin_card, "Kills", 3, column=2)
    entry(kills_admin_card, kills_admin_kills_var, width=120).grid(row=3, column=3, sticky="w", padx=18, pady=5)
    section_label(kills_admin_card, "Escopo", 4)
    kills_admin_scope = ctk.CTkSegmentedButton(
        kills_admin_card,
        values=["Diario", "Geral"],
        variable=kills_admin_scope_var,
        height=34,
        corner_radius=10,
        fg_color=field,
        selected_color=accent,
        selected_hover_color=accent_hover,
        unselected_color=field,
        unselected_hover_color=chip_bg,
        text_color=fg,
        font=("Segoe UI Semibold", 12),
    )
    kills_admin_scope.grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=(5, 10))
    kills_admin_actions = ctk.CTkFrame(kills_admin_card, fg_color=panel, corner_radius=0)
    kills_admin_actions.grid(row=5, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 18))

    kills_style_card = card(
        kills_left,
        "OBS Kills FF",
        "Personalize o overlay transparente /freefire-kills/obs do Jarvis direto pelo app.",
    )
    kills_style_card.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 12))
    kills_style_card.columnconfigure(1, weight=1)
    kills_style_card.columnconfigure(3, weight=1)
    section_label(kills_style_card, "Endpoint estilo", 2)
    entry(kills_style_card, kills_style_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
    section_label(kills_style_card, "URL OBS", 3)
    ctk.CTkEntry(
        kills_style_card,
        textvariable=kills_obs_url_var,
        fg_color=field,
        border_color=border,
        text_color=fg,
        state="readonly",
    ).grid(row=3, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
    section_label(kills_style_card, "Título", 4)
    entry(kills_style_card, kills_style_title_var).grid(row=4, column=1, sticky="ew", padx=18, pady=4)
    section_label(kills_style_card, "Fonte", 4, column=2)
    combo(kills_style_card, kills_style_font_var, ["impact", "arial", "trebuchet", "verdana", "tahoma", "georgia", "courier", "system"], width=160).grid(
        row=4, column=3, sticky="ew", padx=18, pady=4
    )
    section_label(kills_style_card, "Alinhamento", 5)
    combo(kills_style_card, kills_style_align_var, ["left", "center", "right"], width=140).grid(row=5, column=1, sticky="ew", padx=18, pady=4)
    section_label(kills_style_card, "Título", 5, column=2)
    combo(kills_style_card, kills_style_title_align_var, ["left", "center", "right"], width=140).grid(
        row=5, column=3, sticky="ew", padx=18, pady=4
    )
    kills_style_sizes = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_sizes.grid(row=6, column=0, columnspan=4, sticky="ew", padx=18, pady=4)
    for label, var in (
        ("Título", kills_style_title_size_var),
        ("Nome", kills_style_row_size_var),
        ("Kills", kills_style_kills_size_var),
        ("Rank", kills_style_rank_size_var),
        ("Peso", kills_style_weight_var),
        ("Altura", kills_style_row_height_var),
        ("Espaço", kills_style_row_gap_var),
    ):
        ctk.CTkLabel(kills_style_sizes, text=label, text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 6))
        entry(kills_style_sizes, var, width=58).pack(side=tk.LEFT, padx=(0, 10))
    kills_style_layout = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_layout.grid(row=7, column=0, columnspan=4, sticky="ew", padx=18, pady=4)
    for label, var in (
        ("Largura", kills_style_row_max_width_var),
        ("Gap col.", kills_style_column_gap_var),
        ("Pad. linha", kills_style_row_padding_var),
        ("Padding", kills_style_wrap_padding_var),
        ("Troca s", kills_style_switch_seconds_var),
        ("Raio", kills_style_row_radius_var),
        ("Borda px", kills_style_accent_width_var),
    ):
        ctk.CTkLabel(kills_style_layout, text=label, text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 6))
        entry(kills_style_layout, var, width=58).pack(side=tk.LEFT, padx=(0, 10))
    kills_style_colors = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_colors.grid(row=8, column=0, columnspan=4, sticky="ew", padx=18, pady=4)
    for label, var in (
        ("Título", kills_style_title_color_var),
        ("Rank", kills_style_rank_color_var),
        ("Nome", kills_style_name_color_var),
        ("Kills", kills_style_kills_color_var),
        ("Sombra", kills_style_shadow_color_var),
        ("Fundo", kills_style_row_bg_color_var),
        ("Borda", kills_style_accent_color_var),
    ):
        ctk.CTkLabel(kills_style_colors, text=label, text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 6))
        entry(kills_style_colors, var, width=84).pack(side=tk.LEFT, padx=(0, 10))
    kills_style_effects = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_effects.grid(row=9, column=0, columnspan=4, sticky="ew", padx=18, pady=4)
    for label, var in (
        ("Blur sombra", kills_style_shadow_blur_var),
        ("Opac. fundo", kills_style_row_bg_opacity_var),
    ):
        ctk.CTkLabel(kills_style_effects, text=label, text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(0, 6))
        entry(kills_style_effects, var, width=72).pack(side=tk.LEFT, padx=(0, 10))
    kills_style_toggles = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_toggles.grid(row=10, column=0, columnspan=4, sticky="ew", padx=18, pady=6)
    for label, var in (
        ("Título", kills_style_show_title_var),
        ("Maiúsculo", kills_style_uppercase_var),
        ("Mostrar #", kills_style_rank_prefix_var),
        ("Medalhas", kills_style_medals_var),
        ("Fundo", kills_style_row_bg_var),
        ("Borda", kills_style_accent_var),
    ):
        ctk.CTkCheckBox(
            kills_style_toggles,
            text=label,
            variable=var,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).pack(side=tk.LEFT, padx=(0, 12))
    kills_style_footer = ctk.CTkFrame(kills_style_card, fg_color=panel, corner_radius=0)
    kills_style_footer.grid(row=11, column=0, columnspan=4, sticky="ew", padx=18, pady=(4, 18))
    kills_style_footer.columnconfigure(0, weight=1)
    ctk.CTkLabel(kills_style_footer, textvariable=kills_style_status_var, text_color=accent, font=("Segoe UI Semibold", 11), anchor="w").grid(
        row=0, column=0, sticky="ew", padx=(0, 10)
    )
    kills_style_actions = ctk.CTkFrame(kills_style_footer, fg_color=panel, corner_radius=0)
    kills_style_actions.grid(row=0, column=1, sticky="e")

    kills_admin_card.grid_remove()
    kills_style_card.grid_remove()

    manual_card = card(kills_left, "Kills FF", "Digite as kills feitas na partida e lance no rank diario ou geral.")
    manual_card.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=12, pady=(8, 12))
    manual_card.columnconfigure(0, weight=1)
    manual_card.rowconfigure(4, weight=1)
    manual_scope_row = ctk.CTkFrame(manual_card, fg_color=panel, corner_radius=0)
    manual_scope_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(2, 10))
    manual_scope_row.columnconfigure(0, weight=1)
    manual_scope_segmented = ctk.CTkSegmentedButton(
        manual_scope_row,
        values=["Diario", "Geral"],
        variable=manual_scope_var,
        height=36,
        corner_radius=12,
        fg_color=field,
        selected_color=accent,
        selected_hover_color=accent_hover,
        unselected_color=field,
        unselected_hover_color=chip_bg,
        text_color=fg,
        font=("Segoe UI Semibold", 12),
        command=lambda _value=None: on_manual_scope_change(),
    )
    manual_scope_segmented.grid(row=0, column=0, sticky="ew", padx=(0, 0), pady=4)
    table_header = ctk.CTkFrame(manual_card, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
    table_header.grid(row=3, column=0, columnspan=4, sticky="ew", padx=18, pady=(4, 0))
    table_header.columnconfigure(0, weight=1)
    ctk.CTkLabel(table_header, text="Nick do jogador", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=0, sticky="w", padx=14, pady=(0, 6)
    )
    ctk.CTkLabel(table_header, text="Kills", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=1, sticky="w", padx=12, pady=(0, 6)
    )
    manual_table_frame = ctk.CTkScrollableFrame(
        manual_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color="#3a1518",
        scrollbar_button_hover_color="#5a1d22",
    )
    manual_table_frame.grid(row=4, column=0, columnspan=4, sticky="nsew", padx=18, pady=(0, 12))
    manual_table_frame.columnconfigure(0, weight=1)
    manual_actions = ctk.CTkFrame(manual_card, fg_color=panel, corner_radius=0)
    manual_actions.grid(row=5, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 18))

    def build_kills_rank_section(
        parent: Any,
        title: str,
        subtitle: str,
        count_var: tk.StringVar,
        total_var: tk.StringVar,
        row: int,
    ) -> ctk.CTkScrollableFrame:
        section = ctk.CTkFrame(parent, fg_color=panel_alt, corner_radius=16, border_width=1, border_color=border)
        section.grid(row=row, column=0, sticky="nsew", padx=18, pady=(0, 12))
        section.columnconfigure(0, weight=1)
        section.rowconfigure(3, weight=1)

        header = ctk.CTkFrame(section, fg_color=panel_alt, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 8))
        header.columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text=title, text_color=fg, font=("Segoe UI Semibold", 15), anchor="w").grid(
            row=0, column=0, sticky="ew"
        )
        ctk.CTkLabel(header, text=subtitle, text_color=muted, font=("Segoe UI", 11), anchor="w").grid(
            row=1, column=0, sticky="ew", pady=(2, 0)
        )

        metrics = ctk.CTkFrame(section, fg_color=field, corner_radius=12, border_width=1, border_color=border)
        metrics.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        for metric_column in range(2):
            metrics.columnconfigure(metric_column, weight=1)
        for metric_column, label in enumerate(("Jogadores", "Kills")):
            ctk.CTkLabel(metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=metric_column, sticky="w", padx=12, pady=(10, 0)
            )
        ctk.CTkLabel(metrics, textvariable=count_var, text_color=teal, font=("Segoe UI Semibold", 22)).grid(
            row=1, column=0, sticky="w", padx=12, pady=(0, 10)
        )
        ctk.CTkLabel(metrics, textvariable=total_var, text_color=teal, font=("Segoe UI Semibold", 22)).grid(
            row=1, column=1, sticky="w", padx=12, pady=(0, 10)
        )

        rank_header = ctk.CTkFrame(section, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
        rank_header.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 0))
        rank_header.columnconfigure(1, weight=1)
        ctk.CTkLabel(rank_header, text="#", text_color=muted, font=("Segoe UI Semibold", 11), width=42).grid(
            row=0, column=0, sticky="w", padx=(12, 4), pady=(0, 6)
        )
        ctk.CTkLabel(rank_header, text="Jogador", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=0, column=1, sticky="w", padx=8, pady=(0, 6)
        )
        ctk.CTkLabel(rank_header, text="Kills", text_color=muted, font=("Segoe UI Semibold", 11), width=70).grid(
            row=0, column=2, sticky="e", padx=(8, 12), pady=(0, 6)
        )
        ctk.CTkLabel(rank_header, text="Ação", text_color=muted, font=("Segoe UI Semibold", 11), width=68).grid(
            row=0, column=3, sticky="e", padx=(4, 12), pady=(0, 6)
        )

        table_frame = ctk.CTkScrollableFrame(
            section,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            scrollbar_button_color="#3a1518",
            scrollbar_button_hover_color="#5a1d22",
        )
        table_frame.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 14))
        table_frame.columnconfigure(0, weight=1)
        return table_frame

    kills_rank_card = card(
        kills_right,
        "Rank Kills FF",
        "Dois rankings separados vindos do Jarvis, somente para visualizacao.",
    )
    kills_rank_card.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 12))
    kills_rank_card.columnconfigure(0, weight=1)
    kills_rank_card.rowconfigure(3, weight=1)
    kills_rank_card.rowconfigure(4, weight=1)
    kills_rank_toolbar = ctk.CTkFrame(kills_rank_card, fg_color=panel, corner_radius=0)
    kills_rank_toolbar.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 12))
    kills_rank_toolbar.columnconfigure(0, weight=1)
    ctk.CTkLabel(
        kills_rank_toolbar,
        text="Atualiza automaticamente pelo Jarvis; use Buscar Jarvis para forcar leitura.",
        text_color=muted,
        font=("Segoe UI", 11),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
    button(kills_rank_toolbar, "Buscar Jarvis", lambda: fetch_panel_kills(force=True), "default", width=128).grid(
        row=0, column=1, sticky="e"
    )
    kills_daily_rank_table_frame = build_kills_rank_section(
        kills_rank_card,
        "Kills Diárias",
        "Ranking resetado por período diário no site.",
        kills_daily_rank_count_var,
        kills_daily_rank_total_var,
        3,
    )
    kills_global_rank_table_frame = build_kills_rank_section(
        kills_rank_card,
        "Kills Geral",
        "Acumulado geral dos jogadores no Jarvis.",
        kills_global_rank_count_var,
        kills_global_rank_total_var,
        4,
    )
    kills_ignored_header = ctk.CTkFrame(kills_rank_card, fg_color=panel, corner_radius=0)
    kills_ignored_header.grid(row=5, column=0, sticky="ew", padx=18, pady=(0, 4))
    kills_ignored_header.columnconfigure(0, weight=1)
    ctk.CTkLabel(
        kills_ignored_header,
        text="Ignorados",
        text_color=fg,
        font=("Segoe UI Semibold", 13),
        anchor="w",
    ).grid(row=0, column=0, sticky="ew")
    ctk.CTkLabel(
        kills_ignored_header,
        textvariable=kills_ignored_count_var,
        text_color=muted,
        font=("Segoe UI Semibold", 12),
        width=40,
    ).grid(row=0, column=1, sticky="e")
    kills_ignored_frame = ctk.CTkScrollableFrame(
        kills_rank_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color="#3a1518",
        scrollbar_button_hover_color="#5a1d22",
        height=92,
    )
    kills_ignored_frame.grid(row=6, column=0, sticky="ew", padx=18, pady=(0, 18))
    kills_ignored_frame.columnconfigure(0, weight=1)
    kills_rank_card.grid_remove()

    kills_overlay_daily_rows: list[Any] = []
    kills_overlay_global_rows: list[Any] = []
    kills_overlay_card = card(
        kills_right,
        "Overlay de ranking Kills FF",
        "Ranking interno separado entre diário e geral.",
    )
    kills_overlay_card.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 12))
    kills_overlay_card.columnconfigure(0, weight=1)
    kills_overlay_card.rowconfigure(3, weight=1)

    kills_overlay_toolbar = ctk.CTkFrame(kills_overlay_card, fg_color=panel, corner_radius=0)
    kills_overlay_toolbar.grid(row=2, column=0, sticky="ew", padx=18, pady=(2, 8))
    kills_overlay_toolbar.columnconfigure(0, weight=1)
    button(kills_overlay_toolbar, "Atualizar rank", lambda: fetch_panel_kills(force=True), "accent", width=128).grid(
        row=0, column=0, sticky="e"
    )

    kills_overlay_tabview = ctk.CTkTabview(
        kills_overlay_card,
        fg_color=field,
        segmented_button_fg_color=panel_alt,
        segmented_button_selected_color=accent,
        segmented_button_selected_hover_color=accent_hover,
        segmented_button_unselected_color=panel_alt,
        segmented_button_unselected_hover_color=chip_bg,
        text_color=fg,
        corner_radius=14,
        border_width=1,
        border_color=border,
        command=lambda: schedule_kills_visual_refresh(40),
    )
    kills_overlay_tabview.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
    kills_overlay_tabview.add("Diário")
    kills_overlay_tabview.add("Geral")
    kills_overlay_daily_tab = kills_overlay_tabview.tab("Diário")
    kills_overlay_global_tab = kills_overlay_tabview.tab("Geral")
    for overlay_tab in (kills_overlay_daily_tab, kills_overlay_global_tab):
        overlay_tab.configure(fg_color=field)
        overlay_tab.columnconfigure(0, weight=1)
        overlay_tab.rowconfigure(1, weight=1)

    def build_kills_overlay_rank_tab(parent: Any) -> ctk.CTkScrollableFrame:
        header = ctk.CTkFrame(parent, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        header.columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Rank", text_color=muted, font=("Segoe UI Semibold", 11), width=48).grid(
            row=0, column=0, sticky="w", padx=(12, 6), pady=(0, 6)
        )
        ctk.CTkLabel(header, text="Jogador", text_color=muted, font=("Segoe UI Semibold", 11), anchor="w").grid(
            row=0, column=1, sticky="ew", padx=8, pady=(0, 6)
        )
        ctk.CTkLabel(header, text="Kills", text_color=muted, font=("Segoe UI Semibold", 11), width=80).grid(
            row=0, column=2, sticky="e", padx=(8, 12), pady=(0, 6)
        )
        table = ctk.CTkScrollableFrame(
            parent,
            fg_color="#050609",
            corner_radius=12,
            border_width=1,
            border_color=border,
            scrollbar_button_color="#3a1518",
            scrollbar_button_hover_color="#5a1d22",
        )
        table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        table.columnconfigure(0, weight=1)
        return table

    kills_overlay_daily_frame = build_kills_overlay_rank_tab(kills_overlay_daily_tab)
    kills_overlay_global_frame = build_kills_overlay_rank_tab(kills_overlay_global_tab)

    if not ff_queue_site_sync_hidden:
        ff_queue_left = ctk.CTkScrollableFrame(
            ff_queue_tab,
            fg_color=bg,
            corner_radius=0,
            scrollbar_button_color=chip_bg,
            scrollbar_button_hover_color=accent,
        )
        ff_queue_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        ff_queue_left.columnconfigure(0, weight=1)
        ff_queue_left.rowconfigure(2, weight=1)

        ff_queue_right = ctk.CTkFrame(ff_queue_tab, fg_color=bg, corner_radius=0)
        ff_queue_right.grid(row=0, column=1, sticky="nsew", padx=(4, 0), pady=0)
        ff_queue_right.columnconfigure(0, weight=1)
        ff_queue_right.rowconfigure(0, weight=1)

        ff_queue_sync_card = card(
            ff_queue_left,
            "Fila Free Fire em tempo real",
            "Controle a fila de jogadores e mantenha tudo sincronizado com o painel Jarvis.",
        )
        ff_queue_sync_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        ff_queue_sync_card.columnconfigure(1, weight=1)
        ff_queue_sync_card.columnconfigure(3, weight=1)
        section_label(ff_queue_sync_card, "URL da fila/Jarvis", 2)
        entry(ff_queue_sync_card, ff_queue_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
        section_label(ff_queue_sync_card, "Sala", 3)
        entry(ff_queue_sync_card, ff_queue_room_var, width=180).grid(row=3, column=1, sticky="w", padx=18, pady=5)
        section_label(ff_queue_sync_card, "Ler fila a cada", 3, column=2)
        ff_poll_row = ctk.CTkFrame(ff_queue_sync_card, fg_color=panel, corner_radius=0)
        ff_poll_row.grid(row=3, column=3, sticky="ew", padx=18, pady=5)
        entry(ff_poll_row, ff_queue_poll_seconds_var, width=80).pack(side=tk.LEFT)
        ctk.CTkLabel(ff_poll_row, text="segundos", text_color=muted, font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(8, 18))
        ctk.CTkCheckBox(
            ff_poll_row,
            text="Sincronizar automaticamente",
            variable=ff_queue_enabled_var,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).pack(side=tk.LEFT)

        ff_queue_metrics = ctk.CTkFrame(ff_queue_left, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        ff_queue_metrics.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        for column in range(2):
            ff_queue_metrics.columnconfigure(column, weight=1)
        for col, label in enumerate(("Na fila", "Jogando")):
            ctk.CTkLabel(ff_queue_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=col, sticky="w", padx=18, pady=(14, 0)
            )
        ctk.CTkLabel(ff_queue_metrics, textvariable=ff_queue_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(ff_queue_metrics, textvariable=ff_queue_playing_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=1, sticky="w", padx=18, pady=(0, 14)
        )
        ff_queue_summary_card = card(
            ff_queue_right,
            "Resumo de salas",
            "Lista visual igual ao site: jogadores únicos e salas pendentes por estado.",
        )
        ff_queue_summary_card.grid(row=0, column=0, sticky="nsew", padx=(8, 12), pady=(12, 12))
        ff_queue_summary_card.columnconfigure(0, weight=1)
        ff_queue_summary_card.rowconfigure(3, weight=1)
        ff_queue_summary_metrics = ctk.CTkFrame(
            ff_queue_summary_card,
            fg_color=panel_alt,
            corner_radius=12,
            border_width=1,
            border_color=border,
        )
        ff_queue_summary_metrics.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 10))
        ff_queue_summary_metrics.columnconfigure(0, weight=1)
        ff_queue_summary_metrics.columnconfigure(1, weight=1)
        for column, (label, var) in enumerate(
            (
                ("Jogadores", ff_queue_summary_count_var),
                ("Salas", ff_queue_summary_rooms_var),
            )
        ):
            ctk.CTkLabel(ff_queue_summary_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=column, sticky="w", padx=12, pady=(10, 0)
            )
            ctk.CTkLabel(ff_queue_summary_metrics, textvariable=var, text_color=teal, font=("Segoe UI Semibold", 22)).grid(
                row=1, column=column, sticky="w", padx=12, pady=(0, 10)
            )
        ff_queue_summary_frame = ctk.CTkScrollableFrame(
            ff_queue_summary_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=180,
            scrollbar_button_color="#3a1518",
            scrollbar_button_hover_color="#5a1d22",
        )
        ff_queue_summary_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        ff_queue_summary_frame.columnconfigure(0, weight=1)

        ff_queue_manual_card = card(
            ff_queue_left,
            "Adicionar jogador manualmente",
            "Mesmo cadastro do site: nome, ID do membro, ID FF e quantidade de salas.",
        )
        ff_queue_manual_card.grid(row=3, column=0, sticky="ew", padx=12, pady=8)
        ff_queue_manual_card.columnconfigure(1, weight=1)
        ff_queue_manual_card.columnconfigure(3, weight=1)
        section_label(ff_queue_manual_card, "Nome", 2)
        entry(ff_queue_manual_card, ff_queue_manual_name_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
        section_label(ff_queue_manual_card, "ID membro", 3)
        entry(ff_queue_manual_card, ff_queue_manual_user_id_var).grid(row=3, column=1, sticky="ew", padx=18, pady=4)
        section_label(ff_queue_manual_card, "ID FF", 3, column=2)
        entry(ff_queue_manual_card, ff_queue_manual_ff_id_var).grid(row=3, column=3, sticky="ew", padx=18, pady=4)
        section_label(ff_queue_manual_card, "Salas", 4)
        entry(ff_queue_manual_card, ff_queue_manual_rooms_var, width=90).grid(row=4, column=1, sticky="w", padx=18, pady=(4, 14))
        ff_queue_manual_actions = ctk.CTkFrame(ff_queue_manual_card, fg_color=panel, corner_radius=0)
        ff_queue_manual_actions.grid(row=4, column=2, columnspan=2, sticky="e", padx=18, pady=(4, 14))
        button(ff_queue_manual_actions, "Adicionar no Jarvis", lambda: add_ff_queue_manual_member(), "accent", width=142).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        button(ff_queue_manual_actions, "Limpar", lambda: clear_ff_queue_manual_form(), "ghost", width=80).pack(side=tk.LEFT)

        tikfinity_ff_card = card(
            ff_queue_left,
            "Salas por Gifts TikFinity",
            "Converta moedas de presentes em salas e vincule espectadores ao cadastro da Fila FF.",
        )
        tikfinity_ff_card.grid(row=4, column=0, sticky="ew", padx=12, pady=8)
        tikfinity_ff_card.columnconfigure(1, weight=1)
        tikfinity_ff_card.columnconfigure(3, weight=1)
        section_label(tikfinity_ff_card, "URL Jarvis", 2)
        entry(tikfinity_ff_card, tikfinity_ff_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
        section_label(tikfinity_ff_card, "Perfil", 3)
        entry(tikfinity_ff_card, tikfinity_ff_profile_var, width=120).grid(row=3, column=1, sticky="w", padx=18, pady=4)
        section_label(tikfinity_ff_card, "Moedas por sala", 3, column=2)
        entry(tikfinity_ff_card, tikfinity_ff_coins_var, width=100).grid(row=3, column=3, sticky="w", padx=18, pady=4)
        section_label(tikfinity_ff_card, "Token webhook", 4)
        entry(tikfinity_ff_card, tikfinity_ff_token_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
        section_label(tikfinity_ff_card, "Webhook", 5)
        ctk.CTkEntry(
            tikfinity_ff_card,
            textvariable=tikfinity_ff_webhook_var,
            fg_color=field,
            border_color=border,
            text_color=fg,
            state="readonly",
        ).grid(row=5, column=1, columnspan=3, sticky="ew", padx=18, pady=4)
        tikfinity_ff_toggle_row = ctk.CTkFrame(tikfinity_ff_card, fg_color=panel, corner_radius=0)
        tikfinity_ff_toggle_row.grid(row=6, column=0, columnspan=4, sticky="ew", padx=18, pady=(6, 4))
        ctk.CTkCheckBox(
            tikfinity_ff_toggle_row,
            text="Ativar gifts do TikFinity",
            variable=tikfinity_ff_enabled_var,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).pack(side=tk.LEFT, padx=(0, 12))
        ctk.CTkLabel(tikfinity_ff_toggle_row, textvariable=tikfinity_ff_summary_var, text_color=muted, font=("Segoe UI", 11)).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ctk.CTkLabel(tikfinity_ff_toggle_row, textvariable=tikfinity_ff_status_var, text_color=accent, font=("Segoe UI Semibold", 11)).pack(
            side=tk.RIGHT
        )
        tikfinity_ff_actions = ctk.CTkFrame(tikfinity_ff_card, fg_color=panel, corner_radius=0)
        tikfinity_ff_actions.grid(row=7, column=0, columnspan=4, sticky="ew", padx=18, pady=(4, 10))
        button(tikfinity_ff_actions, "Buscar", lambda: fetch_tikfinity_ff_panel(force=True), "default", width=82).pack(side=tk.LEFT, padx=(0, 6))
        button(tikfinity_ff_actions, "Salvar config", lambda: save_tikfinity_ff_config(), "accent", width=112).pack(side=tk.LEFT, padx=(0, 6))
        button(tikfinity_ff_actions, "Copiar webhook", lambda: copy_tikfinity_ff_webhook(), "default", width=126).pack(side=tk.LEFT, padx=(0, 6))
        button(tikfinity_ff_actions, "Limpar histórico", lambda: clear_tikfinity_ff_history(), "danger", width=126).pack(side=tk.LEFT)

        tikfinity_ff_map_card = ctk.CTkFrame(tikfinity_ff_card, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        tikfinity_ff_map_card.grid(row=8, column=0, columnspan=4, sticky="ew", padx=18, pady=(2, 10))
        tikfinity_ff_map_card.columnconfigure(1, weight=1)
        tikfinity_ff_map_card.columnconfigure(3, weight=1)
        section_label(tikfinity_ff_map_card, "TikTok", 0)
        entry(tikfinity_ff_map_card, tikfinity_ff_map_handle_var).grid(row=0, column=1, sticky="ew", padx=10, pady=4)
        section_label(tikfinity_ff_map_card, "ID membro", 0, column=2)
        entry(tikfinity_ff_map_card, tikfinity_ff_map_user_id_var).grid(row=0, column=3, sticky="ew", padx=10, pady=4)
        section_label(tikfinity_ff_map_card, "Nome", 1)
        entry(tikfinity_ff_map_card, tikfinity_ff_map_display_var).grid(row=1, column=1, sticky="ew", padx=10, pady=4)
        section_label(tikfinity_ff_map_card, "ID FF", 1, column=2)
        entry(tikfinity_ff_map_card, tikfinity_ff_map_ff_id_var).grid(row=1, column=3, sticky="ew", padx=10, pady=4)
        button(tikfinity_ff_map_card, "Vincular TikTok", lambda: add_tikfinity_ff_mapping(), "accent", width=130).grid(
            row=2, column=0, columnspan=4, sticky="ew", padx=10, pady=(6, 10)
        )

        ctk.CTkLabel(tikfinity_ff_card, text="Vínculos", text_color=fg, font=("Segoe UI Semibold", 13)).grid(
            row=9, column=0, columnspan=4, sticky="w", padx=18, pady=(4, 2)
        )
        tikfinity_ff_mappings_frame = ctk.CTkScrollableFrame(
            tikfinity_ff_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=112,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        tikfinity_ff_mappings_frame.grid(row=10, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 8))
        tikfinity_ff_mappings_frame.columnconfigure(0, weight=1)
        ctk.CTkLabel(tikfinity_ff_card, text="Moedas acumuladas", text_color=fg, font=("Segoe UI Semibold", 13)).grid(
            row=11, column=0, columnspan=4, sticky="w", padx=18, pady=(4, 2)
        )
        tikfinity_ff_users_frame = ctk.CTkScrollableFrame(
            tikfinity_ff_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=126,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        tikfinity_ff_users_frame.grid(row=12, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 8))
        tikfinity_ff_users_frame.columnconfigure(0, weight=1)
        ctk.CTkLabel(tikfinity_ff_card, text="Histórico recente", text_color=fg, font=("Segoe UI Semibold", 13)).grid(
            row=13, column=0, columnspan=4, sticky="w", padx=18, pady=(4, 2)
        )
        tikfinity_ff_history_frame = ctk.CTkScrollableFrame(
            tikfinity_ff_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=126,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        tikfinity_ff_history_frame.grid(row=14, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 18))
        tikfinity_ff_history_frame.columnconfigure(0, weight=1)
        ff_queue_manual_card.grid_remove()
        tikfinity_ff_card.grid_remove()

        ff_queue_card = card(
            ff_queue_left,
            "Fila FF",
            "Organize jogadores por ordem, status e observações. As alterações podem ir para o Jarvis em tempo real.",
        )
        ff_queue_card.grid(row=2, column=0, sticky="nsew", padx=12, pady=(8, 12))
        ff_queue_card.columnconfigure(0, weight=1)
        ff_queue_card.rowconfigure(3, weight=1)
        ff_queue_header = ctk.CTkFrame(ff_queue_card, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
        ff_queue_header.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(4, 0))
        ff_queue_header.columnconfigure(0, weight=1)
        ctk.CTkLabel(ff_queue_header, text="Nick", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=0, column=0, sticky="w", padx=14, pady=(0, 6)
        )
        ctk.CTkLabel(ff_queue_header, text="Observação", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=0, column=1, sticky="w", padx=12, pady=(0, 6)
        )
        ctk.CTkLabel(ff_queue_header, text="Salas", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=0, column=2, sticky="w", padx=12, pady=(0, 6)
        )
        ctk.CTkLabel(ff_queue_header, text="Status", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
            row=0, column=3, sticky="w", padx=12, pady=(0, 6)
        )
        ff_queue_table_frame = ctk.CTkScrollableFrame(
            ff_queue_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            height=430,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        ff_queue_table_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=18, pady=(0, 12))
        ff_queue_table_frame.columnconfigure(0, weight=1)
        ff_queue_actions = ctk.CTkFrame(ff_queue_card, fg_color=panel, corner_radius=0)
        ff_queue_actions.grid(row=4, column=0, columnspan=4, sticky="ew", padx=18, pady=(0, 18))

    if not ff_overlay_site_sync_hidden:
        ff_overlay_controls = ctk.CTkScrollableFrame(
            ff_overlay_tab,
            fg_color=bg,
            corner_radius=0,
            scrollbar_button_color=chip_bg,
            scrollbar_button_hover_color=accent,
        )
        ff_overlay_controls.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
        ff_overlay_controls.columnconfigure(0, weight=1)

        ff_overlay_sync_card = card(
            ff_overlay_controls,
            "Overlay FF sincronizado",
            "Mostra Kills FF e Fila FF usando os mesmos dados em tempo real do painel Jarvis.",
        )
        ff_overlay_sync_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        ff_overlay_sync_card.columnconfigure(1, weight=1)
        ctk.CTkLabel(
            ff_overlay_sync_card,
            text="Usa as URLs configuradas em Kills FF e Fila FF. O overlay atualiza quando o app lê ou envia dados para o Jarvis.",
            text_color=muted,
            font=("Segoe UI", 11),
            wraplength=340,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 6))
        section_label(ff_overlay_sync_card, "URL Overlay/Jarvis", 3)
        entry(ff_overlay_sync_card, ff_overlay_url_var).grid(row=3, column=1, sticky="ew", padx=18, pady=5)
        ff_overlay_realtime_row = ctk.CTkFrame(ff_overlay_sync_card, fg_color=panel, corner_radius=0)
        ff_overlay_realtime_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=18, pady=(4, 2))
        ff_overlay_realtime_row.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            ff_overlay_realtime_row,
            text="Kills FF em modo manual: use os botões Salvar ou Atualizar.",
            text_color=fg,
            font=("Segoe UI Semibold", 12),
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            ff_overlay_realtime_row,
            text="Sincronizar Fila FF automaticamente",
            variable=ff_queue_enabled_var,
            command=lambda: schedule_ff_queue_poll(),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=1, column=0, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            ff_overlay_realtime_row,
            text="Sincronizar Overlay FF automaticamente",
            variable=ff_overlay_enabled_var,
            command=lambda: schedule_ff_overlay_sync(100),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=2, column=0, sticky="w", padx=(0, 12), pady=4)
        ff_overlay_actions = ctk.CTkFrame(ff_overlay_sync_card, fg_color=panel, corner_radius=0)
        ff_overlay_actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 18))

        ff_overlay_site_card = card(
            ff_overlay_controls,
            "Overlay OBS do site",
            "Carregue e salve a configuracao usada na URL /freefire/overlay do Jarvis.",
        )
        ff_overlay_site_card.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        ff_overlay_site_card.columnconfigure(1, weight=1)
        ff_overlay_site_card.columnconfigure(3, weight=1)
        section_label(ff_overlay_site_card, "Endpoint config", 2)
        entry(ff_overlay_site_card, ff_overlay_config_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
        section_label(ff_overlay_site_card, "Perfil", 3)
        entry(ff_overlay_site_card, ff_overlay_site_profile_var, width=150).grid(row=3, column=1, sticky="w", padx=18, pady=5)
        section_label(ff_overlay_site_card, "Nome do perfil", 3, column=2)
        entry(ff_overlay_site_card, ff_overlay_site_label_var).grid(row=3, column=3, sticky="ew", padx=18, pady=5)
        section_label(ff_overlay_site_card, "URL OBS", 4)
        entry(ff_overlay_site_card, ff_overlay_site_obs_url_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=5)

        ff_overlay_site_toggles = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel, corner_radius=0)
        ff_overlay_site_toggles.grid(row=5, column=0, columnspan=4, sticky="ew", padx=18, pady=(6, 6))
        for toggle_column in range(3):
            ff_overlay_site_toggles.columnconfigure(toggle_column, weight=1)
        for toggle_index, (text, var) in enumerate(
            (
                ("Rank geral", ff_overlay_site_enabled_general_var),
                ("Rank do dia", ff_overlay_site_enabled_daily_var),
                ("Fila FF", ff_overlay_site_enabled_queue_var),
                ("Fundo blocos", ff_overlay_site_panel_bg_var),
                ("Mostrar #", ff_overlay_site_rank_prefix_var),
                ("Medalhas", ff_overlay_site_medals_var),
            )
        ):
            ctk.CTkCheckBox(
                ff_overlay_site_toggles,
                text=text,
                variable=var,
                fg_color=accent,
                hover_color=accent_hover,
                border_color=border,
                text_color=fg,
            ).grid(row=toggle_index // 3, column=toggle_index % 3, sticky="w", padx=(0, 12), pady=4)

        section_label(ff_overlay_site_card, "Layout", 6)
        combo(ff_overlay_site_card, ff_overlay_site_layout_var, ["horizontal", "vertical", "grid"], width=150).grid(
            row=6, column=1, sticky="w", padx=18, pady=5
        )
        section_label(ff_overlay_site_card, "Fonte", 6, column=2)
        combo(ff_overlay_site_card, ff_overlay_site_font_var, ["impact", "bebas", "rajdhani", "inter", "mono"], width=150).grid(
            row=6, column=3, sticky="w", padx=18, pady=5
        )
        section_label(ff_overlay_site_card, "Animacao", 7)
        combo(ff_overlay_site_card, ff_overlay_site_animation_var, ["none", "fade", "slide", "pop"], width=150).grid(
            row=7, column=1, sticky="w", padx=18, pady=5
        )
        section_label(ff_overlay_site_card, "Refresh ms", 7, column=2)
        entry(ff_overlay_site_card, ff_overlay_site_refresh_var, width=110).grid(row=7, column=3, sticky="w", padx=18, pady=5)
        section_label(ff_overlay_site_card, "Troca seg.", 8)
        entry(ff_overlay_site_card, ff_overlay_site_switch_var, width=110).grid(row=8, column=1, sticky="w", padx=18, pady=5)
        section_label(ff_overlay_site_card, "Largura bloco", 8, column=2)
        entry(ff_overlay_site_card, ff_overlay_site_panel_width_var, width=110).grid(row=8, column=3, sticky="w", padx=18, pady=5)
        section_label(ff_overlay_site_card, "Limites", 9)
        ff_overlay_site_limits = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel, corner_radius=0)
        ff_overlay_site_limits.grid(row=9, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
        entry(ff_overlay_site_limits, ff_overlay_site_limit_general_var, width=70).pack(side=tk.LEFT)
        ctk.CTkLabel(ff_overlay_site_limits, text="geral", text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(6, 12))
        entry(ff_overlay_site_limits, ff_overlay_site_limit_daily_var, width=70).pack(side=tk.LEFT)
        ctk.CTkLabel(ff_overlay_site_limits, text="dia", text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(6, 12))
        entry(ff_overlay_site_limits, ff_overlay_site_limit_queue_var, width=70).pack(side=tk.LEFT)
        ctk.CTkLabel(ff_overlay_site_limits, text="fila", text_color=muted, font=("Segoe UI", 11)).pack(side=tk.LEFT, padx=(6, 12))

        ff_overlay_site_dimensions = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        ff_overlay_site_dimensions.grid(row=10, column=0, columnspan=4, sticky="ew", padx=18, pady=(8, 6))
        for dimension_column in range(6):
            ff_overlay_site_dimensions.columnconfigure(dimension_column, weight=1)
        ctk.CTkLabel(
            ff_overlay_site_dimensions,
            text="Tamanho e espaçamento",
            text_color=fg,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=0, column=0, columnspan=6, sticky="ew", padx=12, pady=(10, 2))
        for index, (label, var, width) in enumerate(
            (
                ("Gap", ff_overlay_site_gap_var, 70),
                ("Padding", ff_overlay_site_padding_var, 70),
                ("Título", ff_overlay_site_title_size_var, 70),
                ("Linha", ff_overlay_site_row_size_var, 70),
                ("Valor", ff_overlay_site_value_size_var, 70),
                ("Altura", ff_overlay_site_row_height_var, 70),
            )
        ):
            ctk.CTkLabel(ff_overlay_site_dimensions, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=1, column=index, sticky="w", padx=12, pady=(4, 0)
            )
            entry(ff_overlay_site_dimensions, var, width=width).grid(row=2, column=index, sticky="ew", padx=12, pady=(0, 10))

        ff_overlay_site_colors = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        ff_overlay_site_colors.grid(row=11, column=0, columnspan=4, sticky="ew", padx=18, pady=6)
        for color_column in range(6):
            ff_overlay_site_colors.columnconfigure(color_column, weight=1)
        ctk.CTkLabel(
            ff_overlay_site_colors,
            text="Fundo, linha e acento",
            text_color=fg,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=0, column=0, columnspan=6, sticky="ew", padx=12, pady=(10, 2))
        for index, (label, var, width) in enumerate(
            (
                ("Fundo", ff_overlay_site_panel_bg_color_var, 92),
                ("Opac.", ff_overlay_site_panel_bg_opacity_var, 70),
                ("Raio", ff_overlay_site_panel_radius_var, 70),
                ("Linha", ff_overlay_site_row_bg_color_var, 92),
                ("Opac.", ff_overlay_site_row_bg_opacity_var, 70),
                ("Acento", ff_overlay_site_accent_width_var, 70),
            )
        ):
            ctk.CTkLabel(ff_overlay_site_colors, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=1, column=index, sticky="w", padx=12, pady=(4, 0)
            )
            entry(ff_overlay_site_colors, var, width=width).grid(row=2, column=index, sticky="ew", padx=12, pady=(0, 10))

        ff_overlay_site_panels = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        ff_overlay_site_panels.grid(row=12, column=0, columnspan=4, sticky="ew", padx=18, pady=6)
        for panel_column in range(3):
            ff_overlay_site_panels.columnconfigure(panel_column, weight=1)
        ctk.CTkLabel(
            ff_overlay_site_panels,
            text="Títulos e cores por painel",
            text_color=fg,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", padx=12, pady=(10, 2))
        for column, (panel_key, panel_title) in enumerate((("general", "Geral"), ("daily", "Dia"), ("queue", "Fila"))):
            panel_box = ctk.CTkFrame(ff_overlay_site_panels, fg_color=field, corner_radius=10, border_width=1, border_color=border)
            panel_box.grid(row=1, column=column, sticky="nsew", padx=8, pady=(4, 12))
            panel_box.columnconfigure(1, weight=1)
            ctk.CTkLabel(panel_box, text=panel_title, text_color=fg, font=("Segoe UI Semibold", 12), anchor="w").grid(
                row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(8, 2)
            )
            for row_index, (label, field_key) in enumerate(
                (
                    ("Título", "title"),
                    ("Cor título", "title_color"),
                    ("Cor #", "rank_color"),
                    ("Cor nome", "name_color"),
                    ("Cor valor", "value_color"),
                    ("Cor acento", "accent_color"),
                ),
                start=1,
            ):
                ctk.CTkLabel(panel_box, text=label, text_color=muted, font=("Segoe UI", 10)).grid(
                    row=row_index, column=0, sticky="w", padx=(10, 6), pady=3
                )
                entry(panel_box, ff_overlay_site_panel_vars[panel_key][field_key], width=104).grid(
                    row=row_index, column=1, sticky="ew", padx=(0, 10), pady=3
                )
        ctk.CTkLabel(
            ff_overlay_site_card,
            textvariable=ff_overlay_site_status_var,
            text_color=accent,
            font=("Segoe UI Semibold", 12),
            anchor="w",
        ).grid(row=13, column=0, columnspan=4, sticky="ew", padx=18, pady=(6, 0))
        ff_overlay_site_actions = ctk.CTkFrame(ff_overlay_site_card, fg_color=panel, corner_radius=0)
        ff_overlay_site_actions.grid(row=14, column=0, columnspan=4, sticky="ew", padx=18, pady=(10, 18))

        ff_overlay_metrics = ctk.CTkFrame(
            ff_overlay_controls,
            fg_color=panel_alt,
            corner_radius=12,
            border_width=1,
            border_color=border,
        )
        ff_overlay_metrics.grid(row=2, column=0, sticky="ew", padx=12, pady=8)
        for column in range(3):
            ff_overlay_metrics.columnconfigure(column, weight=1)
        for col, (label, value_var) in enumerate(
            (
                ("Jogadores", manual_count_var),
                ("Kills", manual_total_var),
                ("Fila ativa", ff_queue_count_var),
            )
        ):
            ctk.CTkLabel(ff_overlay_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=col, sticky="w", padx=16, pady=(12, 0)
            )
            ctk.CTkLabel(ff_overlay_metrics, textvariable=value_var, text_color=teal, font=("Segoe UI Semibold", 24)).grid(
                row=1, column=col, sticky="w", padx=16, pady=(0, 12)
            )
        ff_overlay_options = card(ff_overlay_controls, "Aparencia do overlay", "Controle a janela que fica sobre o jogo ou OBS.")
        ff_overlay_options.grid(row=3, column=0, sticky="ew", padx=12, pady=8)
        ff_overlay_options.columnconfigure(1, weight=1)
        ctk.CTkLabel(ff_overlay_options, text="Opacidade", text_color=muted, font=("Segoe UI", 11)).grid(
            row=2, column=0, sticky="w", padx=18, pady=(10, 4)
        )
        ff_overlay_opacity_slider = ctk.CTkSlider(
            ff_overlay_options,
            from_=35,
            to=100,
            number_of_steps=65,
            variable=ff_overlay_opacity_var,
            command=lambda _value: apply_ff_overlay_settings(refresh=True),
        )
        ff_overlay_opacity_slider.grid(row=2, column=1, sticky="ew", padx=8, pady=(10, 4))
        ctk.CTkLabel(ff_overlay_options, textvariable=ff_overlay_opacity_text, text_color=muted, font=("Segoe UI", 11)).grid(
            row=2, column=2, sticky="e", padx=(8, 18), pady=(10, 4)
        )
        ctk.CTkLabel(ff_overlay_options, text="Largura", text_color=muted, font=("Segoe UI", 11)).grid(
            row=3, column=0, sticky="w", padx=18, pady=4
        )
        ff_overlay_width_slider = ctk.CTkSlider(
            ff_overlay_options,
            from_=420,
            to=1400,
            number_of_steps=98,
            variable=ff_overlay_width_var,
            command=lambda _value: apply_ff_overlay_settings(refresh=True),
        )
        ff_overlay_width_slider.grid(row=3, column=1, sticky="ew", padx=8, pady=4)
        ctk.CTkLabel(ff_overlay_options, textvariable=ff_overlay_size_text, text_color=fg, font=("Segoe UI Semibold", 11)).grid(
            row=3, column=2, sticky="e", padx=(8, 18), pady=4
        )
        ctk.CTkLabel(ff_overlay_options, text="Altura", text_color=muted, font=("Segoe UI", 11)).grid(
            row=4, column=0, sticky="w", padx=18, pady=4
        )
        ff_overlay_height_slider = ctk.CTkSlider(
            ff_overlay_options,
            from_=240,
            to=900,
            number_of_steps=66,
            variable=ff_overlay_height_var,
            command=lambda _value: apply_ff_overlay_settings(refresh=True),
        )
        ff_overlay_height_slider.grid(row=4, column=1, sticky="ew", padx=8, pady=4)
        ff_overlay_toggle_row = ctk.CTkFrame(ff_overlay_options, fg_color=panel, corner_radius=0)
        ff_overlay_toggle_row.grid(row=5, column=0, columnspan=3, sticky="ew", padx=18, pady=(8, 18))
        for col in range(3):
            ff_overlay_toggle_row.columnconfigure(col, weight=1)
        ctk.CTkCheckBox(
            ff_overlay_toggle_row,
            text="Mostrar Kills FF",
            variable=ff_overlay_show_kills_var,
            command=lambda: refresh_ff_overlay(force=True),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            ff_overlay_toggle_row,
            text="Mostrar Fila FF",
            variable=ff_overlay_show_queue_var,
            command=lambda: refresh_ff_overlay(force=True),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            ff_overlay_toggle_row,
            text="Compacto",
            variable=ff_overlay_compact_var,
            command=lambda: refresh_ff_overlay(force=True),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=2, sticky="w", padx=(0, 12), pady=4)

        ff_overlay_preview_card = card(ff_overlay_tab, "Preview Overlay FF", "Visual que sera usado na janela de overlay.")
        ff_overlay_preview_card.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=(12, 12))
        ff_overlay_preview_card.columnconfigure(0, weight=1)
        ff_overlay_preview_card.rowconfigure(2, weight=1)
        ff_overlay_preview_frame = ctk.CTkFrame(
            ff_overlay_preview_card,
            fg_color="#050609",
            corner_radius=14,
            border_width=1,
            border_color=accent,
        )
        ff_overlay_preview_frame.grid(row=2, column=0, sticky="nsew", padx=18, pady=(8, 18))
        ff_overlay_preview_frame.columnconfigure(0, weight=1)

    if not chat_tab_hidden:
        chat_connection_card = card(
            live_chat_tab,
            "Chat ao vivo por eventos",
            "Receba mensagens do TikFinity sem depender de navegador aberto ou raspagem de tela.",
        )
        chat_connection_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        chat_connection_card.columnconfigure(1, weight=1)
        chat_connection_card.columnconfigure(3, weight=1)
        section_label(chat_connection_card, "Fonte", 2)
        chat_source_combo = combo(chat_connection_card, chat_source_var, ["Webhook local", "TikFinity WebSocket"], width=190)
        chat_source_combo.grid(row=2, column=1, sticky="w", padx=18, pady=5)
        chat_source_combo.configure(command=lambda _value: update_chat_endpoint_text())
        section_label(chat_connection_card, "Host", 2, column=2)
        entry(chat_connection_card, chat_webhook_host_var, width=140).grid(row=2, column=3, sticky="w", padx=18, pady=5)
        section_label(chat_connection_card, "Porta", 3)
        entry(chat_connection_card, chat_webhook_port_var, width=100).grid(row=3, column=1, sticky="w", padx=18, pady=5)
        section_label(chat_connection_card, "Token secreto", 3, column=2)
        entry(chat_connection_card, chat_webhook_token_var).grid(row=3, column=3, sticky="ew", padx=18, pady=5)
        section_label(chat_connection_card, "URL WebSocket", 4)
        entry(chat_connection_card, chat_websocket_url_var).grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=5)

        endpoint_box = ctk.CTkFrame(chat_connection_card, fg_color=field, corner_radius=10, border_width=1, border_color=border)
        endpoint_box.grid(row=5, column=0, columnspan=4, sticky="ew", padx=18, pady=(10, 8))
        endpoint_box.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            endpoint_box,
            textvariable=chat_endpoint_var,
            text_color=muted,
            font=("Consolas", 10),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=12, pady=10)
        chat_actions = ctk.CTkFrame(chat_connection_card, fg_color=panel, corner_radius=0)
        chat_actions.grid(row=6, column=0, columnspan=4, sticky="ew", padx=18, pady=(8, 18))

        chat_metrics = ctk.CTkFrame(live_chat_tab, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        chat_metrics.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        for column in range(4):
            chat_metrics.columnconfigure(column, weight=1)
        for col, label in enumerate(("Mensagens", "Usuários", "Plataforma", "Status")):
            ctk.CTkLabel(chat_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=col, sticky="w", padx=18, pady=(14, 0)
            )
        ctk.CTkLabel(chat_metrics, textvariable=chat_message_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(chat_metrics, textvariable=chat_user_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=1, sticky="w", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(chat_metrics, textvariable=chat_platform_var, text_color=accent, font=("Segoe UI Semibold", 14)).grid(
            row=1, column=2, sticky="w", padx=18, pady=(4, 14)
        )
        ctk.CTkLabel(chat_metrics, textvariable=chat_status_var, text_color=accent, font=("Segoe UI Semibold", 14)).grid(
            row=1, column=3, sticky="w", padx=18, pady=(4, 14)
        )

        chat_overlay_card = card(
            live_chat_tab,
            "Overlay para jogo",
            "Janela transparente, sempre no topo, para acompanhar o chat usando apenas um monitor.",
        )
        chat_overlay_card.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 8))
        chat_overlay_card.columnconfigure(1, weight=1)
        chat_overlay_card.columnconfigure(4, weight=1)

        ctk.CTkLabel(chat_overlay_card, text="Opacidade", text_color=muted, font=("Segoe UI", 11)).grid(
            row=2, column=0, sticky="w", padx=18, pady=(8, 4)
        )
        chat_overlay_opacity_slider = ctk.CTkSlider(
            chat_overlay_card,
            from_=35,
            to=100,
            number_of_steps=65,
            variable=chat_overlay_opacity_var,
            command=lambda _value: apply_chat_overlay_settings(),
        )
        chat_overlay_opacity_slider.grid(row=2, column=1, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            chat_overlay_card,
            textvariable=chat_overlay_opacity_text,
            text_color=fg,
            font=("Segoe UI Semibold", 11),
            width=52,
        ).grid(row=2, column=2, sticky="e", padx=(0, 18), pady=(8, 4))

        ctk.CTkLabel(chat_overlay_card, text="Fonte", text_color=muted, font=("Segoe UI", 11)).grid(
            row=2, column=3, sticky="w", padx=18, pady=(8, 4)
        )
        chat_overlay_font_slider = ctk.CTkSlider(
            chat_overlay_card,
            from_=10,
            to=24,
            number_of_steps=14,
            variable=chat_overlay_font_size_var,
            command=lambda _value: apply_chat_overlay_settings(refresh=True),
        )
        chat_overlay_font_slider.grid(row=2, column=4, sticky="ew", padx=8, pady=(8, 4))
        ctk.CTkLabel(
            chat_overlay_card,
            textvariable=chat_overlay_font_size_text,
            text_color=fg,
            font=("Segoe UI Semibold", 11),
            width=52,
        ).grid(row=2, column=5, sticky="e", padx=(0, 18), pady=(8, 4))

        overlay_option_row = ctk.CTkFrame(chat_overlay_card, fg_color=panel, corner_radius=0)
        overlay_option_row.grid(row=3, column=0, columnspan=6, sticky="ew", padx=18, pady=(8, 4))
        for col in range(3):
            overlay_option_row.columnconfigure(col, weight=1)
        ctk.CTkCheckBox(
            overlay_option_row,
            text="Modo compacto",
            variable=chat_overlay_compact_var,
            command=lambda: apply_chat_overlay_settings(refresh=True),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            overlay_option_row,
            text="Mostrar controles",
            variable=chat_overlay_controls_var,
            command=lambda: apply_chat_overlay_settings(),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=1, sticky="w", padx=(0, 12), pady=4)
        ctk.CTkCheckBox(
            overlay_option_row,
            text="Click-through",
            variable=chat_overlay_clickthrough_var,
            command=lambda: apply_chat_overlay_settings(),
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=2, sticky="w", pady=4)

        overlay_actions = ctk.CTkFrame(chat_overlay_card, fg_color=panel, corner_radius=0)
        overlay_actions.grid(row=4, column=0, columnspan=6, sticky="ew", padx=18, pady=(6, 18))
        button(overlay_actions, "Abrir overlay", lambda: open_chat_overlay_window(), "accent", width=120).pack(side=tk.LEFT, padx=(0, 8))
        button(overlay_actions, "Aplicar ajustes", lambda: apply_chat_overlay_settings(refresh=True), "default", width=120).pack(side=tk.LEFT, padx=(0, 8))
        button(overlay_actions, "Mensagem teste", lambda: add_chat_test_message(), "default", width=128).pack(side=tk.LEFT, padx=(0, 8))
        button(overlay_actions, "Fechar overlay", lambda: close_chat_overlay(), "danger", width=112).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkLabel(
            overlay_actions,
            text="Use click-through só depois de posicionar o overlay.",
            text_color=muted,
            font=("Segoe UI", 10),
        ).pack(side=tk.LEFT, padx=(8, 0))

        chat_list_card = card(live_chat_tab, "Tela de chat", "Acompanhe as mensagens da live em tempo real com avatar, plataforma e filtro.")
        chat_list_card.grid(row=3, column=0, sticky="nsew", padx=12, pady=(8, 12))
        chat_list_card.columnconfigure(0, weight=1)
        chat_list_card.rowconfigure(3, weight=1)
        chat_filter_row = ctk.CTkFrame(chat_list_card, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
        chat_filter_row.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(4, 8))
        chat_filter_row.columnconfigure(1, weight=1)
        ctk.CTkLabel(chat_filter_row, text="Filtro", text_color=muted, font=("Segoe UI", 12)).grid(
            row=0, column=0, sticky="w", padx=(0, 10), pady=4
        )
        entry(chat_filter_row, chat_filter_var).grid(row=0, column=1, sticky="ew", pady=4)
        chat_messages_frame = ctk.CTkScrollableFrame(
            chat_list_card,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        chat_messages_frame.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=18, pady=(0, 18))
        chat_messages_frame.columnconfigure(0, weight=1)

    commands_settings_col = ctk.CTkFrame(commands_tab, fg_color=bg, corner_radius=0)
    commands_settings_col.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=12)
    commands_settings_col.columnconfigure(0, weight=1)
    commands_settings_col.rowconfigure(2, weight=1)
    commands_list_col = ctk.CTkFrame(commands_tab, fg_color=bg, corner_radius=0)
    commands_list_col.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=12)
    commands_list_col.columnconfigure(0, weight=1)
    commands_list_col.rowconfigure(0, weight=1)

    command_bot_card = card(
        commands_settings_col,
        "Bot de comandos",
        "Detecta comandos no chat lido pelo TikFinity e responde com delay seguro.",
    )
    command_bot_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    command_bot_card.columnconfigure(1, weight=1)
    command_bot_card.columnconfigure(3, weight=1)
    ctk.CTkCheckBox(
        command_bot_card,
        text="Ativar respostas automaticas",
        variable=chat_commands_enabled_var,
        fg_color=accent,
        hover_color=accent_hover,
        border_color=border,
        text_color=fg,
    ).grid(row=2, column=0, columnspan=4, sticky="w", padx=18, pady=(6, 8))
    section_label(command_bot_card, "Metodo", 3)
    combo(command_bot_card, bot_delivery_method_var, BOT_DELIVERY_METHOD_OPTIONS, width=230).grid(
        row=3, column=1, sticky="w", padx=18, pady=5
    )
    section_label(command_bot_card, "Delay seguro", 3, column=2)
    entry(command_bot_card, bot_safe_delay_var, width=90).grid(row=3, column=3, sticky="w", padx=18, pady=5)
    section_label(command_bot_card, "Cooldown padrao", 4)
    entry(command_bot_card, bot_default_cooldown_var, width=90).grid(row=4, column=1, sticky="w", padx=18, pady=5)
    section_label(command_bot_card, "Ignorar usuarios", 4, column=2)
    entry(command_bot_card, bot_ignore_usernames_var).grid(row=4, column=3, sticky="ew", padx=18, pady=5)

    streamerbot_card = card(
        commands_settings_col,
        "Envio para TikFinity",
        "O modo direto abre uma ponte local. HTTP, senha e action ficam so para Streamer.bot legado.",
    )
    streamerbot_card.grid(row=1, column=0, sticky="ew", pady=8)
    streamerbot_card.columnconfigure(1, weight=1)
    section_label(streamerbot_card, "Ponte WS", 2)
    entry(streamerbot_card, bot_streamerbot_ws_url_var).grid(row=2, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(streamerbot_card, "HTTP", 3)
    entry(streamerbot_card, bot_streamerbot_http_url_var).grid(row=3, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(streamerbot_card, "Senha WS", 4)
    entry(streamerbot_card, bot_streamerbot_password_var, show="*").grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(streamerbot_card, "Action nome", 5)
    entry(streamerbot_card, bot_streamerbot_action_name_var).grid(row=5, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    section_label(streamerbot_card, "Action ID", 6)
    entry(streamerbot_card, bot_streamerbot_action_id_var).grid(row=6, column=1, columnspan=3, sticky="ew", padx=18, pady=5)
    streamerbot_actions = ctk.CTkFrame(streamerbot_card, fg_color=panel, corner_radius=0)
    streamerbot_actions.grid(row=7, column=0, columnspan=4, sticky="ew", padx=18, pady=(8, 18))
    button(streamerbot_actions, "Testar envio", lambda: test_bot_send(), "accent", width=120).pack(side=tk.LEFT, padx=(0, 8))
    button(streamerbot_actions, "Salvar", lambda: save_form(), "ghost", width=86).pack(side=tk.LEFT, padx=(0, 8))

    bot_status_card = ctk.CTkFrame(
        commands_settings_col,
        fg_color=panel_alt,
        corner_radius=12,
        border_width=1,
        border_color=border,
    )
    bot_status_card.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
    for column in range(3):
        bot_status_card.columnconfigure(column, weight=1)
    for col, label in enumerate(("Fila", "Ultimo envio", "Status")):
        ctk.CTkLabel(bot_status_card, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=18, pady=(16, 0)
        )
    ctk.CTkLabel(bot_status_card, textvariable=bot_queue_count_var, text_color=teal, font=("Segoe UI Semibold", 24)).grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 16)
    )
    ctk.CTkLabel(bot_status_card, textvariable=bot_last_sent_var, text_color=fg, font=("Segoe UI Semibold", 12)).grid(
        row=1, column=1, sticky="w", padx=18, pady=(4, 16)
    )
    ctk.CTkLabel(bot_status_card, textvariable=bot_status_var, text_color=accent, font=("Segoe UI Semibold", 12)).grid(
        row=1, column=2, sticky="w", padx=18, pady=(4, 16)
    )

    commands_card = card(
        commands_list_col,
        "Comandos personalizados",
        "Use variaveis como {user}, {args}, {command}, {platform} e {time}.",
    )
    commands_card.grid(row=0, column=0, sticky="nsew")
    commands_card.columnconfigure(0, weight=1)
    commands_card.rowconfigure(3, weight=1)
    commands_header = ctk.CTkFrame(commands_card, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
    commands_header.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 0))
    commands_header.columnconfigure(1, weight=1)
    commands_header.columnconfigure(2, weight=4)
    ctk.CTkLabel(commands_header, text="On", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=0, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(commands_header, text="Comando", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=1, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(commands_header, text="Resposta", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=2, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(commands_header, text="Cooldown", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=3, sticky="w", padx=10, pady=9
    )
    commands_table_frame = ctk.CTkScrollableFrame(
        commands_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color=border,
        scrollbar_button_hover_color=accent,
    )
    commands_table_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
    commands_table_frame.columnconfigure(0, weight=1)
    commands_actions = ctk.CTkFrame(commands_card, fg_color=panel, corner_radius=0)
    commands_actions.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
    button(commands_actions, "Adicionar comando", lambda: add_custom_command_row(), "accent", width=150).pack(side=tk.LEFT, padx=(0, 8))
    button(commands_actions, "Exemplo", lambda: add_custom_command_row("!pix", "Pix do Aizen: coloque sua chave aqui, {user}.", 45, True), "default", width=96).pack(side=tk.LEFT, padx=(0, 8))
    button(commands_actions, "Salvar", lambda: save_form(), "ghost", width=86).pack(side=tk.LEFT, padx=(0, 8))

    timers_settings_col = ctk.CTkFrame(timers_tab, fg_color=bg, corner_radius=0)
    timers_settings_col.grid(row=0, column=0, sticky="nsew", padx=(12, 8), pady=12)
    timers_settings_col.columnconfigure(0, weight=1)
    timers_settings_col.rowconfigure(2, weight=1)
    timers_list_col = ctk.CTkFrame(timers_tab, fg_color=bg, corner_radius=0)
    timers_list_col.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=12)
    timers_list_col.columnconfigure(0, weight=1)
    timers_list_col.rowconfigure(0, weight=1)

    timer_bot_card = card(
        timers_settings_col,
        "Temporizador do bot",
        "Envia mensagens automaticas em intervalos, usando a mesma action configurada na aba Comandos.",
    )
    timer_bot_card.grid(row=0, column=0, sticky="ew", pady=(0, 8))
    timer_bot_card.columnconfigure(1, weight=1)
    ctk.CTkCheckBox(
        timer_bot_card,
        text="Ativar temporizadores",
        variable=chat_timers_enabled_var,
        fg_color=accent,
        hover_color=accent_hover,
        border_color=border,
        text_color=fg,
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(6, 8))
    section_label(timer_bot_card, "Intervalo padrao", 3)
    entry(timer_bot_card, bot_default_timer_interval_var, width=100).grid(row=3, column=1, sticky="w", padx=18, pady=5)
    section_label(timer_bot_card, "Min. mensagens", 4)
    entry(timer_bot_card, bot_default_timer_min_messages_var, width=100).grid(row=4, column=1, sticky="w", padx=18, pady=5)
    ctk.CTkLabel(
        timer_bot_card,
        text="Use 300 a 600 segundos para mensagens recorrentes. O delay seguro global continua valendo.",
        text_color=muted,
        font=("Segoe UI", 11),
        wraplength=320,
        justify="left",
    ).grid(row=5, column=0, columnspan=2, sticky="w", padx=18, pady=(6, 18))

    timer_status_card = ctk.CTkFrame(
        timers_settings_col,
        fg_color=panel_alt,
        corner_radius=12,
        border_width=1,
        border_color=border,
    )
    timer_status_card.grid(row=1, column=0, sticky="ew", pady=8)
    for column in range(3):
        timer_status_card.columnconfigure(column, weight=1)
    for col, label in enumerate(("Ativos", "Proximo", "Status")):
        ctk.CTkLabel(timer_status_card, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=18, pady=(16, 0)
        )
    ctk.CTkLabel(timer_status_card, textvariable=timer_active_count_var, text_color=teal, font=("Segoe UI Semibold", 24)).grid(
        row=1, column=0, sticky="w", padx=18, pady=(0, 16)
    )
    ctk.CTkLabel(timer_status_card, textvariable=timer_next_send_var, text_color=fg, font=("Segoe UI Semibold", 12)).grid(
        row=1, column=1, sticky="w", padx=18, pady=(4, 16)
    )
    ctk.CTkLabel(timer_status_card, textvariable=timer_status_var, text_color=accent, font=("Segoe UI Semibold", 12)).grid(
        row=1, column=2, sticky="w", padx=18, pady=(4, 16)
    )

    timer_help_card = card(
        timers_settings_col,
        "Boas praticas",
        "Crie mensagens curtas para Discord, LivePix, regras e redes sociais. Evite intervalos agressivos.",
    )
    timer_help_card.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
    ctk.CTkLabel(
        timer_help_card,
        text=(
            "O campo Min. mensagens define quantas mensagens novas precisam aparecer no chat desde o ultimo disparo. "
            "Com 0, o timer dispara mesmo sem movimento no chat."
        ),
        text_color=muted,
        font=("Segoe UI", 12),
        wraplength=340,
        justify="left",
    ).grid(row=2, column=0, columnspan=4, sticky="new", padx=18, pady=(0, 18))

    timers_card = card(
        timers_list_col,
        "Mensagens automaticas",
        "Configure uma ou mais mensagens recorrentes, com intervalo e regra de atividade independentes.",
    )
    timers_card.grid(row=0, column=0, sticky="nsew")
    timers_card.columnconfigure(0, weight=1)
    timers_card.rowconfigure(3, weight=1)
    timers_header = ctk.CTkFrame(timers_card, fg_color=table_header_bg, corner_radius=10, border_width=1, border_color=border)
    timers_header.grid(row=2, column=0, sticky="ew", padx=18, pady=(4, 0))
    timers_header.columnconfigure(1, weight=1)
    timers_header.columnconfigure(2, weight=4)
    ctk.CTkLabel(timers_header, text="On", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=0, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(timers_header, text="Nome", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=1, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(timers_header, text="Mensagem", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=2, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(timers_header, text="Intervalo", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=3, sticky="w", padx=10, pady=9
    )
    ctk.CTkLabel(timers_header, text="Min. chat", text_color=muted, font=("Segoe UI Semibold", 11)).grid(
        row=0, column=4, sticky="w", padx=10, pady=9
    )
    timers_table_frame = ctk.CTkScrollableFrame(
        timers_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color=border,
        scrollbar_button_hover_color=accent,
    )
    timers_table_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 12))
    timers_table_frame.columnconfigure(0, weight=1)
    timers_actions = ctk.CTkFrame(timers_card, fg_color=panel, corner_radius=0)
    timers_actions.grid(row=4, column=0, sticky="ew", padx=18, pady=(0, 18))
    button(timers_actions, "Adicionar timer", lambda: add_chat_timer_row(), "accent", width=140).pack(side=tk.LEFT, padx=(0, 8))
    button(
        timers_actions,
        "Exemplo",
        lambda: add_chat_timer_row("Discord", "Entre no Discord do Aizen: coloque seu convite aqui.", 600, 6, True),
        "default",
        width=96,
    ).pack(side=tk.LEFT, padx=(0, 8))
    button(timers_actions, "Salvar", lambda: save_form(), "ghost", width=86).pack(side=tk.LEFT, padx=(0, 8))

    raffle_left = ctk.CTkScrollableFrame(
        raffle_body,
        fg_color=bg,
        corner_radius=0,
        scrollbar_button_color=chip_bg,
        scrollbar_button_hover_color=accent,
    )
    raffle_left.grid(row=0, column=0, sticky="nsew", padx=(0, 4), pady=0)
    raffle_left.columnconfigure(0, weight=1)
    raffle_left.rowconfigure(1, weight=1)

    raffle_controls = card(raffle_left, "Configurar sorteio", "Use eventos do app para entrar participantes automaticamente pelo comando ativo.")
    raffle_controls.grid(row=0, column=0, sticky="new", padx=12, pady=(12, 8))
    section_label(raffle_controls, "Fonte do sorteio", 2)
    combo(raffle_controls, raffle_source_mode_var, ["Eventos do app", "URL do chat (legado)"], width=210).grid(
        row=2, column=1, sticky="w", padx=18, pady=5
    )
    section_label(raffle_controls, "URL do chat legado", 3)
    entry(raffle_controls, tikfinity_url_var).grid(row=3, column=1, sticky="ew", padx=18, pady=5)
    section_label(raffle_controls, "Comando", 4)
    entry(raffle_controls, raffle_command_var, width=160).grid(row=4, column=1, sticky="w", padx=18, pady=5)
    section_label(raffle_controls, "Minutos", 5)
    entry(raffle_controls, raffle_minutes_var, width=92).grid(row=5, column=1, sticky="w", padx=18, pady=5)
    section_label(raffle_controls, "Entradas por tipo", 6)
    raffle_entries_row = ctk.CTkFrame(raffle_controls, fg_color=panel, corner_radius=0)
    raffle_entries_row.grid(row=6, column=1, sticky="ew", padx=18, pady=5)
    for column in range(10):
        raffle_entries_row.columnconfigure(column, weight=1 if column in {1, 3, 5, 7, 9} else 0)
    ctk.CTkLabel(raffle_entries_row, text="Normal", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=0, sticky="w", padx=(0, 6)
    )
    entry(raffle_entries_row, raffle_entries_normal_var, width=54).grid(row=0, column=1, sticky="w", padx=(0, 12))
    ctk.CTkLabel(raffle_entries_row, text="Fã", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=2, sticky="w", padx=(0, 6)
    )
    entry(raffle_entries_row, raffle_entries_fan_var, width=54).grid(row=0, column=3, sticky="w", padx=(0, 12))
    ctk.CTkLabel(raffle_entries_row, text="Super fã", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=4, sticky="w", padx=(0, 6)
    )
    entry(raffle_entries_row, raffle_entries_super_fan_var, width=54).grid(row=0, column=5, sticky="w", padx=(0, 12))
    ctk.CTkLabel(raffle_entries_row, text="Gift", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=6, sticky="w", padx=(0, 6)
    )
    entry(raffle_entries_row, raffle_entries_gift_var, width=54).grid(row=0, column=7, sticky="w", padx=(0, 12))
    ctk.CTkLabel(raffle_entries_row, text="Sub", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=8, sticky="w", padx=(0, 6)
    )
    entry(raffle_entries_row, raffle_entries_sub_var, width=54).grid(row=0, column=9, sticky="w")

    section_label(raffle_controls, "Anti-fraude", 7)
    anti_fraud_row = ctk.CTkFrame(raffle_controls, fg_color=panel, corner_radius=0)
    anti_fraud_row.grid(row=7, column=1, sticky="ew", padx=18, pady=5)
    anti_fraud_row.columnconfigure(1, weight=1)
    ctk.CTkLabel(anti_fraud_row, text="Cooldown", text_color=muted, font=("Segoe UI", 11)).grid(
        row=0, column=0, sticky="w", padx=(0, 6)
    )
    entry(anti_fraud_row, raffle_cooldown_var, width=64).grid(row=0, column=1, sticky="w", padx=(0, 14))
    ctk.CTkCheckBox(
        anti_fraud_row,
        text="Incluir moderador",
        variable=raffle_include_moderators_var,
        fg_color=accent,
        hover_color=accent_hover,
        text_color=fg,
    ).grid(row=0, column=2, sticky="w")

    metrics = ctk.CTkFrame(raffle_controls, fg_color=field, corner_radius=12, border_width=1, border_color=border)
    metrics.grid(row=8, column=0, columnspan=2, sticky="ew", padx=18, pady=(14, 8))
    metrics.columnconfigure(0, weight=1)
    metrics.columnconfigure(1, weight=1)
    metrics.columnconfigure(2, weight=1)
    metrics.columnconfigure(3, weight=1)
    for col, label in enumerate(("Tempo", "Participantes", "Entradas", "Estado")):
        ctk.CTkLabel(metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(row=0, column=col, sticky="w", padx=14, pady=(12, 0))
    ctk.CTkLabel(metrics, textvariable=raffle_timer_var, text_color=teal, font=("Segoe UI Semibold", 25)).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 14))
    ctk.CTkLabel(metrics, textvariable=raffle_count_var, text_color=teal, font=("Segoe UI Semibold", 25)).grid(row=1, column=1, sticky="w", padx=14, pady=(0, 14))
    ctk.CTkLabel(metrics, textvariable=raffle_entries_var, text_color=teal, font=("Segoe UI Semibold", 25)).grid(row=1, column=2, sticky="w", padx=14, pady=(0, 14))
    ctk.CTkLabel(metrics, textvariable=raffle_state_var, text_color=accent, font=("Segoe UI Semibold", 14)).grid(row=1, column=3, sticky="w", padx=14, pady=(4, 14))

    raffle_buttons = ctk.CTkFrame(raffle_controls, fg_color=panel, corner_radius=0)
    raffle_buttons.grid(row=9, column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 18))

    layout_controls = ctk.CTkFrame(raffle_controls, fg_color=field, corner_radius=12, border_width=1, border_color=border)
    layout_controls.grid(row=10, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 18))
    layout_controls.columnconfigure(1, weight=1)
    layout_controls.columnconfigure(3, weight=1)
    ctk.CTkLabel(
        layout_controls,
        text="Personalizar janelas",
        text_color=fg,
        font=("Segoe UI Semibold", 13),
    ).grid(row=0, column=0, columnspan=4, sticky="w", padx=14, pady=(12, 4))

    queue_size_label = ctk.CTkLabel(layout_controls, textvariable=queue_size_text, text_color=muted, font=("Segoe UI", 11))
    event_size_label = ctk.CTkLabel(layout_controls, textvariable=event_size_text, text_color=muted, font=("Segoe UI", 11))
    winner_size_label = ctk.CTkLabel(layout_controls, textvariable=winner_size_text, text_color=muted, font=("Segoe UI", 11))
    font_size_label = ctk.CTkLabel(layout_controls, textvariable=font_size_text, text_color=muted, font=("Segoe UI", 11))

    ctk.CTkLabel(layout_controls, text="Fila", text_color=muted, font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", padx=14, pady=4)
    ctk.CTkLabel(layout_controls, text="Eventos", text_color=muted, font=("Segoe UI", 11)).grid(row=2, column=0, sticky="w", padx=14, pady=4)
    ctk.CTkLabel(layout_controls, text="Vencedor", text_color=muted, font=("Segoe UI", 11)).grid(row=1, column=2, sticky="w", padx=(14, 8), pady=4)
    ctk.CTkLabel(layout_controls, text="Fonte", text_color=muted, font=("Segoe UI", 11)).grid(row=2, column=2, sticky="w", padx=(14, 8), pady=4)

    queue_slider = ctk.CTkSlider(layout_controls, from_=240, to=900, number_of_steps=66, variable=participants_height_var)
    event_slider = ctk.CTkSlider(layout_controls, from_=90, to=360, number_of_steps=27, variable=events_height_var)
    winner_slider = ctk.CTkSlider(layout_controls, from_=260, to=520, number_of_steps=26, variable=winner_width_var)
    font_slider = ctk.CTkSlider(layout_controls, from_=10, to=20, number_of_steps=10, variable=raffle_font_size_var)
    queue_slider.grid(row=1, column=1, sticky="ew", padx=8, pady=4)
    event_slider.grid(row=2, column=1, sticky="ew", padx=8, pady=(4, 14))
    winner_slider.grid(row=1, column=3, sticky="ew", padx=8, pady=4)
    font_slider.grid(row=2, column=3, sticky="ew", padx=8, pady=(4, 14))
    queue_size_label.grid(row=1, column=4, sticky="e", padx=(4, 14), pady=4)
    event_size_label.grid(row=2, column=4, sticky="e", padx=(4, 14), pady=(4, 14))
    winner_size_label.grid(row=1, column=5, sticky="e", padx=(4, 14), pady=4)
    font_size_label.grid(row=2, column=5, sticky="e", padx=(4, 14), pady=(4, 14))
    layout_controls.grid_remove()

    winner_card = ctk.CTkFrame(
        raffle_left,
        fg_color=panel_alt,
        corner_radius=12,
        border_width=1,
        border_color=border,
    )
    winner_card.grid(row=1, column=0, sticky="nsew", padx=12, pady=(8, 12))
    winner_card.columnconfigure(0, weight=1)
    winner_card.rowconfigure(5, weight=1)
    ctk.CTkLabel(winner_card, text="VENCEDOR", text_color=muted, font=("Segoe UI Semibold", 12)).grid(row=0, column=0, sticky="w", padx=24, pady=(24, 0))
    wheel_canvas = tk.Canvas(
        winner_card,
        height=138,
        bg=panel_alt,
        highlightthickness=0,
        bd=0,
    )
    wheel_canvas.grid(row=1, column=0, sticky="ew", padx=18, pady=(14, 0))
    winner_avatar_label = make_avatar_label(winner_card, "-", "", size=92)
    winner_avatar_label.grid(row=2, column=0, sticky="n", padx=24, pady=(18, 8))
    winner_label = ctk.CTkLabel(
        winner_card,
        textvariable=raffle_winner_var,
        text_color=accent,
        font=("Segoe UI Semibold", 34),
        wraplength=430,
        justify="center",
    )
    winner_label.grid(row=3, column=0, sticky="ew", padx=24, pady=(0, 12))
    ctk.CTkLabel(
        winner_card,
        text="Após o sorteio, só as mensagens do vencedor aparecem abaixo.",
        text_color=muted,
        font=("Segoe UI", 11),
        wraplength=430,
    ).grid(row=4, column=0, sticky="ew", padx=24, pady=(0, 12))
    winner_messages_text = ctk.CTkTextbox(
        winner_card,
        height=130,
        wrap="word",
        fg_color=field,
        text_color=fg,
        border_width=1,
        border_color=border,
        corner_radius=10,
        font=("Segoe UI", 11),
    )
    winner_messages_text.grid(row=5, column=0, sticky="nsew", padx=24, pady=(0, 24))
    winner_messages_text.insert("end", "As mensagens do vencedor aparecerão aqui.\n")
    winner_messages_text.configure(state="disabled")

    participant_card = card(raffle_body, "Fila do sorteio", "Participantes únicos capturados pelo comando ativo.")
    participant_card.grid(row=0, column=1, sticky="nsew", padx=(8, 12), pady=(12, 12))
    participant_card.rowconfigure(2, weight=1)
    participant_card.columnconfigure(0, weight=1)
    participants_frame = ctk.CTkScrollableFrame(
        participant_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color="#3a1518",
        scrollbar_button_hover_color="#5a1d22",
    )
    participants_frame.grid(row=2, column=0, columnspan=4, sticky="nsew", padx=18, pady=(8, 18))
    participants_frame.columnconfigure(0, weight=1)

    log_card = ctk.CTkFrame(events_tab, fg_color=panel, corner_radius=12, border_width=1, border_color=border)
    log_card.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
    log_card.columnconfigure(0, weight=1)
    log_card.rowconfigure(1, weight=1)
    ctk.CTkLabel(
        log_card,
        text="Logs",
        text_color=fg,
        font=("Segoe UI Semibold", 16),
    ).grid(row=0, column=0, sticky="w", padx=18, pady=(16, 6))
    log_text = ctk.CTkTextbox(
        log_card,
        height=280,
        wrap="word",
        fg_color=field,
        text_color=fg,
        border_width=1,
        border_color=border,
        corner_radius=10,
        font=("Consolas", 9),
    )
    log_text.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
    log_text.configure(state="disabled")

    def layout_value(var: tk.IntVar, min_value: int, max_value: int) -> int:
        return max(min_value, min(max_value, int(float(var.get()))))

    def apply_layout_settings(_value: float | None = None) -> None:
        participants_height = layout_value(participants_height_var, 240, 900)
        events_height = layout_value(events_height_var, 90, 360)
        winner_width = layout_value(winner_width_var, 260, 520)
        font_size = layout_value(raffle_font_size_var, 10, 20)

        queue_size_text.set(f"{participants_height}px")
        event_size_text.set(f"{events_height}px")
        winner_size_text.set(f"{winner_width}px")
        font_size_text.set(f"{font_size}px")

        winner_card.configure(width=winner_width)
        winner_label.configure(font=("Segoe UI Semibold", max(24, font_size + 18)), wraplength=max(220, winner_width - 60))
        winner_messages_text.configure(height=max(110, int(participants_height * 0.45)), font=("Segoe UI", font_size))
        log_text.configure(height=events_height, font=("Consolas", max(9, font_size - 2)))

        participant_card.grid_propagate(True)
        if ff_queue_card is not None:
            ff_queue_card.grid_propagate(True)
        winner_card.grid_propagate(False)
        log_card.grid_propagate(True)

        try:
            if hasattr(refresh_participant_list, "_items"):
                delattr(refresh_participant_list, "_items")
            refresh_participant_list(raffle_worker.participant_items() if raffle_worker else [])
        except NameError:
            pass

    queue_slider.configure(command=apply_layout_settings)
    event_slider.configure(command=apply_layout_settings)
    winner_slider.configure(command=apply_layout_settings)
    font_slider.configure(command=apply_layout_settings)
    apply_layout_settings()

    def default_kills_style() -> dict[str, Any]:
        return {
            "title_text": "TOP KILLS",
            "font_family": "impact",
            "text_align": "left",
            "title_align": "left",
            "title_size": 34,
            "row_size": 26,
            "kills_size": 28,
            "rank_size": 24,
            "font_weight": 900,
            "row_height": 42,
            "row_gap": 5,
            "row_max_width": 0,
            "column_gap": 10,
            "row_padding_x": 10,
            "wrap_padding": 8,
            "switch_seconds": 10,
            "title_color": "#FFD54A",
            "rank_color": "#FFD54A",
            "name_color": "#FFFFFF",
            "kills_color": "#66FF99",
            "shadow_color": "#000000",
            "shadow_blur": 7,
            "row_bg_color": "#000000",
            "row_bg_opacity": 35,
            "accent_color": "#FF4655",
            "accent_width": 4,
            "row_radius": 8,
            "show_title": True,
            "uppercase_title": True,
            "show_rank_prefix": True,
            "show_medals": True,
            "row_bg_enabled": False,
            "accent_enabled": False,
        }

    def kills_style_int(var: tk.StringVar, fallback: int, min_value: int, max_value: int) -> int:
        value = max(min_value, min(max_value, normalize_kill_value(var.get()) or fallback))
        var.set(str(value))
        return value

    def apply_kills_style(style: dict[str, Any]) -> None:
        data = default_kills_style()
        if isinstance(style, dict):
            data.update(style)
        kills_style_title_var.set(str(data.get("title_text") or "TOP KILLS")[:40])
        kills_style_font_var.set(str(data.get("font_family") or "impact"))
        kills_style_align_var.set(str(data.get("text_align") or "left"))
        kills_style_title_align_var.set(str(data.get("title_align") or "left"))
        kills_style_title_size_var.set(str(max(18, min(96, normalize_kill_value(data.get("title_size", 34))))))
        kills_style_row_size_var.set(str(max(14, min(80, normalize_kill_value(data.get("row_size", 26))))))
        kills_style_kills_size_var.set(str(max(14, min(96, normalize_kill_value(data.get("kills_size", 28))))))
        kills_style_rank_size_var.set(str(max(12, min(80, normalize_kill_value(data.get("rank_size", 24))))))
        kills_style_weight_var.set(str(max(300, min(900, normalize_kill_value(data.get("font_weight", 900))))))
        kills_style_row_height_var.set(str(max(24, min(120, normalize_kill_value(data.get("row_height", 42))))))
        kills_style_row_gap_var.set(str(max(0, min(30, normalize_kill_value(data.get("row_gap", 5))))))
        kills_style_row_max_width_var.set(str(max(0, min(1200, normalize_kill_value(data.get("row_max_width", 0))))))
        kills_style_column_gap_var.set(str(max(0, min(60, normalize_kill_value(data.get("column_gap", 10))))))
        kills_style_row_padding_var.set(str(max(0, min(60, normalize_kill_value(data.get("row_padding_x", 10))))))
        kills_style_wrap_padding_var.set(str(max(0, min(80, normalize_kill_value(data.get("wrap_padding", 8))))))
        kills_style_switch_seconds_var.set(str(max(3, min(120, normalize_kill_value(data.get("switch_seconds", 10))))))
        kills_style_title_color_var.set(normalize_hex_color(data.get("title_color"), "#FFD54A"))
        kills_style_rank_color_var.set(normalize_hex_color(data.get("rank_color"), "#FFD54A"))
        kills_style_name_color_var.set(normalize_hex_color(data.get("name_color"), "#FFFFFF"))
        kills_style_kills_color_var.set(normalize_hex_color(data.get("kills_color"), "#66FF99"))
        kills_style_shadow_color_var.set(normalize_hex_color(data.get("shadow_color"), "#000000"))
        kills_style_shadow_blur_var.set(str(max(0, min(24, normalize_kill_value(data.get("shadow_blur", 7))))))
        kills_style_row_bg_color_var.set(normalize_hex_color(data.get("row_bg_color"), "#000000"))
        kills_style_row_bg_opacity_var.set(str(max(0, min(100, normalize_kill_value(data.get("row_bg_opacity", 35))))))
        kills_style_accent_color_var.set(normalize_hex_color(data.get("accent_color"), "#FF4655"))
        kills_style_accent_width_var.set(str(max(0, min(20, normalize_kill_value(data.get("accent_width", 4))))))
        kills_style_row_radius_var.set(str(max(0, min(40, normalize_kill_value(data.get("row_radius", 8))))))
        kills_style_show_title_var.set(bool(data.get("show_title", True)))
        kills_style_uppercase_var.set(bool(data.get("uppercase_title", True)))
        kills_style_rank_prefix_var.set(bool(data.get("show_rank_prefix", True)))
        kills_style_medals_var.set(bool(data.get("show_medals", True)))
        kills_style_row_bg_var.set(bool(data.get("row_bg_enabled", False)))
        kills_style_accent_var.set(bool(data.get("accent_enabled", False)))

    def collect_kills_style() -> dict[str, Any]:
        return {
            "title_text": kills_style_title_var.get().strip()[:40] or "TOP KILLS",
            "font_family": kills_style_font_var.get().strip() or "impact",
            "text_align": kills_style_align_var.get().strip() or "left",
            "title_align": kills_style_title_align_var.get().strip() or "left",
            "title_size": kills_style_int(kills_style_title_size_var, 34, 18, 96),
            "row_size": kills_style_int(kills_style_row_size_var, 26, 14, 80),
            "kills_size": kills_style_int(kills_style_kills_size_var, 28, 14, 96),
            "rank_size": kills_style_int(kills_style_rank_size_var, 24, 12, 80),
            "font_weight": kills_style_int(kills_style_weight_var, 900, 300, 900),
            "row_height": kills_style_int(kills_style_row_height_var, 42, 24, 120),
            "row_gap": kills_style_int(kills_style_row_gap_var, 5, 0, 30),
            "row_max_width": kills_style_int(kills_style_row_max_width_var, 0, 0, 1200),
            "column_gap": kills_style_int(kills_style_column_gap_var, 10, 0, 60),
            "row_padding_x": kills_style_int(kills_style_row_padding_var, 10, 0, 60),
            "wrap_padding": kills_style_int(kills_style_wrap_padding_var, 8, 0, 80),
            "switch_seconds": kills_style_int(kills_style_switch_seconds_var, 10, 3, 120),
            "title_color": normalize_hex_color(kills_style_title_color_var.get(), "#FFD54A"),
            "rank_color": normalize_hex_color(kills_style_rank_color_var.get(), "#FFD54A"),
            "name_color": normalize_hex_color(kills_style_name_color_var.get(), "#FFFFFF"),
            "kills_color": normalize_hex_color(kills_style_kills_color_var.get(), "#66FF99"),
            "shadow_color": normalize_hex_color(kills_style_shadow_color_var.get(), "#000000"),
            "shadow_blur": kills_style_int(kills_style_shadow_blur_var, 7, 0, 24),
            "row_bg_color": normalize_hex_color(kills_style_row_bg_color_var.get(), "#000000"),
            "row_bg_opacity": kills_style_int(kills_style_row_bg_opacity_var, 35, 0, 100),
            "accent_color": normalize_hex_color(kills_style_accent_color_var.get(), "#FF4655"),
            "accent_width": kills_style_int(kills_style_accent_width_var, 4, 0, 20),
            "row_radius": kills_style_int(kills_style_row_radius_var, 8, 0, 40),
            "show_title": bool(kills_style_show_title_var.get()),
            "uppercase_title": bool(kills_style_uppercase_var.get()),
            "show_rank_prefix": bool(kills_style_rank_prefix_var.get()),
            "show_medals": bool(kills_style_medals_var.get()),
            "row_bg_enabled": bool(kills_style_row_bg_var.get()),
            "accent_enabled": bool(kills_style_accent_var.get()),
        }

    def kills_style_endpoint() -> str:
        endpoint_url = normalize_endpoint_url(kills_style_url_var.get())
        if endpoint_url:
            return derive_kills_style_endpoint(endpoint_url)
        source_url = normalize_endpoint_url(sync_url_var.get())
        if source_url:
            return derive_kills_style_endpoint(source_url)
        base_url = normalize_endpoint_url(jarvis_base_url_var.get())
        return derive_kills_style_endpoint(base_url) if base_url else ""

    def load_kills_style(force: bool = True) -> None:
        if kills_ff_site_sync_hidden:
            kills_style_status_var.set("Desativado")
            if force:
                log("Estilo OBS Kills FF desativado porque a aba Kills FF esta oculta.")
            return
        endpoint_url = kills_style_endpoint()
        if not endpoint_url:
            kills_style_status_var.set("Sem endpoint")
            if force:
                log("Configure a URL do Jarvis para carregar o estilo OBS Kills FF.")
            return
        kills_style_url_var.set(endpoint_url)
        kills_obs_url_var.set(derive_kills_obs_url(endpoint_url))
        kills_style_status_var.set("Carregando")
        local_device_id = str(config.get("device_id", "")).strip()
        local_device_name = device_name_var.get().strip()
        local_token = jarvis_token_var.get().strip()

        def run() -> None:
            try:
                style = fetch_kills_style(endpoint_url, device_id=local_device_id, device_name=local_device_name, token=local_token)
                enqueue_sync_event("kills_style_loaded", {"style": style})
            except Exception as exc:
                enqueue_sync_event("kills_style_error", {"error": str(exc), "label": "carregar estilo"})

        start_sync_worker(run, name="AizenKillsStyleLoad")

    def save_kills_style() -> None:
        if kills_ff_site_sync_hidden:
            kills_style_status_var.set("Desativado")
            log("Estilo OBS Kills FF desativado porque a aba Kills FF esta oculta.")
            return
        endpoint_url = kills_style_endpoint()
        if not endpoint_url:
            kills_style_status_var.set("Sem endpoint")
            log("Configure a URL do Jarvis para salvar o estilo OBS Kills FF.")
            return
        kills_style_url_var.set(endpoint_url)
        kills_obs_url_var.set(derive_kills_obs_url(endpoint_url))
        style = collect_kills_style()
        kills_style_status_var.set("Salvando")
        local_device_id = str(config.get("device_id", "")).strip()
        local_device_name = device_name_var.get().strip()
        local_token = jarvis_token_var.get().strip()

        def run() -> None:
            try:
                saved = send_kills_style_update(endpoint_url, style, device_id=local_device_id, device_name=local_device_name, token=local_token)
                enqueue_sync_event("kills_style_saved", {"style": saved})
            except Exception as exc:
                enqueue_sync_event("kills_style_error", {"error": str(exc), "label": "salvar estilo"})

        start_sync_worker(run, name="AizenKillsStyleSave")

    def reset_kills_style_form() -> None:
        apply_kills_style(default_kills_style())
        kills_style_status_var.set("Padrão aplicado")

    def copy_kills_obs_url() -> None:
        url = kills_obs_url_var.get().strip() or (derive_kills_obs_url(kills_style_endpoint()) if kills_style_endpoint() else "")
        if not url:
            kills_style_status_var.set("Sem URL OBS")
            return
        root.clipboard_clear()
        root.clipboard_append(url)
        kills_style_status_var.set("URL OBS copiada")

    def open_kills_obs_url() -> None:
        url = kills_obs_url_var.get().strip() or (derive_kills_obs_url(kills_style_endpoint()) if kills_style_endpoint() else "")
        if not url:
            kills_style_status_var.set("Sem URL OBS")
            return
        webbrowser.open(url)

    def sorted_rank_players(players: list[PlayerKill]) -> list[PlayerKill]:
        merged: dict[str, PlayerKill] = {}
        order: list[str] = []
        for player in players:
            name = player.name.strip()
            if not name:
                continue
            key = normalize_player_key(name)
            if key not in merged:
                merged[key] = PlayerKill(
                    name=name,
                    kills=max(0, normalize_kill_value(player.kills)),
                    key=player.key,
                    ff_player_id=player.ff_player_id,
                    entries=player.entries,
                )
                order.append(key)
            else:
                merged[key].kills = max(merged[key].kills, normalize_kill_value(player.kills))
                if player.key and not merged[key].key:
                    merged[key].key = player.key
                if player.ff_player_id and not merged[key].ff_player_id:
                    merged[key].ff_player_id = player.ff_player_id
                merged[key].entries = max(merged[key].entries, normalize_kill_value(player.entries))
        return sorted((merged[key] for key in order), key=lambda item: (-item.kills, normalize_player_key(item.name)))

    def current_kills_rank_players() -> list[PlayerKill]:
        if kills_rank_mode_var.get() == "Geral":
            return kills_global_ranking
        return kills_daily_ranking

    def current_kills_rank_scope() -> str:
        return "general" if kills_rank_mode_var.get() == "Geral" else "daily"

    def clone_player_list(players: list[PlayerKill]) -> list[PlayerKill]:
        return [
            PlayerKill(
                name=player.name,
                kills=normalize_kill_value(player.kills),
                key=player.key,
                ff_player_id=player.ff_player_id,
                entries=normalize_kill_value(player.entries),
            )
            for player in players
        ]

    def merge_manual_player_kills(players: list[PlayerKill]) -> list[PlayerKill]:
        merged: dict[str, PlayerKill] = {}
        order: list[str] = []
        for player in players:
            name = player.name.strip()
            if not name:
                continue
            key = normalize_player_key(name)
            if key not in merged:
                merged[key] = PlayerKill(
                    name=name,
                    kills=normalize_kill_value(player.kills),
                    key=player.key,
                    ff_player_id=player.ff_player_id,
                    entries=normalize_kill_value(player.entries),
                )
                order.append(key)
                continue
            merged[key].kills += normalize_kill_value(player.kills)
            if player.key and not merged[key].key:
                merged[key].key = player.key
            if player.ff_player_id and not merged[key].ff_player_id:
                merged[key].ff_player_id = player.ff_player_id
            merged[key].entries = max(merged[key].entries, normalize_kill_value(player.entries))
        return sorted((merged[key] for key in order), key=lambda item: (-item.kills, normalize_player_key(item.name)))

    def current_manual_scope() -> str:
        scope = normalize_kills_scope_value(manual_scope_var.get())
        return scope if scope in {"daily", "general"} else "daily"

    def manual_scope_label(scope: str | None = None) -> str:
        return kills_scope_label(scope or current_manual_scope())

    def manual_scope_rank_players(scope: str | None = None) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        return kills_global_ranking if clean_scope == "general" else kills_daily_ranking

    def manual_players_need_name_completion(players: list[PlayerKill]) -> bool:
        return any(not str(player.name or "").strip() and normalize_kill_value(player.kills) > 0 for player in players)

    def clear_manual_reference_cache() -> None:
        nonlocal manual_reference_cache_generation
        manual_reference_cache_generation += 1
        manual_reference_cache.clear()

    def manual_reference_cache_key(scope: str) -> str:
        clean_scope = normalize_kills_scope_value(scope)
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        return f"{clean_scope}|{manual_reference_cache_generation}"

    def manual_name_reference_players(scope: str | None = None) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        cache_key = manual_reference_cache_key(clean_scope)
        cached = manual_reference_cache.get(clean_scope)
        if cached and cached[0] == cache_key:
            return clone_player_list(cached[1])
        other_scope = "daily" if clean_scope == "general" else "general"
        references: list[PlayerKill] = []
        for row in manual_rows:
            try:
                visible_name = row["name_var"].get().strip()
                visible_kills = normalize_kill_value(row["kills_var"].get())
            except (KeyError, tk.TclError):
                continue
            if visible_name:
                references.append(PlayerKill(visible_name, visible_kills, key=normalize_player_key(visible_name)))
        references.extend(manual_scope_rank_players(clean_scope))
        references.extend(manual_scope_buffers.get(clean_scope, []))
        references.extend(manual_scope_rank_players(other_scope))
        references.extend(manual_scope_buffers.get(other_scope, []))
        players = sorted_rank_players(references)
        manual_reference_cache[clean_scope] = (cache_key, clone_player_list(players))
        return players

    def complete_manual_player_names(
        players: list[PlayerKill],
        scope: str | None = None,
        references: list[PlayerKill] | None = None,
    ) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        if not manual_players_need_name_completion(players):
            return complete_player_names_from_references(players, None)
        source_players = references if references is not None else manual_name_reference_players(clean_scope)
        return complete_player_names_from_references(players, source_players)

    def repair_manual_scope_buffer_names(scope: str | None = None, references: list[PlayerKill] | None = None) -> bool:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        buffered_players = manual_scope_buffers.get(clean_scope, [])
        if not buffered_players:
            return False
        if not manual_players_need_name_completion(buffered_players):
            return False
        completed_players = complete_manual_player_names(buffered_players, clean_scope, references=references)
        if len(completed_players) == len(buffered_players) and all(
            left.name == right.name and normalize_kill_value(left.kills) == normalize_kill_value(right.kills)
            for left, right in zip(completed_players, buffered_players)
        ):
            return False
        manual_scope_buffers[clean_scope] = clone_player_list(completed_players)
        clear_manual_reference_cache()
        return True

    def manual_scope_display_players(scope: str | None = None, prefer_remote: bool = True) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        rank_source = manual_scope_rank_players(clean_scope)
        rank_references = manual_name_reference_players(clean_scope) if manual_players_need_name_completion(rank_source) else None
        rank_players = merge_manual_player_kills(complete_manual_player_names(rank_source, clean_scope, references=rank_references))
        if rank_players:
            repair_manual_scope_buffer_names(clean_scope, references=rank_players)
        if prefer_remote and rank_players and clean_scope not in manual_scope_dirty:
            manual_scope_buffers[clean_scope] = clone_player_list(rank_players)
            clear_manual_reference_cache()
            return clone_player_list(rank_players)
        buffered_players = manual_scope_buffers.get(clean_scope) or []
        if buffered_players:
            buffer_references = rank_players if manual_players_need_name_completion(buffered_players) else None
            completed_players = merge_manual_player_kills(
                complete_manual_player_names(buffered_players, clean_scope, references=buffer_references)
            )
            manual_scope_buffers[clean_scope] = clone_player_list(completed_players)
            clear_manual_reference_cache()
            return clone_player_list(completed_players)
        if rank_players:
            manual_scope_buffers[clean_scope] = clone_player_list(rank_players)
            clear_manual_reference_cache()
            return clone_player_list(rank_players)
        return []

    def sync_kills_rank_tab_with_manual_scope(scope: str | None = None) -> None:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        rank_label = "Geral" if clean_scope == "general" else "Diario"
        kills_rank_mode_var.set(rank_label)
        try:
            kills_overlay_tabview.set("Geral" if clean_scope == "general" else "Diário")
        except (NameError, AttributeError, tk.TclError):
            pass

    def remember_current_manual_scope() -> None:
        scope = current_manual_scope()
        manual_scope_buffers[scope] = clone_player_list(collect_manual_players(scope=scope))
        clear_manual_reference_cache()

    def refresh_manual_table_for_scope(scope: str | None = None, prefer_remote: bool = True) -> None:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        repair_manual_scope_buffer_names(clean_scope)
        players = manual_scope_display_players(clean_scope, prefer_remote=prefer_remote)
        set_manual_players(players, scope=clean_scope)
        try:
            fill_visible_manual_missing_names_from_rank(clean_scope)
        except NameError:
            pass
        sync_kills_rank_tab_with_manual_scope(clean_scope)
        manual_status_var.set("Mostrando rank geral" if clean_scope == "general" else "Mostrando rank diario")

    def on_manual_scope_change() -> None:
        nonlocal manual_active_scope
        previous_scope = manual_active_scope
        new_scope = current_manual_scope()
        if new_scope not in {"daily", "general"}:
            new_scope = "daily"
            manual_scope_var.set("Diario")
        if previous_scope in {"daily", "general"}:
            manual_scope_buffers[previous_scope] = clone_player_list(collect_manual_players(scope=previous_scope))
            clear_manual_reference_cache()
        manual_active_scope = new_scope
        config["kills_manual_scope"] = new_scope
        refresh_manual_table_for_scope(new_scope, prefer_remote=True)

    def run_kills_rank_action(
        action: str,
        player: PlayerKill | None = None,
        kills: int | None = None,
        scope: str | None = None,
        label: str = "",
        confirm_text: str = "",
        new_name: str = "",
        ff_player_id: str = "",
    ) -> bool:
        if kills_ff_site_sync_hidden:
            manual_status_var.set("Desativado")
            log("Acoes remotas de Kills FF desativadas porque a aba Kills FF esta oculta.")
            return False
        if confirm_text and not messagebox.askyesno("Kills FF", confirm_text):
            return False
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return False
        endpoint_url = local_config.get("kills_realtime_url", "").strip()
        if not endpoint_url:
            manual_status_var.set("Sem endpoint")
            log("Informe a URL do painel/Jarvis para aplicar acoes no ranking.")
            return False
        manual_status_var.set(label or "Aplicando acao")
        action_scope = scope or current_kills_rank_scope()

        def run() -> None:
            try:
                state = send_kills_action_update(
                    endpoint_url,
                    action,
                    player=player,
                    kills=kills,
                    scope=action_scope,
                    new_name=new_name,
                    ff_player_id=ff_player_id,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("kills_sync_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event("kills_action_done", {"state": state, "action": action, "label": label or action})
            except Exception as exc:
                enqueue_sync_event("kills_action_error", {"error": str(exc), "action": action, "label": label or action})

        start_sync_worker(run, name="AizenKillsAction")
        return True

    def kills_admin_scope_value() -> str:
        scope = normalize_kills_scope_value(kills_admin_scope_var.get())
        return scope if scope in {"daily", "general"} else "daily"

    def select_kills_admin_player(player: PlayerKill, scope_label: str) -> None:
        clean_scope = "Geral" if str(scope_label).strip().lower().startswith("ger") else "Diario"
        kills_admin_name_var.set(player.name)
        kills_admin_new_name_var.set("")
        kills_admin_ff_id_var.set(str(player.ff_player_id or ""))
        kills_admin_kills_var.set("1")
        kills_admin_scope_var.set(clean_scope)
        kills_admin_key_var.set(player.key or normalize_player_key(player.name))
        manual_status_var.set(f"Selecionado: {player.name}")

    def kills_admin_player(require_name: bool = True) -> PlayerKill | None:
        name = kills_admin_name_var.get().strip()
        if require_name and not name:
            messagebox.showinfo("Kills FF", "Informe o jogador atual.")
            return None
        ff_player_id = re.sub(r"\D+", "", kills_admin_ff_id_var.get())
        player_key = kills_admin_key_var.get().strip() or normalize_player_key(name)
        return PlayerKill(name=name, kills=0, key=player_key, ff_player_id=ff_player_id)

    def kills_admin_kill_value() -> int | None:
        try:
            value = int(float(kills_admin_kills_var.get().replace(",", ".")))
        except ValueError:
            messagebox.showinfo("Kills FF", "Informe uma quantidade de kills valida.")
            return None
        return max(0, min(999999, value))

    def apply_kills_admin_action(action: str) -> None:
        normalized = str(action or "").strip().lower()
        scope = kills_admin_scope_value()

        if normalized in {"reset", "reset_daily", "reset_general"}:
            if normalized == "reset":
                run_kills_rank_action(
                    "reset",
                    scope="both",
                    label="Zerando tudo",
                    confirm_text="Resetar o ranking diário e o ranking geral? Jogadores ignorados serão mantidos.",
                )
                return
            confirm_text = (
                "Resetar o ranking diario? O ranking geral sera mantido."
                if normalized == "reset_daily"
                else "Resetar o ranking geral? O ranking diario sera mantido."
            )
            label = "Zerando diario" if normalized == "reset_daily" else "Zerando geral"
            run_kills_rank_action(normalized, scope="daily" if normalized == "reset_daily" else "general", label=label, confirm_text=confirm_text)
            return

        player = kills_admin_player(require_name=True)
        if player is None:
            return

        if normalized in {"add", "remove", "set"}:
            kills = kills_admin_kill_value()
            if kills is None:
                return
            labels = {
                "add": "Somando kills",
                "remove": "Removendo kills",
                "set": "Definindo kills",
            }
            run_kills_rank_action(normalized, player=player, kills=kills, scope=scope, label=labels[normalized])
            return

        if normalized == "set_name":
            new_name = kills_admin_new_name_var.get().strip()
            if not new_name:
                messagebox.showinfo("Kills FF", "Informe o novo nome.")
                return
            run_kills_rank_action("set_name", player=player, new_name=new_name, scope="both", label="Editando nome")
            return

        if normalized == "set_ff_id":
            raw_id = kills_admin_ff_id_var.get().strip()
            clean_id = re.sub(r"\D+", "", raw_id)
            if raw_id and not re.fullmatch(r"\d{5,15}", clean_id):
                messagebox.showinfo("Kills FF", "ID FF invalido. Use somente numeros, de 5 a 15 digitos.")
                return
            run_kills_rank_action("set_ff_id", player=player, ff_player_id=clean_id, scope="both", label="Editando ID FF")
            return

        if normalized == "ignore":
            run_kills_rank_action(
                "ignore",
                player=player,
                scope="both",
                label="Ignorando jogador",
                confirm_text=f"Ignorar {player.name} no ranking e no OBS?",
            )
            return

        if normalized == "unignore":
            run_kills_rank_action("unignore", player=player, scope="both", label="Reexibindo jogador")
            return

        if normalized == "delete":
            run_kills_rank_action(
                "delete",
                player=player,
                scope=scope,
                label="Removendo jogador",
                confirm_text=f"Remover {player.name} do ranking selecionado?",
            )
            return

        messagebox.showinfo("Kills FF", "Acao invalida.")

    def clear_kills_admin_fields() -> None:
        kills_admin_name_var.set("")
        kills_admin_new_name_var.set("")
        kills_admin_ff_id_var.set("")
        kills_admin_kills_var.set("1")
        kills_admin_scope_var.set("Diario")
        kills_admin_key_var.set("")

    def prompt_set_kills_rank_value(player: PlayerKill) -> None:
        value = simpledialog.askinteger(
            "Definir kills",
            f"Novo total de kills para {player.name}:",
            initialvalue=max(0, normalize_kill_value(player.kills)),
            minvalue=0,
            maxvalue=999999,
            parent=root,
        )
        if value is None:
            return
        run_kills_rank_action("set", player=player, kills=value, label="Definindo kills")

    def prompt_set_kills_rank_name(player: PlayerKill) -> None:
        value = simpledialog.askstring("Editar nome", f"Novo nome para {player.name}:", initialvalue=player.name, parent=root)
        clean = str(value or "").strip()
        if not clean:
            return
        run_kills_rank_action("set_name", player=player, new_name=clean, scope="both", label="Editando nome")

    def prompt_set_kills_rank_ff_id(player: PlayerKill) -> None:
        value = simpledialog.askstring("Editar ID FF", f"ID Free Fire de {player.name}:", initialvalue=player.ff_player_id, parent=root)
        if value is None:
            return
        clean = re.sub(r"\D+", "", str(value))
        run_kills_rank_action("set_ff_id", player=player, ff_player_id=clean, scope="both", label="Editando ID FF")

    def prompt_ignore_kills_rank_name() -> None:
        value = simpledialog.askstring("Ignorar jogador", "Nome do jogador para ignorar no ranking:", parent=root)
        clean = str(value or "").strip()
        if not clean:
            return
        run_kills_rank_action(
            "ignore",
            player=PlayerKill(clean, 0, key=normalize_player_key(clean)),
            scope="both",
            label="Ignorando jogador",
            confirm_text=f"Ignorar {clean} no ranking e no OBS?",
        )

    def prompt_unignore_kills_rank_name() -> None:
        value = simpledialog.askstring("Reexibir jogador", "Nome do jogador para voltar ao ranking:", parent=root)
        clean = str(value or "").strip()
        if not clean:
            return
        run_kills_rank_action(
            "unignore",
            player=PlayerKill(clean, 0, key=normalize_player_key(clean)),
            scope="both",
            label="Reexibindo jogador",
        )

    def is_kills_ff_tab_active() -> bool:
        if kills_ff_site_sync_hidden:
            return False
        try:
            return tabview.get() == "Kills FF"
        except (AttributeError, tk.TclError):
            return False

    def is_ff_queue_tab_active() -> bool:
        if ff_queue_site_sync_hidden:
            return False
        try:
            return tabview.get() == "Fila FF"
        except (AttributeError, tk.TclError):
            return False

    def update_digest_part(digest: Any, value: Any) -> None:
        digest.update(str(value if value is not None else "").encode("utf-8", "replace"))
        digest.update(b"\0")

    def player_rank_light_signature(players: list[PlayerKill], limit: int | None = None) -> str:
        digest = hashlib.sha1()
        count = 0
        for index, player in enumerate(players):
            if limit is not None and index >= limit:
                break
            count += 1
            update_digest_part(digest, player.name)
            update_digest_part(digest, player.key)
            update_digest_part(digest, normalize_kill_value(player.kills))
            update_digest_part(digest, player.ff_player_id)
            update_digest_part(digest, normalize_kill_value(player.entries))
        update_digest_part(digest, count)
        update_digest_part(digest, len(players))
        return digest.hexdigest()

    def ignored_players_light_signature(players: list[IgnoredKillPlayer]) -> str:
        digest = hashlib.sha1()
        for player in players:
            update_digest_part(digest, player.name)
            update_digest_part(digest, player.key)
        update_digest_part(digest, len(players))
        return digest.hexdigest()

    def refresh_kills_ignored_list(force: bool = False) -> None:
        nonlocal kills_ignored_render_pending
        if not force and not is_kills_ff_tab_active():
            if not kills_ignored_render_pending:
                kills_ignored_render_pending = True
            return
        kills_ignored_count_var.set(str(len(kills_ignored_players)))
        ignored_signature = ignored_players_light_signature(kills_ignored_players)
        if (
            getattr(refresh_kills_ignored_list, "_signature", None) == ignored_signature
            and not kills_ignored_render_pending
        ):
            return
        refresh_kills_ignored_list._signature = ignored_signature  # type: ignore[attr-defined]
        refresh_kills_ignored_list._deferred_signature = ""  # type: ignore[attr-defined]
        kills_ignored_render_pending = False
        for widget in kills_ignored_rows:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        kills_ignored_rows.clear()

        if not kills_ignored_players:
            empty = ctk.CTkLabel(
                kills_ignored_frame,
                text="Nenhum jogador ignorado.",
                text_color=muted,
                font=("Segoe UI", 12),
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=14, pady=12)
            kills_ignored_rows.append(empty)
            return

        for index, ignored_player in enumerate(kills_ignored_players, start=1):
            row_frame = ctk.CTkFrame(
                kills_ignored_frame,
                fg_color="#171014" if index % 2 else "#0f0b0e",
                corner_radius=10,
            )
            row_frame.grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
            row_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row_frame,
                text=ignored_player.name,
                text_color=fg,
                font=("Segoe UI Semibold", 12),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=(12, 6), pady=8)
            button(
                row_frame,
                "Reexibir",
                lambda target=ignored_player: run_kills_rank_action(
                    "unignore",
                    player=PlayerKill(target.name, 0, key=target.key or normalize_player_key(target.name)),
                    scope="both",
                    label="Reexibindo jogador",
                ),
                "accent",
                width=82,
            ).grid(row=0, column=1, sticky="e", padx=(6, 12), pady=8)
            kills_ignored_rows.append(row_frame)

    def refresh_kills_rank_table(force: bool = False) -> None:
        nonlocal kills_rank_render_pending
        if not force and not is_kills_ff_tab_active():
            if not kills_rank_render_pending:
                kills_rank_render_pending = True
            return
        daily_total = sum(player.kills for player in kills_daily_ranking)
        global_total = sum(player.kills for player in kills_global_ranking)
        set_text_var(kills_daily_rank_count_var, len(kills_daily_ranking))
        set_text_var(kills_daily_rank_total_var, daily_total)
        set_text_var(kills_global_rank_count_var, len(kills_global_ranking))
        set_text_var(kills_global_rank_total_var, global_total)
        rank_signature_limit = max(KILLS_RANK_RENDER_LIMIT, KILLS_OVERLAY_RENDER_LIMIT)
        table_signature = (
            player_rank_light_signature(kills_daily_ranking, limit=rank_signature_limit),
            daily_total,
            player_rank_light_signature(kills_global_ranking, limit=rank_signature_limit),
            global_total,
            ignored_players_light_signature(kills_ignored_players),
        )
        if not force and getattr(refresh_kills_rank_table, "_signature", None) == table_signature and not kills_rank_render_pending:
            return
        refresh_kills_rank_table._signature = table_signature  # type: ignore[attr-defined]
        refresh_kills_rank_table._deferred_signature = ""  # type: ignore[attr-defined]
        kills_rank_render_pending = False

        def rank_render_signature(players: list[PlayerKill], limit: int) -> str:
            return player_rank_light_signature(players, limit=limit)

        def table_render_unchanged(signature_key: str, row_widgets: list[Any], signature: str) -> bool:
            if force or not row_widgets:
                return False
            if getattr(refresh_kills_rank_table, signature_key, None) == signature:
                return True
            setattr(refresh_kills_rank_table, signature_key, signature)
            return False

        def render_rank(
            table_frame: Any,
            row_widgets: list[Any],
            players: list[PlayerKill],
            count_var: tk.StringVar,
            total_var: tk.StringVar,
            empty_text: str,
            scope_label: str,
            total_kills: int | None = None,
        ) -> None:
            row_signature = rank_render_signature(players, KILLS_RANK_RENDER_LIMIT)
            set_text_var(count_var, len(players))
            set_text_var(total_var, total_kills if total_kills is not None else sum(player.kills for player in players))
            if table_render_unchanged(f"_rank_signature_{scope_label}", row_widgets, row_signature):
                return
            setattr(refresh_kills_rank_table, f"_rank_signature_{scope_label}", row_signature)
            generation_key = f"_rank_generation_{scope_label}"
            after_key = f"_rank_after_{scope_label}"
            after_id = getattr(refresh_kills_rank_table, after_key, None)
            if after_id is not None:
                try:
                    root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(refresh_kills_rank_table, after_key, None)
            generation = int(getattr(refresh_kills_rank_table, generation_key, 0) or 0) + 1
            setattr(refresh_kills_rank_table, generation_key, generation)
            for widget in row_widgets:
                try:
                    widget.destroy()
                except tk.TclError:
                    pass
            row_widgets.clear()

            if not players:
                empty = ctk.CTkLabel(
                    table_frame,
                    text=empty_text,
                    text_color=muted,
                    font=("Segoe UI", 12),
                    anchor="w",
                )
                empty.grid(row=0, column=0, sticky="ew", padx=14, pady=14)
                row_widgets.append(empty)
                return

            display_players = list(players[:KILLS_RANK_RENDER_LIMIT])

            def render_row(index: int, player: PlayerKill) -> None:
                row_frame = ctk.CTkFrame(
                    table_frame,
                    fg_color="#171014" if index % 2 else "#0f0b0e",
                    corner_radius=10,
                )
                row_frame.grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
                row_frame.columnconfigure(1, weight=1)
                medal_color = accent if index <= 3 else muted
                ctk.CTkLabel(
                    row_frame,
                    text=f"{index:02d}",
                    text_color=medal_color,
                    font=("Segoe UI Semibold", 12),
                    width=42,
                ).grid(row=0, column=0, sticky="w", padx=(12, 6), pady=8)
                ctk.CTkLabel(
                    row_frame,
                    text=player.name,
                    text_color=fg,
                    font=("Segoe UI Semibold", 12),
                    anchor="w",
                ).grid(row=0, column=1, sticky="ew", padx=6, pady=8)
                ctk.CTkLabel(
                    row_frame,
                    text=str(player.kills),
                    text_color=teal,
                    font=("Segoe UI Semibold", 14),
                    width=70,
                ).grid(row=0, column=2, sticky="e", padx=(6, 8), pady=8)
                button(
                    row_frame,
                    "Usar",
                    lambda selected=player, scope=scope_label: select_kills_admin_player(selected, scope),
                    "default",
                    width=58,
                ).grid(row=0, column=3, sticky="e", padx=(4, 10), pady=6)
                row_widgets.append(row_frame)

            def render_chunk(start_index: int = 0) -> None:
                if app_closing or getattr(refresh_kills_rank_table, generation_key, None) != generation:
                    return
                end_index = min(len(display_players), start_index + KILLS_RANK_RENDER_CHUNK_SIZE)
                for zero_index in range(start_index, end_index):
                    render_row(zero_index + 1, display_players[zero_index])
                if end_index < len(display_players):
                    next_after_id = root.after(
                        KILLS_RANK_RENDER_CHUNK_DELAY_MS,
                        lambda next_index=end_index: render_chunk(next_index),
                    )
                    setattr(refresh_kills_rank_table, after_key, next_after_id)
                    return
                setattr(refresh_kills_rank_table, after_key, None)

            if len(display_players) >= KILLS_RANK_INCREMENTAL_THRESHOLD:
                render_chunk(0)
                return

            for index, player in enumerate(display_players, start=1):
                render_row(index, player)

        def render_overlay_rank(
            table_frame: Any,
            row_widgets: list[Any],
            players: list[PlayerKill],
            empty_text: str,
            signature_key: str,
        ) -> None:
            row_signature = rank_render_signature(players, KILLS_OVERLAY_RENDER_LIMIT)
            if table_render_unchanged(signature_key, row_widgets, row_signature):
                return
            setattr(refresh_kills_rank_table, signature_key, row_signature)
            generation_key = f"{signature_key}_generation"
            after_key = f"{signature_key}_after"
            after_id = getattr(refresh_kills_rank_table, after_key, None)
            if after_id is not None:
                try:
                    root.after_cancel(after_id)
                except tk.TclError:
                    pass
                setattr(refresh_kills_rank_table, after_key, None)
            generation = int(getattr(refresh_kills_rank_table, generation_key, 0) or 0) + 1
            setattr(refresh_kills_rank_table, generation_key, generation)
            for widget in row_widgets:
                try:
                    widget.destroy()
                except tk.TclError:
                    pass
            row_widgets.clear()

            if not players:
                empty = ctk.CTkLabel(
                    table_frame,
                    text=empty_text,
                    text_color=muted,
                    font=("Segoe UI", 12),
                    anchor="center",
                    justify="center",
                )
                empty.grid(row=0, column=0, sticky="nsew", padx=16, pady=18)
                row_widgets.append(empty)
                return

            display_players = list(players[:KILLS_OVERLAY_RENDER_LIMIT])

            def render_overlay_row(index: int, player: PlayerKill) -> None:
                row_frame = ctk.CTkFrame(
                    table_frame,
                    fg_color="#171014" if index % 2 else "#0f0b0e",
                    corner_radius=12,
                    border_width=1 if index <= 3 else 0,
                    border_color=accent if index == 1 else border,
                )
                row_frame.grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
                row_frame.columnconfigure(1, weight=1)
                rank_color = accent if index == 1 else teal if index <= 3 else muted
                ctk.CTkLabel(
                    row_frame,
                    text=f"#{index:02d}",
                    text_color=rank_color,
                    font=("Segoe UI Semibold", 14),
                    width=54,
                ).grid(row=0, column=0, sticky="w", padx=(12, 8), pady=10)
                ctk.CTkLabel(
                    row_frame,
                    text=player.name,
                    text_color=fg,
                    font=("Segoe UI Semibold", 14),
                    anchor="w",
                ).grid(row=0, column=1, sticky="ew", padx=6, pady=10)
                ctk.CTkLabel(
                    row_frame,
                    text=str(player.kills),
                    text_color=teal,
                    font=("Segoe UI Semibold", 18),
                    width=80,
                ).grid(row=0, column=2, sticky="e", padx=(8, 14), pady=10)
                row_widgets.append(row_frame)

            def render_overlay_chunk(start_index: int = 0) -> None:
                if app_closing or getattr(refresh_kills_rank_table, generation_key, None) != generation:
                    return
                end_index = min(len(display_players), start_index + KILLS_RANK_RENDER_CHUNK_SIZE)
                for zero_index in range(start_index, end_index):
                    render_overlay_row(zero_index + 1, display_players[zero_index])
                if end_index < len(display_players):
                    next_after_id = root.after(
                        KILLS_RANK_RENDER_CHUNK_DELAY_MS,
                        lambda next_index=end_index: render_overlay_chunk(next_index),
                    )
                    setattr(refresh_kills_rank_table, after_key, next_after_id)
                    return
                setattr(refresh_kills_rank_table, after_key, None)

            if len(display_players) >= KILLS_RANK_INCREMENTAL_THRESHOLD:
                render_overlay_chunk(0)
                return

            for index, player in enumerate(display_players, start=1):
                render_overlay_row(index, player)

        try:
            admin_rank_visible = bool(kills_rank_card.winfo_ismapped())
        except tk.TclError:
            admin_rank_visible = False
        if admin_rank_visible:
            render_rank(
                kills_daily_rank_table_frame,
                kills_daily_rank_rows,
                kills_daily_ranking,
                kills_daily_rank_count_var,
                kills_daily_rank_total_var,
                "Busque o painel Jarvis para carregar as kills diárias.",
                "Diario",
                daily_total,
            )
            render_rank(
                kills_global_rank_table_frame,
                kills_global_rank_rows,
                kills_global_ranking,
                kills_global_rank_count_var,
                kills_global_rank_total_var,
                "Busque o painel Jarvis para carregar as kills gerais.",
                "Geral",
                global_total,
            )

        try:
            overlay_rank_tab = kills_overlay_tabview.get()
        except (AttributeError, tk.TclError):
            overlay_rank_tab = "Diário"
        if overlay_rank_tab == "Geral":
            render_overlay_rank(
                kills_overlay_global_frame,
                kills_overlay_global_rows,
                kills_global_ranking,
                "Rank geral ainda não recebido do Jarvis.",
                "_overlay_signature_global",
            )
        else:
            render_overlay_rank(
                kills_overlay_daily_frame,
                kills_overlay_daily_rows,
                kills_daily_ranking,
                "Rank diário ainda não recebido do Jarvis.",
                "_overlay_signature_daily",
            )

    def apply_kills_rankings(state: RealtimeState) -> None:
        nonlocal kills_daily_ranking, kills_global_ranking, kills_ignored_players
        nonlocal kills_rank_render_pending, kills_ignored_render_pending
        nonlocal manual_table_render_pending, manual_table_render_scope
        incoming_daily = complete_manual_player_names(state.daily_ranking or [], "daily")
        incoming_global_source = state.global_ranking if state.global_ranking else ([] if state.daily_ranking else state.players or [])
        incoming_global = complete_manual_player_names(incoming_global_source, "general")
        kills_daily_ranking = sorted_rank_players(incoming_daily)
        if state.global_ranking:
            kills_global_ranking = sorted_rank_players(incoming_global)
        elif not state.daily_ranking:
            kills_global_ranking = sorted_rank_players(incoming_global)
        else:
            kills_global_ranking = []
        kills_ignored_players = list(state.ignored_players or [])
        clear_manual_reference_cache()
        current_scope = current_manual_scope()
        if not is_kills_ff_tab_active():
            if "daily" not in manual_scope_dirty and kills_daily_ranking:
                manual_scope_buffers["daily"] = clone_player_list(kills_daily_ranking)
            if "general" not in manual_scope_dirty and kills_global_ranking:
                manual_scope_buffers["general"] = clone_player_list(kills_global_ranking)
            if current_scope not in manual_scope_dirty:
                manual_table_render_pending = True
                manual_table_render_scope = current_scope
                update_manual_metrics(manual_scope_buffers.get(current_scope, []))
            kills_rank_render_pending = True
            kills_ignored_render_pending = True
            set_text_var(
                kills_overlay_status_var,
                f"Carregado: {len(kills_daily_ranking)} dia / {len(kills_global_ranking)} geral"
                if (kills_daily_ranking or kills_global_ranking)
                else "Jarvis respondeu sem ranking",
            )
            return
        repair_manual_scope_buffer_names("daily", references=kills_daily_ranking)
        repair_manual_scope_buffer_names("general", references=kills_global_ranking)
        refresh_kills_ignored_list()
        if current_scope not in manual_scope_dirty:
            current_players = read_manual_players_light(fill_missing_names=False, scope=current_scope)
            rank_players = manual_scope_rank_players(current_scope)
            if (
                not manual_players_need_name_completion(rank_players)
                and not manual_players_need_name_completion(current_players)
                and manual_signature(rank_players, current_scope) == manual_signature(current_players, current_scope)
            ):
                update_manual_metrics(current_players)
            else:
                display_players = manual_scope_display_players(current_scope, prefer_remote=True)
                if manual_signature(display_players, current_scope) != manual_signature(current_players, current_scope):
                    set_manual_players(display_players, scope=current_scope)
                    sync_kills_rank_tab_with_manual_scope(current_scope)
                    fill_visible_manual_missing_names_from_rank(current_scope)
                else:
                    fill_visible_manual_missing_names_from_rank(current_scope)
                    update_manual_metrics()
        else:
            fill_visible_manual_missing_names_from_rank(current_scope)
            update_manual_metrics()
        set_text_var(
            kills_overlay_status_var,
            f"Carregado: {len(kills_daily_ranking)} dia / {len(kills_global_ranking)} geral"
            if (kills_daily_ranking or kills_global_ranking)
            else "Jarvis respondeu sem ranking",
        )
        schedule_kills_visual_refresh(delay_ms=80)

    def current_kills_rank_cache_signature() -> str:
        return "|".join(
            (
                player_rank_light_signature(kills_daily_ranking),
                player_rank_light_signature(kills_global_ranking),
            )
        )

    def save_kills_rank_cache() -> None:
        nonlocal kills_rank_cache_signature
        if not (kills_daily_ranking or kills_global_ranking):
            return
        cache_signature = current_kills_rank_cache_signature()
        if cache_signature == kills_rank_cache_signature and isinstance(config.get("kills_rank_cache"), dict):
            return
        config["kills_rank_cache"] = {
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "daily_ranking": player_payload(kills_daily_ranking),
            "ranking": player_payload(kills_global_ranking),
        }
        kills_rank_cache_signature = cache_signature
        try:
            save_config_snapshot_in_background(config)
        except Exception as exc:
            log(f"Nao consegui salvar cache do ranking Kills FF: {exc}")

    def apply_kills_rank_cache() -> bool:
        nonlocal kills_rank_cache_signature
        cached = config.get("kills_rank_cache")
        if not isinstance(cached, dict):
            return False
        state = parse_realtime_state(cached)
        if not (state.daily_ranking or state.global_ranking):
            return False
        apply_kills_rankings(state)
        kills_rank_cache_signature = current_kills_rank_cache_signature()
        cached_at = str(cached.get("updated_at") or "").strip()
        suffix = f" ({cached_at})" if cached_at else ""
        set_text_var(kills_overlay_status_var, f"Mostrando último rank salvo{suffix}")
        return True

    def kills_rank_signature_for_state(state: RealtimeState) -> str:
        return "|".join(
            (
                player_rank_light_signature(state.daily_ranking or []),
                player_rank_light_signature(state.global_ranking or state.players or []),
                ignored_players_light_signature(state.ignored_players or []),
                str(state.total_players),
                str(state.total_kills),
            )
        )

    def manual_signature(players: list[PlayerKill], scope: str = "") -> str:
        clean_scope = normalize_kills_scope_value(scope) if scope else ""
        return f"{clean_scope}|{player_rank_light_signature(players)}"

    def manual_snapshot_signature(daily_players: list[PlayerKill], general_players: list[PlayerKill]) -> str:
        return "|".join(
            (
                "both",
                "daily",
                player_rank_light_signature(sorted_player_kills(daily_players)),
                "general",
                player_rank_light_signature(sorted_player_kills(general_players)),
            )
        )

    def manual_config_snapshot_signature() -> str:
        scoped_players = config.get("manual_kills_by_scope")
        if isinstance(scoped_players, dict):
            daily_players = parse_players_payload(scoped_players.get("daily", []))
            general_players = parse_players_payload(scoped_players.get("general", []))
        else:
            daily_players = []
            general_players = []
        return "|".join(
            (
                normalize_kills_scope_value(config.get("kills_manual_scope", "")),
                str(config.get("kills_realtime_url") or ""),
                str(config.get("jarvis_base_url") or ""),
                str(config.get("kills_sync_room") or ""),
                str(config.get("device_name") or ""),
                str(config.get("jarvis_api_token") or ""),
                str(config.get("message_title") or ""),
                manual_snapshot_signature(daily_players, general_players),
            )
        )

    def poll_interval_seconds() -> int:
        try:
            value = int(float(poll_seconds_var.get().replace(",", ".")))
        except ValueError:
            value = 15
        return max(10, min(120, value))

    def collect_manual_widget_players(fill_missing_names: bool = True, scope: str | None = None) -> list[PlayerKill]:
        nonlocal manual_applying_remote
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        players: list[PlayerKill] = []
        for row in manual_rows:
            name = row["name_var"].get().strip()
            players.append(PlayerKill(name=name, kills=normalize_kill_value(row["kills_var"].get())))
        if not manual_players_need_name_completion(players):
            return merge_manual_player_kills(players)
        players = complete_manual_player_names(players, clean_scope)
        if fill_missing_names and not manual_applying_remote:
            missing_name_updates = [
                (row, player.name.strip())
                for row, player in zip(manual_rows, players)
                if not row["name_var"].get().strip() and player.name.strip()
            ]
            if missing_name_updates:
                previous_applying_remote = manual_applying_remote
                manual_applying_remote = True
                try:
                    for row, completed_name in missing_name_updates:
                        row["name_var"].set(completed_name)
                finally:
                    manual_applying_remote = previous_applying_remote
        return merge_manual_player_kills(players)

    def collect_manual_players(fill_missing_names: bool = True, scope: str | None = None) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        if manual_table_render_pending and manual_table_render_scope == clean_scope:
            buffered_players = manual_scope_buffers.get(clean_scope, [])
            if not manual_players_need_name_completion(buffered_players):
                return merge_manual_player_kills(buffered_players)
            return merge_manual_player_kills(
                complete_manual_player_names(buffered_players, clean_scope)
            )
        return collect_manual_widget_players(fill_missing_names=fill_missing_names, scope=clean_scope)

    def read_manual_players_light(fill_missing_names: bool = False, scope: str | None = None) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        if (
            clean_scope == current_manual_scope()
            and manual_visual_after_id is None
            and not manual_table_render_pending
            and manual_scope_buffers.get(clean_scope)
        ):
            return clone_player_list(manual_scope_buffers.get(clean_scope, []))
        return collect_manual_players(fill_missing_names=fill_missing_names, scope=clean_scope)

    def manual_scope_buffer_snapshot(
        scope: str | None = None,
        references: list[PlayerKill] | None = None,
    ) -> list[PlayerKill]:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        buffered_players = manual_scope_buffers.get(clean_scope, [])
        if manual_players_need_name_completion(buffered_players):
            buffered_players = complete_manual_player_names(buffered_players, clean_scope, references=references)
        players = merge_manual_player_kills(buffered_players)
        manual_scope_buffers[clean_scope] = clone_player_list(players)
        clear_manual_reference_cache()
        return players

    def update_manual_metrics(players: list[PlayerKill] | None = None) -> None:
        if manual_bulk_updating:
            return
        metric_players = players if players is not None else collect_manual_players()
        count_value = manual_remote_count_override if manual_remote_count_override is not None else len(metric_players)
        total_value = manual_remote_total_override if manual_remote_total_override is not None else sum(player.kills for player in metric_players)
        set_text_var(manual_count_var, count_value)
        set_text_var(manual_total_var, total_value)
        return

    def clear_manual_metric_overrides() -> None:
        nonlocal manual_remote_count_override, manual_remote_total_override
        manual_remote_count_override = None
        manual_remote_total_override = None

    def update_manual_row_numbers() -> None:
        for index, row in enumerate(manual_rows, start=1):
            grid_row = index - 1
            label_text = f"{index:02d}"
            row_color = "#171014" if index % 2 else "#0f0b0e"
            try:
                if row.get("_grid_row") != grid_row:
                    row["frame"].grid(row=grid_row, column=0, sticky="ew", padx=8, pady=4)
                    row["_grid_row"] = grid_row
                if row.get("_index_text") != label_text:
                    row["index_label"].configure(text=label_text)
                    row["_index_text"] = label_text
                if row.get("_row_color") != row_color:
                    row["frame"].configure(fg_color=row_color)
                    row["_row_color"] = row_color
            except tk.TclError:
                pass

    def sort_manual_rows_by_kills() -> None:
        def row_sort_key(row: dict[str, Any]) -> tuple[int, int, str]:
            name = row["name_var"].get().strip()
            return (
                0 if name else 1,
                -normalize_kill_value(row["kills_var"].get()),
                normalize_player_key(name),
            )

        manual_rows.sort(
            key=row_sort_key
        )
        update_manual_row_numbers()

    def apply_local_rank_players(scope: str, players: list[PlayerKill], schedule_refresh: bool = True) -> None:
        nonlocal kills_daily_ranking, kills_global_ranking
        clean_scope = normalize_kills_scope_value(scope)
        if clean_scope not in {"daily", "general"}:
            return
        manual_scope_buffers[clean_scope] = clone_player_list(players)
        clear_manual_reference_cache()
        if clean_scope == "general":
            kills_global_ranking = clone_player_list(players)
        else:
            kills_daily_ranking = clone_player_list(players)
        if manual_bulk_updating or not schedule_refresh:
            return
        schedule_kills_visual_refresh()

    def refresh_local_rank_from_manual_scope(scope: str | None = None) -> None:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            return
        buffered_players = manual_scope_buffers.get(clean_scope, [])
        if manual_players_need_name_completion(buffered_players):
            buffered_players = complete_manual_player_names(buffered_players, clean_scope)
        players = merge_manual_player_kills(buffered_players)
        apply_local_rank_players(clean_scope, players)

    def fill_visible_manual_missing_names_from_rank(scope: str | None = None) -> bool:
        nonlocal manual_applying_remote
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"} or clean_scope != current_manual_scope():
            return False
        needs_fill = any(
            not row["name_var"].get().strip() and normalize_kill_value(row["kills_var"].get()) > 0
            for row in manual_rows
        )
        if not needs_fill:
            return False
        references = manual_name_reference_players(clean_scope)
        if not references:
            return False

        used_keys = {
            normalize_player_key(row["name_var"].get())
            for row in manual_rows
            if row["name_var"].get().strip()
        }
        named_visible_count = len(used_keys)
        references_by_kills: dict[int, list[PlayerKill]] = {}
        for player in references:
            name = player.name.strip()
            key = normalize_player_key(name)
            if not name or key in used_keys:
                continue
            references_by_kills.setdefault(normalize_kill_value(player.kills), []).append(player)

        changed = False
        previous_applying_remote = manual_applying_remote
        manual_applying_remote = True
        try:
            for index, row in enumerate(manual_rows):
                if row["name_var"].get().strip():
                    continue
                kills = normalize_kill_value(row["kills_var"].get())
                if kills <= 0:
                    continue
                candidate: PlayerKill | None = None
                if index < len(references):
                    indexed_candidate = references[index]
                    indexed_key = normalize_player_key(indexed_candidate.name)
                    indexed_kills = normalize_kill_value(indexed_candidate.kills)
                    if (
                        indexed_candidate.name.strip()
                        and indexed_key not in used_keys
                        and (indexed_kills == kills or named_visible_count == 0)
                    ):
                        candidate = indexed_candidate
                if candidate is None:
                    for kill_candidate in references_by_kills.get(kills, []):
                        candidate_key = normalize_player_key(kill_candidate.name)
                        if candidate_key not in used_keys:
                            candidate = kill_candidate
                            break
                if candidate is None:
                    continue
                candidate_key = normalize_player_key(candidate.name)
                row["name_var"].set(candidate.name)
                used_keys.add(candidate_key)
                changed = True
        finally:
            manual_applying_remote = previous_applying_remote

        if changed:
            manual_scope_buffers[clean_scope] = clone_player_list(collect_manual_players(fill_missing_names=False, scope=clean_scope))
            clear_manual_reference_cache()
            refresh_local_rank_from_manual_scope(clean_scope)
        return changed

    def run_manual_visual_refresh() -> None:
        nonlocal manual_visual_after_id, manual_visual_sort_pending
        manual_visual_after_id = None
        if app_closing or manual_applying_remote:
            return
        scope = current_manual_scope()
        if scope not in {"daily", "general"}:
            scope = "daily"
        should_sort = manual_visual_sort_pending
        manual_visual_sort_pending = False
        should_sort = fill_visible_manual_missing_names_from_rank(scope) or should_sort
        if should_sort:
            sort_manual_rows_by_kills()
        players = collect_manual_players(scope=scope)
        apply_local_rank_players(scope, players, schedule_refresh=False)
        if not manual_bulk_updating:
            schedule_kills_visual_refresh()
        update_manual_metrics(players)

    def schedule_manual_visual_refresh(delay_ms: int = 160, sort_rows: bool = True) -> None:
        nonlocal manual_visual_after_id, manual_visual_sort_pending
        if app_closing or manual_applying_remote:
            return
        manual_visual_sort_pending = manual_visual_sort_pending or sort_rows
        if manual_visual_after_id is not None:
            try:
                root.after_cancel(manual_visual_after_id)
            except tk.TclError:
                pass
        manual_visual_after_id = root.after(delay_ms, run_manual_visual_refresh)

    def cancel_manual_visual_refresh() -> None:
        nonlocal manual_visual_after_id, manual_visual_sort_pending
        if manual_visual_after_id is not None:
            try:
                root.after_cancel(manual_visual_after_id)
            except tk.TclError:
                pass
            manual_visual_after_id = None
        manual_visual_sort_pending = False

    def capture_visible_manual_scope_for_send(scope: str | None = None, render_pending_table: bool = True) -> None:
        nonlocal manual_table_render_pending, manual_table_render_scope
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"} or clean_scope != current_manual_scope() or not manual_rows:
            return
        visible_players = collect_manual_widget_players(scope=clean_scope)
        if not visible_players and manual_scope_buffers.get(clean_scope):
            return

        buffered_players = clone_player_list(manual_scope_buffers.get(clean_scope, []))
        if manual_table_render_pending and len(visible_players) < len(buffered_players):
            merged: dict[str, PlayerKill] = {
                normalize_player_key(player.name): player
                for player in buffered_players
                if player.name.strip()
            }
            for player in visible_players:
                key = normalize_player_key(player.name)
                if key:
                    merged[key] = player
            manual_scope_buffers[clean_scope] = sorted_rank_players(list(merged.values()))
            clear_manual_reference_cache()
            cancel_manual_table_incremental_render()
            if render_pending_table:
                manual_table_render_pending = False
                manual_table_render_scope = ""
                try:
                    set_manual_players(manual_scope_buffers[clean_scope], scope=clean_scope, force_render=True)
                except NameError:
                    pass
            else:
                manual_table_render_pending = True
                manual_table_render_scope = clean_scope
                update_manual_metrics(manual_scope_buffers[clean_scope])
        else:
            cancel_manual_table_incremental_render()
            manual_table_render_pending = False
            manual_table_render_scope = ""
            manual_scope_buffers[clean_scope] = clone_player_list(visible_players)
            clear_manual_reference_cache()
        repair_manual_scope_buffer_names(clean_scope)

    def run_kills_visual_refresh() -> None:
        nonlocal kills_visual_after_id
        kills_visual_after_id = None
        if app_closing:
            return
        try:
            refresh_kills_rank_table()
        except NameError:
            pass
        if not ff_overlay_site_sync_hidden or ff_overlay_preview_frame is not None or ff_overlay_content_frame is not None:
            try:
                refresh_ff_overlay()
            except NameError:
                pass

    def ff_overlay_visual_target_active() -> bool:
        if ff_overlay_content_frame is not None:
            return True
        if ff_overlay_preview_frame is None:
            return False
        try:
            return bool(ff_overlay_preview_frame.winfo_ismapped())
        except tk.TclError:
            return False

    def schedule_kills_visual_refresh(delay_ms: int = KILLS_VISUAL_REFRESH_DELAY_MS) -> None:
        nonlocal kills_visual_after_id, kills_rank_render_pending, kills_ignored_render_pending
        if app_closing:
            return
        if not is_kills_ff_tab_active() and not ff_overlay_visual_target_active():
            kills_rank_render_pending = True
            kills_ignored_render_pending = True
            return
        if kills_visual_after_id is not None:
            try:
                root.after_cancel(kills_visual_after_id)
            except tk.TclError:
                pass
        kills_visual_after_id = root.after(max(40, delay_ms), run_kills_visual_refresh)

    def cancel_kills_visual_refresh() -> None:
        nonlocal kills_visual_after_id
        if kills_visual_after_id is not None:
            try:
                root.after_cancel(kills_visual_after_id)
            except tk.TclError:
                pass
            kills_visual_after_id = None

    def update_manual_config_snapshot(scope: str | None = None) -> None:
        clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        fill_visible_manual_missing_names_from_rank(clean_scope)
        if clean_scope == current_manual_scope() and not manual_table_render_pending:
            manual_scope_buffers[clean_scope] = clone_player_list(read_manual_players_light(fill_missing_names=False, scope=clean_scope))
            clear_manual_reference_cache()
        for scope_key in ("daily", "general"):
            repair_manual_scope_buffer_names(scope_key)
        endpoint_url = normalize_endpoint_url(sync_url_var.get())
        jarvis_base_url = normalize_endpoint_url(jarvis_base_url_var.get()).rstrip("/")
        config["kills_realtime_url"] = endpoint_url
        config["jarvis_endpoint_url"] = endpoint_url
        config["jarvis_base_url"] = jarvis_base_url
        config["kills_manual_scope"] = clean_scope
        config["kills_sync_room"] = sync_room_var.get().strip() or "principal"
        config["device_name"] = device_name_var.get().strip() or default_device_name()
        config["jarvis_api_token"] = jarvis_token_var.get().strip()
        config["message_title"] = title_var.get().strip() or "Kills da partida"
        config["manual_kills"] = player_payload(manual_scope_buffers.get(clean_scope, []))
        config["manual_kills_by_scope"] = {
            "daily": player_payload(manual_scope_buffers.get("daily", [])),
            "general": player_payload(manual_scope_buffers.get("general", [])),
        }

    def run_manual_config_autosave() -> None:
        nonlocal manual_config_after_id, manual_config_signature
        manual_config_after_id = None
        if app_closing:
            return
        try:
            update_manual_config_snapshot()
            signature = manual_config_snapshot_signature()
            if signature == manual_config_signature:
                return
            manual_config_signature = signature
            save_config_snapshot_in_background(config)
        except Exception as exc:
            log(f"Auto-save leve do Kills FF aguardando configuração válida: {exc}")

    def cancel_manual_config_autosave() -> None:
        nonlocal manual_config_after_id
        if manual_config_after_id is None:
            return
        try:
            root.after_cancel(manual_config_after_id)
        except tk.TclError:
            pass
        manual_config_after_id = None

    def schedule_manual_config_autosave(delay_ms: int = 1200) -> None:
        nonlocal manual_config_after_id
        if app_closing:
            return
        cancel_manual_config_autosave()
        manual_config_after_id = root.after(delay_ms, run_manual_config_autosave)

    def on_manual_change(*_args: Any, sort_rows: bool = True) -> None:
        nonlocal manual_last_local_edit_at, manual_table_render_signature
        if manual_applying_remote:
            return
        scope = current_manual_scope()
        clear_manual_reference_cache()
        manual_table_render_signature = None
        manual_scope_dirty.add(scope)
        clear_manual_metric_overrides()
        manual_last_local_edit_at = time.monotonic()
        manual_status_var.set("Editando")
        try:
            schedule_manual_config_autosave()
        except NameError:
            pass
        schedule_manual_visual_refresh(sort_rows=sort_rows)

    def manual_autocomplete_key(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
        ascii_text = "".join(character for character in normalized if not unicodedata.combining(character))
        return re.sub(r"[^a-z0-9]+", " ", ascii_text).strip()

    def manual_name_match_score(query: str, candidate: str) -> float:
        query_key = manual_autocomplete_key(query)
        candidate_key = manual_autocomplete_key(candidate)
        if not query_key or not candidate_key:
            return 0.0
        if query_key == candidate_key:
            return 120.0
        if candidate_key.startswith(query_key):
            return 110.0 - min(len(candidate_key) / 100.0, 8.0)
        candidate_words = candidate_key.split()
        if any(word.startswith(query_key) for word in candidate_words):
            return 100.0
        if query_key in candidate_key:
            return 90.0
        query_words = query_key.split()
        if query_words and all(any(word in candidate_word for candidate_word in candidate_words) for word in query_words):
            return 78.0
        if len(query_key) < 3:
            return 0.0
        similarity = SequenceMatcher(None, query_key, candidate_key).ratio()
        if similarity >= 0.48:
            return 55.0 + similarity * 30.0
        return 0.0

    def manual_name_suggestions(row: dict[str, Any], query: str, limit: int = 5) -> list[tuple[str, int, float]]:
        seen: set[str] = set()
        ranked: list[tuple[str, int, float]] = []
        for candidate_row in manual_rows:
            if candidate_row is row:
                continue
            candidate_name = candidate_row["name_var"].get().strip()
            if not candidate_name:
                continue
            key = normalize_player_key(candidate_name)
            if key in seen:
                continue
            seen.add(key)
            score = manual_name_match_score(query, candidate_name)
            if score <= 0:
                continue
            ranked.append((candidate_name, normalize_kill_value(candidate_row["kills_var"].get()), score))
        ranked.sort(key=lambda item: (-item[2], manual_autocomplete_key(item[0])))
        return ranked[:limit]

    def manual_existing_name_suggestions(query: str, limit: int = 8) -> list[tuple[str, int, float]]:
        seen: set[str] = set()
        ranked: list[tuple[str, int, float]] = []
        sources = manual_name_reference_players(current_manual_scope())
        for player in sources:
            candidate_name = player.name.strip()
            if not candidate_name:
                continue
            key = normalize_player_key(candidate_name)
            if key in seen:
                continue
            seen.add(key)
            score = manual_name_match_score(query, candidate_name)
            if score <= 0:
                continue
            ranked.append((candidate_name, normalize_kill_value(player.kills), score))
        ranked.sort(key=lambda item: (-item[2], manual_autocomplete_key(item[0])))
        return ranked[:limit]

    def cancel_manual_name_suggestion_refresh(row: dict[str, Any]) -> None:
        after_id = manual_suggestion_after_ids.pop(id(row), None)
        if after_id is None:
            return
        try:
            root.after_cancel(after_id)
        except tk.TclError:
            pass

    def schedule_manual_name_suggestions(row: dict[str, Any], delay_ms: int = 90) -> None:
        if manual_applying_remote or app_closing:
            return
        cancel_manual_name_suggestion_refresh(row)

        def run() -> None:
            manual_suggestion_after_ids.pop(id(row), None)
            if app_closing:
                return
            if any(candidate is row for candidate in manual_rows):
                refresh_manual_name_suggestions(row)

        manual_suggestion_after_ids[id(row)] = root.after(max(0, delay_ms), run)

    def hide_manual_name_suggestions(row: dict[str, Any]) -> None:
        cancel_manual_name_suggestion_refresh(row)
        suggestion_frame = row.get("suggestion_frame")
        if not suggestion_frame:
            return
        for widget in suggestion_frame.winfo_children():
            try:
                widget.destroy()
            except tk.TclError:
                pass
        try:
            suggestion_frame.grid_remove()
        except tk.TclError:
            pass

    def apply_manual_name_suggestion(row: dict[str, Any], selected_name: str) -> None:
        row["name_var"].set(selected_name)
        hide_manual_name_suggestions(row)
        try:
            row["name_entry"].focus_set()
            row["name_entry"].icursor(tk.END)
        except tk.TclError:
            pass

    def refresh_manual_name_suggestions(row: dict[str, Any]) -> None:
        if manual_applying_remote:
            hide_manual_name_suggestions(row)
            return
        query = row["name_var"].get().strip()
        if len(manual_autocomplete_key(query)) < 1:
            hide_manual_name_suggestions(row)
            return
        suggestions = manual_name_suggestions(row, query)
        suggestion_frame = row.get("suggestion_frame")
        if suggestion_frame is None:
            return
        for widget in suggestion_frame.winfo_children():
            widget.destroy()
        if not suggestions:
            hide_manual_name_suggestions(row)
            return
        suggestion_frame.grid()
        ctk.CTkLabel(
            suggestion_frame,
            text="Sugestões da tabela - clique ou pressione Enter",
            text_color=muted,
            font=("Segoe UI", 10),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=10, pady=(7, 2))
        for index, (candidate_name, candidate_kills, score) in enumerate(suggestions):
            item = ctk.CTkFrame(
                suggestion_frame,
                fg_color="#211116" if index == 0 else "#151015",
                corner_radius=8,
                border_width=1 if index == 0 else 0,
                border_color=accent,
            )
            item.grid(row=index + 1, column=0, sticky="ew", padx=4, pady=(4 if index == 0 else 2, 2))
            item.columnconfigure(0, weight=1)
            button_text = f"{candidate_name}   {candidate_kills} kill{'s' if candidate_kills != 1 else ''}"
            suggestion_button = ctk.CTkButton(
                item,
                text=button_text,
                command=lambda name=candidate_name, target_row=row: apply_manual_name_suggestion(target_row, name),
                height=30,
                fg_color="transparent",
                hover_color="#30151b",
                text_color=fg,
                anchor="w",
                corner_radius=7,
                font=("Segoe UI Semibold", 12),
            )
            suggestion_button.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
            ctk.CTkLabel(
                item,
                text="exato" if score >= 120 else "parecido",
                text_color=teal if score >= 100 else muted,
                font=("Segoe UI", 10),
            ).grid(row=0, column=1, sticky="e", padx=(4, 10), pady=3)

    def select_first_manual_name_suggestion(row: dict[str, Any]) -> str | None:
        suggestions = manual_name_suggestions(row, row["name_var"].get().strip(), limit=1)
        if not suggestions:
            return None
        apply_manual_name_suggestion(row, suggestions[0][0])
        return "break"

    def add_manual_row(name: str = "", kills: int = 0, notify: bool = True) -> None:
        row_index = len(manual_rows)
        row_frame = ctk.CTkFrame(
            manual_table_frame,
            fg_color="#171014" if row_index % 2 == 0 else "#0f0b0e",
            corner_radius=10,
        )
        row_frame.columnconfigure(1, weight=1)

        index_label = ctk.CTkLabel(
            row_frame,
            text=f"{row_index + 1:02d}",
            text_color=muted,
            font=("Segoe UI Semibold", 12),
            width=38,
        )
        index_label.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=8)

        name_var = tk.StringVar(value=name)
        kills_var = tk.StringVar(value=str(normalize_kill_value(kills)))
        name_cell = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)
        name_cell.grid(row=0, column=1, sticky="ew", padx=6, pady=8)
        name_cell.columnconfigure(0, weight=1)
        name_entry = entry(name_cell, name_var)
        name_entry.grid(row=0, column=0, sticky="ew")
        suggestion_frame = ctk.CTkFrame(
            name_cell,
            fg_color="#0a080b",
            corner_radius=10,
            border_width=1,
            border_color=border,
        )
        suggestion_frame.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        suggestion_frame.columnconfigure(0, weight=1)
        suggestion_frame.grid_remove()
        entry(row_frame, kills_var, width=78).grid(row=0, column=2, sticky="w", padx=6, pady=8)

        row: dict[str, Any] = {}

        def adjust(delta: int) -> None:
            kills_var.set(str(max(0, normalize_kill_value(kills_var.get()) + delta)))

        def remove() -> None:
            remove_manual_row(row)

        button(row_frame, "-", lambda: adjust(-1), "ghost", width=42).grid(row=0, column=3, padx=(6, 2), pady=8)
        button(row_frame, "+", lambda: adjust(1), "accent", width=42).grid(row=0, column=4, padx=2, pady=8)
        button(row_frame, "Remover", remove, "danger", width=92).grid(row=0, column=5, padx=(6, 12), pady=8)

        row.update(
            {
                "frame": row_frame,
                "index_label": index_label,
                "name_var": name_var,
                "name_entry": name_entry,
                "suggestion_frame": suggestion_frame,
                "kills_var": kills_var,
            }
        )
        manual_rows.append(row)
        name_var.trace_add(
            "write",
            lambda *_args, target_row=row: (on_manual_change(sort_rows=False), schedule_manual_name_suggestions(target_row)),
        )
        kills_var.trace_add("write", lambda *_args: on_manual_change(sort_rows=True))
        name_entry.bind("<FocusIn>", lambda _event, target_row=row: refresh_manual_name_suggestions(target_row))
        name_entry.bind("<FocusOut>", lambda _event, target_row=row: root.after(140, lambda: hide_manual_name_suggestions(target_row)))
        name_entry.bind("<Return>", lambda _event, target_row=row: select_first_manual_name_suggestion(target_row))
        if not manual_bulk_updating:
            update_manual_row_numbers()
            update_manual_metrics()
        if notify:
            on_manual_change()

    def add_or_increment_manual_player_all_scopes(name: str, kills: int) -> None:
        nonlocal manual_bulk_updating, manual_last_local_edit_at
        clean_name = re.sub(r"\s+", " ", str(name or "").strip())
        if not clean_name:
            return
        add_kills = normalize_kill_value(kills)
        active_scope = current_manual_scope()
        if active_scope not in {"daily", "general"}:
            active_scope = "daily"
        manual_scope_buffers[active_scope] = merge_manual_player_kills(collect_manual_players(scope=active_scope))
        clear_manual_reference_cache()

        previous_bulk_updating = manual_bulk_updating
        manual_bulk_updating = True
        try:
            for scope_key in ("daily", "general"):
                if scope_key == active_scope:
                    players = clone_player_list(manual_scope_buffers.get(scope_key, []))
                else:
                    players = manual_scope_display_players(scope_key, prefer_remote=True)
                players.append(PlayerKill(clean_name, add_kills, key=normalize_player_key(clean_name)))
                manual_scope_buffers[scope_key] = merge_manual_player_kills(players)
                clear_manual_reference_cache()
                manual_scope_dirty.add(scope_key)
                refresh_local_rank_from_manual_scope(scope_key)
        finally:
            manual_bulk_updating = previous_bulk_updating

        set_manual_players(manual_scope_buffers[active_scope], scope=active_scope)
        sync_kills_rank_tab_with_manual_scope(active_scope)
        clear_manual_metric_overrides()
        manual_last_local_edit_at = time.monotonic()
        schedule_kills_visual_refresh(delay_ms=80)
        update_manual_metrics()
        manual_status_var.set("Adicionado no diario e geral")
        try:
            schedule_manual_config_autosave()
        except NameError:
            pass

    def open_manual_kill_dialog() -> None:
        dialog = ctk.CTkToplevel(root)
        dialog.title("Adicionar jogador em Kills FF")
        dialog.geometry("560x460")
        dialog.minsize(460, 360)
        dialog.configure(fg_color=bg)
        try:
            dialog.transient(root)
            dialog.grab_set()
            dialog.lift()
            dialog.focus_force()
        except tk.TclError:
            pass
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        name_var = tk.StringVar(value="")
        kills_var = tk.StringVar(value="0")

        dialog_card = card(
            dialog,
            "Adicionar jogador",
            "Inclua o nick e as kills para o rank selecionado em Kills FF.",
        )
        dialog_card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        dialog_card.columnconfigure(1, weight=1)
        dialog_card.rowconfigure(3, weight=0)

        section_label(dialog_card, "Nick", 2)
        name_entry = entry(dialog_card, name_var)
        name_entry.grid(row=2, column=1, sticky="ew", padx=18, pady=(5, 2))
        suggestion_frame = ctk.CTkScrollableFrame(
            dialog_card,
            height=132,
            fg_color=field,
            corner_radius=8,
            border_width=1,
            border_color=border,
            scrollbar_button_color=chip_bg,
            scrollbar_button_hover_color=accent,
        )
        suggestion_frame.grid(row=3, column=1, sticky="nsew", padx=18, pady=(0, 5))
        suggestion_frame.columnconfigure(0, weight=1)
        suggestion_frame.grid_remove()
        section_label(dialog_card, "Kills", 4)
        entry(dialog_card, kills_var, width=100).grid(row=4, column=1, sticky="w", padx=18, pady=5)

        dialog_actions = ctk.CTkFrame(dialog_card, fg_color=panel, corner_radius=0)
        dialog_actions.grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 18))

        def hide_dialog_suggestions() -> None:
            for widget in suggestion_frame.winfo_children():
                try:
                    widget.destroy()
                except tk.TclError:
                    pass
            try:
                suggestion_frame.grid_remove()
            except tk.TclError:
                pass
            dialog_card.rowconfigure(3, weight=0)

        def apply_dialog_suggestion(selected_name: str) -> None:
            name_var.set(selected_name)
            hide_dialog_suggestions()
            try:
                name_entry.focus_set()
                name_entry.icursor(tk.END)
            except tk.TclError:
                pass

        def refresh_dialog_suggestions(*_args: Any) -> None:
            query = name_var.get().strip()
            if len(manual_autocomplete_key(query)) < 1:
                hide_dialog_suggestions()
                return
            suggestions = manual_existing_name_suggestions(query)
            for widget in suggestion_frame.winfo_children():
                try:
                    widget.destroy()
                except tk.TclError:
                    pass
            if not suggestions:
                hide_dialog_suggestions()
                return
            dialog_card.rowconfigure(3, weight=1)
            suggestion_frame.grid()
            ctk.CTkLabel(
                suggestion_frame,
                text="Jogadores ja lancados",
                text_color=muted,
                font=("Segoe UI Semibold", 11),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
            for index, (candidate_name, candidate_kills, score) in enumerate(suggestions, start=1):
                row = ctk.CTkFrame(
                    suggestion_frame,
                    fg_color="#211116" if index == 1 else "#151015",
                    corner_radius=8,
                    border_width=1 if index == 1 else 0,
                    border_color=accent,
                )
                row.grid(row=index, column=0, sticky="ew", padx=4, pady=(4 if index == 1 else 2, 2))
                row.columnconfigure(0, weight=1)
                suggestion_button = ctk.CTkButton(
                    row,
                    text=f"{candidate_name}   {candidate_kills} kill{'s' if candidate_kills != 1 else ''}",
                    command=lambda name=candidate_name: apply_dialog_suggestion(name),
                    height=32,
                    fg_color="transparent",
                    hover_color="#30151b",
                    text_color=fg,
                    anchor="w",
                    corner_radius=7,
                    font=("Segoe UI Semibold", 12),
                )
                suggestion_button.grid(row=0, column=0, sticky="ew", padx=3, pady=3)
                ctk.CTkLabel(
                    row,
                    text="inicio" if score >= 100 else "parecido",
                    text_color=teal if score >= 100 else muted,
                    font=("Segoe UI", 10),
                ).grid(row=0, column=1, sticky="e", padx=(4, 10), pady=3)

        def select_first_dialog_suggestion() -> bool:
            suggestions = manual_existing_name_suggestions(name_var.get().strip(), limit=1)
            if not suggestions:
                return False
            apply_dialog_suggestion(suggestions[0][0])
            return True

        def add_and_close() -> None:
            clean_name = name_var.get().strip()
            if not clean_name:
                messagebox.showinfo("Kills FF", "Informe o nick do jogador.")
                return
            add_or_increment_manual_player_all_scopes(clean_name, normalize_kill_value(kills_var.get()))
            try:
                dialog.destroy()
            except tk.TclError:
                pass

        button(dialog_actions, "Adicionar", add_and_close, "accent", width=120).pack(side=tk.LEFT, padx=(0, 8))
        button(dialog_actions, "Cancelar", dialog.destroy, "ghost", width=100).pack(side=tk.LEFT, padx=(0, 8))
        name_var.trace_add("write", refresh_dialog_suggestions)
        name_entry.focus_set()
        name_entry.bind("<FocusIn>", lambda _event: refresh_dialog_suggestions())
        name_entry.bind("<FocusOut>", lambda _event: root.after(140, hide_dialog_suggestions))
        name_entry.bind("<Return>", lambda _event: "break" if select_first_dialog_suggestion() else (add_and_close(), "break")[-1])

    def remove_manual_row(row: dict[str, Any]) -> None:
        if row not in manual_rows:
            return
        cancel_manual_name_suggestion_refresh(row)
        manual_rows.remove(row)
        row["frame"].destroy()
        if not manual_rows:
            add_manual_row(notify=False)
        update_manual_row_numbers()
        update_manual_metrics()
        on_manual_change()

    def cancel_manual_table_incremental_render() -> None:
        nonlocal manual_table_render_after_id, manual_table_render_generation, manual_table_render_signature
        manual_table_render_generation += 1
        manual_table_render_signature = None
        if manual_table_render_after_id is None:
            return
        try:
            root.after_cancel(manual_table_render_after_id)
        except tk.TclError:
            pass
        manual_table_render_after_id = None

    def apply_manual_row_player(row: dict[str, Any], index: int, player: PlayerKill) -> None:
        try:
            hide_manual_name_suggestions(row)
            set_text_var(row["name_var"], player.name)
            set_text_var(row["kills_var"], normalize_kill_value(player.kills))
            label_text = f"{index + 1:02d}"
            row_color = "#171014" if index % 2 == 0 else "#0f0b0e"
            if row.get("_grid_row") != index:
                row["frame"].grid(row=index, column=0, sticky="ew", padx=8, pady=4)
                row["_grid_row"] = index
            if row.get("_index_text") != label_text:
                row["index_label"].configure(text=label_text)
                row["_index_text"] = label_text
            if row.get("_row_color") != row_color:
                row["frame"].configure(fg_color=row_color)
                row["_row_color"] = row_color
        except tk.TclError:
            pass

    def start_incremental_manual_table_render(
        players: list[PlayerKill],
        minimum_rows: int,
        total_players: int | None,
        total_kills: int | None,
        scope: str,
    ) -> None:
        nonlocal manual_applying_remote, manual_bulk_updating, manual_remote_count_override, manual_remote_total_override
        nonlocal manual_table_render_after_id, manual_table_render_pending, manual_table_render_scope
        nonlocal manual_table_render_signature
        clean_scope = normalize_kills_scope_value(scope)
        if clean_scope not in {"daily", "general"}:
            clean_scope = "daily"
        snapshot_players = clone_player_list(players)
        target_rows = max(len(snapshot_players), minimum_rows)
        render_signature = (clean_scope, manual_signature(snapshot_players, clean_scope), target_rows)
        cancel_manual_table_incremental_render()
        render_generation = manual_table_render_generation
        manual_table_render_pending = True
        manual_table_render_scope = clean_scope
        manual_table_render_signature = None
        manual_remote_count_override = total_players
        manual_remote_total_override = total_kills

        while len(manual_rows) > target_rows:
            row = manual_rows.pop()
            try:
                row["frame"].destroy()
            except tk.TclError:
                pass

        def render_chunk(start_index: int = 0) -> None:
            nonlocal manual_applying_remote, manual_bulk_updating, manual_table_render_after_id
            nonlocal manual_table_render_pending, manual_table_render_scope
            nonlocal manual_table_render_signature
            manual_table_render_after_id = None
            if app_closing or render_generation != manual_table_render_generation:
                return
            end_index = min(target_rows, start_index + MANUAL_TABLE_RENDER_CHUNK_SIZE)
            previous_applying_remote = manual_applying_remote
            previous_bulk_updating = manual_bulk_updating
            manual_applying_remote = True
            manual_bulk_updating = True
            try:
                while len(manual_rows) < end_index:
                    add_manual_row(notify=False)
                for index in range(start_index, end_index):
                    player = snapshot_players[index] if index < len(snapshot_players) else PlayerKill("", 0)
                    apply_manual_row_player(manual_rows[index], index, player)
            finally:
                manual_bulk_updating = previous_bulk_updating
                manual_applying_remote = previous_applying_remote

            if end_index < target_rows:
                manual_table_render_after_id = root.after(
                    MANUAL_TABLE_RENDER_CHUNK_DELAY_MS,
                    lambda next_index=end_index: render_chunk(next_index),
                )
                return

            update_manual_row_numbers()
            if manual_table_render_scope == clean_scope:
                manual_table_render_pending = False
                manual_table_render_scope = ""
            manual_table_render_signature = render_signature
            if not manual_bulk_updating:
                update_manual_metrics(snapshot_players)

        manual_table_render_after_id = root.after(0, render_chunk)

    def set_manual_players(
        players: list[PlayerKill],
        minimum_rows: int = 8,
        total_players: int | None = None,
        total_kills: int | None = None,
        scope: str | None = None,
        force_render: bool = False,
    ) -> None:
        nonlocal manual_applying_remote, manual_bulk_updating, manual_remote_count_override, manual_remote_total_override
        nonlocal manual_table_render_pending, manual_table_render_scope
        nonlocal manual_table_render_signature
        previous_bulk_updating = manual_bulk_updating
        manual_applying_remote = True
        manual_bulk_updating = True
        manual_remote_count_override = total_players
        manual_remote_total_override = total_kills
        try:
            clean_scope = normalize_kills_scope_value(scope or current_manual_scope())
            if clean_scope not in {"daily", "general"}:
                clean_scope = current_manual_scope()
            players = merge_manual_player_kills(complete_manual_player_names(players, clean_scope))
            manual_scope_buffers[clean_scope] = clone_player_list(players)
            clear_manual_reference_cache()
            if not force_render and not is_kills_ff_tab_active():
                cancel_manual_table_incremental_render()
                for row in manual_rows:
                    row["frame"].destroy()
                manual_rows.clear()
                manual_table_render_pending = True
                manual_table_render_scope = clean_scope
                manual_table_render_signature = None
                return
            target_rows = max(len(players), minimum_rows)
            render_signature = (clean_scope, manual_signature(players, clean_scope), target_rows)
            skip_render = (
                not force_render
                and not manual_table_render_pending
                and manual_table_render_after_id is None
                and manual_table_render_signature == render_signature
                and len(manual_rows) == target_rows
            )
            if skip_render:
                manual_bulk_updating = previous_bulk_updating
                manual_applying_remote = False
                if not manual_bulk_updating:
                    update_manual_metrics(players)
                return
            widget_delta = abs(len(manual_rows) - target_rows)
            if target_rows >= MANUAL_TABLE_INCREMENTAL_THRESHOLD and widget_delta > MANUAL_TABLE_RENDER_CHUNK_SIZE:
                start_incremental_manual_table_render(players, minimum_rows, total_players, total_kills, clean_scope)
                return
            cancel_manual_table_incremental_render()
            while len(manual_rows) > target_rows:
                row = manual_rows.pop()
                try:
                    row["frame"].destroy()
                except tk.TclError:
                    pass
            while len(manual_rows) < target_rows:
                add_manual_row(notify=False)
            for index, row in enumerate(manual_rows):
                player = players[index] if index < len(players) else PlayerKill("", 0)
                apply_manual_row_player(row, index, player)
            update_manual_row_numbers()
            if manual_table_render_scope == clean_scope:
                manual_table_render_pending = False
                manual_table_render_scope = ""
            manual_table_render_signature = render_signature
        finally:
            manual_bulk_updating = previous_bulk_updating
            manual_applying_remote = False
        if not manual_bulk_updating:
            update_manual_metrics()

    def clear_manual_table() -> None:
        set_manual_players([])
        manual_status_var.set("Tabela limpa")
        on_manual_change()

    def reset_manual_kills() -> None:
        dialog = ctk.CTkToplevel(root)
        dialog.title("Zerar Kills FF")
        dialog.geometry("420x260")
        dialog.minsize(380, 240)
        dialog.configure(fg_color=bg)
        try:
            dialog.transient(root)
            dialog.grab_set()
            dialog.lift()
            dialog.focus_force()
        except tk.TclError:
            pass
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)
        reset_card = card(dialog, "Zerar Kills FF", "Escolha qual ranking do Jarvis deve ser zerado.")
        reset_card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        reset_actions = ctk.CTkFrame(reset_card, fg_color=panel, corner_radius=0)
        reset_actions.grid(row=2, column=0, columnspan=4, sticky="ew", padx=18, pady=(14, 18))
        for column in range(3):
            reset_actions.columnconfigure(column, weight=1)

        def choose_reset(action: str) -> None:
            try:
                dialog.destroy()
            except tk.TclError:
                pass
            apply_kills_admin_action(action)

        button(reset_actions, "Diario", lambda: choose_reset("reset_daily"), "danger", width=1).grid(
            row=0, column=0, sticky="ew", padx=(0, 6), pady=4
        )
        button(reset_actions, "Geral", lambda: choose_reset("reset_general"), "danger", width=1).grid(
            row=0, column=1, sticky="ew", padx=6, pady=4
        )
        button(reset_actions, "Cancelar", dialog.destroy, "ghost", width=1).grid(
            row=0, column=2, sticky="ew", padx=(6, 0), pady=4
        )

    def queue_summary_items(entries: list[FFQueueEntry]) -> list[dict[str, Any]]:
        grouped: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for entry_item in entries:
            name = entry_item.name.strip()
            status = normalize_queue_status(entry_item.status)
            if not name or status == "Concluido":
                continue
            key = ff_queue_merge_key(entry_item)
            if key not in grouped:
                grouped[key] = {
                    "name": name,
                    "rooms": 0,
                    "waiting": 0,
                    "called": 0,
                    "playing": 0,
                    "ff_player_id": str(entry_item.ff_player_id or "").strip(),
                    "panel_user_id": str(entry_item.panel_user_id or entry_item.user_id or "").strip(),
                }
                order.append(key)
            rooms = max(1, normalize_kill_value(entry_item.rooms))
            grouped[key]["rooms"] += rooms
            if entry_item.ff_player_id and not grouped[key]["ff_player_id"]:
                grouped[key]["ff_player_id"] = str(entry_item.ff_player_id).strip()
            if (entry_item.panel_user_id or entry_item.user_id) and not grouped[key]["panel_user_id"]:
                grouped[key]["panel_user_id"] = str(entry_item.panel_user_id or entry_item.user_id).strip()
            if status == "Jogando":
                grouped[key]["playing"] += rooms
            elif status == "Chamado":
                grouped[key]["called"] += rooms
            else:
                grouped[key]["waiting"] += rooms
        return sorted(
            (grouped[key] for key in order),
            key=lambda item: (-int(item["rooms"]), normalize_player_key(str(item["name"]))),
        )

    def refresh_ff_queue_summary(entries: list[FFQueueEntry] | None = None) -> None:
        if ff_queue_site_sync_hidden:
            return
        items = queue_summary_items(entries if entries is not None else collect_ff_queue_entries())
        signature = [("__totals__", ff_queue_remote_count_override, ff_queue_remote_rooms_override)] + [
            (
                item["name"],
                item["rooms"],
                item["waiting"],
                item["called"],
                item["playing"],
                item.get("ff_player_id", ""),
                item.get("panel_user_id", ""),
            )
            for item in items
        ]
        if getattr(refresh_ff_queue_summary, "_signature", None) == signature:
            return
        refresh_ff_queue_summary._signature = signature  # type: ignore[attr-defined]

        for widget in ff_queue_summary_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        ff_queue_summary_widgets.clear()

        summary_count = ff_queue_remote_count_override if ff_queue_remote_count_override is not None else len(items)
        summary_rooms = ff_queue_remote_rooms_override if ff_queue_remote_rooms_override is not None else sum(int(item["rooms"]) for item in items)
        set_text_var(ff_queue_summary_count_var, summary_count)
        set_text_var(ff_queue_summary_rooms_var, summary_rooms)

        if not items:
            empty = ctk.CTkLabel(
                ff_queue_summary_frame,
                text="Nenhuma sala pendente na fila.",
                text_color=muted,
                font=("Segoe UI", 12),
                anchor="w",
            )
            empty.grid(row=0, column=0, sticky="ew", padx=12, pady=14)
            ff_queue_summary_widgets.append(empty)
            return

        for index, item in enumerate(items[:80], start=1):
            row_frame = ctk.CTkFrame(
                ff_queue_summary_frame,
                fg_color="#171014" if index % 2 else "#0f0b0e",
                corner_radius=10,
            )
            row_frame.grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
            row_frame.columnconfigure(1, weight=1)
            medal_color = accent if index <= 3 else muted
            ctk.CTkLabel(
                row_frame,
                text=f"{index:02d}",
                text_color=medal_color,
                font=("Segoe UI Semibold", 12),
                width=36,
            ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(10, 6), pady=8)
            ctk.CTkLabel(
                row_frame,
                text=str(item["name"]),
                text_color=fg,
                font=("Segoe UI Semibold", 12),
                anchor="w",
            ).grid(row=0, column=1, sticky="ew", padx=4, pady=(8, 0))
            detail_parts = []
            if item.get("panel_user_id"):
                detail_parts.append(f"ID {item['panel_user_id']}")
            if item.get("ff_player_id"):
                detail_parts.append(f"ID FF {item['ff_player_id']}")
            if item.get("waiting"):
                detail_parts.append(f"{item['waiting']} aguardando")
            if item.get("called"):
                detail_parts.append(f"{item['called']} chamado")
            if item.get("playing"):
                detail_parts.append(f"{item['playing']} jogando")
            ctk.CTkLabel(
                row_frame,
                text=" | ".join(detail_parts) or "-",
                text_color=muted,
                font=("Segoe UI", 10),
                anchor="w",
            ).grid(row=1, column=1, sticky="ew", padx=4, pady=(0, 8))
            ctk.CTkLabel(
                row_frame,
                text=str(item["rooms"]),
                text_color=teal,
                font=("Segoe UI Semibold", 18),
                width=50,
            ).grid(row=0, column=2, rowspan=2, sticky="e", padx=(8, 12), pady=8)
            ff_queue_summary_widgets.append(row_frame)

    def ff_queue_signature(entries: list[FFQueueEntry]) -> str:
        digest = hashlib.sha1()
        for entry in entries:
            update_digest_part(digest, entry.name)
            update_digest_part(digest, entry.note)
            update_digest_part(digest, entry.status)
            update_digest_part(digest, normalize_kill_value(entry.rooms))
            update_digest_part(digest, entry.user_id)
            update_digest_part(digest, entry.panel_user_id)
            update_digest_part(digest, entry.ff_player_id)
        update_digest_part(digest, len(entries))
        return digest.hexdigest()

    def clone_ff_queue_entries(entries: list[FFQueueEntry]) -> list[FFQueueEntry]:
        return [
            FFQueueEntry(
                name=entry.name,
                note=entry.note,
                status=entry.status,
                rooms=normalize_kill_value(entry.rooms),
                user_id=entry.user_id,
                panel_user_id=entry.panel_user_id,
                ff_player_id=entry.ff_player_id,
            )
            for entry in entries
        ]

    def ff_queue_poll_interval_seconds() -> int:
        try:
            value = int(float(ff_queue_poll_seconds_var.get().replace(",", ".")))
        except ValueError:
            value = 15
        return max(10, min(120, value))

    def collect_ff_queue_entries() -> list[FFQueueEntry]:
        if ff_queue_render_pending and not is_ff_queue_tab_active():
            return clone_ff_queue_entries(ff_queue_cached_entries)
        entries: list[FFQueueEntry] = []
        for row in ff_queue_rows:
            name = row["name_var"].get().strip()
            if not name:
                continue
            entries.append(
                FFQueueEntry(
                    name=name,
                    note=row["note_var"].get().strip(),
                    status=normalize_queue_status(row["status_var"].get()),
                    rooms=max(1, normalize_kill_value(row["rooms_var"].get())),
                    user_id=str(row.get("user_id", "") or "").strip(),
                    panel_user_id=str(row.get("panel_user_id", "") or "").strip(),
                    ff_player_id=str(row.get("ff_player_id", "") or "").strip(),
                )
            )
        return merge_ff_queue_entries(entries)

    def update_ff_queue_metrics() -> None:
        if ff_queue_site_sync_hidden:
            return
        entries = collect_ff_queue_entries()
        count_value = (
            ff_queue_remote_count_override
            if ff_queue_remote_count_override is not None
            else sum(1 for entry in entries if entry.status != "Concluido")
        )
        set_text_var(ff_queue_count_var, count_value)
        set_text_var(ff_queue_playing_var, sum(1 for entry in entries if entry.status == "Jogando"))
        refresh_ff_queue_summary(entries)

    def clear_ff_queue_metric_overrides() -> None:
        nonlocal ff_queue_remote_count_override, ff_queue_remote_rooms_override
        ff_queue_remote_count_override = None
        ff_queue_remote_rooms_override = None

    def update_ff_queue_row_numbers() -> None:
        for index, row in enumerate(ff_queue_rows, start=1):
            row["frame"].grid(row=index - 1, column=0, sticky="ew", padx=8, pady=4)
            row["index_label"].configure(text=f"{index:02d}")

    def schedule_ff_queue_sync(delay_ms: int = 700) -> None:
        nonlocal ff_queue_sync_after_id
        if app_closing or ff_queue_site_sync_hidden:
            return
        if ff_queue_applying_remote or not ff_queue_enabled_var.get():
            return
        if ff_queue_sync_after_id is not None:
            try:
                root.after_cancel(ff_queue_sync_after_id)
            except tk.TclError:
                pass
        ff_queue_sync_after_id = root.after(delay_ms, lambda: send_ff_queue(force=False))

    def on_ff_queue_change(*_args: Any) -> None:
        nonlocal ff_queue_last_local_edit_at
        if ff_queue_applying_remote:
            return
        clear_ff_queue_metric_overrides()
        ff_queue_last_local_edit_at = time.monotonic()
        update_ff_queue_metrics()
        ff_queue_status_var.set("Editando")
        try:
            schedule_config_autosave()
        except NameError:
            pass
        schedule_ff_queue_sync()

    def ff_queue_row_entry(row: dict[str, Any]) -> FFQueueEntry:
        return FFQueueEntry(
            name=row["name_var"].get().strip(),
            note=row["note_var"].get().strip(),
            status=normalize_queue_status(row["status_var"].get()),
            rooms=max(0, normalize_kill_value(row["rooms_var"].get())),
            user_id=str(row.get("user_id", "") or "").strip(),
            panel_user_id=str(row.get("panel_user_id", "") or "").strip(),
            ff_player_id=str(row.get("ff_player_id", "") or "").strip(),
        )

    def ff_queue_row_has_remote_identity(row: dict[str, Any]) -> bool:
        entry_item = ff_queue_row_entry(row)
        return bool(entry_item.user_id or entry_item.panel_user_id or entry_item.ff_player_id)

    def run_ff_queue_remote_action(
        action: str,
        row: dict[str, Any] | None = None,
        entry: FFQueueEntry | None = None,
        credits: int | None = None,
        fallback: callable | None = None,
        label: str = "",
    ) -> bool:
        if ff_queue_site_sync_hidden:
            if fallback is not None:
                fallback()
            return False
        if row is not None and not ff_queue_row_has_remote_identity(row):
            if fallback is not None:
                fallback()
            return False
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return False
        endpoint_url = local_config.get("ff_queue_realtime_url", "").strip()
        if not endpoint_url:
            if fallback is not None:
                fallback()
            return False

        entry_item = entry if entry is not None else (ff_queue_row_entry(row) if row is not None else None)
        ff_queue_status_var.set(label or "Aplicando")

        def run() -> None:
            try:
                state = send_ff_queue_action_update(
                    endpoint_url,
                    action,
                    entry=entry_item,
                    credits=credits,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("ff_queue_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_ff_queue_event("action_done", {"state": state, "action": action, "label": label or action})
            except Exception as exc:
                enqueue_ff_queue_event("action_error", {"error": str(exc), "action": action, "label": label or action})

        start_ff_queue_worker(run, name="AizenFFQueueAction")
        return True

    def clear_ff_queue_manual_form() -> None:
        ff_queue_manual_name_var.set("")
        ff_queue_manual_user_id_var.set("")
        ff_queue_manual_ff_id_var.set("")
        ff_queue_manual_rooms_var.set("1")

    def add_ff_queue_manual_member() -> None:
        name = ff_queue_manual_name_var.get().strip()
        user_id = ff_queue_manual_user_id_var.get().strip()
        raw_ff_id = ff_queue_manual_ff_id_var.get().strip()
        ff_player_id = re.sub(r"\D+", "", raw_ff_id)
        if raw_ff_id and not re.fullmatch(r"\d{5,15}", ff_player_id):
            messagebox.showerror("Fila FF", "ID FF inválido. Use somente números, de 5 a 15 dígitos.")
            return
        rooms = max(1, min(9999, normalize_kill_value(ff_queue_manual_rooms_var.get())))
        ff_queue_manual_rooms_var.set(str(rooms))
        if not name and not user_id and not ff_player_id:
            messagebox.showinfo("Fila FF", "Informe pelo menos nome, ID do membro ou ID FF.")
            return
        display_name = name or (f"ID FF {ff_player_id}" if ff_player_id else user_id)
        entry_item = FFQueueEntry(
            display_name,
            "",
            "Na fila",
            rooms=rooms,
            user_id=user_id,
            ff_player_id=ff_player_id,
        )

        def fallback() -> None:
            add_ff_queue_row(
                display_name,
                "",
                "Na fila",
                rooms,
                user_id=user_id,
                ff_player_id=ff_player_id,
            )
            ff_queue_status_var.set("Adicionado localmente")
            clear_ff_queue_manual_form()

        if run_ff_queue_remote_action(
            "add_member",
            entry=entry_item,
            credits=rooms,
            fallback=fallback,
            label="Adicionando jogador",
        ):
            clear_ff_queue_manual_form()

    def open_ff_queue_manual_dialog() -> None:
        dialog = ctk.CTkToplevel(root)
        dialog.title("Adicionar jogador na Fila FF")
        dialog.geometry("520x430")
        dialog.minsize(460, 380)
        dialog.configure(fg_color=bg)
        try:
            dialog.transient(root)
            dialog.grab_set()
            dialog.focus_force()
        except tk.TclError:
            pass
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        dialog_card = card(
            dialog,
            "Adicionar jogador",
            "Informe os dados que serão enviados para a Fila FF do Jarvis.",
        )
        dialog_card.grid(row=0, column=0, sticky="nsew", padx=16, pady=16)
        dialog_card.columnconfigure(1, weight=1)

        section_label(dialog_card, "Nome", 2)
        entry(dialog_card, ff_queue_manual_name_var).grid(row=2, column=1, sticky="ew", padx=18, pady=5)
        section_label(dialog_card, "ID membro", 3)
        entry(dialog_card, ff_queue_manual_user_id_var).grid(row=3, column=1, sticky="ew", padx=18, pady=5)
        section_label(dialog_card, "ID FF", 4)
        entry(dialog_card, ff_queue_manual_ff_id_var).grid(row=4, column=1, sticky="ew", padx=18, pady=5)
        section_label(dialog_card, "Salas", 5)
        entry(dialog_card, ff_queue_manual_rooms_var, width=100).grid(row=5, column=1, sticky="w", padx=18, pady=5)

        dialog_actions = ctk.CTkFrame(dialog_card, fg_color=panel, corner_radius=0)
        dialog_actions.grid(row=6, column=0, columnspan=2, sticky="ew", padx=18, pady=(16, 18))

        def add_and_close() -> None:
            before_name = ff_queue_manual_name_var.get().strip()
            before_user_id = ff_queue_manual_user_id_var.get().strip()
            before_ff_id = ff_queue_manual_ff_id_var.get().strip()
            add_ff_queue_manual_member()
            still_has_input = any(
                (
                    ff_queue_manual_name_var.get().strip(),
                    ff_queue_manual_user_id_var.get().strip(),
                    ff_queue_manual_ff_id_var.get().strip(),
                )
            )
            if (before_name or before_user_id or before_ff_id) and not still_has_input:
                try:
                    dialog.destroy()
                except tk.TclError:
                    pass

        button(dialog_actions, "Adicionar no Jarvis", add_and_close, "accent", width=150).pack(side=tk.LEFT, padx=(0, 8))
        button(dialog_actions, "Limpar", clear_ff_queue_manual_form, "ghost", width=82).pack(side=tk.LEFT, padx=(0, 8))
        button(dialog_actions, "Cancelar", dialog.destroy, "danger", width=82).pack(side=tk.LEFT)

    def adjust_ff_queue_rooms(row: dict[str, Any], delta: int) -> None:
        if row not in ff_queue_rows:
            return
        current = max(1, normalize_kill_value(row["rooms_var"].get()))
        next_value = max(0, current + delta)
        action = "add_credit" if delta > 0 else "remove_credit"
        if next_value <= 0:
            run_ff_queue_remote_action(action, row=row, credits=abs(delta), label="Atualizando salas")
            remove_ff_queue_row_local(row)
            return
        row["rooms_var"].set(str(next_value))
        run_ff_queue_remote_action(action, row=row, credits=abs(delta), label="Atualizando salas")

    def move_ff_queue_row(row: dict[str, Any], delta: int) -> None:
        if row not in ff_queue_rows:
            return
        remote_action = "move_up" if delta < 0 else "move_down"
        if run_ff_queue_remote_action(remote_action, row=row, label="Reordenando fila"):
            return
        index = ff_queue_rows.index(row)
        new_index = max(0, min(len(ff_queue_rows) - 1, index + delta))
        if index == new_index:
            return
        ff_queue_rows[index], ff_queue_rows[new_index] = ff_queue_rows[new_index], ff_queue_rows[index]
        update_ff_queue_row_numbers()
        on_ff_queue_change()

    def move_ff_queue_row_to(row: dict[str, Any], target: str) -> None:
        if row not in ff_queue_rows:
            return
        target = "top" if str(target).lower() == "top" else "bottom"
        remote_action = "move_top" if target == "top" else "move_bottom"
        if run_ff_queue_remote_action(remote_action, row=row, label="Reordenando fila"):
            return
        ff_queue_rows.remove(row)
        if target == "top":
            ff_queue_rows.insert(0, row)
        else:
            ff_queue_rows.append(row)
        update_ff_queue_row_numbers()
        on_ff_queue_change()

    def save_ff_queue_row_name(row: dict[str, Any]) -> None:
        if row not in ff_queue_rows:
            return
        name = row["name_var"].get().strip()
        if not name:
            messagebox.showinfo("Fila FF", "Informe o nome do jogador.")
            return
        if run_ff_queue_remote_action("set_name", row=row, label="Salvando nome"):
            return
        ff_queue_status_var.set("Nome salvo localmente")
        on_ff_queue_change()

    def edit_ff_queue_ff_id(row: dict[str, Any]) -> None:
        if row not in ff_queue_rows:
            return
        current = str(row.get("ff_player_id", "") or "").strip()
        value = simpledialog.askstring(
            "ID Free Fire",
            f"ID FF de {row['name_var'].get().strip() or 'jogador'}:",
            initialvalue=current,
            parent=root,
        )
        if value is None:
            return
        clean = re.sub(r"\D+", "", str(value or "").strip())
        if value.strip() and not re.fullmatch(r"\d{5,15}", clean):
            messagebox.showerror("Fila FF", "ID FF inválido. Use somente números, de 5 a 15 dígitos.")
            return
        row["ff_player_id"] = clean
        id_var = row.get("ff_player_id_var")
        if id_var is not None:
            id_var.set(clean or "-")
        if run_ff_queue_remote_action("set_ff_id", row=row, label="Salvando ID FF"):
            return
        ff_queue_status_var.set("ID FF salvo localmente")
        on_ff_queue_change()

    def set_ff_queue_rooms_prompt(row: dict[str, Any]) -> None:
        if row not in ff_queue_rows:
            return
        current = max(0, normalize_kill_value(row["rooms_var"].get()))
        value = simpledialog.askinteger(
            "Definir salas",
            f"Quantidade de salas de {row['name_var'].get().strip() or 'jogador'}:",
            initialvalue=current,
            minvalue=0,
            maxvalue=9999,
            parent=root,
        )
        if value is None:
            return
        if value <= 0:
            run_ff_queue_remote_action("set_credit", row=row, credits=value, label="Definindo salas")
            remove_ff_queue_row_local(row)
            return
        row["rooms_var"].set(str(value))
        run_ff_queue_remote_action("set_credit", row=row, credits=value, label="Definindo salas")

    def add_ff_queue_row(
        name: str = "",
        note: str = "",
        status: str = "Na fila",
        rooms: int = 1,
        notify: bool = True,
        user_id: str = "",
        panel_user_id: str = "",
        ff_player_id: str = "",
    ) -> None:
        if ff_queue_site_sync_hidden or ff_queue_table_frame is None:
            return
        row_index = len(ff_queue_rows)
        row_frame = ctk.CTkFrame(
            ff_queue_table_frame,
            fg_color="#171014" if row_index % 2 == 0 else "#0f0b0e",
            corner_radius=12,
        )
        row_frame.columnconfigure(1, weight=2)
        row_frame.columnconfigure(2, weight=1)

        index_label = ctk.CTkLabel(
            row_frame,
            text=f"{row_index + 1:02d}",
            text_color=muted,
            font=("Segoe UI Semibold", 12),
            width=38,
        )
        index_label.grid(row=0, column=0, sticky="w", padx=(12, 6), pady=8)

        name_var = tk.StringVar(value=name)
        note_var = tk.StringVar(value=note)
        status_var = tk.StringVar(value=normalize_queue_status(status))
        rooms_var = tk.StringVar(value=str(max(1, normalize_kill_value(rooms))))
        panel_user_id_var = tk.StringVar(value=str(panel_user_id or user_id or "-").strip() or "-")
        ff_player_id_var = tk.StringVar(value=str(ff_player_id or "-").strip() or "-")
        entry(row_frame, name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=8)
        entry(row_frame, note_var).grid(row=0, column=2, sticky="ew", padx=6, pady=8)
        entry(row_frame, rooms_var, width=72).grid(row=0, column=3, sticky="w", padx=6, pady=8)
        combo(row_frame, status_var, FF_QUEUE_STATUSES, width=130).grid(row=0, column=4, sticky="w", padx=6, pady=8)

        row: dict[str, Any] = {}

        def remove() -> None:
            remove_ff_queue_row(row)

        action_bar = ctk.CTkFrame(row_frame, fg_color="transparent", corner_radius=0)
        action_bar.grid(row=1, column=1, columnspan=4, sticky="ew", padx=6, pady=(0, 10))
        action_bar.columnconfigure(1, weight=1)
        action_bar.columnconfigure(3, weight=1)
        ctk.CTkLabel(
            action_bar,
            text="ID membro",
            text_color=muted,
            font=("Segoe UI Semibold", 11),
        ).grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkLabel(
            action_bar,
            textvariable=panel_user_id_var,
            text_color=fg,
            font=("Segoe UI", 11),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=2)
        ctk.CTkLabel(
            action_bar,
            text="ID FF",
            text_color=muted,
            font=("Segoe UI Semibold", 11),
        ).grid(row=0, column=2, sticky="w", padx=(0, 6), pady=2)
        ctk.CTkLabel(
            action_bar,
            textvariable=ff_player_id_var,
            text_color=fg,
            font=("Segoe UI", 11),
            anchor="w",
        ).grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=2)
        button(action_bar, "Salvar nome", lambda: save_ff_queue_row_name(row), "default", width=94).grid(row=0, column=4, padx=2, pady=2)
        button(action_bar, "ID FF", lambda: edit_ff_queue_ff_id(row), "default", width=62).grid(row=0, column=5, padx=2, pady=2)
        button(action_bar, "Topo", lambda: move_ff_queue_row_to(row, "top"), "ghost", width=58).grid(row=1, column=0, padx=(0, 2), pady=2)
        button(action_bar, "↑", lambda: move_ff_queue_row(row, -1), "ghost", width=38).grid(row=1, column=1, sticky="w", padx=2, pady=2)
        button(action_bar, "↓", lambda: move_ff_queue_row(row, 1), "ghost", width=38).grid(row=1, column=2, sticky="w", padx=2, pady=2)
        button(action_bar, "Final", lambda: move_ff_queue_row_to(row, "bottom"), "ghost", width=58).grid(row=1, column=3, sticky="w", padx=2, pady=2)
        button(action_bar, "+1", lambda: adjust_ff_queue_rooms(row, 1), "accent", width=44).grid(row=1, column=4, padx=2, pady=2)
        button(action_bar, "-1", lambda: adjust_ff_queue_rooms(row, -1), "ghost", width=44).grid(row=1, column=5, padx=2, pady=2)
        button(action_bar, "Definir", lambda: set_ff_queue_rooms_prompt(row), "default", width=70).grid(row=1, column=6, padx=2, pady=2)
        button(action_bar, "Remover", remove, "danger", width=86).grid(row=1, column=7, padx=(2, 0), pady=2)

        row.update(
            {
                "frame": row_frame,
                "index_label": index_label,
                "name_var": name_var,
                "note_var": note_var,
                "rooms_var": rooms_var,
                "status_var": status_var,
                "user_id": str(user_id or "").strip(),
                "panel_user_id": str(panel_user_id or "").strip(),
                "panel_user_id_var": panel_user_id_var,
                "ff_player_id": str(ff_player_id or "").strip(),
                "ff_player_id_var": ff_player_id_var,
            }
        )
        ff_queue_rows.append(row)
        name_var.trace_add("write", on_ff_queue_change)
        note_var.trace_add("write", on_ff_queue_change)
        rooms_var.trace_add("write", on_ff_queue_change)
        status_var.trace_add("write", on_ff_queue_change)
        update_ff_queue_row_numbers()
        update_ff_queue_metrics()
        if notify:
            on_ff_queue_change()

    def remove_ff_queue_row_local(row: dict[str, Any]) -> None:
        if row not in ff_queue_rows:
            return
        ff_queue_rows.remove(row)
        row["frame"].destroy()
        update_ff_queue_row_numbers()
        update_ff_queue_metrics()
        on_ff_queue_change()

    def remove_ff_queue_row(row: dict[str, Any]) -> None:
        if row not in ff_queue_rows:
            return
        if run_ff_queue_remote_action("remove_member", row=row, label="Removendo jogador"):
            return
        remove_ff_queue_row_local(row)

    def set_ff_queue_entries(
        entries: list[FFQueueEntry],
        minimum_rows: int = 0,
        total_members: int | None = None,
        total_credits: int | None = None,
    ) -> None:
        nonlocal ff_queue_applying_remote, ff_queue_remote_count_override, ff_queue_remote_rooms_override
        nonlocal ff_queue_cached_entries, ff_queue_render_pending, ff_queue_render_minimum_rows
        normalized_entries = clone_ff_queue_entries(merge_ff_queue_entries(entries))
        next_signature = (
            ff_queue_signature(normalized_entries),
            int(minimum_rows),
            total_members,
            total_credits,
        )
        current_signature = getattr(set_ff_queue_entries, "_signature", None)
        if current_signature == next_signature and not ff_queue_render_pending:
            ff_queue_remote_count_override = total_members
            ff_queue_remote_rooms_override = total_credits
            return
        ff_queue_cached_entries = clone_ff_queue_entries(normalized_entries)
        set_ff_queue_entries._signature = next_signature  # type: ignore[attr-defined]
        if ff_queue_site_sync_hidden:
            ff_queue_remote_count_override = total_members
            ff_queue_remote_rooms_override = total_credits
            return
        if not is_ff_queue_tab_active():
            ff_queue_remote_count_override = total_members
            ff_queue_remote_rooms_override = total_credits
            ff_queue_render_pending = True
            ff_queue_render_minimum_rows = int(minimum_rows)
            summary_entries = clone_ff_queue_entries(normalized_entries)
            summary_count = (
                ff_queue_remote_count_override
                if ff_queue_remote_count_override is not None
                else sum(1 for entry in summary_entries if entry.status != "Concluido")
            )
            set_text_var(ff_queue_count_var, summary_count)
            set_text_var(ff_queue_playing_var, sum(1 for entry in summary_entries if entry.status == "Jogando"))
            return
        ff_queue_applying_remote = True
        try:
            ff_queue_remote_count_override = total_members
            ff_queue_remote_rooms_override = total_credits
            ff_queue_render_pending = False
            ff_queue_render_minimum_rows = 0
            for row in ff_queue_rows:
                row["frame"].destroy()
            ff_queue_rows.clear()
            for entry_item in normalized_entries:
                add_ff_queue_row(
                    entry_item.name,
                    entry_item.note,
                    entry_item.status,
                    entry_item.rooms,
                    notify=False,
                    user_id=entry_item.user_id,
                    panel_user_id=entry_item.panel_user_id,
                    ff_player_id=entry_item.ff_player_id,
                )
            while len(ff_queue_rows) < minimum_rows:
                add_ff_queue_row(notify=False)
            update_ff_queue_row_numbers()
            update_ff_queue_metrics()
        finally:
            ff_queue_applying_remote = False

    def clear_ff_queue() -> None:
        if run_ff_queue_remote_action("clear_queue", label="Limpando fila"):
            return
        set_ff_queue_entries([])
        ff_queue_status_var.set("Fila limpa")
        on_ff_queue_change()

    def call_next_ff_queue() -> None:
        if run_ff_queue_remote_action("serve_next", label="Atendendo proximo"):
            return
        next_entries, served, remaining = serve_next_queue_entries(collect_ff_queue_entries())
        if served is None:
            messagebox.showinfo("Fila FF", "Nao ha jogadores aguardando na fila.")
            return
        set_ff_queue_entries(next_entries)
        ff_queue_status_var.set(f"Atendido: {served.name} ({remaining} sala(s) restantes)")
        on_ff_queue_change()

    def mark_called_playing() -> None:
        for row in ff_queue_rows:
            if row["name_var"].get().strip() and normalize_queue_status(row["status_var"].get()) == "Chamado":
                row["status_var"].set("Jogando")
                ff_queue_status_var.set("Jogador em partida")
                return
        messagebox.showinfo("Fila FF", "Nao ha jogador chamado para marcar como jogando.")

    def finish_playing_ff_queue() -> None:
        changed = False
        for row in ff_queue_rows:
            if row["name_var"].get().strip() and normalize_queue_status(row["status_var"].get()) == "Jogando":
                row["status_var"].set("Concluido")
                changed = True
        if changed:
            ff_queue_status_var.set("Partida finalizada")
        else:
            messagebox.showinfo("Fila FF", "Nao ha jogador marcado como jogando.")

    def ff_overlay_site_endpoint() -> str:
        endpoint_url = normalize_endpoint_url(ff_overlay_config_url_var.get())
        if endpoint_url:
            return derive_ff_overlay_config_endpoint(endpoint_url)
        realtime_url = normalize_endpoint_url(ff_overlay_url_var.get())
        if realtime_url:
            return derive_ff_overlay_config_endpoint(realtime_url)
        base_url = normalize_endpoint_url(jarvis_base_url_var.get()).rstrip("/")
        if base_url:
            return derive_ff_overlay_config_endpoint(base_url)
        return ""

    def ff_overlay_site_int(var: tk.StringVar, default: int, min_value: int, max_value: int) -> int:
        try:
            value = int(float(var.get().replace(",", ".")))
        except ValueError:
            value = default
        value = max(min_value, min(max_value, value))
        var.set(str(value))
        return value

    def ff_overlay_site_color(var: tk.StringVar, default: str) -> str:
        value = normalize_hex_color(var.get(), default)
        var.set(value)
        return value

    def apply_ff_overlay_site_config(payload: dict[str, Any]) -> None:
        nonlocal ff_overlay_site_profiles, ff_overlay_site_last_config
        cfg = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        ff_overlay_site_last_config = dict(cfg)
        profiles = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
        ff_overlay_site_profiles = [item for item in profiles if isinstance(item, dict)]
        profile = str(payload.get("profile") or ff_overlay_site_profile_var.get() or "streamer1").strip() or "streamer1"
        ff_overlay_site_profile_var.set(profile)
        ff_overlay_site_label_var.set(str(payload.get("profile_label") or ""))
        ff_overlay_site_obs_url_var.set(str(payload.get("overlay_url") or "-"))
        ff_overlay_config_url_var.set(ff_overlay_site_endpoint())
        ff_overlay_site_enabled_general_var.set(bool(cfg.get("enabled_general", True)))
        ff_overlay_site_enabled_daily_var.set(bool(cfg.get("enabled_daily", True)))
        ff_overlay_site_enabled_queue_var.set(bool(cfg.get("enabled_queue", True)))
        ff_overlay_site_panel_bg_var.set(bool(cfg.get("panel_bg_enabled", True)))
        ff_overlay_site_rank_prefix_var.set(bool(cfg.get("show_rank_prefix", True)))
        ff_overlay_site_medals_var.set(bool(cfg.get("show_medals", True)))
        ff_overlay_site_layout_var.set(str(cfg.get("layout") or "horizontal"))
        ff_overlay_site_font_var.set(str(cfg.get("font_family") or "impact"))
        ff_overlay_site_animation_var.set(str(cfg.get("animation") or "slide"))
        ff_overlay_site_refresh_var.set(str(max(1000, normalize_kill_value(cfg.get("refresh_ms", 2500)))))
        ff_overlay_site_switch_var.set(str(max(3, normalize_kill_value(cfg.get("switch_seconds", 10)))))
        ff_overlay_site_limit_general_var.set(str(max(1, normalize_kill_value(cfg.get("limit_general", 10)))))
        ff_overlay_site_limit_daily_var.set(str(max(1, normalize_kill_value(cfg.get("limit_daily", 10)))))
        ff_overlay_site_limit_queue_var.set(str(max(1, normalize_kill_value(cfg.get("limit_queue", 8)))))
        ff_overlay_site_panel_width_var.set(str(max(180, normalize_kill_value(cfg.get("panel_width", 360)))))
        ff_overlay_site_gap_var.set(str(max(0, normalize_kill_value(cfg.get("gap", 14)))))
        ff_overlay_site_padding_var.set(str(max(0, normalize_kill_value(cfg.get("wrap_padding", 8)))))
        ff_overlay_site_title_size_var.set(str(max(14, normalize_kill_value(cfg.get("title_size", 30)))))
        ff_overlay_site_row_size_var.set(str(max(12, normalize_kill_value(cfg.get("row_size", 22)))))
        ff_overlay_site_value_size_var.set(str(max(12, normalize_kill_value(cfg.get("value_size", 24)))))
        ff_overlay_site_row_height_var.set(str(max(24, normalize_kill_value(cfg.get("row_height", 40)))))
        ff_overlay_site_panel_bg_color_var.set(normalize_hex_color(cfg.get("panel_bg_color"), "#05070D"))
        ff_overlay_site_panel_bg_opacity_var.set(str(max(0, min(100, normalize_kill_value(cfg.get("panel_bg_opacity", 48))))))
        ff_overlay_site_panel_radius_var.set(str(max(0, normalize_kill_value(cfg.get("panel_radius", 10)))))
        ff_overlay_site_row_bg_color_var.set(normalize_hex_color(cfg.get("row_bg_color"), "#000000"))
        ff_overlay_site_row_bg_opacity_var.set(str(max(0, min(100, normalize_kill_value(cfg.get("row_bg_opacity", 28))))))
        ff_overlay_site_accent_width_var.set(str(max(0, normalize_kill_value(cfg.get("accent_width", 4)))))
        for panel_key, defaults in ff_overlay_site_panel_defaults.items():
            panel_cfg = cfg.get(panel_key) if isinstance(cfg.get(panel_key), dict) else {}
            for field_key, default_value in defaults.items():
                value = panel_cfg.get(field_key, default_value)
                if field_key.endswith("_color"):
                    value = normalize_hex_color(value, str(default_value))
                else:
                    value = str(value or default_value)
                ff_overlay_site_panel_vars[panel_key][field_key].set(str(value))
        label = ff_overlay_site_label_var.get().strip() or profile
        ff_overlay_site_status_var.set(f"Config carregada: {label}")

    def collect_ff_overlay_site_config() -> dict[str, Any]:
        cfg = dict(ff_overlay_site_last_config)
        panel_payload = {}
        for panel_key, defaults in ff_overlay_site_panel_defaults.items():
            panel_payload[panel_key] = {
                "title": ff_overlay_site_panel_vars[panel_key]["title"].get().strip() or str(defaults["title"]),
                "title_color": ff_overlay_site_color(ff_overlay_site_panel_vars[panel_key]["title_color"], str(defaults["title_color"])),
                "rank_color": ff_overlay_site_color(ff_overlay_site_panel_vars[panel_key]["rank_color"], str(defaults["rank_color"])),
                "name_color": ff_overlay_site_color(ff_overlay_site_panel_vars[panel_key]["name_color"], str(defaults["name_color"])),
                "value_color": ff_overlay_site_color(ff_overlay_site_panel_vars[panel_key]["value_color"], str(defaults["value_color"])),
                "accent_color": ff_overlay_site_color(ff_overlay_site_panel_vars[panel_key]["accent_color"], str(defaults["accent_color"])),
            }
        cfg.update(
            {
                "enabled_general": bool(ff_overlay_site_enabled_general_var.get()),
                "enabled_daily": bool(ff_overlay_site_enabled_daily_var.get()),
                "enabled_queue": bool(ff_overlay_site_enabled_queue_var.get()),
                "panel_bg_enabled": bool(ff_overlay_site_panel_bg_var.get()),
                "show_rank_prefix": bool(ff_overlay_site_rank_prefix_var.get()),
                "show_medals": bool(ff_overlay_site_medals_var.get()),
                "layout": ff_overlay_site_layout_var.get().strip() or "horizontal",
                "font_family": ff_overlay_site_font_var.get().strip() or "impact",
                "animation": ff_overlay_site_animation_var.get().strip() or "slide",
                "refresh_ms": ff_overlay_site_int(ff_overlay_site_refresh_var, 2500, 1000, 60000),
                "switch_seconds": ff_overlay_site_int(ff_overlay_site_switch_var, 10, 3, 120),
                "limit_general": ff_overlay_site_int(ff_overlay_site_limit_general_var, 10, 1, 50),
                "limit_daily": ff_overlay_site_int(ff_overlay_site_limit_daily_var, 10, 1, 50),
                "limit_queue": ff_overlay_site_int(ff_overlay_site_limit_queue_var, 8, 1, 50),
                "panel_width": ff_overlay_site_int(ff_overlay_site_panel_width_var, 360, 180, 900),
                "gap": ff_overlay_site_int(ff_overlay_site_gap_var, 14, 0, 80),
                "wrap_padding": ff_overlay_site_int(ff_overlay_site_padding_var, 8, 0, 120),
                "title_size": ff_overlay_site_int(ff_overlay_site_title_size_var, 30, 14, 96),
                "row_size": ff_overlay_site_int(ff_overlay_site_row_size_var, 22, 12, 72),
                "value_size": ff_overlay_site_int(ff_overlay_site_value_size_var, 24, 12, 80),
                "row_height": ff_overlay_site_int(ff_overlay_site_row_height_var, 40, 24, 120),
                "panel_bg_color": ff_overlay_site_color(ff_overlay_site_panel_bg_color_var, "#05070D"),
                "panel_bg_opacity": ff_overlay_site_int(ff_overlay_site_panel_bg_opacity_var, 48, 0, 100),
                "panel_radius": ff_overlay_site_int(ff_overlay_site_panel_radius_var, 10, 0, 50),
                "row_bg_color": ff_overlay_site_color(ff_overlay_site_row_bg_color_var, "#000000"),
                "row_bg_opacity": ff_overlay_site_int(ff_overlay_site_row_bg_opacity_var, 28, 0, 100),
                "accent_width": ff_overlay_site_int(ff_overlay_site_accent_width_var, 4, 0, 20),
                **panel_payload,
            }
        )
        return cfg

    def fetch_ff_overlay_site_config(force: bool = True) -> None:
        if ff_overlay_site_sync_hidden:
            ff_overlay_site_status_var.set("Desativado")
            log("Config do Overlay FF desativada porque Kills FF e Fila FF estao ocultas.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        endpoint_url = ff_overlay_site_endpoint()
        if not endpoint_url:
            ff_overlay_site_status_var.set("Sem endpoint")
            log("Configure o endpoint de config do Overlay FF.")
            return
        ff_overlay_config_url_var.set(endpoint_url)
        profile = ff_overlay_site_profile_var.get().strip() or "streamer1"
        ff_overlay_site_status_var.set("Carregando config")

        def run() -> None:
            try:
                payload = fetch_ff_overlay_config(
                    endpoint_url,
                    profile=profile,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event("ff_overlay_config_fetched", {"payload": payload, "force": force})
            except Exception as exc:
                enqueue_sync_event("ff_overlay_config_error", {"error": str(exc), "label": "carregar config"})

        start_sync_worker(run, name="AizenFFOverlayConfigFetch")

    def ff_overlay_site_action(action: str, payload: dict[str, Any] | None = None, label: str = "") -> None:
        if ff_overlay_site_sync_hidden:
            ff_overlay_site_status_var.set("Desativado")
            log("Config do Overlay FF desativada porque Kills FF e Fila FF estao ocultas.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        endpoint_url = ff_overlay_site_endpoint()
        if not endpoint_url:
            ff_overlay_site_status_var.set("Sem endpoint")
            log("Configure o endpoint de config do Overlay FF.")
            return
        ff_overlay_config_url_var.set(endpoint_url)
        profile = ff_overlay_site_profile_var.get().strip() or "streamer1"
        ff_overlay_site_status_var.set(label or "Salvando config")

        def run() -> None:
            try:
                result = send_ff_overlay_config_action(
                    endpoint_url,
                    action,
                    payload or {},
                    profile=profile,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event("ff_overlay_config_saved", {"payload": result, "label": label or action})
            except Exception as exc:
                enqueue_sync_event("ff_overlay_config_error", {"error": str(exc), "label": label or action})

        start_sync_worker(run, name="AizenFFOverlayConfigSave")

    def save_ff_overlay_site_config() -> None:
        ff_overlay_site_action(
            "save_config",
            {"config": collect_ff_overlay_site_config(), "label": ff_overlay_site_label_var.get().strip()},
            "Salvando overlay OBS",
        )

    def create_ff_overlay_site_profile() -> None:
        label = ff_overlay_site_label_var.get().strip()
        if not label:
            value = simpledialog.askstring("Novo perfil", "Nome do novo perfil do Overlay FF:", parent=root)
            label = str(value or "").strip()
        if not label:
            return
        ff_overlay_site_action("create_profile", {"label": label, "source_profile": ff_overlay_site_profile_var.get().strip()}, "Criando perfil")

    def copy_ff_overlay_site_url() -> None:
        value = ff_overlay_site_obs_url_var.get().strip()
        if not value or value == "-":
            messagebox.showinfo("Overlay FF", "Carregue a config para obter a URL OBS.")
            return
        root.clipboard_clear()
        root.clipboard_append(value)
        ff_overlay_site_status_var.set("URL OBS copiada")

    def open_ff_overlay_site_url() -> None:
        value = ff_overlay_site_obs_url_var.get().strip()
        if not value or value == "-":
            messagebox.showinfo("Overlay FF", "Carregue a config para obter a URL OBS.")
            return
        webbrowser.open(value)

    def tikfinity_ff_endpoint() -> str:
        endpoint_url = normalize_endpoint_url(tikfinity_ff_url_var.get())
        if endpoint_url:
            return derive_tikfinity_ff_gifts_endpoint(endpoint_url)
        base_url = normalize_endpoint_url(jarvis_base_url_var.get()).rstrip("/")
        if base_url:
            return derive_tikfinity_ff_gifts_endpoint(base_url)
        queue_url = normalize_endpoint_url(ff_queue_url_var.get())
        if queue_url:
            return derive_tikfinity_ff_gifts_endpoint(queue_url)
        return ""

    def tikfinity_ff_clean_profile() -> str:
        return tikfinity_ff_profile_var.get().strip() or "streamer1"

    def tikfinity_ff_clear_widget_list(widgets: list[Any]) -> None:
        for widget in widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        widgets.clear()

    def tikfinity_ff_ts_label(value: Any) -> str:
        try:
            ts = float(value or 0)
        except (TypeError, ValueError):
            ts = 0
        if ts <= 0:
            return "-"
        try:
            return datetime.fromtimestamp(ts).strftime("%d/%m %H:%M")
        except (OSError, ValueError):
            return "-"

    def apply_tikfinity_ff_state(payload: dict[str, Any]) -> None:
        nonlocal tikfinity_ff_profiles
        config_payload = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        profiles_payload = payload.get("profiles") if isinstance(payload.get("profiles"), list) else []
        tikfinity_ff_profiles = [item for item in profiles_payload if isinstance(item, dict)]
        profile = str(payload.get("profile") or tikfinity_ff_profile_var.get() or "streamer1").strip() or "streamer1"
        tikfinity_ff_profile_var.set(profile)
        tikfinity_ff_enabled_var.set(bool(config_payload.get("enabled", True)))
        tikfinity_ff_coins_var.set(str(max(1, normalize_kill_value(config_payload.get("coins_per_room", 50)))))
        webhook_url = str(payload.get("webhook_url") or payload.get("webhook_path_url") or "-").strip() or "-"
        tikfinity_ff_webhook_var.set(webhook_url)
        mappings = payload.get("mappings") if isinstance(payload.get("mappings"), list) else []
        users = payload.get("users") if isinstance(payload.get("users"), list) else []
        history = payload.get("history") if isinstance(payload.get("history"), list) else []
        tikfinity_ff_summary_var.set(f"{len(mappings)} vínculos | {len(users)} usuários | {len(history)} eventos")
        if (
            ff_queue_site_sync_hidden
            or tikfinity_ff_mappings_frame is None
            or tikfinity_ff_users_frame is None
            or tikfinity_ff_history_frame is None
        ):
            return

        tikfinity_ff_clear_widget_list(tikfinity_ff_widgets)
        if not mappings:
            empty = ctk.CTkLabel(tikfinity_ff_mappings_frame, text="Nenhum TikTok vinculado.", text_color=muted, font=("Segoe UI", 12))
            empty.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            tikfinity_ff_widgets.append(empty)
        for index, item in enumerate(mappings[:20], start=1):
            handle = str(item.get("social_user") or "-")
            user_id = str(item.get("user_id") or "-")
            display = str(item.get("display_name") or "")
            ffid = str(item.get("ff_player_id") or "-")
            row_frame = ctk.CTkFrame(tikfinity_ff_mappings_frame, fg_color="#171014", corner_radius=10)
            row_frame.grid(row=index - 1, column=0, sticky="ew", padx=6, pady=4)
            row_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(row_frame, text=f"@{handle} -> {display or user_id}", text_color=fg, font=("Segoe UI Semibold", 12), anchor="w").grid(
                row=0, column=0, sticky="ew", padx=10, pady=(8, 0)
            )
            ctk.CTkLabel(row_frame, text=f"ID {user_id} | FF {ffid}", text_color=muted, font=("Segoe UI", 11), anchor="w").grid(
                row=1, column=0, sticky="ew", padx=10, pady=(0, 8)
            )
            button(
                row_frame,
                "Remover",
                lambda target=handle: tikfinity_ff_action("remove_mapping", {"social_user": target}, "Removendo vínculo"),
                "danger",
                width=78,
            ).grid(row=0, column=1, rowspan=2, padx=(4, 10), pady=8)
            tikfinity_ff_widgets.append(row_frame)

        tikfinity_ff_clear_widget_list(tikfinity_ff_user_widgets)
        if not users:
            empty = ctk.CTkLabel(tikfinity_ff_users_frame, text="Nenhum gift processado.", text_color=muted, font=("Segoe UI", 12))
            empty.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            tikfinity_ff_user_widgets.append(empty)
        for index, item in enumerate(users[:20], start=1):
            name = str(item.get("display_name") or item.get("social_user") or item.get("user_id") or "-")
            social = str(item.get("social_user") or "-")
            uid = str(item.get("user_id") or "")
            coins = normalize_kill_value(item.get("total_coins", 0))
            pending = normalize_kill_value(item.get("pending_coins", 0))
            rooms = normalize_kill_value(item.get("rooms_added", 0))
            row_frame = ctk.CTkFrame(tikfinity_ff_users_frame, fg_color="#10131a", corner_radius=10)
            row_frame.grid(row=index - 1, column=0, sticky="ew", padx=6, pady=4)
            row_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(row_frame, text=name, text_color=fg, font=("Segoe UI Semibold", 12), anchor="w").grid(
                row=0, column=0, sticky="ew", padx=10, pady=(8, 0)
            )
            ctk.CTkLabel(
                row_frame,
                text=f"@{social} | {coins} moedas | resto {pending} | +{rooms} salas",
                text_color=muted,
                font=("Segoe UI", 11),
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 8))
            button(
                row_frame,
                "Zerar",
                lambda target=uid: tikfinity_ff_action("reset_user", {"user_id": target}, "Zerando usuário"),
                "danger",
                width=62,
            ).grid(row=0, column=1, rowspan=2, padx=(4, 10), pady=8)
            tikfinity_ff_user_widgets.append(row_frame)

        tikfinity_ff_clear_widget_list(tikfinity_ff_history_widgets)
        if not history:
            empty = ctk.CTkLabel(tikfinity_ff_history_frame, text="Sem histórico de gifts.", text_color=muted, font=("Segoe UI", 12))
            empty.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            tikfinity_ff_history_widgets.append(empty)
        for index, item in enumerate(history[:10], start=1):
            name = str(item.get("display_name") or item.get("social_user") or "-")
            gift = str(item.get("gift_name") or "gift")
            coins = normalize_kill_value(item.get("coins_added", 0))
            rooms = normalize_kill_value(item.get("ff_room_credits_added", 0))
            row_frame = ctk.CTkFrame(tikfinity_ff_history_frame, fg_color="#171014", corner_radius=10)
            row_frame.grid(row=index - 1, column=0, sticky="ew", padx=6, pady=4)
            row_frame.columnconfigure(0, weight=1)
            ctk.CTkLabel(
                row_frame,
                text=f"{tikfinity_ff_ts_label(item.get('ts'))} | {name}",
                text_color=fg,
                font=("Segoe UI Semibold", 12),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
            ctk.CTkLabel(row_frame, text=f"{gift} | +{coins} moedas | +{rooms} salas", text_color=muted, font=("Segoe UI", 11), anchor="w").grid(
                row=1, column=0, sticky="ew", padx=10, pady=(0, 8)
            )
            tikfinity_ff_history_widgets.append(row_frame)

    def fetch_tikfinity_ff_panel(force: bool = True) -> None:
        if ff_queue_site_sync_hidden:
            tikfinity_ff_status_var.set("Desativado")
            if force:
                log("TikFinity Gifts FF desativado porque a aba Fila FF esta oculta.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        endpoint_url = local_config.get("tikfinity_ff_gifts_url", "").strip()
        if not endpoint_url:
            tikfinity_ff_status_var.set("Sem endpoint")
            if force:
                log("Configure a URL de TikFinity Gifts do Jarvis.")
            return
        tikfinity_ff_status_var.set("Lendo Jarvis")

        def run() -> None:
            try:
                payload = fetch_tikfinity_ff_gifts(
                    endpoint_url,
                    profile=str(local_config.get("tikfinity_ff_profile", "streamer1")),
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_ff_queue_event("tikfinity_ff_fetched", {"payload": payload, "force": force})
            except Exception as exc:
                enqueue_ff_queue_event("tikfinity_ff_error", {"error": str(exc), "label": "buscar TikFinity FF"})

        start_ff_queue_worker(run, name="AizenTikFinityFFFetch")

    def tikfinity_ff_action(action: str, payload: dict[str, Any] | None = None, label: str = "") -> None:
        if ff_queue_site_sync_hidden:
            tikfinity_ff_status_var.set("Desativado")
            log("TikFinity Gifts FF desativado porque a aba Fila FF esta oculta.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return
        endpoint_url = local_config.get("tikfinity_ff_gifts_url", "").strip()
        if not endpoint_url:
            tikfinity_ff_status_var.set("Sem endpoint")
            log("Configure a URL de TikFinity Gifts do Jarvis.")
            return
        tikfinity_ff_status_var.set(label or "Enviando")

        def run() -> None:
            try:
                result = send_tikfinity_ff_gifts_action(
                    endpoint_url,
                    action,
                    payload or {},
                    profile=str(local_config.get("tikfinity_ff_profile", "streamer1")),
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_ff_queue_event("tikfinity_ff_action_done", {"payload": result, "label": label or action})
            except Exception as exc:
                enqueue_ff_queue_event("tikfinity_ff_error", {"error": str(exc), "label": label or action})

        start_ff_queue_worker(run, name="AizenTikFinityFFAction")

    def save_tikfinity_ff_config() -> None:
        tikfinity_ff_action(
            "save_config",
            {
                "enabled": bool(tikfinity_ff_enabled_var.get()),
                "coins_per_room": max(1, normalize_kill_value(tikfinity_ff_coins_var.get())),
                "token": tikfinity_ff_token_var.get().strip(),
            },
            "Salvando TikFinity",
        )

    def add_tikfinity_ff_mapping() -> None:
        handle = tikfinity_ff_map_handle_var.get().strip()
        user_id = tikfinity_ff_map_user_id_var.get().strip()
        if not handle or not user_id:
            messagebox.showinfo("TikFinity FF", "Informe TikTok e ID do membro.")
            return
        ffid = re.sub(r"\D+", "", tikfinity_ff_map_ff_id_var.get())
        if tikfinity_ff_map_ff_id_var.get().strip() and not re.fullmatch(r"\d{5,15}", ffid):
            messagebox.showerror("TikFinity FF", "ID FF inválido. Use somente números, de 5 a 15 dígitos.")
            return
        tikfinity_ff_action(
            "add_mapping",
            {
                "social_user": handle,
                "user_id": user_id,
                "display_name": tikfinity_ff_map_display_var.get().strip(),
                "ff_player_id": ffid,
            },
            "Vinculando TikTok",
        )
        tikfinity_ff_map_handle_var.set("")
        tikfinity_ff_map_user_id_var.set("")
        tikfinity_ff_map_display_var.set("")
        tikfinity_ff_map_ff_id_var.set("")

    def clear_tikfinity_ff_history() -> None:
        if not messagebox.askyesno("TikFinity FF", "Limpar histórico e eventos recentes de gifts?"):
            return
        tikfinity_ff_action("clear_history", {}, "Limpando histórico")

    def copy_tikfinity_ff_webhook() -> None:
        url = tikfinity_ff_webhook_var.get().strip()
        if not url or url == "-":
            url = tikfinity_ff_endpoint().replace("/api/tikfinity/ff-gifts", f"/api/tikfinity/gift?profile={tikfinity_ff_clean_profile()}")
        if tikfinity_ff_token_var.get().strip() and "token=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}token={quote(tikfinity_ff_token_var.get().strip())}"
        root.clipboard_clear()
        root.clipboard_append(url)
        tikfinity_ff_status_var.set("Webhook copiado")

    def apply_jarvis_base_url() -> None:
        base_url = jarvis_base_url_var.get().strip()
        kills_url = derive_jarvis_endpoint(base_url, "kills")
        queue_url = derive_jarvis_endpoint(base_url, "queue")
        kills_style_url = derive_kills_style_endpoint(base_url)
        kills_obs_url = derive_kills_obs_url(base_url)
        tikfinity_url = derive_tikfinity_ff_gifts_endpoint(base_url)
        if not kills_url or not queue_url:
            messagebox.showinfo("Jarvis FF", "Informe a URL base do Jarvis ou um endpoint /api/freefire-kills.")
            return
        jarvis_base_url_var.set(normalize_endpoint_url(base_url).rstrip("/"))
        sync_url_var.set(kills_url)
        kills_style_url_var.set(kills_style_url)
        kills_obs_url_var.set(kills_obs_url)
        ff_queue_url_var.set(queue_url)
        tikfinity_ff_url_var.set(tikfinity_url)
        manual_status_var.set("Endpoint configurado")
        ff_queue_status_var.set("Endpoint configurado")
        log("Endpoints Jarvis FF preenchidos para Kills FF e Fila FF.")

    def test_jarvis_connection() -> None:
        if kills_ff_site_sync_hidden and ff_queue_site_sync_hidden:
            manual_status_var.set("Desativado")
            ff_queue_status_var.set("Desativado")
            ff_overlay_status_var.set("Desativado")
            tikfinity_ff_status_var.set("Desativado")
            log("Teste Jarvis FF desativado porque Kills FF e Fila FF estao ocultas.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Jarvis FF", str(exc))
            return

        kills_url = str(local_config.get("kills_realtime_url", "")).strip()
        queue_url = str(local_config.get("ff_queue_realtime_url", "")).strip()
        overlay_url = str(local_config.get("ff_overlay_realtime_url", "")).strip()
        tikfinity_url = str(local_config.get("tikfinity_ff_gifts_url", "")).strip()
        if not kills_url or not queue_url:
            messagebox.showinfo("Jarvis FF", "Configure os endpoints de Kills FF e Fila FF antes de testar.")
            return
        manual_status_var.set("Testando Jarvis")
        ff_queue_status_var.set("Testando Jarvis")
        ff_overlay_status_var.set("Testando Jarvis")
        tikfinity_ff_status_var.set("Testando Jarvis")

        def run() -> None:
            results: dict[str, str] = {}
            try:
                fetch_kills_realtime(
                    kills_url,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room="",
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                results["kills"] = ""
            except Exception as exc:
                results["kills"] = str(exc)
            try:
                fetch_ff_queue_realtime(
                    queue_url,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("ff_queue_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                results["queue"] = ""
            except Exception as exc:
                results["queue"] = str(exc)
            if overlay_url:
                try:
                    fetch_ff_overlay_realtime(
                        overlay_url,
                        device_id=str(local_config.get("device_id", "")),
                        device_name=str(local_config.get("device_name", "")),
                        room=str(local_config.get("kills_sync_room", "principal")),
                        token=str(local_config.get("jarvis_api_token", "")),
                    )
                    results["overlay"] = ""
                except Exception as exc:
                    results["overlay"] = str(exc)
            else:
                results["overlay"] = "Endpoint opcional nao configurado"
            if tikfinity_url:
                try:
                    fetch_tikfinity_ff_gifts(
                        tikfinity_url,
                        profile=str(local_config.get("tikfinity_ff_profile", "streamer1")),
                        device_id=str(local_config.get("device_id", "")),
                        device_name=str(local_config.get("device_name", "")),
                        token=str(local_config.get("jarvis_api_token", "")),
                    )
                    results["tikfinity"] = ""
                except Exception as exc:
                    results["tikfinity"] = str(exc)
            else:
                results["tikfinity"] = "Endpoint opcional nao configurado"
            enqueue_sync_event("jarvis_test", results)

        start_sync_worker(run, name="AizenJarvisTest")

    def ff_overlay_snapshot() -> tuple[list[PlayerKill], list[dict[str, Any]], int, int]:
        players = overlay_rank_players(kills_daily_ranking, kills_global_ranking, read_manual_players_light(scope=current_manual_scope()))
        queue_items = queue_summary_items(collect_ff_queue_entries())
        total_kills = sum(player.kills for player in players)
        active_rooms = sum(int(item["rooms"]) for item in queue_items)
        return players, queue_items, total_kills, active_rooms

    def ff_overlay_options_payload() -> dict[str, Any]:
        return {
            "show_kills": bool(ff_overlay_show_kills_var.get()),
            "show_queue": bool(ff_overlay_show_queue_var.get()),
            "compact": bool(ff_overlay_compact_var.get()),
            "opacity": layout_value(ff_overlay_opacity_var, 35, 100),
            "width": layout_value(ff_overlay_width_var, 420, 1400),
            "height": layout_value(ff_overlay_height_var, 240, 900),
            "kills_room": sync_room_var.get().strip() or "principal",
            "queue_room": ff_queue_room_var.get().strip() or "principal",
        }

    def ff_overlay_signature() -> str:
        players, _queue_items, _total_kills, _active_rooms = ff_overlay_snapshot()
        digest = hashlib.sha1()
        update_digest_part(digest, player_rank_light_signature(players))
        update_digest_part(digest, ff_queue_signature(collect_ff_queue_entries()))
        for key, value in sorted(ff_overlay_options_payload().items()):
            update_digest_part(digest, key)
            update_digest_part(digest, value)
        return digest.hexdigest()

    def ff_overlay_queue_items_signature(queue_items: list[dict[str, Any]]) -> str:
        digest = hashlib.sha1()
        for item in queue_items:
            update_digest_part(digest, item.get("name", ""))
            update_digest_part(digest, item.get("rooms", 0))
            update_digest_part(digest, item.get("waiting", 0))
            update_digest_part(digest, item.get("called", 0))
            update_digest_part(digest, item.get("playing", 0))
            update_digest_part(digest, item.get("panel_user_id", ""))
            update_digest_part(digest, item.get("ff_player_id", ""))
        update_digest_part(digest, len(queue_items))
        return digest.hexdigest()

    def render_ff_overlay_panel(target: Any, widget_store: list[Any], preview: bool = False) -> None:
        for widget in widget_store:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        widget_store.clear()

        players, queue_items, total_kills, active_rooms = ff_overlay_snapshot()
        compact = bool(ff_overlay_compact_var.get())
        show_kills = bool(ff_overlay_show_kills_var.get())
        show_queue = bool(ff_overlay_show_queue_var.get())

        shell = ctk.CTkFrame(target, fg_color="#050609", corner_radius=14, border_width=1, border_color=accent)
        shell.grid(row=0, column=0, sticky="nsew", padx=10 if preview else 8, pady=10 if preview else 8)
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)
        widget_store.append(shell)

        header = ctk.CTkFrame(shell, fg_color="#101116", corner_radius=12)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 8))
        header.columnconfigure(0, weight=1)
        widget_store.append(header)
        ctk.CTkLabel(
            header,
            text="FREE FIRE",
            text_color=fg,
            font=("Segoe UI Semibold", 18 if compact else 24),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(
            header,
            text=f"{len(players)} jogadores  |  {total_kills} kills  |  {active_rooms} salas na fila",
            text_color=muted,
            font=("Segoe UI", 10 if compact else 12),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))
        ctk.CTkLabel(
            header,
            text="LIVE",
            text_color="#07100d",
            fg_color=teal,
            corner_radius=999,
            font=("Segoe UI Semibold", 11),
            padx=12,
            pady=5,
        ).grid(row=0, column=1, rowspan=2, sticky="e", padx=14, pady=12)

        if show_kills:
            kills_panel = ctk.CTkFrame(shell, fg_color="#0b0d12", corner_radius=12, border_width=1, border_color=border)
            kills_panel.grid(row=1, column=0, sticky="nsew", padx=(12, 6 if show_queue else 12), pady=(0, 12))
            kills_panel.columnconfigure(0, weight=1)
            widget_store.append(kills_panel)
            ctk.CTkLabel(
                kills_panel,
                text="KILLS FF",
                text_color=accent,
                font=("Segoe UI Semibold", 12),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
            display_players = players[:4 if compact else 6]
            if not display_players:
                ctk.CTkLabel(
                    kills_panel,
                    text="Aguardando painel Jarvis",
                    text_color=muted,
                    font=("Segoe UI", 12),
                ).grid(row=1, column=0, sticky="ew", padx=14, pady=18)
            for index, player in enumerate(display_players, start=1):
                row = ctk.CTkFrame(kills_panel, fg_color="#151820" if index % 2 else "#0f1118", corner_radius=9)
                row.grid(row=index, column=0, sticky="ew", padx=10, pady=3)
                row.columnconfigure(1, weight=1)
                ctk.CTkLabel(row, text=f"{index:02d}", text_color=muted, font=("Segoe UI Semibold", 11), width=34).grid(
                    row=0, column=0, sticky="w", padx=(10, 6), pady=8
                )
                ctk.CTkLabel(row, text=player.name, text_color=fg, font=("Segoe UI Semibold", 12), anchor="w").grid(
                    row=0, column=1, sticky="ew", padx=4, pady=8
                )
                ctk.CTkLabel(
                    row,
                    text=str(player.kills),
                    text_color="#07100d",
                    fg_color=teal,
                    corner_radius=999,
                    font=("Segoe UI Semibold", 12),
                    padx=10,
                    pady=4,
                ).grid(row=0, column=2, sticky="e", padx=(6, 10), pady=8)

        if show_queue:
            queue_column = 1 if show_kills else 0
            queue_colspan = 1 if show_kills else 2
            queue_panel = ctk.CTkFrame(shell, fg_color="#0b0d12", corner_radius=12, border_width=1, border_color=border)
            queue_panel.grid(row=1, column=queue_column, columnspan=queue_colspan, sticky="nsew", padx=(6 if show_kills else 12, 12), pady=(0, 12))
            queue_panel.columnconfigure(0, weight=1)
            widget_store.append(queue_panel)
            ctk.CTkLabel(
                queue_panel,
                text="FILA FF",
                text_color=accent,
                font=("Segoe UI Semibold", 12),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
            display_queue = queue_items[:4 if compact else 6]
            if not display_queue:
                ctk.CTkLabel(
                    queue_panel,
                    text="Fila vazia ou sem leitura",
                    text_color=muted,
                    font=("Segoe UI", 12),
                ).grid(row=1, column=0, sticky="ew", padx=14, pady=18)
            for index, item in enumerate(display_queue, start=1):
                status_parts = []
                if item["playing"]:
                    status_parts.append(f"{item['playing']} jogando")
                if item["called"]:
                    status_parts.append(f"{item['called']} chamado")
                if item["waiting"]:
                    status_parts.append(f"{item['waiting']} fila")
                status_text = " | ".join(status_parts) or "ativo"
                row = ctk.CTkFrame(queue_panel, fg_color="#151820" if index % 2 else "#0f1118", corner_radius=9)
                row.grid(row=index, column=0, sticky="ew", padx=10, pady=3)
                row.columnconfigure(0, weight=1)
                ctk.CTkLabel(row, text=item["name"], text_color=fg, font=("Segoe UI Semibold", 12), anchor="w").grid(
                    row=0, column=0, sticky="ew", padx=10, pady=(8, 0)
                )
                ctk.CTkLabel(row, text=status_text, text_color=muted, font=("Segoe UI", 10), anchor="w").grid(
                    row=1, column=0, sticky="ew", padx=10, pady=(0, 8)
                )
                ctk.CTkLabel(
                    row,
                    text=f"{int(item['rooms'])}x",
                    text_color="#fff7f7",
                    fg_color=accent,
                    corner_radius=999,
                    font=("Segoe UI Semibold", 11),
                    padx=9,
                    pady=4,
                ).grid(row=0, column=1, rowspan=2, sticky="e", padx=(6, 10), pady=8)

        if not show_kills and not show_queue:
            ctk.CTkLabel(
                shell,
                text="Ative Kills FF ou Fila FF para exibir dados no overlay.",
                text_color=muted,
                font=("Segoe UI Semibold", 14),
            ).grid(row=1, column=0, columnspan=2, sticky="nsew", padx=18, pady=30)

    def refresh_ff_overlay(force: bool = False) -> None:
        if ff_overlay_site_sync_hidden and ff_overlay_preview_frame is None and ff_overlay_content_frame is None:
            return
        players, queue_items, total_kills, active_rooms = ff_overlay_snapshot()
        signature = "|".join(
            (
                player_rank_light_signature(players),
                str(total_kills),
                str(active_rooms),
                ff_overlay_queue_items_signature(queue_items),
                str(bool(ff_overlay_compact_var.get())),
                str(bool(ff_overlay_show_kills_var.get())),
                str(bool(ff_overlay_show_queue_var.get())),
            )
        )
        if not force and getattr(refresh_ff_overlay, "_signature", None) == signature:
            return
        refresh_ff_overlay._signature = signature  # type: ignore[attr-defined]
        if ff_overlay_preview_frame is not None:
            render_ff_overlay_panel(ff_overlay_preview_frame, ff_overlay_widgets, preview=True)
        try:
            if ff_overlay_content_frame is not None:
                render_ff_overlay_panel(ff_overlay_content_frame, getattr(refresh_ff_overlay, "_window_widgets", []), preview=False)
        except NameError:
            pass
        if not ff_overlay_applying_remote:
            schedule_ff_overlay_sync()

    def schedule_ff_overlay_sync(delay_ms: int = 900) -> None:
        nonlocal ff_overlay_sync_after_id
        if app_closing or ff_overlay_site_sync_hidden or ff_overlay_applying_remote or not ff_overlay_enabled_var.get():
            if ff_overlay_sync_after_id is not None:
                try:
                    root.after_cancel(ff_overlay_sync_after_id)
                except tk.TclError:
                    pass
                ff_overlay_sync_after_id = None
            return
        if ff_overlay_sync_after_id is not None:
            try:
                root.after_cancel(ff_overlay_sync_after_id)
            except tk.TclError:
                pass
        ff_overlay_sync_after_id = root.after(delay_ms, lambda: send_ff_overlay(force=False))

    def send_ff_overlay(force: bool = True) -> None:
        nonlocal ff_overlay_sending, ff_overlay_last_signature, ff_overlay_sync_after_id
        ff_overlay_sync_after_id = None
        if ff_overlay_site_sync_hidden:
            if force:
                ff_overlay_status_var.set("Desativado")
                log("Overlay FF nao foi enviado porque Kills FF e Fila FF estao ocultas.")
            return
        try:
            local_config = update_config_from_form()
            if force:
                save_config_snapshot_in_background(local_config)
        except Exception as exc:
            if force:
                messagebox.showerror("Overlay FF", str(exc))
            return

        endpoint_url = str(local_config.get("ff_overlay_realtime_url", "")).strip()
        if not endpoint_url:
            if force:
                log("Informe a URL Overlay/Jarvis para enviar o Overlay FF.")
            return
        signature = ff_overlay_signature()
        if not force and signature == ff_overlay_last_signature:
            return
        if ff_overlay_sending:
            return
        overlay_players_snapshot = read_manual_players_light(scope=current_manual_scope())
        overlay_queue_snapshot = collect_ff_queue_entries()
        overlay_options_snapshot = ff_overlay_options_payload()
        ff_overlay_sending = True
        ff_overlay_status_var.set("Enviando")

        def run() -> None:
            try:
                response_text = send_ff_overlay_realtime_update(
                    endpoint_url,
                    overlay_players_snapshot,
                    overlay_queue_snapshot,
                    options=overlay_options_snapshot,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("kills_sync_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event("overlay_sent", {"signature": signature, "response": response_text})
            except Exception as exc:
                enqueue_sync_event("overlay_send_error", str(exc))

        start_sync_worker(run, name="AizenFFOverlaySend")

    def fetch_ff_overlay(force: bool = True) -> None:
        nonlocal ff_overlay_fetching
        if ff_overlay_site_sync_hidden:
            if force:
                ff_overlay_status_var.set("Desativado")
                log("Overlay FF nao foi buscado porque Kills FF e Fila FF estao ocultas.")
            return
        try:
            local_config = update_config_from_form()
            if force:
                save_config_snapshot_in_background(local_config)
        except Exception as exc:
            if force:
                messagebox.showerror("Overlay FF", str(exc))
            return

        endpoint_url = str(local_config.get("ff_overlay_realtime_url", "")).strip()
        if not endpoint_url:
            if force:
                log("Informe a URL Overlay/Jarvis para buscar o Overlay FF.")
            return
        if ff_overlay_fetching:
            return
        ff_overlay_fetching = True
        if force:
            ff_overlay_status_var.set("Lendo Jarvis")

        def run() -> None:
            try:
                kills_state, queue_state = fetch_ff_overlay_realtime(
                    endpoint_url,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("kills_sync_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event(
                    "overlay_fetched",
                    {
                        "kills_state": kills_state,
                        "queue_state": queue_state,
                        "force": force,
                    },
                )
            except Exception as exc:
                enqueue_sync_event("overlay_fetch_error", {"error": str(exc), "force": force})

        start_sync_worker(run, name="AizenFFOverlayFetch")

    def apply_ff_overlay_settings(refresh: bool = False) -> None:
        opacity = layout_value(ff_overlay_opacity_var, 35, 100)
        width = layout_value(ff_overlay_width_var, 420, 1400)
        height = layout_value(ff_overlay_height_var, 240, 900)
        ff_overlay_opacity_text.set(f"{opacity}%")
        ff_overlay_size_text.set(f"{width} x {height}px")
        if ff_overlay_window is not None:
            try:
                ff_overlay_window.geometry(f"{width}x{height}")
                ff_overlay_window.attributes("-topmost", True)
                ff_overlay_window.attributes("-alpha", max(0.35, min(1.0, opacity / 100)))
            except tk.TclError:
                pass
        if refresh:
            refresh_ff_overlay(force=True)

    def close_ff_overlay_window() -> None:
        nonlocal ff_overlay_window, ff_overlay_content_frame, ff_overlay_controls_frame
        if ff_overlay_window is not None:
            try:
                ff_overlay_width_var.set(max(420, int(ff_overlay_window.winfo_width())))
                ff_overlay_height_var.set(max(240, int(ff_overlay_window.winfo_height())))
                ff_overlay_window.destroy()
            except tk.TclError:
                pass
        ff_overlay_window = None
        ff_overlay_content_frame = None
        ff_overlay_controls_frame = None

    def open_ff_overlay_window() -> None:
        nonlocal ff_overlay_window, ff_overlay_content_frame, ff_overlay_controls_frame
        if ff_overlay_window is not None:
            try:
                if ff_overlay_window.winfo_exists():
                    ff_overlay_window.lift()
                    refresh_ff_overlay(force=True)
                    return
            except tk.TclError:
                pass

        width = layout_value(ff_overlay_width_var, 420, 1400)
        height = layout_value(ff_overlay_height_var, 240, 900)
        window = ctk.CTkToplevel(root)
        ff_overlay_window = window
        window.title("Overlay FF - Aizen Stream Control")
        window.geometry(f"{width}x{height}+80+90")
        window.minsize(420, 240)
        window.resizable(True, True)
        window.overrideredirect(True)
        window.configure(fg_color="#050506")
        window.attributes("-topmost", True)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(1, weight=1)
        if APP_ICON.exists():
            try:
                window.iconbitmap(str(APP_ICON))
            except tk.TclError:
                pass

        controls = ctk.CTkFrame(window, fg_color="#101116", corner_radius=12, border_width=1, border_color=border)
        ff_overlay_controls_frame = controls
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        controls.columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(controls, text="Overlay FF", text_color=fg, font=("Segoe UI Semibold", 13), anchor="w")
        title_label.grid(row=0, column=0, sticky="ew", padx=12, pady=7)
        button(controls, "Atualizar", lambda: refresh_overlay_from_jarvis(), "accent", width=78).grid(row=0, column=1, padx=(0, 6), pady=5)
        button(controls, "Ocultar", lambda: controls.grid_remove(), "ghost", width=72).grid(row=0, column=2, padx=(0, 6), pady=5)
        button(controls, "X", close_ff_overlay_window, "danger", width=42).grid(row=0, column=3, padx=(0, 8), pady=5)

        content = ctk.CTkFrame(window, fg_color="#050506", corner_radius=0)
        ff_overlay_content_frame = content
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        drag_state = {"x": 0, "y": 0}

        def start_drag(event: Any) -> None:
            drag_state["x"] = event.x_root - window.winfo_x()
            drag_state["y"] = event.y_root - window.winfo_y()

        def drag_window(event: Any) -> None:
            window.geometry(f"+{event.x_root - drag_state['x']}+{event.y_root - drag_state['y']}")

        for drag_widget in (controls, title_label):
            drag_widget.bind("<ButtonPress-1>", start_drag)
            drag_widget.bind("<B1-Motion>", drag_window)

        refresh_ff_overlay._window_widgets = []  # type: ignore[attr-defined]
        apply_ff_overlay_settings(refresh=True)
        log("Overlay FF aberto e sincronizado com Kills FF/Fila FF.")

    def refresh_overlay_from_jarvis() -> None:
        if ff_overlay_site_sync_hidden:
            ff_overlay_status_var.set("Desativado")
            log("Atualizacao do Overlay FF pelo Jarvis desativada porque Kills FF e Fila FF estao ocultas.")
            refresh_ff_overlay(force=True)
            return
        fetch_panel_kills(force=True)
        fetch_ff_queue(force=True)
        fetch_ff_overlay(force=True)
        refresh_ff_overlay(force=True)

    def chat_source_key() -> str:
        return "websocket" if chat_source_var.get() == "TikFinity WebSocket" else "webhook"

    def raffle_source_key() -> str:
        return "browser" if raffle_source_mode_var.get() == "URL do chat (legado)" else "events"

    def raffle_entries_value(var: tk.StringVar, fallback: int) -> int:
        try:
            value = int(float(var.get().replace(",", ".")))
        except ValueError:
            value = fallback
        return max(1, min(50, value))

    def raffle_cooldown_seconds() -> int:
        try:
            value = int(float(raffle_cooldown_var.get().replace(",", ".")))
        except ValueError:
            value = 8
        return max(0, min(300, value))

    def chat_webhook_port() -> int:
        try:
            value = int(float(chat_webhook_port_var.get().replace(",", ".")))
        except ValueError:
            value = 8765
        return max(1024, min(65535, value))

    def chat_max_messages() -> int:
        try:
            value = int(config.get("chat_max_messages", 250))
        except (TypeError, ValueError):
            value = 250
        return max(50, min(1000, value))

    def chat_endpoint_url(include_token: bool = True) -> str:
        host = chat_webhook_host_var.get().strip() or "127.0.0.1"
        port = chat_webhook_port()
        token = chat_webhook_token_var.get().strip()
        url = f"http://{host}:{port}/api/chat-event"
        if include_token and token:
            url = f"{url}?token={token}"
        return url

    def update_chat_endpoint_text() -> None:
        if chat_source_key() == "websocket":
            url = chat_websocket_url_var.get().strip() or DEFAULT_TIKFINITY_WEBSOCKET_URL
            chat_endpoint_var.set(f"WebSocket: {url}")
        else:
            chat_endpoint_var.set(f"POST JSON: {chat_endpoint_url(include_token=True)}")

    def receive_chat_payload(payload: dict[str, Any], source: str) -> None:
        queued = enqueue_chat_event("message", {"payload": payload, "source": source})
        if queued:
            return

        dropped = int(getattr(receive_chat_payload, "_dropped", 0)) + 1
        receive_chat_payload._dropped = dropped  # type: ignore[attr-defined]
        now = time.monotonic()
        last_log_at = float(getattr(receive_chat_payload, "_last_log_at", 0.0))
        if now - last_log_at >= 8.0:
            log(f"Chat muito movimentado: {dropped} evento(s) antigo(s) omitidos para manter o app leve.")
            receive_chat_payload._dropped = 0  # type: ignore[attr-defined]
            receive_chat_payload._last_log_at = now  # type: ignore[attr-defined]

    def stop_chat_listener(silent: bool = False) -> None:
        nonlocal chat_webhook_server, chat_websocket_worker
        if chat_webhook_server is not None:
            chat_webhook_server.stop()
            chat_webhook_server = None
        if chat_websocket_worker is not None:
            worker = chat_websocket_worker
            chat_websocket_worker.stop()
            worker_thread = worker.thread
            if worker_thread is not None and worker_thread is not threading.current_thread():
                worker_thread.join(timeout=0.8)
            chat_websocket_worker = None
        chat_status_var.set("Desligado")
        if not silent:
            log("Leitor de chat parado.")

    def start_chat_listener(open_monitor: bool = True) -> None:
        nonlocal chat_webhook_server, chat_websocket_worker
        if chat_listener_hidden:
            chat_status_var.set("Desativado")
            log("Leitor de chat desativado porque a aba Chat Ao Vivo esta oculta.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
            stop_chat_listener(silent=True)
            if chat_source_key() == "websocket":
                websocket_url = normalize_tikfinity_websocket_url(chat_websocket_url_var.get())
                chat_websocket_url_var.set(websocket_url)
                local_config["chat_websocket_url"] = websocket_url
                save_config_snapshot_in_background(local_config)
                worker = ChatWebSocketWorker(websocket_url, receive_chat_payload, log)
                worker.start()
                chat_websocket_worker = worker
                chat_status_var.set("WebSocket ativo")
                log("Leitor de chat iniciado por WebSocket.")
            else:
                server = LocalChatWebhookServer(
                    chat_webhook_host_var.get().strip() or "127.0.0.1",
                    chat_webhook_port(),
                    chat_webhook_token_var.get().strip(),
                    receive_chat_payload,
                    log,
                )
                server.start()
                chat_webhook_server = server
                chat_status_var.set("Webhook ativo")
            update_chat_endpoint_text()
            schedule_chat_event_pump(0)
            if open_monitor:
                open_chat_monitor_window()
        except Exception as exc:
            chat_status_var.set("Erro")
            messagebox.showerror("Chat ao vivo", str(exc))

    def copy_chat_endpoint() -> None:
        update_chat_endpoint_text()
        root.clipboard_clear()
        root.clipboard_append(
            chat_endpoint_url(include_token=True)
            if chat_source_key() == "webhook"
            else normalize_tikfinity_websocket_url(chat_websocket_url_var.get())
        )
        log("Endpoint do chat copiado.")

    def clear_chat_messages() -> None:
        chat_messages.clear()
        chat_users.clear()
        chat_seen_messages.clear()
        refresh_chat_messages(force=True)
        chat_message_count_var.set("0")
        chat_user_count_var.set("0")
        chat_platform_var.set("-")
        log("Tela de chat limpa.")

    def live_chat_key(message: LiveChatMessage) -> str:
        if message.message_id:
            return f"{message.platform}|{message.user_id}|{message.message_id}"
        return f"{message.platform}|{message.user_id}|{message.username}|{message.comment}|{message.received_at}"

    def rebuild_recent_chat_users() -> None:
        chat_users.clear()
        for recent_message in chat_messages[-chat_max_messages() :]:
            user_key = recent_message.user_id or normalize_player_key(recent_message.username)
            if user_key:
                chat_users[user_key] = recent_message

    def normalize_bot_confirmation_text(value: Any) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

    def bot_reply_seen_in_chat(text: str, start_index: int = 0) -> bool:
        expected = normalize_bot_confirmation_text(text)
        if not expected:
            return False
        recent_messages = chat_messages[max(0, start_index) :]
        for chat_message in reversed(recent_messages[-80:]):
            if normalize_bot_confirmation_text(chat_message.comment) == expected:
                return True
        return False

    def confirm_bot_reply_from_chat(message: LiveChatMessage) -> None:
        if not bot_pending_confirmations:
            return
        received = normalize_bot_confirmation_text(message.comment)
        if not received:
            return
        for delivery_id, pending in list(bot_pending_confirmations.items()):
            expected = normalize_bot_confirmation_text(pending.get("message"))
            if expected and expected == received:
                bot_pending_confirmations.pop(delivery_id, None)
                bot_status_var.set("Confirmado na live")
                log(f"Bot confirmado no chat: {message.username}: {message.comment[:120]}")

    def apply_window_clickthrough(window: Any, enabled: bool) -> None:
        if os.name != "nt":
            return
        try:
            window.update_idletasks()
            hwnd = int(window.winfo_id())
            user32 = ctypes.windll.user32
            get_window_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
            set_window_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
            gwl_exstyle = -20
            ws_ex_transparent = 0x00000020
            ws_ex_layered = 0x00080000
            ws_ex_toolwindow = 0x00000080
            style = int(get_window_long(hwnd, gwl_exstyle))
            style |= ws_ex_layered | ws_ex_toolwindow
            if enabled:
                style |= ws_ex_transparent
            else:
                style &= ~ws_ex_transparent
            set_window_long(hwnd, gwl_exstyle, style)
        except Exception:
            pass

    def apply_chat_overlay_settings(refresh: bool = False) -> None:
        opacity = layout_value(chat_overlay_opacity_var, 35, 100)
        font_size = layout_value(chat_overlay_font_size_var, 10, 24)
        chat_overlay_opacity_text.set(f"{opacity}%")
        chat_overlay_font_size_text.set(f"{font_size}px")
        if chat_overlay_window is None:
            return
        try:
            chat_overlay_window.attributes("-topmost", True)
            chat_overlay_window.attributes("-alpha", max(0.35, min(1.0, opacity / 100)))
            if chat_overlay_controls_frame is not None:
                if chat_overlay_controls_var.get():
                    chat_overlay_controls_frame.grid()
                else:
                    chat_overlay_controls_frame.grid_remove()
            apply_window_clickthrough(chat_overlay_window, chat_overlay_clickthrough_var.get())
            if refresh:
                refresh_chat_messages(force=True)
        except tk.TclError:
            pass

    def close_chat_overlay() -> None:
        nonlocal chat_overlay_window, chat_overlay_messages_frame, chat_overlay_controls_frame
        if chat_overlay_window is not None:
            try:
                chat_overlay_width_var.set(max(300, int(chat_overlay_window.winfo_width())))
                chat_overlay_height_var.set(max(220, int(chat_overlay_window.winfo_height())))
                chat_overlay_window.destroy()
            except tk.TclError:
                pass
        chat_overlay_window = None
        chat_overlay_messages_frame = None
        chat_overlay_controls_frame = None
        for widget in chat_overlay_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        chat_overlay_widgets.clear()

    def open_chat_overlay_window() -> None:
        nonlocal chat_overlay_window, chat_overlay_messages_frame, chat_overlay_controls_frame
        chat_overlay_controls_var.set(True)
        chat_overlay_clickthrough_var.set(False)
        if chat_overlay_window is not None:
            try:
                if chat_overlay_window.winfo_exists():
                    chat_overlay_window.lift()
                    apply_chat_overlay_settings(refresh=True)
                    return
            except tk.TclError:
                pass

        width = layout_value(chat_overlay_width_var, 300, 900)
        height = layout_value(chat_overlay_height_var, 220, 1000)
        window = ctk.CTkToplevel(root)
        chat_overlay_window = window
        window.title("Chat Overlay - Aizen Stream Control")
        window.geometry(f"{width}x{height}+60+80")
        window.minsize(300, 220)
        window.resizable(True, True)
        window.overrideredirect(True)
        window.configure(fg_color="#050506")
        window.attributes("-topmost", True)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        if APP_ICON.exists():
            try:
                window.iconbitmap(str(APP_ICON))
            except tk.TclError:
                pass

        shell = ctk.CTkFrame(
            window,
            fg_color="#09090d",
            corner_radius=16,
            border_width=1,
            border_color=accent,
        )
        shell.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(shell, fg_color="#111016", corner_radius=12)
        chat_overlay_controls_frame = controls
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        controls.columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(
            controls,
            text="Chat Overlay",
            text_color=fg,
            font=("Segoe UI Semibold", 13),
            anchor="w",
        )
        title_label.grid(row=0, column=0, sticky="ew", padx=12, pady=8)
        ctk.CTkLabel(
            controls,
            text="arraste para mover",
            text_color=muted,
            font=("Segoe UI", 10),
        ).grid(row=0, column=1, sticky="e", padx=(0, 8), pady=8)

        def toggle_controls() -> None:
            chat_overlay_controls_var.set(False)
            apply_chat_overlay_settings()

        def enable_clickthrough() -> None:
            chat_overlay_clickthrough_var.set(True)
            apply_chat_overlay_settings()
            log("Overlay em modo click-through. Desative pela aba Chat Ao Vivo para mover ou fechar pelo mouse.")

        button(controls, "Ocultar", toggle_controls, "ghost", width=78).grid(row=0, column=2, sticky="e", padx=(0, 6), pady=6)
        button(controls, "Fixar", enable_clickthrough, "accent", width=70).grid(row=0, column=3, sticky="e", padx=(0, 6), pady=6)
        button(controls, "Teste", lambda: add_chat_test_message(), "default", width=70).grid(
            row=0, column=4, sticky="e", padx=(0, 6), pady=6
        )
        button(controls, "X", close_chat_overlay, "danger", width=42).grid(row=0, column=5, sticky="e", padx=(0, 8), pady=6)

        drag_state = {"x": 0, "y": 0}

        def start_drag(event: Any) -> None:
            if chat_overlay_clickthrough_var.get():
                return
            drag_state["x"] = event.x_root - window.winfo_x()
            drag_state["y"] = event.y_root - window.winfo_y()

        def drag_window(event: Any) -> None:
            if chat_overlay_clickthrough_var.get():
                return
            window.geometry(f"+{event.x_root - drag_state['x']}+{event.y_root - drag_state['y']}")

        for drag_widget in (controls, title_label):
            drag_widget.bind("<ButtonPress-1>", start_drag)
            drag_widget.bind("<B1-Motion>", drag_window)

        chat_overlay_messages_frame = ctk.CTkScrollableFrame(
            shell,
            fg_color="#050609",
            corner_radius=12,
            border_width=1,
            border_color="#2a161a",
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        chat_overlay_messages_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        chat_overlay_messages_frame.columnconfigure(0, weight=1)

        grip = ctk.CTkLabel(
            shell,
            text="resize",
            text_color=muted,
            font=("Segoe UI", 9),
            anchor="e",
        )
        grip.grid(row=2, column=0, sticky="e", padx=12, pady=(0, 8))
        resize_state = {"x": 0, "y": 0, "w": width, "h": height}

        def start_resize(event: Any) -> None:
            if chat_overlay_clickthrough_var.get():
                return
            resize_state["x"] = event.x_root
            resize_state["y"] = event.y_root
            resize_state["w"] = window.winfo_width()
            resize_state["h"] = window.winfo_height()

        def resize_window(event: Any) -> None:
            if chat_overlay_clickthrough_var.get():
                return
            new_width = max(300, resize_state["w"] + event.x_root - resize_state["x"])
            new_height = max(220, resize_state["h"] + event.y_root - resize_state["y"])
            chat_overlay_width_var.set(int(new_width))
            chat_overlay_height_var.set(int(new_height))
            window.geometry(f"{int(new_width)}x{int(new_height)}")
            refresh_chat_messages(force=True)

        grip.bind("<ButtonPress-1>", start_resize)
        grip.bind("<B1-Motion>", resize_window)

        def close_overlay_window() -> None:
            close_chat_overlay()

        window.protocol("WM_DELETE_WINDOW", close_overlay_window)
        try:
            delattr(refresh_chat_messages, "_signature")
        except AttributeError:
            pass
        apply_chat_overlay_settings(refresh=True)
        log("Overlay do chat aberto. Ajuste a posicao e depois use Fixar/click-through se quiser jogar por baixo.")

    def close_chat_monitor_window() -> None:
        nonlocal chat_monitor_window, chat_monitor_messages_frame, chat_monitor_always_on_top_var
        window = chat_monitor_window
        chat_monitor_window = None
        chat_monitor_messages_frame = None
        chat_monitor_always_on_top_var = None
        for widget in chat_monitor_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        chat_monitor_widgets.clear()
        if window is not None:
            try:
                window.destroy()
            except tk.TclError:
                pass

    def open_chat_monitor_window() -> None:
        nonlocal chat_monitor_window, chat_monitor_messages_frame, chat_monitor_always_on_top_var
        if chat_monitor_window is not None:
            try:
                if chat_monitor_window.winfo_exists():
                    chat_monitor_window.lift()
                    chat_monitor_window.focus_force()
                    refresh_chat_messages(force=True)
                    return
            except tk.TclError:
                pass

        window = ctk.CTkToplevel(root)
        chat_monitor_window = window
        chat_monitor_always_on_top_var = tk.BooleanVar(value=False)
        window.title("Chat Ao Vivo - Aizen Stream Control")
        window.geometry("760x900")
        window.minsize(520, 560)
        window.resizable(True, True)
        window.configure(fg_color=canvas_bg)
        window.columnconfigure(0, weight=1)
        window.rowconfigure(3, weight=1)
        if APP_ICON.exists():
            try:
                window.iconbitmap(str(APP_ICON))
            except tk.TclError:
                pass

        top = ctk.CTkFrame(window, fg_color=canvas_bg, corner_radius=0)
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
        top.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            top,
            text="Chat Ao Vivo",
            text_color=fg,
            font=("Segoe UI Semibold", 26),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            top,
            text="Monitor dedicado para acompanhar a live em tela cheia ou em outro monitor.",
            text_color=muted,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(2, 0))

        def maximize_monitor() -> None:
            try:
                window.state("zoomed")
            except tk.TclError:
                window.geometry(f"{window.winfo_screenwidth()}x{window.winfo_screenheight()}+0+0")

        def toggle_topmost() -> None:
            if chat_monitor_always_on_top_var is not None:
                window.attributes("-topmost", bool(chat_monitor_always_on_top_var.get()))

        monitor_actions = ctk.CTkFrame(top, fg_color=canvas_bg, corner_radius=0)
        monitor_actions.grid(row=0, column=1, rowspan=2, sticky="e")
        ctk.CTkCheckBox(
            monitor_actions,
            text="Sempre visível",
            variable=chat_monitor_always_on_top_var,
            command=toggle_topmost,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).pack(side=tk.LEFT, padx=(0, 8))
        button(monitor_actions, "Maximizar", maximize_monitor, "accent", width=100).pack(side=tk.LEFT, padx=(0, 8))
        button(monitor_actions, "Limpar", clear_chat_messages, "ghost", width=82).pack(side=tk.LEFT)

        monitor_metrics = ctk.CTkFrame(window, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
        monitor_metrics.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 10))
        for column in range(4):
            monitor_metrics.columnconfigure(column, weight=1)
        for col, label in enumerate(("Mensagens", "Usuários", "Plataforma", "Status")):
            ctk.CTkLabel(monitor_metrics, text=label, text_color=muted, font=("Segoe UI", 11)).grid(
                row=0, column=col, sticky="w", padx=18, pady=(14, 0)
            )
        ctk.CTkLabel(monitor_metrics, textvariable=chat_message_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=0, sticky="w", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(monitor_metrics, textvariable=chat_user_count_var, text_color=teal, font=("Segoe UI Semibold", 26)).grid(
            row=1, column=1, sticky="w", padx=18, pady=(0, 14)
        )
        ctk.CTkLabel(monitor_metrics, textvariable=chat_platform_var, text_color=accent, font=("Segoe UI Semibold", 14)).grid(
            row=1, column=2, sticky="w", padx=18, pady=(4, 14)
        )
        ctk.CTkLabel(monitor_metrics, textvariable=chat_status_var, text_color=accent, font=("Segoe UI Semibold", 14)).grid(
            row=1, column=3, sticky="w", padx=18, pady=(4, 14)
        )

        filter_bar = ctk.CTkFrame(window, fg_color=panel, corner_radius=12, border_width=1, border_color=border)
        filter_bar.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 10))
        filter_bar.columnconfigure(1, weight=1)
        ctk.CTkLabel(filter_bar, text="Filtro", text_color=muted, font=("Segoe UI", 12)).grid(
            row=0, column=0, sticky="w", padx=(14, 10), pady=12
        )
        entry(filter_bar, chat_filter_var).grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=12)

        chat_monitor_messages_frame = ctk.CTkScrollableFrame(
            window,
            fg_color=field,
            corner_radius=12,
            border_width=1,
            border_color=border,
            scrollbar_button_color=border,
            scrollbar_button_hover_color=accent,
        )
        chat_monitor_messages_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
        chat_monitor_messages_frame.columnconfigure(0, weight=1)

        window.protocol("WM_DELETE_WINDOW", close_chat_monitor_window)
        refresh_chat_messages(force=True)

    def add_live_chat_message(message: LiveChatMessage) -> None:
        key = live_chat_key(message)
        if key in chat_seen_messages:
            return
        chat_seen_messages.add(key)
        chat_messages.append(message)
        user_key = message.user_id or normalize_player_key(message.username)
        chat_users[user_key] = message
        limit = chat_max_messages()
        if len(chat_messages) > limit:
            removed = chat_messages[: len(chat_messages) - limit]
            del chat_messages[: len(chat_messages) - limit]
            for old_message in removed:
                chat_seen_messages.discard(live_chat_key(old_message))
            rebuild_recent_chat_users()
        elif len(chat_users) > CHAT_USER_CACHE_LIMIT:
            rebuild_recent_chat_users()
        chat_message_count_var.set(str(len(chat_messages)))
        chat_user_count_var.set(str(len(chat_users)))
        chat_platform_var.set(message.platform or "-")
        chat_status_var.set("Recebendo chat")

        confirm_bot_reply_from_chat(message)
        if raffle_worker is not None and getattr(raffle_worker, "source_mode", "browser") == "events":
            raffle_worker.handle_live_chat_event(message)
        handle_custom_chat_commands(message)

    def add_chat_test_message() -> None:
        now = datetime.now().strftime("%H:%M:%S")
        add_live_chat_message(
            LiveChatMessage(
                username="Teste Overlay",
                comment="Mensagem de teste do overlay. Se isto aparecer, a janela esta renderizando corretamente.",
                platform="Aizen",
                received_at=now,
                message_id=f"overlay-test-{time.time()}",
                source="local",
            )
        )
        refresh_chat_messages(force=True)
        log("Mensagem de teste enviada para o chat ao vivo.")

    def visible_chat_messages() -> list[LiveChatMessage]:
        filter_text = chat_filter_var.get().strip().casefold()
        return [
            message
            for message in chat_messages
            if not filter_text
            or filter_text in message.username.casefold()
            or filter_text in message.comment.casefold()
            or filter_text in message.platform.casefold()
        ][-140:]

    CHAT_EMPTY_KEY = "__empty_chat__"

    def chat_row_color(row_index: int) -> str:
        return "#171014" if row_index % 2 == 0 else "#0f0b0e"

    def chat_widget_key(widget: Any) -> str:
        return str(getattr(widget, "_chat_key", ""))

    def cancel_chat_incremental_render(widget_store: list[Any]) -> None:
        store_key = id(widget_store)
        chat_render_generations[store_key] = chat_render_generations.get(store_key, 0) + 1
        after_id = chat_render_after_ids.pop(store_key, None)
        if after_id is None:
            return
        try:
            root.after_cancel(after_id)
        except tk.TclError:
            pass

    def destroy_chat_widgets(widget_store: list[Any]) -> None:
        cancel_chat_incremental_render(widget_store)
        for widget in widget_store:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        widget_store.clear()

    def scroll_chat_to_bottom(target_frame: Any) -> None:
        def do_scroll() -> None:
            try:
                target_frame._parent_canvas.yview_moveto(1.0)  # type: ignore[attr-defined]
            except Exception:
                pass

        try:
            target_frame.after_idle(do_scroll)
        except tk.TclError:
            pass

    def render_empty_chat(target_frame: Any, widget_store: list[Any], large: bool, overlay: bool = False) -> None:
        if len(widget_store) == 1 and chat_widget_key(widget_store[0]) == CHAT_EMPTY_KEY:
            return
        destroy_chat_widgets(widget_store)
        if overlay:
            empty = ctk.CTkFrame(
                target_frame,
                fg_color="#101016",
                corner_radius=14,
                border_width=1,
                border_color=accent,
            )
            empty._chat_key = CHAT_EMPTY_KEY  # type: ignore[attr-defined]
            empty.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            empty.columnconfigure(0, weight=1)
            ctk.CTkLabel(
                empty,
                text="Aguardando chat",
                text_color=accent,
                font=("Segoe UI Semibold", max(12, layout_value(chat_overlay_font_size_var, 10, 24))),
                anchor="w",
            ).grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
            ctk.CTkLabel(
                empty,
                text="Abra o Chat Ao Vivo e envie uma mensagem. Use o botao Teste para conferir o overlay.",
                text_color=fg,
                font=("Segoe UI", max(10, layout_value(chat_overlay_font_size_var, 10, 24) - 2)),
                wraplength=max(220, layout_value(chat_overlay_width_var, 300, 900) - 54),
                justify="left",
                anchor="w",
            ).grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 12))
            widget_store.append(empty)
            return

        empty = ctk.CTkLabel(
            target_frame,
            text="Nenhuma mensagem recebida ainda",
            text_color=muted,
            font=("Segoe UI", 15 if large else 13),
        )
        empty._chat_key = CHAT_EMPTY_KEY  # type: ignore[attr-defined]
        empty.grid(row=0, column=0, sticky="ew", padx=14, pady=16)
        widget_store.append(empty)

    def build_chat_message_widget(
        target_frame: Any,
        message: LiveChatMessage,
        row_index: int,
        large: bool,
        overlay: bool = False,
    ) -> Any:
        if overlay:
            font_size = layout_value(chat_overlay_font_size_var, 10, 24)
            compact = bool(chat_overlay_compact_var.get())
            avatar_size = 30 if compact else 40
            name_font = ("Segoe UI Semibold", max(10, font_size - 1))
            meta_font = ("Segoe UI", max(8, font_size - 4))
            message_font = ("Segoe UI", font_size)
            wraplength = max(210, layout_value(chat_overlay_width_var, 300, 900) - (92 if compact else 110))
            row_fg = "#101016" if row_index % 2 == 0 else "#090a0f"
            corner_radius = 12
            row_pad = 4 if compact else 6
        else:
            avatar_size = 54 if large else 44
            name_font = ("Segoe UI Semibold", 16 if large else 13)
            meta_font = ("Segoe UI", 11 if large else 10)
            message_font = ("Segoe UI", 15 if large else 12)
            wraplength = 1360 if large else 980
            row_fg = chat_row_color(row_index)
            corner_radius = 12 if large else 10
            row_pad = 5

        item = ctk.CTkFrame(
            target_frame,
            fg_color=row_fg,
            corner_radius=corner_radius,
            border_width=1 if overlay else 0,
            border_color="#2b181d" if overlay else row_fg,
        )
        item._chat_key = live_chat_key(message)  # type: ignore[attr-defined]
        item.grid(row=row_index, column=0, sticky="ew", padx=8, pady=row_pad)
        item.columnconfigure(1, weight=1)
        avatar = make_avatar_label(item, message.username, message.avatar_url, size=avatar_size)
        avatar.grid(row=0, column=0, rowspan=2, sticky="nw", padx=(10, 8), pady=8 if overlay else 10)
        item._chat_avatar_label = avatar  # type: ignore[attr-defined]
        meta = ctk.CTkFrame(item, fg_color="transparent", corner_radius=0)
        meta.grid(row=0, column=1, sticky="ew", padx=(0, 10 if overlay else 12), pady=(7 if overlay else 9, 0))
        meta.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            meta,
            text=message.username,
            text_color=accent if overlay else fg,
            font=name_font,
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        if not overlay or not chat_overlay_compact_var.get():
            ctk.CTkLabel(
                meta,
                text=f"{message.platform or 'Live'} • {message.received_at}",
                text_color=muted,
                font=meta_font,
                anchor="e",
            ).grid(row=0, column=1, sticky="e", padx=(8, 0))
        ctk.CTkLabel(
            item,
            text=message.comment,
            text_color=fg,
            font=message_font,
            wraplength=wraplength,
            justify="left",
            anchor="w",
        ).grid(row=1, column=1, sticky="ew", padx=(0, 12 if overlay else 14), pady=(0, 8 if overlay else 11))
        return item

    def reindex_chat_widgets(widget_store: list[Any], overlay: bool = False) -> None:
        for row_index, widget in enumerate(widget_store):
            try:
                widget.grid(row=row_index, column=0, sticky="ew", padx=8, pady=5)
                widget.configure(fg_color=("#101016" if row_index % 2 == 0 else "#090a0f") if overlay else chat_row_color(row_index))
            except tk.TclError:
                pass

    def update_chat_avatar_widget_keys(keys: set[tuple[str, int]]) -> None:
        clean_keys = {(url.strip(), size) for url, size in keys if str(url or "").strip()}
        if not clean_keys:
            return
        for widget_store in (chat_widgets, chat_monitor_widgets, chat_overlay_widgets):
            for widget in widget_store:
                label = getattr(widget, "_chat_avatar_label", None)
                if label is None:
                    continue
                label_key = (
                    str(getattr(label, "_avatar_url", "")).strip(),
                    int(getattr(label, "_avatar_size", 0) or 0),
                )
                if label_key not in clean_keys:
                    continue
                name = str(getattr(label, "_avatar_name", ""))
                image = avatar_image_cache.get(label_key)
                try:
                    label.configure(image=image, text="" if image else avatar_initials(name))
                    label._avatar_image = image  # type: ignore[attr-defined]
                except tk.TclError:
                    pass

    def update_chat_avatar_widgets(url: str, size: int) -> None:
        update_chat_avatar_widget_keys({((url or "").strip(), size)})

    def render_chat_messages(
        target_frame: Any,
        widget_store: list[Any],
        visible: list[LiveChatMessage],
        large: bool = False,
        force: bool = False,
        overlay: bool = False,
    ) -> None:
        def start_incremental_full_render() -> None:
            snapshot = list(visible)
            destroy_chat_widgets(widget_store)
            store_key = id(widget_store)
            generation = chat_render_generations.get(store_key, 0)

            def render_chunk(start_index: int = 0) -> None:
                chat_render_after_ids.pop(store_key, None)
                if app_closing or chat_render_generations.get(store_key, 0) != generation:
                    return
                try:
                    if not target_frame.winfo_exists():
                        return
                except tk.TclError:
                    return
                end_index = min(len(snapshot), start_index + CHAT_RENDER_CHUNK_SIZE)
                for row_index in range(start_index, end_index):
                    try:
                        widget_store.append(build_chat_message_widget(target_frame, snapshot[row_index], row_index, large, overlay))
                    except tk.TclError:
                        return
                if end_index < len(snapshot):
                    try:
                        chat_render_after_ids[store_key] = root.after(
                            CHAT_RENDER_CHUNK_DELAY_MS,
                            lambda next_index=end_index: render_chunk(next_index),
                        )
                    except tk.TclError:
                        pass
                    return
                scroll_chat_to_bottom(target_frame)

            try:
                chat_render_after_ids[store_key] = root.after(0, render_chunk)
            except tk.TclError:
                pass

        if force:
            destroy_chat_widgets(widget_store)

        if not visible:
            render_empty_chat(target_frame, widget_store, large, overlay=overlay)
            return

        if len(widget_store) == 1 and chat_widget_key(widget_store[0]) == CHAT_EMPTY_KEY:
            destroy_chat_widgets(widget_store)

        new_keys = [live_chat_key(message) for message in visible]
        old_keys = [chat_widget_key(widget) for widget in widget_store]

        if old_keys == new_keys:
            return

        if not widget_store:
            if len(visible) >= CHAT_RENDER_INCREMENTAL_THRESHOLD:
                start_incremental_full_render()
                return
            for row_index, message in enumerate(visible):
                widget_store.append(build_chat_message_widget(target_frame, message, row_index, large, overlay))
            scroll_chat_to_bottom(target_frame)
            return

        if not force and old_keys:
            max_overlap = min(len(old_keys), len(new_keys))
            overlap = 0
            for size in range(max_overlap, 0, -1):
                if old_keys[-size:] == new_keys[:size]:
                    overlap = size
                    break
            if overlap and overlap >= max(1, max_overlap - 20):
                remove_count = len(old_keys) - overlap
                for widget in widget_store[:remove_count]:
                    try:
                        widget.destroy()
                    except tk.TclError:
                        pass
                del widget_store[:remove_count]
                for message in visible[overlap:]:
                    widget_store.append(build_chat_message_widget(target_frame, message, len(widget_store), large, overlay))
                reindex_chat_widgets(widget_store, overlay=overlay)
                scroll_chat_to_bottom(target_frame)
                return

        if len(visible) >= CHAT_RENDER_INCREMENTAL_THRESHOLD:
            start_incremental_full_render()
            return
        destroy_chat_widgets(widget_store)
        if not visible:
            empty = ctk.CTkLabel(
                target_frame,
                text="Nenhuma mensagem recebida ainda",
                text_color=muted,
                font=("Segoe UI", 15 if large else 13),
            )
            empty._chat_key = CHAT_EMPTY_KEY  # type: ignore[attr-defined]
            empty.grid(row=0, column=0, sticky="ew", padx=14, pady=16)
            widget_store.append(empty)
            return

        for row_index, message in enumerate(visible):
            widget_store.append(build_chat_message_widget(target_frame, message, row_index, large, overlay))
        scroll_chat_to_bottom(target_frame)

    def refresh_chat_messages(force: bool = False) -> None:
        render_main_chat = not chat_tab_hidden
        render_monitor_chat = chat_monitor_messages_frame is not None
        render_overlay_chat = chat_overlay_messages_frame is not None
        if not (render_main_chat or render_monitor_chat or render_overlay_chat):
            return
        visible = visible_chat_messages()
        signature = [
            (
                message.received_at,
                message.username,
                message.comment,
                message.avatar_url,
                message.platform,
            )
            for message in visible
        ]
        if not force and getattr(refresh_chat_messages, "_signature", None) == signature:
            return
        refresh_chat_messages._signature = signature  # type: ignore[attr-defined]

        if render_main_chat:
            render_chat_messages(chat_messages_frame, chat_widgets, visible, large=False, force=force)
        elif chat_widgets:
            destroy_chat_widgets(chat_widgets)
        if render_monitor_chat:
            try:
                render_chat_messages(chat_monitor_messages_frame, chat_monitor_widgets, visible, large=True, force=force)
            except tk.TclError:
                pass
        if render_overlay_chat:
            try:
                render_chat_messages(chat_overlay_messages_frame, chat_overlay_widgets, visible, large=False, force=force, overlay=True)
            except tk.TclError:
                pass

    def chat_event_runtime_active() -> bool:
        if chat_commands_enabled_var.get() or chat_timers_enabled_var.get() or bot_pending_confirmations:
            return True
        if not chat_tab_hidden or chat_monitor_messages_frame is not None or chat_overlay_messages_frame is not None:
            return True
        try:
            return bool(raffle_worker and raffle_worker.is_running())
        except Exception:
            return False

    def schedule_chat_event_pump(delay_ms: int = 0) -> None:
        nonlocal chat_event_pump_after_id
        if app_closing:
            return
        if not in_ui_thread():
            return
        if chat_event_pump_after_id is not None:
            try:
                root.after_cancel(chat_event_pump_after_id)
            except tk.TclError:
                pass
        chat_event_pump_after_id = root.after(max(0, delay_ms), pump_chat_event_queue)

    def pump_chat_event_queue() -> None:
        nonlocal chat_event_pump_after_id, chat_event_quiet_cycles
        chat_event_pump_after_id = None
        if app_closing:
            return
        updated = False
        processed = False
        processed_count = 0
        batch_limit = CHAT_EVENT_BATCH_LIMIT
        deadline = time.monotonic() + UI_PUMP_TIME_BUDGET_SECONDS
        while processed_count < batch_limit:
            if processed_count and time.monotonic() >= deadline:
                break
            try:
                kind, payload = chat_event_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            processed = True
            if kind == "message":
                raw_payload = payload.get("payload") if isinstance(payload, dict) else None
                source = str(payload.get("source") or "") if isinstance(payload, dict) else ""
                if isinstance(raw_payload, LiveChatMessage):
                    message = raw_payload
                else:
                    message = normalize_live_chat_payload(raw_payload, source=source)
                if message is not None:
                    add_live_chat_message(message)
                    updated = True
                elif is_live_chat_event_payload(raw_payload):
                    now = time.monotonic()
                    pending_unknown = int(getattr(pump_chat_event_queue, "_pending_unknown", 0)) + 1
                    last_unknown_log = float(getattr(pump_chat_event_queue, "_last_unknown_log_at", 0.0))
                    pump_chat_event_queue._pending_unknown = pending_unknown  # type: ignore[attr-defined]
                    if now - last_unknown_log >= 5.0:
                        suffix = f" ({pending_unknown} eventos acumulados)" if pending_unknown > 1 else ""
                        log(f"Evento de chat recebido, mas nao exibido{suffix}: {compact_json_preview(raw_payload)}")
                        pump_chat_event_queue._pending_unknown = 0  # type: ignore[attr-defined]
                        pump_chat_event_queue._last_unknown_log_at = now  # type: ignore[attr-defined]
            elif kind == "status":
                chat_status_var.set(str(payload))
        if updated:
            refresh_chat_messages()
        if app_closing:
            return
        if processed:
            chat_event_quiet_cycles = 0
        else:
            chat_event_quiet_cycles = min(chat_event_quiet_cycles + 1, 8)
        if not chat_event_queue.empty():
            schedule_chat_event_pump(CHAT_EVENT_BUSY_PUMP_MS)
        elif chat_event_runtime_active():
            visible_chat_active = (
                not chat_tab_hidden
                or chat_monitor_messages_frame is not None
                or chat_overlay_messages_frame is not None
            )
            try:
                raffle_active = bool(raffle_worker and raffle_worker.is_running())
            except Exception:
                raffle_active = False
            if chat_event_quiet_cycles < 3:
                idle_delay_ms = CHAT_EVENT_IDLE_PUMP_MS
            elif visible_chat_active or bot_pending_confirmations or raffle_active:
                idle_delay_ms = CHAT_EVENT_QUIET_PUMP_MS
            else:
                idle_delay_ms = CHAT_EVENT_BACKGROUND_QUIET_PUMP_MS
            schedule_chat_event_pump(idle_delay_ms)

    def bot_safe_delay_seconds() -> int:
        try:
            value = int(float(bot_safe_delay_var.get().replace(",", ".")))
        except ValueError:
            value = 15
        value = max(15, value)
        bot_safe_delay_var.set(str(value))
        return value

    def bot_default_cooldown_seconds() -> int:
        try:
            value = int(float(bot_default_cooldown_var.get().replace(",", ".")))
        except ValueError:
            value = 30
        value = max(0, value)
        bot_default_cooldown_var.set(str(value))
        return value

    def bot_default_timer_interval_seconds() -> int:
        try:
            value = int(float(bot_default_timer_interval_var.get().replace(",", ".")))
        except ValueError:
            value = 600
        value = max(60, value)
        bot_default_timer_interval_var.set(str(value))
        return value

    def bot_default_timer_min_messages() -> int:
        try:
            value = int(float(bot_default_timer_min_messages_var.get().replace(",", ".")))
        except ValueError:
            value = 5
        value = max(0, value)
        bot_default_timer_min_messages_var.set(str(value))
        return value

    def bot_delivery_method_key() -> str:
        return bot_delivery_method_from_label(bot_delivery_method_var.get())

    def stop_tikfinity_direct_bridge(silent: bool = False) -> None:
        nonlocal bot_bridge_server
        if bot_bridge_server is None:
            return
        bot_bridge_server.stop()
        bot_bridge_server = None
        if not silent:
            log("Ponte direta do TikFinity parada.")

    def ensure_tikfinity_direct_bridge() -> TikfinityDirectBridgeServer:
        nonlocal bot_bridge_server
        if app_closing:
            raise RuntimeError("O app esta fechando; ponte do TikFinity nao pode iniciar.")
        preferred_url = normalize_streamerbot_websocket_url(bot_streamerbot_ws_url_var.get())
        bot_streamerbot_ws_url_var.set(preferred_url)
        candidate_urls = tikfinity_direct_bridge_url_candidates(preferred_url)
        if bot_bridge_server is not None and bot_bridge_server.url in candidate_urls and bot_bridge_server.is_running():
            return bot_bridge_server
        stop_tikfinity_direct_bridge(silent=True)
        port_errors: list[str] = []
        for candidate_url in candidate_urls:
            server = TikfinityDirectBridgeServer(candidate_url, log)
            try:
                server.start()
            except TikfinityBridgePortInUseError as exc:
                port_errors.append(str(exc))
                continue
            bot_bridge_server = server
            if server.url != preferred_url:
                bot_streamerbot_ws_url_var.set(server.url)
                log(
                    f"Porta da ponte TikFinity ocupada ({preferred_url}). "
                    f"Use no TikFinity: Setup > Streamer.bot Connection = {server.url}"
                )
            log(f"Ponte direta do TikFinity ativa em {server.url}.")
            return server
        detail = " ".join(port_errors) or "Todas as portas alternativas falharam."
        raise RuntimeError(
            "Nao consegui abrir a ponte direta do TikFinity. "
            f"{detail} Feche o programa usando a porta ou configure no TikFinity uma porta livre como "
            "ws://127.0.0.1:8081/."
        )

    def refresh_tikfinity_direct_bridge(*_args: Any) -> None:
        if app_closing:
            return
        if bot_delivery_method_key() != BOT_DELIVERY_TIKFINITY_DIRECT:
            stop_tikfinity_direct_bridge(silent=True)
            return
        if not (chat_commands_enabled_var.get() or chat_timers_enabled_var.get()):
            stop_tikfinity_direct_bridge(silent=True)
            return
        try:
            ensure_tikfinity_direct_bridge()
            if bot_status_var.get() in {"Desligado", "Erro"}:
                bot_status_var.set("Ponte direta ativa")
        except Exception as exc:
            bot_status_var.set("Erro")
            log(f"Erro na ponte direta do TikFinity: {exc}")

    def bot_ignored_usernames() -> set[str]:
        raw = bot_ignore_usernames_var.get()
        return {item.strip().casefold() for item in re.split(r"[,;\n]+", raw) if item.strip()}

    def bot_settings_from_vars() -> dict[str, Any]:
        method = bot_delivery_method_key()
        settings = {
            "method": method,
            "websocket_url": normalize_streamerbot_websocket_url(bot_streamerbot_ws_url_var.get()),
            "http_url": normalize_streamerbot_http_url(bot_streamerbot_http_url_var.get()),
            "password": bot_streamerbot_password_var.get(),
            "action_name": bot_streamerbot_action_name_var.get().strip(),
            "action_id": bot_streamerbot_action_id_var.get().strip(),
        }
        if method == BOT_DELIVERY_TIKFINITY_DIRECT:
            settings["bridge_server"] = ensure_tikfinity_direct_bridge()
        return settings

    def update_bot_queue_count() -> None:
        bot_queue_count_var.set(str(bot_reply_queue.qsize()))

    def default_custom_commands() -> list[ChatCommand]:
        return [
            ChatCommand("!pix", "Pix do Aizen: coloque sua chave aqui, {user}.", False, 45),
            ChatCommand("!dc", "Entre no Discord: coloque seu convite aqui.", False, 45),
        ]

    def default_chat_timers() -> list[ChatTimer]:
        return [
            ChatTimer("Discord", "Entre no Discord do Aizen: coloque seu convite aqui.", False, 600, 6),
            ChatTimer("LivePix", "Apoie a live pelo LivePix: coloque seu link ou chave aqui.", False, 600, 8),
        ]

    def enqueue_bot_reply_payload(payload: dict[str, Any]) -> bool:
        try:
            bot_reply_queue.put_nowait(payload)
            return True
        except queue.Full:
            pass
        try:
            bot_reply_queue.get_nowait()
            note_queue_drop("bot_reply", "Fila do bot cheia")
        except queue.Empty:
            pass
        try:
            bot_reply_queue.put_nowait(payload)
            return True
        except queue.Full:
            note_queue_drop("bot_reply", "Fila do bot cheia")
            return False

    def enqueue_bot_send_result(ok: bool, detail: str, payload: dict[str, Any]) -> None:
        result = (ok, detail, payload)
        try:
            bot_send_result_queue.put_nowait(result)
            return
        except queue.Full:
            pass
        try:
            bot_send_result_queue.get_nowait()
            note_queue_drop("bot_result", "Fila de retorno do bot cheia")
        except queue.Empty:
            pass
        try:
            bot_send_result_queue.put_nowait(result)
        except queue.Full:
            note_queue_drop("bot_result", "Fila de retorno do bot cheia")

    def reindex_custom_command_rows() -> None:
        for index, row in enumerate(custom_command_rows):
            frame = row["frame"]
            try:
                frame.grid(row=index, column=0, sticky="ew", padx=8, pady=(8 if index == 0 else 4, 4))
            except tk.TclError:
                pass

    def mark_custom_command_cache_dirty(*_args: Any) -> None:
        nonlocal custom_command_cache_dirty
        custom_command_cache_dirty = True

    def remove_custom_command_row(row: dict[str, Any]) -> None:
        if row in custom_command_rows:
            custom_command_rows.remove(row)
            mark_custom_command_cache_dirty()
        try:
            row["frame"].destroy()
        except tk.TclError:
            pass
        if not custom_command_bulk_loading:
            reindex_custom_command_rows()
            try:
                schedule_config_autosave()
            except NameError:
                pass

    def add_custom_command_row(
        command: str = "",
        response: str = "",
        cooldown: int | None = None,
        enabled: bool = True,
    ) -> None:
        nonlocal custom_command_rows_loaded
        if not custom_command_rows_loaded and not custom_command_bulk_loading:
            ensure_custom_command_rows_rendered()
        if cooldown is None:
            cooldown = bot_default_cooldown_seconds()
        frame = ctk.CTkFrame(commands_table_frame, fg_color="#101016", corner_radius=10)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=4)
        enabled_var = tk.BooleanVar(value=enabled)
        command_var = tk.StringVar(value=command)
        response_var = tk.StringVar(value=response)
        cooldown_var = tk.StringVar(value=str(max(0, int(cooldown))))
        row: dict[str, Any] = {
            "frame": frame,
            "enabled": enabled_var,
            "command": command_var,
            "response": response_var,
            "cooldown": cooldown_var,
        }
        ctk.CTkCheckBox(
            frame,
            text="",
            width=28,
            variable=enabled_var,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=0, sticky="w", padx=(10, 4), pady=10)
        entry(frame, command_var, width=130).grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        entry(frame, response_var).grid(row=0, column=2, sticky="ew", padx=6, pady=10)
        entry(frame, cooldown_var, width=82).grid(row=0, column=3, sticky="ew", padx=6, pady=10)
        button(frame, "Teste", lambda command_row=row: test_custom_command_row(command_row), "default", width=66).grid(
            row=0, column=4, sticky="e", padx=6, pady=10
        )
        button(frame, "X", lambda command_row=row: remove_custom_command_row(command_row), "danger", width=42).grid(
            row=0, column=5, sticky="e", padx=(0, 10), pady=10
        )
        custom_command_rows.append(row)
        custom_command_rows_loaded = True
        for variable in (enabled_var, command_var, response_var, cooldown_var):
            variable.trace_add("write", lambda *_args: (mark_custom_command_cache_dirty(), schedule_config_autosave()))
        mark_custom_command_cache_dirty()
        if not custom_command_bulk_loading:
            reindex_custom_command_rows()

    def collect_custom_commands(normalize_inputs: bool = True) -> list[ChatCommand]:
        nonlocal custom_command_cache, custom_command_lookup_cache, custom_command_cache_dirty
        if not custom_command_rows_loaded:
            custom_command_cache_dirty = False
            custom_command_lookup_cache = {command.command: command for command in custom_command_cache}
            return list(custom_command_cache)
        commands: list[ChatCommand] = []
        seen: set[str] = set()
        for row in custom_command_rows:
            command = normalize_chat_command(row["command"].get())
            response = row["response"].get().strip()
            if not command or not response or command in seen:
                continue
            try:
                cooldown = int(float(row["cooldown"].get().replace(",", ".")))
            except ValueError:
                cooldown = bot_default_cooldown_seconds()
            cooldown = max(0, cooldown)
            if normalize_inputs:
                if row["command"].get() != command:
                    row["command"].set(command)
                if row["cooldown"].get() != str(cooldown):
                    row["cooldown"].set(str(cooldown))
            commands.append(
                ChatCommand(
                    command=command,
                    response=response,
                    enabled=bool(row["enabled"].get()),
                    cooldown_seconds=cooldown,
                )
            )
            seen.add(command)
        custom_command_cache = commands
        custom_command_lookup_cache = {command.command: command for command in commands}
        custom_command_cache_dirty = False
        return commands

    def runtime_custom_command(token: str) -> ChatCommand | None:
        if custom_command_cache_dirty:
            collect_custom_commands(normalize_inputs=False)
        return custom_command_lookup_cache.get(token)

    def set_custom_commands(commands: list[ChatCommand], render: bool = False) -> None:
        nonlocal custom_command_bulk_loading, custom_command_cache, custom_command_lookup_cache
        nonlocal custom_command_cache_dirty, custom_command_rows_loaded
        commands = list(commands or default_custom_commands())
        custom_command_cache = commands
        custom_command_lookup_cache = {command.command: command for command in commands}
        custom_command_cache_dirty = False
        if not render:
            custom_command_rows_loaded = False
            return
        previous_bulk_loading = custom_command_bulk_loading
        custom_command_bulk_loading = True
        try:
            for row in list(custom_command_rows):
                remove_custom_command_row(row)
            custom_command_rows_loaded = True
            for command in commands:
                add_custom_command_row(command.command, command.response, command.cooldown_seconds, command.enabled)
        finally:
            custom_command_bulk_loading = previous_bulk_loading
        collect_custom_commands(normalize_inputs=False)
        reindex_custom_command_rows()

    def ensure_custom_command_rows_rendered() -> None:
        if custom_command_rows_loaded:
            return
        set_custom_commands(custom_command_cache or default_custom_commands(), render=True)

    def reindex_chat_timer_rows() -> None:
        for index, row in enumerate(chat_timer_rows):
            frame = row["frame"]
            try:
                frame.grid(row=index, column=0, sticky="ew", padx=8, pady=(8 if index == 0 else 4, 4))
            except tk.TclError:
                pass

    def remove_chat_timer_row(row: dict[str, Any]) -> None:
        if row in chat_timer_rows:
            chat_timer_rows.remove(row)
        chat_timer_runtime.pop(row.get("id", ""), None)
        try:
            row["frame"].destroy()
        except tk.TclError:
            pass
        if not chat_timer_bulk_loading:
            reindex_chat_timer_rows()
            try:
                schedule_config_autosave()
            except NameError:
                pass

    def add_chat_timer_row(
        name: str = "",
        message: str = "",
        interval: int | None = None,
        min_messages: int | None = None,
        enabled: bool = True,
    ) -> None:
        nonlocal chat_timer_rows_loaded
        if not chat_timer_rows_loaded and not chat_timer_bulk_loading:
            ensure_chat_timer_rows_rendered()
        if interval is None:
            interval = bot_default_timer_interval_seconds()
        if min_messages is None:
            min_messages = bot_default_timer_min_messages()
        frame = ctk.CTkFrame(timers_table_frame, fg_color="#101016", corner_radius=10)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=4)
        enabled_var = tk.BooleanVar(value=enabled)
        name_var = tk.StringVar(value=name)
        message_var = tk.StringVar(value=message)
        interval_var = tk.StringVar(value=str(max(60, int(interval))))
        min_messages_var = tk.StringVar(value=str(max(0, int(min_messages))))
        row: dict[str, Any] = {
            "id": uuid.uuid4().hex,
            "frame": frame,
            "enabled": enabled_var,
            "name": name_var,
            "message": message_var,
            "interval": interval_var,
            "min_messages": min_messages_var,
        }
        ctk.CTkCheckBox(
            frame,
            text="",
            width=28,
            variable=enabled_var,
            fg_color=accent,
            hover_color=accent_hover,
            border_color=border,
            text_color=fg,
        ).grid(row=0, column=0, sticky="w", padx=(10, 4), pady=10)
        entry(frame, name_var, width=130).grid(row=0, column=1, sticky="ew", padx=6, pady=10)
        entry(frame, message_var).grid(row=0, column=2, sticky="ew", padx=6, pady=10)
        entry(frame, interval_var, width=90).grid(row=0, column=3, sticky="ew", padx=6, pady=10)
        entry(frame, min_messages_var, width=84).grid(row=0, column=4, sticky="ew", padx=6, pady=10)
        button(frame, "Teste", lambda timer_row=row: test_chat_timer_row(timer_row), "default", width=66).grid(
            row=0, column=5, sticky="e", padx=6, pady=10
        )
        button(frame, "X", lambda timer_row=row: remove_chat_timer_row(timer_row), "danger", width=42).grid(
            row=0, column=6, sticky="e", padx=(0, 10), pady=10
        )
        chat_timer_rows.append(row)
        chat_timer_rows_loaded = True
        for variable in (enabled_var, name_var, message_var, interval_var, min_messages_var):
            variable.trace_add("write", lambda *_args: schedule_config_autosave())
        if not chat_timer_bulk_loading:
            reindex_chat_timer_rows()

    def timer_row_interval_seconds(row: dict[str, Any]) -> int:
        try:
            value = int(float(row["interval"].get().replace(",", ".")))
        except ValueError:
            value = bot_default_timer_interval_seconds()
        return max(60, value)

    def timer_row_min_messages(row: dict[str, Any]) -> int:
        try:
            value = int(float(row["min_messages"].get().replace(",", ".")))
        except ValueError:
            value = bot_default_timer_min_messages()
        return max(0, value)

    def collect_chat_timers() -> list[ChatTimer]:
        nonlocal chat_timer_cache
        if not chat_timer_rows_loaded:
            return list(chat_timer_cache)
        timers: list[ChatTimer] = []
        seen: set[str] = set()
        for row in chat_timer_rows:
            name = re.sub(r"\s+", " ", row["name"].get().strip())[:80]
            message = re.sub(r"\s+", " ", row["message"].get().strip())
            key = name.casefold()
            if not name or not message or key in seen:
                continue
            interval = timer_row_interval_seconds(row)
            min_messages = timer_row_min_messages(row)
            row["name"].set(name)
            row["message"].set(message)
            row["interval"].set(str(interval))
            row["min_messages"].set(str(min_messages))
            timers.append(
                ChatTimer(
                    name=name,
                    message=message,
                    enabled=bool(row["enabled"].get()),
                    interval_seconds=interval,
                    min_chat_messages=min_messages,
                )
            )
            seen.add(key)
        chat_timer_cache = timers
        return timers

    def set_chat_timers(timers: list[ChatTimer], render: bool | None = None) -> None:
        nonlocal chat_timer_bulk_loading, chat_timer_cache, chat_timer_rows_loaded
        timers = list(timers or default_chat_timers())
        chat_timer_cache = timers
        if render is None:
            render = False
        if not render:
            chat_timer_rows_loaded = False
            return
        previous_bulk_loading = chat_timer_bulk_loading
        chat_timer_bulk_loading = True
        try:
            for row in list(chat_timer_rows):
                remove_chat_timer_row(row)
            chat_timer_rows_loaded = True
            for timer in timers:
                add_chat_timer_row(
                    timer.name,
                    timer.message,
                    timer.interval_seconds,
                    timer.min_chat_messages,
                    timer.enabled,
                )
        finally:
            chat_timer_bulk_loading = previous_bulk_loading
        chat_timer_cache = collect_chat_timers()
        reindex_chat_timer_rows()

    def ensure_chat_timer_rows_rendered() -> None:
        if chat_timer_rows_loaded:
            return
        set_chat_timers(chat_timer_cache or default_chat_timers(), render=True)

    def chat_timer_cache_id(timer: ChatTimer) -> str:
        source = (
            f"{timer.name.casefold()}\0{timer.message}\0"
            f"{int(timer.interval_seconds)}\0{int(timer.min_chat_messages)}"
        )
        return f"cache:{hashlib.sha1(source.encode('utf-8', errors='ignore')).hexdigest()[:16]}"

    def queue_chat_timer_payload(timer_id: str, name: str, template: str, test: bool = False) -> bool:
        clean_name = re.sub(r"\s+", " ", str(name or "").strip())[:80] or "Timer"
        template = str(template or "").strip()
        if not template:
            return False
        message = LiveChatMessage(
            username="AizenTimer",
            comment=clean_name,
            platform="Timer",
            received_at=datetime.now().strftime("%H:%M:%S"),
            message_id=f"timer-{timer_id or uuid.uuid4().hex}-{time.time()}",
            source="timer",
        )
        response = render_chat_command_response(template, message, f"timer:{clean_name}", "")
        queue_bot_reply(response, message, f"timer:{clean_name}", "", test=test)
        return True

    def queue_chat_timer_row(row: dict[str, Any], test: bool = False) -> bool:
        return queue_chat_timer_payload(
            str(row.get("id") or ""),
            row["name"].get(),
            row["message"].get(),
            test=test,
        )

    def test_chat_timer_row(row: dict[str, Any]) -> None:
        if queue_chat_timer_row(row, test=True):
            timer_status_var.set("Teste na fila")
        else:
            timer_status_var.set("Timer vazio")

    def active_chat_timer_entries() -> list[dict[str, Any]]:
        if chat_timer_rows_loaded:
            entries: list[dict[str, Any]] = []
            for row in chat_timer_rows:
                name = re.sub(r"\s+", " ", row["name"].get().strip())[:80]
                message = row["message"].get().strip()
                if not bool(row["enabled"].get()) or not message:
                    continue
                entries.append(
                    {
                        "id": str(row.get("id") or ""),
                        "name": name or "Timer",
                        "message": message,
                        "interval": timer_row_interval_seconds(row),
                        "min_messages": timer_row_min_messages(row),
                    }
                )
            return entries
        entries = []
        for timer in chat_timer_cache:
            name = re.sub(r"\s+", " ", str(timer.name or "").strip())[:80]
            message = str(timer.message or "").strip()
            if not bool(timer.enabled) or not message:
                continue
            entries.append(
                {
                    "id": chat_timer_cache_id(timer),
                    "name": name or "Timer",
                    "message": message,
                    "interval": max(60, int(timer.interval_seconds or bot_default_timer_interval_seconds())),
                    "min_messages": max(0, int(timer.min_chat_messages or bot_default_timer_min_messages())),
                }
            )
        return entries

    def schedule_chat_timer_pump(delay_ms: int = 0) -> None:
        nonlocal chat_timer_after_id
        if app_closing:
            return
        if chat_timer_after_id is not None:
            try:
                root.after_cancel(chat_timer_after_id)
            except tk.TclError:
                pass
        chat_timer_after_id = root.after(max(0, delay_ms), pump_chat_timers)

    def pump_chat_timers() -> None:
        nonlocal chat_timer_after_id
        chat_timer_after_id = None
        if app_closing:
            return
        now = time.time()
        active_rows = active_chat_timer_entries()
        current_ids = {str(row["id"]) for row in active_rows}
        for timer_id in list(chat_timer_runtime):
            if timer_id not in current_ids:
                chat_timer_runtime.pop(timer_id, None)

        timer_active_count_var.set(str(len(active_rows)))

        if not chat_timers_enabled_var.get():
            timer_status_var.set("Desligado")
            timer_next_send_var.set("-")
            if not app_closing:
                schedule_chat_timer_pump(BACKGROUND_DISABLED_PUMP_MS)
            return

        if not active_rows:
            timer_status_var.set("Sem timers ativos")
            timer_next_send_var.set("-")
            if not app_closing:
                schedule_chat_timer_pump(3000)
            return

        nearest_next_at: float | None = None
        queued = 0
        waiting_for_chat = False
        for row in active_rows:
            timer_id = str(row["id"])
            interval = max(60, normalize_kill_value(row.get("interval")))
            min_messages = max(0, normalize_kill_value(row.get("min_messages")))
            runtime = chat_timer_runtime.setdefault(
                timer_id,
                {
                    "next_at": now + interval,
                    "last_chat_count": len(chat_messages),
                    "interval": interval,
                    "min_messages": min_messages,
                },
            )
            if runtime.get("interval") != interval or runtime.get("min_messages") != min_messages:
                runtime["interval"] = interval
                runtime["min_messages"] = min_messages
                runtime["next_at"] = now + interval
                runtime["last_chat_count"] = len(chat_messages)

            if now >= float(runtime.get("next_at", now + interval)):
                new_messages = len(chat_messages) - int(runtime.get("last_chat_count", len(chat_messages)))
                if new_messages >= min_messages:
                    if queue_chat_timer_payload(
                        timer_id,
                        str(row.get("name") or "Timer"),
                        str(row.get("message") or ""),
                    ):
                        queued += 1
                    runtime["last_chat_count"] = len(chat_messages)
                    runtime["next_at"] = now + interval
                else:
                    waiting_for_chat = True
                    runtime["next_at"] = now + min(30, interval)

            next_at = float(runtime.get("next_at", now + interval))
            nearest_next_at = next_at if nearest_next_at is None else min(nearest_next_at, next_at)

        if queued:
            timer_status_var.set("Mensagem na fila")
        elif waiting_for_chat:
            timer_status_var.set("Aguardando chat")
        else:
            timer_status_var.set("Rodando")

        if nearest_next_at is None:
            timer_next_send_var.set("-")
        else:
            remaining = max(0, int(nearest_next_at - now))
            timer_next_send_var.set(f"{remaining // 60:02d}:{remaining % 60:02d}")
        if not app_closing:
            schedule_chat_timer_pump(1000)

    def queue_bot_reply(text: str, message: LiveChatMessage, command: str, args: str, test: bool = False) -> None:
        response_text = re.sub(r"\s+", " ", text).strip()
        if not response_text:
            return
        payload = {
            "deliveryId": f"bot-{uuid.uuid4().hex}",
            "attempt": 1,
            "message": response_text,
            "username": message.username,
            "user": message.username,
            "nick": message.username,
            "command": command,
            "args": args,
            "sourceMessage": message.comment,
            "platform": message.platform or "Live",
            "fromAizen": True,
            "test": bool(test),
        }
        if enqueue_bot_reply_payload(payload):
            update_bot_queue_count()
            bot_status_var.set("Na fila")
            log(f"Resposta do bot enfileirada: {response_text[:120]}")
            schedule_bot_send_pump(0)
        else:
            update_bot_queue_count()
            bot_status_var.set("Fila cheia")

    def schedule_bot_delivery_confirmation(payload: dict[str, Any]) -> None:
        delivery_id = str(payload.get("deliveryId") or f"bot-{uuid.uuid4().hex}")
        payload["deliveryId"] = delivery_id
        bot_pending_confirmations[delivery_id] = {
            "message": str(payload.get("message") or ""),
            "payload": payload,
            "sent_at": time.time(),
            "attempt": int(payload.get("attempt") or 1),
            "chat_index": int(payload.get("sendChatIndex") or len(chat_messages)),
        }
        root.after(7000, lambda current_id=delivery_id: check_bot_delivery_confirmation(current_id))

    def check_bot_delivery_confirmation(delivery_id: str) -> None:
        nonlocal bot_next_allowed_at
        if app_closing:
            return
        pending = bot_pending_confirmations.get(delivery_id)
        if not pending:
            return
        message_text = str(pending.get("message") or "")
        if bot_reply_seen_in_chat(message_text, int(pending.get("chat_index") or 0)):
            bot_pending_confirmations.pop(delivery_id, None)
            bot_status_var.set("Confirmado na live")
            log(f"Bot confirmado no chat: {message_text[:120]}")
            return
        payload = dict(pending.get("payload") or {})
        attempt = int(pending.get("attempt") or payload.get("attempt") or 1)
        bot_pending_confirmations.pop(delivery_id, None)
        if attempt < 2 and bot_delivery_method_key() == BOT_DELIVERY_TIKFINITY_DIRECT:
            payload["attempt"] = attempt + 1
            payload["retry"] = True
            payload["deliveryId"] = f"bot-{uuid.uuid4().hex}"
            stop_tikfinity_direct_bridge(silent=True)
            bot_next_allowed_at = 0.0
            if enqueue_bot_reply_payload(payload):
                update_bot_queue_count()
                bot_status_var.set("Reenviando")
            else:
                update_bot_queue_count()
                bot_status_var.set("Fila cheia")
                return
            log(
                "TikFinity recebeu o pacote do bot, mas a mensagem nao apareceu no chat em 7s; "
                "reiniciando a ponte direta e reenviando uma vez."
            )
            schedule_bot_send_pump(200)
            return
        bot_status_var.set("Sem confirmação")
        log(
            "TikFinity recebeu o pacote do bot, mas o app nao viu a mensagem voltar no chat. "
            "No TikFinity, desconecte/conecte Setup > Streamer.bot Connection e teste novamente."
        )

    def should_ignore_bot_user(message: LiveChatMessage) -> bool:
        ignored = bot_ignored_usernames()
        return bool(ignored and message.username.strip().casefold() in ignored)

    def handle_custom_chat_commands(message: LiveChatMessage) -> None:
        if not chat_commands_enabled_var.get():
            return
        if message.platform == "Aizen" or should_ignore_bot_user(message):
            return
        token, args = chat_command_token(message.comment)
        if not token:
            return
        now = time.time()
        command = runtime_custom_command(token)
        if command is None:
            bot_status_var.set(f"{token} sem cadastro")
            if now - bot_command_last_missed.get(f"missing:{token}", 0.0) >= 10:
                bot_command_last_missed[f"missing:{token}"] = now
                log(f"Comando do chat recebido, mas nao existe comando ativo para: {token}")
            return
        if not command.enabled:
            bot_status_var.set(f"{token} desativado")
            if now - bot_command_last_missed.get(f"disabled:{token}", 0.0) >= 10:
                bot_command_last_missed[f"disabled:{token}"] = now
                log(f"Comando do chat recebido, mas esta desativado: {token}")
            return
        cooldown = max(0, command.cooldown_seconds)
        last_sent = bot_command_last_sent.get(command.command, 0.0)
        if cooldown and now - last_sent < cooldown:
            remaining = int(cooldown - (now - last_sent))
            bot_status_var.set(f"Cooldown {remaining}s")
            if now - bot_command_last_missed.get(f"cooldown:{token}", 0.0) >= 10:
                bot_command_last_missed[f"cooldown:{token}"] = now
                log(f"Comando {token} recebido, aguardando cooldown ({remaining}s).")
            return
        response = render_chat_command_response(command.response, message, command.command, args)
        bot_command_last_sent[command.command] = now
        bot_status_var.set(f"Comando {token}")
        log(f"Comando do chat reconhecido: {message.username}: {token}")
        queue_bot_reply(response, message, command.command, args)

    def test_custom_command_row(row: dict[str, Any]) -> None:
        command = normalize_chat_command(row["command"].get()) or "!teste"
        message = LiveChatMessage(
            username="AizenTeste",
            comment=f"{command} teste",
            platform="Teste",
            received_at=datetime.now().strftime("%H:%M:%S"),
            message_id=f"command-test-{time.time()}",
            source="local",
        )
        response = render_chat_command_response(row["response"].get(), message, command, "teste")
        queue_bot_reply(response, message, command, "teste", test=True)

    def test_bot_send() -> None:
        message = LiveChatMessage(
            username="AizenTeste",
            comment="!teste",
            platform="Teste",
            received_at=datetime.now().strftime("%H:%M:%S"),
            message_id=f"bot-send-test-{time.time()}",
            source="local",
        )
        queue_bot_reply(
            "Mensagem de teste do Aizen Stream Control via TikFinity direto.",
            message,
            "!teste",
            "",
            test=True,
        )

    def schedule_bot_send_pump(delay_ms: int = 0) -> None:
        nonlocal bot_pump_after_id
        if app_closing:
            return
        if bot_pump_after_id is not None:
            try:
                root.after_cancel(bot_pump_after_id)
            except tk.TclError:
                pass
        bot_pump_after_id = root.after(max(0, delay_ms), pump_bot_send_results)

    def pump_bot_send_results() -> None:
        nonlocal bot_sending, bot_next_allowed_at, bot_pump_after_id
        bot_pump_after_id = None
        if app_closing:
            return
        processed_results = 0
        while processed_results < 20:
            try:
                ok, detail, payload = bot_send_result_queue.get_nowait()
            except queue.Empty:
                break
            processed_results += 1
            bot_sending = False
            bot_next_allowed_at = time.time() + bot_safe_delay_seconds()
            update_bot_queue_count()
            if ok:
                bot_last_sent_var.set(datetime.now().strftime("%H:%M:%S"))
                detail_text = str(detail or "")
                message_preview = str(payload.get("message", ""))[:140]
                if detail_text.startswith("TikFinity recebeu pacote"):
                    bot_status_var.set("Aguardando confirmação")
                    log(f"Bot enviado ao TikFinity; aguardando aparecer no chat: {message_preview}")
                    schedule_bot_delivery_confirmation(payload)
                    root.after(1200, ensure_chat_listener_for_bot)
                    if bool(payload.get("test")):
                        log(detail_text)
                else:
                    bot_status_var.set("Enviado")
                    log(f"Bot respondeu na live: {message_preview}")
                    root.after(1200, ensure_chat_listener_for_bot)
            else:
                bot_status_var.set("Erro")
                log(f"Erro ao enviar resposta do bot: {detail}")
        if not bot_send_result_queue.empty():
            schedule_bot_send_pump(50)
            return

        if bot_sending:
            if not app_closing:
                schedule_bot_send_pump(300)
            return

        if bot_reply_queue.empty():
            update_bot_queue_count()
            if (chat_commands_enabled_var.get() or chat_timers_enabled_var.get()) and bot_status_var.get() in {
                "Desligado",
                "Na fila",
            }:
                if chat_commands_enabled_var.get() and chat_timers_enabled_var.get():
                    bot_status_var.set("Aguardando comando/timer")
                elif chat_timers_enabled_var.get():
                    bot_status_var.set("Aguardando timer")
                else:
                    bot_status_var.set("Aguardando comando")
            return

        remaining = bot_next_allowed_at - time.time()
        if remaining > 0:
            bot_status_var.set(f"Delay seguro {int(remaining) + 1}s")
            update_bot_queue_count()
            if not app_closing:
                schedule_bot_send_pump(500)
            return

        payload = bot_reply_queue.get_nowait()
        payload["sendChatIndex"] = len(chat_messages)
        update_bot_queue_count()
        bot_sending = True
        bot_status_var.set("Enviando")
        try:
            settings = bot_settings_from_vars()
        except Exception as exc:
            enqueue_bot_send_result(False, str(exc), payload)
            if not app_closing:
                schedule_bot_send_pump(250)
            return

        def send() -> None:
            try:
                detail = send_chatbot_message_via_streamerbot(settings, payload)
                enqueue_bot_send_result(True, detail, payload)
            except Exception as exc:
                enqueue_bot_send_result(False, str(exc), payload)

        try:
            bot_executor.submit(send)
        except RuntimeError:
            bot_sending = False
            if not app_closing:
                enqueue_bot_send_result(False, "Nao consegui iniciar envio do bot; app esta encerrando.", payload)
        if not app_closing:
            schedule_bot_send_pump(250)

    def livepix_webhook_port() -> int:
        try:
            value = int(float(livepix_webhook_port_var.get().replace(",", ".")))
        except ValueError:
            value = 8787
        value = max(1024, min(65535, value))
        livepix_webhook_port_var.set(str(value))
        return value

    def livepix_goal_amount_cents() -> int:
        try:
            value = float(livepix_goal_amount_var.get().replace(".", "").replace(",", "."))
        except ValueError:
            value = 500.0
        cents = max(0, int(round(value * 100)))
        return cents

    def livepix_checkout_amount_cents() -> int:
        try:
            value = float(livepix_checkout_amount_var.get().replace(".", "").replace(",", "."))
        except ValueError:
            value = 10.0
        cents = max(100, int(round(value * 100)))
        livepix_checkout_amount_var.set(f"{cents / 100:.2f}".replace(".", ","))
        return cents

    def livepix_endpoint_url(include_token: bool = True) -> str:
        host = livepix_webhook_host_var.get().strip() or "127.0.0.1"
        port = livepix_webhook_port()
        token = livepix_webhook_token_var.get().strip()
        url = f"http://{host}:{port}/api/livepix"
        if include_token and token:
            url = f"{url}?token={token}"
        return url

    def update_livepix_endpoint_text() -> None:
        livepix_endpoint_var.set(f"POST JSON: {livepix_endpoint_url(include_token=True)}")

    def livepix_client() -> LivepixApiClient:
        return LivepixApiClient(
            livepix_client_id_var.get(),
            livepix_client_secret_var.get(),
            livepix_scopes_var.get(),
            log,
        )

    def livepix_error_detail(exc: Exception) -> str:
        error_text = str(exc)
        if isinstance(exc, requests.Timeout):
            return "Tempo esgotado ao conectar na Livepix; verifique internet/firewall e tente de novo"
        if isinstance(exc, requests.ConnectionError):
            if "NameResolutionError" in error_text or "Failed to resolve" in error_text or "getaddrinfo failed" in error_text:
                return "DNS falhou ao resolver oauth.livepix.gg; troque o DNS/reinicie a internet e teste novamente"
            if "Max retries exceeded" in error_text:
                return "Nao consegui conectar na Livepix; verifique internet, firewall, proxy ou bloqueio de DNS"
            return f"Falha de conexao com a Livepix: {error_text[:160]}"
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            response = exc.response
            body = ""
            try:
                payload = response.json()
                body = str(payload.get("message") or payload.get("error_description") or payload.get("error") or "")
            except ValueError:
                body = response.text.strip()
            body = body[:180].strip()
            if response.status_code == 401:
                return "401 credenciais invalidas ou sem permissao"
            if response.status_code == 403:
                return "403 escopos/permissoes insuficientes"
            if response.status_code == 429:
                return "429 limite de requisicoes da Livepix; aguarde um pouco e teste de novo"
            return f"{response.status_code} {body or response.reason}".strip()
        return error_text[:220]

    def livepix_event_identity(event: LivepixEvent) -> tuple[str, str]:
        return (event.kind, event.event_id or event.reference)

    def merge_livepix_events(new_events: list[LivepixEvent], refresh: bool = True, persist: bool = True) -> int:
        existing = {livepix_event_identity(event): event for event in livepix_events}
        added = 0
        updated = False
        for event in new_events:
            key = livepix_event_identity(event)
            current = existing.get(key)
            if current is not None:
                for attr in ("reference", "username", "message", "proof", "created_at", "source"):
                    new_value = str(getattr(event, attr, "") or "").strip()
                    old_value = str(getattr(current, attr, "") or "").strip()
                    if new_value and new_value != old_value:
                        setattr(current, attr, new_value)
                        updated = True
                if event.amount and event.amount != current.amount:
                    current.amount = event.amount
                    updated = True
                if event.currency and event.currency != current.currency:
                    current.currency = event.currency.upper()
                    updated = True
                if event.flagged and not current.flagged:
                    current.flagged = True
                    updated = True
                continue
            livepix_events.append(event)
            existing[key] = event
            added += 1
        livepix_events.sort(key=lambda item: item.created_at or "", reverse=True)
        del livepix_events[LIVEPIX_EVENT_STORAGE_LIMIT:]
        if (added or updated) and persist:
            save_livepix_events(livepix_events_path(config_path), livepix_events)
        if refresh:
            schedule_livepix_dashboard_refresh()
        return added

    def livepix_event_title(event: LivepixEvent) -> str:
        kind_label = {
            "message": "mensagem",
            "payment": "pagamento",
            "subscription": "assinatura",
        }.get(event.kind, "apoio")
        name = event.username.strip() or "Apoiador"
        amount = format_livepix_amount(event.amount, event.currency)
        if event.message:
            return f"{name} enviou {kind_label} de {amount}: {event.message}"
        return f"{name} enviou {kind_label} de {amount}"

    def announce_livepix_event(event: LivepixEvent) -> None:
        if not livepix_announce_in_chat_var.get():
            return
        message = LiveChatMessage(
            username=event.username or "Livepix",
            comment=livepix_event_title(event),
            platform="Livepix",
            message_id=f"livepix-{event.kind}-{event.event_id or event.reference}",
            source="livepix",
            received_at=datetime.now().strftime("%H:%M:%S"),
            supporter_tier="gift" if event.amount >= 5000 else "fan",
        )
        add_live_chat_message(message)
        refresh_chat_messages(force=True)

    def livepix_public_page_path() -> Path:
        raw_path = livepix_public_page_file_var.get().strip() or "livepix_public.html"
        path = Path(raw_path)
        if not path.is_absolute():
            path = ROOT / path
        return path

    def export_livepix_public_page() -> None:
        refresh_livepix_dashboard()
        path = livepix_public_page_path()
        events = livepix_events[:30]
        ranking = livepix_ranking_var.get().splitlines() if livepix_ranking_var.get() != "-" else []
        event_items = "\n".join(
            f"<li><strong>{html.escape(event.username or 'Apoiador')}</strong> "
            f"<span>{html.escape(format_livepix_amount(event.amount, event.currency))}</span>"
            f"<p>{html.escape(event.message or event.reference or event.created_at)}</p></li>"
            for event in events
        )
        ranking_items = "\n".join(f"<li>{html.escape(line)}</li>" for line in ranking)
        page = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(livepix_goal_label_var.get() or 'Livepix')}</title>
  <style>
    body {{ margin: 0; font-family: Segoe UI, Arial, sans-serif; background: #08090d; color: #f8f3f2; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 32px 18px; }}
    h1 {{ margin: 0 0 6px; font-size: 34px; }}
    .muted {{ color: #ad9da0; }}
    .metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin: 22px 0; }}
    .card {{ background: #101116; border: 1px solid #332025; border-radius: 8px; padding: 16px; }}
    .value {{ color: #35d6a5; font-size: 26px; font-weight: 700; }}
    ol, ul {{ padding-left: 22px; }}
    li {{ margin: 10px 0; }}
    li span {{ color: #35d6a5; font-weight: 700; }}
    p {{ margin: 4px 0 0; color: #ad9da0; }}
  </style>
</head>
<body>
  <main>
    <h1>{html.escape(livepix_goal_label_var.get() or 'Meta da live')}</h1>
    <div class="muted">Atualizado em {html.escape(datetime.now().strftime('%d/%m/%Y %H:%M:%S'))}</div>
    <section class="metrics">
      <div class="card"><div class="muted">Total</div><div class="value">{html.escape(livepix_total_var.get())}</div></div>
      <div class="card"><div class="muted">Meta</div><div class="value">{html.escape(livepix_goal_var.get())}</div></div>
      <div class="card"><div class="muted">Eventos</div><div class="value">{html.escape(livepix_count_var.get())}</div></div>
    </section>
    <section class="card">
      <h2>Top apoiadores</h2>
      <ol>{ranking_items or '<li>Nenhum apoio registrado ainda</li>'}</ol>
    </section>
    <section class="card">
      <h2>Últimos apoios</h2>
      <ul>{event_items or '<li>Nenhum evento recebido ainda</li>'}</ul>
    </section>
  </main>
</body>
</html>
"""
        path.write_text(page, encoding="utf-8")
        livepix_status_var.set("Página exportada")
        log(f"Página pública Livepix exportada em {path}")

    def livepix_period_events() -> list[LivepixEvent]:
        return [event for event in livepix_events if event.currency.upper() == livepix_currency_var.get().strip().upper()]

    def livepix_selected_wallet() -> dict[str, Any]:
        wallet = livepix_dashboard_state.get("wallet", [])
        if not isinstance(wallet, list):
            return {}
        selected_currency = livepix_currency_var.get().strip().upper() or "BRL"
        selected = next(
            (
                item
                for item in wallet
                if isinstance(item, dict) and str(item.get("currency", "")).upper() == selected_currency
            ),
            wallet[0] if wallet and isinstance(wallet[0], dict) else {},
        )
        return selected if isinstance(selected, dict) else {}

    def livepix_mapping_amount(mapping: Any, paths: tuple[tuple[str, ...], ...]) -> int:
        if not isinstance(mapping, dict):
            return 0
        return livepix_amount_cents(livepix_first_value(mapping, paths))

    def livepix_metric_display(value: str) -> str:
        clean = str(value or "").strip()
        if livepix_values_visible_var.get() or clean in {"", "-"}:
            return clean or "-"
        return "••••"

    def refresh_livepix_metric_visibility() -> None:
        livepix_account_display_var.set(livepix_metric_display(livepix_account_var.get()))
        livepix_total_display_var.set(livepix_metric_display(livepix_total_var.get()))
        livepix_balance_display_var.set(livepix_metric_display(livepix_balance_var.get()))
        livepix_pending_display_var.set(livepix_metric_display(livepix_pending_var.get()))
        livepix_count_display_var.set(livepix_metric_display(livepix_count_var.get()))

    def toggle_livepix_metric_visibility() -> None:
        livepix_values_visible_var.set(not livepix_values_visible_var.get())
        refresh_livepix_metric_visibility()

    def livepix_payload_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        pages = payload.get("pages")
        if isinstance(pages, list):
            items: list[dict[str, Any]] = []
            for page_payload in pages:
                items.extend(livepix_payload_items(page_payload))
            return items
        packaged_items = payload.get("items")
        if isinstance(packaged_items, list):
            return [item for item in packaged_items if isinstance(item, dict)]
        data = payload.get("data", [])
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in ("items", "results", "records", "transactions", "payments", "messages"):
                value = data.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def livepix_wallet_items(payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        values = []
        data = payload.get("data")
        if isinstance(data, list):
            values = data
        elif isinstance(data, dict):
            for key in ("wallets", "balances", "items", "results", "records", "accounts"):
                nested = data.get(key)
                if isinstance(nested, list):
                    values = nested
                    break
            else:
                values = [data]
        else:
            for key in ("wallets", "balances", "items", "results", "records", "accounts"):
                nested = payload.get(key)
                if isinstance(nested, list):
                    values = nested
                    break
        return [item for item in values if isinstance(item, dict)]

    def livepix_total_amount_from_payload(payload: Any) -> int:
        if isinstance(payload, list):
            return max((livepix_total_amount_from_payload(item) for item in payload), default=0)
        if not isinstance(payload, dict):
            return 0
        pages = payload.get("pages")
        page_total = livepix_total_amount_from_payload(pages) if isinstance(pages, list) else 0
        paths = (
            ("totalReceived",),
            ("receivedTotal",),
            ("totalReceivedAmount",),
            ("amountReceived",),
            ("totalAmount",),
            ("total_amount",),
            ("amountTotal",),
            ("amount_total",),
            ("paidAmountTotal",),
            ("grossAmountTotal",),
            ("netAmountTotal",),
            ("totalPaidAmount",),
            ("totalGrossAmount",),
            ("totalNetAmount",),
            ("stats", "totalReceived"),
            ("stats", "receivedTotal"),
            ("stats", "totalAmount"),
            ("summary", "totalReceived"),
            ("summary", "receivedTotal"),
            ("summary", "totalAmount"),
            ("summary", "amount"),
            ("totals", "received"),
            ("totals", "totalReceived"),
            ("totals", "amount"),
            ("totals", "totalAmount"),
            ("total", "amount"),
            ("total", "value"),
            ("meta", "totalAmount"),
            ("metadata", "totalAmount"),
            ("pagination", "totalAmount"),
            ("data", "totalReceived"),
            ("data", "receivedTotal"),
            ("data", "totalAmount"),
            ("data", "summary", "totalReceived"),
            ("data", "summary", "totalAmount"),
            ("data", "totals", "amount"),
        )
        return max(page_total, *(livepix_mapping_amount(payload, (path,)) for path in paths))

    def livepix_payload_count_hint(payload: Any) -> int:
        if not isinstance(payload, dict):
            return 0
        paths = (
            ("totalCount",),
            ("totalItems",),
            ("itemCount",),
            ("countTotal",),
            ("recordsTotal",),
            ("pagination", "totalCount"),
            ("pagination", "totalItems"),
            ("pagination", "itemCount"),
            ("pagination", "total"),
            ("meta", "totalCount"),
            ("meta", "totalItems"),
            ("meta", "itemCount"),
            ("data", "totalCount"),
            ("data", "totalItems"),
            ("data", "pagination", "totalCount"),
            ("data", "pagination", "totalItems"),
        )
        for path in paths:
            try:
                value = int(livepix_first_value(payload, (path,), 0) or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return 0

    def livepix_next_cursor(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        value = livepix_first_value(
            payload,
            (
                ("nextCursor",),
                ("cursor", "next"),
                ("pagination", "nextCursor"),
                ("pagination", "cursor"),
                ("meta", "nextCursor"),
                ("data", "nextCursor"),
                ("data", "pagination", "nextCursor"),
            ),
            "",
        )
        return _first_text(value)

    def livepix_payload_total_pages(payload: Any) -> int:
        if not isinstance(payload, dict):
            return 0
        paths = (
            ("totalPages",),
            ("pages",),
            ("pageCount",),
            ("pagination", "totalPages"),
            ("pagination", "pages"),
            ("meta", "totalPages"),
            ("meta", "pages"),
            ("data", "totalPages"),
            ("data", "pagination", "totalPages"),
        )
        for path in paths:
            try:
                value = int(livepix_first_value(payload, (path,), 0) or 0)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
        return 0

    def livepix_payload_has_more(payload: Any, item_count: int, limit: int, page: int) -> bool:
        if not isinstance(payload, dict):
            return item_count >= limit
        explicit = livepix_first_value(
            payload,
            (
                ("hasMore",),
                ("hasNext",),
                ("hasNextPage",),
                ("pagination", "hasMore"),
                ("pagination", "hasNext"),
                ("pagination", "hasNextPage"),
                ("meta", "hasMore"),
                ("data", "pagination", "hasMore"),
            ),
        )
        if isinstance(explicit, bool):
            return explicit
        total_pages = livepix_payload_total_pages(payload)
        if total_pages:
            return page < total_pages
        total_count = livepix_payload_count_hint(payload)
        if total_count:
            return item_count < total_count
        return item_count >= limit

    def livepix_collection_item_key(item: Any, fallback: int) -> str:
        if not isinstance(item, dict):
            return f"fallback:{fallback}"
        key = livepix_first_text_from(
            item,
            (
                ("id",),
                ("uuid",),
                ("reference",),
                ("transactionId",),
                ("paymentId",),
                ("messageId",),
                ("resource", "id"),
                ("data", "id"),
            ),
        )
        if key:
            return key
        return f"payload:{hashlib.sha1(json.dumps(item, sort_keys=True, ensure_ascii=False, default=str).encode('utf-8')).hexdigest()}"

    def livepix_wallet_current_total(wallet_item: Any) -> int:
        if not isinstance(wallet_item, dict):
            return 0
        balance = livepix_mapping_amount(wallet_item, (("balance",), ("balanceAvailable",), ("available",)))
        pending = livepix_mapping_amount(wallet_item, (("balancePending",), ("pending",), ("pendingBalance",)))
        held = livepix_mapping_amount(wallet_item, (("balanceHeld",), ("held",), ("heldBalance",)))
        return balance + pending + held

    def livepix_positive_amount_sum(items: Any) -> int:
        if not isinstance(items, list):
            return 0
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            status = livepix_first_text_from(item, (("status",), ("state",), ("type",), ("kind",))).casefold()
            if any(marker in status for marker in ("withdraw", "saque", "debit", "refund", "estorno", "cancel")):
                continue
            total += livepix_mapping_amount(
                item,
                (
                    ("amount",),
                    ("value",),
                    ("total",),
                    ("grossAmount",),
                    ("netAmount",),
                    ("paidAmount",),
                ),
            )
        return total

    def livepix_complete_total(local_total: int, selected_wallet: dict[str, Any] | None = None) -> int:
        selected_currency = livepix_currency_var.get().strip().upper() or "BRL"
        cache_key = (
            id(livepix_dashboard_state),
            str(livepix_dashboard_state.get("synced_at") or ""),
            selected_currency,
            int(local_total),
        )
        cache = getattr(livepix_complete_total, "_cache", None)
        if cache and cache[0] == cache_key:
            return int(cache[1])
        candidates = [local_total]
        account = livepix_dashboard_state.get("account", {})
        extras = livepix_dashboard_state.get("extras", {})
        raw = livepix_dashboard_state.get("raw", {})
        if isinstance(account, dict):
            candidates.append(livepix_total_amount_from_payload(account))
        if selected_wallet is None:
            selected_wallet = livepix_selected_wallet()
        if selected_wallet:
            candidates.append(livepix_total_amount_from_payload(selected_wallet))
            candidates.append(livepix_wallet_current_total(selected_wallet))
        if isinstance(extras, dict):
            candidates.append(livepix_positive_amount_sum(extras.get("transactions")))
            candidates.append(livepix_positive_amount_sum(extras.get("receivables")))
        if isinstance(raw, dict):
            for key in ("account", "payments", "messages", "wallet", "transactions", "receivables"):
                candidates.append(livepix_total_amount_from_payload(raw.get(key)))
        total = max(candidates) if candidates else local_total
        livepix_complete_total._cache = (cache_key, total)  # type: ignore[attr-defined]
        return total

    def refresh_livepix_dashboard() -> None:
        events = livepix_period_events()
        currency = livepix_currency_var.get().strip().upper() or "BRL"
        local_total = 0
        by_user: dict[str, int] = {}
        for event in events:
            if event.kind in {"payment", "message", "subscription"}:
                local_total += event.amount
            name = event.username.strip() or event.reference or "Apoiador"
            by_user[name] = by_user.get(name, 0) + event.amount
        selected_wallet = livepix_selected_wallet()
        total = livepix_complete_total(local_total, selected_wallet=selected_wallet)
        goal = livepix_goal_amount_cents()
        set_text_var(livepix_total_var, format_livepix_amount(total, currency))
        set_text_var(livepix_count_var, len(events))
        set_text_var(livepix_goal_var, f"{min(999, int((total / goal) * 100)) if goal else 0}%")
        if selected_wallet:
            selected_currency = str(selected_wallet.get("currency") or livepix_currency_var.get()).upper()
            balance = livepix_mapping_amount(selected_wallet, (("balance",), ("balanceAvailable",), ("available",)))
            pending = livepix_mapping_amount(selected_wallet, (("balancePending",), ("pending",), ("pendingBalance",)))
            held = livepix_mapping_amount(selected_wallet, (("balanceHeld",), ("held",), ("heldBalance",)))
            set_text_var(livepix_balance_var, format_livepix_amount(balance, selected_currency))
            set_text_var(livepix_pending_var, format_livepix_amount(pending + held, selected_currency))
            set_text_var(
                livepix_wallet_var,
                f"Disponível {format_livepix_amount(balance, selected_currency)} | "
                f"pendente {format_livepix_amount(pending, selected_currency)} | "
                f"retido {format_livepix_amount(held, selected_currency)}",
            )
        else:
            set_text_var(livepix_balance_var, "-")
            set_text_var(livepix_pending_var, "-")
        if by_user:
            top_name, top_amount = max(by_user.items(), key=lambda item: item[1])
            set_text_var(livepix_top_var, f"{top_name} - {format_livepix_amount(top_amount, currency)}")
            ranking_lines = [
                f"{index}. {name} - {format_livepix_amount(amount, currency)}"
                for index, (name, amount) in enumerate(
                    sorted(by_user.items(), key=lambda item: item[1], reverse=True)[:10],
                    start=1,
                )
            ]
            set_text_var(livepix_ranking_var, "\n".join(ranking_lines))
        else:
            set_text_var(livepix_top_var, "-")
            set_text_var(livepix_ranking_var, "-")
        refresh_livepix_metric_visibility()
        render_livepix_events()
        if livepix_overlay_frame is not None:
            overlay_signature = (
                livepix_total_var.get(),
                livepix_goal_var.get(),
                tuple(
                    (
                        event.kind,
                        event.event_id,
                        event.reference,
                        event.username,
                        event.message,
                        event.amount,
                        event.currency,
                    )
                    for event in events[:5]
                ),
            )
            if getattr(refresh_livepix_dashboard, "_overlay_signature", None) != overlay_signature:
                refresh_livepix_dashboard._overlay_signature = overlay_signature  # type: ignore[attr-defined]
                render_livepix_overlay()

    def run_scheduled_livepix_dashboard_refresh() -> None:
        nonlocal livepix_dashboard_after_id
        livepix_dashboard_after_id = None
        if app_closing:
            return
        refresh_livepix_dashboard()

    def schedule_livepix_dashboard_refresh(delay_ms: int = LIVEPIX_DASHBOARD_REFRESH_DELAY_MS) -> None:
        nonlocal livepix_dashboard_after_id
        if app_closing:
            return
        if livepix_dashboard_after_id is not None:
            try:
                root.after_cancel(livepix_dashboard_after_id)
            except tk.TclError:
                pass
        livepix_dashboard_after_id = root.after(max(0, delay_ms), run_scheduled_livepix_dashboard_refresh)

    def replay_livepix_history_event(event: LivepixEvent) -> None:
        announce_livepix_event(event)
        livepix_status_var.set("Evento reexibido")
        if livepix_overlay_frame is not None:
            render_livepix_overlay()

    def toggle_livepix_history_flag(event: LivepixEvent) -> None:
        key = livepix_event_identity(event)
        for item in livepix_events:
            if livepix_event_identity(item) == key:
                item.flagged = not item.flagged
                save_livepix_events(livepix_events_path(config_path), livepix_events)
                livepix_status_var.set("Marcado" if item.flagged else "Desmarcado")
                schedule_livepix_dashboard_refresh()
                return

    def hide_livepix_history_event(event: LivepixEvent) -> None:
        key = livepix_event_identity(event)
        if not messagebox.askyesno("Livepix", "Ocultar este Livepix do histórico local?"):
            return
        livepix_events[:] = [item for item in livepix_events if livepix_event_identity(item) != key]
        save_livepix_events(livepix_events_path(config_path), livepix_events)
        livepix_status_var.set("Evento ocultado")
        refresh_livepix_dashboard()

    def is_commands_tab_active() -> bool:
        try:
            return tabview.get() == "Comandos"
        except (AttributeError, tk.TclError):
            return False

    def is_timers_tab_active() -> bool:
        try:
            return tabview.get() == "Temporizador"
        except (AttributeError, tk.TclError):
            return False

    def is_logs_tab_active() -> bool:
        try:
            return tabview.get() == "Logs"
        except (AttributeError, tk.TclError):
            return False

    def is_livepix_tab_active() -> bool:
        try:
            return tabview.get() == "Livepix"
        except (AttributeError, tk.TclError):
            return False

    def is_appearance_tab_active() -> bool:
        try:
            return tabview.get() == "Aparência"
        except (AttributeError, tk.TclError):
            return False

    def cancel_livepix_event_render() -> None:
        nonlocal livepix_render_after_id, livepix_render_generation
        livepix_render_generation += 1
        if livepix_render_after_id is None:
            return
        try:
            root.after_cancel(livepix_render_after_id)
        except tk.TclError:
            pass
        livepix_render_after_id = None

    def render_livepix_events(force: bool = False) -> None:
        nonlocal livepix_history_render_pending, livepix_render_after_id, livepix_render_generation
        if "livepix_events_frame" not in globals() and not hasattr(render_livepix_events, "frame"):
            return
        frame = getattr(render_livepix_events, "frame", None)
        if frame is None:
            return
        events = livepix_events[:LIVEPIX_HISTORY_RENDER_LIMIT]
        render_signature = [
            (
                livepix_event_identity(event),
                event.username,
                event.message,
                event.amount,
                event.currency,
                event.created_at,
                event.flagged,
            )
            for event in events
        ]
        render_signature.append(("currency", livepix_currency_var.get().strip().upper()))
        if not force and not is_livepix_tab_active():
            if getattr(render_livepix_events, "_deferred_signature", None) != render_signature:
                render_livepix_events._deferred_signature = render_signature  # type: ignore[attr-defined]
                livepix_history_render_pending = True
            return
        if (
            getattr(render_livepix_events, "_signature", None) == render_signature
            and not livepix_history_render_pending
            and livepix_render_after_id is None
        ):
            return
        render_livepix_events._signature = render_signature  # type: ignore[attr-defined]
        render_livepix_events._deferred_signature = []  # type: ignore[attr-defined]
        livepix_history_render_pending = False
        cancel_livepix_event_render()
        for widget in livepix_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        livepix_widgets.clear()
        if not events:
            empty = ctk.CTkLabel(
                frame,
                text="Nenhum Livepix recebido ainda. A sincronização automática vai preencher este histórico quando houver dados.",
                text_color=muted,
                font=("Segoe UI", 13),
                wraplength=680,
            )
            empty.grid(row=0, column=0, sticky="ew", padx=16, pady=20)
            livepix_widgets.append(empty)
            return
        try:
            wraplength = max(420, frame.winfo_width() - 210)
        except tk.TclError:
            wraplength = 680
        render_generation = livepix_render_generation

        def render_chunk(start_index: int = 0, row_index: int = 0, current_date: str = "") -> None:
            nonlocal livepix_render_after_id
            livepix_render_after_id = None
            if app_closing or render_generation != livepix_render_generation:
                return
            end_index = min(len(events), start_index + LIVEPIX_HISTORY_RENDER_CHUNK_SIZE)
            for event in events[start_index:end_index]:
                date_label = format_livepix_date_label(event.created_at)
                if date_label != current_date:
                    current_date = date_label
                    date_widget = ctk.CTkLabel(
                        frame,
                        text=date_label,
                        text_color=muted,
                        font=("Segoe UI Semibold", 15),
                        anchor="w",
                    )
                    date_widget.grid(row=row_index, column=0, sticky="ew", padx=10, pady=(18 if row_index else 6, 6))
                    livepix_widgets.append(date_widget)
                    row_index += 1

                row = ctk.CTkFrame(frame, fg_color="#151515", corner_radius=6, border_width=1, border_color=border)
                row.grid(row=row_index, column=0, sticky="ew", padx=10, pady=5)
                row.columnconfigure(1, weight=1)
                row.columnconfigure(3, weight=0)
                kind_label = {
                    "message": "Mensagem",
                    "payment": "Pagamento",
                    "subscription": "Assinatura",
                }.get(event.kind, event.kind.title() or "Evento")
                ctk.CTkLabel(row, text="↔", text_color=muted, font=("Segoe UI Semibold", 16), width=26).grid(
                    row=0, column=0, sticky="nw", padx=(16, 4), pady=(18, 0)
                )
                title = event.username or event.reference or "Apoiador"
                ctk.CTkLabel(row, text=title, text_color=fg, font=("Segoe UI Semibold", 15), anchor="w").grid(
                    row=0, column=1, sticky="ew", padx=8, pady=(18, 0)
                )
                ctk.CTkLabel(row, text=format_livepix_time_label(event.created_at), text_color=muted, font=("Segoe UI", 12), anchor="w").grid(
                    row=1, column=1, sticky="ew", padx=8, pady=(0, 14)
                )
                ctk.CTkLabel(row, text="▣", text_color=muted, font=("Segoe UI Semibold", 14), width=26).grid(
                    row=2, column=0, sticky="nw", padx=(16, 4), pady=(0, 0)
                )
                detail = event.message or event.reference or kind_label
                ctk.CTkLabel(row, text=detail[:500], text_color=fg, font=("Segoe UI", 13), anchor="w", justify="left", wraplength=wraplength).grid(
                    row=2, column=1, columnspan=3, sticky="ew", padx=8, pady=(0, 24)
                )
                ctk.CTkLabel(
                    row,
                    text=format_livepix_amount(event.amount, event.currency),
                    text_color="#31e06f",
                    font=("Segoe UI Semibold", 20),
                    anchor="w",
                ).grid(row=3, column=0, columnspan=2, sticky="w", padx=(16, 8), pady=(0, 20))
                actions = ctk.CTkFrame(row, fg_color="#151515", corner_radius=0)
                actions.grid(row=3, column=3, sticky="e", padx=(8, 18), pady=(0, 18))
                button(actions, "▶", lambda item=event: replay_livepix_history_event(item), "ghost", width=42).pack(side=tk.LEFT, padx=(0, 8))
                button(actions, "⚑", lambda item=event: toggle_livepix_history_flag(item), "ghost", width=42).pack(side=tk.LEFT, padx=(0, 8))
                button(actions, "⊘", lambda item=event: hide_livepix_history_event(item), "ghost", width=42).pack(side=tk.LEFT)
                if event.flagged:
                    ctk.CTkLabel(row, text="Marcado", text_color=danger, font=("Segoe UI Semibold", 11)).grid(
                        row=1, column=3, sticky="e", padx=(8, 18), pady=(0, 14)
                    )
                livepix_widgets.append(row)
                row_index += 1
            if end_index < len(events):
                livepix_render_after_id = root.after(
                    25,
                    lambda next_index=end_index, next_row=row_index, next_date=current_date: render_chunk(
                        next_index,
                        next_row,
                        next_date,
                    ),
                )

        livepix_render_after_id = root.after(0, render_chunk)

    def handle_livepix_webhook(payload: dict[str, Any]) -> None:
        enqueue_livepix_event("webhook", payload)

    def fetch_livepix_webhook_details(payload: dict[str, Any], client: LivepixApiClient) -> None:
        try:
            data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
            resource = data.get("resource") if isinstance(data.get("resource"), dict) else {}
            resource_id = _first_text(resource.get("id"), data.get("id"))
            resource_type = _first_text(resource.get("type"), data.get("type")).lower()
            event: LivepixEvent | None = None
            if resource_id and resource_type == "payment":
                event = client.payment(resource_id)
            elif resource_id and resource_type == "message":
                event = client.message(resource_id)
            elif resource_id and resource_type == "subscription":
                event = client.subscription(resource_id)
            if event is None:
                event = parse_livepix_event(payload, source="webhook")
            enqueue_livepix_event("webhook_detail", event)
        except Exception as exc:
            fallback = parse_livepix_event(payload, source="webhook")
            enqueue_livepix_event("webhook_detail", fallback)
            enqueue_livepix_event("status", f"Webhook recebido; detalhe API falhou: {livepix_error_detail(exc)}")

    def update_livepix_config_from_vars() -> dict[str, Any]:
        config["livepix_enabled"] = bool(livepix_enabled_var.get())
        config["livepix_client_id"] = livepix_client_id_var.get().strip()
        config["livepix_client_secret"] = livepix_client_secret_var.get().strip()
        config["livepix_scopes"] = livepix_scopes_var.get().strip()
        config["livepix_webhook_host"] = livepix_webhook_host_var.get().strip() or "127.0.0.1"
        config["livepix_webhook_port"] = livepix_webhook_port()
        config["livepix_webhook_token"] = livepix_webhook_token_var.get().strip()
        config["livepix_redirect_url"] = livepix_redirect_url_var.get().strip() or "https://livepix.gg"
        config["livepix_goal_amount"] = livepix_goal_amount_cents()
        config["livepix_goal_label"] = livepix_goal_label_var.get().strip() or "Meta da live"
        config["livepix_currency"] = livepix_currency_var.get().strip().upper() or "BRL"
        config["livepix_checkout_amount"] = livepix_checkout_amount_cents()
        config["livepix_checkout_user"] = livepix_checkout_user_var.get().strip() or "Apoiador"
        config["livepix_checkout_message"] = livepix_checkout_message_var.get().strip() or "Apoio para a live!"
        config["livepix_plan_id"] = livepix_plan_id_var.get().strip()
        config["livepix_plan_slug"] = livepix_plan_slug_var.get().strip() or "vip-live"
        config["livepix_plan_name"] = livepix_plan_name_var.get().strip() or "VIP da live"
        config["livepix_plan_description"] = livepix_plan_description_var.get().strip()
        config["livepix_subscription_recurrence"] = livepix_subscription_recurrence_var.get().strip() or "monthly"
        config["livepix_subscriber_email"] = livepix_subscriber_email_var.get().strip()
        config["livepix_announce_in_chat"] = bool(livepix_announce_in_chat_var.get())
        config["livepix_public_page_file"] = livepix_public_page_file_var.get().strip() or "livepix_public.html"
        return config

    def save_livepix_config_silent() -> dict[str, Any]:
        livepix_config = update_livepix_config_from_vars()
        save_config_snapshot_in_background(livepix_config)
        return livepix_config

    def start_livepix_webhook() -> None:
        nonlocal livepix_webhook_server
        try:
            save_livepix_config_silent()
            stop_livepix_webhook(silent=True)
            server = LocalLivepixWebhookServer(
                livepix_webhook_host_var.get().strip() or "127.0.0.1",
                livepix_webhook_port(),
                livepix_webhook_token_var.get().strip(),
                handle_livepix_webhook,
                log,
            )
            server.start()
            livepix_webhook_server = server
            livepix_status_var.set("Webhook ativo")
            update_livepix_endpoint_text()
            schedule_livepix_queue_pump(0)
        except Exception as exc:
            livepix_status_var.set("Erro")
            messagebox.showerror("Livepix", str(exc))

    def stop_livepix_webhook(silent: bool = False) -> None:
        nonlocal livepix_webhook_server
        if livepix_webhook_server is not None:
            livepix_webhook_server.stop()
            livepix_webhook_server = None
        if not silent:
            livepix_status_var.set("Desligado")
            log("Webhook Livepix parado.")

    def sync_livepix_from_api(show_error_dialog: bool = True, full_sync: bool = True) -> None:
        nonlocal livepix_sync_running, livepix_full_sync_pending
        if livepix_sync_running:
            if full_sync:
                livepix_full_sync_pending = True
            livepix_status_var.set("Sincronizando")
            if show_error_dialog:
                log("Livepix sincronizacao ja esta em andamento; aguarde finalizar.")
            return
        try:
            save_livepix_config_silent()
            client = livepix_client()
            selected_currency = livepix_currency_var.get().strip().upper() or "BRL"
        except Exception as exc:
            detail = str(exc)
            livepix_status_var.set("Configure a API")
            livepix_extra_var.set(detail)
            log(f"Livepix sincronizacao ignorada: {detail}")
            if show_error_dialog:
                messagebox.showerror("Livepix", detail)
            return
        is_full_sync = bool(full_sync)
        if is_full_sync:
            livepix_full_sync_pending = False
        livepix_sync_running = True
        livepix_status_var.set("Sincronizando" if is_full_sync else "Sync leve")

        def run() -> None:
            try:
                sync_errors: list[str] = []
                collection_limit = LIVEPIX_FULL_COLLECTION_LIMIT if is_full_sync else LIVEPIX_LIGHT_COLLECTION_LIMIT
                collection_pages = LIVEPIX_FULL_COLLECTION_MAX_PAGES if is_full_sync else LIVEPIX_LIGHT_COLLECTION_MAX_PAGES

                def try_livepix(label: str, getter: callable, fallback: Any) -> Any:
                    try:
                        return getter()
                    except Exception as exc:
                        sync_errors.append(f"{label}: {livepix_error_detail(exc)}")
                        return fallback

                def fetch_livepix_collection(label: str, path: str, limit: int = 100, max_pages: int = 12) -> tuple[dict[str, Any], list[dict[str, Any]]]:
                    first_payload = try_livepix(label, lambda: client.request("GET", path, params={"limit": limit}), {})
                    if not isinstance(first_payload, dict):
                        return {}, []
                    pages: list[dict[str, Any]] = [first_payload]
                    items = livepix_payload_items(first_payload)
                    seen = {livepix_collection_item_key(item, index) for index, item in enumerate(items)}
                    cursor = livepix_next_cursor(first_payload)
                    page = 1
                    while page < max_pages and livepix_payload_has_more(pages[-1], len(items), limit, page):
                        page += 1
                        params = {"limit": limit}
                        if cursor:
                            params["cursor"] = cursor
                        else:
                            params["page"] = page
                        try:
                            page_payload = client.request("GET", path, params=params)
                        except Exception as exc:
                            sync_errors.append(f"{label}: pagina {page} falhou: {livepix_error_detail(exc)}")
                            break
                        page_items = livepix_payload_items(page_payload)
                        fresh_items: list[dict[str, Any]] = []
                        for index, item in enumerate(page_items, start=len(items)):
                            key = livepix_collection_item_key(item, index)
                            if key in seen:
                                continue
                            seen.add(key)
                            fresh_items.append(item)
                        if not fresh_items and len(page_items) >= limit and not cursor and page == 2:
                            try:
                                page_payload = client.request("GET", path, params={"limit": limit, "offset": len(items)})
                                page_items = livepix_payload_items(page_payload)
                                fresh_items = []
                                for index, item in enumerate(page_items, start=len(items)):
                                    key = livepix_collection_item_key(item, index)
                                    if key in seen:
                                        continue
                                    seen.add(key)
                                    fresh_items.append(item)
                            except Exception:
                                pass
                        if not fresh_items:
                            expected_total = livepix_payload_count_hint(pages[0])
                            expected_pages = livepix_payload_total_pages(pages[0])
                            if expected_total > len(items) or (expected_pages and page <= expected_pages) or cursor:
                                sync_errors.append(
                                    f"{label}: API indicou mais registros, mas a pagina {page} nao trouxe itens novos"
                                )
                            break
                        pages.append(page_payload if isinstance(page_payload, dict) else {})
                        items.extend(fresh_items)
                        cursor = livepix_next_cursor(page_payload)
                        time.sleep(0.15)
                    if page >= max_pages and livepix_payload_has_more(pages[-1], len(items), limit, page):
                        sync_errors.append(f"{label}: limite interno de {max_pages} paginas atingido; total pode estar parcial")
                    return {"pages": pages, "items": items, "count": len(items)}, items

                account_payload = try_livepix("conta", lambda: client.request("GET", "/account"), {})
                account_data = account_payload.get("data", {}) if isinstance(account_payload, dict) else {}
                account = account_data if isinstance(account_data, dict) else {}
                payments_payload, payment_items = fetch_livepix_collection(
                    "pagamentos",
                    "/payments",
                    limit=collection_limit,
                    max_pages=collection_pages,
                )
                payments = [
                    event
                    for item in payment_items
                    if (event := parse_livepix_event(item, "payment", "api"))
                ]
                messages_payload, message_items = fetch_livepix_collection(
                    "mensagens",
                    "/messages",
                    limit=collection_limit,
                    max_pages=collection_pages,
                )
                messages = [
                    event
                    for item in message_items
                    if (event := parse_livepix_event(item, "message", "api"))
                ]
                wallet_payload = try_livepix("carteira", lambda: client.request("GET", "/wallet"), {})
                wallet = livepix_wallet_items(wallet_payload)
                extras: dict[str, Any] = {}
                raw_payloads: dict[str, Any] = {
                    "account": account_payload if isinstance(account_payload, dict) else {},
                    "payments": payments_payload if isinstance(payments_payload, dict) else {},
                    "messages": messages_payload if isinstance(messages_payload, dict) else {},
                    "wallet": wallet_payload if isinstance(wallet_payload, dict) else {},
                }
                extras["sync_mode"] = "full" if is_full_sync else "light"
                transaction_items: list[dict[str, Any]] = []
                receivable_items: list[dict[str, Any]] = []
                if is_full_sync:
                    for name, getter in (
                        ("currencies", client.currencies),
                        ("plans", client.plans),
                        ("subscriptions", client.subscriptions),
                        ("rewards", client.rewards),
                        ("webhooks", client.webhooks),
                    ):
                        try:
                            result = getter()
                            extras[name] = result
                        except Exception as exc:
                            detail = livepix_error_detail(exc)
                            extras[name] = f"erro: {detail}"
                            sync_errors.append(f"{name}: {detail}")
                    transactions_payload, transaction_items = fetch_livepix_collection(
                        "transacoes",
                        f"/wallet/{selected_currency}/transactions",
                        limit=collection_limit,
                        max_pages=collection_pages,
                    )
                    receivables_payload, receivable_items = fetch_livepix_collection(
                        "recebiveis",
                        f"/wallet/{selected_currency}/receivables",
                        limit=collection_limit,
                        max_pages=collection_pages,
                    )
                    raw_payloads["transactions"] = transactions_payload
                    raw_payloads["receivables"] = receivables_payload
                    extras["transactions"] = transaction_items
                    extras["receivables"] = receivable_items
                reward_grants: list[dict[str, Any]] = []
                if is_full_sync and isinstance(extras.get("rewards"), list):
                    for reward in extras["rewards"]:
                        reward_id = str(reward.get("id", "")).strip() if isinstance(reward, dict) else ""
                        if not reward_id:
                            continue
                        try:
                            reward_grants.extend(client.reward_grants(reward_id))
                        except Exception as exc:
                            detail = livepix_error_detail(exc)
                            reward_grants.append({"rewardId": reward_id, "error": detail})
                            sync_errors.append(f"reward_grants: {detail}")
                extras["reward_grants"] = reward_grants
                subscription_events = [
                    event
                    for item in extras.get("subscriptions", [])
                    if isinstance(item, dict) and (event := parse_livepix_event(item, "subscription", "api"))
                ] if isinstance(extras.get("subscriptions"), list) else []
                transaction_events = [
                    event
                    for item in extras.get("transactions", [])
                    if isinstance(item, dict)
                    and (event := parse_livepix_event(item, "payment", "api"))
                    and event.amount > 0
                ] if isinstance(extras.get("transactions"), list) else []
                receivable_events = [
                    event
                    for item in extras.get("receivables", [])
                    if isinstance(item, dict)
                    and (event := parse_livepix_event(item, "payment", "api"))
                    and event.amount > 0
                ] if isinstance(extras.get("receivables"), list) else []
                enqueue_livepix_event(
                    "api_synced",
                    {
                        "account": account,
                        "events": payments + messages + subscription_events + transaction_events + receivable_events,
                        "wallet": wallet,
                        "extras": extras,
                        "raw": raw_payloads,
                        "errors": sync_errors,
                        "full_sync": is_full_sync,
                    },
                )
            except Exception as exc:
                enqueue_livepix_event("api_sync_error", livepix_error_detail(exc))

        start_livepix_worker(run, name="AizenLivepixSync")

    def test_livepix_account() -> None:
        sync_livepix_from_api(show_error_dialog=True, full_sync=True)

    def auto_sync_livepix_on_start() -> None:
        if not livepix_enabled_var.get():
            return
        if not livepix_client_id_var.get().strip() or not livepix_client_secret_var.get().strip():
            livepix_status_var.set("Configure a API")
            return
        startup_full_sync = is_livepix_tab_active() or livepix_overlay_frame is not None
        if startup_full_sync:
            log("Sincronizando Livepix automaticamente ao abrir o app.")
        else:
            log("Sincronizando Livepix automaticamente em modo leve; sync completa fica para a aba Livepix.")
        sync_livepix_from_api(show_error_dialog=False, full_sync=startup_full_sync)

    def maybe_start_livepix_full_sync_when_visible() -> None:
        nonlocal livepix_full_sync_pending
        if not livepix_full_sync_pending or livepix_sync_running:
            return
        if not is_livepix_tab_active():
            return
        if not livepix_enabled_var.get():
            livepix_full_sync_pending = False
            return
        if not livepix_client_id_var.get().strip() or not livepix_client_secret_var.get().strip():
            return
        log("Livepix: completando sincronizacao completa agora que a aba foi aberta.")
        sync_livepix_from_api(show_error_dialog=False, full_sync=True)

    def livepix_startup_work_needed() -> bool:
        if livepix_enabled_var.get():
            return True
        if livepix_webhook_server is not None or livepix_overlay_frame is not None:
            return True
        return is_livepix_tab_active()

    def schedule_livepix_startup_tasks() -> None:
        if app_closing:
            return
        if livepix_startup_work_needed():
            root.after(650, lambda: schedule_livepix_dashboard_refresh(0))
            root.after(LIVEPIX_STARTUP_HISTORY_DELAY_MS, start_livepix_history_load)
        if (
            livepix_enabled_var.get()
            and livepix_client_id_var.get().strip()
            and livepix_client_secret_var.get().strip()
        ):
            root.after(LIVEPIX_STARTUP_SYNC_DELAY_MS, auto_sync_livepix_on_start)

    def create_livepix_checkout(kind: str) -> None:
        try:
            save_livepix_config_silent()
            client = livepix_client()
            amount = livepix_checkout_amount_cents()
            currency = livepix_currency_var.get().strip().upper() or "BRL"
            redirect_url = livepix_redirect_url_var.get().strip() or "https://livepix.gg"
            checkout_user = livepix_checkout_user_var.get().strip() or "Apoiador"
            checkout_message = livepix_checkout_message_var.get().strip() or "Apoio para a live!"
        except Exception as exc:
            messagebox.showerror("Livepix", str(exc))
            return
        livepix_status_var.set("Criando checkout")

        def run() -> None:
            try:
                if kind == "message":
                    data = client.create_message(
                        checkout_user,
                        checkout_message,
                        amount,
                        currency,
                        redirect_url,
                    )
                else:
                    data = client.create_payment(amount, currency, redirect_url)
                enqueue_livepix_event("checkout", data)
            except Exception as exc:
                enqueue_livepix_event("error", livepix_error_detail(exc))

        start_livepix_worker(run, name="AizenLivepixCheckout")

    def create_livepix_plan() -> None:
        try:
            save_livepix_config_silent()
            client = livepix_client()
            amount = livepix_checkout_amount_cents()
            slug = livepix_plan_slug_var.get().strip() or "vip-live"
            name = livepix_plan_name_var.get().strip() or "VIP da live"
            description = livepix_plan_description_var.get().strip()
        except Exception as exc:
            messagebox.showerror("Livepix", str(exc))
            return
        livepix_status_var.set("Criando plano")

        def run() -> None:
            try:
                data = client.create_plan(slug, name, description, amount)
                enqueue_livepix_event("plan_created", data)
            except Exception as exc:
                enqueue_livepix_event("error", livepix_error_detail(exc))

        start_livepix_worker(run, name="AizenLivepixPlan")

    def create_livepix_subscription_checkout() -> None:
        try:
            save_livepix_config_silent()
            client = livepix_client()
            plan_id = livepix_plan_id_var.get().strip()
            if not plan_id:
                raise ValueError("Informe o ID do plano ou crie um plano primeiro.")
            recurrence = livepix_subscription_recurrence_var.get().strip() or "monthly"
            username = livepix_checkout_user_var.get().strip() or "Apoiador"
            email = livepix_subscriber_email_var.get().strip()
            redirect_url = livepix_redirect_url_var.get().strip() or "https://livepix.gg"
        except Exception as exc:
            messagebox.showerror("Livepix", str(exc))
            return
        livepix_status_var.set("Criando assinatura")

        def run() -> None:
            try:
                data = client.create_subscription(plan_id, recurrence, username, email, redirect_url)
                enqueue_livepix_event("checkout", data)
            except Exception as exc:
                enqueue_livepix_event("error", livepix_error_detail(exc))

        start_livepix_worker(run, name="AizenLivepixSubscription")

    def copy_livepix_endpoint() -> None:
        update_livepix_endpoint_text()
        root.clipboard_clear()
        root.clipboard_append(livepix_endpoint_url(include_token=True))
        log("Endpoint Livepix copiado.")

    def register_livepix_webhook() -> None:
        try:
            save_livepix_config_silent()
            client = livepix_client()
            url = livepix_endpoint_url(include_token=True)
        except Exception as exc:
            messagebox.showerror("Livepix", str(exc))
            return
        livepix_status_var.set("Cadastrando webhook")

        def run() -> None:
            try:
                data = client.create_webhook(url)
                enqueue_livepix_event("status", f"Webhook cadastrado {data.get('id', '')}".strip())
            except Exception as exc:
                enqueue_livepix_event("error", livepix_error_detail(exc))

        start_livepix_worker(run, name="AizenLivepixWebhookCreate")

    def copy_livepix_checkout(url: str) -> None:
        root.clipboard_clear()
        root.clipboard_append(url)
        livepix_status_var.set("Checkout copiado")
        log(f"Checkout Livepix copiado: {url}")

    def livepix_control(action: str) -> None:
        try:
            client = livepix_client()
        except Exception as exc:
            messagebox.showerror("Livepix", str(exc))
            return

        def run() -> None:
            try:
                if action == "skip":
                    client.skip_alert()
                elif action == "replay":
                    client.replay_alert()
                elif action == "autoplay_on":
                    client.set_autoplay(True)
                elif action == "autoplay_off":
                    client.set_autoplay(False)
                enqueue_livepix_event("status", "Controle enviado")
            except Exception as exc:
                enqueue_livepix_event("error", str(exc))

        start_livepix_worker(run, name="AizenLivepixControl")

    def clear_livepix_events() -> None:
        nonlocal livepix_events_loaded, livepix_events_loading, livepix_history_load_generation
        livepix_events_loaded = True
        livepix_events_loading = False
        livepix_history_load_generation += 1
        livepix_events.clear()
        save_livepix_events(livepix_events_path(config_path), livepix_events)
        refresh_livepix_dashboard()
        livepix_status_var.set("Histórico limpo")

    def add_livepix_test_event() -> None:
        event = LivepixEvent(
            event_id=f"test-{time.time()}",
            kind="message",
            reference=uuid.uuid4().hex[:8],
            username="AizenTeste",
            message="Mensagem de teste Livepix para conferir dashboard e overlay.",
            amount=livepix_checkout_amount_cents(),
            currency=livepix_currency_var.get().strip().upper() or "BRL",
            created_at=datetime.now().isoformat(timespec="seconds"),
            source="test",
        )
        merge_livepix_events([event])
        announce_livepix_event(event)
        livepix_status_var.set("Teste adicionado")

    def render_livepix_overlay() -> None:
        if livepix_overlay_frame is None:
            return
        for child in livepix_overlay_frame.winfo_children():
            child.destroy()
        events = livepix_events[:5]
        ctk.CTkLabel(livepix_overlay_frame, text=livepix_goal_label_var.get() or "Meta da live", text_color=accent, font=("Segoe UI Semibold", 18), anchor="w").grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 0))
        ctk.CTkLabel(livepix_overlay_frame, text=f"{livepix_total_var.get()}  |  {livepix_goal_var.get()}", text_color=fg, font=("Segoe UI Semibold", 30), anchor="w").grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 10))
        for index, event in enumerate(events, start=2):
            text = f"{event.username or 'Apoiador'} - {format_livepix_amount(event.amount, event.currency)}"
            if event.message:
                text = f"{text}: {event.message[:70]}"
            ctk.CTkLabel(livepix_overlay_frame, text=text, text_color=teal if index == 2 else fg, font=("Segoe UI", 14), anchor="w", wraplength=560).grid(row=index, column=0, sticky="ew", padx=16, pady=3)

    def open_livepix_overlay() -> None:
        nonlocal livepix_overlay_window, livepix_overlay_frame
        if livepix_overlay_window is not None:
            try:
                if livepix_overlay_window.winfo_exists():
                    livepix_overlay_window.lift()
                    render_livepix_overlay()
                    return
            except tk.TclError:
                pass
        window = ctk.CTkToplevel(root)
        livepix_overlay_window = window
        window.title("Livepix Overlay - Aizen Stream Control")
        window.geometry("640x320+120+120")
        window.minsize(420, 220)
        window.overrideredirect(True)
        window.attributes("-topmost", True)
        window.attributes("-alpha", 0.92)
        window.configure(fg_color="#050506")
        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=1)
        shell = ctk.CTkFrame(window, fg_color="#09090d", corner_radius=16, border_width=1, border_color=accent)
        shell.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        shell.columnconfigure(0, weight=1)
        controls = ctk.CTkFrame(shell, fg_color="#101116", corner_radius=12)
        controls.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        controls.columnconfigure(0, weight=1)
        title_label = ctk.CTkLabel(controls, text="Livepix", text_color=fg, font=("Segoe UI Semibold", 13), anchor="w")
        title_label.grid(row=0, column=0, sticky="ew", padx=12, pady=7)
        button(controls, "Teste", add_livepix_test_event, "default", width=70).grid(row=0, column=1, padx=(0, 6), pady=5)
        button(controls, "X", close_livepix_overlay, "danger", width=42).grid(row=0, column=2, padx=(0, 8), pady=5)
        livepix_overlay_frame = ctk.CTkFrame(shell, fg_color="#050609", corner_radius=12)
        livepix_overlay_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        livepix_overlay_frame.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        drag_state = {"x": 0, "y": 0}

        def start_drag(event: Any) -> None:
            drag_state["x"] = event.x_root - window.winfo_x()
            drag_state["y"] = event.y_root - window.winfo_y()

        def drag_window(event: Any) -> None:
            window.geometry(f"+{event.x_root - drag_state['x']}+{event.y_root - drag_state['y']}")

        for drag_widget in (controls, title_label):
            drag_widget.bind("<ButtonPress-1>", start_drag)
            drag_widget.bind("<B1-Motion>", drag_window)
        render_livepix_overlay()

    def close_livepix_overlay() -> None:
        nonlocal livepix_overlay_window, livepix_overlay_frame
        if livepix_overlay_window is not None:
            try:
                livepix_overlay_window.destroy()
            except tk.TclError:
                pass
        livepix_overlay_window = None
        livepix_overlay_frame = None

    def schedule_livepix_queue_pump(delay_ms: int = 0) -> None:
        nonlocal livepix_pump_after_id
        if app_closing:
            return
        if not in_ui_thread():
            return
        if livepix_pump_after_id is not None:
            try:
                root.after_cancel(livepix_pump_after_id)
            except tk.TclError:
                pass
        livepix_pump_after_id = root.after(max(0, delay_ms), pump_livepix_queue)

    def pump_livepix_queue() -> None:
        nonlocal livepix_dashboard_state, livepix_sync_running, livepix_events_loaded, livepix_events_loading
        nonlocal livepix_history_render_pending, livepix_pump_after_id, livepix_workers_active
        nonlocal livepix_full_sync_pending
        livepix_pump_after_id = None
        if app_closing:
            return
        processed = False
        processed_count = 0
        batch_limit = 12
        deadline = time.monotonic() + UI_PUMP_TIME_BUDGET_SECONDS
        while processed_count < batch_limit:
            if processed_count and time.monotonic() >= deadline:
                break
            try:
                kind, payload = livepix_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            processed = True
            if kind == "__worker_done":
                livepix_workers_active = max(0, livepix_workers_active - 1)
                continue
            if kind == "history_loaded":
                livepix_events_loading = False
                if not isinstance(payload, dict) or int(payload.get("generation") or 0) != livepix_history_load_generation:
                    continue
                livepix_events_loaded = True
                loaded_events = payload.get("events")
                if isinstance(loaded_events, list):
                    added = merge_livepix_events(loaded_events, refresh=False, persist=False)
                    if loaded_events or added:
                        log(f"Historico Livepix carregado em segundo plano ({len(loaded_events)} evento(s)).")
                if is_livepix_tab_active() or livepix_overlay_frame is not None:
                    render_livepix_events(force=True)
                    render_livepix_overlay()
                else:
                    livepix_history_render_pending = True
                schedule_livepix_dashboard_refresh()
            elif kind == "history_load_error":
                livepix_events_loading = False
                livepix_events_loaded = True
                log(f"Nao consegui carregar historico Livepix em segundo plano: {payload}")
            elif kind == "webhook":
                event = parse_livepix_event(payload, source="webhook")
                if event is not None:
                    livepix_status_var.set("Webhook recebido")
                    log(f"Livepix webhook: {event.kind} {event.reference}; buscando detalhes.")
                    try:
                        detail_client = livepix_client()
                    except Exception as exc:
                        enqueue_livepix_event("webhook_detail", event)
                        enqueue_livepix_event("status", f"Webhook recebido; detalhe API falhou: {livepix_error_detail(exc)}")
                    else:
                        start_livepix_worker(
                            lambda current_payload=payload, current_client=detail_client: fetch_livepix_webhook_details(
                                current_payload,
                                current_client,
                            ),
                            name="AizenLivepixWebhookDetail",
                        )
                else:
                    livepix_status_var.set("Webhook sem detalhes")
                    log(f"Livepix webhook recebido. Use sincronizar para buscar detalhes: {compact_json_preview(payload)}")
            elif kind == "webhook_detail":
                if isinstance(payload, LivepixEvent):
                    merge_livepix_events([payload])
                    announce_livepix_event(payload)
                    livepix_status_var.set("Webhook detalhado")
            elif kind == "api_synced":
                livepix_sync_running = False
                account = payload.get("account", {}) if isinstance(payload, dict) else {}
                events = payload.get("events", []) if isinstance(payload, dict) else []
                wallet = payload.get("wallet", []) if isinstance(payload, dict) else []
                extras = payload.get("extras", {}) if isinstance(payload, dict) else {}
                raw = payload.get("raw", {}) if isinstance(payload, dict) else {}
                errors = payload.get("errors", []) if isinstance(payload, dict) else []
                full_sync = bool(payload.get("full_sync")) if isinstance(payload, dict) else True
                livepix_full_sync_pending = not full_sync
                livepix_dashboard_state = {
                    "account": account if isinstance(account, dict) else {},
                    "wallet": wallet if isinstance(wallet, list) else [],
                    "extras": extras if isinstance(extras, dict) else {},
                    "raw": raw if isinstance(raw, dict) else {},
                    "synced_at": datetime.now().isoformat(timespec="seconds"),
                }
                display = livepix_first_text_from(
                    account,
                    (
                        ("displayName",),
                        ("username",),
                        ("name",),
                        ("email",),
                        ("account", "displayName"),
                        ("user", "displayName"),
                        ("user", "username"),
                    ),
                ) if isinstance(account, dict) else ""
                display = display or "-"
                livepix_account_var.set(display)
                if isinstance(wallet, list):
                    selected_currency = livepix_currency_var.get().strip().upper() or "BRL"
                    selected_wallet = next(
                        (
                            item
                            for item in wallet
                            if isinstance(item, dict) and str(item.get("currency", "")).upper() == selected_currency
                        ),
                        wallet[0] if wallet and isinstance(wallet[0], dict) else {},
                    )
                    if isinstance(selected_wallet, dict) and selected_wallet:
                        balance = livepix_mapping_amount(selected_wallet, (("balance",), ("balanceAvailable",), ("available",)))
                        pending = livepix_mapping_amount(selected_wallet, (("balancePending",), ("pending",), ("pendingBalance",)))
                        held = livepix_mapping_amount(selected_wallet, (("balanceHeld",), ("held",), ("heldBalance",)))
                        livepix_wallet_var.set(
                            f"{format_livepix_amount(balance, selected_wallet.get('currency', selected_currency))} "
                            f"(pendente {format_livepix_amount(pending, selected_wallet.get('currency', selected_currency))}, "
                            f"retido {format_livepix_amount(held, selected_wallet.get('currency', selected_currency))})"
                        )
                    else:
                        livepix_wallet_var.set("-")
                if isinstance(extras, dict):
                    parts = []
                    labels = {
                        "currencies": "moedas",
                        "plans": "planos",
                        "subscriptions": "assinaturas",
                        "rewards": "recompensas",
                        "reward_grants": "concedidas",
                        "webhooks": "webhooks",
                        "transactions": "transações",
                        "receivables": "recebíveis",
                    }
                    for key, label in labels.items():
                        value = extras.get(key)
                        if isinstance(value, list):
                            parts.append(f"{len(value)} {label}")
                    if isinstance(errors, list) and errors:
                        parts.append(f"avisos: {'; '.join(str(item) for item in errors[:3])}")
                    livepix_extra_var.set(" | ".join(parts) if parts else "-")
                added = merge_livepix_events(events if isinstance(events, list) else [], refresh=False)
                critical_prefixes = ("conta:", "pagamentos:", "mensagens:", "carteira:", "transacoes:", "recebiveis:")
                critical_errors = [
                    str(item)
                    for item in errors
                    if str(item).casefold().startswith(critical_prefixes)
                ] if isinstance(errors, list) else []
                if critical_errors:
                    failed_parts = []
                    for item in critical_errors:
                        part = str(item).split(":", 1)[0].strip()
                        if part and part not in failed_parts:
                            failed_parts.append(part)
                    livepix_status_var.set(f"Parcial: {', '.join(failed_parts[:2])}"[:34] if failed_parts else "Parcial")
                    log(f"Livepix sincronizado parcialmente: {'; '.join(critical_errors[:6])}")
                else:
                    status_prefix = "Sincronizado" if full_sync else "Sync leve"
                    livepix_status_var.set(f"{status_prefix} (+{added})")
                    if isinstance(errors, list) and errors:
                        log(f"Livepix sincronizado com avisos opcionais: {'; '.join(str(item) for item in errors[:6])}")
                schedule_livepix_dashboard_refresh()
                if livepix_full_sync_pending:
                    maybe_start_livepix_full_sync_when_visible()
            elif kind == "checkout":
                url = _first_text(payload.get("redirectUrl"), payload.get("url")) if isinstance(payload, dict) else ""
                if url:
                    copy_livepix_checkout(url)
                    messagebox.showinfo("Livepix checkout", f"Link copiado:\n{url}")
                else:
                    livepix_status_var.set("Checkout criado")
            elif kind == "plan_created":
                plan_id = _first_text(payload.get("id")) if isinstance(payload, dict) else ""
                if plan_id:
                    livepix_plan_id_var.set(plan_id)
                    livepix_status_var.set("Plano criado")
                    save_livepix_config_silent()
                else:
                    livepix_status_var.set("Plano criado")
            elif kind == "status":
                livepix_status_var.set(str(payload))
            elif kind == "api_sync_error":
                livepix_sync_running = False
                detail = str(payload)
                if detail:
                    livepix_status_var.set(detail[:34])
                    livepix_extra_var.set(detail)
                else:
                    livepix_status_var.set("Erro")
                log(f"Livepix erro: {payload}")
            elif kind == "error":
                detail = str(payload)
                if detail:
                    livepix_status_var.set(detail[:34])
                    livepix_extra_var.set(detail)
                else:
                    livepix_status_var.set("Erro")
                log(f"Livepix erro: {payload}")
        if not app_closing:
            if not livepix_queue.empty():
                delay_ms = 25
            elif processed:
                delay_ms = 160
            elif (
                livepix_workers_active
                or livepix_sync_running
                or livepix_webhook_server is not None
                or livepix_overlay_frame is not None
                or is_livepix_tab_active()
            ):
                delay_ms = 800
            elif livepix_enabled_var.get():
                delay_ms = LIVEPIX_INACTIVE_IDLE_PUMP_MS
            else:
                return
            schedule_livepix_queue_pump(delay_ms)

    def appearance_config_from_vars() -> dict[str, str]:
        preset = appearance_preset_var.get().strip() or DEFAULT_THEME_NAME
        base = dict(THEME_PRESETS.get(preset, THEME_PRESETS[DEFAULT_THEME_NAME]))
        base["preset"] = preset if preset in THEME_PRESETS else DEFAULT_THEME_NAME
        base["theme_schema_version"] = THEME_SCHEMA_VERSION
        base["logo_path"] = logo_path_var.get().strip()
        for key in THEME_COLOR_KEYS:
            base[key] = normalize_hex_color(theme_color_vars[key].get(), base[key])
            set_text_var(theme_color_vars[key], base[key])
        return base

    def update_config_from_form() -> dict[str, Any]:
        jarvis_base_url = normalize_endpoint_url(jarvis_base_url_var.get()).rstrip("/")
        endpoint_url = normalize_endpoint_url(sync_url_var.get())
        if jarvis_base_url and not endpoint_url:
            endpoint_url = derive_jarvis_endpoint(jarvis_base_url, "kills")
        set_text_var(sync_url_var, endpoint_url)
        config["kills_realtime_url"] = endpoint_url
        config["jarvis_endpoint_url"] = endpoint_url
        config["jarvis_base_url"] = jarvis_base_url
        set_text_var(jarvis_base_url_var, jarvis_base_url)
        config["kills_realtime_auto_sync"] = False
        config["kills_realtime_poll_seconds"] = poll_interval_seconds()
        config["kills_sync_room"] = sync_room_var.get().strip() or "principal"
        kills_style_url = normalize_endpoint_url(kills_style_url_var.get())
        if not kills_style_url and endpoint_url:
            kills_style_url = derive_kills_style_endpoint(endpoint_url)
        elif jarvis_base_url and not kills_style_url:
            kills_style_url = derive_kills_style_endpoint(jarvis_base_url)
        config["freefire_kills_style_url"] = kills_style_url
        set_text_var(kills_style_url_var, kills_style_url)
        if kills_style_url:
            set_text_var(kills_obs_url_var, derive_kills_obs_url(kills_style_url))
        queue_url = normalize_endpoint_url(ff_queue_url_var.get())
        if jarvis_base_url and not queue_url:
            queue_url = derive_jarvis_endpoint(jarvis_base_url, "queue")
        config["ff_queue_realtime_url"] = queue_url
        set_text_var(ff_queue_url_var, config["ff_queue_realtime_url"])
        overlay_url = normalize_endpoint_url(ff_overlay_url_var.get())
        if jarvis_base_url and not overlay_url:
            overlay_url = derive_jarvis_endpoint(jarvis_base_url, "overlay")
        config["ff_overlay_realtime_url"] = overlay_url
        set_text_var(ff_overlay_url_var, config["ff_overlay_realtime_url"])
        overlay_config_url = normalize_endpoint_url(ff_overlay_config_url_var.get())
        if not overlay_config_url and overlay_url:
            overlay_config_url = derive_ff_overlay_config_endpoint(overlay_url)
        if jarvis_base_url and not overlay_config_url:
            overlay_config_url = derive_ff_overlay_config_endpoint(jarvis_base_url)
        config["ff_overlay_config_url"] = overlay_config_url
        set_text_var(ff_overlay_config_url_var, config["ff_overlay_config_url"])
        config["ff_overlay_profile"] = ff_overlay_site_profile_var.get().strip() or "streamer1"
        config["ff_queue_auto_sync"] = bool(ff_queue_enabled_var.get()) and not ff_queue_site_sync_hidden
        config["ff_overlay_auto_sync"] = bool(ff_overlay_enabled_var.get()) and not ff_overlay_site_sync_hidden
        config["ff_queue_poll_seconds"] = ff_queue_poll_interval_seconds()
        config["ff_queue_room"] = ff_queue_room_var.get().strip() or "principal"
        if not ff_queue_site_sync_hidden:
            config["ff_queue_items"] = ff_queue_payload(collect_ff_queue_entries())
        tikfinity_ff_url = normalize_endpoint_url(tikfinity_ff_url_var.get())
        if jarvis_base_url and not tikfinity_ff_url:
            tikfinity_ff_url = derive_tikfinity_ff_gifts_endpoint(jarvis_base_url)
        elif queue_url and not tikfinity_ff_url:
            tikfinity_ff_url = derive_tikfinity_ff_gifts_endpoint(queue_url)
        config["tikfinity_ff_gifts_url"] = tikfinity_ff_url
        set_text_var(tikfinity_ff_url_var, tikfinity_ff_url)
        config["tikfinity_ff_profile"] = tikfinity_ff_profile_var.get().strip() or "streamer1"
        config["tikfinity_ff_enabled"] = bool(tikfinity_ff_enabled_var.get()) and not ff_queue_site_sync_hidden
        config["tikfinity_ff_coins_per_room"] = max(1, normalize_kill_value(tikfinity_ff_coins_var.get()))
        set_text_var(tikfinity_ff_coins_var, config["tikfinity_ff_coins_per_room"])
        config["tikfinity_ff_token"] = tikfinity_ff_token_var.get().strip()
        config["device_name"] = device_name_var.get().strip() or default_device_name()
        config["jarvis_api_token"] = jarvis_token_var.get().strip()
        config["auto_update_enabled"] = bool(auto_update_var.get())
        config["updates_manifest_url"] = updates_manifest_url_var.get().strip()
        config["message_title"] = title_var.get().strip() or "Kills da partida"
        manual_scope = normalize_kills_scope_value(manual_scope_var.get())
        if manual_scope not in {"daily", "general"}:
            manual_scope = "daily"
        config["kills_manual_scope"] = manual_scope
        set_text_var(manual_scope_var, kills_scope_label(config["kills_manual_scope"]))
        manual_scope_buffers[manual_scope] = clone_player_list(
            read_manual_players_light(fill_missing_names=False, scope=manual_scope)
        )
        clear_manual_reference_cache()
        config["manual_kills"] = player_payload(manual_scope_buffers.get(manual_scope, []))
        config["manual_kills_by_scope"] = {
            "daily": player_payload(manual_scope_buffers.get("daily", [])),
            "general": player_payload(manual_scope_buffers.get("general", [])),
        }
        config["tikfinity_chat_url"] = tikfinity_url_var.get().strip()
        config["chat_event_source"] = chat_source_key()
        config["chat_webhook_host"] = chat_webhook_host_var.get().strip() or "127.0.0.1"
        config["chat_webhook_port"] = chat_webhook_port()
        config["chat_webhook_token"] = chat_webhook_token_var.get().strip()
        try:
            config["chat_websocket_url"] = normalize_tikfinity_websocket_url(chat_websocket_url_var.get())
            set_text_var(chat_websocket_url_var, config["chat_websocket_url"])
        except ValueError:
            if chat_source_key() == "websocket":
                raise
            config["chat_websocket_url"] = DEFAULT_TIKFINITY_WEBSOCKET_URL
            set_text_var(chat_websocket_url_var, DEFAULT_TIKFINITY_WEBSOCKET_URL)
        config["chat_commands_enabled"] = bool(chat_commands_enabled_var.get())
        config["chat_commands"] = chat_command_payload(collect_custom_commands())
        config["chat_timers_enabled"] = bool(chat_timers_enabled_var.get())
        config["chat_timers"] = chat_timer_payload(collect_chat_timers())
        config["bot_safe_delay_seconds"] = bot_safe_delay_seconds()
        config["bot_default_command_cooldown_seconds"] = bot_default_cooldown_seconds()
        config["bot_default_timer_interval_seconds"] = bot_default_timer_interval_seconds()
        config["bot_default_timer_min_messages"] = bot_default_timer_min_messages()
        config["bot_delivery_method"] = bot_delivery_method_key()
        config["bot_streamerbot_ws_url"] = normalize_streamerbot_websocket_url(bot_streamerbot_ws_url_var.get())
        set_text_var(bot_streamerbot_ws_url_var, config["bot_streamerbot_ws_url"])
        config["bot_streamerbot_http_url"] = normalize_streamerbot_http_url(bot_streamerbot_http_url_var.get())
        set_text_var(bot_streamerbot_http_url_var, config["bot_streamerbot_http_url"])
        config["bot_streamerbot_password"] = bot_streamerbot_password_var.get()
        config["bot_streamerbot_action_name"] = bot_streamerbot_action_name_var.get().strip()
        config["bot_streamerbot_action_id"] = bot_streamerbot_action_id_var.get().strip()
        config["bot_ignore_usernames"] = bot_ignore_usernames_var.get().strip()
        config["livepix_enabled"] = bool(livepix_enabled_var.get())
        config["livepix_client_id"] = livepix_client_id_var.get().strip()
        config["livepix_client_secret"] = livepix_client_secret_var.get().strip()
        config["livepix_scopes"] = livepix_scopes_var.get().strip()
        config["livepix_webhook_host"] = livepix_webhook_host_var.get().strip() or "127.0.0.1"
        config["livepix_webhook_port"] = livepix_webhook_port()
        config["livepix_webhook_token"] = livepix_webhook_token_var.get().strip()
        config["livepix_redirect_url"] = livepix_redirect_url_var.get().strip() or "https://livepix.gg"
        config["livepix_goal_amount"] = livepix_goal_amount_cents()
        config["livepix_goal_label"] = livepix_goal_label_var.get().strip() or "Meta da live"
        config["livepix_currency"] = livepix_currency_var.get().strip().upper() or "BRL"
        config["livepix_checkout_amount"] = livepix_checkout_amount_cents()
        config["livepix_checkout_user"] = livepix_checkout_user_var.get().strip() or "Apoiador"
        config["livepix_checkout_message"] = livepix_checkout_message_var.get().strip() or "Apoio para a live!"
        config["livepix_plan_id"] = livepix_plan_id_var.get().strip()
        config["livepix_plan_slug"] = livepix_plan_slug_var.get().strip() or "vip-live"
        config["livepix_plan_name"] = livepix_plan_name_var.get().strip() or "VIP da live"
        config["livepix_plan_description"] = livepix_plan_description_var.get().strip()
        config["livepix_subscription_recurrence"] = livepix_subscription_recurrence_var.get().strip() or "monthly"
        config["livepix_subscriber_email"] = livepix_subscriber_email_var.get().strip()
        config["livepix_announce_in_chat"] = bool(livepix_announce_in_chat_var.get())
        config["livepix_public_page_file"] = livepix_public_page_file_var.get().strip() or "livepix_public.html"
        config["raffle_source_mode"] = raffle_source_key()
        config["raffle_command"] = raffle_command_var.get().strip() or "!sorteio"
        config["raffle_duration_seconds"] = int(float(raffle_minutes_var.get().replace(",", ".")) * 60)
        config["raffle_entries_normal"] = raffle_entries_value(raffle_entries_normal_var, 1)
        config["raffle_entries_fan"] = raffle_entries_value(raffle_entries_fan_var, 2)
        config["raffle_entries_super_fan"] = raffle_entries_value(raffle_entries_super_fan_var, 3)
        config["raffle_entries_gift"] = raffle_entries_value(raffle_entries_gift_var, 5)
        config["raffle_entries_sub"] = raffle_entries_value(raffle_entries_sub_var, 10)
        config["raffle_user_cooldown_seconds"] = raffle_cooldown_seconds()
        config["raffle_include_moderators"] = bool(raffle_include_moderators_var.get())
        set_text_var(raffle_entries_normal_var, config["raffle_entries_normal"])
        set_text_var(raffle_entries_fan_var, config["raffle_entries_fan"])
        set_text_var(raffle_entries_super_fan_var, config["raffle_entries_super_fan"])
        set_text_var(raffle_entries_gift_var, config["raffle_entries_gift"])
        set_text_var(raffle_entries_sub_var, config["raffle_entries_sub"])
        set_text_var(raffle_cooldown_var, config["raffle_user_cooldown_seconds"])
        config["ui_layout"] = {
            "participants_height": layout_value(participants_height_var, 240, 900),
            "events_height": layout_value(events_height_var, 90, 360),
            "winner_width": layout_value(winner_width_var, 260, 520),
            "raffle_font_size": layout_value(raffle_font_size_var, 10, 20),
            "chat_overlay_opacity": layout_value(chat_overlay_opacity_var, 35, 100),
            "chat_overlay_font_size": layout_value(chat_overlay_font_size_var, 10, 24),
            "chat_overlay_width": layout_value(chat_overlay_width_var, 300, 900),
            "chat_overlay_height": layout_value(chat_overlay_height_var, 220, 1000),
            "chat_overlay_compact": bool(chat_overlay_compact_var.get()),
            "chat_overlay_controls": bool(chat_overlay_controls_var.get()),
            "chat_overlay_clickthrough": bool(chat_overlay_clickthrough_var.get()),
            "ff_overlay_opacity": layout_value(ff_overlay_opacity_var, 35, 100),
            "ff_overlay_width": layout_value(ff_overlay_width_var, 420, 1400),
            "ff_overlay_height": layout_value(ff_overlay_height_var, 240, 900),
            "ff_overlay_compact": bool(ff_overlay_compact_var.get()),
            "ff_overlay_show_queue": bool(ff_overlay_show_queue_var.get()),
            "ff_overlay_show_kills": bool(ff_overlay_show_kills_var.get()),
        }
        config["ui_theme"] = appearance_config_from_vars()
        return config

    def ensure_config_autosave_worker() -> None:
        nonlocal config_auto_save_worker_started, config_auto_save_pending
        if config_auto_save_worker_started:
            return
        config_auto_save_worker_started = True

        def run() -> None:
            nonlocal config_auto_save_pending
            while True:
                config_auto_save_event.wait()
                while True:
                    with config_auto_save_lock:
                        pending = config_auto_save_pending
                        config_auto_save_pending = None
                        if pending is None:
                            config_auto_save_event.clear()
                            break
                    generation, path, payload, compact, payload_kind = pending
                    if generation != config_auto_save_write_generation:
                        continue
                    try:
                        if payload_kind == "text":
                            content = str(payload)
                        else:
                            snapshot = payload if isinstance(payload, dict) else {}
                            content = (
                                json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
                                if compact
                                else json.dumps(snapshot, ensure_ascii=False, indent=2)
                            )
                        if generation != config_auto_save_write_generation:
                            continue
                        write_text_if_changed(path, content)
                    except Exception as exc:
                        log(f"Auto-save em segundo plano falhou: {exc}")

        threading.Thread(target=run, name="AizenConfigAutosave", daemon=True).start()

    def queue_config_autosave(path: Path, payload: str | dict[str, Any], compact: bool, payload_kind: str) -> None:
        nonlocal config_auto_save_write_generation, config_auto_save_pending
        ensure_config_autosave_worker()
        config_auto_save_write_generation += 1
        generation = config_auto_save_write_generation
        with config_auto_save_lock:
            config_auto_save_pending = (generation, path, payload, compact, payload_kind)
            config_auto_save_event.set()

    def save_config_text_in_background(path: Path, content: str) -> None:
        queue_config_autosave(path, content, compact=True, payload_kind="text")

    def save_config_dict_in_background(path: Path, config_snapshot: dict[str, Any], compact: bool = True) -> None:
        queue_config_autosave(path, dict(config_snapshot), compact=compact, payload_kind="dict")

    def save_config_snapshot_in_background(config_snapshot: dict[str, Any], compact: bool = True) -> None:
        try:
            save_config_dict_in_background(config_path, config_snapshot, compact=compact)
        except Exception as exc:
            log(f"Auto-save em segundo plano aguardando configuração válida: {exc}")

    def save_current_config_silent(compact: bool = False, background: bool = False) -> bool:
        nonlocal config_auto_save_running, config_auto_save_write_generation
        try:
            config_auto_save_running = True
            current_config = update_config_from_form()
            if background:
                save_config_dict_in_background(config_path, current_config, compact=compact)
            else:
                config_auto_save_write_generation += 1
                if compact:
                    save_config_compact(config_path, current_config)
                else:
                    save_config(config_path, current_config)
            return True
        except Exception as exc:
            log(f"Auto-save aguardando configuração válida: {exc}")
            return False
        finally:
            config_auto_save_running = False

    def run_config_autosave() -> None:
        nonlocal config_auto_save_after_id
        config_auto_save_after_id = None
        if app_closing:
            return
        save_current_config_silent(compact=True, background=True)

    def schedule_config_autosave(delay_ms: int = 1800) -> None:
        nonlocal config_auto_save_after_id
        if app_closing or config_auto_save_running:
            return
        if config_auto_save_after_id is not None:
            try:
                root.after_cancel(config_auto_save_after_id)
            except tk.TclError:
                pass
        config_auto_save_after_id = root.after(delay_ms, run_config_autosave)

    def bind_config_autosave(*variables: Any) -> None:
        for variable in variables:
            variable.trace_add("write", lambda *_args: schedule_config_autosave())

    def save_form() -> None:
        if save_current_config_silent(compact=True, background=True):
            log(f"Configuracao enviada para salvar em segundo plano em {config_path}")
        else:
            messagebox.showerror("Erro", "Nao consegui salvar agora. Verifique se algum campo numerico esta incompleto.")

    def restart_app() -> None:
        save_config(config_path, update_config_from_form())
        if IS_FROZEN:
            command = [sys.executable]
            cwd = APP_DIR
        else:
            command = [sys.executable, str(Path(__file__).resolve()), "--config", str(config_path), "--gui"]
            cwd = ROOT
        creationflags = 0x08000000 if os.name == "nt" else 0
        subprocess.Popen(command, cwd=str(cwd), creationflags=creationflags)
        root.destroy()

    def save_appearance(restart: bool = False) -> None:
        try:
            if restart:
                save_config(config_path, update_config_from_form())
            else:
                if not save_current_config_silent(compact=True, background=True):
                    messagebox.showerror("Erro", "Nao consegui salvar agora. Verifique se algum campo numerico esta incompleto.")
                    return
            log("Aparencia salva.")
            if restart:
                restart_app()
            else:
                messagebox.showinfo("Aparencia", "Tema salvo. Use 'Salvar e reabrir' para aplicar em toda a interface.")
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def apply_theme_preset(*_args: Any) -> None:
        preset = appearance_preset_var.get()
        preset_colors = THEME_PRESETS.get(preset)
        if not preset_colors:
            return
        for key, value in preset_colors.items():
            if key in theme_color_vars:
                theme_color_vars[key].set(value)
        try:
            update_theme_swatches()
        except NameError:
            pass

    def manual_kills_send_config() -> dict[str, Any]:
        jarvis_base_url = normalize_endpoint_url(jarvis_base_url_var.get()).rstrip("/")
        endpoint_url = normalize_endpoint_url(sync_url_var.get())
        if jarvis_base_url and not endpoint_url:
            endpoint_url = derive_jarvis_endpoint(jarvis_base_url, "kills")
            sync_url_var.set(endpoint_url)
        if jarvis_base_url != str(config.get("jarvis_base_url", "") or ""):
            jarvis_base_url_var.set(jarvis_base_url)
        device_id = str(config.get("device_id") or "").strip()
        if not device_id:
            device_id = uuid.uuid4().hex
            config["device_id"] = device_id
        return {
            "kills_realtime_url": endpoint_url,
            "jarvis_endpoint_url": endpoint_url,
            "jarvis_base_url": jarvis_base_url,
            "kills_manual_scope": normalize_kills_scope_value(manual_scope_var.get()),
            "device_id": device_id,
            "device_name": device_name_var.get().strip() or default_device_name(),
            "kills_sync_room": sync_room_var.get().strip() or "principal",
            "jarvis_api_token": jarvis_token_var.get().strip(),
        }

    def send_manual_kills(force: bool = True) -> None:
        nonlocal manual_bulk_updating, manual_sending, manual_sync_after_id, manual_last_signature
        manual_sync_after_id = None
        if kills_ff_site_sync_hidden:
            if force:
                log("Sincronizacao Kills FF desativada porque a aba esta oculta.")
            return
        if not force:
            return
        cancel_manual_visual_refresh()
        try:
            local_config = manual_kills_send_config()
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return

        endpoint_url = str(
            local_config.get("kills_realtime_url")
            or local_config.get("jarvis_endpoint_url")
            or ""
        ).strip()
        if not endpoint_url and str(local_config.get("jarvis_base_url") or "").strip():
            endpoint_url = derive_jarvis_endpoint(str(local_config.get("jarvis_base_url") or ""), "kills")
            local_config["kills_realtime_url"] = endpoint_url
            sync_url_var.set(endpoint_url)
        active_scope = normalize_kills_scope_value(local_config.get("kills_manual_scope", "daily"))
        if active_scope not in {"daily", "general"}:
            active_scope = "daily"
        fill_visible_manual_missing_names_from_rank(active_scope)
        capture_visible_manual_scope_for_send(active_scope, render_pending_table=False)
        if active_scope == current_manual_scope():
            unresolved_rows = [
                index
                for index, row in enumerate(manual_rows, start=1)
                if not row["name_var"].get().strip() and normalize_kill_value(row["kills_var"].get()) > 0
            ]
            if unresolved_rows:
                manual_status_var.set("Nick pendente")
                log(
                    "Nao enviei Kills FF: existem linhas com kills sem nick "
                    f"({', '.join(str(index) for index in unresolved_rows[:6])})."
                )
                messagebox.showinfo("Kills FF", "Preencha o nick dos jogadores que possuem kills antes de salvar.")
                return
        daily_references = (
            manual_name_reference_players("daily")
            if manual_players_need_name_completion(manual_scope_buffers.get("daily", []))
            else None
        )
        general_references = (
            manual_name_reference_players("general")
            if manual_players_need_name_completion(manual_scope_buffers.get("general", []))
            else None
        )
        daily_players = manual_scope_buffer_snapshot("daily", references=daily_references)
        general_players = manual_scope_buffer_snapshot("general", references=general_references)
        if not daily_players and active_scope != "daily" and kills_daily_ranking:
            daily_players = clone_player_list(kills_daily_ranking)
            manual_scope_buffers["daily"] = clone_player_list(daily_players)
        if not general_players and active_scope != "general" and kills_global_ranking:
            general_players = clone_player_list(kills_global_ranking)
            manual_scope_buffers["general"] = clone_player_list(general_players)
        apply_local_rank_players("daily", daily_players, schedule_refresh=False)
        apply_local_rank_players("general", general_players, schedule_refresh=False)
        config["kills_realtime_url"] = endpoint_url
        config["jarvis_endpoint_url"] = endpoint_url
        config["jarvis_base_url"] = str(local_config.get("jarvis_base_url") or "")
        config["kills_manual_scope"] = active_scope
        config["manual_kills"] = player_payload(manual_scope_buffers.get(active_scope, []))
        config["manual_kills_by_scope"] = {
            "daily": player_payload(daily_players),
            "general": player_payload(general_players),
        }
        config["device_name"] = str(local_config.get("device_name") or default_device_name())
        config["jarvis_api_token"] = str(local_config.get("jarvis_api_token") or "")
        config["kills_sync_room"] = str(local_config.get("kills_sync_room") or "principal")
        schedule_kills_visual_refresh(delay_ms=240)
        scope_players = daily_players if active_scope == "daily" else general_players
        signature = manual_signature(scope_players, active_scope)
        scopes_to_save = manual_kills_scopes_to_save(active_scope, manual_scope_dirty, daily_players, general_players)
        if not endpoint_url:
            manual_status_var.set("Sem endpoint")
            if force:
                log("Informe a URL do painel/Jarvis para sincronizar as kills.")
            return
        if not scope_players:
            manual_status_var.set("Sem jogadores")
            if force:
                log("Adicione pelo menos um jogador antes de enviar as kills.")
            return
        cancel_manual_config_autosave()
        save_config_snapshot_in_background(config)
        if not force and signature == manual_last_signature:
            manual_status_var.set("Sincronizado")
            return
        if manual_sending:
            return

        manual_sending = True
        manual_status_var.set("Enviando")

        def run() -> None:
            try:
                snapshot_daily_players = clone_player_list(daily_players)
                snapshot_general_players = clone_player_list(general_players)
                players_by_scope: dict[str, list[PlayerKill]] = {
                    "daily": snapshot_daily_players,
                    "general": snapshot_general_players,
                }
                final_state: RealtimeState | None = None

                def update_saved_scope_players(state: RealtimeState) -> None:
                    for scope_key in ("daily", "general"):
                        saved_scope_players = kills_scope_players_from_state(state, scope_key)
                        if saved_scope_players:
                            players_by_scope[scope_key] = clone_player_list(saved_scope_players)

                def preserve_unsaved_empty_scopes() -> bool:
                    missing_scopes = [
                        scope_key
                        for scope_key in ("daily", "general")
                        if scope_key not in scopes_to_save and not players_by_scope.get(scope_key)
                    ]
                    if not missing_scopes:
                        return True
                    try:
                        remote_state = fetch_kills_rank_realtime(
                            endpoint_url,
                            device_id=str(local_config.get("device_id", "")),
                            device_name=str(local_config.get("device_name", "")),
                            room=str(local_config.get("kills_sync_room", "principal")),
                            token=str(local_config.get("jarvis_api_token", "")),
                            timeout=KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
                        )
                        if not (remote_state.daily_ranking or remote_state.global_ranking or remote_state.players):
                            remote_state = fetch_kills_realtime(
                                endpoint_url,
                                device_id=str(local_config.get("device_id", "")),
                                device_name=str(local_config.get("device_name", "")),
                                room=str(local_config.get("kills_sync_room", "principal")),
                                token=str(local_config.get("jarvis_api_token", "")),
                                timeout=KILLS_CONFIRM_GET_TIMEOUT_SECONDS,
                            )
                    except Exception:
                        return False
                    for scope_key in missing_scopes:
                        remote_players = kills_scope_players_from_state(remote_state, scope_key)
                        if remote_players:
                            players_by_scope[scope_key] = clone_player_list(remote_players)
                    return True

                snapshot_ready = manual_kills_should_send_snapshot(scopes_to_save)
                if snapshot_ready:
                    try:
                        final_state = send_kills_snapshot_update(
                            endpoint_url,
                            players_by_scope["daily"],
                            players_by_scope["general"],
                            device_id=str(local_config.get("device_id", "")),
                            device_name=str(local_config.get("device_name", "")),
                            room=str(local_config.get("kills_sync_room", "principal")),
                            token=str(local_config.get("jarvis_api_token", "")),
                        )
                        update_saved_scope_players(final_state)
                    except Exception:
                        if manual_kills_should_send_snapshot(scopes_to_save):
                            raise
                        final_state = None

                if final_state is None:
                    for index, scope_to_save in enumerate(scopes_to_save):
                        other_scope = "general" if scope_to_save == "daily" else "daily"
                        remaining_scopes = set(scopes_to_save[index + 1 :])
                        preserve_players: list[PlayerKill] | None = None
                        if other_scope in remaining_scopes or players_by_scope.get(other_scope):
                            preserve_players = clone_player_list(players_by_scope.get(other_scope, []))
                        final_state = send_kills_scope_replace_update(
                            endpoint_url,
                            scope_to_save,
                            players_by_scope[scope_to_save],
                            preserve_players=preserve_players,
                            device_id=str(local_config.get("device_id", "")),
                            device_name=str(local_config.get("device_name", "")),
                            room=str(local_config.get("kills_sync_room", "principal")),
                            token=str(local_config.get("jarvis_api_token", "")),
                        )
                        saved_scope_players = kills_scope_players_from_state(final_state, scope_to_save)
                        if saved_scope_players:
                            players_by_scope[scope_to_save] = clone_player_list(saved_scope_players)
                        other_scope_players = kills_scope_players_from_state(final_state, other_scope)
                        if other_scope not in remaining_scopes and other_scope_players:
                            players_by_scope[other_scope] = clone_player_list(other_scope_players)
                if final_state is None:
                    final_state = local_kills_snapshot_state(
                        players_by_scope["daily"],
                        players_by_scope["general"],
                        updated_by=str(local_config.get("device_name", "")),
                    )
                final_daily_players = kills_scope_players_from_state(final_state, "daily")
                final_general_players = kills_scope_players_from_state(final_state, "general")
                if not final_daily_players and players_by_scope["daily"]:
                    final_daily_players = players_by_scope["daily"]
                if not final_general_players and players_by_scope["general"]:
                    final_general_players = players_by_scope["general"]
                enqueue_sync_event(
                    "manual_rank_sent",
                    {
                        "count": len(scope_players),
                        "signature": manual_snapshot_signature(final_daily_players, final_general_players),
                        "scope": active_scope,
                        "scopes": list(scopes_to_save),
                        "daily_count": len(final_daily_players),
                        "general_count": len(final_general_players),
                        "daily_kills": sum(player.kills for player in final_daily_players),
                        "general_kills": sum(player.kills for player in final_general_players),
                        "state": final_state,
                    },
                )
            except Exception as exc:
                enqueue_sync_event("send_error", str(exc))

        start_sync_worker(run, name="AizenManualKillsSend")

    def fetch_panel_kills(force: bool = True) -> None:
        nonlocal manual_fetching
        if kills_ff_site_sync_hidden:
            if force:
                log("Leitura Kills FF desativada porque a aba esta oculta.")
            return
        if not force:
            return
        try:
            local_config = manual_kills_send_config()
            if force:
                schedule_manual_config_autosave(900)
        except Exception as exc:
            local_config = dict(config)
            endpoint_url = str(local_config.get("kills_realtime_url") or local_config.get("jarvis_endpoint_url") or "").strip()
            if not endpoint_url and str(local_config.get("jarvis_base_url") or "").strip():
                endpoint_url = derive_jarvis_endpoint(str(local_config.get("jarvis_base_url") or ""), "kills")
                local_config["kills_realtime_url"] = endpoint_url
            if force:
                messagebox.showerror("Erro", str(exc))
            elif not endpoint_url:
                log(f"Nao consegui preparar a configuracao de Kills FF: {exc}")
                return

        endpoint_url = local_config.get("kills_realtime_url", "").strip()
        if not endpoint_url:
            if force:
                set_text_var(manual_status_var, "Sem endpoint")
                set_text_var(kills_overlay_status_var, "Configure a URL do Jarvis")
                log("Informe a URL do painel/Jarvis para buscar as kills.")
            return
        if manual_fetching:
            return

        manual_fetching = True
        if force:
            set_text_var(manual_status_var, "Lendo painel")
            set_text_var(kills_overlay_status_var, "Lendo ranking do Jarvis")

        def run() -> None:
            try:
                state = fetch_kills_realtime(
                    endpoint_url,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("kills_sync_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_sync_event("fetched", {"state": state, "force": force})
            except Exception as exc:
                enqueue_sync_event("fetch_error", {"error": str(exc), "force": force})

        start_sync_worker(run, name="AizenManualKillsFetch")

    def send_ff_queue(force: bool = True) -> None:
        nonlocal ff_queue_sending, ff_queue_sync_after_id, ff_queue_last_signature
        ff_queue_sync_after_id = None
        if ff_queue_site_sync_hidden:
            if force:
                log("Sincronizacao Fila FF desativada porque a aba esta oculta.")
            return
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))
            return

        endpoint_url = local_config.get("ff_queue_realtime_url", "").strip()
        entries = collect_ff_queue_entries()
        signature = ff_queue_signature(entries)
        if not endpoint_url:
            ff_queue_status_var.set("Sem endpoint")
            if force:
                log("Informe a URL da fila/Jarvis para sincronizar a Fila FF.")
            return
        if not force and signature == ff_queue_last_signature:
            ff_queue_status_var.set("Sincronizado")
            return
        if ff_queue_sending:
            return

        ff_queue_sending = True
        ff_queue_status_var.set("Enviando")

        def run() -> None:
            try:
                response_text = send_ff_queue_realtime_update(
                    endpoint_url,
                    entries,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("ff_queue_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_ff_queue_event("sent", {"count": len(entries), "signature": signature, "response": response_text})
            except Exception as exc:
                enqueue_ff_queue_event("send_error", str(exc))

        start_ff_queue_worker(run, name="AizenFFQueueSend")

    def fetch_ff_queue(force: bool = True) -> None:
        nonlocal ff_queue_fetching
        if ff_queue_site_sync_hidden:
            if force:
                log("Leitura Fila FF desativada porque a aba esta oculta.")
            return
        try:
            local_config = update_config_from_form()
            if force:
                save_config_snapshot_in_background(local_config)
        except Exception as exc:
            if force:
                messagebox.showerror("Erro", str(exc))
            return

        endpoint_url = local_config.get("ff_queue_realtime_url", "").strip()
        if not endpoint_url:
            if force:
                set_text_var(ff_queue_status_var, "Sem endpoint")
                log("Informe a URL da fila/Jarvis para buscar a Fila FF.")
            return
        if ff_queue_fetching:
            return

        ff_queue_fetching = True
        if force:
            set_text_var(ff_queue_status_var, "Lendo Jarvis")

        def run() -> None:
            try:
                state = fetch_ff_queue_realtime(
                    endpoint_url,
                    device_id=str(local_config.get("device_id", "")),
                    device_name=str(local_config.get("device_name", "")),
                    room=str(local_config.get("ff_queue_room", "principal")),
                    token=str(local_config.get("jarvis_api_token", "")),
                )
                enqueue_ff_queue_event("fetched", {"state": state, "force": force})
            except Exception as exc:
                enqueue_ff_queue_event("fetch_error", {"error": str(exc), "force": force})

        start_ff_queue_worker(run, name="AizenFFQueueFetch")

    def schedule_ff_queue_poll(delay_ms: int | None = None) -> None:
        nonlocal ff_queue_poll_after_id
        if app_closing or ff_queue_site_sync_hidden:
            if ff_queue_poll_after_id is not None:
                try:
                    root.after_cancel(ff_queue_poll_after_id)
                except tk.TclError:
                    pass
                ff_queue_poll_after_id = None
            return
        if not ff_queue_enabled_var.get():
            if ff_queue_poll_after_id is not None:
                try:
                    root.after_cancel(ff_queue_poll_after_id)
                except tk.TclError:
                    pass
                ff_queue_poll_after_id = None
            return
        if ff_queue_poll_after_id is not None:
            try:
                root.after_cancel(ff_queue_poll_after_id)
            except tk.TclError:
                pass
        if delay_ms is None:
            delay_ms = adaptive_poll_seconds(ff_queue_poll_interval_seconds(), ff_queue_poll_quiet_cycles) * 1000
        ff_queue_poll_after_id = root.after(delay_ms, run_ff_queue_poll)

    def run_ff_queue_poll() -> None:
        nonlocal ff_queue_poll_after_id
        if app_closing:
            return
        ff_queue_poll_after_id = None
        if ff_queue_enabled_var.get() and not ff_queue_site_sync_hidden:
            fetch_ff_queue(force=False)
        if not ff_queue_site_sync_hidden:
            schedule_ff_queue_poll()

    def schedule_ff_overlay_poll(delay_ms: int | None = None) -> None:
        nonlocal ff_overlay_poll_after_id
        if app_closing or ff_overlay_site_sync_hidden:
            if ff_overlay_poll_after_id is not None:
                try:
                    root.after_cancel(ff_overlay_poll_after_id)
                except tk.TclError:
                    pass
                ff_overlay_poll_after_id = None
            return
        if not ff_overlay_enabled_var.get():
            if ff_overlay_poll_after_id is not None:
                try:
                    root.after_cancel(ff_overlay_poll_after_id)
                except tk.TclError:
                    pass
                ff_overlay_poll_after_id = None
            return
        if ff_overlay_poll_after_id is not None:
            try:
                root.after_cancel(ff_overlay_poll_after_id)
            except tk.TclError:
                pass
        if delay_ms is None:
            delay_ms = adaptive_poll_seconds(ff_queue_poll_interval_seconds(), ff_overlay_poll_quiet_cycles, max_seconds=120) * 1000
        ff_overlay_poll_after_id = root.after(delay_ms, run_ff_overlay_poll)

    def run_ff_overlay_poll() -> None:
        nonlocal ff_overlay_poll_after_id
        if app_closing or ff_overlay_site_sync_hidden:
            return
        ff_overlay_poll_after_id = None
        if ff_overlay_enabled_var.get() and not ff_overlay_site_sync_hidden:
            fetch_ff_overlay(force=False)
        if not ff_overlay_site_sync_hidden:
            schedule_ff_overlay_poll()

    def handle_sync_event(kind: str, payload: Any) -> None:
        nonlocal manual_sending, manual_fetching, manual_last_signature, manual_last_remote_signature
        nonlocal manual_last_rank_signature, manual_poll_quiet_cycles
        nonlocal ff_overlay_sending, ff_overlay_fetching, ff_overlay_last_signature, ff_overlay_last_remote_signature
        nonlocal ff_overlay_poll_quiet_cycles
        nonlocal ff_overlay_applying_remote
        nonlocal manual_last_fetch_error, manual_remote_count_override, manual_remote_total_override
        nonlocal manual_dns_retry_after_id
        if kind == "sent":
            manual_sending = False
            manual_last_signature = payload["signature"]
            manual_poll_quiet_cycles = 0
            set_text_var(manual_status_var, "Sincronizado")
            set_text_var(manual_source_var, device_name_var.get().strip() or default_device_name())
            response_text = str(payload.get("response", "")).strip()
            if response_text:
                log(f"Kills enviadas para o painel ({payload['count']} jogador(es)). Resposta: {response_text[:200]}")
            else:
                log(f"Kills enviadas para o painel ({payload['count']} jogador(es)).")
            return

        if kind == "manual_rank_sent":
            manual_sending = False
            manual_last_signature = payload["signature"]
            manual_poll_quiet_cycles = 0
            sent_scopes = payload.get("scopes")
            if isinstance(sent_scopes, list):
                for sent_scope in sent_scopes:
                    clean_sent_scope = normalize_kills_scope_value(sent_scope)
                    if clean_sent_scope in {"daily", "general"}:
                        manual_scope_dirty.discard(clean_sent_scope)
            else:
                sent_scope = normalize_kills_scope_value(payload.get("scope"))
                if sent_scope in {"daily", "general"}:
                    manual_scope_dirty.discard(sent_scope)
            state = payload.get("state")
            if isinstance(state, RealtimeState):
                apply_kills_rankings(state)
                manual_last_rank_signature = kills_rank_signature_for_state(state)
                manual_remote_count_override = state.total_players
                manual_remote_total_override = state.total_kills
                save_kills_rank_cache()
                if state.updated_by:
                    set_text_var(manual_source_var, state.updated_by)
                else:
                    set_text_var(manual_source_var, device_name_var.get().strip() or default_device_name())
            else:
                set_text_var(manual_source_var, device_name_var.get().strip() or default_device_name())
            update_manual_metrics()
            set_text_var(manual_status_var, "Sincronizado")
            sent_scope = normalize_kills_scope_value(payload.get("scope"))
            logged_scopes: list[str] = []
            if isinstance(sent_scopes, list):
                for raw_scope in sent_scopes:
                    clean_sent_scope = normalize_kills_scope_value(raw_scope)
                    if clean_sent_scope in {"daily", "general"} and clean_sent_scope not in logged_scopes:
                        logged_scopes.append(clean_sent_scope)
            elif sent_scope in {"daily", "general"}:
                logged_scopes.append(sent_scope)
            if logged_scopes:
                summary_parts = []
                for clean_sent_scope in logged_scopes:
                    label = kills_scope_label(clean_sent_scope)
                    count_key = "daily_count" if clean_sent_scope == "daily" else "general_count"
                    kills_key = "daily_kills" if clean_sent_scope == "daily" else "general_kills"
                    summary_parts.append(
                        f"{label}: {payload.get(count_key, 0)} jogador(es), {payload.get(kills_key, 0)} kills"
                    )
                log(f"Kills FF salvas no Jarvis ({' / '.join(summary_parts)}).")
            else:
                log(
                    "Kills FF salvas no Jarvis exatamente como no app "
                    f"({payload.get('daily_count', 0)} diario, {payload.get('daily_kills', 0)} kills / "
                    f"{payload.get('general_count', 0)} geral, {payload.get('general_kills', 0)} kills)."
                )
            return

        if kind == "send_error":
            manual_sending = False
            manual_status_var.set("Erro no envio")
            log(f"Erro ao enviar kills para o painel: {payload}")
            return

        if kind == "kills_action_done":
            state: RealtimeState = payload["state"]
            apply_kills_rankings(state)
            manual_last_rank_signature = kills_rank_signature_for_state(state)
            manual_poll_quiet_cycles = 0
            manual_remote_count_override = state.total_players
            manual_remote_total_override = state.total_kills
            update_manual_metrics()
            if state.updated_by:
                set_text_var(manual_source_var, state.updated_by)
            set_text_var(manual_status_var, "Ranking atualizado")
            label = str(payload.get("label") or payload.get("action") or "acao")
            log(f"Ranking Kills FF atualizado pelo Jarvis: {label}.")
            return

        if kind == "kills_action_error":
            error = str(payload.get("error") or payload)
            label = str(payload.get("label") or payload.get("action") or "acao")
            manual_status_var.set("Erro na acao")
            log(f"Nao consegui aplicar acao de Kills FF ({label}): {error}")
            return

        if kind == "kills_style_loaded":
            style = payload.get("style") if isinstance(payload, dict) else payload
            if isinstance(style, dict):
                apply_kills_style(style)
            kills_style_status_var.set("Estilo carregado")
            log("Estilo OBS Kills FF carregado do Jarvis.")
            return

        if kind == "kills_style_saved":
            style = payload.get("style") if isinstance(payload, dict) else payload
            if isinstance(style, dict):
                apply_kills_style(style)
            kills_style_status_var.set("Estilo salvo")
            log("Estilo OBS Kills FF salvo no Jarvis.")
            return

        if kind == "kills_style_error":
            label = str(payload.get("label") or "estilo") if isinstance(payload, dict) else "estilo"
            error = str(payload.get("error") or payload) if isinstance(payload, dict) else str(payload)
            kills_style_status_var.set("Erro")
            log(f"Nao consegui sincronizar estilo OBS Kills FF ({label}): {error}")
            return

        if kind == "fetched":
            manual_fetching = False
            if manual_dns_retry_after_id is not None:
                try:
                    root.after_cancel(manual_dns_retry_after_id)
                except tk.TclError:
                    pass
                manual_dns_retry_after_id = None
            state: RealtimeState = payload["state"]
            players = state.players
            force = bool(payload["force"])
            has_rankings = bool(state.daily_ranking or state.global_ranking)
            manual_last_fetch_error = ""
            if has_rankings:
                rank_signature = kills_rank_signature_for_state(state)
                rank_changed = rank_signature != manual_last_rank_signature
                if not force and not rank_changed:
                    manual_poll_quiet_cycles = min(manual_poll_quiet_cycles + 1, 8)
                    return
                manual_poll_quiet_cycles = 0 if rank_changed else min(manual_poll_quiet_cycles + 1, 8)
                manual_last_rank_signature = rank_signature
                apply_kills_rankings(state)
                if rank_changed:
                    save_kills_rank_cache()
                manual_remote_count_override = state.total_players
                manual_remote_total_override = state.total_kills
                update_manual_metrics()
                if state.updated_by:
                    set_text_var(manual_source_var, state.updated_by)
                if force:
                    set_text_var(manual_status_var, "Ranking atualizado")
                source_suffix = f" por {state.updated_by}" if state.updated_by else ""
                display_count = state.total_players if state.total_players is not None else len(state.global_ranking or players)
                display_total = state.total_kills if state.total_kills is not None else sum(player.kills for player in state.global_ranking or players)
                if force or rank_changed:
                    log(
                        f"Ranking Kills FF atualizado ({len(state.daily_ranking or [])} diario, "
                        f"{display_count} geral, {display_total} kills){source_suffix}."
                    )
                return
            if force:
                set_text_var(kills_overlay_status_var, "Jarvis respondeu sem rank do dia/geral")
            signature = manual_signature(players)
            current_signature = manual_signature(read_manual_players_light(scope=current_manual_scope()))
            if signature != current_signature:
                if time.monotonic() - manual_last_local_edit_at < 1.2 and not force:
                    manual_poll_quiet_cycles = min(manual_poll_quiet_cycles + 1, 8)
                    return
                manual_poll_quiet_cycles = 0
                manual_last_remote_signature = signature
                set_manual_players(
                    players,
                    total_players=state.total_players,
                    total_kills=state.total_kills,
                    scope=current_manual_scope(),
                )
                if state.updated_by:
                    set_text_var(manual_source_var, state.updated_by)
                if force:
                    set_text_var(manual_status_var, "Atualizado pelo painel")
                source_suffix = f" por {state.updated_by}" if state.updated_by else ""
                display_count = state.total_players if state.total_players is not None else len(players)
                display_total = state.total_kills if state.total_kills is not None else sum(player.kills for player in players)
                log(f"Painel lido em tempo real ({display_count} jogador(es), {display_total} kills){source_suffix}.")
            elif force:
                manual_poll_quiet_cycles = min(manual_poll_quiet_cycles + 1, 8)
                manual_remote_count_override = state.total_players
                manual_remote_total_override = state.total_kills
                update_manual_metrics()
                if state.updated_by:
                    set_text_var(manual_source_var, state.updated_by)
                log("Painel lido, sem mudanças na lista de kills.")
            else:
                manual_poll_quiet_cycles = min(manual_poll_quiet_cycles + 1, 8)
            return

        if kind == "fetch_error":
            manual_fetching = False
            error = str(payload["error"])
            force = bool(payload["force"])
            manual_poll_quiet_cycles = min(manual_poll_quiet_cycles + 1, 8)
            if force:
                set_text_var(manual_status_var, "Painel sem leitura")
            dns_error = "NameResolutionError" in error or "getaddrinfo failed" in error or "Failed to resolve" in error
            if dns_error:
                cache_loaded = apply_kills_rank_cache()
                if force:
                    set_text_var(kills_overlay_status_var, "DNS falhou; usando último rank salvo" if cache_loaded else "DNS falhou; aguardando reconexão")
            else:
                if force:
                    set_text_var(kills_overlay_status_var, "Erro ao ler ranking")
            if force or error != manual_last_fetch_error:
                log(f"Nao consegui ler o painel via GET: {error}")
                manual_last_fetch_error = error
            return

        if kind == "jarvis_test":
            if isinstance(payload, dict):
                kills_error = str(payload.get("kills") or "")
                queue_error = str(payload.get("queue") or "")
                overlay_error = str(payload.get("overlay") or "")
                tikfinity_error = str(payload.get("tikfinity") or "")
                manual_status_var.set("Jarvis conectado" if not kills_error else "Jarvis com erro")
                ff_queue_status_var.set("Jarvis conectado" if not queue_error else "Jarvis com erro")
                if overlay_error == "Endpoint opcional nao configurado":
                    ff_overlay_status_var.set("Opcional")
                else:
                    ff_overlay_status_var.set("Jarvis conectado" if not overlay_error else "Jarvis com erro")
                if tikfinity_error == "Endpoint opcional nao configurado":
                    tikfinity_ff_status_var.set("Opcional")
                else:
                    tikfinity_ff_status_var.set("Jarvis conectado" if not tikfinity_error else "Jarvis com erro")
                errors = []
                if kills_error:
                    errors.append(f"Kills FF: {kills_error}")
                if queue_error:
                    errors.append(f"Fila FF: {queue_error}")
                if overlay_error and overlay_error != "Endpoint opcional nao configurado":
                    errors.append(f"Overlay FF: {overlay_error}")
                if tikfinity_error and tikfinity_error != "Endpoint opcional nao configurado":
                    errors.append(f"TikFinity FF: {tikfinity_error}")
            else:
                errors = payload if isinstance(payload, list) else [str(payload)]
                if errors:
                    manual_status_var.set("Jarvis com erro")
                    ff_queue_status_var.set("Jarvis com erro")
                    ff_overlay_status_var.set("Jarvis com erro")
                    tikfinity_ff_status_var.set("Jarvis com erro")
            if errors:
                log("Teste Jarvis FF falhou: " + " | ".join(str(error) for error in errors))
            else:
                if isinstance(payload, dict) and payload.get("overlay") == "Endpoint opcional nao configurado":
                    log("Teste Jarvis FF concluido: Kills FF e Fila FF responderam via GET; Overlay FF esta opcional.")
                else:
                    log("Teste Jarvis FF concluido: endpoints configurados responderam via GET.")
            return

        if kind == "overlay_sent":
            ff_overlay_sending = False
            ff_overlay_last_signature = str(payload.get("signature", ""))
            ff_overlay_poll_quiet_cycles = 0
            set_text_var(ff_overlay_status_var, "Sincronizado")
            response_text = str(payload.get("response", "")).strip()
            if response_text:
                log(f"Overlay FF enviado para o Jarvis. Resposta: {response_text[:200]}")
            else:
                log("Overlay FF enviado para o Jarvis.")
            return

        if kind == "overlay_send_error":
            ff_overlay_sending = False
            ff_overlay_status_var.set("Erro no envio")
            log(f"Erro ao enviar Overlay FF para o Jarvis: {payload}")
            return

        if kind == "overlay_fetched":
            ff_overlay_fetching = False
            kills_state: RealtimeState = payload["kills_state"]
            queue_state: FFQueueState = payload["queue_state"]
            force = bool(payload.get("force", False)) if isinstance(payload, dict) else False
            kills_has_rankings = bool(kills_state.daily_ranking or kills_state.global_ranking)
            remote_kills_signature = manual_signature([] if kills_has_rankings else kills_state.players)
            remote_queue_signature = ff_queue_signature(queue_state.entries)
            current_kills_signature = manual_signature([] if kills_has_rankings else read_manual_players_light(scope=current_manual_scope()))
            current_queue_signature = ff_queue_signature(collect_ff_queue_entries())
            if kills_has_rankings:
                rank_signature = kills_rank_signature_for_state(kills_state)
                if force or rank_signature != manual_last_rank_signature:
                    apply_kills_rankings(kills_state)
                    manual_last_rank_signature = rank_signature
                    ff_overlay_poll_quiet_cycles = 0
                else:
                    ff_overlay_poll_quiet_cycles = min(ff_overlay_poll_quiet_cycles + 1, 8)
                manual_remote_count_override = kills_state.total_players
                manual_remote_total_override = kills_state.total_kills
                update_manual_metrics()
                if kills_state.updated_by:
                    set_text_var(manual_source_var, kills_state.updated_by)
                if force:
                    set_text_var(manual_status_var, "Ranking atualizado")
            if (
                not force
                and remote_kills_signature == current_kills_signature
                and remote_queue_signature == current_queue_signature
            ):
                ff_overlay_poll_quiet_cycles = min(ff_overlay_poll_quiet_cycles + 1, 8)
                return
            if (
                not force
                and (
                    time.monotonic() - manual_last_local_edit_at < 1.2
                    or time.monotonic() - ff_queue_last_local_edit_at < 1.2
                )
            ):
                ff_overlay_poll_quiet_cycles = min(ff_overlay_poll_quiet_cycles + 1, 8)
                return
            ff_overlay_poll_quiet_cycles = 0
            ff_overlay_applying_remote = True
            try:
                if kills_state.players and not kills_has_rankings:
                    set_manual_players(
                        kills_state.players,
                        total_players=kills_state.total_players,
                        total_kills=kills_state.total_kills,
                        scope=current_manual_scope(),
                    )
                    if kills_state.updated_by:
                        set_text_var(manual_source_var, kills_state.updated_by)
                    if force:
                        set_text_var(manual_status_var, "Overlay lido")
                if queue_state.entries:
                    set_ff_queue_entries(
                        queue_state.entries,
                        total_members=queue_state.total_members,
                        total_credits=queue_state.total_credits,
                    )
                    if queue_state.updated_by:
                        set_text_var(ff_queue_source_var, queue_state.updated_by)
                    if force:
                        set_text_var(ff_queue_status_var, "Overlay lido")
                if force:
                    set_text_var(ff_overlay_status_var, "Atualizado pelo Jarvis")
                refresh_ff_overlay(force=True)
                ff_overlay_last_signature = ff_overlay_signature()
            finally:
                ff_overlay_applying_remote = False
            if force:
                log(
                    "Overlay FF lido do Jarvis "
                    f"({len(kills_state.players)} jogador(es), {len(queue_state.entries)} item(ns) de fila)."
                )
            return

        if kind == "overlay_fetch_error":
            ff_overlay_fetching = False
            error = str(payload.get("error", payload))
            force = bool(payload.get("force", False)) if isinstance(payload, dict) else False
            ff_overlay_poll_quiet_cycles = min(ff_overlay_poll_quiet_cycles + 1, 8)
            if force:
                set_text_var(ff_overlay_status_var, "Jarvis sem leitura")
            if force:
                log(f"Nao consegui ler o Overlay FF via GET: {error}")
            return

        if kind == "ff_overlay_config_fetched":
            data = payload.get("payload") if isinstance(payload, dict) else payload
            if isinstance(data, dict):
                apply_ff_overlay_site_config(data)
            log("Configuracao OBS do Overlay FF carregada do Jarvis.")
            return

        if kind == "ff_overlay_config_saved":
            data = payload.get("payload") if isinstance(payload, dict) else payload
            if isinstance(data, dict):
                apply_ff_overlay_site_config(data)
            label = str(payload.get("label") or "config") if isinstance(payload, dict) else "config"
            ff_overlay_site_status_var.set("Config sincronizada")
            log(f"Configuracao OBS do Overlay FF atualizada pelo Jarvis: {label}.")
            return

        if kind == "ff_overlay_config_error":
            label = str(payload.get("label") or "Overlay FF") if isinstance(payload, dict) else "Overlay FF"
            error = str(payload.get("error") or payload) if isinstance(payload, dict) else str(payload)
            ff_overlay_site_status_var.set("Erro")
            log(f"Nao consegui sincronizar config do Overlay FF ({label}): {error}")
            return

    def handle_ff_queue_sync_event(kind: str, payload: Any) -> None:
        nonlocal ff_queue_sending, ff_queue_fetching, ff_queue_last_signature, ff_queue_last_fetch_error
        nonlocal ff_queue_poll_quiet_cycles
        if kind == "sent":
            ff_queue_sending = False
            ff_queue_last_signature = payload["signature"]
            ff_queue_poll_quiet_cycles = 0
            set_text_var(ff_queue_status_var, "Sincronizado")
            set_text_var(ff_queue_source_var, device_name_var.get().strip() or default_device_name())
            response_text = str(payload.get("response", "")).strip()
            if response_text:
                log(f"Fila FF enviada para o Jarvis ({payload['count']} jogador(es)). Resposta: {response_text[:200]}")
            else:
                log(f"Fila FF enviada para o Jarvis ({payload['count']} jogador(es)).")
            return

        if kind == "send_error":
            ff_queue_sending = False
            ff_queue_status_var.set("Erro no envio")
            log(f"Erro ao enviar Fila FF para o Jarvis: {payload}")
            return

        if kind == "action_done":
            state: FFQueueState = payload["state"]
            entries = state.entries
            action = str(payload.get("action") or "")
            current_entries = collect_ff_queue_entries()
            if action in {"add_credit", "remove_credit", "set_credit"} and time.monotonic() - ff_queue_last_local_edit_at < 3.0:
                ff_queue_last_signature = ff_queue_signature(current_entries)
                ff_queue_last_fetch_error = ""
                ff_queue_poll_quiet_cycles = 0
                if state.updated_by:
                    set_text_var(ff_queue_source_var, state.updated_by)
                set_text_var(ff_queue_status_var, "Sincronizado")
                label = str(payload.get("label") or action or "acao")
                log(f"Fila FF atualizada: {label} ({len(current_entries)} jogador(es)).")
                return
            if not entries and current_entries:
                ff_queue_last_signature = ff_queue_signature(current_entries)
                ff_queue_last_fetch_error = ""
                ff_queue_poll_quiet_cycles = 0
                if state.updated_by:
                    set_text_var(ff_queue_source_var, state.updated_by)
                label = str(payload.get("label") or payload.get("action") or "acao")
                set_text_var(ff_queue_status_var, "Sincronizado")
                log(f"Fila FF confirmou a acao sem devolver lista completa: {label}.")
                return
            set_ff_queue_entries(entries, total_members=state.total_members, total_credits=state.total_credits)
            ff_queue_last_signature = ff_queue_signature(entries)
            ff_queue_last_fetch_error = ""
            ff_queue_poll_quiet_cycles = 0
            if state.updated_by:
                set_text_var(ff_queue_source_var, state.updated_by)
            label = str(payload.get("label") or payload.get("action") or "acao")
            set_text_var(ff_queue_status_var, "Sincronizado")
            log(f"Fila FF atualizada pelo Jarvis: {label} ({len(entries)} jogador(es)).")
            return

        if kind == "action_error":
            label = str(payload.get("label") or payload.get("action") or "acao")
            error = str(payload.get("error") or payload)
            ff_queue_status_var.set("Erro na acao")
            log(f"Nao consegui aplicar acao da Fila FF ({label}): {error}")
            return

        if kind == "tikfinity_ff_fetched":
            data = payload.get("payload") if isinstance(payload, dict) else payload
            if isinstance(data, dict):
                apply_tikfinity_ff_state(data)
            tikfinity_ff_status_var.set("TikFinity carregado")
            log("TikFinity Gifts FF lido do Jarvis.")
            return

        if kind == "tikfinity_ff_action_done":
            data = payload.get("payload") if isinstance(payload, dict) else payload
            if isinstance(data, dict):
                apply_tikfinity_ff_state(data)
            label = str(payload.get("label") or "acao") if isinstance(payload, dict) else "acao"
            tikfinity_ff_status_var.set("Sincronizado")
            log(f"TikFinity Gifts FF atualizado pelo Jarvis: {label}.")
            fetch_ff_queue(force=True)
            return

        if kind == "tikfinity_ff_error":
            label = str(payload.get("label") or "TikFinity FF") if isinstance(payload, dict) else "TikFinity FF"
            error = str(payload.get("error") or payload) if isinstance(payload, dict) else str(payload)
            tikfinity_ff_status_var.set("Erro")
            log(f"Nao consegui sincronizar {label}: {error}")
            return

        if kind == "fetched":
            ff_queue_fetching = False
            state: FFQueueState = payload["state"]
            entries = state.entries
            force = bool(payload["force"])
            signature = ff_queue_signature(entries)
            current_signature = ff_queue_signature(collect_ff_queue_entries())
            ff_queue_last_fetch_error = ""
            remote_totals_changed = (
                state.total_members is not None
                and state.total_members != ff_queue_remote_count_override
            ) or (
                state.total_credits is not None
                and state.total_credits != ff_queue_remote_rooms_override
            )
            if signature != current_signature:
                if time.monotonic() - ff_queue_last_local_edit_at < 1.2 and not force:
                    ff_queue_poll_quiet_cycles = min(ff_queue_poll_quiet_cycles + 1, 8)
                    return
                ff_queue_poll_quiet_cycles = 0
                set_ff_queue_entries(entries, total_members=state.total_members, total_credits=state.total_credits)
                if state.updated_by:
                    set_text_var(ff_queue_source_var, state.updated_by)
                if force:
                    set_text_var(ff_queue_status_var, "Atualizado pelo Jarvis")
                source_suffix = f" por {state.updated_by}" if state.updated_by else ""
                log(f"Fila FF lida em tempo real ({len(entries)} jogador(es)){source_suffix}.")
            elif remote_totals_changed:
                ff_queue_poll_quiet_cycles = 0
                set_ff_queue_entries(entries, total_members=state.total_members, total_credits=state.total_credits)
                if state.updated_by:
                    set_text_var(ff_queue_source_var, state.updated_by)
                if force:
                    set_text_var(ff_queue_status_var, "Resumo atualizado")
                if force:
                    log("Resumo da Fila FF atualizado pelo Jarvis.")
            elif force:
                ff_queue_poll_quiet_cycles = min(ff_queue_poll_quiet_cycles + 1, 8)
                if state.updated_by:
                    set_text_var(ff_queue_source_var, state.updated_by)
                log("Fila FF lida, sem mudanças.")
            else:
                ff_queue_poll_quiet_cycles = min(ff_queue_poll_quiet_cycles + 1, 8)
            return

        if kind == "fetch_error":
            ff_queue_fetching = False
            error = str(payload["error"])
            force = bool(payload["force"])
            ff_queue_poll_quiet_cycles = min(ff_queue_poll_quiet_cycles + 1, 8)
            if force:
                set_text_var(ff_queue_status_var, "Jarvis sem leitura")
            if force or error != ff_queue_last_fetch_error:
                log(f"Nao consegui ler a Fila FF via GET: {error}")
                ff_queue_last_fetch_error = error

    def schedule_sync_queue_pump(delay_ms: int = 0) -> None:
        nonlocal sync_pump_after_id
        if app_closing:
            return
        if not in_ui_thread():
            return
        if sync_pump_after_id is not None:
            try:
                root.after_cancel(sync_pump_after_id)
            except tk.TclError:
                pass
        sync_pump_after_id = root.after(max(0, delay_ms), pump_sync_queue)

    def pump_sync_queue() -> None:
        nonlocal sync_pump_after_id, sync_workers_active
        sync_pump_after_id = None
        if app_closing:
            return
        processed = False
        processed_count = 0
        batch_limit = 12
        deadline = time.monotonic() + UI_PUMP_TIME_BUDGET_SECONDS
        while processed_count < batch_limit:
            if processed_count and time.monotonic() >= deadline:
                break
            try:
                kind, payload = sync_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            processed = True
            if kind == "__worker_done":
                sync_workers_active = max(0, sync_workers_active - 1)
                continue
            handle_sync_event(kind, payload)
        if not app_closing and not sync_queue.empty():
            schedule_sync_queue_pump(25 if processed else 0)
        elif not app_closing and (
            sync_workers_active or manual_sending or manual_fetching or ff_overlay_sending or ff_overlay_fetching
        ):
            schedule_sync_queue_pump(250)

    def schedule_ff_queue_sync_pump(delay_ms: int = 0) -> None:
        nonlocal ff_queue_pump_after_id
        if app_closing:
            return
        if not in_ui_thread():
            return
        if ff_queue_pump_after_id is not None:
            try:
                root.after_cancel(ff_queue_pump_after_id)
            except tk.TclError:
                pass
        ff_queue_pump_after_id = root.after(max(0, delay_ms), pump_ff_queue_sync_queue)

    def pump_ff_queue_sync_queue() -> None:
        nonlocal ff_queue_pump_after_id, ff_queue_workers_active
        ff_queue_pump_after_id = None
        if app_closing:
            return
        processed = False
        processed_count = 0
        batch_limit = 12
        deadline = time.monotonic() + UI_PUMP_TIME_BUDGET_SECONDS
        while processed_count < batch_limit:
            if processed_count and time.monotonic() >= deadline:
                break
            try:
                kind, payload = ff_queue_sync_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            processed = True
            if kind == "__worker_done":
                ff_queue_workers_active = max(0, ff_queue_workers_active - 1)
                continue
            handle_ff_queue_sync_event(kind, payload)
        if not app_closing and not ff_queue_sync_queue.empty():
            schedule_ff_queue_sync_pump(25 if processed else 0)
        elif not app_closing and (ff_queue_workers_active or ff_queue_sending or ff_queue_fetching):
            schedule_ff_queue_sync_pump(250)

    def open_layout_window() -> None:
        window = ctk.CTkToplevel(root)
        window.title("Personalizar janelas")
        window.geometry("520x420")
        window.minsize(480, 380)
        window.configure(fg_color=canvas_bg)
        window.transient(root)
        window.grab_set()

        box = ctk.CTkFrame(window, fg_color=panel, corner_radius=12, border_width=1, border_color=border)
        box.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        box.columnconfigure(1, weight=1)
        ctk.CTkLabel(box, text="Personalizar janelas", text_color=fg, font=("Segoe UI Semibold", 18)).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=18, pady=(18, 2)
        )
        ctk.CTkLabel(
            box,
            text="Ajuste em tempo real e salve para manter ao reabrir.",
            text_color=muted,
            font=("Segoe UI", 11),
        ).grid(row=1, column=0, columnspan=3, sticky="w", padx=18, pady=(0, 18))

        rows = [
            ("Altura da fila", participants_height_var, 240, 900, queue_size_text),
            ("Altura dos eventos", events_height_var, 90, 360, event_size_text),
            ("Largura do vencedor", winner_width_var, 260, 520, winner_size_text),
            ("Fonte da fila/chat", raffle_font_size_var, 10, 20, font_size_text),
        ]
        for row_index, (label_text, variable, min_value, max_value, value_text) in enumerate(rows, start=2):
            ctk.CTkLabel(box, text=label_text, text_color=muted, font=("Segoe UI", 12)).grid(
                row=row_index, column=0, sticky="w", padx=18, pady=12
            )
            slider = ctk.CTkSlider(
                box,
                from_=min_value,
                to=max_value,
                number_of_steps=max_value - min_value,
                variable=variable,
                command=apply_layout_settings,
            )
            slider.grid(row=row_index, column=1, sticky="ew", padx=14, pady=12)
            ctk.CTkLabel(box, textvariable=value_text, text_color=fg, font=("Segoe UI Semibold", 12)).grid(
                row=row_index, column=2, sticky="e", padx=18, pady=12
            )

        def save_and_close() -> None:
            save_form()
            window.destroy()

        actions = ctk.CTkFrame(box, fg_color=panel, corner_radius=0)
        actions.grid(row=6, column=0, columnspan=3, sticky="ew", padx=18, pady=(18, 18))
        button(actions, "Salvar personalização", save_and_close, "accent").pack(side=tk.LEFT, padx=(0, 8))
        button(actions, "Fechar", window.destroy, "default").pack(side=tk.LEFT)

    def format_raffle_timer(seconds: int) -> str:
        seconds = max(0, seconds)
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def is_raffle_tab_active() -> bool:
        try:
            return tabview.get() == "Sorteio Chat"
        except (AttributeError, tk.TclError):
            return False

    def normalize_participant_items(items: list[Any]) -> list[RaffleParticipant]:
        normalized: list[RaffleParticipant] = []
        for index, item in enumerate(items, start=1):
            if isinstance(item, RaffleParticipant):
                normalized.append(item)
            elif isinstance(item, dict):
                name = str(item.get("name") or item.get("username") or item.get("nick") or "").strip()
                if name:
                    normalized.append(
                        RaffleParticipant(
                            key=str(item.get("key") or f"local-{index}"),
                            name=name,
                            avatar_url=str(item.get("avatar_url") or item.get("avatar") or ""),
                            platform=str(item.get("platform") or ""),
                            supporter_tier=str(item.get("supporter_tier") or "normal"),
                            entries=max(1, normalize_kill_value(item.get("entries", 1))),
                            bonus_reason=str(item.get("bonus_reason") or ""),
                            joined_at=str(item.get("joined_at") or ""),
                        )
                    )
            else:
                name = str(item)
                normalized.append(RaffleParticipant(key=f"local-{index}", name=name))
        return normalized

    def supporter_tier_label(tier: str) -> str:
        return {"fan": "Fã", "super_fan": "Super fã", "gift": "Gift", "sub": "Sub"}.get(str(tier or "normal"), "Seguidor")

    def cancel_raffle_participant_render() -> None:
        nonlocal raffle_participant_render_after_id, raffle_participant_render_generation
        raffle_participant_render_generation += 1
        if raffle_participant_render_after_id is None:
            return
        try:
            root.after_cancel(raffle_participant_render_after_id)
        except tk.TclError:
            pass
        raffle_participant_render_after_id = None

    def clear_participant_widgets() -> None:
        cancel_raffle_participant_render()
        for widget in participant_widgets:
            try:
                widget.destroy()
            except tk.TclError:
                pass
        participant_widgets.clear()

    def build_participant_widget(row_index: int, participant: RaffleParticipant) -> Any:
        item_frame = ctk.CTkFrame(
            participants_frame,
            fg_color="#171014" if row_index % 2 == 0 else "#0f0b0e",
            corner_radius=12,
        )
        item_frame.grid(row=row_index, column=0, sticky="ew", padx=8, pady=4)
        item_frame.columnconfigure(1, weight=1)
        avatar_label = make_avatar_label(item_frame, participant.name, participant.avatar_url, size=42)
        avatar_label.grid(row=0, column=0, sticky="w", padx=(10, 8), pady=8)
        text_stack = ctk.CTkFrame(item_frame, fg_color="transparent", corner_radius=0)
        text_stack.grid(row=0, column=1, sticky="ew", padx=(0, 14), pady=7)
        text_stack.columnconfigure(0, weight=1)
        ctk.CTkLabel(
            text_stack,
            text=f"{row_index + 1:02d}  {participant.name}",
            text_color=fg,
            font=("Segoe UI Semibold", layout_value(raffle_font_size_var, 10, 20)),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        platform_suffix = f" · {participant.platform}" if participant.platform else ""
        ctk.CTkLabel(
            text_stack,
            text=f"{participant.entries} entrada(s) · {supporter_tier_label(participant.supporter_tier)}{platform_suffix}",
            text_color=muted,
            font=("Segoe UI", max(9, layout_value(raffle_font_size_var, 10, 20) - 2)),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew")
        return item_frame

    def refresh_participant_list(items: list[Any], force: bool = False) -> None:
        nonlocal raffle_participant_render_pending, raffle_participant_pending_items, raffle_participant_render_after_id
        if not force and not is_raffle_tab_active():
            cancel_raffle_participant_render()
            raffle_participant_pending_items = list(items)
            raffle_participant_render_pending = True
            return
        participants = normalize_participant_items(items)
        desired = [
            (
                participant.key,
                participant.name,
                participant.avatar_url,
                participant.platform,
                participant.supporter_tier,
                participant.entries,
            )
            for participant in participants
        ]
        if getattr(refresh_participant_list, "_items", None) == desired:
            raffle_participant_render_pending = False
            raffle_participant_pending_items = []
            return
        refresh_participant_list._items = desired  # type: ignore[attr-defined]
        raffle_participant_render_pending = False
        raffle_participant_pending_items = []

        clear_participant_widgets()

        if not desired:
            empty = ctk.CTkLabel(
                participants_frame,
                text="Nenhum participante ainda",
                text_color=muted,
                font=("Segoe UI", layout_value(raffle_font_size_var, 10, 20)),
            )
            empty.grid(row=0, column=0, sticky="ew", padx=14, pady=14)
            participant_widgets.append(empty)
            return

        if len(participants) >= RAFFLE_PARTICIPANT_RENDER_THRESHOLD:
            snapshot = list(participants)
            render_generation = raffle_participant_render_generation

            def render_chunk(start_index: int = 0) -> None:
                nonlocal raffle_participant_render_after_id
                raffle_participant_render_after_id = None
                if app_closing or render_generation != raffle_participant_render_generation:
                    return
                end_index = min(len(snapshot), start_index + RAFFLE_PARTICIPANT_RENDER_CHUNK_SIZE)
                for row_index in range(start_index, end_index):
                    try:
                        participant_widgets.append(build_participant_widget(row_index, snapshot[row_index]))
                    except tk.TclError:
                        return
                if end_index < len(snapshot):
                    raffle_participant_render_after_id = root.after(
                        RAFFLE_PARTICIPANT_RENDER_CHUNK_DELAY_MS,
                        lambda next_index=end_index: render_chunk(next_index),
                    )

            raffle_participant_render_after_id = root.after(0, render_chunk)
            return

        for row_index, participant in enumerate(participants):
            participant_widgets.append(build_participant_widget(row_index, participant))

    def update_winner_avatar(winner: RaffleWinner | None) -> None:
        nonlocal winner_avatar_current
        if winner is None:
            winner_avatar_current = ("", "-")
            winner_avatar_label.configure(image=None, text="-")
            draw_raffle_wheel([])
            return
        winner_avatar_current = (winner.avatar_url, winner.name)
        image = request_avatar_image(winner.avatar_url, 92)
        winner_avatar_label.configure(
            image=image,
            text="" if image else avatar_initials(winner.name),
        )

    def draw_raffle_wheel(items: list[Any], focus_index: int = 0, winner: RaffleWinner | None = None, confetti: bool = False) -> None:
        participants = normalize_participant_items(items)
        wheel_canvas.delete("all")
        width = max(360, int(wheel_canvas.winfo_width() or 430))
        height = max(120, int(wheel_canvas.winfo_height() or 138))
        wheel_canvas.create_rectangle(0, 0, width, height, fill=panel_alt, outline="")
        if not participants:
            wheel_canvas.create_text(width // 2, height // 2, text="Roleta aguardando participantes", fill=muted, font=("Segoe UI", 12))
            return
        visible = 7
        card_width = max(96, width // visible)
        center = width // 2
        for offset in range(-3, 4):
            participant = participants[(focus_index + offset) % len(participants)]
            x = center + offset * card_width
            active = offset == 0
            fill = field if active else "#121016"
            outline = accent if active else border
            wheel_canvas.create_rectangle(x - card_width // 2 + 5, 20, x + card_width // 2 - 5, 108, fill=fill, outline=outline, width=2 if active else 1)
            wheel_canvas.create_oval(x - 18, 30, x + 18, 66, fill=accent if active else border, outline="")
            wheel_canvas.create_text(x, 48, text=avatar_initials(participant.name), fill=panel_alt if active else fg, font=("Segoe UI Semibold", 10))
            display_name = participant.name[:14] + ("..." if len(participant.name) > 14 else "")
            wheel_canvas.create_text(x, 80, text=display_name, fill=fg if active else muted, font=("Segoe UI Semibold", 10 if active else 9))
            wheel_canvas.create_text(x, 96, text=f"{participant.entries}x", fill=teal if active else muted, font=("Segoe UI", 9))
        wheel_canvas.create_polygon(center - 11, 8, center + 11, 8, center, 22, fill=accent, outline="")
        if winner:
            wheel_canvas.create_text(center, 124, text=f"Vencedor: {winner.name}", fill=accent, font=("Segoe UI Semibold", 12))
        if confetti:
            colors = [accent, teal, "#ffd166", "#8bb0ff", fg]
            for _ in range(42):
                x = secrets.randbelow(max(1, width))
                y = secrets.randbelow(max(1, height))
                color = colors[secrets.randbelow(len(colors))]
                wheel_canvas.create_rectangle(x, y, x + 5, y + 9, fill=color, outline="")

    def pump_avatar_results() -> None:
        nonlocal avatar_result_after_id, raffle_participant_render_pending, raffle_participant_pending_items
        avatar_result_after_id = None
        if app_closing:
            return
        updated = False
        updated_avatar_keys: set[tuple[str, int]] = set()
        processed_count = 0
        batch_limit = AVATAR_RESULT_BATCH_LIMIT
        while processed_count < batch_limit:
            try:
                url, size, image = avatar_result_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            key = (url, size)
            avatar_pending.discard(key)
            if image is not None:
                avatar_image_cache[key] = ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
            else:
                avatar_image_cache[key] = None
            updated_avatar_keys.add(key)
            updated = True
        if updated:
            try:
                prune_avatar_image_cache()
                update_chat_avatar_widget_keys(updated_avatar_keys)
                if raffle_worker is not None:
                    if is_raffle_tab_active():
                        if hasattr(refresh_participant_list, "_items"):
                            delattr(refresh_participant_list, "_items")
                        refresh_participant_list(raffle_worker.participant_items(), force=True)
                    else:
                        raffle_participant_pending_items = raffle_worker.participant_items()
                        raffle_participant_render_pending = True
                current_url, current_name = winner_avatar_current
                if current_url or current_name != "-":
                    image = avatar_image_cache.get((current_url, 92))
                    winner_avatar_label.configure(image=image, text="" if image else avatar_initials(current_name))
            except Exception:
                pass
        if not app_closing:
            delay_ms = 40 if not avatar_result_queue.empty() else 300 if avatar_pending else BACKGROUND_DISABLED_PUMP_MS
            schedule_avatar_result_pump(delay_ms)

    def refresh_winner_messages(items: list[dict[str, str]]) -> None:
        rendered = "\n".join(
            f"[{item.get('time', '--:--:--')}] {item.get('username', '')}: {item.get('comment', '')}"
            for item in items
        )
        if not rendered:
            rendered = "Aguardando mensagens do vencedor..."
        if getattr(refresh_winner_messages, "_text", None) == rendered:
            return
        refresh_winner_messages._text = rendered  # type: ignore[attr-defined]
        winner_messages_text.configure(state="normal")
        winner_messages_text.delete("1.0", "end")
        winner_messages_text.insert("end", rendered)
        winner_messages_text.see("end")
        winner_messages_text.configure(state="disabled")

    def pump_winner_messages() -> None:
        if app_closing or raffle_worker is None:
            return
        refresh_winner_messages(raffle_worker.winner_message_items())
        if not app_closing:
            root.after(600, pump_winner_messages)

    def raffle_history_path() -> Path:
        raw_path = str(config.get("raffle_history_file", "raffle_history.json")).strip() or "raffle_history.json"
        path = Path(raw_path)
        return path if path.is_absolute() else ROOT / path

    def update_raffle_status() -> None:
        nonlocal raffle_worker
        if app_closing or raffle_worker is None:
            return

        remaining = int(max(0, raffle_end_at - time.monotonic()))
        participant_names = raffle_worker.participant_names()
        raffle_timer_var.set(format_raffle_timer(remaining))
        raffle_count_var.set(str(len(participant_names)))
        raffle_entries_var.set(str(raffle_worker.total_entries()))
        refresh_participant_list(raffle_worker.participant_items())

        if raffle_worker.is_finished():
            start_raffle_button.configure(state=tk.DISABLED)
            cancel_raffle_button.configure(state=tk.DISABLED)
            finish_raffle_button.configure(state=tk.NORMAL)
            redraw_raffle_button.configure(state=tk.DISABLED)
            conclude_raffle_button.configure(state=tk.DISABLED)
            raffle_state_var.set("Pronto")
            return

        if not app_closing:
            root.after(500, update_raffle_status)

    def start_raffle() -> None:
        nonlocal raffle_worker, raffle_end_at, raffle_animating, raffle_started_at
        try:
            local_config = update_config_from_form()
            save_config_snapshot_in_background(local_config)
            if raffle_worker is not None:
                messagebox.showinfo("Sorteio", "Conclua ou cancele o sorteio atual antes de iniciar outro.")
                return
            if raffle_animating:
                return

            duration_seconds = int(local_config.get("raffle_duration_seconds", 600))
            source_mode = str(local_config.get("raffle_source_mode", "events"))
            if source_mode == "events" and chat_webhook_server is None and chat_websocket_worker is None:
                if chat_listener_hidden:
                    messagebox.showinfo(
                        "Sorteio",
                        "A captura de eventos do app esta desativada porque a aba Chat Ao Vivo esta oculta.",
                    )
                    return
                start_chat_listener()
                if chat_webhook_server is None and chat_websocket_worker is None:
                    return
            raffle_worker = TikfinityRaffleWorker(
                local_config.get("tikfinity_chat_url", "") if source_mode == "browser" else "",
                local_config.get("raffle_command", "!sorteio"),
                duration_seconds,
                log,
                source_mode=source_mode,
                entries_normal=int(local_config.get("raffle_entries_normal", 1)),
                entries_fan=int(local_config.get("raffle_entries_fan", 2)),
                entries_super_fan=int(local_config.get("raffle_entries_super_fan", 3)),
                entries_gift=int(local_config.get("raffle_entries_gift", 5)),
                entries_sub=int(local_config.get("raffle_entries_sub", 10)),
                user_cooldown_seconds=int(local_config.get("raffle_user_cooldown_seconds", 8)),
                include_moderators=bool(local_config.get("raffle_include_moderators", True)),
            )
            raffle_worker.start()
            raffle_started_at = datetime.now()
            raffle_end_at = time.monotonic() + duration_seconds
            raffle_timer_var.set(format_raffle_timer(duration_seconds))
            raffle_count_var.set("0")
            raffle_entries_var.set("0")
            raffle_winner_var.set("-")
            update_winner_avatar(None)
            raffle_state_var.set("Coletando")
            refresh_participant_list([])
            refresh_winner_messages([])
            start_raffle_button.configure(state=tk.DISABLED)
            finish_raffle_button.configure(state=tk.DISABLED)
            redraw_raffle_button.configure(state=tk.DISABLED)
            conclude_raffle_button.configure(state=tk.DISABLED)
            cancel_raffle_button.configure(state=tk.NORMAL)
            source_label = "eventos do app" if source_mode == "events" else "URL do chat legado"
            log(
                f"Sorteio iniciado por {duration_seconds // 60} minuto(s). "
                f"Fonte: {source_label}. Comando: {local_config.get('raffle_command')}"
            )
            update_raffle_status()
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def animate_winner(names: list[str], winner: RaffleWinner) -> None:
        nonlocal raffle_animating
        participants = raffle_worker.participant_items() if raffle_worker else [winner]
        frames = 58
        raffle_animating = True
        raffle_state_var.set("Sorteando")
        start_raffle_button.configure(state=tk.DISABLED)
        finish_raffle_button.configure(state=tk.DISABLED)
        redraw_raffle_button.configure(state=tk.DISABLED)
        conclude_raffle_button.configure(state=tk.DISABLED)
        cancel_raffle_button.configure(state=tk.DISABLED)

        def step(index: int = 0) -> None:
            nonlocal raffle_animating
            if index < frames:
                focus = index % max(1, len(participants))
                selected = participants[focus]
                raffle_winner_var.set(selected.name)
                draw_raffle_wheel(participants, focus_index=focus)
                if index % 4 == 0:
                    try:
                        root.bell()
                    except Exception:
                        pass
                delay = 28 + int(index * 3.3)
                root.after(delay, lambda: step(index + 1))
                return

            raffle_winner_var.set(winner.name)
            winner_index = next((index for index, participant in enumerate(participants) if participant.key == winner.key), 0)
            draw_raffle_wheel(participants, focus_index=winner_index, winner=winner, confetti=True)
            update_winner_avatar(winner)
            raffle_state_var.set("Aguardando mensagens")
            start_raffle_button.configure(state=tk.DISABLED)
            finish_raffle_button.configure(state=tk.DISABLED)
            redraw_raffle_button.configure(state=tk.NORMAL if raffle_worker and raffle_worker.has_remaining_winners() else tk.DISABLED)
            conclude_raffle_button.configure(state=tk.NORMAL)
            cancel_raffle_button.configure(state=tk.NORMAL)
            raffle_animating = False
            refresh_winner_messages([])
            pump_winner_messages()
            log(f"Vencedor do sorteio: {winner.name} ({winner.entries} entrada(s))")

        step()

    def finish_raffle() -> None:
        nonlocal raffle_worker
        if raffle_worker is None:
            return
        if not raffle_worker.is_finished():
            messagebox.showinfo("Sorteio", "Aguarde o cronometro terminar para finalizar o sorteio.")
            return

        names = raffle_worker.participant_names()
        refresh_participant_list(raffle_worker.participant_items())
        winner = raffle_worker.draw_winner()
        if winner:
            animate_winner(names, winner)
        else:
            raffle_winner_var.set("-")
            update_winner_avatar(None)
            raffle_state_var.set("Sem participantes")
            log("Sorteio encerrado sem participantes.")
            raffle_worker.stop()
            start_raffle_button.configure(state=tk.NORMAL)
            finish_raffle_button.configure(state=tk.DISABLED)
            redraw_raffle_button.configure(state=tk.DISABLED)
            conclude_raffle_button.configure(state=tk.DISABLED)
            raffle_worker = None

    def redraw_raffle() -> None:
        if raffle_worker is None or raffle_animating:
            return
        winner = raffle_worker.draw_winner()
        if not winner:
            messagebox.showinfo("Sorteio", "Nao ha outros participantes para sortear.")
            redraw_raffle_button.configure(state=tk.DISABLED)
            return
        refresh_winner_messages([])
        update_winner_avatar(None)
        animate_winner(raffle_worker.participant_names(), winner)

    def conclude_raffle() -> None:
        nonlocal raffle_worker, raffle_started_at
        if raffle_worker is None:
            return

        participants = raffle_worker.participant_names()
        participant_items = raffle_worker.participant_history_items()
        blocked_attempts = raffle_worker.blocked_history_items()
        winners = raffle_worker.drawn_winner_names()
        winner_messages = raffle_worker.winner_message_items()
        record = {
            "started_at": raffle_started_at.isoformat(timespec="seconds") if raffle_started_at else None,
            "concluded_at": datetime.now().isoformat(timespec="seconds"),
            "chat_url": tikfinity_url_var.get().strip(),
            "source_mode": raffle_source_key(),
            "command": raffle_command_var.get().strip() or "!sorteio",
            "duration_seconds": int(config.get("raffle_duration_seconds", 600)),
            "participants_count": len(participants),
            "total_entries": raffle_worker.total_entries(),
            "participants": participants,
            "participant_items": participant_items,
            "blocked_attempts": blocked_attempts,
            "winners": winners,
            "final_winner": winners[-1] if winners else None,
            "final_winner_messages": winner_messages,
        }
        path = raffle_history_path()
        append_raffle_history(path, record)
        raffle_worker.stop()
        raffle_worker = None
        raffle_started_at = None
        raffle_state_var.set("Concluido")
        start_raffle_button.configure(state=tk.NORMAL)
        finish_raffle_button.configure(state=tk.DISABLED)
        redraw_raffle_button.configure(state=tk.DISABLED)
        conclude_raffle_button.configure(state=tk.DISABLED)
        cancel_raffle_button.configure(state=tk.DISABLED)
        log(f"Sorteio concluido e salvo em: {path}")

    def cancel_raffle() -> None:
        nonlocal raffle_worker, raffle_started_at
        if raffle_worker is None:
            return
        raffle_worker.stop()
        raffle_worker = None
        raffle_started_at = None
        raffle_timer_var.set("00:00")
        update_winner_avatar(None)
        raffle_state_var.set("Cancelado")
        start_raffle_button.configure(state=tk.NORMAL)
        finish_raffle_button.configure(state=tk.DISABLED)
        redraw_raffle_button.configure(state=tk.DISABLED)
        conclude_raffle_button.configure(state=tk.DISABLED)
        cancel_raffle_button.configure(state=tk.DISABLED)
        log("Sorteio cancelado.")

    def hide_window() -> None:
        root.iconify()

    def close_app() -> None:
        nonlocal app_closing
        nonlocal manual_sync_after_id, manual_poll_after_id, manual_visual_after_id, manual_config_after_id, kills_visual_after_id
        nonlocal ff_queue_sync_after_id, ff_queue_poll_after_id
        nonlocal ff_overlay_sync_after_id, ff_overlay_poll_after_id
        nonlocal config_auto_save_after_id
        nonlocal sync_pump_after_id, ff_queue_pump_after_id, chat_event_pump_after_id
        nonlocal bot_pump_after_id, chat_timer_after_id, livepix_pump_after_id, avatar_result_after_id
        nonlocal deferred_render_after_id
        if app_closing:
            return
        save_current_config_silent(compact=True)
        app_closing = True
        for after_id in (
            manual_sync_after_id,
            manual_poll_after_id,
            manual_visual_after_id,
            manual_config_after_id,
            kills_visual_after_id,
            ff_queue_sync_after_id,
            ff_queue_poll_after_id,
            ff_overlay_sync_after_id,
            ff_overlay_poll_after_id,
            config_auto_save_after_id,
            sync_pump_after_id,
            ff_queue_pump_after_id,
            chat_event_pump_after_id,
            bot_pump_after_id,
            chat_timer_after_id,
            livepix_pump_after_id,
            avatar_result_after_id,
            deferred_render_after_id,
        ):
            if after_id is not None:
                try:
                    root.after_cancel(after_id)
                except tk.TclError:
                    pass
        manual_sync_after_id = None
        manual_poll_after_id = None
        manual_visual_after_id = None
        manual_config_after_id = None
        kills_visual_after_id = None
        ff_queue_sync_after_id = None
        ff_queue_poll_after_id = None
        ff_overlay_sync_after_id = None
        ff_overlay_poll_after_id = None
        config_auto_save_after_id = None
        sync_pump_after_id = None
        ff_queue_pump_after_id = None
        chat_event_pump_after_id = None
        bot_pump_after_id = None
        chat_timer_after_id = None
        livepix_pump_after_id = None
        avatar_result_after_id = None
        deferred_render_after_id = None
        try:
            if raffle_worker is not None:
                raffle_worker.stop()
            stop_tikfinity_direct_bridge(silent=True)
            stop_chat_listener(silent=True)
            stop_livepix_webhook(silent=True)
            close_ff_overlay_window()
            close_chat_monitor_window()
            close_chat_overlay()
            close_livepix_overlay()
            for executor in (sync_executor, ff_queue_executor, livepix_executor, bot_executor):
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except Exception:
                    pass
        finally:
            try:
                root.quit()
            except tk.TclError:
                pass
            try:
                root.destroy()
            except tk.TclError:
                pass

    livepix_left = ctk.CTkScrollableFrame(
        livepix_tab,
        fg_color=bg,
        corner_radius=0,
        scrollbar_button_color=chip_bg,
        scrollbar_button_hover_color=accent,
    )
    livepix_left.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=0)
    livepix_left.columnconfigure(0, weight=1)
    livepix_right = ctk.CTkFrame(livepix_tab, fg_color=bg, corner_radius=0)
    livepix_right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=0)
    livepix_right.columnconfigure(0, weight=1)
    livepix_right.rowconfigure(1, weight=1)

    livepix_config_card = card(livepix_left, "Livepix API", "OAuth2, webhooks, checkout, metas e alertas.")
    livepix_config_card.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
    livepix_config_card.columnconfigure(1, weight=1)
    ctk.CTkCheckBox(
        livepix_config_card,
        text="Ativar integração Livepix",
        variable=livepix_enabled_var,
        fg_color=accent,
        hover_color=accent_hover,
        border_color=border,
        text_color=fg,
    ).grid(row=2, column=0, columnspan=2, sticky="w", padx=18, pady=(4, 10))
    section_label(livepix_config_card, "Client ID", 3)
    entry(livepix_config_card, livepix_client_id_var).grid(row=3, column=1, sticky="ew", padx=(8, 18), pady=(6, 4))
    section_label(livepix_config_card, "Client Secret", 4)
    entry(livepix_config_card, livepix_client_secret_var, show="*").grid(row=4, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_config_card, "Escopos", 5)
    entry(livepix_config_card, livepix_scopes_var).grid(row=5, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_config_card, "Moeda", 6)
    combo(livepix_config_card, livepix_currency_var, ["BRL", "BNB", "BTC", "ETH", "USDT"], width=140).grid(
        row=6, column=1, sticky="w", padx=(8, 18), pady=4
    )
    livepix_config_actions = ctk.CTkFrame(livepix_config_card, fg_color=panel, corner_radius=0)
    livepix_config_actions.grid(row=7, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 16))
    button(livepix_config_actions, "Testar e sincronizar", test_livepix_account, "accent", width=150).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_config_actions, "Salvar", save_form, "default", width=88).pack(side=tk.LEFT)

    livepix_webhook_card = card(livepix_left, "Webhook local", "Recebe notificações da Livepix e atualiza o painel.")
    livepix_webhook_card.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
    livepix_webhook_card.columnconfigure(1, weight=1)
    section_label(livepix_webhook_card, "Host", 2)
    entry(livepix_webhook_card, livepix_webhook_host_var).grid(row=2, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_webhook_card, "Porta", 3)
    entry(livepix_webhook_card, livepix_webhook_port_var, width=120).grid(row=3, column=1, sticky="w", padx=(8, 18), pady=4)
    section_label(livepix_webhook_card, "Token", 4)
    entry(livepix_webhook_card, livepix_webhook_token_var).grid(row=4, column=1, sticky="ew", padx=(8, 18), pady=4)
    entry(livepix_webhook_card, livepix_endpoint_var).grid(row=5, column=0, columnspan=2, sticky="ew", padx=18, pady=(10, 4))
    livepix_webhook_actions = ctk.CTkFrame(livepix_webhook_card, fg_color=panel, corner_radius=0)
    livepix_webhook_actions.grid(row=6, column=0, columnspan=2, sticky="ew", padx=18, pady=(8, 16))
    button(livepix_webhook_actions, "Iniciar", start_livepix_webhook, "accent", width=90).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_webhook_actions, "Parar", stop_livepix_webhook, "danger", width=80).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_webhook_actions, "Copiar URL", copy_livepix_endpoint, "default", width=100).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_webhook_actions, "Cadastrar", register_livepix_webhook, "ghost", width=94).pack(side=tk.LEFT)

    livepix_checkout_card = card(livepix_left, "Checkout", "Gera links de pagamento ou mensagem paga.")
    livepix_checkout_card.grid(row=2, column=0, sticky="ew", padx=12, pady=8)
    livepix_checkout_card.columnconfigure(1, weight=1)
    section_label(livepix_checkout_card, "Valor", 2)
    entry(livepix_checkout_card, livepix_checkout_amount_var, width=140).grid(row=2, column=1, sticky="w", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Nome", 3)
    entry(livepix_checkout_card, livepix_checkout_user_var).grid(row=3, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Mensagem", 4)
    entry(livepix_checkout_card, livepix_checkout_message_var).grid(row=4, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Retorno", 5)
    entry(livepix_checkout_card, livepix_redirect_url_var).grid(row=5, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Plano ID", 6)
    entry(livepix_checkout_card, livepix_plan_id_var).grid(row=6, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Plano", 7)
    plan_row = ctk.CTkFrame(livepix_checkout_card, fg_color=panel, corner_radius=0)
    plan_row.grid(row=7, column=1, sticky="ew", padx=(8, 18), pady=4)
    plan_row.columnconfigure(0, weight=1)
    plan_row.columnconfigure(1, weight=1)
    entry(plan_row, livepix_plan_slug_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))
    entry(plan_row, livepix_plan_name_var).grid(row=0, column=1, sticky="ew", padx=(6, 0))
    section_label(livepix_checkout_card, "Descrição", 8)
    entry(livepix_checkout_card, livepix_plan_description_var).grid(row=8, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_checkout_card, "Recorrência", 9)
    sub_row = ctk.CTkFrame(livepix_checkout_card, fg_color=panel, corner_radius=0)
    sub_row.grid(row=9, column=1, sticky="ew", padx=(8, 18), pady=4)
    sub_row.columnconfigure(0, weight=1)
    sub_row.columnconfigure(1, weight=1)
    combo(sub_row, livepix_subscription_recurrence_var, ["monthly", "quarterly", "semiannual", "yearly"], width=150).grid(
        row=0, column=0, sticky="ew", padx=(0, 6)
    )
    entry(sub_row, livepix_subscriber_email_var, placeholder_text="email opcional").grid(row=0, column=1, sticky="ew", padx=(6, 0))
    livepix_checkout_actions = ctk.CTkFrame(livepix_checkout_card, fg_color=panel, corner_radius=0)
    livepix_checkout_actions.grid(row=10, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 16))
    button(livepix_checkout_actions, "Pagamento", lambda: create_livepix_checkout("payment"), "accent", width=112).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_checkout_actions, "Mensagem paga", lambda: create_livepix_checkout("message"), "default", width=126).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_checkout_actions, "Criar plano", create_livepix_plan, "ghost", width=100).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_checkout_actions, "Assinatura", create_livepix_subscription_checkout, "accent", width=104).pack(side=tk.LEFT)

    livepix_goal_card = card(livepix_left, "Meta e overlay", "Configura meta local e janela para OBS.")
    livepix_goal_card.grid(row=3, column=0, sticky="ew", padx=12, pady=(8, 12))
    livepix_goal_card.columnconfigure(1, weight=1)
    section_label(livepix_goal_card, "Título", 2)
    entry(livepix_goal_card, livepix_goal_label_var).grid(row=2, column=1, sticky="ew", padx=(8, 18), pady=4)
    section_label(livepix_goal_card, "Meta", 3)
    entry(livepix_goal_card, livepix_goal_amount_var, width=140).grid(row=3, column=1, sticky="w", padx=(8, 18), pady=4)
    section_label(livepix_goal_card, "Página", 4)
    entry(livepix_goal_card, livepix_public_page_file_var).grid(row=4, column=1, sticky="ew", padx=(8, 18), pady=4)
    ctk.CTkCheckBox(
        livepix_goal_card,
        text="Anunciar eventos Livepix no Chat Ao Vivo/overlay",
        variable=livepix_announce_in_chat_var,
        fg_color=accent,
        hover_color=accent_hover,
        border_color=border,
        text_color=fg,
    ).grid(row=5, column=0, columnspan=2, sticky="w", padx=18, pady=(8, 0))
    livepix_goal_actions = ctk.CTkFrame(livepix_goal_card, fg_color=panel, corner_radius=0)
    livepix_goal_actions.grid(row=6, column=0, columnspan=2, sticky="ew", padx=18, pady=(12, 16))
    button(livepix_goal_actions, "Abrir overlay", open_livepix_overlay, "accent", width=118).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_goal_actions, "Evento teste", add_livepix_test_event, "default", width=110).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_goal_actions, "Exportar HTML", export_livepix_public_page, "ghost", width=120).pack(side=tk.LEFT)

    livepix_metrics = ctk.CTkFrame(livepix_right, fg_color=panel_alt, corner_radius=12, border_width=1, border_color=border)
    livepix_metrics.grid(row=0, column=0, sticky="ew", padx=0, pady=(12, 8))
    for column in range(6):
        livepix_metrics.columnconfigure(column, weight=1)
    livepix_metrics.columnconfigure(6, weight=0)
    metric_specs = [
        ("Status", livepix_status_var, accent),
        ("Conta", livepix_account_display_var, fg),
        ("Total", livepix_total_display_var, teal),
        ("Carteira", livepix_balance_display_var, teal),
        ("Pendente", livepix_pending_display_var, blue),
        ("Eventos", livepix_count_display_var, fg),
    ]
    for col, (label_text, variable, color) in enumerate(metric_specs):
        ctk.CTkLabel(livepix_metrics, text=label_text, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=16, pady=(14, 0)
        )
        ctk.CTkLabel(livepix_metrics, textvariable=variable, text_color=color, font=("Segoe UI Semibold", 16), anchor="w").grid(
            row=1, column=col, sticky="ew", padx=16, pady=(0, 14)
        )
    button(livepix_metrics, "👁", toggle_livepix_metric_visibility, "ghost", width=42).grid(
        row=0,
        column=6,
        rowspan=2,
        sticky="e",
        padx=(0, 14),
        pady=14,
    )
    refresh_livepix_metric_visibility()

    livepix_events_card = card(livepix_right, "Últimos Livepix recebidos", "Histórico sincronizado da conta, pagamentos, mensagens e webhooks locais.")
    livepix_events_card.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
    livepix_events_card.columnconfigure(0, weight=1)
    livepix_events_card.rowconfigure(3, weight=1)
    livepix_control_actions = ctk.CTkFrame(livepix_events_card, fg_color=panel, corner_radius=0)
    livepix_control_actions.grid(row=2, column=0, sticky="ew", padx=18, pady=(8, 10))
    button(livepix_control_actions, "Sincronizar", lambda: sync_livepix_from_api(show_error_dialog=True), "accent", width=104).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_control_actions, "Pular alerta", lambda: livepix_control("skip"), "default", width=105).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_control_actions, "Reexibir", lambda: livepix_control("replay"), "default", width=90).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_control_actions, "Auto on", lambda: livepix_control("autoplay_on"), "accent", width=86).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_control_actions, "Auto off", lambda: livepix_control("autoplay_off"), "danger", width=86).pack(side=tk.LEFT, padx=(0, 8))
    button(livepix_control_actions, "Limpar histórico", clear_livepix_events, "ghost", width=120).pack(side=tk.LEFT)
    livepix_events_frame = ctk.CTkScrollableFrame(
        livepix_events_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        scrollbar_button_color=border,
        scrollbar_button_hover_color=accent,
    )
    livepix_events_frame.grid(row=3, column=0, sticky="nsew", padx=18, pady=(0, 18))
    livepix_events_frame.columnconfigure(0, weight=1)
    render_livepix_events.frame = livepix_events_frame  # type: ignore[attr-defined]
    update_livepix_endpoint_text()

    appearance_body = ctk.CTkScrollableFrame(
        appearance_tab,
        fg_color=bg,
        corner_radius=0,
        scrollbar_button_color=border,
        scrollbar_button_hover_color=accent,
    )
    appearance_body.grid(row=0, column=0, sticky="nsew")
    appearance_body.columnconfigure(0, weight=1)
    appearance_body.columnconfigure(1, weight=1)

    brand_card = card(
        appearance_body,
        "Identidade visual",
        "Troque o avatar principal e escolha um preset de tema para o app.",
    )
    brand_card.grid(row=0, column=0, sticky="nsew", padx=12, pady=(12, 8))
    brand_card.columnconfigure(1, weight=1)
    logo_preview_box = ctk.CTkFrame(
        brand_card,
        fg_color=field,
        corner_radius=12,
        border_width=1,
        border_color=border,
        width=152,
        height=152,
    )
    logo_preview_box.grid(row=2, column=0, rowspan=5, sticky="nw", padx=18, pady=(12, 18))
    logo_preview_box.grid_propagate(False)
    logo_preview_label = ctk.CTkLabel(logo_preview_box, text="", text_color=accent, font=("Segoe UI Semibold", 42))
    logo_preview_label.place(relx=0.5, rely=0.5, anchor="center")

    section_label(brand_card, "Preset", 2, column=1)
    appearance_preset_combo = combo(brand_card, appearance_preset_var, list(THEME_PRESETS.keys()), width=220)
    appearance_preset_combo.grid(row=2, column=2, columnspan=2, sticky="ew", padx=18, pady=5)
    appearance_preset_combo.configure(command=lambda _value: apply_theme_preset())
    section_label(brand_card, "Imagem/avatar", 3, column=1)
    entry(brand_card, logo_path_var).grid(row=3, column=2, columnspan=2, sticky="ew", padx=18, pady=5)

    theme_preview = ctk.CTkFrame(
        appearance_body,
        fg_color=panel_alt,
        corner_radius=12,
        border_width=1,
        border_color=border,
    )
    theme_preview.grid(row=0, column=1, sticky="nsew", padx=12, pady=(12, 8))
    theme_preview.columnconfigure(0, weight=1)
    ctk.CTkLabel(
        theme_preview,
        text="Preview 2026",
        text_color=fg,
        font=("Segoe UI Semibold", 20),
    ).grid(row=0, column=0, sticky="w", padx=22, pady=(22, 4))
    ctk.CTkLabel(
        theme_preview,
        text="Painel escuro, bordas suaves, alto contraste e identidade própria.",
        text_color=muted,
        font=("Segoe UI", 11),
    ).grid(row=1, column=0, sticky="w", padx=22, pady=(0, 16))
    preview_metric = ctk.CTkFrame(theme_preview, fg_color=field, corner_radius=12, border_width=1, border_color=border)
    preview_metric.grid(row=2, column=0, sticky="ew", padx=22, pady=(0, 14))
    preview_metric.columnconfigure((0, 1, 2), weight=1)
    for col, (label_text, value_text) in enumerate((("Jogadores", "8"), ("Kills", "42"), ("Status", "Live"))):
        ctk.CTkLabel(preview_metric, text=label_text, text_color=muted, font=("Segoe UI", 11)).grid(
            row=0, column=col, sticky="w", padx=14, pady=(12, 0)
        )
        ctk.CTkLabel(preview_metric, text=value_text, text_color=teal, font=("Segoe UI Semibold", 24)).grid(
            row=1, column=col, sticky="w", padx=14, pady=(0, 12)
        )
    ctk.CTkButton(
        theme_preview,
        text="Botão principal",
        fg_color=accent,
        hover_color=accent_hover,
        text_color="#fff7f7",
        corner_radius=12,
        height=40,
        font=("Segoe UI Semibold", 12),
    ).grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 22))

    colors_card = card(
        appearance_body,
        "Editor de tema",
        "Ajuste as cores do app. Salve e reabra para aplicar em toda a interface.",
    )
    colors_card.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=12, pady=(8, 12))
    colors_card.columnconfigure(1, weight=1)
    colors_card.columnconfigure(4, weight=1)
    color_labels = {
        "canvas_bg": "Fundo geral",
        "bg": "Fundo das abas",
        "panel": "Cards",
        "panel_alt": "Card destaque",
        "field": "Campos",
        "border": "Bordas",
        "fg": "Texto principal",
        "muted": "Texto secundário",
        "accent": "Cor principal",
        "accent_hover": "Hover principal",
        "teal": "Métrica/destaque",
        "blue": "Badge secundário",
        "danger": "Perigo",
    }
    color_swatches: dict[str, Any] = {}
    theme_swatch_updating = False

    def update_logo_preview(path_text: str | None = None) -> None:
        preview_theme = appearance_config_from_vars()
        if path_text is not None:
            preview_theme["logo_path"] = path_text
        path = resolve_logo_path(preview_theme)
        try:
            image = Image.open(path)
            preview_image = ctk.CTkImage(light_image=image, dark_image=image, size=(124, 124))
            root._appearance_logo_preview = preview_image  # type: ignore[attr-defined]
            logo_preview_label.configure(image=preview_image, text="")
        except Exception:
            logo_preview_label.configure(image=None, text="A")

    def choose_logo() -> None:
        selected = filedialog.askopenfilename(
            title="Escolher imagem do app",
            filetypes=[
                ("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if selected:
            logo_path_var.set(selected)
            update_logo_preview(selected)

    def clear_logo() -> None:
        logo_path_var.set("")
        update_logo_preview("")

    def choose_theme_color(key: str) -> None:
        selected = colorchooser.askcolor(color=theme_color_vars[key].get(), title=f"Escolher {color_labels[key]}")
        if selected and selected[1]:
            theme_color_vars[key].set(selected[1].lower())
            update_theme_swatches()

    def update_theme_swatches() -> None:
        nonlocal theme_swatch_updating
        if theme_swatch_updating:
            return
        theme_swatch_updating = True
        try:
            for key, widget in color_swatches.items():
                color = normalize_hex_color(theme_color_vars[key].get(), THEME_PRESETS[DEFAULT_THEME_NAME][key])
                theme_color_vars[key].set(color)
                widget.configure(fg_color=color, hover_color=color, text=color)
        finally:
            theme_swatch_updating = False

    def refresh_appearance_preview_if_needed(force: bool = False) -> None:
        nonlocal appearance_preview_pending
        if not force and not appearance_preview_pending:
            return
        if not force and not is_appearance_tab_active():
            return
        update_logo_preview()
        update_theme_swatches()
        appearance_preview_pending = False

    logo_actions = ctk.CTkFrame(brand_card, fg_color=panel, corner_radius=0)
    logo_actions.grid(row=4, column=1, columnspan=3, sticky="ew", padx=18, pady=(8, 4))
    button(logo_actions, "Escolher imagem", choose_logo, "accent", width=140).pack(side=tk.LEFT, padx=(0, 8))
    button(logo_actions, "Usar padrão", clear_logo, "ghost", width=110).pack(side=tk.LEFT, padx=(0, 8))
    ctk.CTkLabel(
        brand_card,
        text="Dica: use PNG quadrado para ficar perfeito no cabeçalho.",
        text_color=muted,
        font=("Segoe UI", 11),
    ).grid(row=5, column=1, columnspan=3, sticky="w", padx=18, pady=(4, 18))

    for index, key in enumerate(THEME_COLOR_KEYS):
        row = 2 + index // 2
        base_col = 0 if index % 2 == 0 else 3
        ctk.CTkLabel(colors_card, text=color_labels[key], text_color=muted, font=("Segoe UI", 11)).grid(
            row=row, column=base_col, sticky="w", padx=18, pady=6
        )
        entry(colors_card, theme_color_vars[key], width=110).grid(row=row, column=base_col + 1, sticky="ew", padx=8, pady=6)
        swatch = ctk.CTkButton(
            colors_card,
            text=theme_color_vars[key].get(),
            width=92,
            height=32,
            corner_radius=10,
            fg_color=theme_color_vars[key].get(),
            hover_color=theme_color_vars[key].get(),
            text_color="#ffffff",
            command=lambda color_key=key: choose_theme_color(color_key),
        )
        swatch.grid(row=row, column=base_col + 2, sticky="e", padx=(0, 18), pady=6)
        color_swatches[key] = swatch

    appearance_actions = ctk.CTkFrame(colors_card, fg_color=panel, corner_radius=0)
    appearance_actions.grid(row=10, column=0, columnspan=6, sticky="ew", padx=18, pady=(18, 18))
    button(appearance_actions, "Salvar e reabrir", lambda: save_appearance(restart=True), "accent", width=150).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    button(appearance_actions, "Salvar", lambda: save_appearance(restart=False), "ghost", width=90).pack(
        side=tk.LEFT, padx=(0, 8)
    )
    button(appearance_actions, "Aplicar preset", apply_theme_preset, "default", width=120).pack(side=tk.LEFT, padx=(0, 8))
    button(appearance_actions, "Atualizar preview", update_theme_swatches, "default", width=130).pack(side=tk.LEFT, padx=(0, 8))
    button(appearance_actions, "Minimizar", hide_window, "default", width=96).pack(side=tk.LEFT, padx=(0, 8))

    logo_preview_label.configure(image=None, text="A")

    button(general_actions, "Salvar configurações", save_form, "accent", width=150).pack(side=tk.LEFT, padx=(0, 8))
    button(general_actions, "Minimizar", hide_window, "default", width=96).pack(side=tk.LEFT, padx=(0, 8))
    button(general_actions, "Sair", close_app, "danger", width=76).pack(side=tk.LEFT, padx=(0, 8))

    start_raffle_button = button(raffle_buttons, "Iniciar sorteio", start_raffle, "accent")
    start_raffle_button.pack(side=tk.LEFT, padx=(0, 8))
    finish_raffle_button = button(raffle_buttons, "Sortear vencedor", finish_raffle)
    finish_raffle_button.configure(state="disabled")
    finish_raffle_button.pack(side=tk.LEFT, padx=(0, 8))
    redraw_raffle_button = button(raffle_buttons, "Sortear outro", redraw_raffle)
    redraw_raffle_button.configure(state="disabled")
    redraw_raffle_button.pack(side=tk.LEFT, padx=(0, 8))
    conclude_raffle_button = button(raffle_buttons, "Concluir sorteio", conclude_raffle, "accent")
    conclude_raffle_button.configure(state="disabled")
    conclude_raffle_button.pack(side=tk.LEFT, padx=(0, 8))
    button(raffle_buttons, "Personalizar janelas", open_layout_window, "ghost").pack(side=tk.LEFT, padx=(0, 8))
    cancel_raffle_button = button(raffle_buttons, "Cancelar", cancel_raffle, "danger")
    cancel_raffle_button.configure(state="disabled")
    cancel_raffle_button.pack(side=tk.LEFT, padx=(0, 8))

    def grid_action_buttons(parent: Any, specs: list[tuple[str, Any, str]], columns: int = 4) -> None:
        for column in range(columns):
            parent.columnconfigure(column, weight=1)
        for index, (text, command, style) in enumerate(specs):
            action_button = button(parent, text, command, style, width=1)
            action_button.grid(
                row=index // columns,
                column=index % columns,
                sticky="ew",
                padx=4,
                pady=4,
            )

    grid_action_buttons(
        kills_admin_actions,
        [
            ("Somar", lambda: apply_kills_admin_action("add"), "accent"),
            ("Remover kill", lambda: apply_kills_admin_action("remove"), "ghost"),
            ("Definir kills", lambda: apply_kills_admin_action("set"), "default"),
            ("Salvar nome", lambda: apply_kills_admin_action("set_name"), "default"),
            ("Salvar ID FF", lambda: apply_kills_admin_action("set_ff_id"), "default"),
            ("Ignorar", lambda: apply_kills_admin_action("ignore"), "danger"),
            ("Reexibir", lambda: apply_kills_admin_action("unignore"), "accent"),
            ("Remover rank", lambda: apply_kills_admin_action("delete"), "danger"),
            ("Reset tudo", lambda: apply_kills_admin_action("reset"), "danger"),
            ("Reset diario", lambda: apply_kills_admin_action("reset_daily"), "danger"),
            ("Reset geral", lambda: apply_kills_admin_action("reset_general"), "danger"),
            ("Atualizar", lambda: fetch_panel_kills(force=True), "default"),
            ("Limpar campos", clear_kills_admin_fields, "ghost"),
        ],
        columns=4,
    )

    for label, command, style_name, width in (
        ("Carregar", lambda: load_kills_style(force=True), "accent", 92),
        ("Salvar", save_kills_style, "accent", 86),
        ("Padrão", reset_kills_style_form, "default", 82),
        ("Copiar OBS", copy_kills_obs_url, "default", 104),
        ("Abrir", open_kills_obs_url, "ghost", 72),
    ):
        button(kills_style_actions, label, command, style_name, width=width).pack(side=tk.LEFT, padx=(0, 6))

    grid_action_buttons(
        manual_actions,
        [
            ("Adicionar jogador", open_manual_kill_dialog, "accent"),
            ("Salvar", lambda: send_manual_kills(force=True), "accent"),
            ("Zerar", reset_manual_kills, "ghost"),
        ],
        columns=3,
    )

    if ff_queue_actions is not None:
        grid_action_buttons(
            ff_queue_actions,
            [
                ("Adicionar jogador", open_ff_queue_manual_dialog, "accent"),
                ("Atender próximo", call_next_ff_queue, "accent"),
                ("Marcar jogando", mark_called_playing, "default"),
                ("Finalizar partida", finish_playing_ff_queue, "ghost"),
                ("Enviar agora", lambda: send_ff_queue(force=True), "accent"),
                ("Buscar Jarvis", lambda: fetch_ff_queue(force=True), "default"),
                ("Sincronizar", lambda: run_ff_queue_remote_action("sync", label="Sincronizando fila"), "default"),
                ("Limpar", clear_ff_queue, "danger"),
                ("Salvar", save_form, "ghost"),
            ],
        )

    if ff_overlay_site_actions is not None:
        grid_action_buttons(
            ff_overlay_site_actions,
            [
                ("Carregar config", lambda: fetch_ff_overlay_site_config(force=True), "accent"),
                ("Salvar no Jarvis", save_ff_overlay_site_config, "accent"),
                ("Criar perfil", create_ff_overlay_site_profile, "default"),
                ("Copiar URL OBS", copy_ff_overlay_site_url, "default"),
                ("Abrir OBS", open_ff_overlay_site_url, "default"),
                ("Salvar local", save_form, "ghost"),
            ],
            columns=3,
        )

    if ff_overlay_actions is not None:
        grid_action_buttons(
            ff_overlay_actions,
            [
                ("Abrir overlay", open_ff_overlay_window, "accent"),
                ("Atualizar Jarvis", refresh_overlay_from_jarvis, "accent"),
                ("Enviar overlay", lambda: send_ff_overlay(force=True), "accent"),
                ("Buscar overlay", lambda: fetch_ff_overlay(force=True), "default"),
                ("Atualizar kills", lambda: fetch_panel_kills(force=True), "default"),
                ("Buscar fila", lambda: fetch_ff_queue(force=True), "default"),
                ("Salvar", save_form, "ghost"),
                ("Fechar overlay", close_ff_overlay_window, "danger"),
            ],
            columns=4,
        )
    if chat_actions is not None:
        button(chat_actions, "Iniciar chat", start_chat_listener, "accent", width=120).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Abrir janela", open_chat_monitor_window, "default", width=112).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Overlay jogo", open_chat_overlay_window, "accent", width=112).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Parar", stop_chat_listener, "danger", width=84).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Copiar endpoint", copy_chat_endpoint, "default", width=130).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Limpar chat", clear_chat_messages, "ghost", width=104).pack(side=tk.LEFT, padx=(0, 8))
        button(chat_actions, "Salvar", save_form, "ghost", width=86).pack(side=tk.LEFT, padx=(0, 8))

    root.protocol("WM_DELETE_WINDOW", close_app)

    def pump_log() -> None:
        nonlocal log_rendered_count, log_needs_full_render, log_full_render_cursor
        if app_closing:
            return
        messages: list[str] = []
        processed_count = 0
        batch_limit = LOG_PUMP_BATCH_LIMIT
        deadline = time.monotonic() + UI_PUMP_TIME_BUDGET_SECONDS
        while processed_count < batch_limit:
            if processed_count and time.monotonic() >= deadline:
                break
            try:
                message = log_queue.get_nowait()
            except queue.Empty:
                break
            processed_count += 1
            messages.append(message)
        if messages:
            log_render_buffer.extend(messages)
            overflow = len(log_render_buffer) - LOG_TEXT_MAX_LINES
            if overflow > 0:
                del log_render_buffer[:overflow]
                log_rendered_count = max(0, log_rendered_count - overflow)
                log_full_render_cursor = 0
                log_needs_full_render = True
        logs_active = is_logs_tab_active()
        if log_rendered_count > len(log_render_buffer):
            log_rendered_count = 0
            log_full_render_cursor = 0
            log_needs_full_render = True
        if logs_active and (log_needs_full_render or log_rendered_count < len(log_render_buffer)):
            try:
                log_text.configure(state="normal")
                if log_needs_full_render:
                    if log_full_render_cursor <= 0:
                        log_text.delete("1.0", tk.END)
                        log_rendered_count = 0
                    end_index = min(
                        len(log_render_buffer),
                        log_full_render_cursor + LOG_FULL_RENDER_CHUNK_LINES,
                    )
                    chunk = log_render_buffer[log_full_render_cursor:end_index]
                    if chunk:
                        log_text.insert(tk.END, "\n".join(chunk) + "\n")
                    log_full_render_cursor = end_index
                    log_rendered_count = end_index
                    if end_index >= len(log_render_buffer):
                        log_full_render_cursor = 0
                        log_needs_full_render = False
                else:
                    pending_messages = log_render_buffer[log_rendered_count:]
                    if pending_messages:
                        log_text.insert(tk.END, "\n".join(pending_messages) + "\n")
                        log_rendered_count = len(log_render_buffer)
                log_text.see(tk.END)
                log_text.configure(state="disabled")
            except tk.TclError:
                pass
        if not app_closing:
            if logs_active and log_needs_full_render:
                delay_ms = 35
            elif not log_queue.empty():
                delay_ms = 30
            elif logs_active and messages:
                delay_ms = 150
            elif messages:
                delay_ms = 450
            elif logs_active:
                delay_ms = 900
            else:
                delay_ms = LOG_INACTIVE_IDLE_PUMP_MS
            root.after(delay_ms, pump_log)

    saved_manual_players = parse_players_payload(config.get("manual_kills", []))
    saved_manual_by_scope = config.get("manual_kills_by_scope")
    if isinstance(saved_manual_by_scope, dict):
        manual_scope_buffers["daily"] = parse_players_payload(saved_manual_by_scope.get("daily", []))
        manual_scope_buffers["general"] = parse_players_payload(saved_manual_by_scope.get("general", []))
    if not (manual_scope_buffers["daily"] or manual_scope_buffers["general"]):
        manual_scope_buffers[manual_active_scope] = clone_player_list(saved_manual_players)
    initial_manual_players = manual_scope_buffers.get(manual_active_scope, [])
    if is_kills_ff_tab_active():
        initial_manual_players = manual_scope_display_players(manual_active_scope, prefer_remote=False)
        set_manual_players(initial_manual_players, scope=manual_active_scope)
    else:
        manual_table_render_pending = True
        manual_table_render_scope = manual_active_scope
        update_manual_metrics(initial_manual_players)
    sync_kills_rank_tab_with_manual_scope(manual_active_scope)
    manual_last_signature = manual_signature(initial_manual_players, manual_active_scope)
    saved_ff_queue_entries = parse_ff_queue_payload(config.get("ff_queue_items", []))
    if ff_queue_site_sync_hidden:
        ff_queue_last_signature = ff_queue_signature(saved_ff_queue_entries)
    else:
        set_ff_queue_entries(saved_ff_queue_entries)
        ff_queue_last_signature = ff_queue_signature(collect_ff_queue_entries())
    set_custom_commands(parse_chat_commands_payload(config.get("chat_commands", [])))
    set_chat_timers(parse_chat_timers_payload(config.get("chat_timers", [])))
    if not ff_queue_site_sync_hidden:
        ff_queue_enabled_var.trace_add("write", lambda *_args: schedule_ff_queue_sync(100))
        ff_queue_poll_seconds_var.trace_add("write", lambda *_args: schedule_ff_queue_poll())
    auto_update_var.trace_add(
        "write",
        lambda *_args: general_update_state_var.set("Ativa" if auto_update_var.get() else "Desativada"),
    )
    chat_webhook_host_var.trace_add("write", lambda *_args: update_chat_endpoint_text())
    chat_webhook_port_var.trace_add("write", lambda *_args: update_chat_endpoint_text())
    chat_webhook_token_var.trace_add("write", lambda *_args: update_chat_endpoint_text())
    chat_websocket_url_var.trace_add("write", lambda *_args: update_chat_endpoint_text())
    chat_filter_var.trace_add("write", lambda *_args: refresh_chat_messages(force=True))
    livepix_webhook_host_var.trace_add("write", lambda *_args: update_livepix_endpoint_text())
    livepix_webhook_port_var.trace_add("write", lambda *_args: update_livepix_endpoint_text())
    livepix_webhook_token_var.trace_add("write", lambda *_args: update_livepix_endpoint_text())
    livepix_goal_amount_var.trace_add("write", lambda *_args: schedule_livepix_dashboard_refresh())
    livepix_currency_var.trace_add("write", lambda *_args: schedule_livepix_dashboard_refresh())

    bind_config_autosave(
        sync_url_var,
        title_var,
        kills_style_url_var,
        sync_room_var,
        ff_queue_url_var,
        ff_overlay_url_var,
        ff_overlay_config_url_var,
        ff_overlay_site_profile_var,
        tikfinity_ff_url_var,
        tikfinity_ff_profile_var,
        tikfinity_ff_enabled_var,
        tikfinity_ff_coins_var,
        tikfinity_ff_token_var,
        ff_queue_room_var,
        jarvis_base_url_var,
        ff_queue_enabled_var,
        ff_overlay_enabled_var,
        ff_queue_poll_seconds_var,
        device_name_var,
        jarvis_token_var,
        poll_seconds_var,
        manual_scope_var,
        auto_update_var,
        updates_manifest_url_var,
        tikfinity_url_var,
        chat_source_var,
        chat_webhook_host_var,
        chat_webhook_port_var,
        chat_webhook_token_var,
        chat_websocket_url_var,
        chat_commands_enabled_var,
        chat_timers_enabled_var,
        bot_delivery_method_var,
        bot_streamerbot_ws_url_var,
        bot_streamerbot_http_url_var,
        bot_streamerbot_password_var,
        bot_streamerbot_action_name_var,
        bot_streamerbot_action_id_var,
        bot_safe_delay_var,
        bot_default_cooldown_var,
        bot_default_timer_interval_var,
        bot_default_timer_min_messages_var,
        bot_ignore_usernames_var,
        livepix_enabled_var,
        livepix_client_id_var,
        livepix_client_secret_var,
        livepix_scopes_var,
        livepix_webhook_host_var,
        livepix_webhook_port_var,
        livepix_webhook_token_var,
        livepix_redirect_url_var,
        livepix_goal_amount_var,
        livepix_goal_label_var,
        livepix_currency_var,
        livepix_checkout_amount_var,
        livepix_checkout_user_var,
        livepix_checkout_message_var,
        livepix_plan_id_var,
        livepix_plan_slug_var,
        livepix_plan_name_var,
        livepix_plan_description_var,
        livepix_subscription_recurrence_var,
        livepix_subscriber_email_var,
        livepix_announce_in_chat_var,
        livepix_public_page_file_var,
        raffle_source_mode_var,
        raffle_command_var,
        raffle_minutes_var,
        raffle_entries_normal_var,
        raffle_entries_fan_var,
        raffle_entries_super_fan_var,
        raffle_entries_gift_var,
        raffle_entries_sub_var,
        raffle_cooldown_var,
        raffle_include_moderators_var,
        participants_height_var,
        events_height_var,
        winner_width_var,
        raffle_font_size_var,
        chat_overlay_opacity_var,
        chat_overlay_font_size_var,
        chat_overlay_width_var,
        chat_overlay_height_var,
        chat_overlay_compact_var,
        chat_overlay_controls_var,
        chat_overlay_clickthrough_var,
        ff_overlay_opacity_var,
        ff_overlay_width_var,
        ff_overlay_height_var,
        ff_overlay_compact_var,
        ff_overlay_show_queue_var,
        ff_overlay_show_kills_var,
        appearance_preset_var,
        logo_path_var,
        *theme_color_vars.values(),
    )

    def update_local_source_labels(*_args: Any) -> None:
        local_name = device_name_var.get().strip() or default_device_name()
        manual_source_var.set(local_name)
        ff_queue_source_var.set(local_name)

    def ensure_chat_listener_for_bot(*_args: Any) -> None:
        nonlocal chat_websocket_worker
        if app_closing:
            return
        if not (chat_commands_enabled_var.get() or chat_timers_enabled_var.get()):
            return
        if chat_webhook_server is not None:
            return
        if chat_websocket_worker is not None:
            worker_thread = chat_websocket_worker.thread
            if worker_thread is not None and worker_thread.is_alive():
                return
            log("Leitor de chat WebSocket parou; reiniciando automaticamente.")
            try:
                chat_websocket_worker.stop()
            except Exception:
                pass
            chat_websocket_worker = None
        start_chat_listener(open_monitor=False)

    def ensure_bot_runtime(*_args: Any) -> None:
        if not (chat_commands_enabled_var.get() or chat_timers_enabled_var.get() or bot_pending_confirmations):
            stop_tikfinity_direct_bridge(silent=True)
            if chat_tab_hidden:
                stop_chat_listener(silent=True)
            return
        ensure_chat_listener_for_bot()
        refresh_tikfinity_direct_bridge()
        if chat_commands_enabled_var.get() or chat_timers_enabled_var.get() or not bot_reply_queue.empty():
            schedule_bot_send_pump(0)
            schedule_chat_event_pump(0)
        if chat_timers_enabled_var.get():
            schedule_chat_timer_pump(0)

    def schedule_deferred_render_pump(delay_ms: int = 0) -> None:
        nonlocal deferred_render_after_id
        if app_closing:
            return
        if not in_ui_thread():
            return
        if deferred_render_after_id is not None:
            try:
                root.after_cancel(deferred_render_after_id)
            except tk.TclError:
                pass
        deferred_render_after_id = root.after(max(0, delay_ms), pump_deferred_kills_render)

    def pump_deferred_kills_render() -> None:
        nonlocal deferred_render_after_id, kills_rank_cache_pending
        deferred_render_after_id = None
        if app_closing:
            return
        kills_active = is_kills_ff_tab_active()
        ff_queue_active = is_ff_queue_tab_active()
        commands_active = is_commands_tab_active()
        timers_active = is_timers_tab_active()
        livepix_active = is_livepix_tab_active()
        raffle_active = is_raffle_tab_active()
        appearance_active = is_appearance_tab_active()
        has_kills_pending = manual_table_render_pending or kills_rank_render_pending or kills_ignored_render_pending
        has_ff_queue_pending = ff_queue_render_pending
        has_livepix_pending = livepix_history_render_pending
        has_raffle_pending = raffle_participant_render_pending and bool(raffle_participant_pending_items)
        has_appearance_pending = appearance_preview_pending and appearance_active
        if commands_active:
            ensure_custom_command_rows_rendered()
        if timers_active:
            ensure_chat_timer_rows_rendered()
        if kills_active:
            if kills_rank_cache_pending:
                kills_rank_cache_pending = False
                if not apply_kills_rank_cache():
                    refresh_kills_rank_table()
                    refresh_kills_ignored_list()
            if manual_table_render_pending and manual_table_render_after_id is None:
                render_scope = manual_table_render_scope if manual_table_render_scope in {"daily", "general"} else current_manual_scope()
                set_manual_players(
                    manual_scope_display_players(render_scope, prefer_remote=False),
                    scope=render_scope,
                    force_render=True,
                )
            try:
                active_overlay_rank_tab = kills_overlay_tabview.get()
            except (AttributeError, tk.TclError):
                active_overlay_rank_tab = "Diário"
            active_overlay_missing = (
                not kills_overlay_global_rows
                if active_overlay_rank_tab == "Geral"
                else not kills_overlay_daily_rows
            )
            if kills_rank_render_pending or active_overlay_missing:
                refresh_kills_rank_table(force=active_overlay_missing)
            if kills_ignored_render_pending or not kills_ignored_rows:
                refresh_kills_ignored_list(force=not kills_ignored_render_pending and not kills_ignored_rows)
        if ff_queue_active and ff_queue_render_pending:
            set_ff_queue_entries(
                clone_ff_queue_entries(ff_queue_cached_entries),
                minimum_rows=ff_queue_render_minimum_rows,
                total_members=ff_queue_remote_count_override,
                total_credits=ff_queue_remote_rooms_override,
            )
        if livepix_active:
            start_livepix_history_load(force=True)
            maybe_start_livepix_full_sync_when_visible()
        if livepix_active and (livepix_history_render_pending or not livepix_widgets):
            render_livepix_events(force=True)
        if raffle_active and raffle_participant_render_pending:
            refresh_participant_list(raffle_participant_pending_items, force=True)
        if appearance_active and appearance_preview_pending:
            refresh_appearance_preview_if_needed(force=True)
        active_tab_pending = (
            (kills_active and has_kills_pending)
            or (ff_queue_active and has_ff_queue_pending)
            or (livepix_active and has_livepix_pending)
            or (raffle_active and has_raffle_pending)
            or (appearance_active and has_appearance_pending)
        )
        if active_tab_pending:
            schedule_deferred_render_pump(350)

    tabview.configure(command=lambda: schedule_deferred_render_pump(0))

    def run_startup_ui_tasks() -> None:
        nonlocal kills_rank_cache_pending, raffle_participant_render_pending, raffle_participant_pending_items
        if app_closing:
            return
        update_chat_endpoint_text()
        if chat_overlay_window is not None:
            apply_chat_overlay_settings()
        if not chat_tab_hidden or chat_monitor_messages_frame is not None or chat_overlay_messages_frame is not None:
            refresh_chat_messages(force=True)
        if is_raffle_tab_active():
            refresh_participant_list([], force=True)
        else:
            raffle_participant_pending_items = []
            raffle_participant_render_pending = True
        if not kills_ff_site_sync_hidden:
            if is_kills_ff_tab_active():
                if not apply_kills_rank_cache():
                    refresh_kills_rank_table()
                    refresh_kills_ignored_list()
            else:
                kills_rank_cache_pending = True
        if not ff_queue_site_sync_hidden:
            apply_tikfinity_ff_state({})

    def run_startup_runtime_tasks() -> None:
        if app_closing:
            return
        ensure_bot_runtime()
        if chat_commands_enabled_var.get() or chat_timers_enabled_var.get():
            root.after(700, lambda: ensure_chat_listener_for_bot())

    def start_stale_pyinstaller_cleanup() -> None:
        if app_closing:
            return

        def run() -> None:
            removed = cleanup_stale_pyinstaller_dirs(APP_DIR)
            if removed:
                log(f"Limpeza leve: {removed} pasta(s) temporaria(s) antiga(s) removida(s).")

        threading.Thread(target=run, name="AizenPyInstallerCleanup", daemon=True).start()

    device_name_var.trace_add("write", update_local_source_labels)
    chat_commands_enabled_var.trace_add("write", ensure_bot_runtime)
    chat_timers_enabled_var.trace_add("write", ensure_bot_runtime)
    livepix_enabled_var.trace_add("write", lambda *_args: start_livepix_history_load(force=livepix_enabled_var.get()))
    bot_delivery_method_var.trace_add("write", refresh_tikfinity_direct_bridge)
    pump_log()
    if not sync_queue.empty():
        schedule_sync_queue_pump(0)
    if not ff_queue_sync_queue.empty():
        schedule_ff_queue_sync_pump(0)
    if chat_event_runtime_active() or not chat_event_queue.empty():
        schedule_chat_event_pump(0)
    if livepix_startup_work_needed():
        schedule_livepix_queue_pump(0)
    schedule_livepix_startup_tasks()
    if chat_commands_enabled_var.get() or chat_timers_enabled_var.get() or not bot_reply_queue.empty():
        schedule_bot_send_pump(0)
    if chat_timers_enabled_var.get():
        schedule_chat_timer_pump(0)
    if avatar_pending or not avatar_result_queue.empty():
        schedule_avatar_result_pump(0)
    if not ff_queue_site_sync_hidden:
        root.after(1400, lambda: fetch_ff_queue(force=False))
    if not ff_queue_site_sync_hidden:
        schedule_ff_queue_poll()
    root.after(STARTUP_IDLE_TASK_DELAY_MS, run_startup_ui_tasks)
    root.after(STARTUP_IDLE_TASK_DELAY_MS + 250, run_startup_runtime_tasks)
    root.after(STARTUP_MAINTENANCE_DELAY_MS, start_stale_pyinstaller_cleanup)
    log("Kills FF ativo em modo manual. Abas Fila FF, Overlay FF e Chat Ao Vivo seguem ocultas.")
    root.mainloop()
    return 0


def run_socket_diagnostic(output_path: Path) -> int:
    result: dict[str, Any] = {
        "app": APP_NAME,
        "version": APP_VERSION,
        "executable": sys.executable,
        "ok": False,
        "tests": [],
    }

    def record(name: str, ok: bool, detail: str = "") -> None:
        result["tests"].append({"name": name, "ok": ok, "detail": detail})

    try:
        addresses = socket.getaddrinfo("127.0.0.1", 21213)
        record("getaddrinfo", True, str(addresses[:1]))
    except Exception as exc:
        record("getaddrinfo", False, repr(exc))

    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.close()
        record("socket_create", True)
    except Exception as exc:
        record("socket_create", False, repr(exc))

    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 0))
        address = server_socket.getsockname()
        server_socket.close()
        record("socket_bind", True, str(address))
    except Exception as exc:
        record("socket_bind", False, repr(exc))

    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.settimeout(2)
        client_socket.connect(("127.0.0.1", 21213))
        client_socket.close()
        record("connect_tikfinity_21213", True)
    except Exception as exc:
        record("connect_tikfinity_21213", False, repr(exc))

    result["ok"] = all(bool(item.get("ok")) for item in result["tests"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


def probe_local_winsock() -> tuple[bool, str]:
    sockets: list[socket.socket] = []
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockets.append(test_socket)
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sockets.append(server_socket)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(("127.0.0.1", 0))
        return True, "ok"
    except Exception as exc:
        return False, repr(exc)
    finally:
        for sock in sockets:
            try:
                sock.close()
            except OSError:
                pass


def winsock_restart_marker_path() -> Path:
    return APP_DIR / "winsock_restart.json"


def read_winsock_restart_stage() -> int:
    try:
        data = json.loads(winsock_restart_marker_path().read_text(encoding="utf-8-sig"))
    except Exception:
        return 0
    if not isinstance(data, dict) or str(data.get("version") or "") != APP_VERSION:
        return 0
    try:
        return max(0, int(data.get("stage") or 0))
    except (TypeError, ValueError):
        return 0


def write_winsock_restart_stage(stage: int) -> None:
    try:
        winsock_restart_marker_path().write_text(
            json.dumps({"version": APP_VERSION, "stage": stage, "updated_at": datetime.now().isoformat(timespec="seconds")}),
            encoding="utf-8",
        )
    except OSError:
        pass


def clear_winsock_restart_stage() -> None:
    try:
        winsock_restart_marker_path().unlink(missing_ok=True)
    except OSError:
        pass


def maybe_relaunch_clean_for_winsock(config_path: Path) -> bool:
    if not IS_FROZEN or os.name != "nt":
        return False
    try:
        env_restart_stage = int(os.environ.get(WINSOCK_CLEAN_RESTART_ENV, "0") or "0")
    except ValueError:
        env_restart_stage = 0
    restart_stage = max(env_restart_stage, read_winsock_restart_stage())
    ok, detail = probe_local_winsock()
    if ok:
        if restart_stage:
            clear_winsock_restart_stage()
            write_update_log(f"Winsock OK apos relancamento limpo etapa {restart_stage}.")
        return False
    if not is_winsock_provider_error(detail):
        return False
    if restart_stage >= 2:
        write_update_log(
            f"Winsock ainda falhou apos {restart_stage} relancamentos limpos ({detail}); "
            "continuando para mostrar erro no app."
        )
        return False

    clean_env = clean_pyinstaller_subprocess_env()
    next_stage = restart_stage + 1
    write_winsock_restart_stage(next_stage)
    clean_env[WINSOCK_CLEAN_RESTART_ENV] = str(next_stage)
    launch_args = [sys.executable]
    default_config = config_path.resolve() == DEFAULT_CONFIG.resolve()
    if not default_config:
        launch_args.extend(["--config", str(config_path)])
    creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    try:
        if default_config:
            explorer = Path(os.environ.get("WINDIR", r"C:\Windows")) / "explorer.exe"
            subprocess.Popen(
                [str(explorer if explorer.exists() else "explorer.exe"), sys.executable],
                cwd=str(APP_DIR),
                creationflags=creationflags,
                close_fds=True,
            )
            launch_mode = "explorer"
        else:
            subprocess.Popen(
                launch_args,
                cwd=str(APP_DIR),
                env=clean_env,
                creationflags=creationflags,
                close_fds=True,
            )
            launch_mode = "ambiente limpo"
        write_update_log(
            f"Winsock falhou no processo atual ({detail}); "
            f"app relancado via {launch_mode} etapa {next_stage}."
        )
        return True
    except Exception as exc:
        write_update_log(f"Winsock falhou ({detail}) e o relancamento limpo tambem falhou: {exc}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Painel manual de kills do Free Fire e sorteios para live.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--image", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--watch", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gui", action="store_true", help="Abre a janela de configuracao.")
    parser.add_argument("--version", action="store_true", help="Mostra a versao do aplicativo e sai.")
    parser.add_argument("--dry-run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--debug", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--socket-diagnostic", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.version:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0

    if args.socket_diagnostic:
        return run_socket_diagnostic(args.socket_diagnostic)

    if args.image or args.watch:
        print("Captura automatica por print/OCR foi desativada. Use a interface de kills manuais.")
        return 2

    if maybe_relaunch_clean_for_winsock(args.config):
        return 0

    if maybe_apply_auto_update(args.config):
        return 0

    if args.gui or (not args.image and not args.watch):
        return run_gui(args.config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
