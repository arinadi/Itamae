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

# Gemini model definitions (TTB Standard)
PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-2.5-flash"

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
    """Generates a summary with TTB-style 3 -> 2.5 fallback."""
    if not gemini_client: return "Summarization disabled."

    today_date = datetime.now().strftime("%d %B %Y")
    prompt = build_journalist_summary_prompt(today_date)
    contents = [prompt, transcript]
    
    try:
        log("GEMINI", f"Requesting summary with {PRIMARY_MODEL}...")
        response = await asyncio.to_thread(gemini_client.models.generate_content, model=PRIMARY_MODEL, contents=contents)
        return response.text
    except Exception as e:
        log("ERROR", f"{PRIMARY_MODEL} summary failed: {e}")
        log("GEMINI", f"Retrying with {FALLBACK_MODEL}...")
        try:
            response = await asyncio.to_thread(gemini_client.models.generate_content, model=FALLBACK_MODEL, contents=contents)
            return response.text
        except Exception as fe:
            log("ERROR", f"{FALLBACK_MODEL} summary failed: {fe}")
            return f"❌ Error: {fe}"

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
    td = float(seconds); hours = int(td // 3600); minutes = int((td % 3600) // 60); secs = int(td % 60); millis = int((td - int(td)) * 1000)
    if srt: return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    if hours > 0: return f"[{hours:02d}:{minutes:02d}:{secs:02d}]"
    return f"{minutes:02d}:{secs:02d}"

def get_val(seg, key, default=0.0):
    if hasattr(seg, key): return getattr(seg, key)
    elif isinstance(seg, dict): return seg.get(key, default)
    return default

def format_transcription_native(segments: list) -> str:
    if not segments: return ""
    lines = []
    for seg in segments:
        text = str(get_val(seg, 'text', '')).strip()
        if text: lines.append(text)
    return "\n\n".join(lines)

def format_transcription_srt(segments: list) -> str:
    if not segments: return ""
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start = get_val(seg, 'start', 0.0); end = get_val(seg, 'end', 0.0); text = str(get_val(seg, 'text', '')).strip()
        if not text: continue
        srt_lines.append(f"{i}"); srt_lines.append(f"{format_timestamp(start, True)} --> {format_timestamp(end, True)}"); srt_lines.append(f"{text}\n")
    return "\n".join(srt_lines)

async def transcribe_with_gemini(local_filepath: str, duration: float, gemini_client) -> tuple[str, str, list]:
    if not gemini_client: return "Error: Gemini client not initialized.", "N/A", []
    try:
        log("GEMINI", f"Uploading {os.path.basename(local_filepath)}...")
        audio_file = await asyncio.to_thread(gemini_client.files.upload, file=local_filepath)
        while True:
            audio_file = await asyncio.to_thread(gemini_client.files.get, name=audio_file.name)
            if audio_file.state.name == "ACTIVE": break
            elif audio_file.state.name != "PROCESSING": raise Exception(f"File failed: {audio_file.state.name}")
            await asyncio.sleep(2)
        prompt = "Transcribe this accurately. STRICT: Double newline after every sentence."
        response = await asyncio.to_thread(gemini_client.models.generate_content, model=FALLBACK_MODEL, contents=[audio_file, prompt])
        return response.text, "ID", []
    except Exception as e:
        log("ERROR", f"Gemini transcription failed: {e}"); return f"Error: {e}", "N/A", []

# --- Video Slicer & YouTube Utilities ---

async def fetch_video_metadata(url: str) -> dict:
    """Fast fetch video metadata using yt-dlp --print."""
    cmd = ["yt-dlp", "--no-playlist", "--geo-bypass", "--no-check-certificates", "--quiet", "--no-warnings", "--print", "%(title)s|||%(duration)s|||%(thumbnail)s", url]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            err_text = stderr.decode().lower()
            if "available in your country" in err_text: return {"error": "GEO_BLOCKED"}
            return {"error": "FAILED"}
        output = stdout.decode().strip()
        if "|||" not in output: return {"error": "INVALID"}
        parts = output.split("|||")
        return {"title": parts[0].strip() or "Video", "duration": float(parts[1]) if parts[1] else 0.0, "thumbnail": parts[2].strip() if len(parts) > 2 else None, "original_url": url}
    except Exception as e: log("ERROR", f"Lean fetch failed: {e}"); return {"error": "UNKNOWN"}

async def download_video_optimal(url: str, output_folder: str, job_id: str, use_bypass: bool = True) -> str:
    output_template = os.path.join(output_folder, f"{job_id}.%(ext)s")
    cmd = ["yt-dlp", "-f", "bestvideo[height<=1080][ext=mkv]+bestaudio[ext=m4a]/best[height<=1080]", "--merge-output-format", "mkv", "-o", output_template, "--print", "after_move:filepath"]
    if use_bypass: cmd.append("--geo-bypass")
    cmd.append(url)
    try:
        log("FILE", f"Downloading: {url}")
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, _ = await process.communicate()
        final_path = stdout.decode().strip()
        if final_path and os.path.exists(final_path): return final_path
        for f in os.listdir(output_folder):
            if f.startswith(job_id) and f.endswith((".mkv", ".mp4", ".webm")): return os.path.join(output_folder, f)
        return ""
    except Exception as e: log("ERROR", f"Download failed: {e}"); return ""

async def get_video_highlights_csv(transcript: str, gemini_client) -> list[dict]:
    """Identifies highlights with TTB-style 3 -> 2.5 fallback and robust CSV parsing."""
    if not gemini_client: return []
    system_prompt = (
        "You are a professional Social Media Viral Video Editor. "
        "Analyze the transcript and identify 3-5 high-impact highlights. "
        "For each, you can provide ONE or MORE segments to be stitched (Jump Cut). "
        "Return ONLY a CSV with headers: title,start,end,reason. "
        "In 'reason', write a very short label: 'Funny', 'Profound', 'Action', 'Wise', 'Angry', or 'Reactive'. "
        "STRICT: No preamble, no markdown, no other text. Only the CSV."
    )
    
    async def _request_highlight(model_name: str):
        log("GEMINI", f"Analyzing highlights with {model_name}...")
        response = await asyncio.to_thread(gemini_client.models.generate_content, model=model_name, contents=[system_prompt, transcript])
        raw_text = response.text.strip()
        
        # Robust CSV filtering
        import csv, re
        from io import StringIO
        clean_csv = raw_text
        if "```" in clean_csv:
            match = re.search(r"```(?:csv|text)?\s*(.*?)\s*```", clean_csv, re.DOTALL)
            if match: clean_csv = match.group(1).strip()
        
        lines = clean_csv.splitlines()
        valid_lines = []
        header_found = False
        for line in lines:
            if "title,start,end,reason" in line.lower():
                header_found = True; valid_lines.append("title,start,end,reason"); continue
            if header_found and "," in line: valid_lines.append(line)
        
        if not valid_lines: # Fallback scan
            valid_lines = [l for l in lines if "," in l and any(c.isdigit() for c in l)]

        reader = csv.DictReader(StringIO("\n".join(valid_lines)))
        results = []
        for row in reader:
            try:
                h = {"title": row.get("title", "Highlight").strip(), "start": float(row.get("start", 0)), "end": float(row.get("end", 0)), "reason": row.get("reason", "Interesting").strip()}
                if h["end"] > h["start"]: results.append(h)
            except: continue
        return results

    try:
        return await _request_highlight(PRIMARY_MODEL)
    except Exception as e:
        log("ERROR", f"{PRIMARY_MODEL} highlight failed: {e}")
        log("GEMINI", f"Retrying with {FALLBACK_MODEL}...")
        try:
            return await _request_highlight(FALLBACK_MODEL)
        except Exception as fe:
            log("ERROR", f"{FALLBACK_MODEL} highlight failed: {fe}"); return []

async def slice_video_clip(input_path: str, start: float, end: float, output_path: str, target_size_mb: float = None):
    buffered_start = max(0, start - 0.5); buffered_end = end + 0.5; duration = (buffered_end - buffered_start) / 1.25
    filter_complex = "setpts=0.8*PTS,silenceremove=1:0:-50dB"
    cmd = ["ffmpeg", "-y", "-ss", str(buffered_start), "-to", str(buffered_end), "-i", input_path, "-vf", filter_complex, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path]
    if target_size_mb:
        bitrate_kbps = int(((target_size_mb * 8 * 1024 * 1024) * 0.9 / duration) / 1000)
        cmd = ["ffmpeg", "-y", "-ss", str(buffered_start), "-to", str(buffered_end), "-i", input_path, "-vf", filter_complex, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{bitrate_kbps}k", "-maxrate", f"{bitrate_kbps}k", "-bufsize", f"{bitrate_kbps*2}k", "-c:a", "aac", "-b:a", "128k", output_path]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate(); return process.returncode == 0
    except Exception as e: log("ERROR", f"Clipping failed: {e}"); return False

async def concatenate_video_segments(segment_paths: list[str], output_path: str) -> bool:
    if not segment_paths: return False
    if len(segment_paths) == 1:
        import shutil; shutil.copy(segment_paths[0], output_path); return True
    v_a_inputs = "".join([f"[{i}:v][{i}:a]" for i in range(len(segment_paths))])
    filter_str = f"{v_a_inputs}concat=n={len(segment_paths)}:v=1:a=1[v][a]"
    cmd = ["ffmpeg", "-y"] + [arg for p in segment_paths for arg in ("-i", p)] + ["-filter_complex", filter_str, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", output_path]
    try:
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await process.communicate(); return process.returncode == 0
    except Exception as e: log("ERROR", f"Concat failed: {e}"); return False

async def send_video_adaptive(bot, chat_id: int, video_path: str, caption: str, reply_to_id: int = None):
    try:
        with open(video_path, 'rb') as f: await bot.send_video(chat_id, video=f, caption=caption, parse_mode="MARKDOWN", reply_to_message_id=reply_to_id)
        return True
    except Exception as e:
        err_msg = str(e).lower()
        if "file too large" in err_msg or "request entity too large" in err_msg:
            log("FILE", "Adaptive compression triggered...")
            compressed_path = video_path.replace(".mp4", "_compressed.mp4")
            cmd = ["ffmpeg", "-y", "-i", video_path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", compressed_path]
            process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await process.communicate()
            if process.returncode == 0:
                with open(compressed_path, 'rb') as f: await bot.send_video(chat_id, video=f, caption=f"{caption}\n_(Optimized)_", parse_mode="MARKDOWN", reply_to_message_id=reply_to_id)
                if os.path.exists(compressed_path): os.remove(compressed_path)
                return True
        log("ERROR", f"Failed to send: {e}"); return False
