# Seller Journey Dashboard — GitHub 共享方案

> **目标**：将数据和 Dashboard 存在 GitHub，BD 共同编辑，每次推送自动发布到 puppy.walmart.com。

---

## 📊 架构图

```
主维护权 (BD Lead)
   │
   ├──► 本地 Tracker (FastAPI + SQLite :8765)
   │         │
   │         ├──► python scripts/export_to_repo.py
   │                    │
   │                    ├──► data/s1_sellers.csv
   │                    ├──► data/s2_sellers.csv
   │                    ├──► data/s3_sellers.csv
   │                    └──► dashboard/index.html (快照嵌入)
   │                              │
   └───────────────────────▼
                    GitHub Repo (main branch)
                              │
                    🤖 GitHub Actions 触发
                              │
                              ▼
               puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard
                              │
                              ▼
               所有 BD 实时查看 ✅ (无需任何安装)

BD 全员存取 GitHub 同步数据：
   git pull → python scripts/sync_from_repo.py → 本地 SQLite 得到最新数据
```

---

## 🛠️ 前置条件：安装 Git（只需一次）

如果你还没有装 Git for Windows，请让 IT 协助安装，或前往：
> **https://gitforwindows.org/**

安装时保持默认选项即可。安装完成后打开新的命令提示符验证：
```bash
git --version   # 应显示 git version 2.x.x
```

---

## ⚡ 主维护权 Setup（只需一次）

### Step 1：创建 GitHub Repo

```bash
# 在 GitHub 上创建一个新 repo，例如： walmart-cn/seller-journey
# 然后把这个目录 push 上去：

cd C:\Users\r0z02di\Documents\puppy_workspace\github-solution
git init
git remote add origin https://github.com/<YOUR_ORG>/seller-journey.git
git add .
git commit -m "init: seller journey dashboard"
git branch -M main
git push -u origin main
```

> 💡 建议设为 **Private** repo，仅外招团队员可访问。

---

### Step 2：设置 PUPPY_TOKEN Secret

1. 找到你的 Code Puppy token：
   ```
   %USERPROFILE%\.code_puppy\puppy.cfg
   ```
   复制 `puppy_token =` 后面的内容

2. 在 GitHub repo 设置 Secret：
   - 进入你的 repo → **Settings → Secrets and variables → Actions**
   - 点 **New repository secret**
   - Name: `PUPPY_TOKEN`
   - Value: 将上面复制的 token 粘贴进去
   - 点 **Add secret** ✅

---

### Step 3：第一次导出数据

确保本地 tracker 已开启，然后：

```bash
cd C:\Users\r0z02di\Documents\puppy_workspace\github-solution
python scripts\export_to_repo.py
```

这个命令会：
1. 将 SQLite 数据导出到 `data/*.csv`
2. 从 Tracker 报快照生成 `dashboard/index.html`
3. `git commit + push` 到 GitHub
4. GitHub Actions 自动在 ~1 分钟内发布到 puppy.walmart.com

---

### Step 4：验证初始发布

1. 查看 Actions 进度： `https://github.com/<YOUR_ORG>/seller-journey/actions`
2. 确认 Dashboard 更新：
   `https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard`

---

## 🔄 日常工作流

### 主维护权：更新数据后发布

```bash
# 1. 在本地 tracker 中编辑数据
# 2. 然后运行：
python scripts\export_to_repo.py --message "wk12 data update"
# ✔ CSV 导出 → HTML 快照 → push 到 GitHub → Actions 自动发布
```

### BD 全员：查看 Dashboard

直接打开链接即可：  
https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard

### BD 全员：同步数据到本地（可选）

如果你有本地 tracker 并想同步最新数据：

```bash
git pull origin main
python scripts\sync_from_repo.py
# 然后重启本地 tracker 就能看到最新数据
```

### 手动触发 GitHub Actions发布

如果不想运行 export 脚本，可以直接在 GitHub 网页上手动触发：  
Repo → **Actions → Publish Seller Journey Dashboard → Run workflow**

---

## 👥 其他 BD 建立连接

各 BD 只需拿到 repo 访问权限，就可以：

```bash
# 克隆 repo
git clone https://github.com/<YOUR_ORG>/seller-journey.git
cd seller-journey

# 查看最新数据
git pull

# 导入到本地 tracker
python scripts\sync_from_repo.py
```

---

## 📂 仓库结构

```
seller-journey/
├── .github/
│   └── workflows/
│       └── publish.yml          # GitHub Actions 自动发布
├── data/
│   ├── s1_sellers.csv         # S1 Drive to Launch 数据
│   ├── s2_sellers.csv         # S2 Cold Start 数据
│   └── s3_sellers.csv         # S3 Seller Quality 数据
├── dashboard/
│   └── index.html             # 自动生成的 Dashboard HTML
├── scripts/
│   ├── export_to_repo.py      # 本地 → GitHub (主维护权运行)
│   ├── sync_from_repo.py      # GitHub → 本地 (BD 同步用)
│   └── github_publish.py      # GitHub Actions 内用，发布到 puppy
├── .gitignore
└── README.md
```

---

## ❓ 常见问题

**Q: GitHub Actions 安全吗？ PUPPY_TOKEN 会泄露吗？**  
A: Token 存在 GitHub Encrypted Secrets 中，完全加密，日志中永远不会显示明文。 ✅

**Q: CSV 文件里包含个人信息，安全吗？**  
A: Walmart InfoSec 允许商业数据（邮筱/电话）存入 Private GitHub repo。
   只要不包含 HIPAA 病人数据或 SSN，就符合安全标准。
   确保 repo 设为 **Private** 并仅授权外招团队员即可。

**Q: Dashboard 多久更新一次？**  
A: 每次有人 push 到 main 分支时自动触发，通常 ~1 分钟内生效。

**Q: 如果 Actions 失败怎么办？**  
A: 去 repo → Actions 查看日志。最常见的原因是 PUPPY_TOKEN 过期或设置错误。

**Q: 我就是想看 Dashboard，不需要调整任何东西，怎么办？**  
A: 直接打开链接即可！  
   `https://puppy.walmart.com/sharing/r0z02di/seller-journey-dashboard`

---

## 🛠️ 高级用法

### 将 export 集成到现有 autopublish.py

在 `autopublish.py` 的 `main()` 函数最后添加：

```python
# 发布到 puppy 后，同时同步到 GitHub
import subprocess, pathlib
repo = pathlib.Path.home() / "Documents" / "puppy_workspace" / "github-solution"
subprocess.run(["python", "scripts/export_to_repo.py", "--skip-html",
                "--message", f"auto: hourly sync {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
               cwd=repo)
```

这样每次小时发布时，数据也会自动同步到 GitHub。

---

## 📞 帮助

- Code Puppy 内部支持： `#element-genai-support` Slack 频道
- 学习资源： https://puppy.walmart.com/doghouse
