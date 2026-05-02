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
    """Loads project secrets from a private GitHub Gist if tokens are provided."""
    token = os.environ.get('ITAMAE_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
    gist_id = os.environ.get('ITAMAE_GIST_ID')
    
    if not token or not gist_id:
        print("ℹ️ Gist Loader: No token or Gist ID found. Skipping cloud secrets.")
        return

    print(f"⏳ Gist Loader: Fetching secrets from Gist {gist_id[:4]}...")
    try:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
        response = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=10)
        response.raise_for_status()
        gist_data = response.json()
        secrets_loaded = 0
        for filename, file_info in gist_data.get('files', {}).items():
            content = file_info['content']

            # Case 1: JSON format
            if filename.endswith('.json'):
                try:
                    data = json.loads(content)
                    for key, value in data.items():
                        if key.startswith("ITAMAE_"):
                            os.environ[key] = str(value)
                            secrets_loaded += 1
                except: pass

            # Case 2: .env format (Key=Value) - Recommended
            elif ".env" in filename:
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key.startswith("ITAMAE_"):
                        os.environ[key] = value
                        secrets_loaded += 1

        if secrets_loaded > 0:
            print(f"✅ Gist Loader: Successfully loaded {secrets_loaded} secrets from GitHub.")
        else:
            print("⚠️ Gist Loader: No valid ITAMAE_ secrets found in Gist.")
            
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
        # We are already inside a git repo, assume it's the right one
        print(f"⏳ Updating current directory...")
        run_command("git fetch --depth 1 origin")
        run_command("git reset --hard origin/main")
    elif os.path.exists(REPO_NAME):
        # Repo exists as a subdirectory
        print(f"⏳ Entering and updating {REPO_NAME}...")
        os.chdir(REPO_NAME)
        run_command("git fetch --depth 1 origin")
        run_command("git reset --hard origin/main")
    else:
        # Need to clone
        print(f"⏳ Cloning {REPO_NAME}...")
        token = os.environ.get('ITAMAE_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
        clone_url = REPO_URL
        if token and "github.com" in clone_url:
            clone_url = clone_url.replace("https://", f"https://{token}@")
        
        run_command(f"git clone --depth 1 {clone_url}")
        os.chdir(REPO_NAME)
        
    print(f"✅ Code ready ({int(time.time()) - int(os.environ['INIT_START'])}s)")

    # 2. Install Waiter Dependencies (Ultra Fast)
    print("⏳ Calling the Waiter (Installing core dependencies)...")
    if run_command("pip install -r requirements_waiter.txt -q") != 0:
        print("❌ Failed to install core dependencies")
        sys.exit(1)
    print(f"✅ Waiter is here ({int(time.time()) - int(os.environ['INIT_START'])}s)")

    # 3. Run the Bot
    print("🚀 Starting TTB...")
    run_command("python launcher.py")

if __name__ == "__main__":
    main()
