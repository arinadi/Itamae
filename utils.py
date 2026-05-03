from datetime import datetime
import asyncio
import time
import os
import config

# --- Logging Utilities (Merged from log_utils.py) ---

def get_runtime() -> str:
    """Formats total runtime since INIT_START as 'Xm XXs'."""
    elapsed = time.time() - config.INIT_START
    minutes, seconds = divmod(int(elapsed), 60)
    return f"{minutes}m {seconds:02d}s"

def log(category: str, message: str):
    """
    Print log with format: [HH:MM:SS] [+Runtime] [CATEGORY] message
    
    Categories: INIT, JOB, IDLE, WORKER, GEMINI, WHISPER, FILE, GRADIO, ERROR
    """
    timestamp = time.strftime("%H:%M:%S")
    runtime = get_runtime()
    print(f"[{timestamp}] [+{runtime}] [{category}] {message}")

# --- AI & Formatting Utilities ---

def build_journalist_summary_prompt(today_date: str, file_metadata: str | None = None) -> str:
    """Builder for the summarization prompt."""
    prompt = (
        "Anda adalah AI peringkas untuk jurnalis. "
        "Ringkas transkrip berikut ke dalam Bahasa Indonesia dengan format Plain Text.\n\n"
    )
    
    if file_metadata:
        prompt += (
            "INFORMASI METADATA FILE AUDIO (Sebagai Konteks Tambahan):\n"
            f"{file_metadata}\n\n"
        )
        
    prompt += (
        "ATURAN PENTING:\n"
        "- JANGAN mengarang atau berasumsi informasi yang tidak ada di transkrip.\n"
        "- Jika informasi tidak ditemukan, KOSONGKAN bagian tersebut atau tulis '-'.\n"
        "- Hanya tulis informasi yang JELAS terlihat di transkrip.\n"
        f"- Jika tanggal tidak disebutkan di transkrip, gunakan: {today_date}\n\n"
        "FORMAT OUTPUT:\n\n"
        "FAKTA BERITA\n"
        f"Tanggal: [tanggal dari transkrip atau {today_date}]\n\n"
        "LEAD (Paragraf Pembuka):\n"
        "[1-2 kalimat inti berita: siapa, apa, kapan, dimana]\n\n"
        "BODY:\n"
        "A. [Topik/Angle 1]\n"
        "   - Detail penting\n"
        "   - Kutipan pendukung (jika ada)\n\n"
        "B. [Topik/Angle 2]\n"
        "   - Detail penting\n\n"
        "C. [Topik/Angle 3, jika ada]\n"
        "   - Detail penting\n\n"
        "D. [Topik/Angle 4, jika ada]\n"
        "   - Detail penting\n\n"
        "NARASUMBER:\n"
        "1. [Nama] - [Jabatan] - \"[Kutipan kunci]\"\n"
        "(Kosongkan jika tidak ada narasumber jelas)\n\n"
        "DATA PENDUKUNG:\n"
        "- [Angka/statistik dari transkrip]\n"
        "(Kosongkan jika tidak ada data)\n\n"
        "PERLU KLARIFIKASI:\n"
        "- [Hal yang tidak jelas atau perlu dicek]\n"
        "(Kosongkan jika tidak ada)\n\n"
        "-----\n"
    )
    return prompt

async def summarize_text(transcript: str, gemini_client, mode: str = 'WHISPER') -> str:
    """Generates a journalist-friendly summary of the transcript using the Gemini API in Indonesian."""
    if not gemini_client:
        return "Summarization disabled: Gemini API key not configured or client failed to load."

    today_date = datetime.now().strftime("%d %B %Y")
    
    prompt = build_journalist_summary_prompt(today_date)


    # WHISPER mode: append RETOUCH TRANSCRIPT section
    if mode == 'WHISPER':
        prompt += (
            "\n\n"
            "-----\n\n"
            "RETOUCH TRANSCRIPT:\n"
            "! WARNING: Bagian ini adalah hasil perbaikan AI dan mengandung asumsi.\n\n"
            "[Perbaiki typo, kesalahan penulisan, serta tanda baca (seperti tanda tanya) pada transkrip. "
            "Berikan jeda baris (enter) di setiap akhir paragraf agar teks lebih mudah dibaca. "
            "Pastikan urutan kalimat dan struktur asli teks tetap sama.]\n\n"
            "--- TRANSKRIP ASLI [JANGAN KIRIM KEMBALI] ---\n"
            f"```\n{transcript}\n```"
        )
    
    # Gemini models
    PRIMARY_MODEL = "gemini-3-flash-preview"     # Use newer flash as primary
    FALLBACK_MODEL = "gemini-2.5-flash"

    # WHISPER: transcript already embedded in prompt (RETOUCH section)
    # GEMINI: pass transcript separately to avoid embedding it in the prompt
    contents = prompt if mode == 'WHISPER' else [prompt, transcript]
    
    try:
        log("GEMINI", f"Requesting summary ({len(transcript)} chars) with {PRIMARY_MODEL}...")
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model=PRIMARY_MODEL,
            contents=contents
        )
        log("GEMINI", f"Summary received ({len(response.text)} chars)")
        return response.text
    except Exception as e:
        log("ERROR", f"Gemini {PRIMARY_MODEL} failed: {e}")
        log("GEMINI", f"Retrying with fallback model {FALLBACK_MODEL}...")
        try:
            response = await asyncio.to_thread(
                gemini_client.models.generate_content,
                model=FALLBACK_MODEL,
                contents=contents
            )
            log("GEMINI", f"Fallback summary received ({len(response.text)} chars)")
            return response.text
        except Exception as fallback_error:
            log("ERROR", f"Gemini {FALLBACK_MODEL} also failed: {fallback_error}")
            return f"❌ Error generating summary: {fallback_error}"

def format_duration(seconds: float) -> str:
    """Converts a duration in seconds to a human-readable 'Xm XXs' format."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "N/A"
    minutes, remaining_seconds = divmod(int(seconds), 60)
    return f"{minutes}m {remaining_seconds:02d}s"

def format_timestamp(seconds: float, srt: bool = False) -> str:
    """Formats seconds into [HH:MM:SS] or SRT format HH:MM:SS,mmm."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return "00:00:00,000" if srt else "[00:00]"
    
    td = float(seconds)
    hours = int(td // 3600)
    minutes = int((td % 3600) // 60)
    secs = int(td % 60)
    millis = int((td - int(td)) * 1000)
    
    if srt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"{minutes:02d}:{secs:02d}"

def get_val(seg, key, default=0.0):
    """Helper to safely access attributes (handles dict vs object)."""
    if hasattr(seg, key):
        return getattr(seg, key)
    elif isinstance(seg, dict):
        return seg.get(key, default)
    return default

def format_transcription_native(segments: list) -> str:
    """Formats Whisper segments exactly as output by the model."""
    if not segments: return ""
    lines = []
    for seg in segments:
        text = str(get_val(seg, 'text', '')).strip()
        if not text: continue
        lines.append(f"{text}")
    return "\n\n".join(lines)

def format_transcription_srt(segments: list) -> str:
    """Formats Whisper segments into standard SRT format."""
    if not segments: return ""
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = get_val(seg, 'start', 0.0)
        end = get_val(seg, 'end', 0.0)
        text = str(get_val(seg, 'text', '')).strip()
        if not text: continue
        
        srt_lines.append(f"{i}")
        srt_lines.append(f"{format_timestamp(start, True)} --> {format_timestamp(end, True)}")
        srt_lines.append(f"{text}\n")
    return "\n".join(srt_lines)

async def transcribe_with_gemini(local_filepath: str, duration: float, gemini_client) -> tuple[str, str, list]:
    """Transcribes audio using Gemini API (File API). Returns text, lang, and empty segments (mock)."""
    if not gemini_client:
        return "Error: Gemini client not initialized.", "N/A", []

    try:
        log("GEMINI", f"Uploading {os.path.basename(local_filepath)}...")
        audio_file = await asyncio.to_thread(gemini_client.files.upload, file=local_filepath)
        
        while True:
            audio_file = await asyncio.to_thread(gemini_client.files.get, name=audio_file.name)
            if audio_file.state.name == "ACTIVE": break
            elif audio_file.state.name != "PROCESSING":
                raise Exception(f"File failed to process: {audio_file.state.name}")
            await asyncio.sleep(2)

        prompt = (
            "Transcribe this audio file accurately. Identify speakers. "
            "Output only the transcript. STRICT: Double newline (\\n\\n) after every sentence."
        )

        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model="gemini-2.5-flash",
            contents=[audio_file, prompt]
        )
        # Gemini cloud doesn't give precise segments like Whisper, so we return empty segments list
        return response.text, "ID", []
    except Exception as e:
        log("ERROR", f"Gemini transcription failed: {e}")
        return f"Error: {e}", "N/A", []

# --- Video Slicer & YouTube Utilities ---

async def fetch_video_metadata(url: str, use_bypass: bool = False) -> dict:
    """Fetches video metadata using yt-dlp with auto geo-bypass fallback."""
    import json
    cmd = ["yt-dlp", "--dump-json", "--no-playlist"]
    if use_bypass:
        cmd.append("--geo-bypass")
    cmd.append(url)
    
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_text = stderr.decode().lower()
            if not use_bypass and ("available in your country" in err_text or "geo-restricted" in err_text):
                log("FILE", "Geo-restriction detected. Retrying with --geo-bypass...")
                return await fetch_video_metadata(url, use_bypass=True)
                
            if "available in your country" in err_text:
                return {"error": "GEO_BLOCKED", "message": "Video is geo-restricted in the bot's region."}
            if "private video" in err_text:
                return {"error": "PRIVATE", "message": "Video is private."}
            if "not a valid url" in err_text:
                return {"error": "INVALID_URL", "message": "Invalid YouTube URL."}
            raise Exception(err_text)
            
        meta = json.loads(stdout.decode())
        return {
            "title": meta.get("title", "Unknown Video"),
            "duration": float(meta.get("duration", 0)),
            "thumbnail": meta.get("thumbnail"),
            "original_url": url
        }
    except Exception as e:
        log("ERROR", f"Failed to fetch metadata: {e}")
        return {"error": "UNKNOWN", "message": str(e)}

async def download_video_optimal(url: str, output_folder: str, use_bypass: bool = False) -> str:
    """Downloads video in optimal MKV 1080p format with geo-bypass fallback."""
    output_template = os.path.join(output_folder, "%(id)s.%(ext)s")
    cmd = ["yt-dlp", "-f", "bestvideo[height<=1080][ext=mkv]+bestaudio[ext=m4a]/best[height<=1080]", "--merge-output-format", "mkv", "-o", output_template]
    if use_bypass:
        cmd.append("--geo-bypass")
    cmd.append(url)
    
    try:
        log("FILE", f"Downloading video (Bypass={use_bypass}): {url}")
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            err_text = stderr.decode().lower()
            if not use_bypass and ("available in your country" in err_text or "geo-restricted" in err_text):
                log("FILE", "Geo-restriction during download. Retrying with --geo-bypass...")
                return await download_video_optimal(url, output_folder, use_bypass=True)
            raise Exception(err_text)
            
        for f in os.listdir(output_folder):
            if f.endswith((".mkv", ".mp4", ".webm")): return os.path.join(output_folder, f)
        return ""
    except Exception as e:
        log("ERROR", f"Download failed: {e}"); return ""

async def get_video_highlights_csv(transcript: str, gemini_client) -> list[dict]:
    """Uses Gemini to identify highlights and return them as a list of dicts with 'reason'."""
    if not gemini_client: return []
    system_prompt = (
        "You are a professional Social Media Viral Video Editor. "
        "Analyze the transcript and identify 3-5 high-impact highlights. "
        "For each, you can provide ONE or MORE segments to be stitched (Jump Cut). "
        "Return ONLY a CSV with headers: title,start,end,reason. "
        "In 'reason', write a very short label for the vibe: 'Funny', 'Profound', 'Action', 'Wise', 'Angry', or 'Reactive'. "
        "Duration per title: 10-30s."
    )
    try:
        log("GEMINI", "Analyzing highlights...")
        response = await asyncio.to_thread(gemini_client.models.generate_content, model="gemini-2.5-flash", contents=[system_prompt, transcript])
        csv_text = response.text.strip()
        import csv
        from io import StringIO
        if csv_text.startswith("```"): csv_text = "\n".join(csv_text.split("\n")[1:-1])
        reader = csv.DictReader(StringIO(csv_text))
        highlights = []
        for row in reader:
            try: highlights.append({
                "title": row["title"].strip(), 
                "start": float(row["start"]), 
                "end": float(row["end"]),
                "reason": row.get("reason", "Interesting").strip()
            })
            except: continue
        return highlights
    except Exception as e:
        log("ERROR", f"Highlight failed: {e}"); return []

async def slice_video_clip(input_path: str, start: float, end: float, output_path: str, target_size_mb: float = None):
    """Slices a video clip using FFmpeg with 1.25x speedup and silence removal."""
    buffered_start = max(0, start - 0.5)
    buffered_end = end + 0.5
    duration = (buffered_end - buffered_start) / 1.25
    filter_complex = "setpts=0.8*PTS,silenceremove=1:0:-50dB"
    
    cmd = ["ffmpeg", "-y", "-ss", str(buffered_start), "-to", str(buffered_end), "-i", input_path, "-vf", filter_complex, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path]
    
    if target_size_mb:
        target_bits = (target_size_mb * 8 * 1024 * 1024) * 0.9
        bitrate_kbps = int((target_bits / duration) / 1000)
        cmd = ["ffmpeg", "-y", "-ss", str(buffered_start), "-to", str(buffered_end), "-i", input_path, "-vf", filter_complex, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{bitrate_kbps}k", "-maxrate", f"{bitrate_kbps}k", "-bufsize", f"{bitrate_kbps*2}k", "-c:a", "aac", "-b:a", "128k", output_path]

    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate()
        return process.returncode == 0
    except Exception as e:
        log("ERROR", f"Clipping failed: {e}"); return False

async def concatenate_video_segments(segment_paths: list[str], output_path: str) -> bool:
    """Concatenates multiple segments into one final clip."""
    if not segment_paths: return False
    if len(segment_paths) == 1:
        import shutil; shutil.copy(segment_paths[0], output_path); return True
    
    v_a_inputs = "".join([f"[{i}:v][{i}:a]" for i in range(len(segment_paths))])
    filter_str = f"{v_a_inputs}concat=n={len(segment_paths)}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-y"] + [arg for p in segment_paths for arg in ("-i", p)] + ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate(); return process.returncode == 0
    except Exception as e:
        log("ERROR", f"Concat failed: {e}"); return False

async def send_video_adaptive(bot, chat_id: int, video_path: str, caption: str, reply_to_id: int = None):
    """Sends video to Telegram, auto-compressing if it hits size limits."""
    try:
        with open(video_path, 'rb') as f:
            await bot.send_video(chat_id, video=f, caption=caption, parse_mode="MARKDOWN", reply_to_message_id=reply_to_id)
        return True
    except Exception as e:
        err_msg = str(e).lower()
        if "file too large" in err_msg or "request entity too large" in err_msg:
            log("FILE", "Telegram rejected file size. Attempting adaptive compression...")
            actual_size_mb = os.path.getsize(video_path) / (1024 * 1024)
            compressed_path = video_path.replace(".mp4", "_compressed.mp4")
            cmd = ["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", compressed_path]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await process.communicate()
            if process.returncode == 0:
                with open(compressed_path, 'rb') as f:
                    await bot.send_video(chat_id, video=f, caption=f"{caption}\n_(Optimized for size)_", parse_mode="MARKDOWN", reply_to_message_id=reply_to_id)
                if os.path.exists(compressed_path): os.remove(compressed_path)
                return True
        log("ERROR", f"Failed to send video: {e}"); return False
