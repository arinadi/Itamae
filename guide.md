# 🔪 Master Chef's Guide: Setting Up Itamae Clipper

Welcome to the kitchen! This guide will walk you through the process of setting up **Itamae Clipper** from scratch. Follow these steps to prepare your AI Sushi Chef for service.

---

## 🏗️ Step 1: The Birth of a Chef (BotFather Setup)

First, you need to create your bot on Telegram and get your secret token.

1.  Open Telegram and search for **@BotFather**.
2.  Send `/newbot` and follow the instructions.
    *   **Suggested Name**: `Itamae Clipper` or `Itamae: AI Sushi Chef`
    *   **Suggested Username**: `@ItamaeClipperBot` (or a variation)
3.  **Save the API Token**: You will need this for the `ITAMAE_TELEGRAM_TOKEN` secret.

### 📜 Configure the Chef's Profile
Tell BotFather to set these up for a professional look:
-   **/setabouttext**: `🍣 Itamae: Your AI Sushi Chef for Content. I slice long videos into viral masterpieces using Gemini AI & Whisper.`
-   **/setdescription**: `Welcome to Itamae's Kitchen! Send me a YouTube URL or Video File to get high-paced, jump-cut edited viral clips for TikTok/Reels.`
-   **/setcommands**: Copy and paste the list below:
    ```text
    start - Open the restaurant and check status
    status - View current kitchen equipment and AI readiness
    queue - View the order queue
    extend - Add +5m to the idle timer
    ```

---

## 🆔 Step 2: The VIP Table (Admin Chat ID)

For security, Itamae only serves **one Master** (you). You need your unique Telegram Chat ID.

1.  Search for **@userinfobot** on Telegram.
2.  Send any message to it.
3.  **Copy the ID** (it's a long number). This will be your `ITAMAE_ADMIN_CHAT_ID`.

---

## 🧠 Step 3: The Chef's Brain (Gemini API)

Itamae uses Google Gemini to identify the best "prime cuts" from your video.

1.  Go to [Google AI Studio](https://aistudio.google.com/).
2.  Create a **New API Key**.
3.  Copy this key for the `ITAMAE_GEMINI_KEY` secret.

---

## 🍳 Step 4: Preparing the Kitchen (Google Colab)

This is where the actual cooking (video processing) happens.

1.  **Open the Notebook**: Open the project on Google Colab.
2.  **Hardware Check (MANDATORY)**:
    *   Go to *Runtime > Change runtime type*.
    *   Select **T4 GPU** (or better). Itamae cannot slice without a GPU.
3.  **Add Secrets**:
    *   Click the **Key icon** (Secrets) on the left sidebar.
    *   Add the following keys exactly:
        *   `ITAMAE_TELEGRAM_TOKEN`: (Your Bot Token)
        *   `ITAMAE_ADMIN_CHAT_ID`: (Your ID number)
        *   `ITAMAE_GEMINI_KEY`: (Your Gemini Key)
    *   Enable the **"Notebook access"** toggle for each secret.

---

## 🛎️ Step 5: Service is Open!

1.  **Run the Launch Cell** in Colab.
2.  **Waiter Notification**: In <10 seconds, the bot will message you on Telegram: *"Welcome to Itamae Sushi Bar"*.
3.  **Kitchen Heating**: Wait for the second notification: *"Kitchen is now open!"*. This means the heavy AI tools are installed and ready.

---

## 🍣 How to Order (Usage)

-   **YouTube Clips**: Just paste any YouTube URL. Itamae will fetch the metadata, show you the thumbnail, and start slicing.
-   **Direct Files**: Send any video or audio file as an attachment.
-   **The Result**: You will receive a high-quality transcript first, followed by several **10-30s clips** that are:
    *   Accelerated to **1.25x speed**.
    *   Edited with **AI Jump Cuts** (silence removed).
    *   Stitched together if the topic spans multiple segments.

---

## ⚠️ Troubleshooting (Kitchen Accidents)

-   **"GPU Not Detected"**: Ensure you have selected a GPU runtime in Colab before starting.
-   **"File Too Large"**: Itamae will try to compress it automatically. If it still fails, try a shorter source video.
-   **Bot Not Responding**: Ensure the Colab cell is still running and "Notebook access" is enabled for your secrets.

---

## 🌍 Advanced: One-Key Kitchen (Portable Setup)

Tired of entering secrets every time you switch Colab accounts? Use the **One-Key Kitchen** method to load all secrets automatically from a private GitHub file.

### 1. Create a Private Repository
1.  Create a **New Repository** on GitHub (e.g., `itamae-config`).
2.  Set it to **Private**.
3.  Create a file named `.env.itamae` inside this repo with your secrets:
    ```env
    ITAMAE_TELEGRAM_TOKEN=your_bot_token
    ITAMAE_ADMIN_CHAT_ID=your_chat_id
    ITAMAE_GEMINI_KEY=your_gemini_key
    ```

### 2. Get the Raw API URL
1.  Open your `.env.itamae` file in the GitHub web interface.
2.  Click the **Raw** button.
3.  Copy the URL. It should look like: `https://raw.githubusercontent.com/user/repo/main/.env.itamae`
    *Note: The bot uses the GitHub API, but providing the Raw URL helps it identify the file path.*

### 3. One-Time Colab Setup
Now, in any Colab account, you only need to add **TWO** secrets to the key icon tab:
-   `ITAMAE_GITHUB_TOKEN`: (A GitHub Personal Access Token with `repo` scope)
-   `ITAMAE_CONFIG_URL`: (The URL from Step 2)

Itamae will automatically fetch all your ingredients from your private cloud storage upon startup!

---
*“A master chef serves only perfection. Happy slicing!”* 🔪🍣✨
