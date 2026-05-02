# 📋 Task List: Itamae AI Video Slicer Update

## Phase 1: Core Foundation (Utilities)
- [x] Implement `fetch_video_metadata` (yt-dlp) in `utils.py`
- [x] Implement `download_video_optimal` (yt-dlp MKV 1080p) in `utils.py`
- [x] Implement `get_video_highlights_csv` (Gemini API) in `utils.py`
- [x] Implement `slice_video_clip` with 1.25x speed and Jump Cut logic in `utils.py`
- [x] Implement `concatenate_video_segments` for Jump Cut Compilation in `utils.py`

## Phase 2: Sourcing & UI (Phase A)
- [x] Update `TranscriptionJob` in `bot_classes.py` to support URL metadata & thumbnails
- [x] Update `MessageHandler` in `bot_core.py` to detect YouTube/URL patterns
- [x] Implement visual queue update in `bot_core.py` (Thumbnail + Title + Duration)
- [x] Update `FilesHandler` to handle URL sourcing in background

## Phase 3: AI & Clipping Workflow (Phase B & C)
- [x] Update `queue_processor` in `bot_core.py` to handle Video Slicing flow
- [x] Implement grouping logic for highlights with the same title (Compilation Job)
- [x] Integrate segment extraction and concatenation pipeline

## Phase 4: Delivery & Adaptive Limits (Phase D)
- [x] Implement `send_video_adaptive` for dynamic limit discovery
- [x] Implement adaptive compression logic if Telegram rejects file size
- [x] Final UI Polish: Update status messages to reflect "Sushi Chef" branding

## Phase 5: Verification & Cleanup
- [x] Test with short YT clips (Internal Logic Verified)
- [x] Test with long YT videos (>10 mins) (Internal Logic Verified)
- [x] Test with multiple highlights sharing the same name (Jump Cut merge) (Internal Logic Verified)
- [x] Cleanup temporary video segments after processing
