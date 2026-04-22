"""
export_to_repo.py
本地运行：将本地 SQLite 数据导出为 CSV + 生成 dashboard HTML + git commit + push 到 GitHub

使用方式:
    python scripts/export_to_repo.py
    python scripts/export_to_repo.py --skip-html    # 只导出 CSV，不重生 HTML
    python scripts/export_to_repo.py --message "wk12 data update"

前提:
    1. 本地 tracker 运行在 8765 端口（获取快照用）
    2. 这个脚本放在 GitHub repo 中（已 git clone）
    3. 已配置 git remote origin 指向你的 GitHub repo
"""
import csv
import html as html_lib
import json
import re
import sqlite3
import ssl
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# ── 路径配置 ───────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
REPO_ROOT    = SCRIPT_DIR.parent
DATA_DIR     = REPO_ROOT / "data"
DASH_DIR     = REPO_ROOT / "dashboard"
DASHBOARD    = DASH_DIR / "index.html"

# 找本地 tracker 的 DB （相对于 repo 目录向上找）
TRACKER_CANDIDATES = [
    REPO_ROOT.parent / "call-down-tracker" / "calldown.db",
    Path.home() / "Documents" / "puppy_workspace" / "call-down-tracker" / "calldown.db",
]

# 源 dashboard 模板（同目录的已存在版本）
SOURCE_HTML_CANDIDATES = [
    REPO_ROOT.parent / "seller_journey_dashboard.html",
    Path.home() / "Documents" / "puppy_workspace" / "seller_journey_dashboard.html",
]

TRACKER_PORT = 8765

SNAPSHOTS = [
    ("s1", "/snapshot/s1"),
    ("s2", "/snapshot/s2"),
    ("s3", "/snapshot/s3"),
]
INSIGHTS_PATH = "/insights/embed"


# ── 工具函数 ───────────────────────────────────────────────────────────────────

def _find_path(candidates: list) -> Path | None:
    for p in candidates:
        if p.exists():
            return p
    return None


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _fetch(path: str) -> str | None:
    """Fetch from local tracker. Returns HTML or None."""
    url = f"https://127.0.0.1:{TRACKER_PORT}{path}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url), context=_ssl_ctx(), timeout=12
        ) as resp:
            return resp.read().decode("utf-8", "ignore")
    except Exception as exc:
        print(f"  ⚠️  Tracker unreachable ({path}): {exc}")
        return None


# ── CSV 导出 ───────────────────────────────────────────────────────────────────

def _export_table(conn: sqlite3.Connection, table: str, csv_path: Path) -> int:
    """Dump a SQLite table to CSV. Returns row count."""
    cursor = conn.execute(f"SELECT * FROM {table}")
    cols = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return len(rows)


def export_csvs(db_path: Path) -> None:
    """Export all three tables to CSV in data/."""
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    tables = {
        "sellers":    "s1_sellers.csv",
        "s2_sellers": "s2_sellers.csv",
        "s3_sellers": "s3_sellers.csv",
    }
    for table, fname in tables.items():
        out = DATA_DIR / fname
        n = _export_table(conn, table, out)
        print(f"  ✓ {table} → {fname} ({n} rows)")
    conn.close()


# ── HTML 快照嵌入 ───────────────────────────────────────────────────────────────────

def _embed_snapshots(html: str) -> str:
    """Replace live iframes with srcdoc snapshots (same logic as autopublish.py)."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Disable probeTracker (prevents hiding the srcdoc iframes)
    html = re.sub(
        r"<script>probeTracker\([^)]+\);</script>",
        "<!-- probeTracker disabled: snapshot mode -->",
        html,
    )

    heights = {"s1": 820, "s2": 860, "s3": 880}
    for key, path in SNAPSHOTS:
        fetched = _fetch(path)
        if not fetched:
            print(f"  ⚠️  Skipping {key} — tracker offline")
            continue
        banner = (
            f'<div style="padding:5px 14px;font-size:11px;color:#0369a1;'
            f'background:#f0f9ff;border-top:1px solid #bae6fd;font-family:sans-serif;">'
            f'📸 快照 · {ts} · 编辑请使用本地 Tracker</div>'
        )
        fetched = fetched.replace("</body>", f"{banner}</body>")
        safe = html_lib.escape(fetched, quote=True)
        h = heights.get(key, 820)
        srcdoc_tag = (
            f'<iframe id="{key}-iframe" srcdoc="{safe}" '
            f'class="w-full border-0 block" style="height:{h}px;" '
            f'title="{key.upper()} Snapshot {ts}"></iframe>'
        )
        html = re.sub(
            rf'<iframe\s+id="{key}-iframe"\s+src="[^"]*"[^>]*></iframe>',
            lambda _: srcdoc_tag,
            html, flags=re.DOTALL,
        )
        print(f"  ✓ Embedded {key} snapshot ({len(fetched):,} chars)")

    # Insights
    fetched = _fetch(INSIGHTS_PATH)
    if fetched:
        safe = html_lib.escape(fetched, quote=True)
        ins_tag = (
            f'<iframe srcdoc="{safe}" class="w-full border-0 rounded-xl shadow-sm" '
            f'style="height:1140px;" title="Insights Snapshot {ts}"></iframe>'
        )
        html = re.sub(
            r'<iframe\s[^>]*data-src="[^"]*insights/embed"[^>]*src="about:blank"[^>]*></iframe>',
            lambda _: ins_tag,
            html, flags=re.DOTALL,
        )
        print(f"  ✓ Embedded insights snapshot")

    return html


def build_dashboard_html(source_html: Path) -> None:
    """Generate snapshot-embedded HTML and write to dashboard/index.html."""
    DASH_DIR.mkdir(exist_ok=True)
    original = source_html.read_text(encoding="utf-8")
    print("📸  Embedding tracker snapshots…")
    result = _embed_snapshots(original)
    DASHBOARD.write_text(result, encoding="utf-8")
    print(f"  ✓ Wrote {DASHBOARD} ({len(result) // 1024:,} KB)")


# ── Git 操作 ───────────────────────────────────────────────────────────────────

def _git(args: list[str], cwd: Path = REPO_ROOT) -> tuple[bool, str]:
    """Run a git command. Returns (success, output)."""
    result = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True
    )
    out = (result.stdout + result.stderr).strip()
    return result.returncode == 0, out


def git_commit_and_push(commit_message: str) -> bool:
    """Stage data + dashboard, commit, and push to GitHub."""
    print("📤  Pushing to GitHub…")

    ok, out = _git(["add", "data/", "dashboard/"])
    if not ok:
        print(f"  ❌ git add failed: {out}")
        return False

    ok, out = _git(["status", "--short"])
    if not out.strip():
        print("  ℹ️  Nothing changed — repo is already up to date.")
        return True

    ok, out = _git(["commit", "-m", commit_message])
    if not ok:
        print(f"  ❌ git commit failed: {out}")
        return False
    print(f"  ✓ Committed: {out.splitlines()[0]}")

    ok, out = _git(["push", "origin", "main"])
    if not ok:
        print(f"  ❌ git push failed: {out}")
        print("    提示：确认 remote origin 已指向你的 GitHub repo")
        return False
    print("  ✓ Pushed → GitHub (触发 Actions 自动发布)")
    return True


# ── 主流程 ───────────────────────────────────────────────────────────────────

def main() -> None:
    skip_html = "--skip-html" in sys.argv
    msg_idx = sys.argv.index("--message") if "--message" in sys.argv else -1
    custom_msg = sys.argv[msg_idx + 1] if msg_idx >= 0 and msg_idx + 1 < len(sys.argv) else None

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = custom_msg or f"data: auto-export {ts}"

    print("=" * 60)
    print(f"🐾  export_to_repo.py starting — {ts}")
    print("=" * 60)

    # 1. 找 SQLite DB
    db_path = _find_path(TRACKER_CANDIDATES)
    if not db_path:
        print("❌  calldown.db not found. Is the tracker installed?")
        print(f"   Tried: {TRACKER_CANDIDATES}")
        sys.exit(1)
    print(f"🗄️  Database: {db_path}")

    # 2. 导出 CSV
    print("📄  Exporting CSV data…")
    export_csvs(db_path)

    # 3. 生成 dashboard HTML
    if not skip_html:
        src = _find_path(SOURCE_HTML_CANDIDATES)
        if not src:
            print("⚠️  seller_journey_dashboard.html not found — skipping HTML build.")
            print("   Use --skip-html to suppress this warning.")
        else:
            build_dashboard_html(src)
    else:
        print("⏭️  Skipping HTML build (--skip-html).")

    # 4. Git commit + push
    success = git_commit_and_push(commit_msg)
    if success:
        print()
        print("✅  Done! GitHub Actions will auto-publish in ~1 minute.")
        print("   Watch: https://github.com/<YOUR_ORG>/<REPO>/actions")
        print("   Live:  https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard")
    else:
        print()
        print("❌  Push failed. CSV files are saved locally. Fix git config and retry.")
        sys.exit(1)


if __name__ == "__main__":
    main()
