"""Пути, палитра МТС Exolve, хранение домена (JSON) и ключа (keyring)."""
import json
import os
import sys

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

KEYRING_SERVICE = "exolve_panel"

DEFAULT_RPS = 5
MIN_RPS = 1
MAX_RPS = 50


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def _config_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


APP_DIR = _base_dir()
ASSETS_DIR = os.path.join(APP_DIR, "assets")
CONFIG_FILE = os.path.join(_config_dir(), "vats_config.json")


def asset_path(filename: str) -> str:
    """Полный путь к файлу в assets/."""
    return os.path.join(ASSETS_DIR, filename)


# --- Палитра ---
RED_ACCENT = "#ff0033"
RED_HOVER = "#d6002b"
DARK_HEADER = "#111827"
BG_MAIN = "#f8fafc"
CARD_BG = "#ffffff"
TEXT_MAIN = "#0f172a"
TEXT_MUTED = "#64748b"
BORDER_COLOR = "#e2e8f0"

ROW_BG_NORMAL = "#f8fafc"
ROW_BG_SELECTED = "#e0f2fe"
ROW_BORDER_SELECTED = "#38bdf8"


# --- JSON-хелперы ---
def _load_json(path: str = CONFIG_FILE) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save_json(data: dict, path: str = CONFIG_FILE) -> None:
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Домен ---
def load_domain(path: str = CONFIG_FILE) -> str:
    return _load_json(path).get("domain", "") or ""


def save_domain(domain: str, path: str = CONFIG_FILE) -> None:
    data = _load_json(path)
    data["domain"] = domain
    _save_json(data, path)


# --- RPS ---
def load_rps(path: str = CONFIG_FILE) -> int:
    try:
        v = int(_load_json(path).get("rps", DEFAULT_RPS))
    except Exception:
        return DEFAULT_RPS
    return max(MIN_RPS, min(v, MAX_RPS))


def save_rps(rps: int, path: str = CONFIG_FILE) -> None:
    try:
        v = max(MIN_RPS, min(int(rps), MAX_RPS))
    except Exception:
        v = DEFAULT_RPS
    data = _load_json(path)
    data["rps"] = v
    _save_json(data, path)


# --- Ключ: Windows Credential Manager через keyring ---
def load_key(domain: str) -> str:
    if not domain or not KEYRING_AVAILABLE:
        return ""
    try:
        return keyring.get_password(KEYRING_SERVICE, domain) or ""
    except Exception:
        return ""


def save_key(domain: str, key: str) -> bool:
    if not domain or not KEYRING_AVAILABLE:
        return False
    try:
        keyring.set_password(KEYRING_SERVICE, domain, key)
        return True
    except Exception:
        return False


def delete_key(domain: str) -> None:
    if not domain or not KEYRING_AVAILABLE:
        return
    try:
        keyring.delete_password(KEYRING_SERVICE, domain)
    except Exception:
        pass


def keyring_available() -> bool:
    return KEYRING_AVAILABLE