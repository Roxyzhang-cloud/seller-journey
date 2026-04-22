# Seller Journey Dashboard — GitHub Sync Solution

> **Goal**: Store data & dashboard in GitHub for version control. BD Lead runs one command to sync data to GitHub AND publish to puppy.walmart.com.

---

## Architecture

```
BD Lead (local machine on Walmart Eagle/VPN)
   │
   ├──► python scripts/export_to_repo.py
   │         │
   │         ├── Step 1: Export SQLite → CSV  (data/*.csv)
   │         ├── Step 2: Build dashboard snapshot (dashboard/index.html)
   │         ├── Step 3: Push all files to GitHub via API ✅
   │         └── Step 4: Publish to puppy.walmart.com directly ✅
   │
   ▼
  GitHub Repo (Roxyzhang-cloud/seller-journey)
   │  (data versioned, team can pull & sync to local tracker)
   │
   ▼
  puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard
  (all BD view in browser, no install needed)

> Note: GitHub Actions cannot publish to puppy.walmart.com
> because puppy is Walmart-internal (Eagle/VPN only).
> Publishing is done directly from the local machine.
```

---

## Prerequisites (one-time)

Make sure `scripts/github.cfg` has your GitHub token configured:
```ini
[github]
owner = Roxyzhang-cloud
repo  = seller-journey
token = ghp_YOUR_TOKEN_HERE
```

If your `PUPPY_TOKEN` in GitHub Secrets expires, re-run:
```bash
uv run --with PyNaCl scripts/fix_github_secret.py
```

---

## Daily Workflow (BD Lead)

### Update data + publish dashboard

```bash
cd C:\Users\r0z02di\Documents\puppy_workspace\github-solution
python scripts\export_to_repo.py
```

This single command:
1. Exports S1/S2/S3 data from SQLite → GitHub CSVs
2. Captures live tracker snapshots into the HTML
3. Pushes data to GitHub (for team versioning)
4. Publishes directly to puppy.walmart.com (~30 sec)

```bash
# With a custom commit message:
python scripts\export_to_repo.py --message "wk12 data update"

# Skip HTML rebuild (use existing snapshot):
python scripts\export_to_repo.py --skip-html
```

### View Dashboard (all BD)

Just open:
https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard

### Sync data to local tracker (optional)

If you have a local tracker and want the latest data:
```bash
git pull origin main
python scripts\sync_from_repo.py
# Then restart local tracker to see fresh data
```

---

## Repository Structure

```
seller-journey/
├── .github/
│   └── workflows/
│       └── publish.yml          # GitHub Actions (kept for reference)
├── data/
│   ├── s1_sellers.csv
│   ├── s2_sellers.csv
│   └── s3_sellers.csv
├── dashboard/
│   └── index.html               # Latest dashboard snapshot
├── scripts/
│   ├── export_to_repo.py        # Main script: export + push + publish
│   ├── fix_github_secret.py     # Fix PUPPY_TOKEN in GitHub Secrets
│   ├── sync_from_repo.py        # Pull GitHub data to local tracker
│   └── github_publish.py        # (used by GitHub Actions, reference only)
├── github.cfg                   # GitHub token config (DO NOT commit)
└── README.md
```

---

## FAQ

**Q: Why doesn't GitHub Actions publish to puppy.walmart.com?**
A: `puppy.walmart.com` is on Walmart's internal network (Eagle/VPN). GitHub Actions runs on public GitHub servers which cannot reach it. Publishing happens locally from your machine instead.

**Q: Is the data safe in GitHub?**
A: Walmart InfoSec allows business data (emails/phones) in Private GitHub repos. No HIPAA patient data or SSN. Keep the repo **Private** and restricted to your team.

**Q: How often should I publish?**
A: Run `export_to_repo.py` whenever you update data in the tracker. Weekly is typical.

**Q: My GitHub token expired, how to fix?**
A: Generate a new Fine-grained token at github.com with `contents` + `secrets` + `actions` write permission. Update `scripts/github.cfg`. Then run `fix_github_secret.py` to update the GitHub Secret.

**Q: PUPPY_TOKEN expired?**
A: Restart Code Puppy (token auto-refreshes). Then run: `uv run --with PyNaCl scripts/fix_github_secret.py`

---

## Help

- Code Puppy support: `#element-genai-support` on Slack
- Learning: https://puppy.walmart.com/doghouse
