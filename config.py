import os
import sys
import json
import socket
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent

# Check if running in a Read-Only environment (e.g. Vercel Serverless / AWS Lambda /var/task)
IS_READ_ONLY_FS = False
if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or "/var/task" in str(BASE_DIR):
    IS_READ_ONLY_FS = True
else:
    try:
        test_dir = BASE_DIR / "data"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / ".write_test"
        test_file.touch()
        test_file.unlink()
    except (OSError, PermissionError):
        IS_READ_ONLY_FS = True

if IS_READ_ONLY_FS:
    DATA_DIR = Path("/tmp") / "data"
else:
    DATA_DIR = BASE_DIR / "data"

UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"
VOICE_BANK_DIR = DATA_DIR / "voice_bank"
TEMP_DIR = DATA_DIR / "temp"

for d in [DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, VOICE_BANK_DIR, TEMP_DIR]:
    try:
        d.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# If running in /tmp, seed voice_bank files and character configs from bundle
if IS_READ_ONLY_FS:
    src_vb = BASE_DIR / "data" / "voice_bank"
    if src_vb.exists():
        import shutil
        for item in src_vb.iterdir():
            target = VOICE_BANK_DIR / item.name
            if not target.exists():
                try:
                    if item.is_file():
                        shutil.copy2(item, target)
                except Exception:
                    pass

SETTINGS_FILE = DATA_DIR / "settings.json"

# Check if there is an existing Gemini API key from Panharith API Key folder
DEFAULT_GEMINI_KEY = ""
try:
    alt_settings = Path(r"D:\Panharith\App\Panharith API Key\settings.json")
    if alt_settings.exists():
        with open(alt_settings, "r", encoding="utf-8") as f:
            alt_data = json.load(f)
            DEFAULT_GEMINI_KEY = alt_data.get("gemini_api_key", "")
except Exception:
    pass

DEFAULT_SETTINGS = {
    "app_name": "SVA Clone Dubbing",
    "gemini_api_key": DEFAULT_GEMINI_KEY,
    "gemini_model": "gemini-3.8-flash",
    "tts_provider": "voxcpm", # "edge_tts" or "voxcpm"
    "voxcpm_endpoint": "https://openbmb-voxcpm-demo.hf.space",
    "voxcpm_space_id": "openbmb/VoxCPM-Demo",
    "hf_token": os.environ.get("HF_TOKEN", ""),
    "default_voice": "km-KH-PisethNeural",
    "dub_volume": 120,
    "bg_volume": 20,
    "mute_original": False,
    "use_bgm_only": True,
    "burn_subtitles": True,
    "subtitle_font_size": 22,
    "subtitle_color": "&H00FFFFFF",
    "subtitle_bg": True,
    "auto_speedup_dense": True,
    "speedup_percent": 25
}

def load_settings() -> dict:
    f_path = SETTINGS_FILE
    if not f_path.exists() and (BASE_DIR / "data" / "settings.json").exists():
        f_path = BASE_DIR / "data" / "settings.json"
    if f_path.exists():
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                saved = json.load(f)
                res = DEFAULT_SETTINGS.copy()
                res.update(saved)
                # If gemini key was empty in saved but available in alt_settings, fill it
                if not res.get("gemini_api_key") and DEFAULT_GEMINI_KEY:
                    res["gemini_api_key"] = DEFAULT_GEMINI_KEY
                return res
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()

def save_settings(data: dict):
    current = load_settings()
    current.update(data)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current

def get_local_ip() -> str:
    """Returns local LAN IP for phone access"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
