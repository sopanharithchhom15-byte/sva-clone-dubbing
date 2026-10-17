import os
import sys
import json
import time
import shutil
import asyncio
import traceback
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure UTF-8 console output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import (
    BASE_DIR, DATA_DIR, UPLOAD_DIR, OUTPUT_DIR, VOICE_BANK_DIR, TEMP_DIR,
    load_settings, save_settings, get_local_ip
)
from engine.voice_bank import (
    get_all_voices, save_custom_voice, delete_custom_voice,
    get_available_audio_samples, update_character_voice, reset_character_voice
)
from engine.transcriber import (
    extract_audio, get_media_duration_seconds, parse_srt_string,
    parse_raw_text, segments_to_srt_string, transcribe_audio_with_gemini
)
from engine.tts_engine import generate_segment_voice, generate_voice_preview
from engine.video_renderer import build_master_dub_track, create_ass_subtitles, render_dubbed_video
from engine.tunnel import start_tunnel, get_public_url, stop_tunnel

app = FastAPI(title="SVA Clone Dubbing", version="2.5.0")

@app.on_event("startup")
async def startup_event():
    is_cloud = bool(os.environ.get("PORT") or os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("IS_CLOUD"))
    if not is_cloud:
        port_to_tunnel = globals().get("ACTIVE_PORT", 8000)
        start_tunnel(port_to_tunnel)

@app.on_event("shutdown")
async def shutdown_event():
    stop_tunnel()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# In-memory session-isolated progress trackers
transcribe_states: Dict[str, Dict[str, Any]] = {}
tts_progress_states: Dict[str, Dict[str, Any]] = {}
render_progress_states: Dict[str, Dict[str, Any]] = {}

def get_transcribe_state(session_id: str) -> Dict[str, Any]:
    if session_id not in transcribe_states:
        transcribe_states[session_id] = {"is_running": False, "percent": 0, "message": "រួចរាល់"}
    return transcribe_states[session_id]

def get_tts_state(session_id: str) -> Dict[str, Any]:
    if session_id not in tts_progress_states:
        tts_progress_states[session_id] = {
            "is_running": False, "percent": 0, "current": 0, "total": 0,
            "active_index": -1, "message": "រួចរាល់"
        }
    return tts_progress_states[session_id]

def get_render_state(session_id: str) -> Dict[str, Any]:
    if session_id not in render_progress_states:
        render_progress_states[session_id] = {
            "is_running": False, "percent": 0, "message": "រួចរាល់",
            "video_ready": False, "video_url": "", "audio_url": ""
        }
    return render_progress_states[session_id]

def get_session_dir(session_id: str = "default") -> Path:
    sdir = DATA_DIR / "sessions" / session_id
    (sdir / "voices").mkdir(parents=True, exist_ok=True)
    return sdir

def load_session_state(sdir: Path) -> Dict[str, Any]:
    f = sdir / "state.json"
    if f.exists():
        try:
            with open(f, "r", encoding="utf-8") as fp:
                return json.load(fp)
        except Exception:
            pass
    return {
        "video_path": "",
        "video_name": "",
        "audio_path": "",
        "duration": 0.0,
        "subtitles": [],
        "has_master_dub": False,
        "has_rendered_video": False
    }

def save_session_state(sdir: Path, state: Dict[str, Any]):
    f = sdir / "state.json"
    with open(f, "w", encoding="utf-8") as fp:
        json.dump(state, fp, ensure_ascii=False, indent=2)

@app.get("/")
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return HTMLResponse("<h1>SVA Clone Dubbing Server Ready</h1>")

# Active server port
ACTIVE_PORT = 8000

@app.get("/api/network_info")
async def api_network_info():
    ip = get_local_ip()
    port = ACTIVE_PORT
    pub_url = get_public_url()
    effective_url = pub_url if pub_url else f"http://{ip}:{port}"
    return {
        "local_ip": ip,
        "port": port,
        "url": effective_url,
        "public_url": pub_url,
        "wifi_url": f"http://{ip}:{port}",
        "local_url": f"http://localhost:{port}",
        "is_online": bool(pub_url)
    }

@app.get("/api/settings")
async def api_get_settings():
    return load_settings()

@app.post("/api/settings")
async def api_save_settings(request: Request):
    data = await request.json()
    updated = save_settings(data)
    return JSONResponse({"success": True, "settings": updated})

@app.get("/api/voices")
async def api_get_voices():
    return get_all_voices()

@app.post("/api/voice_bank/upload")
async def api_voice_bank_upload(
    name: str = Form(...),
    voice_id: str = Form(...),
    prompt_text: str = Form(""),
    audio_file: UploadFile = File(...)
):
    safe_name = f"{int(time.time())}_{audio_file.filename}"
    target_path = VOICE_BANK_DIR / safe_name
    with open(target_path, "wb") as buffer:
        shutil.copyfileobj(audio_file.file, buffer)
        
    entry = save_custom_voice(voice_id, name, safe_name, prompt_text)
    return JSONResponse({"success": True, "voice": entry})

@app.delete("/api/voice_bank/{voice_id}")
async def api_voice_bank_delete(voice_id: str):
    success = delete_custom_voice(voice_id)
    return JSONResponse({"success": success})

@app.get("/api/voice_bank/samples")
async def api_voice_bank_samples():
    """Returns list of audio files in voice bank for cloning"""
    return get_available_audio_samples()

@app.get("/api/voice_bank/audio/{filename}")
async def api_voice_bank_audio(filename: str):
    f = VOICE_BANK_DIR / filename
    if f.exists():
        return FileResponse(str(f))
    raise HTTPException(status_code=404, detail="Audio file not found")

@app.post("/api/voice_bank/update_character")
async def api_voice_bank_update_character(
    char_id: str = Form(...),
    provider: str = Form(...),
    ref_audio: Optional[str] = Form(""),
    voice_code: Optional[str] = Form("km-KH-PisethNeural"),
    rate: Optional[str] = Form("+0%"),
    pitch: Optional[str] = Form("+0Hz"),
    audio_file: Optional[UploadFile] = File(None)
):
    selected_ref = ref_audio or ""
    # If a new audio file was uploaded for this character
    if audio_file and audio_file.filename:
        safe_name = f"{int(time.time())}_{audio_file.filename}"
        target_path = VOICE_BANK_DIR / safe_name
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)
        selected_ref = safe_name
        provider = "voxcpm"
        
    updated = update_character_voice(
        char_id=char_id,
        provider=provider,
        ref_audio=selected_ref,
        voice_code=voice_code or "km-KH-PisethNeural",
        rate=rate or "+0%",
        pitch=pitch or "+0Hz"
    )
    return JSONResponse({"success": True, "character": updated})

@app.post("/api/voice_bank/reset_character")
async def api_voice_bank_reset_character(request: Request):
    body = await request.json()
    char_id = body.get("char_id", "")
    success = reset_character_voice(char_id)
    return JSONResponse({"success": success})

@app.post("/api/voice_bank/preview")
async def api_voice_bank_preview(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
        
    char_id = body.get("char_id") or "narrator_male"
    sample_text = body.get("text", "សួស្តី នេះជាសំឡេងគំរូរបស់ខ្ញុំ")
    
    # Check for live overrides from modal
    override = None
    if body.get("provider"):
        override = {
            "id": char_id,
            "name": char_id,
            "provider": body.get("provider", "edge_tts"),
            "ref_audio": body.get("ref_audio", ""),
            "voice_code": body.get("voice_code", "km-KH-PisethNeural"),
            "rate": body.get("rate", "+0%"),
            "pitch": body.get("pitch", "+0Hz")
        }
        
    settings = load_settings()
    out_file = TEMP_DIR / f"preview_{char_id}.mp3"
    
    try:
        await generate_voice_preview(char_id, sample_text, str(out_file), settings, voice_config_override=override)
        return JSONResponse({
            "success": True,
            "audio_url": f"/api/voice_bank/preview_audio/{char_id}?t={int(time.time())}"
        })
    except Exception as e:
        print(f"Preview error: {traceback.format_exc()}")
        return JSONResponse({"success": False, "error": str(e)})

@app.get("/api/voice_bank/preview_audio/{char_id}")
async def api_get_preview_audio(char_id: str):
    out_file = TEMP_DIR / f"preview_{char_id}.mp3"
    if out_file.exists():
        return FileResponse(str(out_file), media_type="audio/mp3")
    raise HTTPException(status_code=404, detail="Preview not found")

@app.get("/api/session_state")
async def api_session_state(session_id: str = "default"):
    sdir = get_session_dir(session_id)
    return load_session_state(sdir)

@app.post("/api/upload_media")
async def api_upload_media(
    file: UploadFile = File(...),
    session_id: str = Form("default")
):
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    
    file_ext = Path(file.filename).suffix.lower()
    dest_file = sdir / f"input_media{file_ext}"
    
    with open(dest_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    duration = get_media_duration_seconds(str(dest_file))
    
    # Extract audio
    extracted_audio = sdir / "extracted_audio.mp3"
    extract_audio(str(dest_file), str(extracted_audio))
    
    state["video_path"] = str(dest_file)
    state["video_name"] = file.filename
    state["audio_path"] = str(extracted_audio)
    state["duration"] = duration
    save_session_state(sdir, state)
    
    return JSONResponse({
        "success": True,
        "filename": file.filename,
        "duration": duration,
        "media_url": f"/api/media/video?session_id={session_id}&t={int(time.time())}"
    })

@app.post("/api/upload_srt")
async def api_upload_srt(
    file: UploadFile = File(...),
    session_id: str = Form("default")
):
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    
    content = await file.read()
    srt_text = content.decode("utf-8", errors="replace")
    segments = parse_srt_string(srt_text)
    if not segments:
        segments = parse_raw_text(srt_text, state.get("duration", 0.0))
        
    state["subtitles"] = segments
    save_session_state(sdir, state)
    return JSONResponse({"success": True, "count": len(segments), "subtitles": segments})

@app.post("/api/parse_text")
async def api_parse_text(request: Request):
    try:
        body = await request.json()
        session_id = body.get("session_id", "default")
        raw_text = body.get("text", "")
        
        sdir = get_session_dir(session_id)
        state = load_session_state(sdir)
        
        # Try parsing as SRT first
        segments = parse_srt_string(raw_text)
        if not segments:
            # Fallback to smart raw text parser
            segments = parse_raw_text(raw_text, state.get("duration", 0.0))
            
        state["subtitles"] = segments
        save_session_state(sdir, state)
        return JSONResponse({"success": True, "count": len(segments), "subtitles": segments})
    except Exception as e:
        print(f"Error in api_parse_text: {e}")
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/update_subtitles")
async def api_update_subtitles(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    subtitles = body.get("subtitles", [])
    
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    state["subtitles"] = subtitles
    save_session_state(sdir, state)
    return JSONResponse({"success": True})

@app.post("/api/transcribe_ai")
async def api_transcribe_ai(request: Request, bg_tasks: BackgroundTasks):
    body = await request.json()
    session_id = body.get("session_id", "default")
    mode = body.get("mode", "dubbing")
    
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    
    audio_path = state.get("audio_path")
    if not audio_path or not Path(audio_path).exists():
        # Check if video exists and extract audio
        vpath = state.get("video_path")
        if vpath and Path(vpath).exists():
            extracted = sdir / "extracted_audio.mp3"
            extract_audio(vpath, str(extracted))
            state["audio_path"] = str(extracted)
            audio_path = str(extracted)
        else:
            return JSONResponse({"success": False, "error": "សូមបញ្ចូលវីដេអូ ឬសំឡេងជាមុនសិន!"}, status_code=400)
            
    settings = load_settings()
    api_key = settings.get("gemini_api_key", "").strip()
    if not api_key:
        return JSONResponse({"success": False, "error": "សូមបញ្ចូល Gemini API Key ក្នុងផ្ទាំង Settings ជាមុនសិន!"}, status_code=400)
        
    model_name = body.get("model") or settings.get("gemini_model", "gemini-3.8-flash")
    
    bg_tasks.add_task(run_transcribe_worker, sdir, audio_path, api_key, model_name, mode, session_id)
    return JSONResponse({"success": True, "message": "កំពុងចាប់ផ្តើម AI Transcribe..."})

def run_transcribe_worker(sdir: Path, audio_path: str, api_key: str, model_name: str, mode: str, session_id: str):
    prog = get_transcribe_state(session_id)
    prog["is_running"] = True
    prog["percent"] = 10
    prog["message"] = "កំពុងរៀបចំសំឡេង..."
    
    def on_prog(pct, msg):
        prog["percent"] = pct
        prog["message"] = msg
        
    try:
        segments = transcribe_audio_with_gemini(
            audio_path=audio_path,
            api_key=api_key,
            model_name=model_name,
            mode=mode,
            progress_callback=on_prog
        )
        if segments:
            state = load_session_state(sdir)
            state["subtitles"] = segments
            save_session_state(sdir, state)
            prog["is_running"] = False
            prog["percent"] = 100
            prog["message"] = f"ជោគជ័យ! បង្កើតបាន {len(segments)} បន្ទាត់!"
        else:
            prog["is_running"] = False
            prog["message"] = "មិនអាចបង្កើត Subtitle បានទេ"
    except Exception as e:
        prog["is_running"] = False
        prog["message"] = f"កំហុស: {str(e)}"
        print(f"Transcribe worker error: {traceback.format_exc()}")

@app.get("/api/transcribe_progress")
async def api_transcribe_progress(session_id: str = "default"):
    return JSONResponse(get_transcribe_state(session_id))

@app.post("/api/generate_voice_single")
async def api_generate_voice_single(request: Request):
    body = await request.json()
    session_id = body.get("session_id", "default")
    idx = body.get("index", 0)
    
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    subs = state.get("subtitles", [])
    if not (0 <= idx < len(subs)):
        raise HTTPException(status_code=400, detail="Invalid index")
        
    seg = subs[idx]
    if body.get("text"):
        seg["text"] = body["text"]
    if body.get("voice"):
        seg["voice"] = body["voice"]
        
    out_file = sdir / "voices" / f"voice_{idx}.mp3"
    settings = load_settings()
    
    try:
        await generate_segment_voice(seg, out_file, settings)
        seg["has_audio"] = True
        save_session_state(sdir, state)
        return JSONResponse({"success": True, "audio_url": f"/api/media/voice/{idx}?session_id={session_id}&t={int(time.time())}"})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@app.post("/api/generate_voice_batch")
async def api_generate_voice_batch(request: Request, bg_tasks: BackgroundTasks):
    body = await request.json()
    session_id = body.get("session_id", "default")
    force = body.get("force", False)
    
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    subs = state.get("subtitles", [])
    if not subs:
        return JSONResponse({"success": False, "error": "មិនទាន់មាន Subtitle សម្រាប់បង្កើតសំឡេងឡើយ!"}, status_code=400)
        
    pending = [i for i, s in enumerate(subs) if force or not s.get("has_audio")]
    if not pending:
        pending = list(range(len(subs)))
        
    bg_tasks.add_task(run_batch_tts_worker, sdir, subs, pending, session_id)
    return JSONResponse({"success": True, "total": len(pending)})

async def run_batch_tts_worker(sdir: Path, subs: List[Dict[str, Any]], indices: List[int], session_id: str):
    prog = get_tts_state(session_id)
    total = len(indices)
    prog.update({
        "is_running": True,
        "percent": 5,
        "current": 0,
        "total": total,
        "message": f"កំពុងចាប់ផ្តើមបង្កើតសំឡេង (០/{total})..."
    })
    
    settings = load_settings()
    vdir = sdir / "voices"
    
    for i, idx in enumerate(indices):
        seg = subs[idx]
        prog["active_index"] = idx
        prog["current"] = i + 1
        prog["percent"] = int(((i + 1) / total) * 95)
        prog["message"] = f"កំពុងអានបន្ទាត់ #{idx + 1}/{len(subs)} ({i+1}/{total}): {seg.get('text', '')[:25]}..."
        
        out_file = vdir / f"voice_{idx}.mp3"
        try:
            await generate_segment_voice(seg, out_file, settings)
            seg["has_audio"] = True
            # Short breathing interval to avoid HuggingFace queue saturation
            await asyncio.sleep(1.2)
        except Exception as e:
            print(f"Error TTS line {idx}: {e}")
            
    # Auto build master dub track
    state = load_session_state(sdir)
    state["subtitles"] = subs
    master_dub = sdir / "master_dub.mp3"
    build_master_dub_track(subs, vdir, master_dub, state.get("duration", 0.0))
    state["has_master_dub"] = True
    save_session_state(sdir, state)
    
    prog.update({
        "is_running": False,
        "percent": 100,
        "message": f"បង្កើតសំឡេងជោគជ័យគ្រប់បន្ទាត់ ({total} បន្ទាត់)!"
    })

@app.get("/api/tts_progress")
async def api_tts_progress(session_id: str = "default"):
    return JSONResponse(get_tts_state(session_id))

@app.post("/api/upload_logo")
async def api_upload_logo(
    file: UploadFile = File(...),
    session_id: str = Form("default")
):
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in [".png", ".jpg", ".jpeg", ".webp"]:
        return JSONResponse({"success": False, "error": "សូមជ្រើសរើសឯកសាររូបភាព (PNG, JPG, WEBP)"}, status_code=400)
        
    dest_file = sdir / f"logo_{int(time.time())}{file_ext}"
    with open(dest_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    state["logo_path"] = str(dest_file)
    state["logo_name"] = file.filename
    state["logo_url"] = f"/api/media/logo?session_id={session_id}&t={int(time.time())}"
    save_session_state(sdir, state)
    
    return JSONResponse({
        "success": True,
        "logo_url": state["logo_url"],
        "logo_name": file.filename
    })

@app.delete("/api/delete_logo")
async def api_delete_logo(session_id: str = "default"):
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    lpath = state.get("logo_path")
    if lpath and Path(lpath).exists():
        try:
            Path(lpath).unlink(missing_ok=True)
        except Exception:
            pass
    state.pop("logo_path", None)
    state.pop("logo_name", None)
    state.pop("logo_url", None)
    save_session_state(sdir, state)
    return JSONResponse({"success": True})

@app.post("/api/render_video")
async def api_render_video(request: Request, bg_tasks: BackgroundTasks):
    body = await request.json()
    session_id = body.get("session_id", "default")
    
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    
    video_path = state.get("video_path")
    if not video_path or not Path(video_path).exists():
        return JSONResponse({"success": False, "error": "សូមបញ្ចូលវីដេអូដើមជាមុនសិន!"}, status_code=400)
        
    settings = load_settings()
    # Override settings if provided in body
    dub_vol = body.get("dub_volume", settings.get("dub_volume", 120))
    bg_vol = body.get("bg_volume", settings.get("bg_volume", 20))
    mute_orig = body.get("mute_original", settings.get("mute_original", False))
    burn_subs = body.get("burn_subtitles", settings.get("burn_subtitles", True))
    effects = body.get("effects", {})
    
    # If logo enabled and no path specified, use saved logo_path
    if effects.get("logo", {}).get("enabled"):
        if not effects["logo"].get("path"):
            effects["logo"]["path"] = state.get("logo_path")
    
    bg_tasks.add_task(
        run_render_worker, sdir, video_path, state,
        dub_vol, bg_vol, mute_orig, burn_subs, effects, session_id
    )
    return JSONResponse({"success": True, "message": "កំពុងចាប់ផ្តើម Render វីដេអូ..."})

def run_render_worker(
    sdir: Path, video_path: str, state: Dict[str, Any],
    dub_vol: int, bg_vol: int, mute_orig: bool, burn_subs: bool,
    effects: Optional[Dict[str, Any]], session_id: str
):
    prog = get_render_state(session_id)
    prog.update({
        "is_running": True,
        "percent": 10,
        "message": "កំពុងរៀបចំឯកសារសំឡេង Master Dub...",
        "video_ready": False
    })
    
    subs = state.get("subtitles", [])
    vdir = sdir / "voices"
    master_dub = sdir / "master_dub.mp3"
    
    # Ensure master dub exists
    build_master_dub_track(subs, vdir, master_dub, state.get("duration", 0.0))
    
    # Generate ASS subtitles for hardcode if enabled
    ass_path = None
    if burn_subs and subs:
        ass_path = sdir / "subtitles.ass"
        create_ass_subtitles(subs, ass_path)
        
    out_video = sdir / "rendered_dubbed_video.mp4"
    
    def on_prog(pct, msg):
        prog["percent"] = pct
        prog["message"] = msg
        
    success = render_dubbed_video(
        video_path=video_path,
        master_dub_audio_path=str(master_dub) if master_dub.exists() else None,
        output_video_path=str(out_video),
        subtitle_ass_path=str(ass_path) if ass_path and ass_path.exists() else None,
        dub_volume_percent=dub_vol,
        bg_volume_percent=bg_vol,
        mute_original=mute_orig,
        burn_subtitles=burn_subs,
        effects=effects,
        progress_callback=on_prog
    )
    
    if success:
        state["has_rendered_video"] = True
        save_session_state(sdir, state)
        prog.update({
            "is_running": False,
            "percent": 100,
            "message": "Render វីដេអូជោគជ័យ ១០០%!",
            "video_ready": True,
            "video_url": f"/api/media/rendered_video?session_id={session_id}&t={int(time.time())}",
            "audio_url": f"/api/media/master_dub?session_id={session_id}&t={int(time.time())}"
        })
    else:
        prog.update({
            "is_running": False,
            "message": "Render វីដេអូបរាជ័យ សូមពិនិត្យ FFmpeg ឬវីដេអូដើម",
            "video_ready": False
        })

@app.get("/api/render_progress")
async def api_render_progress(session_id: str = "default"):
    return JSONResponse(get_render_state(session_id))

@app.post("/api/new_session")
async def api_new_session():
    new_id = f"user_{int(time.time())}_{os.urandom(3).hex()}"
    get_session_dir(new_id)
    return JSONResponse({"session_id": new_id})

@app.get("/api/media/{media_type}")
async def api_get_media(media_type: str, session_id: str = "default"):
    sdir = get_session_dir(session_id)
    if media_type == "video":
        state = load_session_state(sdir)
        vpath = state.get("video_path")
        if vpath and Path(vpath).exists():
            return FileResponse(vpath)
    elif media_type == "logo":
        state = load_session_state(sdir)
        lpath = state.get("logo_path")
        if lpath and Path(lpath).exists():
            return FileResponse(lpath)
    elif media_type == "master_dub":
        f = sdir / "master_dub.mp3"
        if f.exists():
            return FileResponse(str(f), media_type="audio/mp3", filename="master_dub.mp3")
    elif media_type == "rendered_video":
        f = sdir / "rendered_dubbed_video.mp4"
        if f.exists():
            return FileResponse(str(f), media_type="video/mp4", filename="rendered_dubbed_video.mp4")
            
    raise HTTPException(status_code=404, detail="Media not found")

@app.get("/api/media/voice/{index}")
async def api_get_voice_segment(index: int, session_id: str = "default"):
    sdir = get_session_dir(session_id)
    f = sdir / "voices" / f"voice_{index}.mp3"
    if f.exists():
        return FileResponse(str(f), media_type="audio/mp3")
    raise HTTPException(status_code=404, detail="Voice clip not found")

@app.get("/api/export_srt")
async def api_export_srt(session_id: str = "default"):
    sdir = get_session_dir(session_id)
    state = load_session_state(sdir)
    subs = state.get("subtitles", [])
    srt_content = segments_to_srt_string(subs)
    return HTMLResponse(
        content=srt_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=SVA_Dubbing_Subtitles.srt"}
    )

def find_available_port(default_port=8000):
    import socket
    for p in [default_port, 8080, 8050, 8090, 8888]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('127.0.0.1', p)) != 0:
                    return p
        except Exception:
            pass
    return default_port

if __name__ == "__main__":
    import threading
    import webbrowser
    env_port = os.environ.get("PORT")
    is_cloud = bool(env_port or os.environ.get("RENDER") or os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("IS_CLOUD"))
    
    if env_port:
        port = int(env_port)
    else:
        port = find_available_port(8000)
        
    ACTIVE_PORT = port
    local_ip = get_local_ip()
    print("=" * 60)
    print("  🎬 SVA Clone Dubbing - Mobile & Desktop AI Studio")
    print(f"  🌐 Server Port : {port}")
    if not is_cloud:
        print(f"  📱 Phone WiFi  : http://{local_ip}:{port}")
        print(f"  💻 Desktop URL : http://localhost:{port}")
        try:
            threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
        except Exception:
            pass
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=port)
