import os
import re
import subprocess
import requests
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional

def extract_audio(video_path: str, output_audio_path: str) -> bool:
    """Extracts audio from video file to 16kHz mono mp3 for fast transcription/analysis"""
    try:
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "libmp3lame",
            "-ar", "16000", "-ac", "1",
            "-b:a", "64k",
            output_audio_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return res.returncode == 0
    except Exception as e:
        print(f"Error extracting audio: {e}")
        return False

def get_media_duration_seconds(file_path: str) -> float:
    """Get media duration in seconds using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        return float(res.stdout.strip())
    except Exception:
        return 0.0

def seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to 00:00:00,000 format"""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def srt_time_to_seconds(time_str: str) -> float:
    """Convert 00:00:00,000 or 00:00:00.000 to float seconds"""
    try:
        clean = time_str.strip().replace(",", ".")
        parts = clean.split(":")
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        return float(parts[0])
    except Exception:
        return 0.0

def parse_srt_string(srt_text: str) -> List[Dict[str, Any]]:
    """Parses SRT content into a list of segment dictionaries"""
    # Normalize line breaks
    text = srt_text.replace("\r\n", "\n").replace("\r", "\n")
    # Pattern to match: index, timestamp line, and text
    pattern = re.compile(r"(\d+)\n(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3})\n([\s\S]*?)(?=\n{2,}|\Z)")
    
    matches = pattern.findall(text)
    segments = []
    
    for idx, (num, start_raw, end_raw, raw_sub_text) in enumerate(matches):
        sub_text = raw_sub_text.strip()
        # Detect character tag if any: e.g. [សំឡេងប្រុស], [hero_male], [Narrator]
        voice_id = "narrator_male"
        clean_text = sub_text
        
        tag_match = re.match(r"^\[(.*?)\]\s*(.*)", sub_text, re.DOTALL)
        if tag_match:
            tag = tag_match.group(1).strip()
            clean_text = tag_match.group(2).strip()
            if any(k in tag for k in ["ស្រី", "Female", "female", "heroine"]):
                voice_id = "heroine_female"
            elif any(k in tag for k in ["ប្រុស", "Male", "male", "hero"]):
                voice_id = "hero_male"
            elif any(k in tag for k in ["សម្រាយ", "narrator", "Narrator"]):
                voice_id = "narrator_male"
            elif any(k in tag for k in ["តា", "ចាស់", "old_man"]):
                voice_id = "old_man"
            elif any(k in tag for k in ["យាយ", "old_woman"]):
                voice_id = "old_woman"
            elif any(k in tag for k in ["ក្មេងប្រុស", "boy"]):
                voice_id = "boy"
            elif any(k in tag for k in ["ក្មេងស្រី", "girl"]):
                voice_id = "girl"
        # Remove AI artifacts like [span_...], <...>, etc.
        clean_text = re.sub(r"\[span[_\-\d\w]*\]", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", "", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
                
        start_norm = start_raw.replace(".", ",")
        end_norm = end_raw.replace(".", ",")
        
        segments.append({
            "index": idx,
            "start": start_norm,
            "end": end_norm,
            "start_sec": srt_time_to_seconds(start_norm),
            "end_sec": srt_time_to_seconds(end_norm),
            "text": clean_text,
            "voice": voice_id,
            "has_audio": False
        })
        
    return segments

def parse_raw_text(raw_text: str, total_duration_sec: float = 0.0) -> List[Dict[str, Any]]:
    """Converts pasted raw text into timed segments"""
    lines = [line.strip() for line in raw_text.replace("\r\n", "\n").split("\n") if line.strip()]
    if not lines:
        return []
        
    segments = []
    count = len(lines)
    
    # If total duration is provided and reasonable, distribute
    if total_duration_sec > 5.0 and total_duration_sec >= count * 1.5:
        interval = total_duration_sec / count
    else:
        interval = 3.5 # default 3.5s per line
        
    curr_time = 0.5
    for idx, line in enumerate(lines):
        voice_id = "narrator_male"
        clean_text = line
        
        # Check for tags like [សំឡេងស្រី]: អត្ថបទ... or តួស្រី: ...
        tag_match = re.match(r"^(\[.*?\]|[\u1780-\u17FF\w\s]+[:：])\s*(.*)", line)
        if tag_match:
            tag = tag_match.group(1).strip()
            rest = tag_match.group(2).strip()
            if rest:
                clean_text = rest
                if any(k in tag for k in ["ស្រី", "Female", "female", "heroine"]):
                    voice_id = "heroine_female"
                elif any(k in tag for k in ["ប្រុស", "Male", "male", "hero"]):
                    voice_id = "hero_male"
                elif any(k in tag for k in ["សម្រាយ", "narrator"]):
                    voice_id = "narrator_male"
                    
        # Remove AI artifacts like [span_...], <...>, etc.
        clean_text = re.sub(r"\[span[_\-\d\w]*\]", "", clean_text, flags=re.IGNORECASE)
        clean_text = re.sub(r"<[^>]+>", "", clean_text)
        clean_text = re.sub(r"\s+", " ", clean_text).strip()
                    
        # Estimate duration based on text length (Khmer characters)
        line_len = len(clean_text)
        duration = max(2.5, min(12.0, line_len * 0.12))
        
        start_sec = curr_time
        end_sec = curr_time + duration
        curr_time = end_sec + 0.3
        
        segments.append({
            "index": idx,
            "start": seconds_to_srt_time(start_sec),
            "end": seconds_to_srt_time(end_sec),
            "start_sec": start_sec,
            "end_sec": end_sec,
            "text": clean_text,
            "voice": voice_id,
            "has_audio": False
        })
        
    return segments

def segments_to_srt_string(segments: List[Dict[str, Any]]) -> str:
    """Exports segments back to standard SRT formatted text"""
    output = []
    for i, seg in enumerate(segments):
        start = seg.get("start", "00:00:00,000")
        end = seg.get("end", "00:00:02,000")
        text = seg.get("text", "")
        output.append(f"{i + 1}\n{start} --> {end}\n{text}\n")
    return "\n".join(output)

def transcribe_audio_with_gemini(
    audio_path: str, 
    api_key: str, 
    model_name: str = "gemini-2.5-flash",
    mode: str = "dubbing",
    progress_callback = None
) -> Optional[List[Dict[str, Any]]]:
    """Transcribes audio file to Khmer SRT segments using Google Gemini API"""
    if not api_key:
        raise ValueError("សូមបញ្ចូល Google Gemini API Key ក្នុង Settings ជាមុនសិន")
        
    if progress_callback:
        progress_callback(20, "កំពុងអានទិន្នន័យសំឡេង...")
        
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")
        
    if progress_callback:
        progress_callback(40, f"កំពុងបញ្ជូនទៅ Gemini ({model_name})...")
        
    if mode == "recap":
        prompt = (
            "You are a professional Khmer movie recap storyteller. "
            "Listen to this audio and produce a comprehensive Khmer recap/dubbing script in standard SRT subtitle format. "
            "Use timestamps (00:00:00,000 --> 00:00:00,000). "
            "Label narration lines with [សំឡេងអ្នកសម្រាយរឿង] or [សំឡេងអ្នកសម្រាយស្រី], and character dialogue with appropriate tags. "
            "Return ONLY valid SRT format inside code block (```srt ... ```)."
        )
    else:
        prompt = (
            "ចាប់ពីពេលនេះតទៅ សូមអ្នកដើរតួជា អ្នកបកប្រែខ្សែភាពយន្តនិងរឿងភាគអាជីព (Expert Subtitler & Dubbing Translator)។ "
            "ភារកិច្ចចម្បងរបស់អ្នកគឺទាញយកសំឡេងសន្ទនាពីសំឡេងនេះ មកជាភាសាខ្មែរឲ្យបានស្តង់ដារបំផុត ដោយផ្តោតសំខាន់លើ 'ភាសានិយាយ' ដែលរលូន ស៊ីអារម្មណ៍ និងត្រូវសំឡេងតួអង្គ ១០០%។\n"
            "សូមអនុវត្តតាមច្បាប់ទាំង ៥ នេះយ៉ាងតឹងរ៉ឹងបំផុត៖\n"
            "1. ភាសានិយាយធម្មជាតិ (Natural Spoken Language): ហាមដាច់ខាតការបកប្រែតាមបែបសរសេរស្ងួតៗ (Word-for-word)។ ត្រូវប្រើប្រាស់ពាក្យពេចន៍ដែលប្រជាជនខ្មែរនិយមនិយាយប្រចាំថ្ងៃ។ សូមប្រើកន្ទុយពាក្យបញ្ជាក់អារម្មណ៍ (ឧទាហរណ៍៖ ណា, ណ៎, ហ្មង, តើ, អញ្ចឹង, វើយ, ហាស, ចា៎, ចុះ) ឲ្យសក្ដិសមនឹងបរិបទសន្ទនា។\n"
            "2. វិភាគតួអង្គ និងបែងចែកស្លាកសំឡេងឱ្យត្រូវ ១០០% (Accurate Character & Voice Classification):\n"
            "វិភាគសំឡេង ដើម្បីបែងចែកតួអង្គ និងដាក់ស្លាកនៅដើមបន្ទាត់នីមួយៗឱ្យបានត្រឹមត្រូវបំផុត៖\n"
            "- [សំឡេងប្រុស] : បុរសពេញវ័យ (យុវជន, កម្លោះ, មនុស្សប្រុសវ័យធ្វើការ អាយុ ១៨-៥៩ ឆ្នាំ)\n"
            "- [សំឡេងស្រី] : នារីពេញវ័យ (យុវតី, នារីក្រមុំ, ស្ត្រីវ័យធ្វើការ អាយុ ១៨-៥៩ ឆ្នាំ)\n"
            "- [សំឡេងតាចាស់] : មនុស្សចាស់ប្រុស (លោកតា, ឪពុកចាស់, សក់ស្កូវ/ស ឬមានស្នាមជ្រីវជ្រួញ អាយុ ៦០ ឆ្នាំឡើងទៅ)\n"
            "- [សំឡេងយាយចាស់] : មនុស្សចាស់ស្រី (លោកយាយ, ម្ដាយចាស់, សក់ស្កូវ/ស ឬមានស្នាមជ្រីវជ្រួញ អាយុ ៦០ ឆ្នាំឡើងទៅ)\n"
            "- [សំឡេងក្មេងប្រុស] : កុមារា/កូនប្រុសតូច (អាយុក្រោម ១៥ ឆ្នាំ សំឡេងកូនក្មេងស្រួយស្រាល)\n"
            "- [សំឡេងក្មេងស្រី] : កុមារី/កូនស្រីតូច (អាយុក្រោម ១៥ ឆ្នាំ សំឡេងកូនក្មេងស្រួយស្រាល)\n"
            "- [សំឡេងគិតប្រុស] : ការគិតក្នុងចិត្តរបស់តួអង្គប្រុស (មាត់មិនកម្រើក តែមានសំឡេងបន្លឺឡើង)\n"
            "- [សំឡេងគិតស្រី] : ការគិតក្នុងចិត្តរបស់តួអង្គស្រី (មាត់មិនកម្រើក តែមានសំឡេងបន្លឺឡើង)\n"
            "- [សំឡេងអ្នកសម្រាយរឿង] : សំឡេងអ្នកនិទាន/សម្រាយរឿងប្រុស\n"
            "- [សំឡេងអ្នកសម្រាយស្រី] : សំឡេងអ្នកនិទាន/សម្រាយរឿងស្រី\n"
            "⚠️ ហាមដាច់ខាតច្រឡំមនុស្សចាស់ ឬកុមារតូច ទៅជាមនុស្សពេញវ័យធម្មតា! តួអង្គនីមួយៗត្រូវរក្សាស្លាកសំឡេងដដែលជាប់លាប់រហូត ហាមប្តូរសំឡេងធំតូចចុះឡើង។\n"
            "3. បញ្ចេញមនោសញ្ចេតនា (Emotional Depth): អានការបកប្រែរួច ត្រូវតែមានអារម្មណ៍ (ខឹង, សើច, យំ, ផ្អែមល្ហែម, ចំអក, ភ័យស្លន់ស្លោ) ដូចទៅនឹងអត្ថបទដើម។ បើអត្ថបទដើមមានន័យបង្កប់ ឬការលេងពាក្យ ត្រូវបត់បែនពាក្យខ្មែរឲ្យចេញន័យនោះដោយរលូន។\n"
            "4. ទម្រង់លទ្ធផល និង ថេរវេលា (Output Format & Timing): រាល់លទ្ធផលនៃការបកប្រែទាំងអស់ សូមផ្តល់ឲ្យខ្ញុំជាទម្រង់ហ្វាល SRT ដោយដាក់វានៅក្នុង Code Block (```srt ... ```)។ ថេរវេលា Start --> End ត្រូវតែស៊ីគ្នាជាក់លាក់ទៅនឹងពេលតួអង្គកំពុងនិយាយ។\n"
            "ត្រូវដាក់ស្លាកសំឡេងតួអង្គ [សំឡេង...] នៅដើមបន្ទាត់នីមួយៗជាដាច់ខាត (ឧទាហរណ៍៖ [សំឡេងតាចាស់] ឯងឆាប់ចេញពីផ្ទះខ្ញុំភ្លាមទៅ!)។\n"
            "5. ហាមកាត់ផ្ដាច់ប្រយោគ ឬបកប្រែពាក់កណ្ដាលប្រយោគជាដាច់ខាត (Translate Full & Complete Sentences - Zero Truncation): រាល់ប្រយោគដែលតួអង្គនិយាយ ត្រូវតែបកប្រែឱ្យចប់ចុងចប់ដើមពេញលេញ ១០០% ដោយមិនត្រូវកាត់ចោលកន្ទុយប្រយោគ មិនត្រូវកាត់ពាក្យចុងក្រោយ ឬសង្ខេបឡើយ។\n"
            "Return ONLY the valid SRT output inside code block (```srt ... ```), no other explanations."
        )
        
    # Model mapping and fallbacks
    models_to_try = [model_name]
    if model_name == "gemini-3.5-transcribe":
        models_to_try = ["gemini-3.5-transcribe", "gemini-3.8-flash", "gemini-3.5-flash"]
    elif model_name not in ["gemini-3.8-flash", "gemini-3.5-flash"]:
        models_to_try.extend(["gemini-3.8-flash", "gemini-3.5-flash"])

    res_data = None
    last_err = ""
    for current_model in models_to_try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{current_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "audio/mp3", "data": audio_b64}}
                ]
            }],
            "generationConfig": {
                "temperature": 0.2
            }
        }
        
        if progress_callback:
            progress_callback(60, f"Gemini ({current_model}) កំពុងសរសេរអក្សរ Subtitle ខ្មែរ...")
            
        resp = requests.post(endpoint, json=payload, timeout=180)
        if resp.status_code == 200:
            res_data = resp.json()
            break
        else:
            last_err = f"Gemini API Error {resp.status_code} ({current_model}): {resp.text}"
            print(f"Warning: {last_err}, trying next model if available...")

    if not res_data:
        raise RuntimeError(last_err)
    try:
        raw_output = res_data["candidates"][0]["content"]["parts"][0]["text"]
        # Clean any markdown code blocks ```srt ... ```
        clean_srt = re.sub(r"^```(?:srt)?\n?", "", raw_output.strip(), flags=re.MULTILINE)
        clean_srt = re.sub(r"\n?```$", "", clean_srt.strip())
        
        segments = parse_srt_string(clean_srt)
        if not segments:
            # Fallback to raw text parsing
            segments = parse_raw_text(clean_srt)
            
        if progress_callback:
            progress_callback(100, f"Transcribe ជោគជ័យ! បង្កើតបាន {len(segments)} បន្ទាត់")
            
        return segments
    except Exception as e:
        raise RuntimeError(f"Error parsing Gemini response: {e}")
