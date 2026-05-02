# Implementation Plan: AI Video Slicer (Highlights & Clipping)

This plan outlines the implementation of a new feature that allows users to send YouTube URLs or video files to the bot, automatically identify highlights using Gemini, and receive clipped video segments via Telegram.

## 1. Goal
Provide a seamless "Sushi Chef" experience where the bot sources raw video, identifies the best "cuts" (highlights), and serves them as perfectly sliced clips.

## 2. Technical Workflow

### Phase A: Input & Sourcing
1.  **URL Detection**: `FilesHandler` will be updated to detect YouTube/URL patterns.
2.  **Metadata Fetching**: Use `yt-dlp` with the `--dump-json` flag to fetch:
    *   Video Title
    *   Duration
    *   Thumbnail URL
    *   Available Formats
3.  **Visual Queue**: Update the Telegram queue message to display the **Thumbnail**, **Title**, and **Duration**.
4.  **Optimal Download**:
    *   Target: `bestvideo[height<=1080][ext=mkv]+bestaudio[ext=m4a]/best[height<=1080]`
    *   Format: MKV (preferred for robust metadata/stream handling).

### Phase B: AI Analysis (The Brain)
1.  **Transcription**: Transcribe the sourced video (Whisper for local, Gemini for cloud).
2.  **Highlight Extraction**:
    *   **System Prompt**: Instruct Gemini to act as a "Social Media Viral Editor".
    *   **Jump Cut Compilation**: Gemini is encouraged to provide multiple start/end points for the same `title` to create a montage effect.
    *   **Output Format**: STRICT CSV with headers `title, start, end`.
3.  **Parsing & Grouping**: 
    *   Convert CSV to objects.
    *   **Group by Title**: All rows sharing the same title are grouped into a single "Compilation Job" to be merged into one final clip.

### Phase C: Precision Slicing (The Paced Knife)
1.  **Segment Extraction**: For each title group, extract all designated segments with a `-0.5s` / `+0.5s` buffer.
2.  **Processing (1.25x Speed + Silence Removal)**:
    *   Apply `setpts=0.8*PTS` and `atempo=1.25` to each segment.
    *   Apply `silenceremove` filter to remove internal pauses.
3.  **Concatenation (Jump Cut)**:
    *   Stitch all segments with the same title together. The abrupt transitions between segments create the "Jump Cut" style popular in social media.
4.  **FFmpeg Command Template**:
    `ffmpeg -i seg1.mp4 -i seg2.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" output.mp4`

### Phase D: Delivery & Adaptive Optimization
1.  **Dynamic Discovery**: Attempt to send the clip without pre-emptive size checks.
2.  **Error Handling**: If Telegram returns a `FileTooLarge` or similar error:
    *   **Capture Limit**: Dynamically update the internal `BOT_FILESIZE_LIMIT` based on the rejected file size.
    *   **Adaptive Compression**: Calculate the required bitrate to reduce the file size by 20-30% below the detected limit.
    *   **Re-encode**: Use FFmpeg to re-compress the clip.
3.  **Delivery**: Send the (optimized) clip to Telegram with the highlight title.
4.  **UI Feedback**: Update the bot's status message to reflect the newly "learned" file limit.

## 3. Technical Research & Deep Dive

### A. Sourcing (yt-dlp)
*   **Format Selection**: We use `-f "bestvideo[height<=1080][ext=mkv]+bestaudio[ext=m4a]/best[height<=1080]"` to ensure high-quality source material without exceeding 1080p (to keep processing times reasonable).
*   **MKV Container**: Preferred for downloading because it handles stream merging more reliably than MP4 during the initial fetch.
*   **Metadata**: `yt-dlp --dump-json` provides the `thumbnail` (highest res), `title`, `duration`, and `webpage_url` which are critical for the UI.

### B. Clipping & Buffering (FFmpeg)
*   **Precise Cutting**: We avoid `-c copy` because it only cuts at keyframes, leading to black frames or frozen video at the start of a clip. We use re-encoding (`-c:v libx264`) for pixel-perfect start/end points.
*   **Buffer Logic**:
    *   `buffered_start = max(0, start - 0.5)`
    *   `buffered_end = end + 0.5`
    *   Shorter buffers are used to maintain the high-paced "Jump Cut" feel.

### C. Adaptive Bitrate Math
*   When a file is rejected, we calculate the new bitrate using this formula:
    `Target Bitrate (kbps) = (Target File Size in Megabits / Duration in seconds) * 1000`
    *   *Example*: 15MB limit for a 30s clip:
        `(15 * 8) / 30 = 4 Mbps` (approx 4000 kbps).
*   We use a **Two-Pass encoding** or a strict **CBR (Constant Bitrate)** mode to ensure the resulting file *never* exceeds the detected Telegram limit.

## 4. System Prompt Specification

The following prompt is used for Gemini highlight analysis. It is designed to be highly restrictive to ensure parseable CSV output.

```markdown
**Role**: You are a professional Social Media Viral Video Editor.
**Task**: Analyze the provided video transcript and identify 3-5 high-impact highlights. For each highlight, you can provide ONE or MORE time segments that will be stitched together into a single "Jump Cut" clip.

**Selection Criteria**:
1. Target final duration: 10-30 seconds per title (after 1.25x speedup).
2. If a highlight is best explained by jumping between different parts of the video, provide multiple rows with the SAME title.
3. Look for dense information or high-energy parts. Avoid long intro/outro or filler.

**Output Format**: 
Return ONLY a CSV-formatted list. Do not include markdown code blocks, preambles, or postambles. Use the following structure:
title,start,end

**Example Output**:
"The Secret Sauce",45.5,52.0
"The Secret Sauce",70.0,78.5
"Why AI is Slicing",120.0,145.2
```

## 5. Component Updates
...
### `utils.py`
- Add `fetch_video_metadata(url)`: Returns dict with title, duration, thumbnail.
- Add `download_video_optimal(url)`: Handles `yt-dlp` logic.
- Add `get_video_highlights_csv(transcript)`: System prompt for Gemini highlight analysis.
- Add `slice_video_clip(input_path, start, end, output_path)`: FFmpeg wrapper with compression fallback.

### `bot_classes.py`
- Update `TranscriptionJob`: Add fields for `thumbnail_url` and `is_url_job`.
- Update `JobManager.add_job`: Logic to send thumbnail if available.

### `bot_core.py`
- Update `MessageHandler`: Detect URLs in addition to files.
- Update `queue_processor`: Add branch for "Highlight & Clipping" logic after transcription.

## 4. Risks & Mitigations
- **IP Blocking**: `yt-dlp` might get rate-limited. *Solution: Support for cookies/proxy if needed.*
- **Gemini CSV Hallucinations**: Gemini might not follow CSV format perfectly. *Solution: Robust regex parsing and validation.*
- **Slow Encoding**: 1080p encoding can be slow on CPU. *Solution: Prefer WHISPER (GPU) mode for clipping if available.*

## 5. UI/UX Concept
User sends: `https://youtu.be/example`
Bot replies: 
[Thumbnail Image]
**Queued: How to Slicing 101**
⏱️ Duration: 12:45
👨‍🍳 Status: Sourcing Ingredients...

---
*“A master chef serves only perfection, one clip at a time.”* 🔪🍣✨
