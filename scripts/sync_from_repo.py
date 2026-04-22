"""
sync_from_repo.py
BD 本地运行：从 GitHub 拉取最新数据 → 导入到本地 SQLite

适用场景:
    - BD 全员 git pull 后可以同步最新数据到自己的本地 tracker
    - 不需要 tracker 服务运行
使用方式:
    python scripts/sync_from_repo.py
    python scripts/sync_from_repo.py --dry-run    # 只预览，不嵌入
"""
import csv
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT  = SCRIPT_DIR.parent
DATA_DIR   = REPO_ROOT / "data"

# 找本地 calldown.db
DB_CANDIDATES = [
    REPO_ROOT.parent / "call-down-tracker" / "calldown.db",
    Path.home() / "Documents" / "puppy_workspace" / "call-down-tracker" / "calldown.db",
]

TABLE_MAP = {
    "s1_sellers.csv": "sellers",
    "s2_sellers.csv": "s2_sellers",
    "s3_sellers.csv": "s3_sellers",
}


def _find_db() -> Path | None:
    for p in DB_CANDIDATES:
        if p.exists():
            return p
    return None


def sync_csv_to_table(conn: sqlite3.Connection, csv_path: Path, table: str) -> int:
    """
    Upsert all rows from CSV into the SQLite table.
    Uses INSERT OR REPLACE so existing rows are updated.
    """
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return 0

    cols = list(rows[0].keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

    conn.executemany(sql, [[r[c] for c in cols] for r in rows])
    conn.commit()
    return len(rows)


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    print("🐾  sync_from_repo.py")
    print("-" * 40)

    # Check data dir
    if not DATA_DIR.exists():
        print(f"❌  data/ directory not found at {DATA_DIR}")
        print("   Did you git clone the repo correctly?")
        sys.exit(1)

    if dry_run:
        print("🔍  Dry run mode — showing what would be imported:")
        for fname in TABLE_MAP:
            p = DATA_DIR / fname
            if p.exists():
                with p.open(newline="", encoding="utf-8") as f:
                    n = sum(1 for _ in csv.reader(f)) - 1
                print(f"  {fname} → {TABLE_MAP[fname]}: {n} rows")
            else:
                print(f"  {fname}: NOT FOUND")
        return

    db_path = _find_db()
    if not db_path:
        print("❌  calldown.db not found.")
        print("   Is the tracker installed? Run start.bat first to initialize the DB.")
        sys.exit(1)

    print(f"🗄️  Writing to: {db_path}")
    conn = sqlite3.connect(db_path)

    for fname, table in TABLE_MAP.items():
        csv_path = DATA_DIR / fname
        if not csv_path.exists():
            print(f"  ⚠️  {fname} not found — skipping")
            continue
        n = sync_csv_to_table(conn, csv_path, table)
        print(f"  ✓ {fname} → {table} ({n} rows upserted)")

    conn.close()
    print()
    print("✅  Sync complete! Restart tracker to see updated data.")


if __name__ == "__main__":
    main()
