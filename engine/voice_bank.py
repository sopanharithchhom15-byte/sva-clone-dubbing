import os
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from config import VOICE_BANK_DIR

DEFAULT_EDGE_CHARACTERS = [
    {
        "id": "narrator_male",
        "name": "🎙️ អ្នកសម្រាយរឿង (ប្រុស)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-PisethNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "ref_audio": ""
    },
    {
        "id": "narrator_female",
        "name": "🎙️ អ្នកសម្រាយរឿង (ស្រី)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "+0%",
        "pitch": "+0Hz",
        "ref_audio": ""
    },
    {
        "id": "hero_male",
        "name": "👨 តួប្រុស (Hero Adult)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-PisethNeural",
        "rate": "+3%",
        "pitch": "+2Hz",
        "ref_audio": ""
    },
    {
        "id": "heroine_female",
        "name": "👩 តួស្រី (Heroine Adult)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "+3%",
        "pitch": "+4Hz",
        "ref_audio": ""
    },
    {
        "id": "old_man",
        "name": "👴 តាចាស់ (Elderly Man)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-PisethNeural",
        "rate": "-15%",
        "pitch": "-10Hz",
        "ref_audio": ""
    },
    {
        "id": "old_woman",
        "name": "👵 យាយចាស់ (Elderly Woman)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "-15%",
        "pitch": "-8Hz",
        "ref_audio": ""
    },
    {
        "id": "boy",
        "name": "👦 ក្មេងប្រុស (Little Boy)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "+15%",
        "pitch": "+15Hz",
        "ref_audio": ""
    },
    {
        "id": "girl",
        "name": "👧 ក្មេងស្រី (Little Girl)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "+20%",
        "pitch": "+20Hz",
        "ref_audio": ""
    },
    {
        "id": "thought_male",
        "name": "💭 គិតក្នុងចិត្ត (ប្រុស)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-PisethNeural",
        "rate": "-5%",
        "pitch": "-5Hz",
        "ref_audio": ""
    },
    {
        "id": "thought_female",
        "name": "💭 គិតក្នុងចិត្ត (ស្រី)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "-5%",
        "pitch": "-3Hz",
        "ref_audio": ""
    },
    {
        "id": "drama_chinese_male",
        "name": "🏮 តួប្រុស (រឿងចិន)",
        "gender": "male",
        "provider": "edge_tts",
        "voice_code": "km-KH-PisethNeural",
        "rate": "+2%",
        "pitch": "+2Hz",
        "ref_audio": ""
    },
    {
        "id": "drama_chinese_female",
        "name": "🏮 តួស្រី (រឿងចិន)",
        "gender": "female",
        "provider": "edge_tts",
        "voice_code": "km-KH-SreymomNeural",
        "rate": "+3%",
        "pitch": "+4Hz",
        "ref_audio": ""
    }
]

CUSTOM_VOICES_FILE = VOICE_BANK_DIR / "custom_voices.json"
CHARACTER_OVERRIDES_FILE = VOICE_BANK_DIR / "character_overrides.json"

def get_character_overrides() -> Dict[str, Any]:
    if CHARACTER_OVERRIDES_FILE.exists():
        try:
            with open(CHARACTER_OVERRIDES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_character_overrides(overrides: Dict[str, Any]):
    with open(CHARACTER_OVERRIDES_FILE, "w", encoding="utf-8") as f:
        json.dump(overrides, f, ensure_ascii=False, indent=2)

def get_available_audio_samples() -> List[Dict[str, str]]:
    """Returns list of audio files available in the voice bank directory"""
    samples = []
    if VOICE_BANK_DIR.exists():
        for p in VOICE_BANK_DIR.iterdir():
            if p.is_file() and p.suffix.lower() in [".mp3", ".wav", ".m4a", ".ogg", ".aac"]:
                samples.append({
                    "filename": p.name,
                    "url": f"/api/voice_bank/audio/{p.name}"
                })
    return samples

def get_all_voices() -> List[Dict[str, Any]]:
    overrides = get_character_overrides()
    voices = []
    
    # Process default character presets with overrides applied
    for base in DEFAULT_EDGE_CHARACTERS:
        v = base.copy()
        char_id = v["id"]
        if char_id in overrides:
            ov = overrides[char_id]
            v.update(ov)
            v["is_customized"] = True
        else:
            v["is_customized"] = False
        voices.append(v)
        
    # Append custom created voices
    if CUSTOM_VOICES_FILE.exists():
        try:
            with open(CUSTOM_VOICES_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
                for cv in custom:
                    cv["is_custom_profile"] = True
                    voices.append(cv)
        except Exception:
            pass
            
    return voices

def update_character_voice(
    char_id: str,
    provider: str,
    ref_audio: str = "",
    voice_code: str = "km-KH-PisethNeural",
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> Dict[str, Any]:
    """Updates the voice provider and parameters for a specific character"""
    overrides = get_character_overrides()
    overrides[char_id] = {
        "provider": provider,
        "ref_audio": ref_audio,
        "voice_code": voice_code,
        "rate": rate,
        "pitch": pitch
    }
    save_character_overrides(overrides)
    
    # Return updated voice object
    all_v = get_all_voices()
    return next((v for v in all_v if v["id"] == char_id), overrides[char_id])

def reset_character_voice(char_id: str) -> bool:
    """Resets a character voice back to its default Edge-TTS settings"""
    overrides = get_character_overrides()
    if char_id in overrides:
        del overrides[char_id]
        save_character_overrides(overrides)
        return True
    return False

def save_custom_voice(voice_id: str, name: str, ref_audio_filename: str, prompt_text: str = ""):
    custom = []
    if CUSTOM_VOICES_FILE.exists():
        try:
            with open(CUSTOM_VOICES_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
        except Exception:
            custom = []
            
    existing = next((v for v in custom if v["id"] == voice_id), None)
    entry = {
        "id": voice_id,
        "name": name,
        "gender": "custom",
        "provider": "voxcpm",
        "ref_audio": ref_audio_filename,
        "prompt_text": prompt_text,
        "is_custom_profile": True
    }
    if existing:
        existing.update(entry)
    else:
        custom.append(entry)
        
    with open(CUSTOM_VOICES_FILE, "w", encoding="utf-8") as f:
        json.dump(custom, f, ensure_ascii=False, indent=2)
    return entry

def delete_custom_voice(voice_id: str):
    if not CUSTOM_VOICES_FILE.exists():
        return False
    try:
        with open(CUSTOM_VOICES_FILE, "r", encoding="utf-8") as f:
            custom = json.load(f)
        filtered = [v for v in custom if v["id"] != voice_id]
        with open(CUSTOM_VOICES_FILE, "w", encoding="utf-8") as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
