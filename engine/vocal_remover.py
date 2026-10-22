import os
import sys
import re
import time
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Callable, Dict, Any

# Ensure UTF-8 output encoding for Windows console to prevent charmap errors
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def extract_clean_audio_for_separation(media_path: str, output_wav_path: str) -> bool:
    """
    Extracts high-quality stereo 44.1kHz WAV from video or audio file for AI vocal separation.
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", media_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            output_wav_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        return res.returncode == 0 and os.path.exists(output_wav_path)
    except Exception as e:
        print(f"Error extracting audio for separation: {e}")
        return False

def _notify(cb: Optional[Callable[[int, str], None]], pct: int, msg: str):
    if cb:
        try:
            cb(pct, msg)
        except Exception:
            pass

def separate_with_ffmpeg(
    input_wav_path: str,
    output_bgm_path: str,
    output_vocals_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Fast, reliable, zero-RAM vocal and BGM separation using FFmpeg.
    - Isolates stereo BGM/instruments by eliminating center vocal channel.
    - Extracts center vocal track using bandpass + vocal center isolation.
    Guaranteed to run anywhere FFmpeg exists without heavy PyTorch or GPU requirements.
    """
    try:
        _notify(progress_callback, 30, "កំពុងដំណើរការកាត់សំឡេងនិយាយដោយ FFmpeg Filter...")

        # 1. Generate Clean BGM (Subdues center vocal frequencies ~300Hz-3400Hz while preserving stereo BGM & SFX)
        bgm_filter = "stereotools=mlev=0.04:slev=1.35,highpass=f=40,lowpass=f=18000"
        cmd_bgm = [
            "ffmpeg", "-y",
            "-i", input_wav_path,
            "-af", bgm_filter,
            "-acodec", "libmp3lame",
            "-b:a", "192k",
            output_bgm_path
        ]
        res_bgm = subprocess.run(cmd_bgm, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        
        _notify(progress_callback, 70, "កំពុងបំបែកសំឡេង Vocals...")

        # 2. Generate Isolated Vocals (Isolates center channel in speech frequency band)
        vox_filter = "stereotools=mlev=1.5:slev=0.05,bandpass=f=1600:w=2600"
        cmd_vox = [
            "ffmpeg", "-y",
            "-i", input_wav_path,
            "-af", vox_filter,
            "-acodec", "libmp3lame",
            "-b:a", "192k",
            output_vocals_path
        ]
        res_vox = subprocess.run(cmd_vox, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

        ok = res_bgm.returncode == 0 and os.path.exists(output_bgm_path)
        if ok:
            _notify(progress_callback, 100, "កាត់សំឡេងនិយាយ និងរក្សា BGM ជោគជ័យ ១០០%!")
        return ok
    except Exception as e:
        print(f"Error in separate_with_ffmpeg: {e}")
        return False

def separate_vocals_and_bgm(
    input_media_path: str,
    output_bgm_path: str,
    output_vocals_path: str,
    progress_callback: Optional[Callable[[int, str], None]] = None
) -> bool:
    """
    Separates speech/vocals and background music (BGM/Instrumental) from a video or audio file.
    Uses Demucs (htdemucs model, two-stems vocals) if available, with automatic
    seamless fallback to FFmpeg Smart Center-Channel Vocal Remover.
    
    Generates:
    - output_bgm_path: Clean BGM with speech removed (keeping music and sound effects)
    - output_vocals_path: Isolated vocals/speech track
    """
    temp_dir = Path(output_bgm_path).parent / f"temp_demucs_{int(time.time())}"
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    temp_wav = temp_dir / "input_audio.wav"
    demucs_out_dir = temp_dir / "demucs_out"
    demucs_out_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        _notify(progress_callback, 5, "កំពុងទាញយកសំឡេងពីវីដេអូដើម...")
            
        # 1. Extract 44.1kHz stereo audio
        ok = extract_clean_audio_for_separation(input_media_path, str(temp_wav))
        if not ok or not temp_wav.exists():
            _notify(progress_callback, 0, "បរាជ័យក្នុងការទាញយកសំឡេងពីវីដេអូ")
            return False
            
        # Check if Demucs is installed in current Python environment
        has_demucs = False
        try:
            import demucs
            has_demucs = True
        except ImportError:
            has_demucs = False

        if not has_demucs:
            print("Demucs not installed. Using FFmpeg Smart Center-Channel Vocal Separator.")
            return separate_with_ffmpeg(str(temp_wav), output_bgm_path, output_vocals_path, progress_callback)

        _notify(progress_callback, 15, "កំពុងចាប់ផ្តើម AI Demucs ដើម្បីកាត់សំឡេងនិយាយ...")
            
        # 2. Run Demucs CLI
        # Force UTF-8 environment to prevent Windows cp1252 charmap errors
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONLEGACYWINDOWSSTDIO"] = "utf-8"
        
        cmd = [
            sys.executable, "-m", "demucs.separate",
            "-n", "htdemucs",
            "--two-stems", "vocals",
            "-d", "cpu",
            "--mp3",
            "--mp3-bitrate", "192",
            "-o", str(demucs_out_dir),
            str(temp_wav)
        ]
        
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        
        # Read stderr line-by-line to parse progress
        pct_regex = re.compile(r"(\d+)%\|")
        last_pct = 15
        
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
                
            line_str = line.strip()
            if line_str:
                match = pct_regex.search(line_str)
                if match:
                    demucs_pct = int(match.group(1))
                    # Map demucs progress 0%-100% to overall 15%-92%
                    mapped_pct = int(15 + (demucs_pct * 0.77))
                    if mapped_pct != last_pct:
                        last_pct = mapped_pct
                        _notify(progress_callback, mapped_pct, f"AI កំពុងបំបែក BGM & សំឡេងនិយាយ... {demucs_pct}%")
                        
        proc.wait()
        
        if proc.returncode != 0:
            err_msg = proc.stderr.read() if proc.stderr else ""
            print(f"Demucs failed with code {proc.returncode}: {err_msg}. Falling back to FFmpeg vocal separator.")
            return separate_with_ffmpeg(str(temp_wav), output_bgm_path, output_vocals_path, progress_callback)
            
        _notify(progress_callback, 94, "កំពុងរៀបចំឯកសារ BGM និង Vocals...")
            
        # Look for output files in demucs_out/htdemucs/input_audio/
        track_folder = demucs_out_dir / "htdemucs" / "input_audio"
        gen_no_vocals = track_folder / "no_vocals.mp3"
        gen_vocals = track_folder / "vocals.mp3"
        
        if not gen_no_vocals.exists():
            # Check for wav format
            gen_no_vocals = track_folder / "no_vocals.wav"
            gen_vocals = track_folder / "vocals.wav"
            
        if not gen_no_vocals.exists():
            print("Demucs output files not found. Falling back to FFmpeg vocal separator.")
            return separate_with_ffmpeg(str(temp_wav), output_bgm_path, output_vocals_path, progress_callback)
            
        # Copy to target destinations
        shutil.copyfile(str(gen_no_vocals), str(output_bgm_path))
        if gen_vocals.exists():
            shutil.copyfile(str(gen_vocals), str(output_vocals_path))
            
        _notify(progress_callback, 100, "កាត់សំឡេងនិយាយចេញ និងរក្សា BGM ជោគជ័យ ១០០%!")
            
        return True
    except Exception as e:
        print(f"Exception during vocal separation: {e}. Falling back to FFmpeg vocal separator.")
        return separate_with_ffmpeg(str(temp_wav), output_bgm_path, output_vocals_path, progress_callback)
    finally:
        # Clean up temporary files
        try:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

def create_video_with_bgm_only(
    video_path: str,
    bgm_audio_path: str,
    output_video_path: str
) -> bool:
    """
    Muxes the original video stream with the isolated BGM audio stream
    (removing original vocals completely, keeping original video quality without re-encoding video).
    """
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", bgm_audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_video_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        return res.returncode == 0 and os.path.exists(output_video_path)
    except Exception as e:
        print(f"Error creating video with BGM only: {e}")
        return False
