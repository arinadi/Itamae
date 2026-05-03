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

def load_secrets():
    """Loads secrets using Option B (Private Repository File).
    Assumes other core secrets are already set in the environment by the Colab cell.
    """
    # 1. Primary: Private Repository File (Option B)
    token = os.environ.get('ITAMAE_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
    config_url = os.environ.get('ITAMAE_CONFIG_URL')
    
    if token and config_url:
        print(f"🔐 Option B: Fetching private config from cloud...")
        try:
            url = config_url
            headers = {"Authorization": f"token {token}"}
            
            # Convert Raw URLs to API URLs for reliable PAT authentication
            if "raw.githubusercontent.com" in url:
                # Format: https://raw.githubusercontent.com/user/repo/branch/path
                p = url.replace("https://raw.githubusercontent.com/", "").split("/", 3)
                if len(p) >= 4: url = f"https://api.github.com/repos/{p[0]}/{p[1]}/contents/{p[3]}?ref={p[2]}"
            elif "github.com" in url and "/raw/" in url:
                # Format: https://github.com/user/repo/raw/branch/path
                p = url.replace("https://github.com/", "").replace("/raw/", "/").split("/", 3)
                if len(p) >= 4: url = f"https://api.github.com/repos/{p[0]}/{p[1]}/contents/{p[3]}?ref={p[2]}"
            
            if "api.github.com" in url:
                headers["Accept"] = "application/vnd.github.v3.raw"
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            content = response.text
            
            loaded = 0
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line: continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k.startswith("ITAMAE_"):
                    os.environ[k] = v
                    loaded += 1
            if loaded > 0: 
                print(f"✅ Option B: Loaded {loaded} secrets. Skipping Colab Secrets.")
                return 
        except Exception as e:
            print(f"⚠️ Option B failed: {e}")

def main():
    start_time = time.time()
    if 'INIT_START' not in os.environ:
        os.environ['INIT_START'] = str(int(start_time))

    # 0. Load Cloud Secrets (Colab -> Private Repo -> Env)
    load_secrets()

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
        # Use the validated token from setup if available
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
