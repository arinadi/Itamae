# 🔪 Itamae: The Ultimate AI Sushi Chef for Content

[![Google Colab](https://img.shields.io/badge/Run%20on-Google%20Colab-orange?logo=googlecolab)](https://colab.research.google.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Hardware: GPU Required](https://img.shields.io/badge/Hardware-GPU%20Mandatory-red)](https://developer.nvidia.com/cuda-gpus)

**Itamae** (板前) is not just a bot; it's a world-class AI Sushi Chef for your digital content. Its philosophy: **"Identify the prime cuts, remove the fat, and serve only perfection."**

Transform long-form videos into high-paced, viral-ready clips for TikTok, Reels, and Shorts in seconds. Powered by the precision of **OpenAI Whisper** and the creative brain of **Google Gemini**.

---

## 🍣 The Omakese Experience (Key Features)

- **🚀 High-Paced Slicing**: Every clip is automatically accelerated to **1.25x speed**, making your content punchier and more energetic.
- **✂️ AI Jump Cuts**: Our chef automatically removes "uhms," "errs," and dead air, creating seamless, professional "cut-to-cut" transitions.
- **🧠 Genius Selection**: Gemini AI analyzes your transcript to find 3-5 high-impact "hooks" that are guaranteed to grab attention.
- **📦 Multi-Segment Compilation**: If a topic is spread across the video, Itamae stitches the best moments together into one dynamic montage.
- **📥 YouTube Sourcing**: Simply paste a URL. Itamae fetches the "finest ingredients" (1080p MKV) with full metadata and thumbnails.
- **⚖️ Adaptive Serving**: Telegram file limits? No problem. Itamae dynamically detects limits and auto-compresses "servings" to ensure they reach your plate.

---

## 🚀 Quick Setup (The One-Key Kitchen)

For maximum security and speed, Itamae uses the **One-Key Kitchen** method via Google Colab's native Secrets system.

### Step 1: Prepare the Ingredients (Secrets) 🔑
In your **Google Colab**, click the **Secrets** tab (key icon 🔑) and add these ingredients:
- `ITAMAE_TELEGRAM_TOKEN`: (Your Bot Token from @BotFather)
- `ITAMAE_ADMIN_CHAT_ID`: (Your Telegram Chat ID)
- `ITAMAE_GEMINI_KEY`: (Your Google AI Studio Key)
- `ITAMAE_GITHUB_TOKEN`: (Optional, for private cloning)

### Step 2: Heat the Stove 🔥
1.  Set your Runtime to **T4 GPU** or higher (*Runtime > Change runtime type*).
2.  Run this cell to invite the Chef:

    ```python
    # @title 🔪 Launch Itamae Slicer
    import os
    from google.colab import userdata

    # 1. Load Ingredients into Kitchen Environment
    for key in ['ITAMAE_TELEGRAM_TOKEN', 'ITAMAE_ADMIN_CHAT_ID', 'ITAMAE_GEMINI_KEY', 'ITAMAE_GITHUB_TOKEN', 'ITAMAE_CONFIG_URL']:
        try:
            val = userdata.get(key)
            if val: os.environ[key] = str(val)
        except: pass

    # 2. Invite the Chef
    !curl -s https://raw.githubusercontent.com/arinadi/Itamae/main/colab_setup.py -o colab_setup.py && python colab_setup.py
    ```

<details>
<summary><b>Advanced: Option B (Private Config Fallback)</b></summary>

Tired of re-entering secrets for every new Colab? You can store them in a **Private GitHub Repository** (e.g., in a file named `.env.itamae`) and fetch them securely.

1. Add `ITAMAE_GITHUB_TOKEN` (your PAT) to Colab Secrets.
2. Add `ITAMAE_CONFIG_URL` (the Raw URL of your private `.env` file) to Colab Secrets.
3. The bot will automatically pull all other keys from your cloud repository upon startup!
</details>

---

## 🛠️ Chef's Tools (Core Tech)

- **Waiter System**: Ultra-fast startup (<10s). The bot is online immediately while the AI kitchen heats up in the background.
- **The Brain (Gemini 2.5 Flash)**: Identifies the viral hooks and orchestrates the cuts.
- **The Knife (FFmpeg + Whisper)**: Precision transcription and pixel-perfect high-speed encoding.
- **Smart Sourcing (yt-dlp)**: Fetches raw 1080p ingredients from almost any video platform.

---

## 📂 Restaurant Layout

- `bot_core.py`: The **Lead Chef**. Orchestrates the entire kitchen workflow.
- `colab_setup.py`: The **Apprentice**. Handles logistics and setup.
- `launcher.py`: The **Maitre D'**. Ensures GPU is hot and ready for service.
- `utils.py`: The **Chef's Kit**. Sharpened tools for clipping, merging, and compression.

---

*“A master chef serves only perfection. One viral clip at a time.”* 🔪🍣✨
