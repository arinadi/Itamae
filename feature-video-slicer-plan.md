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
    *   **Output Format**: STRICT CSV with headers `title, start, end`.
    *   **Context**: Pass the transcript and video metadata to Gemini.
3.  **Parsing**: Convert the CSV response into a list of clip objects.

### Phase C: Precision Slicing (The Knife)
1.  **Buffering**: Apply a `-1s` start buffer and `+1s` end buffer for each clip to ensure smooth transitions and avoid cutting off mid-sentence.
2.  **FFmpeg Slicing**: Use fast seek (`-ss` before `-i`) and stream copying where possible, or re-encoding if buffering/timestamps require it.
    *   Command template: `ffmpeg -ss [start-1] -to [end+1] -i input.mkv -c:v libx264 -crf 23 -c:a aac [output].mp4`

### Phase D: Delivery & Adaptive Optimization
1.  **Dynamic Discovery**: Attempt to send the clip without pre-emptive size checks.
2.  **Error Handling**: If Telegram returns a `FileTooLarge` or similar error:
    *   **Capture Limit**: Dynamically update the internal `BOT_FILESIZE_LIMIT` based on the rejected file size.
    *   **Adaptive Compression**: Calculate the required bitrate to reduce the file size by 20-30% below the detected limit.
    *   **Re-encode**: Use FFmpeg to re-compress the clip.
3.  **Delivery**: Send the (optimized) clip to Telegram with the highlight title.
4.  **UI Feedback**: Update the bot's status message to reflect the newly "learned" file limit.

## 3. Component Updates

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
