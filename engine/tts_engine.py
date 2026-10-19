import os
import sys
import asyncio
import traceback

# Ensure UTF-8 output encoding for Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from pathlib import Path
from typing import Dict, Any, List, Optional
import edge_tts
from engine.voice_bank import get_all_voices
from config import VOICE_BANK_DIR

def find_voice_config(voice_id: str) -> Dict[str, Any]:
    all_voices = get_all_voices()
    for v in all_voices:
        if v["id"] == voice_id:
            return v
    # default narrator
    return all_voices[0]

async def generate_edge_tts(text: str, voice_code: str, rate: str, pitch: str, output_path: str):
    """Generate audio using Microsoft Edge TTS"""
    clean_text = text.strip() or "..."
    communicate = edge_tts.Communicate(clean_text, voice_code, rate=rate, pitch=pitch)
    await communicate.save(output_path)
    return True

VOXCPM_CLIENT = None
LAST_ENDPOINT = ""

def get_voxcpm_client(endpoint_url: str = "openbmb/VoxCPM-Demo", hf_token: str = ""):
    global VOXCPM_CLIENT, LAST_ENDPOINT
    clean_endpoint = (endpoint_url or "").strip()
    if "huggingface.co/spaces/" in clean_endpoint:
        clean_endpoint = clean_endpoint.split("huggingface.co/spaces/")[1].strip("/")
    if not clean_endpoint:
        clean_endpoint = "openbmb/VoxCPM-Demo"
        
    cache_key = f"{clean_endpoint}_{hf_token}"
    if VOXCPM_CLIENT is not None and LAST_ENDPOINT == cache_key:
        return VOXCPM_CLIENT
        
    from gradio_client import Client
    if hf_token:
        try:
            client = Client(clean_endpoint, token=hf_token)
        except TypeError:
            client = Client(clean_endpoint, hf_token=hf_token)
    else:
        client = Client(clean_endpoint)
        
    VOXCPM_CLIENT = client
    LAST_ENDPOINT = cache_key
    return client

async def generate_voxcpm_tts(
    text: str, 
    ref_audio_path: Optional[str], 
    output_path: str, 
    endpoint_url: str = "openbmb/VoxCPM-Demo",
    hf_token: str = "",
    max_retries: int = 4
):
    """
    Generate audio using VoxCPM (via Gradio Client connecting to openbmb/VoxCPM-Demo)
    with automatic retries and exponential backoff for queue congestion.
    """
    global VOXCPM_CLIENT
    from gradio_client import handle_file
    import shutil
    
    last_err = None
    for attempt in range(max_retries):
        try:
            client = get_voxcpm_client(endpoint_url, hf_token)
            ref_file = handle_file(ref_audio_path) if (ref_audio_path and os.path.exists(ref_audio_path)) else None
            
            loop = asyncio.get_event_loop()
            def _call_gradio():
                return client.predict(
                    text_input=text,
                    control_instruction="",
                    reference_wav_path_input=ref_file,
                    use_prompt_text=False,
                    prompt_text_input="",
                    cfg_value_input=2.0,
                    do_normalize=False,
                    denoise=False,
                    api_name="/generate"
                )
                
            result = await loop.run_in_executor(None, _call_gradio)
            
            if isinstance(result, (tuple, list)):
                res_file = result[0]
            else:
                res_file = result
                
            if res_file and os.path.exists(res_file):
                out_dir = os.path.dirname(output_path)
                if out_dir:
                    os.makedirs(out_dir, exist_ok=True)
                shutil.copy(res_file, output_path)
                return True
            else:
                raise RuntimeError(f"VoxCPM returned invalid file path: {result}")
        except Exception as e:
            last_err = e
            err_msg = str(e)
            print(f"VoxCPM attempt {attempt + 1}/{max_retries} error: {err_msg}")
            # Reset client cache on connection errors
            if "Connection" in err_msg or "timeout" in err_msg.lower() or "504" in err_msg:
                VOXCPM_CLIENT = None
            if attempt < max_retries - 1:
                wait_sec = 2.5 * (attempt + 1)
                print(f"Waiting {wait_sec}s for HuggingFace queue to clear before retry...")
                await asyncio.sleep(wait_sec)
                
    raise last_err

import subprocess
import re
import shutil
from engine.transcriber import get_media_duration_seconds, srt_time_to_seconds

def apply_audio_speedup(audio_path: str, speed_factor: float) -> bool:
    """
    Speeds up an audio file using FFmpeg's atempo filter without changing the pitch.
    Clamped safely to 1.05x - 1.38x to keep speech natural, clear, and easy to understand.
    """
    try:
        if speed_factor <= 1.01:
            return True
        clamped_speed = min(1.38, max(1.05, float(speed_factor)))
        p = Path(audio_path)
        temp_out = p.parent / f"speedup_tmp_{p.stem}{p.suffix}"
        
        cmd = [
            "ffmpeg", "-y", "-i", str(p),
            "-filter:a", f"atempo={clamped_speed:.3f}",
            "-vn", str(temp_out)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode == 0 and temp_out.exists() and temp_out.stat().st_size > 0:
            shutil.move(str(temp_out), str(p))
            return True
        else:
            if temp_out.exists():
                temp_out.unlink()
            return False
    except Exception as e:
        print(f"Error applying audio speedup to {audio_path}: {e}")
        return False

async def generate_segment_voice(
    segment: Dict[str, Any], 
    output_file: Path, 
    settings: Dict[str, Any],
    voice_config_override: Optional[Dict[str, Any]] = None
) -> bool:
    """Generates voice for a single subtitle segment according to its assigned voice and settings"""
    voice_id = segment.get("voice", "narrator_male")
    vcfg = voice_config_override or find_voice_config(voice_id)
    raw_text = segment.get("text", "").strip() or "..."
    
    # Clean bracketed speaker tags/sound effects so TTS doesn't vocalize them
    clean_text = re.sub(r'\[.*?\]|\(.*?\)', '', raw_text).strip()
    if not clean_text:
        clean_text = raw_text

    # Calculate allocated slot duration from timestamps
    start_sec = segment.get("start_sec", 0.0)
    if not start_sec and segment.get("start"):
        start_sec = srt_time_to_seconds(segment["start"])
        
    end_sec = segment.get("end_sec", 0.0)
    if not end_sec and segment.get("end"):
        end_sec = srt_time_to_seconds(segment["end"])
        
    slot_sec = (end_sec - start_sec) if (end_sec > start_sec) else 0.0
    
    # Calculate density: Khmer characters per second
    # Standard speech ~8-11 char/sec. If > 12 chars/sec, text is dense for this slot
    char_count = len(clean_text.replace(" ", ""))
    dense_rate_bonus = 0
    if slot_sec > 0.5 and char_count > 0:
        chars_per_sec = char_count / slot_sec
        if chars_per_sec > 13:
            dense_rate_bonus = 15
        elif chars_per_sec > 10.5:
            dense_rate_bonus = 10

    provider = vcfg.get("provider", "edge_tts")
    
    # If the character itself has a custom ref_audio in voice_bank, use VoxCPM
    ref_audio_name = vcfg.get("ref_audio")
    ref_audio_full = None
    if ref_audio_name:
        ref_path = VOICE_BANK_DIR / ref_audio_name
        if ref_path.exists():
            ref_audio_full = str(ref_path)
            provider = "voxcpm"
            
    if provider == "voxcpm" and ref_audio_full:
        endpoint = settings.get("voxcpm_space_id") or settings.get("voxcpm_endpoint", "openbmb/VoxCPM-Demo")
        token = settings.get("hf_token", "")
        # Call VoxCPM with automatic queue retry
        await generate_voxcpm_tts(
            text=clean_text,
            ref_audio_path=ref_audio_full,
            output_path=str(output_file),
            endpoint_url=endpoint,
            hf_token=token,
            max_retries=4
        )
    else:
        # Edge TTS (Only for characters configured for Edge TTS, not cloned characters)
        voice_code = vcfg.get("voice_code", "km-KH-PisethNeural")
        rate_str = vcfg.get("rate", "+0%")
        # For dense segments with default rate, give slight initial rate boost (+10% to +15%)
        if dense_rate_bonus > 0 and (rate_str == "+0%" or not rate_str):
            rate_str = f"+{dense_rate_bonus}%"
        pitch = vcfg.get("pitch", "+0Hz")
        await generate_edge_tts(clean_text, voice_code, rate_str, pitch, str(output_file))

    # Dynamic post-generation duration adjustment:
    # If the generated speech exceeds the subtitle time slot, speed it up smoothly
    # without cutting off words or changing voice pitch
    if output_file.exists() and slot_sec > 0.5:
        actual_duration = get_media_duration_seconds(str(output_file))
        if actual_duration > (slot_sec + 0.15):
            needed_speed = round(actual_duration / slot_sec, 2)
            target_speed = min(1.35, max(1.05, needed_speed))
            if target_speed >= 1.05:
                print(f"[TTS tempo] Segment duration {actual_duration:.2f}s > slot {slot_sec:.2f}s. Applying dynamic atempo={target_speed}x")
                apply_audio_speedup(str(output_file), target_speed)

    return True

async def generate_voice_preview(
    voice_id: str, 
    sample_text: str, 
    output_path: str, 
    settings: Dict[str, Any],
    voice_config_override: Optional[Dict[str, Any]] = None
):
    """Generates a short audio preview for testing any character voice or clone"""
    text = sample_text or "សួស្តី នេះជាសំឡេងគំរូរបស់ខ្ញុំ"
    seg = {"voice": voice_id, "text": text}
    return await generate_segment_voice(seg, Path(output_path), settings, voice_config_override=voice_config_override)

