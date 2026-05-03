# 🚀 Run Transcription Bot (Telegram Version - Modular)
# ------------------------------------------------------------------------------
# SECTION 1: IMPORT & CONFIGURATION
# ------------------------------------------------------------------------------

import sys
import os
import asyncio
import gc
import time
from typing import Optional

# --- Local Imports ---
import config
from config import Config
from utils import (
    format_duration, 
    log, 
    get_runtime,
    fetch_video_metadata,
    download_video_optimal,
    get_video_highlights_csv,
    slice_video_clip,
    concatenate_video_segments,
    send_video_adaptive,
    format_transcription_srt
)
from bot_classes import TranscriptionJob, IdleMonitor, JobManager, FilesHandler

# --- Transcription Mode (GPU Mandatory) ---
MODE = 'WHISPER'
device = "cuda"

# --- External Libraries (Core - The Waiter) ---
try:
    import telegram
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
    from telegram.constants import ParseMode
    from telegram.request import HTTPXRequest
    from telegram.ext import (Application, CallbackQueryHandler, CommandHandler,
                              ContextTypes, MessageHandler, filters)
    from werkzeug.utils import secure_filename
    import nest_asyncio
except ImportError as e:
    sys.exit(f"❌ Critical Waiter Dependency Missing: {e}\nPlease run: pip install -r requirements_waiter.txt")

GRADIO_AVAILABLE = False
gradio_handler = None
model = None
gemini_client = None
genai = None # Loaded in background

# --- Secrets & Config Alias ---
TELEGRAM_BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID = config.TELEGRAM_CHAT_ID
GEMINI_API_KEY = config.GEMINI_API_KEY

# Config Shortcuts
WHISPER_MODEL = Config.WHISPER_MODEL
WHISPER_PRECISION = Config.WHISPER_PRECISION
WHISPER_BEAM_SIZE = Config.WHISPER_BEAM_SIZE
WHISPER_PATIENCE = Config.WHISPER_PATIENCE
WHISPER_TEMPERATURE = Config.WHISPER_TEMPERATURE
WHISPER_REPETITION_PENALTY = Config.WHISPER_REPETITION_PENALTY
WHISPER_NO_REPEAT_NGRAM_SIZE = Config.WHISPER_NO_REPEAT_NGRAM_SIZE
VAD_FILTER = Config.VAD_FILTER
VAD_THRESHOLD = Config.VAD_THRESHOLD
VAD_MIN_SPEECH_DURATION_MS = Config.VAD_MIN_SPEECH_DURATION_MS
VAD_MIN_SILENCE_DURATION_MS = Config.VAD_MIN_SILENCE_DURATION_MS
VAD_SPEECH_PAD_MS = Config.VAD_SPEECH_PAD_MS
BOT_FILESIZE_LIMIT = Config.BOT_FILESIZE_LIMIT
ENABLE_IDLE_MONITOR = Config.ENABLE_IDLE_MONITOR
IDLE_FIRST_ALERT_MINUTES = Config.IDLE_FIRST_ALERT_MINUTES
IDLE_FINAL_WARNING_MINUTES = Config.IDLE_FINAL_WARNING_MINUTES
IDLE_SHUTDOWN_MINUTES = Config.IDLE_SHUTDOWN_MINUTES

# Detect Colab
try:
    from google.colab import runtime
    IS_COLAB = True
except ImportError:
    IS_COLAB = False
    class MockRuntime:
        def unassign(self): print("🔌 Local Runtime Shutdown Executed")
    runtime = MockRuntime()

# Validation
if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    print("❌ ERROR: Core secrets (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) are missing.")

if not GEMINI_API_KEY:
    print("⚠️ WARNING: GEMINI_API_KEY not set. Summarization features will be disabled.")

# Constants
TRANSCRIPT_FILENAME_PREFIX = "TS"
SUMMARY_FILENAME_PREFIX = "AI"

# ------------------------------------------------------------------------------
# SECTION 2: ENVIRONMENT SETUP
# ------------------------------------------------------------------------------

nest_asyncio.apply()

# --- Compatibility Patch for nest_asyncio and Uvicorn ---
_orig_run = asyncio.run
def _patched_run(main, *, debug=None, loop_factory=None):
    try:
        if loop_factory is not None:
            return _orig_run(main, debug=debug)
        return _orig_run(main, debug=debug)
    except TypeError:
        return _orig_run(main)
asyncio.run = _patched_run

# --- Filesystem Setup ---
UPLOAD_FOLDER = 'uploads'
TRANSCRIPT_FOLDER = 'transcripts'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(TRANSCRIPT_FOLDER, exist_ok=True)

# ------------------------------------------------------------------------------
# SECTION 3: AI AND HARDWARE INITIALIZATION (The Kitchen)
# ------------------------------------------------------------------------------

models_ready_event = asyncio.Event()

async def initialize_models_background():
    """Loads heavy ML dependencies and AI models in the background."""
    global model, gemini_client, GRADIO_AVAILABLE, MODE, device, gradio_handler
    try:
        if SHUTDOWN_IN_PROGRESS: return

        log("INIT", "Kitchen is heating up (Loading GPU acceleration)...")
        
        # 1. Background Installation using uv
        try:
            import torch
            from faster_whisper import WhisperModel
        except ImportError:
            log("INIT", "Kitchen equipment missing. Ordering now (~1 min)...")
            await send_telegram_notification(application, "📦 *Kitchen Update:* Installing GPU-accelerated libraries and JS runtime. Cooking will start shortly.")
            
            await (await asyncio.create_subprocess_exec("pip", "install", "uv", "-q")).wait()
            await (await asyncio.create_subprocess_exec("uv", "pip", "install", "--system", "-r", "requirements_kitchen.txt", "-q")).wait()
            
            # Install Deno for yt-dlp (YouTube extraction)
            log("INIT", "Installing Deno JS runtime...")
            deno_install_cmd = "curl -fsSL https://deno.land/install.sh | sh"
            process = await asyncio.create_subprocess_shell(
                deno_install_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()
            os.environ["PATH"] = f"{os.path.expanduser('~/.deno/bin')}:{os.environ['PATH']}"
            
            log("INIT", "Kitchen equipment arrived.")

        # 2. Hard GPU check
        import torch
        if not torch.cuda.is_available():
            log("ERROR", "GPU not accessible by Torch!")
            await send_telegram_notification(application, "❌ *Kitchen Failure:* GPU not detected by AI engine. Please restart runtime.")
            await perform_shutdown("No GPU available")
            return

        # 3. Load Whisper (GPU Optimized with Batching)
        from faster_whisper import WhisperModel, BatchedInferencePipeline
        log("INIT", f"Loading Whisper ({WHISPER_MODEL}, {device})...")
        
        # Core Model
        base_model = await asyncio.to_thread(WhisperModel, WHISPER_MODEL, device=device, compute_type="float16")
        
        # Optimization: Wrap in BatchedInferencePipeline for 4x speedup
        model = BatchedInferencePipeline(model=base_model)
        log("INIT", "Whisper loaded with BatchedInferencePipeline (Turbo speed).")

        # 4. Initialize Gemini
        if GEMINI_API_KEY:
            from google import genai
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            log("INIT", "Gemini ready.")

        # 5. Gradio
        try:
            import gradio_handler
            GRADIO_AVAILABLE = True
            application.create_task(initialize_gradio_background())
        except ImportError:
            pass

        models_ready_event.set()
        await update_startup_message()
        await send_telegram_notification(application, "🛎️ *Kitchen is now open!* All AI systems are ready to process your orders.")

    except Exception as e:
        log("ERROR", f"Kitchen initialization failed: {e}")
        await send_telegram_notification(application, f"❌ *Kitchen Error:* `{e}`")

# ------------------------------------------------------------------------------
# SECTION 5: GLOBAL OBJECTS & WORKER
# ------------------------------------------------------------------------------

# --- Global State Variables ---
application: Optional[Application] = None
idle_monitor: Optional[IdleMonitor] = None
job_manager: Optional[JobManager] = None
files_handler: Optional[FilesHandler] = None
SHUTDOWN_IN_PROGRESS = False
STARTUP_MESSAGE_ID: Optional[int] = None

async def send_telegram_notification(app: Application, message: str):
    """Sends a formatted message to the designated admin chat."""
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        log("ERROR", f"Telegram notification failed: {e}")

async def perform_shutdown(reason: str):
    """Notifies admins and safely terminates the Colab runtime."""
    global SHUTDOWN_IN_PROGRESS
    if SHUTDOWN_IN_PROGRESS:
        return
    SHUTDOWN_IN_PROGRESS = True
    uptime_str = get_runtime()
    log("SHUTDOWN", f"Initiated. Reason: {reason}")
    try:
        if application:
            await send_telegram_notification(application, f"🔌 *Shutdown*\nReason: {reason}\nUptime: `{uptime_str}`")
            log("SHUTDOWN", "Notification sent")
    except Exception as e:
        log("ERROR", f"Final notification failed: {e}")
    finally:
        log("SHUTDOWN", "Terminating runtime...")
        try:
            if runtime:
                runtime.unassign()
            else:
                log("SHUTDOWN", "Runtime object not found (local execution?)")
        except Exception as e:
            log("ERROR", f"Runtime shutdown failed: {e}")

async def initialize_gradio_background():
    """Launches Gradio web server in background and notifies Telegram with pinned URL."""
    global gradio_handler
    if not GRADIO_AVAILABLE or not gradio_handler:
        log("GRADIO", "Not available, skipping")
        return
    
    try:
        log("GRADIO", "Starting web interface...")
        main_loop = asyncio.get_running_loop()
        gradio_handler.set_dependencies(job_manager, UPLOAD_FOLDER, main_loop)
        public_url = await gradio_handler.launch_gradio_async(share=True)
        
        if public_url:
            log("GRADIO", f"Online: {public_url}")
            await update_startup_message(public_url)
            if STARTUP_MESSAGE_ID:
                try:
                    await application.bot.unpin_all_chat_messages(chat_id=TELEGRAM_CHAT_ID)
                    await application.bot.pin_chat_message(chat_id=TELEGRAM_CHAT_ID, message_id=STARTUP_MESSAGE_ID, disable_notification=True)
                except Exception: pass
    except Exception as e:
        log("ERROR", f"Gradio failed: {str(e)}")
        await send_telegram_notification(application, f"⚠️ *Web UI Warning:* Failed to start Gradio:\n`{str(e)}`")

async def update_startup_message(gradio_url: str = None):
    """Updates the persistent startup message with current status."""
    if not STARTUP_MESSAGE_ID: return

    ai_status = "✅ Kitchen Open" if models_ready_event.is_set() else "⏳ Preparing Kitchen..."
    hardware_label = "NVIDIA GPU"
    
    if not gradio_url and GRADIO_AVAILABLE and gradio_handler and gradio_handler.gradio_app:
        if hasattr(gradio_handler.gradio_app, 'share_url'):
            gradio_url = gradio_handler.gradio_app.share_url

    gradio_text = f"🌐 *Web UI:* {gradio_url}\n" if gradio_url else ""
    
    msg_text = (
        f"🤵 *Welcome to Itamae Sushi Bar*\n"
        f"I am your host. Feel free to send your audio/video files anytime.\n\n"
        f"🛠️ *Equipment:* `{hardware_label}`\n"
        f"🤖 *AI Engine:* `{WHISPER_MODEL}`\n"
        f"📢 *Status:* {ai_status}\n"
        f"{gradio_text}"
        f"📂 *Order Limit:* `{BOT_FILESIZE_LIMIT}MB` per file"
    )
    
    keyboard = [[InlineKeyboardButton("🔌 Close Restaurant", callback_data="shutdown_bot")]]
    try:
        await application.bot.edit_message_text(chat_id=TELEGRAM_CHAT_ID, message_id=STARTUP_MESSAGE_ID, text=msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        log("ERROR", f"Failed to update startup message: {e}")

def run_transcription_process(job: TranscriptionJob) -> tuple[str, str, list]:
    """Runs the blocking Whisper transcription in a separate thread."""
    from utils import log
    log("WHISPER", f"[{job.job_id}] Transcribing {job.original_filename}...")
    
    transcribe_options = {
        "beam_size": WHISPER_BEAM_SIZE,
        "patience": WHISPER_PATIENCE,
        "temperature": WHISPER_TEMPERATURE,
        "repetition_penalty": WHISPER_REPETITION_PENALTY,
        "no_repeat_ngram_size": WHISPER_NO_REPEAT_NGRAM_SIZE
    }
    
    vad_parameters = dict(
        threshold=VAD_THRESHOLD,
        min_speech_duration_ms=VAD_MIN_SPEECH_DURATION_MS,
        min_silence_duration_ms=VAD_MIN_SILENCE_DURATION_MS,
        speech_pad_ms=VAD_SPEECH_PAD_MS
    )
    
    # NOTE: BatchedInferencePipeline REQUIRES vad_filter=True or clip_timestamps
    segments_generator, info = model.transcribe(
        job.local_filepath, 
        vad_filter=True, 
        vad_parameters=vad_parameters, 
        **transcribe_options
    )
    segments = list(segments_generator)
    from utils import format_transcription_native
    formatted_text = format_transcription_native(segments)
    log("WHISPER", f"[{job.job_id}] Done: {len(segments)} segments, lang={info.language}")
    return formatted_text, info.language if info.language else 'N/A', segments

async def queue_processor():
    """The main worker loop that processes jobs from the queue one by one."""
    log("WORKER", "Waiting for AI models...")
    await models_ready_event.wait()
    log("WORKER", "Models ready. Processing jobs...")
    while not SHUTDOWN_IN_PROGRESS:
        job: TranscriptionJob = await job_manager.job_queue.get()
        if job.status == 'cancelled':
            if job.local_filepath and os.path.exists(job.local_filepath): os.remove(job.local_filepath)
            job_manager.job_queue.task_done()
            job_manager.complete_job(job.job_id)
            continue

        job_manager.set_processing_job(job)
        try:
            duration_str = format_duration(job.audio_duration)
            start_time = time.time()

            # --- Phase A: Sourcing ---
            if job.is_url_job:
                await application.bot.send_message(job.chat_id, f"📥 *Sourcing Ingredients:* `{job.video_title}`", parse_mode=ParseMode.MARKDOWN)
                job.local_filepath = await download_video_optimal(job.original_url, UPLOAD_FOLDER, job.job_id)
                if not job.local_filepath: raise Exception("Failed to download video.")

            await application.bot.send_message(job.chat_id, f"▶️ *Processing:* `{job.video_title or job.original_filename}` ({duration_str})...", parse_mode=ParseMode.MARKDOWN)

            # --- Phase B: AI Analysis ---
            transcript_text, detected_language, segments = await asyncio.to_thread(run_transcription_process, job)
            if job.status == 'cancelled': raise asyncio.CancelledError("Cancelled")

            # Save/Send Subtitles (SRT)
            safe_name = secure_filename(os.path.splitext(job.original_filename)[0])[:50]
            
            # Subtitles (SRT) - Primary Output
            if segments:
                srt_text = format_transcription_srt(segments)
                srt_filepath = os.path.join(TRANSCRIPT_FOLDER, f"{safe_name}.srt")
                with open(srt_filepath, "w", encoding="utf-8") as f: f.write(srt_text)
                await application.bot.send_document(job.chat_id, document=open(srt_filepath, 'rb'), filename=os.path.basename(srt_filepath), caption=f"🎬 Subtitles (SRT): `{job.video_title or job.original_filename}`", reply_to_message_id=job.message_id)

            # Highlights & CSV
            highlights = await get_video_highlights_csv(transcript_text, gemini_client)
            if highlights:
                # Send raw CSV with reasons
                import csv
                from io import StringIO
                csv_io = StringIO()
                writer = csv.DictWriter(csv_io, fieldnames=["title", "start", "end", "reason"])
                writer.writeheader()
                writer.writerows(highlights)
                csv_bytes = csv_io.getvalue().encode('utf-8')
                csv_filename = f"{safe_name}.csv"
                await application.bot.send_document(job.chat_id, document=csv_bytes, filename=csv_filename, caption=f"📊 Highlights Metadata (CSV): `{job.video_title or job.original_filename}`", reply_to_message_id=job.message_id)

                from more_itertools import groupby_transform
                grouped = []
                for k, g in groupby_transform(highlights, key=lambda h: h["title"]): grouped.append((k, list(g)))
                
                await application.bot.send_message(job.chat_id, f"🔪 *Chef is slicing:* Identified `{len(grouped)}` highlights. Slicing now...", parse_mode=ParseMode.MARKDOWN)
                
                # --- Phase C: Slicing & Phase D: Delivery ---
                for title, segments_list in grouped:
                    seg_paths = []
                    # Get reason from the first segment in the group
                    reason_label = segments_list[0].get("reason", "Interesting")
                    
                    try:
                        for i, seg in enumerate(segments_list):
                            seg_path = os.path.join(UPLOAD_FOLDER, f"SEG_{i}_{uuid.uuid4().hex[:4]}.mp4")
                            if await slice_video_clip(job.local_filepath, seg["start"], seg["end"], seg_path):
                                seg_paths.append(seg_path)
                        
                        final_clip = os.path.join(UPLOAD_FOLDER, f"CLIP_{secure_filename(title)}.mp4")
                        if await concatenate_video_segments(seg_paths, final_clip):
                            # --- Phase D: Delivery ---
                            success_send = await send_video_adaptive(
                                application.bot, 
                                job.chat_id, 
                                final_clip, 
                                f"🍣 *{title}*\n💡 Vibe: `{reason_label}`", 
                                reply_to_id=job.message_id
                            )
                            if success_send: os.remove(final_clip)
                    finally:
                        for p in seg_paths: 
                            if os.path.exists(p): os.remove(p)

            job.status = "completed"
        except asyncio.CancelledError: pass
        except Exception as e:
            job.status = "failed"; log("ERROR", f"[{job.job_id}] {e}")
            await application.bot.send_message(job.chat_id, f"❌ *Kitchen Accident:* `{e}`", parse_mode=ParseMode.MARKDOWN, reply_to_message_id=job.message_id)
        finally:
            if job.local_filepath and os.path.exists(job.local_filepath):
                try: os.remove(job.local_filepath)
                except Exception: pass
            job_manager.job_queue.task_done()
            job_manager.complete_job(job.job_id)

# ------------------------------------------------------------------------------
# SECTION 6: TELEGRAM UI COMMANDS
# ------------------------------------------------------------------------------

async def get_status_text_and_keyboard():
    processing_job = job_manager.currently_processing
    processing_line = f"👨‍🍳 *Currently Cooking:* `{processing_job.video_title if processing_job.is_url_job else processing_job.original_filename}`\n" if processing_job else ""
    ai_status = "✅ Kitchen Ready" if models_ready_event.is_set() else "⏳ Preparing Kitchen"
    text = (f"📊 *Restaurant Status*\n🛠️ *Equipment:* `NVIDIA GPU`\n🤖 *AI Engine:* `{WHISPER_MODEL}`\n{processing_line}⏳ Uptime: `{get_runtime()}` | Queue: `{job_manager.job_queue.qsize()}`\n🛎️ *AI Status:* {ai_status}")
    keyboard = [[InlineKeyboardButton("📄 View Orders", callback_data="view_cancel_jobs"), InlineKeyboardButton("🔄", callback_data="refresh_status"), InlineKeyboardButton("🔌", callback_data="shutdown_bot")]]
    return text, InlineKeyboardMarkup(keyboard)

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text, reply_markup = await get_status_text_and_keyboard()
    await update.effective_message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    processing_job = job_manager.currently_processing
    queued_jobs = job_manager.get_queued_jobs()
    lines = ["📄 *Job Queue*\n"]
    if processing_job: lines.append(f"\n▶️ *Currently Processing*\n`{processing_job.video_title if processing_job.is_url_job else processing_job.original_filename}`\n(By: {processing_job.author_display_name})")
    if queued_jobs:
        queue_text = [f"*{i}.* `{job.video_title if job.is_url_job else job.original_filename}` (By: {job.author_display_name})" for i, job in enumerate(queued_jobs, 1)]
        lines.append(f"\n⏳ *In Queue ({len(queued_jobs)})*\n" + "\n".join(queue_text))
    elif not processing_job: lines.append("\nThe queue is empty.")
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)

async def extend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ENABLE_IDLE_MONITOR:
        await update.effective_message.reply_text("Idle monitor disabled.")
        return
    msg = "✅ +5m extended" if idle_monitor.extend_timer(5) else "ℹ️ Bot active, no timer."
    await update.effective_message.reply_text(msg)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data
    if data == "refresh_status":
        text, reply_markup = await get_status_text_and_keyboard()
        try: await query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)
        except: pass
    elif data == "shutdown_bot":
        await query.edit_message_text("🔴 *MANUAL SHUTDOWN INITIATED...*", parse_mode=ParseMode.MARKDOWN); await perform_shutdown(f"Manual Shutdown by {query.from_user.first_name}")
    elif data == "view_cancel_jobs":
        queued_jobs = job_manager.get_queued_jobs()
        if not queued_jobs: await query.edit_message_text("The queue is empty.", reply_markup=None); return
        keyboard = [[InlineKeyboardButton(f"{(job.video_title if job.is_url_job else job.original_filename)[:40]}... (ID: {job.job_id})", callback_data=f"cancel_{job.job_id}")] for job in queued_jobs]
        keyboard.append([InlineKeyboardButton("« Back to Status", callback_data="refresh_status")])
        await query.edit_message_text("Select a job below to cancel it:", reply_markup=InlineKeyboardMarkup(keyboard))
    elif data.startswith("cancel_"):
        job_id = data.split("_")[1]; cancelled, job_name = await job_manager.cancel_job(job_id)
        msg = f"✅ Job `{job_name}` was cancelled." if cancelled else "❌ Could not cancel job."
        await query.edit_message_text(msg, reply_markup=None, parse_mode=ParseMode.MARKDOWN)
    elif data == "extend_idle":
        if time.time() - idle_monitor.last_extend_time < 300: await query.answer("⏳ Please wait 5 minutes before extending again.", show_alert=True); return
        if idle_monitor.extend_timer(5):
            idle_monitor.last_extend_time = time.time(); await query.edit_message_text(f"✅ *Idle Extended*\nTimer added +5 minutes.\n_Action by {query.from_user.first_name}_", parse_mode=ParseMode.MARKDOWN)
        else: await query.edit_message_text("ℹ️ Bot is already active, no need to extend.", parse_mode=ParseMode.MARKDOWN)

# ------------------------------------------------------------------------------
# SECTION 7: MAIN ENTRY POINT
# ------------------------------------------------------------------------------

async def main():
    global application, idle_monitor, job_manager, files_handler
    print("🚀 Starting Main Application...")
    request = HTTPXRequest(read_timeout=60.0, connect_timeout=20.0, write_timeout=30.0, pool_timeout=30.0, connection_pool_size=8)
    if not TELEGRAM_BOT_TOKEN: sys.exit("❌ FATAL: No TELEGRAM_BOT_TOKEN found. Exiting.")

    async def post_init(application: Application):
        log("INIT", "Running post-init tasks...")
        application.create_task(queue_processor())
        application.create_task(initialize_models_background())
        if ENABLE_IDLE_MONITOR:
            if MODE == 'GEMINI':
                global IDLE_FIRST_ALERT_MINUTES, IDLE_FINAL_WARNING_MINUTES, IDLE_SHUTDOWN_MINUTES
                IDLE_FIRST_ALERT_MINUTES *= 5; IDLE_FINAL_WARNING_MINUTES *= 5; IDLE_SHUTDOWN_MINUTES *= 5
            idle_monitor.start()

        startup_text = (f"🤵 *Welcome to Itamae Sushi Bar*\nI am your host. Feel free to send your audio/video files anytime.\n\n🛠️ *Equipment:* `Detecting...`\n🤖 *AI Engine:* `{WHISPER_MODEL}`\n📢 *Status:* ⏳ Preparing Kitchen...\n\n📂 *Order Limit:* `{BOT_FILESIZE_LIMIT}MB` per file")
        keyboard = [[InlineKeyboardButton("🔌 Close Restaurant", callback_data="shutdown_bot")]]
        msg = await application.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=startup_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        global STARTUP_MESSAGE_ID; STARTUP_MESSAGE_ID = msg.message_id

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).request(request).post_init(post_init).build()
    idle_monitor = IdleMonitor(application, None, perform_shutdown); job_manager = JobManager(application, idle_monitor, models_ready_event)
    idle_monitor.job_manager = job_manager; files_handler = FilesHandler(job_manager, UPLOAD_FOLDER)
    chat_filter = filters.Chat(chat_id=TELEGRAM_CHAT_ID)

    application.add_handler(CommandHandler(["start", "status"], status_command, filters=chat_filter))
    application.add_handler(CommandHandler("queue", queue_command, filters=chat_filter))
    application.add_handler(CommandHandler("extend", extend_command, filters=chat_filter))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.ATTACHMENT & chat_filter, files_handler.handle_files))
    
    async def handle_text_urls(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.effective_message.text
        if not text: return
        import re; url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        urls = url_pattern.findall(text)
        for url in urls:
            if "youtube.com" in url or "youtu.be" in url:
                status_msg = await update.effective_message.reply_text(f"🔍 *Sourcing Ingredients:* `{url}`", parse_mode=ParseMode.MARKDOWN)
                
                job_manager.start_sourcing()
                try:
                    metadata = await fetch_video_metadata(url)
                finally:
                    job_manager.stop_sourcing()

                if "error" in metadata:
                    error_type = metadata.get("error")
                    if error_type == "GEO_BLOCKED":
                        await status_msg.edit_text("🚫 *Chef's Note: Geo-Blocked*\nThis video is not available in the bot's region. Please **upload the video file directly** to the chat for slicing.")
                    elif error_type == "PRIVATE":
                        await status_msg.edit_text("🔒 *Chef's Note: Private Video*\nI cannot access private videos. Please make sure the video is public or upload the file directly.")
                    elif error_type == "INVALID_URL":
                        await status_msg.edit_text("❌ *Chef's Note: Invalid URL*\nThat doesn't look like a valid YouTube link. Please check and try again.")
                    else:
                        await status_msg.edit_text(f"❌ *Kitchen Accident:*\n`{metadata.get('message', 'Unknown error')}`")
                    continue
                
                job = TranscriptionJob.from_url(update.effective_message, metadata)
                await job_manager.add_job(job)
                await status_msg.delete()

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & chat_filter, handle_text_urls))
    
    async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        error = context.error; print(f"❌ Exception: {error}")
        if "File too large" in str(error): await perform_shutdown(f"Critical Error: {error}")

    application.add_error_handler(global_error_handler)
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("🛑 Bot stopped by user.")
    except Exception as e: print(f"❌ Application crashed: {e}")
    finally:
        if IS_COLAB: runtime.unassign()
