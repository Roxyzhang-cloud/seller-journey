"""
github_publish.py
在 GitHub Actions 中运行：读取 dashboard/index.html → 发布到 puppy.walmart.com

所需环境变量:
    PUPPY_TOKEN  (在 GitHub Repo Settings → Secrets 中设置)
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

# ── 配置 ───────────────────────────────────────────────────────────────────
REPO_ROOT    = Path(__file__).parent.parent
DASHBOARD    = REPO_ROOT / "dashboard" / "index.html"

APP_NAME     = "seller-journey-dashboard"
APP_DESC     = "Seller Journey Call-Down Dashboard (GitHub Auto-Published)"
API_URL      = "https://puppy.walmart.com/api/sharing/upload"
BUSINESS     = "general"
ACCESS_LEVEL = "business"


def _stamp_html(html: str) -> str:
    """把 GitHub Actions 的 build timestamp 注入到 HTML 里。"""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sha = os.environ.get("GITHUB_SHA", "local")[:7]
    actor = os.environ.get("GITHUB_ACTOR", "auto")
    banner = (
        f'<div style="position:fixed;bottom:0;left:0;right:0;z-index:9999;'
        f'padding:4px 16px;font-size:11px;color:#1e3a5f;background:#dbeafe;'
        f'border-top:1px solid #93c5fd;font-family:sans-serif;text-align:center;">'
        f'🤖 GitHub Auto-Published · {ts} · commit <code>{sha}</code> · by {actor}</div>'
    )
    return html.replace("</body>", f"{banner}</body>")


def publish(html_content: str, token: str) -> dict:
    """Post HTML to the puppy.walmart.com sharing API."""
    payload = {
        "name":         APP_NAME,
        "business":     BUSINESS,
        "html_content": html_content,
        "description":  APP_DESC,
        "access_level": ACCESS_LEVEL,
    }
    resp = requests.post(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {token}",
        },
        timeout=60,
    )
    try:
        return resp.json()
    except Exception:
        return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}


def main() -> None:
    token = os.environ.get("PUPPY_TOKEN", "").strip()
    if not token:
        print("❌  PUPPY_TOKEN not set — add it in GitHub Repo → Settings → Secrets.")
        sys.exit(1)

    if not DASHBOARD.exists():
        print(f"❌  Dashboard file not found: {DASHBOARD}")
        print("    Make sure you have run scripts/export_to_repo.py locally and pushed.")
        sys.exit(1)

    print(f"📄  Loading dashboard ({DASHBOARD.stat().st_size // 1024:,} KB)…")
    html = DASHBOARD.read_text(encoding="utf-8")

    html = _stamp_html(html)

    print(f"🚀  Publishing '{APP_NAME}' to puppy.walmart.com…")
    result = publish(html, token)

    if result.get("success"):
        version = result.get("data", {}).get("version", "?")
        url = f"https://puppy.walmart.com/sharing/r0z02di/{APP_NAME}"
        print(f"✅  Published v{version} → {url}")
    else:
        print(f"❌  Publish failed: {result.get('error', result)}")
        sys.exit(2)


if __name__ == "__main__":
    main()
