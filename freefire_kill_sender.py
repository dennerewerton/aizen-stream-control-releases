from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import json
import os
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageGrab, ImageOps


IS_FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
ASSET_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
ROOT = APP_DIR
DEFAULT_CONFIG = APP_DIR / "config.json"
CONFIG_EXAMPLE = ASSET_DIR / "config.example.json"
OCR_SCRIPT = ASSET_DIR / "scripts" / "windows_ocr.ps1"


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


def save_config(path: Path, config: dict[str, Any]) -> None:
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


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
    text = re.sub(r"[^\wÀ-ÿ_.' @+-]", "", text, flags=re.UNICODE).strip(" -")

    normalized = text.casefold()
    for wrong, right in corrections.items():
        if normalized == wrong.casefold():
            return right
    return text


def normalize_player_key(name: str) -> str:
    name = re.sub(r"\s+", " ", name).strip().casefold()
    return name


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
    crop = image.crop(box).convert("RGB")
    resized = crop.resize((crop.width * 4, crop.height * 4), Image.Resampling.LANCZOS)
    resized_5x = crop.resize((crop.width * 5, crop.height * 5), Image.Resampling.LANCZOS)
    gray = ImageEnhance.Contrast(ImageOps.grayscale(resized)).enhance(2.0)
    bw = gray.point(lambda pixel: 0 if pixel < 140 else 255)
    return [("color", resized), ("color5x", resized_5x), ("gray", gray), ("bw", bw)]


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
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    cut = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    return cv2.resize(cut, (32, 48), interpolation=cv2.INTER_NEAREST)


def template_score(sample: np.ndarray, template: np.ndarray) -> float:
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
    # Variants are ordered by reliability for the sample UI: color, gray, then thresholded bw.
    for lines in candidate_lines:
        for line in lines:
            name = clean_name(line, corrections)
            if len(re.sub(r"[^\wÀ-ÿ]", "", name, flags=re.UNICODE)) >= 2:
                return name
    return fallback


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
    kill_mode = layout.get("kill_mode", "single_column")

    with tempfile.TemporaryDirectory(prefix="freefire_ocr_") as tmpdir:
        tmp_path = Path(tmpdir)
        ocr_paths: list[Path] = []
        slots: list[tuple[str, int, list[Path], tuple[int, int, int, int]]] = []

        for side_name, side in (("left", layout["left"]), ("right", layout["right"])):
            for row_index, row in enumerate(layout["rows"], start=1):
                y1, _ = row
                name_x1, name_x2 = side["name"]
                # OCR only the first name line; clan/title text below the nick is noise.
                name_box = scale_box(name_x1, y1, name_x2, y1 + name_height, image.size, reference_size)
                crop_paths = []
                for variant, name_crop in prepare_name_crops(image, name_box):
                    crop_path = tmp_path / f"{side_name}_{row_index}_name_{variant}.png"
                    name_crop.save(crop_path)
                    ocr_paths.append(crop_path)
                    crop_paths.append(crop_path)

                    if keep_debug:
                        debug_dir = ROOT / config.get("debug_dir", "debug")
                        debug_dir.mkdir(exist_ok=True)
                        name_crop.save(debug_dir / crop_path.name)

                slots.append((side_name, row_index, crop_paths, name_box))

        ocr_result = run_windows_ocr(ocr_paths)

        players: list[PlayerKill] = []
        for side_name, row_index, crop_paths, _ in slots:
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
                kills = read_kda_kills(image, kill_box, templates, separators)
            else:
                kills = read_kills(image, kill_box, templates)
            players.append(PlayerKill(name=name, kills=kills))

    return players


def format_message(players: list[PlayerKill], title: str) -> str:
    lines = [title, ""]
    lines.extend(f"({player.name}, {player.kills})" for player in players)
    return "\n".join(lines)


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
        return "https://" + endpoint_url[len("http://") :]
    return endpoint_url


def send_to_jarvis_endpoint(endpoint_url: str, content: str, players: list[PlayerKill]) -> str:
    payload = {
        "content": content,
        "players": [{"name": player.name, "kills": player.kills} for player in players],
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

    target = (capture_target or "primary").strip().lower()
    if target == "all":
        image = ImageGrab.grab(all_screens=True)
    elif target == "active_monitor":
        box = active_monitor_box()
        image = ImageGrab.grab(bbox=box) if box else ImageGrab.grab()
    elif target == "foreground":
        box = foreground_window_box()
        image = ImageGrab.grab(bbox=box) if box else ImageGrab.grab()
    else:
        image = ImageGrab.grab()

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


def run_gui(config_path: Path) -> int:
    import tkinter as tk
    from tkinter import messagebox, ttk

    config = load_config(config_path)
    log_queue: queue.Queue[str] = queue.Queue()
    worker: HotkeyWorker | None = None

    def log(message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        log_queue.put(f"[{stamp}] {message}")

    root = tk.Tk()
    root.title("Free Fire Kill Sender")
    root.geometry("720x520")
    root.minsize(680, 480)

    main = ttk.Frame(root, padding=14)
    main.pack(fill=tk.BOTH, expand=True)
    main.columnconfigure(1, weight=1)

    webhook_var = tk.StringVar(value=config.get("discord_webhook_url", ""))
    jarvis_var = tk.StringVar(value=config.get("jarvis_endpoint_url", ""))
    title_var = tk.StringVar(value=config.get("message_title", "Kills da partida"))
    attach_var = tk.BooleanVar(value=bool(config.get("attach_screenshot", True)))
    ignored_var = tk.StringVar(value=", ".join(parse_player_list(config.get("ignored_players", []))))
    capture_options = {
        "Monitor principal": "primary",
        "Monitor da janela ativa": "active_monitor",
        "Janela ativa": "foreground",
        "Todos os monitores": "all",
    }
    reverse_capture_options = {value: label for label, value in capture_options.items()}
    capture_target_var = tk.StringVar(
        value=reverse_capture_options.get(config.get("capture_target", "primary"), "Monitor principal")
    )

    hotkey = config.get("hotkey", "CTRL+SHIFT+F12").upper()
    hotkey_parts = set(re.split(r"[+\s]+", hotkey))
    ctrl_var = tk.BooleanVar(value="CTRL" in hotkey_parts or "CONTROL" in hotkey_parts)
    shift_var = tk.BooleanVar(value="SHIFT" in hotkey_parts)
    alt_var = tk.BooleanVar(value="ALT" in hotkey_parts)
    win_var = tk.BooleanVar(value="WIN" in hotkey_parts or "WINDOWS" in hotkey_parts)
    selected_key = next((part for part in hotkey_parts if part in VK_CODES and part not in MODIFIERS), "F12")
    key_var = tk.StringVar(value=selected_key)

    ttk.Label(main, text="Webhook Discord").grid(row=0, column=0, sticky="w", pady=4)
    ttk.Entry(main, textvariable=webhook_var).grid(row=0, column=1, columnspan=4, sticky="ew", pady=4)

    ttk.Label(main, text="Endpoint Jarvis").grid(row=1, column=0, sticky="w", pady=4)
    ttk.Entry(main, textvariable=jarvis_var).grid(row=1, column=1, columnspan=4, sticky="ew", pady=4)

    ttk.Label(main, text="Titulo").grid(row=2, column=0, sticky="w", pady=4)
    ttk.Entry(main, textvariable=title_var).grid(row=2, column=1, columnspan=4, sticky="ew", pady=4)

    ttk.Label(main, text="Atalho").grid(row=3, column=0, sticky="w", pady=8)
    ttk.Checkbutton(main, text="Ctrl", variable=ctrl_var).grid(row=3, column=1, sticky="w")
    ttk.Checkbutton(main, text="Shift", variable=shift_var).grid(row=3, column=2, sticky="w")
    ttk.Checkbutton(main, text="Alt", variable=alt_var).grid(row=3, column=3, sticky="w")
    ttk.Checkbutton(main, text="Win", variable=win_var).grid(row=3, column=4, sticky="w")

    key_values = [f"F{i}" for i in range(1, 25)] + [chr(i) for i in range(ord("A"), ord("Z") + 1)] + [str(i) for i in range(10)]
    ttk.Label(main, text="Tecla").grid(row=4, column=0, sticky="w", pady=4)
    ttk.Combobox(main, textvariable=key_var, values=key_values, state="readonly", width=12).grid(row=4, column=1, sticky="w", pady=4)
    ttk.Checkbutton(main, text="Anexar print na mensagem do Discord", variable=attach_var).grid(
        row=4, column=2, columnspan=3, sticky="w", pady=4
    )

    ttk.Label(main, text="Captura").grid(row=5, column=0, sticky="w", pady=4)
    ttk.Combobox(
        main,
        textvariable=capture_target_var,
        values=list(capture_options.keys()),
        state="readonly",
        width=20,
    ).grid(row=5, column=1, sticky="w", pady=4)

    ttk.Label(main, text="Ignorar jogadores").grid(row=6, column=0, sticky="w", pady=4)
    ttk.Entry(main, textvariable=ignored_var).grid(row=6, column=1, columnspan=4, sticky="ew", pady=4)

    status_var = tk.StringVar(value="Parado")
    ttk.Label(main, text="Status").grid(row=7, column=0, sticky="w", pady=4)
    ttk.Label(main, textvariable=status_var).grid(row=7, column=1, columnspan=4, sticky="w", pady=4)

    log_text = tk.Text(main, height=14, wrap="word")
    log_text.grid(row=9, column=0, columnspan=5, sticky="nsew", pady=(10, 0))
    main.rowconfigure(9, weight=1)

    def current_hotkey() -> str:
        parts = []
        if ctrl_var.get():
            parts.append("CTRL")
        if shift_var.get():
            parts.append("SHIFT")
        if alt_var.get():
            parts.append("ALT")
        if win_var.get():
            parts.append("WIN")
        parts.append(key_var.get())
        return "+".join(parts)

    def update_config_from_form() -> dict[str, Any]:
        config["discord_webhook_url"] = webhook_var.get().strip()
        config["jarvis_endpoint_url"] = normalize_endpoint_url(jarvis_var.get())
        jarvis_var.set(config["jarvis_endpoint_url"])
        config["message_title"] = title_var.get().strip() or "Kills da partida"
        config["attach_screenshot"] = bool(attach_var.get())
        config["capture_target"] = capture_options.get(capture_target_var.get(), "primary")
        config["ignored_players"] = parse_player_list(ignored_var.get())
        config["hotkey"] = current_hotkey()
        parse_hotkey(config["hotkey"])
        return config

    def save_form() -> None:
        try:
            save_config(config_path, update_config_from_form())
            log(f"Configuracao salva em {config_path}")
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def start_background() -> None:
        nonlocal worker
        try:
            if worker and worker.thread and worker.thread.is_alive():
                messagebox.showinfo("Rodando", "O monitor ja esta rodando em segundo plano.")
                return
            save_config(config_path, update_config_from_form())
            worker = HotkeyWorker(config, dry_run=False, keep_debug=False, log=log)
            worker.start()
            status_var.set(f"Rodando em segundo plano: {config['hotkey']}")
            log("Pode minimizar a janela. O atalho continua ativo enquanto o app estiver aberto.")
        except Exception as exc:
            messagebox.showerror("Erro", str(exc))

    def test_sample() -> None:
        sample = Path(r"C:\Users\Aizen\Pictures\BlueStacks\Screenshot_2026.06.14_16.58.09.454.png")
        if not sample.exists():
            messagebox.showerror("Erro", f"Imagem de teste nao encontrada:\n{sample}")
            return

        def run() -> None:
            try:
                local_config = update_config_from_form()
                process_image(sample, local_config, dry_run=True, keep_debug=False, log=log)
            except Exception as exc:
                log(f"Erro no teste: {exc}")

        threading.Thread(target=run, daemon=True).start()

    def hide_window() -> None:
        root.iconify()

    def close_app() -> None:
        root.destroy()

    buttons = ttk.Frame(main)
    buttons.grid(row=8, column=0, columnspan=5, sticky="ew", pady=8)
    ttk.Button(buttons, text="Salvar", command=save_form).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(buttons, text="Iniciar em segundo plano", command=start_background).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(buttons, text="Minimizar", command=hide_window).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(buttons, text="Testar com print exemplo", command=test_sample).pack(side=tk.LEFT, padx=(0, 8))
    ttk.Button(buttons, text="Sair", command=close_app).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", hide_window)

    def pump_log() -> None:
        while True:
            try:
                message = log_queue.get_nowait()
            except queue.Empty:
                break
            log_text.insert(tk.END, message + "\n")
            log_text.see(tk.END)
        root.after(150, pump_log)

    pump_log()
    log("Configure o atalho e clique em Iniciar em segundo plano.")
    root.mainloop()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Captura kills do Free Fire e envia para Discord.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--image", type=Path, help="Processa uma imagem salva em vez de capturar a tela.")
    parser.add_argument("--watch", action="store_true", help="Fica ouvindo o atalho global.")
    parser.add_argument("--gui", action="store_true", help="Abre a janela de configuracao.")
    parser.add_argument("--dry-run", action="store_true", help="Mostra o resultado sem enviar para o Discord.")
    parser.add_argument("--debug", action="store_true", help="Salva recortes usados pelo OCR em debug/.")
    args = parser.parse_args()

    if args.gui or (not args.image and not args.watch):
        return run_gui(args.config)

    config = load_config(args.config)
    if args.image:
        process_image(args.image, config, dry_run=args.dry_run, keep_debug=args.debug)
        return 0

    if args.watch or not args.image:
        hotkey_loop(config, dry_run=args.dry_run, keep_debug=args.debug)
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
