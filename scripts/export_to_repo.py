"""
export_to_repo.py
本地运行：将本地 SQLite 数据导出为 CSV + 生成 Dashboard HTML + 通过 GitHub API 推送

不需要本地安装 git！通过 GitHub REST API 直接推送。

使用方式:
    python scripts/export_to_repo.py
    python scripts/export_to_repo.py --skip-html    # 只导出 CSV
    python scripts/export_to_repo.py --message "wk12 data update"

配置文件: scripts/github.cfg
"""
import base64
import configparser
import csv
import html as html_lib
import json
import re
import sqlite3
import ssl
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# ── 路径 ─────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT  = SCRIPT_DIR.parent
DATA_DIR   = REPO_ROOT / "data"
DASH_DIR   = REPO_ROOT / "dashboard"
DASHBOARD  = DASH_DIR / "index.html"
GH_CFG     = SCRIPT_DIR / "github.cfg"

DB_CANDIDATES = [
    REPO_ROOT.parent / "call-down-tracker" / "calldown.db",
    Path.home() / "Documents" / "puppy_workspace" / "call-down-tracker" / "calldown.db",
]
SRC_HTML_CANDIDATES = [
    REPO_ROOT.parent / "seller_journey_dashboard.html",
    Path.home() / "Documents" / "puppy_workspace" / "seller_journey_dashboard.html",
]

TRACKER_PORT  = 8765
SNAPSHOTS     = [("s1","/snapshot/s1"),("s2","/snapshot/s2"),("s3","/snapshot/s3")]
INSIGHTS_PATH = "/insights/embed"

PUPPY_CFG     = Path.home() / ".code_puppy" / "puppy.cfg"
PUPPY_API_URL = "https://puppy.walmart.com/api/sharing/upload"
PUPPY_PAGE    = "seller-journey-dashboard"


# ── 配置加载 ─────────────────────────────────────────────────────────────
def load_cfg() -> dict:
    """Load GitHub repo config from scripts/github.cfg."""
    if not GH_CFG.exists():
        print(f"❌  github.cfg not found at {GH_CFG}")
        print("   请创建该文件，参考 github.cfg.template")
        sys.exit(1)
    cfg = configparser.ConfigParser()
    cfg.read(GH_CFG, encoding="utf-8")
    return {
        "owner": cfg.get("github", "owner"),
        "repo":  cfg.get("github", "repo"),
        "token": cfg.get("github", "token"),
    }


# ── GitHub API ─────────────────────────────────────────────────────────────
GITHUB_API = "https://api.github.com"

def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept":        "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type":  "application/json",
    }

def _gh_get(cfg: dict, path: str) -> dict:
    url = f"{GITHUB_API}/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}"
    req = urllib.request.Request(url, headers=_gh_headers(cfg["token"]))
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"__not_found__": True}
        raise

def _gh_put(cfg: dict, path: str, content_bytes: bytes, message: str, sha: str | None) -> bool:
    url  = f"{GITHUB_API}/repos/{cfg['owner']}/{cfg['repo']}/contents/{path}"
    body = {"message": message, "content": base64.b64encode(content_bytes).decode()}
    if sha:
        body["sha"] = sha
    data = json.dumps(body).encode()
    req  = urllib.request.Request(url, data=data, headers=_gh_headers(cfg["token"]), method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            json.loads(r.read())  # consume response
            return True
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())
        print(f"    ❌ GitHub PUT {path} failed ({e.code}): {err.get('message',str(e))}")
        return False


# ── CSV 导出 ─────────────────────────────────────────────────────────────
def _export_table(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    cursor = conn.execute(f"SELECT * FROM {table}")
    cols   = [d[0] for d in cursor.description]
    rows   = cursor.fetchall()
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)

def export_csvs(db_path: Path) -> dict[str, Path]:
    DATA_DIR.mkdir(exist_ok=True)
    conn   = sqlite3.connect(db_path)
    tables = {"sellers": "s1_sellers.csv",
              "s2_sellers": "s2_sellers.csv",
              "s3_sellers": "s3_sellers.csv"}
    paths  = {}
    for table, fname in tables.items():
        out = DATA_DIR / fname
        n   = _export_table(conn, table, out)
        print(f"  ✓ {table} → {fname} ({n} 行)")
        paths[fname] = out
    conn.close()
    return paths


# ── Dashboard 快照 ─────────────────────────────────────────────────────────────
def _ssl_ctx():
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx

def _fetch(path: str) -> str | None:
    url = f"https://127.0.0.1:{TRACKER_PORT}{path}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url),
                                    context=_ssl_ctx(), timeout=12) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as exc:
        print(f"  ⚠️  Tracker offline ({path}): {exc}")
        return None

def build_dashboard_html(source_html: Path) -> bytes | None:
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
    html = source_html.read_text(encoding="utf-8")
    html = re.sub(r"<script>probeTracker\([^)]+\);</script>",
                  "<!-- probeTracker disabled: snapshot mode -->", html)
    heights = {"s1": 820, "s2": 860, "s3": 880}
    for key, path in SNAPSHOTS:
        fetched = _fetch(path)
        if not fetched:
            continue
        banner = (f'<div style="padding:5px 14px;font-size:11px;color:#0369a1;'
                  f'background:#f0f9ff;border-top:1px solid #bae6fd;font-family:sans-serif;">'
                  f'📸 快照 · {ts}</div>')
        fetched = fetched.replace("</body>", f"{banner}</body>")
        safe    = html_lib.escape(fetched, quote=True)
        h       = heights.get(key, 820)
        srcdoc  = (f'<iframe id="{key}-iframe" srcdoc="{safe}" '
                   f'class="w-full border-0 block" style="height:{h}px;"></iframe>')
        html = re.sub(rf'<iframe\s+id="{key}-iframe"\s+src="[^"]*"[^>]*></iframe>',
                      lambda _: srcdoc, html, flags=re.DOTALL)
        print(f"  ✓ Embedded {key} snapshot")
    fetched = _fetch("/insights/embed")
    if fetched:
        safe   = html_lib.escape(fetched, quote=True)
        ins    = (f'<iframe srcdoc="{safe}" class="w-full border-0 rounded-xl shadow-sm" '
                  f'style="height:1140px;"></iframe>')
        html   = re.sub(r'<iframe\s[^>]*data-src="[^"]*insights/embed"[^>]*></iframe>',
                        lambda _: ins, html, flags=re.DOTALL)
        print("  ✓ Embedded insights")
    return html.encode("utf-8")


# ── GitHub 推送 (API) ─────────────────────────────────────────────────────────────
def push_to_github(cfg: dict, file_paths: dict[str, Path], commit_msg: str) -> tuple[int, int]:
    """Push local files to GitHub via API. Returns (ok_count, fail_count)."""
    ok = fail = 0
    import time
    for repo_path, local_path in file_paths.items():
        info = _gh_get(cfg, repo_path)
        sha  = info.get("sha") if "__not_found__" not in info else None
        content = local_path.read_bytes()
        success  = _gh_put(cfg, repo_path, content, commit_msg, sha)
        if success:
            print(f"  ✓ Pushed {repo_path}")
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)
    return ok, fail


# -- Publish to puppy.walmart.com (local, direct) ---------------------------
def _load_puppy_token() -> str | None:
    """Read puppy_token from ~/.code_puppy/puppy.cfg."""
    if not PUPPY_CFG.exists():
        return None
    cfg = configparser.ConfigParser()
    cfg.read(PUPPY_CFG, encoding="utf-8")
    return cfg.get("puppy", "puppy_token", fallback=None)


def _publish_to_puppy(html_path: Path) -> bool:
    """Publish dashboard/index.html directly to puppy.walmart.com."""
    token = _load_puppy_token()
    if not token:
        print("  [SKIP] puppy.cfg not found or token missing.")
        return False
    html_content = html_path.read_text(encoding="utf-8")
    payload = json.dumps({
        "name":         PUPPY_PAGE,
        "business":     "general",
        "html_content": html_content,
        "description":  "Seller Journey Dashboard (GitHub auto-export)",
        "access_level": "business",
    }).encode("utf-8")
    req = urllib.request.Request(
        PUPPY_API_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            if result.get("success"):
                ver = result.get("data", {}).get("version", "?")
                print(f"  [OK] Published v{ver} -> https://puppy.walmart.com/sharing/r0z02di/{PUPPY_PAGE}")
                return True
            print(f"  [FAIL] {result}")
            return False
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read()).get("detail", str(exc))
        except Exception:
            detail = str(exc)
        print(f"  [FAIL] HTTP {exc.code}: {detail}")
        return False
    except Exception as exc:
        print(f"  [FAIL] {exc}")
        return False


# -- Main flow ----------------------------------------------------------------
def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    skip_html  = "--skip-html"  in sys.argv
    msg_idx    = sys.argv.index("--message") if "--message" in sys.argv else -1
    custom_msg = sys.argv[msg_idx + 1] if 0 <= msg_idx < len(sys.argv)-1 else None
    ts         = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = custom_msg or f"data: auto-export {ts}"

    print("=" * 55)
    print(f"🐾  export_to_repo.py — {ts}")
    print("=" * 55)

    # 1. 读取 GitHub 配置
    cfg = load_cfg()
    print(f"🔗  Repo: {cfg['owner']}/{cfg['repo']}")

    # 2. 找 SQLite DB
    db_path = next((p for p in DB_CANDIDATES if p.exists()), None)
    if not db_path:
        print(f"❌  calldown.db not found. Tried: {DB_CANDIDATES}")
        sys.exit(1)
    print(f"🗄️  DB: {db_path}")

    # 3. 导出 CSV
    print("📄  Exporting CSVs...")
    csv_paths  = export_csvs(db_path)
    to_push    = {f"data/{fname}": path for fname, path in csv_paths.items()}

    # 4. 生成 Dashboard HTML
    if not skip_html:
        src = next((p for p in SRC_HTML_CANDIDATES if p.exists()), None)
        if src:
            print("📸  Building dashboard snapshot...")
            html_bytes = build_dashboard_html(src)
            if html_bytes:
                DASH_DIR.mkdir(exist_ok=True)
                DASHBOARD.write_bytes(html_bytes)
                to_push["dashboard/index.html"] = DASHBOARD
                print(f"  ✓ HTML ready ({len(html_bytes)//1024:,} KB)")
        else:
            print("⚠️  seller_journey_dashboard.html not found — skipping HTML.")
    else:
        # Still push existing HTML if it was pre-written by autopublish
        if DASHBOARD.exists():
            to_push["dashboard/index.html"] = DASHBOARD
            print("⏭️  Using pre-built dashboard/index.html (--skip-html)")

    # 5. Push to GitHub via API
    print(f"📤  Pushing {len(to_push)} files to GitHub...")
    ok, fail = push_to_github(cfg, to_push, commit_msg)
    print(f"  ✓ {ok} pushed, ❌ {fail} failed")

    if ok > 0:
        print()
        print("  GitHub data synced!")
        print(f"  Actions: https://github.com/{cfg['owner']}/{cfg['repo']}/actions")
    else:
        print("  All files failed to push — check github.cfg token")
        sys.exit(1)

    # 6. Publish directly to puppy.walmart.com (local publish, no GitHub Actions needed)
    if "dashboard/index.html" in to_push:
        print("\nPublishing to puppy.walmart.com...")
        _publish_to_puppy(to_push["dashboard/index.html"])
    else:
        print("  Skipping puppy publish (no dashboard HTML).")

    print()
    print("Done!")
    print(f"  Live: https://puppy.walmart.com/sharing/r0z02di/{PUPPY_PAGE}")


if __name__ == "__main__":
    main()
