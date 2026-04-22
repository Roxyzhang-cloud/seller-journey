"""
fix_github_secret.py
Automatically push the local puppy.cfg PUPPY_TOKEN into GitHub repo Secrets.

How it works:
  1. Read puppy_token from ~/.code_puppy/puppy.cfg
  2. Get the repo public key from GitHub API (for encryption)
  3. Encrypt the token using libsodium sealed box
  4. Update PUPPY_TOKEN secret via GitHub API
  5. Trigger the publish workflow

Usage:
  uv run --with PyNaCl scripts/fix_github_secret.py
"""
import base64
import configparser
import json
import sys
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    from nacl.public import PublicKey, SealedBox
except ImportError:
    print("[ERROR] PyNaCl not found. Run with: uv run --with PyNaCl ...")
    sys.exit(1)

# -- Paths -------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent
GH_CFG     = SCRIPT_DIR / "github.cfg"
PUPPY_CFG  = Path.home() / ".code_puppy" / "puppy.cfg"

# -- Proxy (required inside Walmart network) ---------------------------------
proxy = urllib.request.ProxyHandler({
    "http":  "http://sysproxy.wal-mart.com:8080",
    "https": "http://sysproxy.wal-mart.com:8080",
})
urllib.request.install_opener(urllib.request.build_opener(proxy))


def load_config() -> tuple[dict, str]:
    """Load github.cfg and puppy_token."""
    if not GH_CFG.exists():
        print(f"[ERROR] github.cfg not found: {GH_CFG}")
        sys.exit(1)
    gh = configparser.ConfigParser()
    gh.read(GH_CFG, encoding="utf-8")
    cfg = {
        "owner": gh.get("github", "owner"),
        "repo":  gh.get("github", "repo"),
        "token": gh.get("github", "token"),
    }
    if not PUPPY_CFG.exists():
        print(f"[ERROR] puppy.cfg not found: {PUPPY_CFG}")
        sys.exit(1)
    pc = configparser.ConfigParser()
    pc.read(PUPPY_CFG, encoding="utf-8")
    puppy_token = pc.get("puppy", "puppy_token").strip()
    return cfg, puppy_token


def gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type":  "application/json",
    }


def get_repo_public_key(cfg: dict) -> tuple[str, str]:
    """Get the repo's encryption public key. Returns (key_id, key_b64)."""
    url = (f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
           f"/actions/secrets/public-key")
    req = urllib.request.Request(url, headers=gh_headers(cfg["token"]))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())
            return data["key_id"], data["key"]
    except urllib.error.HTTPError as e:
        print(f"[ERROR] Failed to get public key: HTTP {e.code}")
        print("        Check that your GitHub token has 'secrets' write permission.")
        sys.exit(1)


def encrypt_secret(public_key_b64: str, secret_value: str) -> str:
    """Encrypt secret with libsodium sealed box, return base64 ciphertext."""
    pub_key_bytes = base64.b64decode(public_key_b64)
    pub_key       = PublicKey(pub_key_bytes)
    sealed_box    = SealedBox(pub_key)
    encrypted     = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def put_secret(cfg: dict, key_id: str, encrypted_value: str) -> bool:
    """Create/update PUPPY_TOKEN secret via GitHub API."""
    url  = (f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
            f"/actions/secrets/PUPPY_TOKEN")
    body = json.dumps({
        "encrypted_value": encrypted_value,
        "key_id":          key_id,
    }).encode()
    req = urllib.request.Request(
        url, data=body, headers=gh_headers(cfg["token"]), method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status in (201, 204)
    except urllib.error.HTTPError as e:
        err_body = e.read()
        try:
            err = json.loads(err_body)
            msg = err.get('message', str(e))
        except Exception:
            msg = err_body.decode('utf-8', 'replace')[:200]
        print(f"[ERROR] PUT secret failed: HTTP {e.code} - {msg}")
        return False


def trigger_workflow(cfg: dict) -> None:
    """Manually trigger the publish workflow."""
    url  = (f"https://api.github.com/repos/{cfg['owner']}/{cfg['repo']}"
            f"/actions/workflows/publish.yml/dispatches")
    body = json.dumps({"ref": "main"}).encode()
    req  = urllib.request.Request(
        url, data=body, headers=gh_headers(cfg["token"]), method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"[OK] Workflow triggered (HTTP {r.status})")
    except urllib.error.HTTPError as e:
        print(f"[WARN] Trigger failed (HTTP {e.code}) -- do a data push to trigger")


def main() -> None:
    print("=" * 55)
    print("fix_github_secret.py -- Auto-update PUPPY_TOKEN")
    print("=" * 55)

    cfg, puppy_token = load_config()
    print(f"[INFO] Repo: {cfg['owner']}/{cfg['repo']}")
    tlen = len(puppy_token)
    print(f"[INFO] Puppy token: {puppy_token[:16]}...{puppy_token[-4:]} (len={tlen})")

    print("[STEP 1] Getting repo public key...")
    key_id, pub_key_b64 = get_repo_public_key(cfg)
    print(f"         key_id: {key_id}")

    print("[STEP 2] Encrypting PUPPY_TOKEN...")
    encrypted = encrypt_secret(pub_key_b64, puppy_token)
    print(f"         Encrypted ({len(encrypted)} chars) OK")

    print("[STEP 3] Updating PUPPY_TOKEN secret in GitHub...")
    ok = put_secret(cfg, key_id, encrypted)
    if ok:
        print("[OK] PUPPY_TOKEN secret updated!")
    else:
        print("[FAIL] Could not update secret.")
        sys.exit(1)

    print("[STEP 4] Triggering publish workflow...")
    trigger_workflow(cfg)

    print()
    print("Done!")
    print(f"  Actions: https://github.com/{cfg['owner']}/{cfg['repo']}/actions")
    print("  Dashboard: https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard")


if __name__ == "__main__":
    main()
