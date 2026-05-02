# start.py

import os
import sys
import subprocess

def check_cuda():
    """Checks if CUDA is available by querying nvidia-smi."""
    try:
        subprocess.run(["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True, "GPU Detected"
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False, "No GPU detected (nvidia-smi failed or missing)"

def main():
    print("🔍 TTB Smart Runner: Detecting Hardware...")
    
    is_gpu, gpu_reason = check_cuda()
    
    if not is_gpu:
        print(f"❌ FATAL: {gpu_reason}")
        print("This project requires a GPU for video processing/slicing.")
        print("Please enable T4 GPU or higher in Colab Runtime settings.")
        sys.exit(1)

    print(f"🚀 {gpu_reason}. Hardware acceleration enabled.")
    mode = 'WHISPER'
    os.environ['TRANSCRIPTION_MODE'] = mode
    
    # Launch bot_core.py
    print(f"🚀 Starting Itamae in GPU Mode...")
    
    try:
        # Use sys.executable to ensure we use the same environment
        cmd = [sys.executable, "bot_core.py"]
        # In Colab/Terminal, we want to see the output in real-time
        process = subprocess.Popen(cmd)
        process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Runner stopped by user.")
    except Exception as e:
        print(f"❌ Runner Error: {e}")

if __name__ == "__main__":
    main()
