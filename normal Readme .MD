# TechGrowth Hub — Community CRM + WhatsApp Automation

## 🚀 Deploy on Railway (Permanent — No manual running needed)

### Step 1 — Push to GitHub
```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/techgrowth-hub.git
git push -u origin main
```

### Step 2 — Deploy on Railway
1. Go to **https://railway.app** → Login with GitHub
2. Click **"New Project"** → **"Deploy from GitHub repo"**
3. Select your repo → Railway auto-detects everything
4. Click **Deploy** — done ✅

Railway will:
- Install all dependencies automatically
- Install Chromium for WhatsApp automation
- Start the app permanently (restarts if it crashes)
- Give you a public URL like `https://techgrowth-hub.up.railway.app`

---

### ⚠️ WhatsApp QR Scan (One-time only)

WhatsApp needs a one-time QR scan. Since Railway is headless (no screen), do this locally first:

```bash
pip install -r requirements.txt
python -m playwright install chromium
python techgrowth_hub.py setup     # scan QR on your phone
```

Then copy the session folder to Railway using a **Volume**:
1. In Railway → your service → **Volumes**
2. Mount path: `/app/cg_data`
3. Upload your local `cg_data/wa_session/` folder contents

**Or simpler:** Keep WhatsApp running locally and only host the CRM on Railway.

---

### Environment Variables (set in Railway dashboard)
| Variable | Value |
|----------|-------|
| `PORT` | `8000` (Railway sets this automatically) |
| `COMMUNITY_NAME` | `Python Developer` |

---

## 💻 Run Locally
```bash
pip install -r requirements.txt
python -m playwright install chromium
python techgrowth_hub.py           # starts everything — no extra commands
```

## 🌐 Pages
- `/` — Dashboard
- `/leads` — All Leads  
- `/add-lead` — Add Lead
- `/analytics` — Analytics

## 📱 WhatsApp Commands (run separately if needed)
```bash
python techgrowth_hub.py setup              # first-time QR scan
python techgrowth_hub.py test               # send test messages now
python techgrowth_hub.py post ai_tip        # send a specific post
python techgrowth_hub.py welcome "Name" 91XXXXXXXXXX   # welcome a member
python techgrowth_hub.py dm 91XXXXXXXXXX "message"     # send a DM
```
