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
from engine.transcriber import get_media_duration_seconds, srt_time_to_seconds

async def generate_segment_voice(
    segment: Dict[str, Any], 
    output_file: Path, 
    settings: Dict[str, Any],
    voice_config_override: Optional[Dict[str, Any]] = None
) -> bool:
    """Generates voice for a single subtitle segment according to its assigned voice and settings"""
    voice_id = segment.get("voice", "narrator_male")
    vcfg = voice_config_override or find_voice_config(voice_id)
    text = segment.get("text", "").strip() or "..."
    
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
        # Call VoxCPM with automatic queue retry - never fall back to Piseth/Sreymom for cloned characters!
        await generate_voxcpm_tts(
            text=text,
            ref_audio_path=ref_audio_full,
            output_path=str(output_file),
            endpoint_url=endpoint,
            hf_token=token,
            max_retries=4
        )
        return True
    else:
        # Edge TTS (Only for characters configured for Edge TTS, not cloned characters)
        voice_code = vcfg.get("voice_code", "km-KH-PisethNeural")
        rate = vcfg.get("rate", "+0%")
        pitch = vcfg.get("pitch", "+0Hz")
        await generate_edge_tts(text, voice_code, rate, pitch, str(output_file))
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

