from datetime import datetime
import asyncio
import time
import os
import config

# --- System Utilities ---

def get_runtime() -> str:
    """Total runtime since INIT_START."""
    elapsed = time.time() - config.INIT_START
    m, s = divmod(int(elapsed), 60)
    return f"{m}m {s:02d}s"

def log(category: str, message: str):
    """Chef's Log: [HH:MM:SS] [+Runtime] [CAT] msg"""
    print(f"[{time.strftime('%H:%M:%S')}] [+{get_runtime()}] [{category}] {message}")

def format_duration(seconds: float) -> str:
    if not isinstance(seconds, (int, float)) or seconds < 0: return "N/A"
    m, s = divmod(int(seconds), 60)
    return f"{m}m {s:02d}s"

def format_timestamp(seconds: float, srt: bool = False) -> str:
    td = float(max(0, seconds))
    h, m = divmod(int(td // 60), 60)
    s = int(td % 60)
    ms = int((td - int(td)) * 1000)
    if srt: return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h > 0 else f"{m:02d}:{s:02d}"

# --- AI & Formatting ---

PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-2.5-flash"

def parse_ts(ts) -> float:
    """Parses seconds, MM:SS, or HH:MM:SS to float seconds."""
    s = str(ts).strip()
    if not s: return 0.0
    try: return float(s)
    except:
        p = s.split(':')
        try:
            if len(p) == 2: return int(p[0]) * 60 + float(p[1])
            if len(p) == 3: return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2])
        except: pass
    return 0.0

def format_transcription_native(segments: list) -> str:
    """Formats segments with timestamps for AI analysis: [start -> end] text"""
    lines = []
    for s in segments:
        if hasattr(s, 'text') and s.text.strip():
            lines.append(f"[{s.start:.1f} -> {s.end:.1f}] {s.text.strip()}")
    return "\n".join(lines)

def format_transcription_srt(segments: list) -> str:
    lines = []
    for i, s in enumerate(segments, 1):
        lines.append(f"{i}\n{format_timestamp(s.start, True)} --> {format_timestamp(s.end, True)}\n{s.text.strip()}\n")
    return "\n".join(lines)

async def summarize_text(transcript: str, gemini_client, mode: str = 'WHISPER') -> str:
    if not gemini_client: return "Summarization disabled."
    prompt = (f"Anda adalah AI peringkas jurnalis. Ringkas transkrip ini ke Bahasa Indonesia.\n"
              f"FORMAT: Fakta Berita, Lead, Body, Narasumber, Data, Klarifikasi.\n"
              f"Tanggal: {datetime.now().strftime('%d %B %Y')}")
    try:
        log("GEMINI", f"Summarizing with {PRIMARY_MODEL}...")
        res = await asyncio.to_thread(gemini_client.models.generate_content, model=PRIMARY_MODEL, contents=[prompt, transcript])
        return res.text
    except Exception as e:
        log("ERROR", f"Summary fallback triggered: {e}")
        res = await asyncio.to_thread(gemini_client.models.generate_content, model=FALLBACK_MODEL, contents=[prompt, transcript])
        return res.text

async def get_video_highlights_csv(transcript: str, gemini_client) -> list[dict]:
    if not gemini_client: return []
    sys_prompt = ("You are an expert Viral Video Editor for TikTok and Reels. Analyze the transcript and identify 3-5 high-impact highlights.\n"
                  "STRICT RULES FOR HIGHLIGHTS:\n"
                  "- Look for strong HOOKS (attention-grabbing starts), emotional peaks, or controversial takes.\n"
                  "- Each clip MUST be a self-contained point or story.\n"
                  "- Output ONLY CSV with headers: title,start,end,reason.\n"
                  "- 'start' and 'end' MUST be TOTAL SECONDS (e.g. 150.5). Be extremely precise based on the [start -> end] timestamps provided.\n"
                  "- 'reason': Hook, Wise, Insightful, Controversial, or Reactive.\n"
                  "- 'title': Short clickbait title (max 5 words).\n"
                  "- Target 15-45s per title. No preamble, no markdown.")
    
    async def _req(model):
        log("GEMINI", f"Highlighting with {model}...")
        res = await asyncio.to_thread(gemini_client.models.generate_content, model=model, contents=[sys_prompt, transcript])
        text = res.text.strip()
        if "```" in text:
            import re; m = re.search(r"```(?:csv|text)?\s*(.*?)\s*```", text, re.DOTALL)
            if m: text = m.group(1).strip()
        import csv; from io import StringIO
        lines = [l for l in text.splitlines() if "," in l]
        if lines and "title" not in lines[0].lower(): lines.insert(0, "title,start,end,reason")
        reader = csv.DictReader(StringIO("\n".join(lines)))
        results = []
        for r in reader:
            try:
                start = parse_ts(r.get("start", "0"))
                end = parse_ts(r.get("end", "0"))
                if end > start:
                    results.append({
                        "title": r["title"].strip(),
                        "start": start,
                        "end": end,
                        "reason": r.get("reason", "Interesting").strip()
                    })
            except: continue
        return results

    try: return await _req(PRIMARY_MODEL)
    except Exception as e:
        log("ERROR", f"Highlight fallback: {e}")
        return await _req(FALLBACK_MODEL)

# --- Video & Sourcing ---

async def fetch_video_metadata(url: str) -> dict:
    cmd = ["yt-dlp", "--no-playlist", "--xff", "default", "--no-check-certificates", "--quiet", 
           "--extractor-args", "youtube:player_client=android,web",
           "--print", "%(title)s|||%(duration)s|||%(thumbnail)s", url]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        if proc.returncode != 0:
            if "country" in err.decode().lower(): return {"error": "GEO_BLOCKED"}
            return {"error": "FAILED"}
        p = out.decode().strip().split("|||")
        return {"title": p[0], "duration": float(p[1]), "thumbnail": p[2] if len(p)>2 else None, "original_url": url}
    except Exception as e: log("ERROR", f"Fetch fail: {e}"); return {"error": "UNKNOWN"}

async def download_video_optimal(url: str, folder: str, job_id: str) -> str:
    tmpl = os.path.join(folder, f"{job_id}.%(ext)s")
    from config import Config
    cmd = [
        "yt-dlp", "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]", 
        "--merge-output-format", "mkv", "-o", tmpl, 
        "--print", "after_move:filepath", "--xff", "default", "--no-check-certificates", "--no-playlist",
        "-N", "5", "--sponsorblock-remove", "all",
        "--embed-metadata", "--embed-chapters",
        "--extractor-args", "youtube:player_client=android,web",
        "--write-subs", "--write-auto-subs", "--sub-langs", Config.SUBTITLE_LANGS, 
        "--convert-subs", "srt", url
    ]
    try:
        log("FILE", f"Downloading: {url}")
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        out, err = await proc.communicate()
        path = out.decode().strip()
        
        if proc.returncode == 0 and path and os.path.exists(path):
            return path
        
        # Fallback check if --print failed but file exists
        for f in os.listdir(folder):
            if f.startswith(job_id) and f.endswith((".mkv", ".mp4", ".webm")):
                return os.path.join(folder, f)
        
        if err:
            error_msg = err.decode().strip().splitlines()[-1] if err else "Unknown error"
            log("ERROR", f"Download failed: {error_msg}")
        return ""
    except Exception as e:
        log("ERROR", f"Download exception: {e}")
        return ""

async def slice_video_clip(in_path: str, start: float, end: float, out_path: str, mb_limit: float = None):
    dur = (end - start + 1) / 1.25
    v_filt = "setpts=0.8*PTS,silenceremove=1:0:-50dB"
    cmd = ["ffmpeg", "-y", "-ss", str(max(0, start-0.5)), "-to", str(end+0.5), "-i", in_path, "-vf", v_filt, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-b:a", "128k", out_path]
    if mb_limit:
        br = int(((mb_limit * 8 * 1024 * 1024) * 0.9 / dur) / 1000)
        cmd = ["ffmpeg", "-y", "-ss", str(max(0, start-0.5)), "-to", str(end+0.5), "-i", in_path, "-vf", v_filt, "-af", "atempo=1.25", "-c:v", "libx264", "-preset", "veryfast", "-b:v", f"{br}k", "-maxrate", f"{br}k", "-bufsize", f"{br*2}k", "-c:a", "aac", "-b:a", "128k", out_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate(); return proc.returncode == 0

async def concatenate_video_segments(paths: list[str], out_path: str) -> bool:
    if not paths: return False
    if len(paths) == 1: import shutil; shutil.copy(paths[0], out_path); return True
    v_a = "".join([f"[{i}:v][{i}:a]" for i in range(len(paths))])
    cmd = ["ffmpeg", "-y"] + [a for p in paths for a in ("-i", p)] + ["-filter_complex", f"{v_a}concat=n={len(paths)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-c:a", "aac", out_path]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate(); return proc.returncode == 0

def parse_srt_to_segments(srt_path: str) -> list:
    """Parses an SRT file into a list of Whisper-compatible segment objects/dicts."""
    import re
    if not srt_path or not os.path.exists(srt_path): return []
    try:
        with open(srt_path, 'r', encoding='utf-8') as f: content = f.read()
        # Simple SRT regex: index, timestamp, text
        pattern = re.compile(r'(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\s*\n(.*?)(?=\n\d+\s*\n|\Z)', re.DOTALL)
        matches = pattern.findall(content)
        
        def ts_to_sec(ts):
            h, m, s = ts.replace(',', '.').split(':')
            return int(h)*3600 + int(m)*60 + float(s)

        segments = []
        for m in matches:
            segments.append(type('Segment', (), {
                'start': ts_to_sec(m[1]),
                'end': ts_to_sec(m[2]),
                'text': m[3].replace('\n', ' ').strip()
            }))
        return segments
    except Exception as e:
        from bot_classes import log
        log("ERROR", f"SRT Parse fail: {e}")
        return []

async def send_video_adaptive(bot, chat_id: int, path: str, caption: str, reply_id: int = None):
    try:
        with open(path, 'rb') as f: await bot.send_video(chat_id, video=f, caption=caption, parse_mode="MARKDOWN", reply_to_message_id=reply_id)
        return True
    except Exception as e:
        if "large" in str(e).lower():
            c_path = path.replace(".mp4", "_c.mp4")
            cmd = ["ffmpeg", "-y", "-i", path, "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", c_path]
            p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            await p.communicate()
            if p.returncode == 0:
                with open(c_path, 'rb') as f: await bot.send_video(chat_id, video=f, caption=f"{caption}\n_(Optimized)_", parse_mode="MARKDOWN", reply_to_message_id=reply_id)
                if os.path.exists(c_path): os.remove(c_path)
                return True
        log("ERROR", f"Send fail: {e}"); return False
