import os
import time
import sys
import requests
import json

# --- CONFIGURATION ---
REPO_URL = "https://github.com/arinadi/Itamae.git" 
REPO_NAME = "Itamae"
# ---------------------

def run_command(cmd):
    print(f"Executing: {cmd}")
    return os.system(cmd)

def load_secrets_from_gist():
    """Loads project secrets from a private GitHub Gist with smart validation."""
    token = os.environ.get('ITAMAE_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN', '')
    gist_id = os.environ.get('ITAMAE_GIST_ID', '')
    
    # --- Smart Swap Detection ---
    # GitHub Tokens usually start with ghp_ or github_pat_
    # Gist IDs are hexadecimal strings
    if gist_id.startswith(('ghp_', 'github_pat_')) and not token.startswith(('ghp_', 'github_pat_')):
        print("⚠️  DETECTED: Secrets might be swapped! Attempting to fix internally...")
        token, gist_id = gist_id, token
    
    if not token or not gist_id:
        print("ℹ️ Gist Loader: Missing token or Gist ID. Skipping cloud secrets.")
        return

    if not token.startswith(('ghp_', 'github_pat_')):
        print("❌ Gist Loader: ITAMAE_GITHUB_TOKEN invalid format. Should start with 'ghp_'.")
        return

    print(f"⏳ Gist Loader: Fetching secrets from Gist {gist_id[:6]}...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        response = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=10)
        
        if response.status_code == 401:
            print("❌ Gist Loader Error: 401 Unauthorized. Check if your GITHUB_TOKEN is correct and has 'gist' scope.")
            return
        elif response.status_code == 404:
            print(f"❌ Gist Loader Error: 404 Not Found. Gist ID '{gist_id}' is incorrect or private gist inaccessible.")
            return
            
        response.raise_for_status()
        gist_data = response.json()
        secrets_loaded = 0
        
        for filename, file_info in gist_data.get('files', {}).items():
            content = file_info['content']
            
            # Case 1: .env format (Key=Value) - Recommended
            if ".env" in filename or filename == ".env.itamae":
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line: continue
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k.startswith("ITAMAE_"):
                        os.environ[k] = v
                        secrets_loaded += 1
            
            # Case 2: JSON format
            elif filename.endswith('.json'):
                try:
                    data = json.loads(content)
                    for k, v in data.items():
                        if k.startswith("ITAMAE_"):
                            os.environ[k] = str(v)
                            secrets_loaded += 1
                except: pass
        
        if secrets_loaded > 0:
            print(f"✅ Gist Loader: Successfully loaded {secrets_loaded} secrets.")
            # Also set the correctly identified token for git operations later
            os.environ['ITAMAE_GITHUB_TOKEN'] = token
        else:
            print("⚠️ Gist Loader: No ITAMAE_ secrets found in Gist files.")
            
    except Exception as e:
        print(f"❌ Gist Loader Error: {e}")

def main():
    start_time = time.time()
    if 'INIT_START' not in os.environ:
        os.environ['INIT_START'] = str(int(start_time))

    # 0. Load Cloud Secrets
    load_secrets_from_gist()

    print("🔄 Checking environment...")

    # 1. Clone or Update Repository
    if os.path.exists(".git"):
        print(f"⏳ Updating current directory...")
        run_command("git fetch --depth 1 origin")
        run_command("git reset --hard origin/main")
    elif os.path.exists(REPO_NAME):
        print(f"⏳ Entering and updating {REPO_NAME}...")
        os.chdir(REPO_NAME)
        run_command("git fetch --depth 1 origin")
        run_command("git reset --hard origin/main")
    else:
        print(f"⏳ Cloning {REPO_NAME}...")
        # Use the validated token from Gist Loader if available
        token = os.environ.get('ITAMAE_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
        clone_url = REPO_URL
        if token and "github.com" in clone_url:
            # Mask token in print, but use it in command
            print("🔑 Using GitHub Token for cloning...")
            clone_url = clone_url.replace("https://", f"https://{token}@")
        
        run_command(f"git clone --depth 1 {clone_url}")
        if os.path.exists(REPO_NAME):
            os.chdir(REPO_NAME)
        
    print(f"✅ Code ready ({int(time.time()) - int(os.environ['INIT_START'])}s)")

    # 2. Install Waiter Dependencies (Ultra Fast)
    print("⏳ Calling the Waiter (Installing core dependencies)...")
    if run_command("pip install -r requirements_waiter.txt -q") != 0:
        print("❌ Failed to install core dependencies")
        sys.exit(1)
    print(f"✅ Waiter is here ({int(time.time()) - int(os.environ['INIT_START'])}s)")

    # 3. Run the Bot
    print("🚀 Starting Itamae...")
    run_command("python launcher.py")

if __name__ == "__main__":
    main()
