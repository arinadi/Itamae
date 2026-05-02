# 🔪 Itamae: The Master AI Slicer

[![Google Colab](https://img.shields.io/badge/Run%20on-Google%20Colab-orange?logo=googlecolab)](https://colab.research.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Itamae** (板前) is a highly skilled AI "Sushi Chef" for your content. Its philosophy is simple: **"Only cut the best parts to serve."** 

Powered by **OpenAI Whisper** and **Google Gemini**, Itamae analyzes long-form videos or audio files, identifies the most impactful moments (hooks/highlights), and automatically slices them into perfect 15-second "servings" for social media.

---

## 🍣 The Itamae Experience

- **Master Selection**: AI identifies high-vibe segments, ensuring only the most "delicious" content is served.
- **Precision Slicing**: Automatically generates multiple clips (max 15s) with high precision timestamps.
- **YouTube Integration**: Simply provide a URL, and Itamae will source the finest ingredients for you.
- **Efficient Service**: Uses a clipping queue to process and serve your highlights sequentially.

---

## 🚀 Quick Setup (Google Colab)

1.  **Prepare your Secrets** 🔑:
    In Colab's **Secrets** tab, add:
    - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
    - `GEMINI_API_KEY` (Required for highlight analysis)
    - `HF_TOKEN`, `GITHUB_TOKEN` (Optional)

2.  **Turn on the Stove** 🔥:
    Set Runtime to **T4 GPU** (*Runtime > Change runtime type*).

3.  **Invite the Itamae** 🛎️:
    Copy and run this cell:

    ```python
    # @title 🔪 Start Itamae Slicer
    import os
    from google.colab import userdata

    # 1. Prepare Ingredients (Load Secrets)
    for key in ['TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'GEMINI_API_KEY', 'GITHUB_TOKEN', 'HF_TOKEN']:
        try:
            val = userdata.get(key)
            if val: os.environ[key] = str(val)
        except: pass

    # 2. Begin Slicing
    !curl -s https://raw.githubusercontent.com/arinadi/Itamae/main/runner.py -o runner.py && python runner.py
    ```

---

## 🛠️ Ingredients (Core Tech)

- **yt-dlp**: For high-quality sourcing from YouTube and other platforms.
- **OpenAI Whisper**: Precision transcription for perfect time-coded scripts.
- **Google Gemini 2.5 Flash**: The \"Brain\" that identifies the best segments.
- **FFmpeg**: The \"Knife\" that performs the precise slicing.

---

## 📂 Project Structure

- `main.py`: The **Itamae**. Orchestrates transcription, analysis, and slicing.
- `runner.py`: The **Apprentice**. Handles setup and environment preparation.
- `start.py`: The **Dojo Manager**. Ensures all systems are operating at peak performance.
- `utils.py`: The **Master's Tools**. Helpers for analysis and formatting.

---

## 💻 Local Dojo (Manual Run)

```bash
git clone https://github.com/arinadi/Itamae.git
cd Itamae
bash setup_uv.sh
python start.py
```

---

*“A master chef serves only perfection.”* 🔪🍣✨
