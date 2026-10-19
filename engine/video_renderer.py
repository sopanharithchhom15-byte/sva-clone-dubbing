import os
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydub import AudioSegment
from pydub.silence import detect_leading_silence
import time
from engine.transcriber import get_media_duration_seconds, srt_time_to_seconds

def trim_audio_silence(clip: AudioSegment, silence_thresh: int = -42, margin_ms: int = 30) -> AudioSegment:
    """Removes dead air / silence at the beginning and end of a TTS clip while keeping a natural margin."""
    if len(clip) < 100:
        return clip
    try:
        start_trim = detect_leading_silence(clip, silence_threshold=silence_thresh)
        reversed_clip = clip.reverse()
        end_trim = detect_leading_silence(reversed_clip, silence_threshold=silence_thresh)
        
        start_pos = max(0, start_trim - margin_ms)
        end_pos = max(0, end_trim - margin_ms)
        
        trimmed = clip[start_pos : len(clip) - end_pos]
        if len(trimmed) >= 80:
            return trimmed
        return clip
    except Exception:
        return clip

def build_master_dub_track(
    segments: List[Dict[str, Any]], 
    voice_files_dir: Path, 
    output_audio_path: Path, 
    total_duration_sec: float = 0.0
) -> bool:
    """
    Combines individual segment audio files into a single master audio track,
    positioning each voice clip at 100% exact SRT start timestamp.
    Applies silence trimming and smooth fade-out to prevent overlapping and audio cutoff.
    """
    try:
        # Determine total duration
        max_end_sec = 0.0
        for seg in segments:
            end_sec = seg.get("end_sec", 0.0)
            if not end_sec and seg.get("end"):
                end_sec = srt_time_to_seconds(seg["end"])
            if end_sec > max_end_sec:
                max_end_sec = end_sec
                
        final_duration_sec = max(total_duration_sec, max_end_sec + 2.0)
        total_duration_ms = int(final_duration_sec * 1000)
        
        positioned_clips = []
        for idx, seg in enumerate(segments):
            voice_file = voice_files_dir / f"voice_{idx}.mp3"
            if not voice_file.exists():
                voice_file = voice_files_dir / f"voice_{idx}.wav"
                
            if voice_file.exists():
                try:
                    clip = AudioSegment.from_file(str(voice_file))
                    
                    # 1. Clean up dead silence padding produced by TTS models
                    clip = trim_audio_silence(clip, silence_thresh=-42, margin_ms=25)
                    
                    # 2. Smooth 20ms fade-in
                    if len(clip) > 40:
                        clip = clip.fade_in(20)
                        
                    # 3. Exact 100% SRT timestamp alignment
                    start_sec = seg.get("start_sec", 0.0)
                    if not start_sec and seg.get("start"):
                        start_sec = srt_time_to_seconds(seg["start"])
                    target_start_ms = int(start_sec * 1000)
                    
                    # 4. Check next segment start time to prevent voice overlap
                    next_start_ms = None
                    for next_idx in range(idx + 1, len(segments)):
                        next_seg = segments[next_idx]
                        next_file_mp3 = voice_files_dir / f"voice_{next_idx}.mp3"
                        next_file_wav = voice_files_dir / f"voice_{next_idx}.wav"
                        if next_file_mp3.exists() or next_file_wav.exists() or next_seg.get("has_audio"):
                            n_start_sec = next_seg.get("start_sec", 0.0)
                            if not n_start_sec and next_seg.get("start"):
                                n_start_sec = srt_time_to_seconds(next_seg["start"])
                            next_start_ms = int(n_start_sec * 1000)
                            break
                            
                    # Avoid cutting off words at the end of segments
                    # Allow speech natural room so words finish completely without abrupt cuts
                    if next_start_ms is not None and next_start_ms > target_start_ms:
                        available_ms = next_start_ms - target_start_ms
                        overlap_ms = len(clip) - available_ms
                        # Only if speech substantially runs past the next segment start (> 500ms),
                        # allow up to 350ms natural bleed so ending syllables are preserved
                        if overlap_ms > 500 and available_ms > 600:
                            allowed_ms = available_ms + 350
                            if len(clip) > allowed_ms:
                                fade_ms = min(80, max(30, int(allowed_ms * 0.05)))
                                clip = clip[:allowed_ms].fade_out(fade_ms)
                        else:
                            if len(clip) > 40:
                                clip = clip.fade_out(25)
                    else:
                        # Natural trailing fade-out
                        if len(clip) > 40:
                            clip = clip.fade_out(25)
                            
                    positioned_clips.append((target_start_ms, clip))
                except Exception as clip_err:
                    print(f"Error loading clip {voice_file}: {clip_err}")
                    
        # Total duration needed for audio
        last_clip_end = max([pos + len(c) for pos, c in positioned_clips], default=0)
        needed_duration_ms = max(int(total_duration_sec * 1000), last_clip_end + 1000)
        master = AudioSegment.silent(duration=needed_duration_ms)
        
        for pos_ms, clip in positioned_clips:
            master = master.overlay(clip, position=pos_ms)
                    
        # Export master audio
        master.export(str(output_audio_path), format="mp3", bitrate="192k")
        return True
    except Exception as e:
        print(f"Error building master dub track: {e}")
        return False

def create_ass_subtitles(
    segments: List[Dict[str, Any]], 
    output_ass_path: Path, 
    font_name: str = "Khmer OS Battambang",
    font_size: int = 22,
    primary_color: str = "&H00FFFFFF",
    outline_color: str = "&H00000000"
) -> bool:
    """Generates an Advanced SubStation Alpha (.ass) subtitle file with styled Khmer typography"""
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size * 2},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,45,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    def to_ass_time(srt_time_str: str) -> str:
        # 00:00:00,000 -> 0:00:00.00
        clean = srt_time_str.strip().replace(",", ".")
        parts = clean.split(":")
        if len(parts) == 3:
            h = int(parts[0])
            m = parts[1]
            s_parts = parts[2].split(".")
            s = s_parts[0]
            cs = (s_parts[1][:2] if len(s_parts) > 1 else "00").ljust(2, "0")
            return f"{h}:{m}:{s}.{cs}"
        return clean

    events = []
    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        start_ass = to_ass_time(seg.get("start", "00:00:00,000"))
        end_ass = to_ass_time(seg.get("end", "00:00:02,000"))
        # Escape special ASS characters
        clean_ass_text = text.replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")
        events.append(f"Dialogue: 0,{start_ass},{end_ass},Default,,0,0,0,,{clean_ass_text}")
        
    content = header + "\n".join(events) + "\n"
    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.write(content)
    return True

def get_best_font_path() -> Optional[str]:
    """Finds available Khmer or standard font path on Windows and Linux/Docker for FFmpeg drawtext"""
    candidates = [
        # Windows font paths
        Path("C:/Windows/Fonts/KhmerOSbattambang.ttf"),
        Path("C:/Windows/Fonts/KhmerOS.ttf"),
        Path("C:/Windows/Fonts/KhmerOScontent.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("C:/Windows/Fonts/segoeui.ttf"),
        # Linux / Ubuntu / Docker font paths (fonts-khmeros)
        Path("/usr/share/fonts/truetype/khmeros/KhmerOSbattambang.ttf"),
        Path("/usr/share/fonts/truetype/khmeros/KhmerOS.ttf"),
        Path("/usr/share/fonts/truetype/khmeros/KhmerOScontent.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/freefont/FreeSans.ttf"),
        # Local app fonts if bundled
        Path(__file__).resolve().parent.parent / "static" / "fonts" / "KhmerOSbattambang.ttf"
    ]
    for c in candidates:
        if c.exists():
            return str(c.resolve()).replace("\\", "/").replace(":", "\\:")
    return None

def has_audio_stream(file_path: str) -> bool:
    """Checks if media file contains at least one audio stream"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "csv=p=0",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        return bool(res.stdout.strip())
    except Exception:
        return False

def render_dubbed_video(
    video_path: str,
    master_dub_audio_path: Optional[str],
    output_video_path: str,
    subtitle_ass_path: Optional[str] = None,
    dub_volume_percent: int = 120,
    bg_volume_percent: int = 20,
    mute_original: bool = False,
    burn_subtitles: bool = True,
    effects: Optional[Dict[str, Any]] = None,
    progress_callback = None,
    bgm_audio_path: Optional[str] = None,
    use_bgm_only: bool = True
) -> bool:
    """
    Renders the final dubbed video using FFmpeg:
    - Mixes dubbed voice and original audio or separated BGM (vocals removed)
    - Hardcodes styled subtitles if requested
    - Applies video effects: Blur, Flip, Add Text, Add Logo
    """
    temp_text_file = None
    try:
        if progress_callback:
            progress_callback(10, "កំពុងរៀបចំ Render វីដេអូ និង Effect...")
            
        cmd = ["ffmpeg", "-y", "-i", video_path]
        next_input_idx = 1
        
        orig_has_audio = has_audio_stream(video_path)
        has_dub = bool(master_dub_audio_path and os.path.exists(master_dub_audio_path))
        dub_input_idx = None
        if has_dub:
            cmd.extend(["-i", master_dub_audio_path])
            dub_input_idx = next_input_idx
            next_input_idx += 1

        # Check clean BGM input (speech removed)
        bgm_input_idx = None
        has_clean_bgm = bool(use_bgm_only and bgm_audio_path and os.path.exists(bgm_audio_path))
        if has_clean_bgm:
            cmd.extend(["-i", str(bgm_audio_path)])
            bgm_input_idx = next_input_idx
            next_input_idx += 1

        # Check logo overlay input
        effects = effects or {}
        logo_input_idx = None
        logo_cfg = effects.get("logo", {})
        logo_enabled = logo_cfg.get("enabled", False)
        logo_path = logo_cfg.get("path")
        if logo_enabled and logo_path and os.path.exists(str(logo_path)):
            cmd.extend(["-i", str(logo_path)])
            logo_input_idx = next_input_idx
            next_input_idx += 1
            
        # Audio filter
        dub_vol = dub_volume_percent / 100.0
        bg_vol = bg_volume_percent / 100.0
        filter_complex = []
        audio_map = None
        
        if has_dub:
            if mute_original:
                # Use only dubbed audio
                filter_complex.append(f"[{dub_input_idx}:a]volume={dub_vol}[aout]")
                audio_map = "[aout]"
            elif bgm_input_idx is not None:
                # Mix isolated BGM track (speech removed from original video) with dubbed speech
                filter_complex.append(
                    f"[{bgm_input_idx}:a]volume={bg_vol}[abgm];"
                    f"[{dub_input_idx}:a]volume={dub_vol}[adub];"
                    f"[adub][abgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                audio_map = "[aout]"
            elif orig_has_audio:
                # Mix original raw audio with dubbed speech
                filter_complex.append(
                    f"[0:a]volume={bg_vol}[aorig];"
                    f"[{dub_input_idx}:a]volume={dub_vol}[adub];"
                    f"[adub][aorig]amix=inputs=2:duration=first:dropout_transition=2[aout]"
                )
                audio_map = "[aout]"
            else:
                filter_complex.append(f"[{dub_input_idx}:a]volume={dub_vol}[aout]")
                audio_map = "[aout]"
        elif not mute_original:
            if bgm_input_idx is not None:
                filter_complex.append(f"[{bgm_input_idx}:a]volume={bg_vol}[aout]")
                audio_map = "[aout]"
            elif orig_has_audio:
                filter_complex.append("[0:a]volume=1.0[aout]")
                audio_map = "[aout]"
            
        # Video filters chain
        curr_v = "0:v"
        step_idx = 0
        
        # 1. Flip & Blur Effects
        base_v_filters = []
        flip_mode = effects.get("flip", "none")
        if flip_mode == "horizontal":
            base_v_filters.append("hflip")
        elif flip_mode == "vertical":
            base_v_filters.append("vflip")
        elif flip_mode == "both":
            base_v_filters.append("hflip,vflip")
            
        blur_cfg = effects.get("blur", {})
        if blur_cfg.get("enabled", False):
            strength = max(1, min(50, int(blur_cfg.get("strength", 5))))
            base_v_filters.append(f"boxblur={strength}:1")
            
        if base_v_filters:
            step_idx += 1
            next_v = f"v_step{step_idx}"
            filter_complex.append(f"[{curr_v}]{','.join(base_v_filters)}[{next_v}]")
            curr_v = next_v
            
        # 2. Subtitles burn-in
        if burn_subtitles and subtitle_ass_path and os.path.exists(subtitle_ass_path):
            escaped_sub_path = str(Path(subtitle_ass_path).resolve()).replace("\\", "/").replace(":", "\\:")
            step_idx += 1
            next_v = f"v_step{step_idx}"
            filter_complex.append(f"[{curr_v}]subtitles='{escaped_sub_path}'[{next_v}]")
            curr_v = next_v

        # 3. Logo overlay effect
        if logo_input_idx is not None:
            logo_w = max(20, min(1000, int(logo_cfg.get("width", 120))))
            logo_opacity = max(0.05, min(1.0, float(logo_cfg.get("opacity", 0.85))))
            logo_pos = logo_cfg.get("position", "top_right")
            pos_map = {
                "top_left": "30:30",
                "top_center": "(main_w-overlay_w)/2:30",
                "top_right": "main_w-overlay_w-30:30",
                "center": "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
                "bottom_left": "30:main_h-overlay_h-30",
                "bottom_center": "(main_w-overlay_w)/2:main_h-overlay_h-30",
                "bottom_right": "main_w-overlay_w-30:main_h-overlay_h-30"
            }
            xy = pos_map.get(logo_pos, "main_w-overlay_w-30:30")
            step_idx += 1
            logo_prep = f"logo_prep{step_idx}"
            filter_complex.append(f"[{logo_input_idx}:v]scale={logo_w}:-1,format=rgba,colorchannelmixer=aa={logo_opacity}[{logo_prep}]")
            next_v = f"v_step{step_idx}"
            filter_complex.append(f"[{curr_v}][{logo_prep}]overlay={xy}[{next_v}]")
            curr_v = next_v

        # 4. Text watermark effect
        text_cfg = effects.get("text", {})
        text_content = str(text_cfg.get("content", "")).strip()
        if text_cfg.get("enabled", False) and text_content:
            font_path = get_best_font_path()
            font_part = f"fontfile='{font_path}':" if font_path else ""
            font_size = max(12, min(150, int(text_cfg.get("font_size", 32))))
            font_color = str(text_cfg.get("color", "#FFFFFF")).replace("#", "0x")
            if not font_color.startswith("0x") and not font_color.isalpha():
                font_color = "white"
            box_enabled = 1 if text_cfg.get("box", True) else 0
            text_pos = text_cfg.get("position", "top_center")
            text_pos_map = {
                "top_left": "x=30:y=30",
                "top_center": "x=(w-text_w)/2:y=30",
                "top_right": "x=w-text_w-30:y=30",
                "center": "x=(w-text_w)/2:y=(h-text_h)/2",
                "bottom_left": "x=30:y=h-text_h-30",
                "bottom_center": "x=(w-text_w)/2:y=h-text_h-30",
                "bottom_right": "x=w-text_w-30:y=h-text_h-30"
            }
            xy_str = text_pos_map.get(text_pos, "x=(w-text_w)/2:y=30")
            
            parent_dir = Path(output_video_path).parent
            temp_text_file = parent_dir / f"watermark_text_{int(time.time())}.txt"
            with open(temp_text_file, "w", encoding="utf-8") as tf:
                tf.write(text_content)
            escaped_text_file = str(temp_text_file.resolve()).replace("\\", "/").replace(":", "\\:")
            
            step_idx += 1
            next_v = f"v_step{step_idx}"
            filter_complex.append(
                f"[{curr_v}]drawtext={font_part}textfile='{escaped_text_file}':fontsize={font_size}:fontcolor={font_color}:box={box_enabled}:boxcolor=black@0.6:boxborderw=8:{xy_str}[{next_v}]"
            )
            curr_v = next_v
            
        video_map = f"[{curr_v}]" if curr_v != "0:v" else "0:v"
        
        if filter_complex:
            cmd.extend(["-filter_complex", ";".join(filter_complex)])
            
        cmd.extend(["-map", video_map])
        if audio_map:
            cmd.extend([
                "-map", audio_map,
                "-c:a", "aac",
                "-b:a", "192k"
            ])
            
        cmd.extend([
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-movflags", "+faststart",
            output_video_path
        ])
        
        if progress_callback:
            progress_callback(30, "FFmpeg កំពុង Render វីដេអូ និងបញ្ចូលសំឡេង/Effect...")
            
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        stdout, stderr = proc.communicate()
        
        if proc.returncode != 0:
            err_text = stderr.encode("ascii", errors="replace").decode("ascii") if stderr else ""
            print(f"FFmpeg error: {err_text}")
            # Try fallback without subtitle filter if subtitle font failed
            if burn_subtitles and subtitle_ass_path:
                print("Retrying render without hardcoded subtitles...")
                return render_dubbed_video(
                    video_path=video_path,
                    master_dub_audio_path=master_dub_audio_path,
                    output_video_path=output_video_path,
                    subtitle_ass_path=None,
                    dub_volume_percent=dub_volume_percent,
                    bg_volume_percent=bg_volume_percent,
                    mute_original=mute_original,
                    burn_subtitles=False,
                    effects=effects,
                    progress_callback=progress_callback,
                    bgm_audio_path=bgm_audio_path,
                    use_bgm_only=use_bgm_only
                )
            return False
            
        if progress_callback:
            progress_callback(100, "Render វីដេអូជោគជ័យ ១០០%!")
            
        return True
    except Exception as e:
        print(f"Exception during video render: {e}")
        return False
    finally:
        if temp_text_file and temp_text_file.exists():
            try:
                temp_text_file.unlink(missing_ok=True)
            except Exception:
                pass

