"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       TechGrowth Hub — Community CRM + Growth Automation System             ║
║                  All-in-one single file  •  Python 3.9+                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  WHAT THIS DOES:                                                             ║
║  ── WEB CRM ──────────────────────────────────────────────────────────────  ║
║  • FastAPI web dashboard (leads, pipeline, analytics)                       ║
║  • SQLite-backed lead management (add/edit/delete/notes)                    ║
║  • Auto-classification of notes by keyword                                   ║
║  • Follow-up reminders, overdue alerts, analytics                           ║
║  ── WHATSAPP AUTOMATION ───────────────────────────────────────────────────  ║
║  • Auto welcome new members (WhatsApp DM)                                   ║
║  • Auto daily content posts (AI tips, coding, growth, tools, LinkedIn)      ║
║  • Auto motivational messages + daily challenges                            ║
║  • Auto inactive member reminders                                           ║
║  • Auto onboarding DM sequence (day 0/1/3/7/14)                            ║
║  • Auto referral + invite tracking → Google Sheets                          ║
║  • Auto leaderboard generation + weekly posting                             ║
║  • Auto engagement tracking → Google Sheets                                 ║
║  • Auto content scheduling (7 AM–8 PM daily)                               ║
║  ── SHARED ────────────────────────────────────────────────────────────────  ║
║  • HTML analytics dashboard generator                                       ║
║  • Full CLI for manual community management                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  QUICK START:                                                                ║
║    pip install fastapi uvicorn jinja2 playwright schedule selenium           ║
║    python -m playwright install chromium                                    ║
║                                                                              ║
║    python techgrowth_hub.py web         ← start CRM web server (port 8000) ║
║    python techgrowth_hub.py setup       ← first-time WhatsApp QR scan      ║
║    python techgrowth_hub.py run         ← start WhatsApp scheduler         ║
║    python techgrowth_hub.py both        ← web + scheduler together         ║
║    python techgrowth_hub.py help        ← all CLI commands                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ══════════════════════════════════════════════════════════════════════════════
# STDLIB IMPORTS
# ══════════════════════════════════════════════════════════════════════════════
import argparse
import json
import logging
import os
import random
import sqlite3
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def _configure_console_encoding():
    """Avoid Windows console crashes when printing Unicode text."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_configure_console_encoding()


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 1 — SHARED CONFIGURATION  ░░
# ══════════════════════════════════════════════════════════════════════════════

# ─── Google Sheets ────────────────────────────────────────────────────────────
GOOGLE_SHEETS_WEBHOOK = (
    "https://script.google.com/macros/s/"
    "AKfycbx_VORrjFaUc-TF3-7W2PATIgZ_2DsJ-EFmvYBHLd5h3J2EUma32GafICA33dIkCRWp/exec"
)
SHEET_MEMBERS      = "Members"
SHEET_ENGAGEMENT   = "Engagement"
SHEET_REFERRALS    = "Referrals"
SHEET_LEADERBOARD  = "Leaderboard"
SHEET_CONTENT      = "ContentSchedule"
SHEET_ANALYTICS    = "Analytics"

# ─── Community ────────────────────────────────────────────────────────────────
COMMUNITY_NAME       = "TechGrowth Hub"
COMMUNITY_TAGLINE    = "Where Tech Meets Growth 🚀"
WHATSAPP_INVITE_LINK = "https://chat.whatsapp.com/KWJwv2TkjXi0ZPWQ60aA5k"
TARGET_MEMBERS       = 1000
CURRENT_MEMBERS      = 425

# ─── Schedule (24-hour strings) ───────────────────────────────────────────────
DAILY_SCHEDULE = {
    "morning_tip":        "07:00",
    "networking_prompt":  "10:00",
    "afternoon_tool":     "13:00",
    "daily_challenge":    "17:00",
    "inactive_reminders": "19:00",
    "night_recap":        "20:00",
}
INACTIVITY_DAYS = 3

# ─── Points & Rewards ─────────────────────────────────────────────────────────
REFERRAL_POINTS = {
    "invite_accepted":    10,
    "daily_message":       2,
    "react_to_post":       1,
    "share_resource":      5,
    "complete_challenge":  8,
    "help_member":         6,
}
REWARD_TIERS = {
    "Bronze":   {"min": 0,    "max": 49,   "badge": "🥉"},
    "Silver":   {"min": 50,   "max": 149,  "badge": "🥈"},
    "Gold":     {"min": 150,  "max": 299,  "badge": "🥇"},
    "Platinum": {"min": 300,  "max": 599,  "badge": "💎"},
    "Legend":   {"min": 600,  "max": 9999, "badge": "🏆"},
}

# ─── Onboarding Sequence ──────────────────────────────────────────────────────
ONBOARDING_SEQUENCE = [
    {"day": 0,  "type": "welcome",         "delay_hours": 0},
    {"day": 1,  "type": "orientation",     "delay_hours": 24},
    {"day": 3,  "type": "first_challenge", "delay_hours": 72},
    {"day": 7,  "type": "week_check_in",   "delay_hours": 168},
    {"day": 14, "type": "referral_nudge",  "delay_hours": 336},
]

# ─── CRM Config ───────────────────────────────────────────────────────────────
LEAD_STATUSES = [
    "NEW", "CONTACTED", "REPLIED", "QUALIFIED",
    "DEMO_BOOKED", "DEMO_COMPLETED", "PILOT", "CUSTOMER", "LOST"
]
LEAD_SOURCES = [
    "Cold Call", "Website", "Referral", "LinkedIn",
    "Email Campaign", "WhatsApp", "Exhibition", "Partner", "Other"
]
PAIN_POINTS = [
    "Fee Collection", "Attendance Tracking", "Parent Communication",
    "Student Management", "Exam Management", "Timetable", "Other"
]

# ─── File Paths ───────────────────────────────────────────────────────────────
BASE_DIR     = Path(__file__).parent
DATA_DIR     = BASE_DIR / "cg_data"
LOG_DIR      = BASE_DIR / "cg_logs"
SESSION_DIR  = DATA_DIR / "wa_session"
MEMBERS_DB   = DATA_DIR / "members.json"
ANALYTICS_DB = DATA_DIR / "analytics.json"
CRM_DB_PATH  = str(BASE_DIR / "nova_teach_crm.db")

for _d in (DATA_DIR, LOG_DIR, SESSION_DIR, BASE_DIR / "templates", BASE_DIR / "static"):
    _d.mkdir(parents=True, exist_ok=True)

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "system.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("techgrowth_hub")


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 2 — CONTENT LIBRARY  ░░
# ══════════════════════════════════════════════════════════════════════════════

AI_TIPS = [
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "Use *chain-of-thought prompting* to get smarter AI answers.\n\n"
            "Instead of: _'Explain machine learning'_\n"
            "Try: _'Think step-by-step. What is ML, how does it work, and give a "
            "real-world healthcare example?'_\n\n"
            "You'll get 3× more useful output. 💡\n\n#AITips #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "*Prompt engineering is the new skill gap.*\n\n"
            "People earning $150k+ in AI aren't all ML engineers — many are prompt "
            "engineers who extract value from LLMs.\n\n"
            "Free resource 👇\nhttps://learnprompting.org — Start today.\n\n"
            "#PromptEngineering #AICareer #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "ChatGPT + Notion = your personal second brain.\n\n"
            "Workflow:\n1️⃣ Dump raw notes into ChatGPT\n"
            "2️⃣ Ask it to structure + summarize\n3️⃣ Export clean notes to Notion\n\n"
            "Save 2+ hours every week. ✅\n\n#Productivity #AITools #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "*The 'Act As' trick doubles AI quality.*\n\n"
            "Start prompts with: _'Act as a senior [role] with 10 years of experience...'_\n\n"
            "The AI shifts into expert mode. Domain-specific. Precise.\n\n"
            "#AIHacks #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "FREE AI tools you should be using RIGHT NOW:\n\n"
            "🔸 Perplexity.ai — AI search engine\n"
            "🔸 Gamma.app — AI presentations\n"
            "🔸 Otter.ai — AI meeting notes\n"
            "🔸 Runway — AI video editing\n"
            "🔸 ElevenLabs — AI voice generation\n\n"
            "Bookmark this. 📌\n\n#FreeAITools #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "Use AI to *prepare for job interviews* — not just apply.\n\n"
            "Paste the job description + your resume into ChatGPT and ask:\n"
            "_'What are the top 10 questions they'll ask and the ideal answers?'_\n\n"
            "This is worth $10k in salary negotiation power. 💰\n\n"
            "#JobSearch #AICareer #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "*Cursor AI* is replacing traditional IDEs for 1M+ developers.\n\n"
            "VS Code + AI pair programmer. You write intent → AI writes code.\n\n"
            "Free tier at cursor.sh\nYour coding speed: 3–5× faster.\n\n"
            "#CursorAI #DevTools #TechGrowthHub"
        ),
    },
    {
        "title": "🤖 AI Tip of the Day",
        "body": (
            "The *Feynman Technique* + AI = supercharged learning.\n\n"
            "1️⃣ Learn a concept\n"
            "2️⃣ Explain it to ChatGPT like it's a 10-year-old\n"
            "3️⃣ Ask: 'What did I miss or get wrong?'\n"
            "4️⃣ Fill the gaps\n\n"
            "You'll retain 80% more. Science-backed. ✅\n\n"
            "#LearningHacks #TechGrowthHub"
        ),
    },
]

CODING_TIPS = [
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "*Write code for the next developer, not just the machine.*\n\n"
            "Bad: `x = lst[0] * 1.08`\nGood:\n"
            "```python\nTAX_RATE = 0.08\n"
            "price_with_tax = prices[0] * (1 + TAX_RATE)\n```\n\n"
            "Self-documenting code saves teams hundreds of hours. 🧠\n\n"
            "#CleanCode #Python #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "If you're not using *GitHub Copilot*, you're working too hard.\n\n"
            "It writes boilerplate, suggests completions, explains code.\n"
            "Students get it *FREE* with GitHub Education.\n\n"
            "Apply at: education.github.com\n\n#GitHubCopilot #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "*Python one-liners every dev should know:*\n\n"
            "Swap values:    `a, b = b, a`\n"
            "Flatten list:   `[x for sub in nested for x in sub]`\n"
            "Reverse string: `s[::-1]`\n"
            "Most frequent:  `max(lst, key=lst.count)`\n\n"
            "Save this. 🎯\n\n#Python #CodingTips #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "The *1 commit message rule* senior devs swear by:\n\n"
            "❌ `git commit -m 'fix stuff'`\n"
            "✅ `git commit -m 'fix: prevent crash when user list is empty (#204)'`\n\n"
            "Format: `type: short description (ticket#)`\n"
            "Types: feat | fix | docs | refactor | test | chore\n\n"
            "#Git #BestPractices #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "*SQL query you'll use every week:*\n\n"
            "```sql\nSELECT user_id,\n"
            "  COUNT(*) as total_orders,\n"
            "  SUM(amount) as revenue,\n"
            "  AVG(amount) as avg_order\n"
            "FROM orders\n"
            "WHERE created_at >= NOW() - INTERVAL '30 days'\n"
            "GROUP BY user_id\nORDER BY revenue DESC\nLIMIT 10;\n```\n\n"
            "Top 10 customers last 30 days. 📌\n\n#SQL #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "*REST API design in 60 seconds:*\n\n"
            "✅ Use nouns: `/users` not `/getUsers`\n"
            "✅ Use plural: `/products` not `/product`\n"
            "✅ HTTP methods: GET=read, POST=create, PUT=update, DELETE=remove\n"
            "✅ Status codes: 200, 201, 400, 401, 404, 500\n\n"
            "Clean APIs = happy teams. 🤝\n\n#API #WebDev #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "FREE roadmaps for every tech career:\n\n"
            "🗺️ roadmap.sh\n\n"
            "Covers Frontend / Backend / DevOps / Cloud / AI / Cyber Security.\n"
            "Structured. Free. Community-driven. ⭐\n\n"
            "#LearningPath #TechGrowthHub"
        ),
    },
    {
        "title": "💻 Coding Tip of the Day",
        "body": (
            "The *10x developer mindset* isn't about typing faster.\n"
            "It's about solving the right problem.\n\n"
            "Before writing code, ask:\n"
            "1. Should this even be built?\n"
            "2. Can I use an existing library/API?\n"
            "3. What's the simplest version that works?\n\n"
            "Measure twice, cut once. 🪚\n\n#SoftwareEngineering #TechGrowthHub"
        ),
    },
]

GROWTH_HACKS = [
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*The 'Give Before You Ask' framework.*\n\n"
            "90% of people only take. Be in the 10% who give first:\n\n"
            "→ Answer 3 questions before posting your own\n"
            "→ Share a resource without asking for credit\n"
            "→ Introduce two people who should know each other\n\n"
            "This compounds. In 90 days you'll be unmissable. 🚀\n\n"
            "#NetworkingHacks #TechGrowthHub"
        ),
    },
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*The LinkedIn Comment > Post strategy.*\n\n"
            "Find 10 creators in your niche. Comment meaningfully on their posts "
            "WITHIN 30 minutes of them posting.\n\n"
            "You appear in front of their audience. Daily. For free.\n"
            "0 → 5k followers in 6 months. 📊\n\n"
            "#LinkedInGrowth #PersonalBranding #TechGrowthHub"
        ),
    },
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*Build in public — the fastest growth strategy.*\n\n"
            "Share your process, not just your results.\n\n"
            "Week 1: 'I'm learning X'\n"
            "Week 4: 'Here's what I built with X'\n"
            "Week 8: 'Here's what I'd do differently'\n\n"
            "People follow journeys, not destinations. 💪\n\n"
            "#BuildInPublic #TechGrowthHub"
        ),
    },
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*The 3-2-1 newsletter formula:*\n\n"
            "Every week send:\n"
            "3 ideas worth sharing\n"
            "2 resources you found useful\n"
            "1 question to spark thinking\n\n"
            "Start free on beehiiv.com — free up to 2,500 subscribers.\n\n"
            "#Newsletter #ContentCreation #TechGrowthHub"
        ),
    },
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*Referral loops beat ads every time.*\n\n"
            "If every member invites just 1 person this week,\n"
            "this community doubles. From 425 → 850 in 7 days.\n\n"
            "Your action today:\n"
            f"👉 Forward this link to ONE person who deserves to be here:\n"
            f"{WHATSAPP_INVITE_LINK}\n\n"
            "#Referral #CommunityGrowth #TechGrowthHub"
        ),
    },
    {
        "title": "📈 Growth Hack of the Day",
        "body": (
            "*The Content Repurposing machine:*\n\n"
            "Create ONCE → Distribute EVERYWHERE\n\n"
            "1 blog post →\n"
            "  5 LinkedIn posts\n"
            "  10 tweets\n"
            "  1 YouTube script\n"
            "  1 email newsletter\n"
            "  3 community posts\n\n"
            "Tools: Taplio, Typefully, Notion AI\n\n"
            "#ContentStrategy #TechGrowthHub"
        ),
    },
]

NETWORKING_PROMPTS = [
    {
        "title": "🤝 Networking Prompt",
        "body": (
            "*Reply with your 1-line intro:*\n\n"
            "Format: `[Name] | [Role] | [1 thing you're working on]`\n\n"
            "Example: `Priya | ML Engineer | Building fraud detection for fintech`\n\n"
            "React with 🙌 when you've introduced yourself! 👋\n\n"
            "#Networking #TechGrowthHub"
        ),
    },
    {
        "title": "🤝 Collab Corner",
        "body": (
            "*Who's looking for a technical co-founder or collaborator?*\n\n"
            "Reply with:\n"
            "🔹 What you're building\n"
            "🔹 Skills you're looking for\n"
            "🔹 Stage (idea / MVP / launched)\n\n"
            "This group has builders. Let's connect them. 🔗\n\n"
            "#Cofounder #Startup #TechGrowthHub"
        ),
    },
    {
        "title": "🤝 Skill Swap",
        "body": (
            "*Got a skill? Need a skill?*\n\n"
            "✅ I can help with: [your skill]\n"
            "🙏 I'd love help with: [skill you need]\n\n"
            "Example:\n"
            "✅ I can help with: React & TypeScript\n"
            "🙏 I'd love help with: AWS deployment\n\n"
            "Match someone today. DM them. 📩\n\n#SkillSwap #TechGrowthHub"
        ),
    },
    {
        "title": "🤝 Win of the Week",
        "body": (
            "*Share your WIN from this week — big or small!*\n\n"
            "🏆 'Shipped my first API'\n"
            "🏆 'Got a callback for a senior role'\n"
            "🏆 'Hit 100 LinkedIn followers'\n"
            "🏆 'Fixed a 3-day-old bug'\n\n"
            "We celebrate progress here. React with 🔥 to someone's win!\n\n"
            "#WinOfTheWeek #TechGrowthHub"
        ),
    },
    {
        "title": "🤝 Ask Me Anything",
        "body": (
            "*Drop your #1 tech question below.*\n\n"
            "❓ Career advice\n"
            "❓ Tech stack decisions\n"
            "❓ Job search strategy\n"
            "❓ Learning path confusion\n\n"
            "Someone in this community has the answer.\n"
            "Ask. Don't stay stuck. 🙋\n\n#AMA #TechGrowthHub"
        ),
    },
]

FREE_TOOLS = [
    {
        "title": "🛠 Free Tool Spotlight",
        "body": (
            "*Tool: Excalidraw* (excalidraw.com)\n\n"
            "Free virtual whiteboard for hand-drawn diagrams.\n\n"
            "✅ System design interviews\n"
            "✅ Architecture diagrams\n"
            "✅ Brainstorming sessions\n\n"
            "No login needed. Works in browser. 100% free. ✨\n\n"
            "#FreeTools #DevTools #TechGrowthHub"
        ),
    },
    {
        "title": "🛠 Free Tool Spotlight",
        "body": (
            "*Tool: Postman* (postman.com)\n\n"
            "The #1 API testing tool used by 25M+ developers.\n\n"
            "✅ Test REST/GraphQL APIs\n"
            "✅ Automate API tests\n"
            "✅ Mock servers\n"
            "✅ Share collections with your team\n\n#Postman #TechGrowthHub"
        ),
    },
    {
        "title": "🛠 Free Tool Spotlight",
        "body": (
            "*Tool: Railway.app*\n\n"
            "Deploy full-stack apps in under 5 minutes. No DevOps required.\n\n"
            "✅ $5/month free credits\n"
            "✅ PostgreSQL, Redis, MySQL included\n"
            "✅ Auto-deploy from GitHub\n"
            "✅ Custom domains\n\n"
            "Perfect for side projects. 🚂\n\n#Railway #Deployment #TechGrowthHub"
        ),
    },
    {
        "title": "🛠 Free Tool Spotlight",
        "body": (
            "*Tool: Notion* (notion.so) — Free for personal use.\n\n"
            "Power user templates:\n"
            "📋 Job application tracker\n"
            "📋 Project management board\n"
            "📋 Learning notes database\n"
            "📋 Personal CRM\n\n"
            "notion.com/templates → free packs 📌\n\n#Notion #Productivity #TechGrowthHub"
        ),
    },
    {
        "title": "🛠 Free Tool Spotlight",
        "body": (
            "*Tool: Figma* (figma.com) — Industry standard design tool.\n\n"
            "Even as a developer, knowing Figma means:\n"
            "✅ Better collaboration with designers\n"
            "✅ You can prototype your own ideas\n"
            "✅ Huge career advantage 💼\n\n"
            "youtube.com/c/figma → learn in 2 hours\n\n#Figma #UIDesign #TechGrowthHub"
        ),
    },
]

OPPORTUNITIES = [
    {
        "title": "🌟 Opportunity Alert",
        "body": (
            "*FREE certifications that actually matter:*\n\n"
            "☁️ AWS Cloud Practitioner — aws.amazon.com/training\n"
            "🔐 Google Cybersecurity — Coursera (financial aid)\n"
            "🤖 DeepLearning.AI — deeplearning.ai\n"
            "📊 Meta Data Analyst — Coursera\n"
            "🐍 Python Institute — free entry-level exam\n\n"
            "Pick one. Start this weekend. Finish in 4–8 weeks. 📜\n\n"
            "#FreeCertifications #CareerGrowth #TechGrowthHub"
        ),
    },
    {
        "title": "🌟 Opportunity Alert",
        "body": (
            "*Remote tech jobs actively hiring:*\n\n"
            "🔍 remoteok.com\n"
            "🔍 weworkremotely.com\n"
            "🔍 wellfound.com (startups)\n"
            "🔍 levels.fyi (salary transparency)\n"
            "🔍 ycombinator.com/jobs\n\n"
            "Apply to 5 today. Numbers game. 🎯\n\n#RemoteJobs #TechGrowthHub"
        ),
    },
    {
        "title": "🌟 Opportunity Alert",
        "body": (
            "*Big Tech FREE courses — claim yours:*\n\n"
            "📘 Google: grow.google/certificates\n"
            "📘 Microsoft: learn.microsoft.com\n"
            "📘 Meta: facebook.com/business/learn\n"
            "📘 IBM: skillsbuild.org\n"
            "📘 Amazon: aws.amazon.com/free\n\n"
            "All free. All industry-recognised. 📚\n\n#FreeEducation #TechGrowthHub"
        ),
    },
    {
        "title": "🌟 Opportunity Alert",
        "body": (
            "*Top freelance platforms for tech people:*\n\n"
            "💰 Toptal — top 3%, premium rates\n"
            "💰 Upwork — volume + variety\n"
            "💰 Contra — commission-free\n"
            "💰 Lemon.io — vetting + placement\n"
            "💰 Gun.io — developer-focused\n\n"
            "Side income → full income → freedom. 🏄\n\n"
            "#Freelance #TechIncome #TechGrowthHub"
        ),
    },
]

LINKEDIN_POSTS = [
    {
        "title": "💼 LinkedIn Post Template — Copy & Customise",
        "body": (
            "Use this on LinkedIn today:\n\n"
            "────────────\n"
            "6 months ago I was [STRUGGLE].\n\n"
            "Today I [ACHIEVEMENT].\n\n"
            "Here's what I did differently:\n\n"
            "1/ [Lesson 1]\n2/ [Lesson 2]\n3/ [Lesson 3]\n\n"
            "The #1 thing that changed everything: [Key insight]\n\n"
            "If you're in the same place I was 6 months ago — keep going. 🙌\n"
            "────────────\n\n"
            "Consistently gets 500–5,000+ impressions. ✍️\n\n"
            "#LinkedInTips #PersonalBrand #TechGrowthHub"
        ),
    },
    {
        "title": "💼 LinkedIn Hook Templates",
        "body": (
            "The first line = 90% of your LinkedIn reach.\n\n"
            "10 proven hooks:\n\n"
            "1. 'I was wrong about [topic]. Here's what I learned:'\n"
            "2. '[Number] things I wish I knew before [experience]:'\n"
            "3. 'Unpopular opinion: [controversial take]'\n"
            "4. 'I [achieved X] in [timeframe]. Here's the exact process:'\n"
            "5. 'Stop doing [common thing]. Do this instead:'\n"
            "6. 'Nobody talks about [underrated topic]. Let me change that.'\n"
            "7. 'The [role] job market is brutal. Here's how to stand out:'\n"
            "8. 'I reviewed 500 [resumes]. Here's what I saw:'\n"
            "9. 'This one question changed my entire [career]:'\n"
            "10. 'Hot take: [industry] is about to [change].'\n\n"
            "Write your post in 20 minutes. 📝\n\n#LinkedInGrowth #TechGrowthHub"
        ),
    },
]

DAILY_CHALLENGES = [
    {
        "title": "🏆 Daily Challenge",
        "body": (
            "*TODAY'S CHALLENGE: The Intro Post*\n\n"
            "Write a 3-sentence LinkedIn post introducing yourself.\n"
            "Post it. Screenshot it. Share it here.\n\n"
            "🎯 Goal: Build your personal brand muscle\n"
            "⏱ Time: 15 minutes\n"
            "🏅 Points: 8 community points\n\n"
            "React with 💪 when done!\n\n#DailyChallenge #TechGrowthHub"
        ),
    },
    {
        "title": "🏆 Daily Challenge",
        "body": (
            "*TODAY'S CHALLENGE: The Cold DM*\n\n"
            "Send a value-first cold DM to one person you admire on LinkedIn.\n\n"
            "Template:\n"
            "'Hi [Name], I [specific compliment]. I'm [brief intro]. "
            "I'd love to [specific ask]. Thanks!'\n\n"
            "🎯 Goal: Expand your network intentionally\n"
            "⏱ Time: 10 minutes  🏅 Points: 8\n\n"
            "Tell us how it went! 📩\n\n#DailyChallenge #TechGrowthHub"
        ),
    },
    {
        "title": "🏆 Daily Challenge",
        "body": (
            "*TODAY'S CHALLENGE: Teach Something*\n\n"
            "Share ONE thing you learned this week in the group.\n\n"
            "→ A keyboard shortcut\n"
            "→ A Python trick\n"
            "→ A career lesson\n"
            "→ A tool you discovered\n\n"
            "🎯 Goal: Reinforce your learning + help others\n"
            "⏱ Time: 5 minutes  🏅 Points: 5\n\n"
            "Drop your knowledge bomb below 💣\n\n#TechGrowthHub"
        ),
    },
    {
        "title": "🏆 Daily Challenge",
        "body": (
            "*TODAY'S CHALLENGE: Build Your GitHub*\n\n"
            "Push at least one commit today — any project, any size.\n\n"
            "No project? Start one:\n"
            "→ Build a CLI tool\n"
            "→ Scrape a website\n"
            "→ Make a simple REST API\n\n"
            "🎯 Goal: Daily coding habit  ⏱ Time: 30–60 min  🏅 Points: 8\n\n"
            "Share your GitHub link in the group! 🔗\n\n#TechGrowthHub"
        ),
    },
]

MOTIVATIONAL_MESSAGES = [
    (
        "💬 *Thought for the day:*\n\n"
        "_'The best time to start was yesterday. The second best time is now.'_\n\n"
        "Whatever you've been putting off — start today. Not perfectly. Just start. 🚀\n\n"
        "#Motivation #TechGrowthHub"
    ),
    (
        "🌅 Good morning, builders!\n\n"
        "Reminder: You don't need to be perfect to make progress.\n\n"
        "Ship the imperfect version.\nSend the imperfect message.\nWrite the imperfect post.\n\n"
        "Done > Perfect. Every time. ✅\n\n#MorningMotivation #TechGrowthHub"
    ),
    (
        "💡 *The compound effect of small actions:*\n\n"
        "→ 1 coding hour/day = 365 hours/year\n"
        "→ 1 LinkedIn post/week = 52 posts/year\n"
        "→ 1 new connection/day = 365 connections/year\n\n"
        "You don't need big moves. You need consistent small ones.\n"
        "What's your small action today? 👇\n\n#ConsistencyWins #TechGrowthHub"
    ),
]

WELCOME_TEMPLATES = [
    (
        "🎉 Welcome to *TechGrowth Hub*, {name}!\n\n"
        "You've just joined a community of builders, learners, and growth-minded tech people.\n\n"
        "📌 *Community Rules:*\n"
        "✅ Add value before asking for it\n"
        "✅ Share knowledge freely\n"
        "✅ Respect everyone — no spam\n\n"
        "🚀 *What you'll get here daily:*\n"
        "→ AI & coding tips\n→ Career opportunities\n"
        "→ Free tools\n→ Networking events\n→ Community challenges\n\n"
        "Drop your intro: Name | Role | What you're building 💬\n\n_Welcome home._ 🏡"
    ),
    (
        "👋 {name}, welcome to *TechGrowth Hub*!\n\n"
        "You're now part of {member_count}+ tech professionals growing together.\n\n"
        "*Your first 3 actions:*\n"
        "1️⃣ Drop your intro in the group\n"
        "2️⃣ Connect with 2 members\n"
        "3️⃣ Share one resource or tip\n\n"
        "We grow when we give. Let's build something great together. 🔥"
    ),
]

INACTIVITY_TEMPLATES = [
    (
        "Hey {name}! 👋\n\n"
        "We miss you in *TechGrowth Hub*!\n\n"
        "You haven't been active for a few days. Here's what you missed:\n\n"
        "🔥 5 AI tips + 3 free tools + 4 job opportunities\n\n"
        "One message changes your day — and someone else's.\n"
        "Come back and say hi! 💬"
    ),
    (
        "Quick check-in, {name}! 🙌\n\n"
        "The community is buzzing — don't miss out.\n\n"
        "This week alone:\n"
        "→ 5 actionable tips\n→ 3 free tools\n→ 4 job opportunities\n\n"
        "Takes 30 seconds to jump back in. We'll be here. 🏠"
    ),
]

ONBOARDING_TEMPLATES = {
    "welcome": (
        "🎉 Hey {name}! Welcome to *TechGrowth Hub*!\n\n"
        "I'm the community bot. Here's your quick start:\n\n"
        "1️⃣ Introduce yourself in the group\n"
        "2️⃣ React to posts to earn points\n"
        "3️⃣ Share one tip this week\n\n"
        "We're glad you're here. Big things are coming. 🚀"
    ),
    "orientation": (
        "👋 {name}, Day 2 check-in!\n\n"
        "Daily schedule:\n"
        "→ 7AM: AI or coding tip\n→ 10AM: Networking prompt\n"
        "→ 1PM: Free tool\n→ 5PM: Daily challenge\n→ 8PM: Leaderboard\n\n"
        "Every invite, message, and share earns you points.\n"
        "Top 10 are featured in the weekly leaderboard. 🏆"
    ),
    "first_challenge": (
        "🏆 {name}, it's challenge time!\n\n"
        "Day 3 challenge: Write one LinkedIn post today.\n\n"
        "Topic ideas:\n→ Something you learned\n"
        "→ A tool you discovered\n→ A mistake that taught you something\n\n"
        "Share the link in the group → earn 8 community points. 💪"
    ),
    "week_check_in": (
        "🌟 {name}, you've been here a week!\n\n"
        "Quick check:\n"
        "✅ Made any new connections?\n"
        "✅ Shared any tips?\n"
        "✅ Completed any challenges?\n\n"
        "The members who grow fastest here contribute first.\n\n"
        f"*Your invite link:*\n{WHATSAPP_INVITE_LINK}\n\n"
        "Every invite = 10 points + moves you up the leaderboard. 🎯"
    ),
    "referral_nudge": (
        "💰 {name}, here's a growth opportunity.\n\n"
        "You've been here 2 weeks. Our goal: 1,000 members.\n"
        "Currently at {current_count}+.\n\n"
        "Invite rewards:\n"
        "🔸 3 invites → Silver 🥈\n"
        "🔸 10 invites → Gold 🥇\n"
        "🔸 25 invites → Platinum 💎\n"
        "🔸 50 invites → Legend 🏆 + featured spotlight\n\n"
        f"Invite link:\n{WHATSAPP_INVITE_LINK}\n\n"
        "Forward to one smart person today. 📲"
    ),
}


def get_content(content_type: str, offset: int = 0) -> Any:
    """Return today's content for a given type (deterministic daily rotation)."""
    day_idx = date.today().timetuple().tm_yday + offset
    pool_map = {
        "ai_tip":            AI_TIPS,
        "coding_tip":        CODING_TIPS,
        "growth_hack":       GROWTH_HACKS,
        "networking_prompt": NETWORKING_PROMPTS,
        "free_tool":         FREE_TOOLS,
        "opportunity":       OPPORTUNITIES,
        "linkedin_post":     LINKEDIN_POSTS,
        "daily_challenge":   DAILY_CHALLENGES,
        "motivational":      MOTIVATIONAL_MESSAGES,
    }
    pool = pool_map.get(content_type, AI_TIPS)
    return pool[day_idx % len(pool)]


def format_content(content: Any) -> str:
    if isinstance(content, dict):
        return f"{content['title']}\n\n{content['body']}"
    return content


def welcome_message(name: str, member_count: int = CURRENT_MEMBERS) -> str:
    tpl = random.choice(WELCOME_TEMPLATES)
    return tpl.format(name=name, member_count=member_count)


def inactivity_message(name: str) -> str:
    return random.choice(INACTIVITY_TEMPLATES).format(name=name)


def onboarding_message(step_type: str, name: str, current_count: int = CURRENT_MEMBERS) -> str:
    tpl = ONBOARDING_TEMPLATES.get(step_type, "")
    return tpl.format(name=name, current_count=current_count)


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 3 — GOOGLE SHEETS INTEGRATION  ░░
# ══════════════════════════════════════════════════════════════════════════════

def _webhook_post(action: str, payload: Dict) -> Optional[Dict]:
    body = json.dumps({"action": action, **payload}).encode("utf-8")
    req  = urllib.request.Request(
        GOOGLE_SHEETS_WEBHOOK, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.error("Webhook POST [%s] error: %s", action, e)
        return None


def _webhook_get(params: Dict) -> Optional[Dict]:
    url = f"{GOOGLE_SHEETS_WEBHOOK}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        logger.error("Webhook GET error: %s", e)
        return None


def sheets_add_member(member_id, name, phone="", source="organic", referred_by="") -> bool:
    ok = bool(_webhook_post("append_row", {
        "sheet": SHEET_MEMBERS,
        "row": {
            "member_id": member_id, "name": name, "phone": phone,
            "join_date": datetime.now().isoformat(), "source": source,
            "referred_by": referred_by, "points": 0, "tier": "Bronze",
            "badge": "🥉", "last_active": datetime.now().isoformat(),
            "status": "active", "messages_sent": 0, "invites_sent": 0,
            "invites_accepted": 0,
        },
    }))
    if ok and referred_by:
        sheets_award_points(referred_by, "invite_accepted", f"Referred {name}")
    return ok


def sheets_update_active(member_id: str) -> bool:
    return bool(_webhook_post("update_cell", {
        "sheet": SHEET_MEMBERS, "key_col": "member_id", "key_val": member_id,
        "col": "last_active", "val": datetime.now().isoformat(),
    }))


def sheets_get_inactive(days: int = 3) -> List[Dict]:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    res = _webhook_get({"action": "query_rows", "sheet": SHEET_MEMBERS,
                        "filter": f"last_active < {cutoff}", "status": "active"})
    return res.get("rows", []) if res else []


def sheets_get_all_members() -> List[Dict]:
    res = _webhook_get({"action": "get_rows", "sheet": SHEET_MEMBERS})
    return res.get("rows", []) if res else []


def _get_tier(points: int):
    for tier, cfg in REWARD_TIERS.items():
        if cfg["min"] <= points <= cfg["max"]:
            return tier, cfg["badge"]
    return "Bronze", "🥉"


def sheets_award_points(member_id: str, action: str, note: str = "") -> int:
    pts = REFERRAL_POINTS.get(action, 0)
    if not pts:
        return 0
    res = _webhook_post("increment_points", {
        "sheet": SHEET_MEMBERS, "member_id": member_id, "points": pts,
        "action": action, "note": note, "timestamp": datetime.now().isoformat(),
    })
    new_total = (res or {}).get("new_total", 0)
    tier, badge = _get_tier(new_total)
    for col, val in (("tier", tier), ("badge", badge)):
        _webhook_post("update_cell", {
            "sheet": SHEET_MEMBERS, "key_col": "member_id",
            "key_val": member_id, "col": col, "val": val,
        })
    return new_total


def sheets_leaderboard(top_n: int = 10) -> List[Dict]:
    res = _webhook_get({"action": "top_members", "sheet": SHEET_MEMBERS,
                        "sort_by": "points", "limit": str(top_n)})
    members = (res or {}).get("rows", [])
    board = [
        {"rank": i + 1, "name": m.get("name", "?"), "tier": m.get("tier", "Bronze"),
         "badge": m.get("badge", "🥉"), "points": m.get("points", 0),
         "invites": m.get("invites_accepted", 0), "messages": m.get("messages_sent", 0)}
        for i, m in enumerate(members)
    ]
    _webhook_post("overwrite_sheet", {
        "sheet": SHEET_LEADERBOARD, "rows": board,
        "timestamp": datetime.now().isoformat(),
    })
    return board


def format_leaderboard(board: List[Dict]) -> str:
    medals = ["🥇", "🥈", "🥉"]
    lines  = [
        f"🏆 *WEEKLY LEADERBOARD — {COMMUNITY_NAME}* 🏆\n",
        f"_Updated: {date.today().strftime('%d %b %Y')}_\n",
    ]
    for e in board[:10]:
        r = e["rank"]
        m = medals[r - 1] if r <= 3 else f"{r}."
        lines.append(f"{m} *{e['name']}* {e['badge']} — {e['points']} pts | {e['invites']} invites")
    lines.append(
        "\n\n💡 *Earn points by:*\n"
        "→ Inviting members (+10pts)\n→ Daily messages (+2pts)\n"
        "→ Sharing resources (+5pts)\n→ Completing challenges (+8pts)\n\n"
        "React with 🔥 if you're gunning for the top spot!"
    )
    return "\n".join(lines)


def sheets_log_engagement(member_id: str, action_type: str, content_ref: str = "") -> bool:
    if action_type == "message":
        _webhook_post("increment_field", {"sheet": SHEET_MEMBERS, "key_col": "member_id",
                                          "key_val": member_id, "field": "messages_sent"})
        sheets_award_points(member_id, "daily_message")
    return bool(_webhook_post("append_row", {
        "sheet": SHEET_ENGAGEMENT,
        "row": {"timestamp": datetime.now().isoformat(), "member_id": member_id,
                "action_type": action_type, "content_ref": content_ref,
                "date": date.today().isoformat()},
    }))


def sheets_daily_stats() -> Dict:
    res = _webhook_get({"action": "daily_stats", "sheet": SHEET_ENGAGEMENT,
                        "date": date.today().isoformat()})
    s = res or {}
    return {"date": date.today().isoformat(), "active_members": s.get("unique_members", 0),
            "total_messages": s.get("total_messages", 0), "reactions": s.get("reactions", 0),
            "shares": s.get("shares", 0), "new_members": s.get("new_members", 0),
            "invites_sent": s.get("invites_sent", 0)}


def sheets_track_referral(referrer_id: str, new_id: str, new_name: str) -> bool:
    ok = bool(_webhook_post("append_row", {
        "sheet": SHEET_REFERRALS,
        "row": {"timestamp": datetime.now().isoformat(), "referrer_id": referrer_id,
                "new_member_id": new_id, "new_member_name": new_name,
                "status": "completed", "points_awarded": REFERRAL_POINTS["invite_accepted"]},
    }))
    if ok:
        _webhook_post("increment_field", {"sheet": SHEET_MEMBERS, "key_col": "member_id",
                                          "key_val": referrer_id, "field": "invites_accepted"})
    return ok


def sheets_log_post(post_type: str, preview: str, sched_time: str, status: str = "pending") -> bool:
    return bool(_webhook_post("append_row", {
        "sheet": SHEET_CONTENT,
        "row": {"date": date.today().isoformat(), "scheduled_time": sched_time,
                "post_type": post_type, "content_preview": preview[:100],
                "status": status, "created_at": datetime.now().isoformat()},
    }))


def sheets_save_analytics(stats: Dict) -> bool:
    stats["timestamp"] = datetime.now().isoformat()
    return bool(_webhook_post("append_row", {"sheet": SHEET_ANALYTICS, "row": stats}))


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 4 — CRM DATABASE  ░░
# ══════════════════════════════════════════════════════════════════════════════

def get_db():
    conn = sqlite3.connect(CRM_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            institute_name TEXT NOT NULL,
            contact_person TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            city TEXT,
            lead_source TEXT,
            status TEXT DEFAULT 'NEW',
            pain_point TEXT,
            notes TEXT DEFAULT '',
            last_contact_date TEXT,
            next_followup_date TEXT,
            demo_date TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            note TEXT NOT NULL,
            classification TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE CASCADE
        )
        """)
        count = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        if count == 0:
            sample = [
                ("Sunrise Academy", "Rajesh Sharma", "9876543210", "rajesh@sunrise.edu", "Ahmedabad", "Cold Call", "QUALIFIED", "Fee Collection", "2024-01-15", "2024-01-22", None),
                ("Bright Future School", "Priya Patel", "9988776655", "priya@brightfuture.edu", "Surat", "LinkedIn", "DEMO_BOOKED", "Attendance Tracking", "2024-01-14", "2024-01-20", "2024-01-25"),
                ("Knowledge Hub Institute", "Amit Desai", "9123456789", "amit@knowledgehub.edu", "Vadodara", "Referral", "NEW", "Parent Communication", None, date.today().isoformat(), None),
                ("Excel Learning Center", "Sneha Joshi", "9012345678", "sneha@excel.edu", "Rajkot", "Website", "CONTACTED", "Student Management", "2024-01-10", date.today().isoformat(), None),
                ("Genius Kids Academy", "Ravi Mehta", "9876501234", "ravi@geniuskids.edu", "Ahmedabad", "Cold Call", "CUSTOMER", "Fee Collection", "2024-01-05", None, "2024-01-12"),
                ("Star Institute", "Deepa Shah", "9856321470", "deepa@star.edu", "Surat", "Email Campaign", "LOST", "Timetable", "2024-01-08", None, None),
                ("Pioneer School", "Kiran Modi", "9741258963", "kiran@pioneer.edu", "Gandhinagar", "Referral", "DEMO_COMPLETED", "Exam Management", "2024-01-13", "2024-01-21", "2024-01-18"),
                ("Future Leaders Institute", "Anita Rao", "9630147852", "anita@futureleaders.edu", "Ahmedabad", "WhatsApp", "PILOT", "Fee Collection", "2024-01-12", "2024-01-25", "2024-01-15"),
            ]
            for s in sample:
                conn.execute("""
                    INSERT INTO leads (institute_name, contact_person, phone, email, city,
                    lead_source, status, pain_point, last_contact_date, next_followup_date, demo_date)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """, s)


def classify_note(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["attendance", "present", "absent", "biometric"]):
        return "ATTENDANCE"
    if any(w in t for w in ["fee", "fees", "payment", "dues", "invoice", "challan"]):
        return "FEES"
    if any(w in t for w in ["parent", "guardian", "father", "mother", "family"]):
        return "PARENT_COMMUNICATION"
    if any(w in t for w in ["demo", "presentation", "walkthrough"]):
        return "DEMO"
    if any(w in t for w in ["follow", "call", "callback", "ring", "contact"]):
        return "FOLLOWUP"
    return "GENERAL"


def get_lead(lead_id: int):
    with db_conn() as conn:
        lead = conn.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
        if not lead:
            return None
        return dict(lead)


def get_lead_notes(lead_id: int):
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM lead_notes WHERE lead_id=? ORDER BY created_at DESC", (lead_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def today_str():
    return date.today().isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 5 — WHATSAPP BOT  ░░
# ══════════════════════════════════════════════════════════════════════════════

class WhatsAppBot:
    WA_URL  = "https://web.whatsapp.com"
    TIMEOUT = 20_000

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._page = self._browser = self._context = self._pw = None

    def start(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Install playwright: pip install playwright && python -m playwright install chromium")
            return False
        self._pw      = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        session_file = str(SESSION_DIR / "state.json")
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
            storage_state=session_file if Path(session_file).exists() else None,
            viewport={"width": 1280, "height": 800},
        )
        self._page = self._context.new_page()
        self._page.goto(self.WA_URL, wait_until="domcontentloaded")
        if not Path(session_file).exists():
            logger.info("No session found. Please scan the QR code (120s timeout)...")
            self._page.wait_for_selector("div[data-testid='chat-list-search']", timeout=120_000)
            self._context.storage_state(path=session_file)
            logger.info("Session saved — future runs will be headless ✓")
        else:
            try:
                self._page.wait_for_selector("div[data-testid='chat-list-search']", timeout=30_000)
            except Exception:
                logger.warning("Session may be expired. Delete cg_data/wa_session/ and re-run setup.")
                return False
        logger.info("WhatsApp Web ready ✓")
        return True

    def stop(self):
        if self._context:
            self._context.storage_state(path=str(SESSION_DIR / "state.json"))
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _open_chat(self, name: str) -> bool:
        try:
            box = self._page.wait_for_selector("div[data-testid='chat-list-search']", timeout=10_000)
            box.click()
            time.sleep(0.4)
            self._page.keyboard.type(name, delay=80)
            time.sleep(1.5)
            self._page.wait_for_selector(f"span[title='{name}']", timeout=self.TIMEOUT).click()
            time.sleep(0.8)
            return True
        except Exception as e:
            logger.error("Could not open chat '%s': %s", name, e)
            return False

    def _type_and_send(self, message: str) -> bool:
        try:
            inp = self._page.wait_for_selector(
                "div[data-testid='conversation-compose-box-input']", timeout=10_000)
            inp.click()
            for i, line in enumerate(message.split("\n")):
                self._page.keyboard.type(line, delay=25)
                if i < message.count("\n"):
                    self._page.keyboard.press("Shift+Enter")
            time.sleep(0.4)
            self._page.keyboard.press("Enter")
            time.sleep(0.8)
            return True
        except Exception as e:
            logger.error("Send failed: %s", e)
            return False

    def send_group(self, message: str, group_name: str = COMMUNITY_NAME) -> bool:
        if not self._page:
            return False
        return self._open_chat(group_name) and self._type_and_send(message)

    def send_dm(self, phone: str, message: str) -> bool:
        if not self._page:
            return False
        try:
            self._page.goto(f"https://web.whatsapp.com/send?phone={phone}", wait_until="domcontentloaded")
            time.sleep(3)
            try:
                self._page.wait_for_selector("a[data-action='continue']", timeout=4_000).click()
                time.sleep(1.5)
            except Exception:
                pass
            return self._type_and_send(message)
        except Exception as e:
            logger.error("DM to %s failed: %s", phone, e)
            return False


class WhatsAppBotSelenium:
    WA_URL = "https://web.whatsapp.com"

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.driver   = None

    def start(self) -> bool:
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            opts = Options()
            if self.headless:
                opts.add_argument("--headless=new")
            opts.add_argument("--no-sandbox")
            opts.add_argument(f"--user-data-dir={SESSION_DIR}")
            self.driver = webdriver.Chrome(options=opts)
            self.driver.get(self.WA_URL)
            time.sleep(5)
            return True
        except Exception as e:
            logger.error("Selenium start failed: %s", e)
            return False

    def stop(self):
        if self.driver:
            self.driver.quit()

    def send_group(self, message: str, group_name: str = COMMUNITY_NAME) -> bool:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        try:
            s = self.driver.find_element(By.XPATH, "//div[@data-testid='chat-list-search']")
            s.click(); s.send_keys(group_name); time.sleep(2)
            self.driver.find_element(By.XPATH, f"//span[@title='{group_name}']").click()
            time.sleep(1)
            inp = self.driver.find_element(By.XPATH, "//div[@data-testid='conversation-compose-box-input']")
            inp.click()
            for line in message.split("\n"):
                inp.send_keys(line)
                inp.send_keys(Keys.SHIFT + Keys.RETURN)
            inp.send_keys(Keys.RETURN)
            return True
        except Exception as e:
            logger.error("Selenium group send failed: %s", e)
            return False

    def send_dm(self, phone: str, message: str) -> bool:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        try:
            self.driver.get(f"https://web.whatsapp.com/send?phone={phone}")
            time.sleep(4)
            inp = self.driver.find_element(By.XPATH, "//div[@data-testid='conversation-compose-box-input']")
            inp.click()
            for line in message.split("\n"):
                inp.send_keys(line)
                inp.send_keys(Keys.SHIFT + Keys.RETURN)
            inp.send_keys(Keys.RETURN)
            return True
        except Exception as e:
            logger.error("Selenium DM failed: %s", e)
            return False


def make_bot(headless: bool = True) -> Any:
    try:
        import playwright  # noqa
    except ImportError:
        logger.warning("Playwright not found, falling back to Selenium.")
    else:
        bot = WhatsAppBot(headless=headless)
        try:
            if bot.start():
                return bot
        except Exception as e:
            logger.warning("Playwright start failed, falling back to Selenium: %s", str(e).splitlines()[0])
        try:
            bot.stop()
        except Exception:
            pass

    bot = WhatsAppBotSelenium(headless=headless)
    try:
        if bot.start():
            return bot
    except Exception as e:
        logger.error("Selenium start failed: %s", str(e).splitlines()[0])
    try:
        bot.stop()
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 6 — ONBOARDING ENGINE  ░░
# ══════════════════════════════════════════════════════════════════════════════

class OnboardingEngine:
    def __init__(self):
        self._path  = MEMBERS_DB
        self._state = self._load()

    def _load(self) -> Dict:
        if self._path.exists():
            with open(self._path) as f:
                return json.load(f)
        return {}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._state, f, indent=2)

    def register(self, member_id: str, name: str, phone: str, join_time: Optional[datetime] = None):
        if member_id in self._state:
            return
        self._state[member_id] = {
            "name": name, "phone": phone,
            "join_time": (join_time or datetime.now()).isoformat(),
            "completed": [], "next": 0,
        }
        self._save()

    def due_messages(self) -> List[Dict]:
        now = datetime.now()
        due = []
        for mid, s in self._state.items():
            idx = s["next"]
            if idx >= len(ONBOARDING_SEQUENCE):
                continue
            elapsed_h = (now - datetime.fromisoformat(s["join_time"])).total_seconds() / 3600
            step = ONBOARDING_SEQUENCE[idx]
            if elapsed_h >= step["delay_hours"]:
                due.append({"member_id": mid, "name": s["name"],
                            "phone": s["phone"], "step_type": step["type"], "step_idx": idx})
        return due

    def mark_sent(self, member_id: str, step_idx: int):
        if member_id in self._state:
            self._state[member_id]["completed"].append(step_idx)
            self._state[member_id]["next"] = step_idx + 1
            self._save()

    def stats(self) -> Dict:
        total     = len(self._state)
        completed = sum(1 for s in self._state.values() if s["next"] >= len(ONBOARDING_SEQUENCE))
        return {"total": total, "in_progress": total - completed, "completed": completed}

    def run_batch(self, bot) -> int:
        sent = 0
        for item in self.due_messages():
            msg = onboarding_message(item["step_type"], item["name"])
            if bot.send_dm(item["phone"], msg):
                self.mark_sent(item["member_id"], item["step_idx"])
                sent += 1
            time.sleep(2)
        return sent


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 7 — WHATSAPP SCHEDULER  ░░
# ══════════════════════════════════════════════════════════════════════════════

_bot_instance: Optional[Any] = None
_onboarding:   Optional[OnboardingEngine] = None


def _bot() -> Optional[Any]:
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = make_bot(headless=True)
    return _bot_instance


def _ob() -> OnboardingEngine:
    global _onboarding
    if _onboarding is None:
        _onboarding = OnboardingEngine()
    return _onboarding


def _day() -> int:
    return date.today().timetuple().tm_yday


def task_morning_tip():
    bot = _bot()
    if not bot: return
    ctype = "ai_tip" if _day() % 2 == 0 else "coding_tip"
    msg   = format_content(get_content(ctype))
    sheets_log_post(ctype, msg, "07:00")
    bot.send_group(msg)
    logger.info("✅ Morning tip sent: %s", ctype)


def task_networking_prompt():
    bot = _bot()
    if not bot: return
    msg = format_content(get_content("networking_prompt"))
    sheets_log_post("networking_prompt", msg, "10:00")
    bot.send_group(msg)
    logger.info("✅ Networking prompt sent")


def task_growth_hack():
    bot = _bot()
    if not bot: return
    msg = format_content(get_content("growth_hack"))
    sheets_log_post("growth_hack", msg, "11:00")
    bot.send_group(msg)
    logger.info("✅ Growth hack sent")


def task_afternoon_tool():
    bot = _bot()
    if not bot: return
    msg = format_content(get_content("free_tool"))
    sheets_log_post("free_tool", msg, "13:00")
    bot.send_group(msg)
    logger.info("✅ Free tool spotlight sent")


def task_opportunity():
    bot = _bot()
    if not bot: return
    ctype = "opportunity" if _day() % 3 != 0 else "linkedin_post"
    msg   = format_content(get_content(ctype))
    sheets_log_post(ctype, msg, "15:00")
    bot.send_group(msg)
    logger.info("✅ Opportunity post sent: %s", ctype)


def task_daily_challenge():
    bot = _bot()
    if not bot: return
    msg = format_content(get_content("daily_challenge"))
    sheets_log_post("daily_challenge", msg, "17:00")
    bot.send_group(msg)
    logger.info("✅ Daily challenge sent")


def task_inactive_reminders():
    bot = _bot()
    if not bot: return
    members = sheets_get_inactive(days=INACTIVITY_DAYS)
    sent = 0
    for m in members[:20]:
        phone = m.get("phone", "")
        name  = m.get("name", "there")
        if not phone: continue
        if bot.send_dm(phone, inactivity_message(name)):
            sent += 1
        time.sleep(2)
    logger.info("✅ Inactivity reminders: %d/%d sent", sent, len(members))


def task_night_recap():
    bot = _bot()
    if not bot: return
    board = sheets_leaderboard(10)
    lb    = format_leaderboard(board)
    bot.send_group(lb)
    time.sleep(3)
    bot.send_group(
        "💡 *Remember:*\n\n"
        "Every tip you share, every question you ask, every person you invite\n"
        "makes this community stronger.\n\n"
        f"We're at *{CURRENT_MEMBERS}+* members and growing. 🚀\n\n"
        f"Invite one person tonight:\n{WHATSAPP_INVITE_LINK}\n\n"
        "Good night! 🌙 #TechGrowthHub"
    )
    sheets_save_analytics(sheets_daily_stats())
    logger.info("✅ Night recap done.")


def task_onboarding_check():
    ob   = _ob()
    sent = ob.run_batch(_bot()) if _bot() else 0
    if sent:
        logger.info("✅ Onboarding: %d messages sent", sent)


def task_weekly_leaderboard():
    bot = _bot()
    if not bot: return
    board = sheets_leaderboard(10)
    lb    = format_leaderboard(board)
    header = (
        f"🏆 *WEEKLY TOP PERFORMERS — {COMMUNITY_NAME}* 🏆\n"
        f"════════════════════════════\nWeek of {date.today().strftime('%d %B %Y')}\n\n"
    )
    footer = (
        "\n\n🎯 *Next Week's Challenges:*\n"
        "→ Monday: Share your #1 AI tool\n"
        "→ Wednesday: Skill swap post\n"
        "→ Friday: Win of the week\n\n"
        "New week, new chance to climb. Let's go! 💪\n#WeeklyLeaderboard #TechGrowthHub"
    )
    bot.send_group(header + lb + footer)
    logger.info("✅ Weekly leaderboard sent")


def task_referral_blast():
    bot = _bot()
    if not bot: return
    msg = (
        "📣 *FRIDAY INVITE CHALLENGE* 📣\n\n"
        f"We're at *{CURRENT_MEMBERS}+* members. Target: *1,000*.\n\n"
        "This weekend, let's add 100 more.\n"
        "*How?* Each of you invites 1 smart person.\n\n"
        "🏅 Rewards:\n"
        "→ 1 invite: +10 pts\n→ 5 invites: Silver 🥈\n"
        "→ 10 invites: Gold 🥇\n→ 25 invites: Platinum 💎\n\n"
        f"👇 Community Invite Link:\n{WHATSAPP_INVITE_LINK}\n\n"
        "Copy it. Share it. Build with us. 🔥 #TechGrowthHub"
    )
    bot.send_group(msg)
    logger.info("✅ Friday referral blast sent")


def run_scheduler():
    try:
        import schedule
    except ImportError:
        logger.error("Install schedule: pip install schedule")
        sys.exit(1)

    logger.info("=" * 65)
    logger.info(f"  {COMMUNITY_NAME} — WhatsApp Scheduler Started")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 65)

    schedule.every().day.at("07:00").do(task_morning_tip)
    schedule.every().day.at("10:00").do(task_networking_prompt)
    schedule.every().day.at("13:00").do(task_afternoon_tool)
    schedule.every().day.at("17:00").do(task_daily_challenge)
    schedule.every().day.at("19:00").do(task_inactive_reminders)
    schedule.every().day.at("20:00").do(task_night_recap)
    schedule.every().tuesday.at("11:00").do(task_growth_hack)
    schedule.every().thursday.at("11:00").do(task_growth_hack)
    schedule.every().saturday.at("11:00").do(task_growth_hack)
    schedule.every().monday.at("15:00").do(task_opportunity)
    schedule.every().wednesday.at("15:00").do(task_opportunity)
    schedule.every().friday.at("15:00").do(task_opportunity)
    schedule.every().friday.at("18:00").do(task_referral_blast)
    schedule.every().sunday.at("09:00").do(task_weekly_leaderboard)
    schedule.every(1).hours.do(task_onboarding_check)

    while True:
        schedule.run_pending()
        time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 8 — COMMUNITY ANALYTICS DASHBOARD (HTML export)  ░░
# ══════════════════════════════════════════════════════════════════════════════

def generate_community_dashboard(open_browser: bool = True) -> str:
    board   = sheets_leaderboard(10)
    stats   = sheets_daily_stats()
    members = sheets_get_all_members()

    count      = len(members) or CURRENT_MEMBERS
    growth_pct = round((count / TARGET_MEMBERS) * 100, 1)
    medals     = ["🥇", "🥈", "🥉"]

    lb_rows = ""
    for i, e in enumerate(board):
        med = medals[i] if i < 3 else str(i + 1)
        cls = "top-3" if i < 3 else ""
        lb_rows += (
            f'<tr class="{cls}"><td class="medal">{med}</td>'
            f'<td class="nm">{e["name"]} <span class="badge">{e["badge"]}</span></td>'
            f'<td class="tier">{e["tier"]}</td>'
            f'<td class="pts">{e["points"]:,}</td>'
            f'<td class="inv">{e["invites"]}</td>'
            f'<td class="msg">{e["messages"]}</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{COMMUNITY_NAME} — Community Dashboard</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
  :root{{--bg:#060c18;--card:#0f1829;--border:#1a3050;--accent:#00d4ff;--green:#00ff88;--gold:#ffd700;--orange:#ff6b35;--text:#e2e8f0;--muted:#4a6080;--r:14px}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Space Grotesk',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;padding:32px 20px}}
  .wrap{{max-width:1100px;margin:0 auto}}
  header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:36px}}
  .logo h1{{font-size:20px;font-weight:700}}
  .live{{display:flex;align-items:center;gap:6px;background:rgba(0,255,136,.08);border:1px solid rgba(0,255,136,.25);color:var(--green);padding:6px 14px;border-radius:20px;font-size:12px;font-weight:600}}
  .dot{{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}}
  @keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:28px}}
  .sc{{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:22px 18px}}
  .sl{{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}}
  .sv{{font-family:'JetBrains Mono',monospace;font-size:30px;font-weight:600;line-height:1}}
  .sv.cyan{{color:var(--accent)}}.sv.green{{color:var(--green)}}.sv.gold{{color:var(--gold)}}.sv.orange{{color:var(--orange)}}
  .pb{{height:9px;background:rgba(255,255,255,.06);border-radius:99px;overflow:hidden;margin:12px 0 6px}}
  .pf{{height:100%;width:{growth_pct}%;background:linear-gradient(90deg,#0044ff,var(--accent),var(--green));border-radius:99px}}
  table{{width:100%;border-collapse:collapse;background:var(--card);border-radius:var(--r);overflow:hidden;border:1px solid var(--border)}}
  th{{background:rgba(0,212,255,.06);padding:11px 14px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);border-bottom:1px solid var(--border)}}
  td{{padding:13px 14px;border-bottom:1px solid rgba(255,255,255,.03)}}
  tr.top-3{{background:rgba(255,215,0,.025)}}
  .pts{{font-family:'JetBrains Mono',monospace;color:var(--gold);font-weight:600}}
  .inv{{font-family:'JetBrains Mono',monospace;color:var(--green)}}
  .sec-title{{font-size:17px;font-weight:700;margin-bottom:14px}}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo"><h1>🚀 {COMMUNITY_NAME} — Community Dashboard</h1></div>
    <div class="live"><span class="dot"></span>LIVE · {date.today().strftime("%d %b %Y")}</div>
  </header>
  <div class="stats">
    <div class="sc"><div class="sl">Total Members</div><div class="sv cyan">{count:,}</div></div>
    <div class="sc"><div class="sl">Active Today</div><div class="sv green">{stats.get("active_members",0)}</div></div>
    <div class="sc"><div class="sl">New Members</div><div class="sv orange">{stats.get("new_members",0)}</div></div>
    <div class="sc"><div class="sl">Reactions</div><div class="sv gold">{stats.get("reactions",0)}</div></div>
    <div class="sc"><div class="sl">Growth Rate</div><div class="sv cyan">{growth_pct}%</div></div>
  </div>
  <p style="margin-bottom:4px;font-size:13px;color:var(--muted)">🎯 Growth to 1,000 — {count:,}/{TARGET_MEMBERS:,} ({growth_pct}%)</p>
  <div class="pb"><div class="pf"></div></div>
  <div class="sec-title" style="margin-top:28px;">🏆 Member Leaderboard</div>
  <table>
    <thead><tr><th>#</th><th>Member</th><th>Tier</th><th>Points</th><th>Invites</th><th>Messages</th></tr></thead>
    <tbody>{lb_rows if lb_rows else '<tr><td colspan="6" style="text-align:center;padding:32px;color:#4a6080;">No leaderboard data yet</td></tr>'}</tbody>
  </table>
</div>
</body></html>"""

    out = BASE_DIR / "community_dashboard.html"
    out.write_text(html, encoding="utf-8")
    logger.info("Community dashboard written → %s", out)
    if open_browser:
        webbrowser.open(f"file://{out.resolve()}")
    return str(out)


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 9 — FASTAPI WEB APP (CRM)  ░░
# ══════════════════════════════════════════════════════════════════════════════

# ── HTML Templates ─────────────────────────────────────────────────────────────

BASE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>{{ page_title | default('TechGrowth Hub CRM') }}</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet"/>
<style>
  :root {
    --brand: #1e3a5f;
    --accent: #f97316;
    --accent2: #06b6d4;
    --sidebar-w: 240px;
    --bg: #f0f4f8;
    --card: #ffffff;
    --text: #1e293b;
    --muted: #64748b;
    --border: #e2e8f0;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'DM Sans', sans-serif; background: var(--bg); color: var(--text); display: flex; min-height: 100vh; }
  .sidebar { width: var(--sidebar-w); min-height: 100vh; background: var(--brand); display: flex; flex-direction: column; position: fixed; top: 0; left: 0; z-index: 50; box-shadow: 4px 0 24px rgba(0,0,0,0.15); }
  .sidebar-logo { padding: 24px 20px 20px; border-bottom: 1px solid rgba(255,255,255,0.1); }
  .sidebar-logo .brand { font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 800; color: #fff; letter-spacing: -0.5px; line-height: 1.2; }
  .sidebar-logo .sub { font-size: 11px; color: rgba(255,255,255,0.5); margin-top: 2px; letter-spacing: 1px; text-transform: uppercase; }
  .sidebar-logo .dot { color: var(--accent); }
  .nav-section { padding: 16px 12px 8px; }
  .nav-label { font-size: 10px; color: rgba(255,255,255,0.35); letter-spacing: 1.5px; text-transform: uppercase; padding: 0 8px; margin-bottom: 6px; }
  .nav-item { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px; margin-bottom: 2px; color: rgba(255,255,255,0.7); text-decoration: none; font-size: 14px; font-weight: 500; transition: all 0.15s; }
  .nav-item:hover { background: rgba(255,255,255,0.1); color: #fff; }
  .nav-item.active { background: var(--accent); color: #fff; }
  .nav-item svg { width: 16px; height: 16px; flex-shrink: 0; }
  .sidebar-footer { margin-top: auto; padding: 16px; border-top: 1px solid rgba(255,255,255,0.1); }
  .sidebar-footer .version { font-size: 11px; color: rgba(255,255,255,0.3); }
  .main { margin-left: var(--sidebar-w); flex: 1; display: flex; flex-direction: column; min-height: 100vh; }
  .topbar { background: white; border-bottom: 1px solid var(--border); padding: 14px 28px; display: flex; align-items: center; gap: 16px; position: sticky; top: 0; z-index: 40; }
  .topbar-title { font-family: 'Syne', sans-serif; font-size: 18px; font-weight: 700; color: var(--brand); }
  .topbar-search { flex: 1; max-width: 380px; display: flex; align-items: center; gap: 8px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 7px 12px; }
  .topbar-search input { border: none; background: transparent; outline: none; font-size: 13px; color: var(--text); width: 100%; font-family: 'DM Sans', sans-serif; }
  .topbar-right { margin-left: auto; display: flex; align-items: center; gap: 10px; }
  .badge-today { background: #fef3c7; color: #92400e; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 20px; border: 1px solid #fde68a; }
  .content { padding: 28px; flex: 1; }
  .card { background: var(--card); border-radius: 12px; border: 1px solid var(--border); overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); }
  .card-header { padding: 16px 20px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; }
  .card-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 700; color: var(--brand); }
  .card-body { padding: 20px; }
  .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 16px; margin-bottom: 28px; }
  .stat-card { background: var(--card); border-radius: 12px; border: 1px solid var(--border); padding: 20px; position: relative; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.06); transition: transform 0.15s; }
  .stat-card:hover { transform: translateY(-2px); }
  .stat-card .accent-bar { position: absolute; top: 0; left: 0; right: 0; height: 3px; }
  .stat-card .label { font-size: 12px; color: var(--muted); font-weight: 500; margin-top: 4px; }
  .stat-card .value { font-family: 'Syne', sans-serif; font-size: 32px; font-weight: 800; color: var(--brand); line-height: 1; margin-top: 8px; }
  .stat-card .sub { font-size: 11px; color: var(--muted); margin-top: 4px; }
  .stat-card .icon { font-size: 28px; position: absolute; top: 16px; right: 16px; opacity: 0.15; }
  .tbl { width: 100%; border-collapse: collapse; }
  .tbl th { padding: 10px 14px; text-align: left; font-size: 11px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; background: #f8fafc; border-bottom: 1px solid var(--border); }
  .tbl td { padding: 12px 14px; font-size: 13px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  .tbl tr:last-child td { border-bottom: none; }
  .tbl tr:hover td { background: #f8fafc; }
  .tbl a { color: var(--brand); text-decoration: none; font-weight: 600; }
  .tbl a:hover { color: var(--accent); }
  .status-badge { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .status-badge .dot { width: 6px; height: 6px; border-radius: 50%; }
  .btn { display: inline-flex; align-items: center; gap: 6px; padding: 8px 16px; border-radius: 8px; border: none; font-size: 13px; font-weight: 600; cursor: pointer; text-decoration: none; transition: all 0.15s; font-family: 'DM Sans', sans-serif; }
  .btn-primary { background: var(--accent); color: white; }
  .btn-primary:hover { background: #ea6c00; }
  .btn-secondary { background: var(--bg); color: var(--text); border: 1px solid var(--border); }
  .btn-secondary:hover { background: #e2e8f0; }
  .btn-danger { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  .btn-brand { background: var(--brand); color: white; }
  .btn-sm { padding: 5px 10px; font-size: 12px; }
  .form-group { margin-bottom: 18px; }
  .form-label { display: block; font-size: 12px; font-weight: 600; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }
  .form-control { width: 100%; padding: 9px 13px; border-radius: 8px; border: 1px solid var(--border); background: #fff; font-size: 14px; color: var(--text); outline: none; font-family: 'DM Sans', sans-serif; transition: border-color 0.15s; }
  .form-control:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(249,115,22,0.1); }
  textarea.form-control { resize: vertical; min-height: 80px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
  .alert { padding: 12px 16px; border-radius: 8px; font-size: 13px; font-weight: 500; margin-bottom: 16px; }
  .alert-warning { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
  .alert-danger { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  .alert-success { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
  .overdue-row td { background: #fff5f5 !important; }
  .pill { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 11px; font-weight: 600; }
  .note-card { background: #f8fafc; border-radius: 8px; border: 1px solid var(--border); padding: 12px 14px; margin-bottom: 10px; }
  .note-class-badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; margin-bottom: 6px; }
  .lead-header { background: var(--brand); color: white; border-radius: 12px; padding: 28px; margin-bottom: 24px; position: relative; overflow: hidden; }
  .lead-header .title { font-family: 'Syne', sans-serif; font-size: 24px; font-weight: 800; }
  .lead-header .meta { font-size: 13px; opacity: 0.7; margin-top: 4px; }
  .timeline { position: relative; padding-left: 24px; }
  .timeline::before { content: ''; position: absolute; left: 8px; top: 0; bottom: 0; width: 2px; background: var(--border); }
  .timeline-item { position: relative; margin-bottom: 16px; }
  .timeline-item::before { content: ''; position: absolute; left: -20px; top: 4px; width: 10px; height: 10px; border-radius: 50%; background: var(--accent); border: 2px solid white; box-shadow: 0 0 0 2px var(--accent); }
  .timeline-date { font-size: 11px; color: var(--muted); margin-bottom: 4px; }
  .timeline-content { background: #f8fafc; border-radius: 8px; padding: 10px 12px; font-size: 13px; border: 1px solid var(--border); }
  .empty-state { text-align: center; padding: 48px 20px; color: var(--muted); }
  .empty-state .icon { font-size: 48px; margin-bottom: 12px; }
  .bar-chart { display: flex; flex-direction: column; gap: 8px; }
  .bar-row { display: flex; align-items: center; gap: 10px; }
  .bar-label { font-size: 12px; color: var(--muted); min-width: 120px; text-align: right; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .bar-track { flex: 1; background: #f1f5f9; border-radius: 4px; height: 22px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; display: flex; align-items: center; padding-left: 8px; font-size: 11px; font-weight: 700; color: white; }
  .bar-count { font-size: 12px; font-weight: 700; color: var(--brand); min-width: 24px; }
  @media (max-width: 768px) { .sidebar { width: 60px; } .main { margin-left: 60px; } .grid-2, .grid-3 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<nav class="sidebar">
  <div class="sidebar-logo">
    <div class="brand">TechGrowth<span class="dot">.</span>Hub</div>
    <div class="sub">CRM Platform</div>
  </div>
  <div class="nav-section">
    <div class="nav-label">Main</div>
    <a href="/" class="nav-item {{ 'active' if active_page == 'dashboard' }}">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      <span>Dashboard</span>
    </a>
    <a href="/leads" class="nav-item {{ 'active' if active_page == 'leads' }}">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/></svg>
      <span>All Leads</span>
    </a>
    <a href="/add-lead" class="nav-item {{ 'active' if active_page == 'add_lead' }}">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12h14"/></svg>
      <span>Add Lead</span>
    </a>
  </div>
  <div class="nav-section">
    <div class="nav-label">Insights</div>
    <a href="/analytics" class="nav-item {{ 'active' if active_page == 'analytics' }}">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path d="M18 20V10M12 20V4M6 20v-6"/></svg>
      <span>Analytics</span>
    </a>
    <a href="/leads?filter=today_followup" class="nav-item {{ 'active' if active_page == 'followups' }}">
      <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
      <span>Follow-ups</span>
    </a>
  </div>
  <div class="sidebar-footer">
    <div class="version">v2.0.0 · TechGrowth Hub</div>
  </div>
</nav>
<div class="main">
  <div class="topbar">
    <span class="topbar-title">{{ page_title | default('Dashboard') }}</span>
    <form action="/leads" method="get" class="topbar-search" style="margin-left:16px;">
      <svg width="15" height="15" fill="none" viewBox="0 0 24 24" stroke="#94a3b8" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
      <input type="text" name="search" placeholder="Search institutes, contacts..." value="{{ search_query | default('') }}"/>
    </form>
    <div class="topbar-right">
      <span class="badge-today">📅 Today: {{ today }}</span>
      <a href="/add-lead" class="btn btn-primary btn-sm">+ New Lead</a>
    </div>
  </div>
  <div class="content">
    {% block content %}{% endblock %}
  </div>
</div>
</body>
</html>"""


def write_template(name: str, content: str):
    path = BASE_DIR / "templates" / name
    path.write_text(content, encoding="utf-8")


def _setup_templates():
    write_template("base.html", BASE_HTML)

    # ── dashboard ──
    write_template("dashboard.html", BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="stats-grid">
  {% set stat_items = [
    ('Total Leads', stats.total, '#1e3a5f', '👥', 'All time'),
    ('New', stats.new, '#6366f1', '✨', 'Pending contact'),
    ('Qualified', stats.qualified, '#06b6d4', '⚡', 'High intent'),
    ('Demo Booked', stats.demo_booked, '#3b82f6', '📅', 'Scheduled'),
    ('Customers', stats.customers, '#22c55e', '🏆', 'Closed won'),
    ('Lost', stats.lost, '#ef4444', '❌', 'Closed lost'),
    ('Conversion', stats.conversion_rate|string + '%', '#f97316', '📈', 'Lead → Customer'),
    ("Today's FUP", stats.today_followup, '#f59e0b', '🔔', 'Action needed'),
    ('Overdue FUP', stats.overdue_followup, '#dc2626', '⚠️', 'Needs attention'),
  ] %}
  {% for label, value, color, icon, sub in stat_items %}
  <div class="stat-card">
    <div class="accent-bar" style="background:{{ color }}"></div>
    <div class="icon">{{ icon }}</div>
    <div class="label">{{ label }}</div>
    <div class="value" style="color:{{ color }}">{{ value }}</div>
    <div class="sub">{{ sub }}</div>
  </div>
  {% endfor %}
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:24px;">
  <div class="card">
    <div class="card-header"><span class="card-title">🔔 Today's Follow-ups</span><a href="/leads?filter=today_followup" class="btn btn-secondary btn-sm">View All</a></div>
    {% if today_followups %}
    <div style="overflow-x:auto;"><table class="tbl"><thead><tr><th>Institute</th><th>Contact</th><th>Status</th></tr></thead><tbody>
    {% for l in today_followups[:6] %}{% set sc = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}
    <tr><td><a href="/lead/{{ l.id }}">{{ l.institute_name }}</a></td><td style="color:#64748b;font-size:12px;">{{ l.contact_person }}</td><td><span class="status-badge" style="background:{{ sc.get(l.status,'#94a3b8') }}20;color:{{ sc.get(l.status,'#94a3b8') }};"><span class="dot" style="background:{{ sc.get(l.status,'#94a3b8') }}"></span>{{ l.status }}</span></td></tr>
    {% endfor %}
    </tbody></table></div>
    {% else %}<div class="empty-state"><div class="icon">✅</div><p>No follow-ups today!</p></div>{% endif %}
  </div>
  <div class="card">
    <div class="card-header"><span class="card-title">⚠️ Overdue Follow-ups</span><a href="/leads?filter=overdue" class="btn btn-danger btn-sm">View All</a></div>
    {% if overdue_followups %}
    <div style="overflow-x:auto;"><table class="tbl"><thead><tr><th>Institute</th><th>Due Date</th><th>Status</th></tr></thead><tbody>
    {% for l in overdue_followups[:6] %}{% set sc = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}
    <tr class="overdue-row"><td><a href="/lead/{{ l.id }}">{{ l.institute_name }}</a></td><td style="color:#dc2626;font-size:12px;font-weight:600;">{{ l.next_followup_date }}</td><td><span class="status-badge" style="background:{{ sc.get(l.status,'#94a3b8') }}20;color:{{ sc.get(l.status,'#94a3b8') }};"><span class="dot" style="background:{{ sc.get(l.status,'#94a3b8') }}"></span>{{ l.status }}</span></td></tr>
    {% endfor %}
    </tbody></table></div>
    {% else %}<div class="empty-state"><div class="icon">🎉</div><p>No overdue follow-ups!</p></div>{% endif %}
  </div>
</div>
<div class="card">
  <div class="card-header"><span class="card-title">📋 Recent Leads</span><a href="/leads" class="btn btn-secondary btn-sm">View All →</a></div>
  <div style="overflow-x:auto;"><table class="tbl">
    <thead><tr><th>Institute</th><th>Contact</th><th>City</th><th>Source</th><th>Status</th><th>Next Follow-up</th><th>Actions</th></tr></thead>
    <tbody>
    {% for l in recent_leads %}{% set sc = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}
    <tr>
      <td><a href="/lead/{{ l.id }}">{{ l.institute_name }}</a></td>
      <td><div style="font-size:13px;">{{ l.contact_person }}</div><div style="font-size:11px;color:#64748b;">{{ l.phone }}</div></td>
      <td style="color:#64748b;">{{ l.city or '—' }}</td>
      <td><span class="pill" style="background:#f1f5f9;color:#475569;">{{ l.lead_source or '—' }}</span></td>
      <td><span class="status-badge" style="background:{{ sc.get(l.status,'#94a3b8') }}20;color:{{ sc.get(l.status,'#94a3b8') }};"><span class="dot" style="background:{{ sc.get(l.status,'#94a3b8') }}"></span>{{ l.status }}</span></td>
      <td style="font-size:12px;color:{% if l.next_followup_date and l.next_followup_date < today %}#dc2626{% else %}#64748b{% endif %};">{{ l.next_followup_date or '—' }}</td>
      <td><a href="/edit-lead/{{ l.id }}" class="btn btn-secondary btn-sm">Edit</a></td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
</div>
"""))

    # ── leads list ──
    write_template("leads.html", BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="card" style="margin-bottom:20px;padding:16px 20px;">
  <form action="/leads" method="get" style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <input type="text" name="search" value="{{ search or '' }}" placeholder="Search institute, contact, city..." class="form-control" style="max-width:260px;"/>
    <select name="status" class="form-control" style="max-width:170px;"><option value="">All Statuses</option>{% for s in statuses %}<option value="{{ s }}" {% if s == status_filter %}selected{% endif %}>{{ s }}</option>{% endfor %}</select>
    <select name="city" class="form-control" style="max-width:150px;"><option value="">All Cities</option>{% for c in cities %}<option value="{{ c }}" {% if c == city_filter %}selected{% endif %}>{{ c }}</option>{% endfor %}</select>
    <select name="filter" class="form-control" style="max-width:180px;"><option value="">No Date Filter</option><option value="today_followup" {% if filter_type == 'today_followup' %}selected{% endif %}>Today's Follow-ups</option><option value="overdue" {% if filter_type == 'overdue' %}selected{% endif %}>Overdue</option><option value="upcoming" {% if filter_type == 'upcoming' %}selected{% endif %}>Upcoming (7 days)</option></select>
    <button type="submit" class="btn btn-brand">Filter</button>
    <a href="/leads" class="btn btn-secondary">Clear</a>
    <a href="/add-lead" class="btn btn-primary" style="margin-left:auto;">+ Add Lead</a>
  </form>
</div>
<div style="margin-bottom:12px;"><span style="font-size:13px;color:#64748b;font-weight:500;">{{ leads|length }} lead{{ 's' if leads|length != 1 }} found</span></div>
<div class="card">
  {% if leads %}
  <div style="overflow-x:auto;"><table class="tbl">
    <thead><tr><th>#</th><th>Institute</th><th>Contact</th><th>City</th><th>Source</th><th>Status</th><th>Pain Point</th><th>Next Follow-up</th><th>Actions</th></tr></thead>
    <tbody>
    {% for l in leads %}{% set sc = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}{% set is_overdue = l.next_followup_date and l.next_followup_date < today %}
    <tr class="{{ 'overdue-row' if is_overdue }}">
      <td style="color:#94a3b8;font-size:12px;">{{ l.id }}</td>
      <td><a href="/lead/{{ l.id }}">{{ l.institute_name }}</a>{% if is_overdue %}<span style="font-size:10px;color:#dc2626;font-weight:700;margin-left:6px;">OVERDUE</span>{% endif %}</td>
      <td><div style="font-weight:500;">{{ l.contact_person }}</div><div style="font-size:11px;color:#64748b;">{{ l.phone or '' }}</div></td>
      <td style="color:#64748b;font-size:13px;">{{ l.city or '—' }}</td>
      <td><span class="pill" style="background:#f1f5f9;color:#475569;font-size:11px;">{{ l.lead_source or '—' }}</span></td>
      <td><span class="status-badge" style="background:{{ sc.get(l.status,'#94a3b8') }}20;color:{{ sc.get(l.status,'#94a3b8') }};"><span class="dot" style="background:{{ sc.get(l.status,'#94a3b8') }}"></span>{{ l.status }}</span></td>
      <td style="font-size:12px;color:#64748b;">{{ l.pain_point or '—' }}</td>
      <td style="font-size:12px;color:{{ '#dc2626' if is_overdue else '#64748b' }};font-weight:{{ '700' if is_overdue else '400' }};">{{ l.next_followup_date or '—' }}</td>
      <td><div style="display:flex;gap:6px;"><a href="/lead/{{ l.id }}" class="btn btn-secondary btn-sm">View</a><a href="/edit-lead/{{ l.id }}" class="btn btn-secondary btn-sm">Edit</a><form action="/delete-lead/{{ l.id }}" method="post" onsubmit="return confirm('Delete?');" style="display:inline;"><button type="submit" class="btn btn-danger btn-sm">✕</button></form></div></td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% else %}<div class="empty-state"><div class="icon">🔍</div><p>No leads found.</p><a href="/add-lead" class="btn btn-primary" style="margin-top:16px;">Add First Lead</a></div>{% endif %}
</div>
"""))

    # ── add/edit lead form ──
    ADD_EDIT_FORM = """
{% set is_edit = lead is defined and lead %}
<form action="{{ '/edit-lead/' + lead.id|string if is_edit else '/add-lead' }}" method="post">
  {% if msg %}<div class="alert alert-{{ 'success' if 'success' in msg.lower() else 'danger' }}" style="margin-bottom:20px;">{{ msg }}</div>{% endif %}
  <div class="grid-2" style="gap:20px;align-items:start;">
    <div>
      <div class="card" style="margin-bottom:20px;">
        <div class="card-header"><span class="card-title">Institute Information</span></div>
        <div class="card-body">
          <div class="form-group"><label class="form-label">Institute Name *</label><input type="text" name="institute_name" class="form-control" required value="{{ lead.institute_name if is_edit else '' }}" placeholder="e.g. Sunrise Academy"/></div>
          <div class="form-group"><label class="form-label">Contact Person *</label><input type="text" name="contact_person" class="form-control" required value="{{ lead.contact_person if is_edit else '' }}" placeholder="Principal / Manager name"/></div>
          <div class="grid-2">
            <div class="form-group"><label class="form-label">Phone</label><input type="text" name="phone" class="form-control" value="{{ lead.phone if is_edit else '' }}" placeholder="9876543210"/></div>
            <div class="form-group"><label class="form-label">Email</label><input type="email" name="email" class="form-control" value="{{ lead.email if is_edit else '' }}" placeholder="info@school.edu"/></div>
          </div>
          <div class="form-group"><label class="form-label">City</label><input type="text" name="city" class="form-control" value="{{ lead.city if is_edit else '' }}" placeholder="Ahmedabad"/></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header"><span class="card-title">Notes</span></div>
        <div class="card-body">
          <div class="form-group"><label class="form-label">Notes / Observations</label><textarea name="notes" class="form-control" rows="5" placeholder="Auto-classified by keywords (fees, attendance, parent, demo...)">{{ lead.notes if is_edit else '' }}</textarea></div>
        </div>
      </div>
    </div>
    <div>
      <div class="card" style="margin-bottom:20px;">
        <div class="card-header"><span class="card-title">Lead Details</span></div>
        <div class="card-body">
          <div class="form-group"><label class="form-label">Lead Source</label><select name="lead_source" class="form-control"><option value="">Select Source</option>{% for src in sources %}<option value="{{ src }}" {% if is_edit and lead.lead_source == src %}selected{% endif %}>{{ src }}</option>{% endfor %}</select></div>
          <div class="form-group"><label class="form-label">Status</label><select name="status" class="form-control">{% for s in statuses %}<option value="{{ s }}" {% if is_edit and lead.status == s %}selected{% elif not is_edit and s == 'NEW' %}selected{% endif %}>{{ s }}</option>{% endfor %}</select></div>
          <div class="form-group"><label class="form-label">Pain Point</label><select name="pain_point" class="form-control"><option value="">Select Pain Point</option>{% for p in pain_points %}<option value="{{ p }}" {% if is_edit and lead.pain_point == p %}selected{% endif %}>{{ p }}</option>{% endfor %}</select></div>
        </div>
      </div>
      <div class="card" style="margin-bottom:20px;">
        <div class="card-header"><span class="card-title">Dates & Schedule</span></div>
        <div class="card-body">
          <div class="form-group"><label class="form-label">Last Contact Date</label><input type="date" name="last_contact_date" class="form-control" value="{{ lead.last_contact_date if is_edit else '' }}"/></div>
          <div class="form-group"><label class="form-label">Next Follow-up Date</label><input type="date" name="next_followup_date" class="form-control" value="{{ lead.next_followup_date if is_edit else '' }}"/></div>
          <div class="form-group"><label class="form-label">Demo Date</label><input type="date" name="demo_date" class="form-control" value="{{ lead.demo_date if is_edit else '' }}"/></div>
        </div>
      </div>
      <div style="display:flex;gap:10px;">
        <button type="submit" class="btn btn-primary" style="flex:1;">{{ '💾 Update Lead' if is_edit else '✅ Create Lead' }}</button>
        <a href="{{ '/lead/' + lead.id|string if is_edit else '/leads' }}" class="btn btn-secondary">Cancel</a>
      </div>
    </div>
  </div>
</form>
"""
    write_template("add_lead.html", BASE_HTML.replace("{% block content %}{% endblock %}", ADD_EDIT_FORM))
    write_template("edit_lead.html", BASE_HTML.replace("{% block content %}{% endblock %}", ADD_EDIT_FORM))

    # ── lead detail ──
    write_template("lead_detail.html", BASE_HTML.replace("{% block content %}{% endblock %}", """
{% set sc = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}
<div class="lead-header">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;">
    <div>
      <div class="title">{{ lead.institute_name }}</div>
      <div class="meta">{{ lead.contact_person }} · {{ lead.phone or 'No phone' }} · {{ lead.city or 'No city' }}</div>
      <div style="margin-top:12px;">
        <span class="status-badge" style="background:{{ sc.get(lead.status,'#94a3b8') }}30;color:white;border:1px solid rgba(255,255,255,0.3);"><span class="dot" style="background:white;"></span>{{ lead.status }}</span>
        {% if lead.pain_point %}<span style="margin-left:8px;font-size:12px;opacity:0.7;">📌 {{ lead.pain_point }}</span>{% endif %}
        {% if lead.lead_source %}<span style="margin-left:8px;font-size:12px;opacity:0.7;">📡 {{ lead.lead_source }}</span>{% endif %}
      </div>
    </div>
    <div style="display:flex;gap:8px;">
      <a href="/edit-lead/{{ lead.id }}" class="btn btn-secondary">✏️ Edit</a>
      <form action="/delete-lead/{{ lead.id }}" method="post" onsubmit="return confirm('Delete?');"><button type="submit" class="btn btn-danger">🗑️ Delete</button></form>
    </div>
  </div>
</div>
<div class="grid-2" style="gap:20px;align-items:start;">
  <div>
    <div class="card" style="margin-bottom:20px;">
      <div class="card-header"><span class="card-title">Contact Information</span></div>
      <div class="card-body">
        <table style="width:100%;border-collapse:collapse;">
          {% set info = [('📧 Email', lead.email or '—'),('📱 Phone', lead.phone or '—'),('🏙️ City', lead.city or '—'),('📡 Source', lead.lead_source or '—'),('📌 Pain Point', lead.pain_point or '—'),('📅 Last Contact', lead.last_contact_date or '—'),('🔔 Next Follow-up', lead.next_followup_date or '—'),('🎯 Demo Date', lead.demo_date or '—'),('🗓️ Created', lead.created_at[:10] if lead.created_at else '—'),] %}
          {% for label, value in info %}
          <tr><td style="padding:8px 0;font-size:12px;color:#64748b;font-weight:600;width:140px;border-bottom:1px solid #f1f5f9;">{{ label }}</td><td style="padding:8px 0;font-size:13px;border-bottom:1px solid #f1f5f9;color:{% if value == '—' %}#94a3b8{% else %}#1e293b{% endif %};">{{ value }}</td></tr>
          {% endfor %}
        </table>
        {% if lead.next_followup_date and lead.next_followup_date < today %}<div class="alert alert-danger" style="margin-top:12px;">⚠️ Follow-up <strong>overdue</strong> since {{ lead.next_followup_date }}</div>{% elif lead.next_followup_date == today %}<div class="alert alert-warning" style="margin-top:12px;">🔔 Follow-up due <strong>today!</strong></div>{% endif %}
      </div>
    </div>
    <div class="card">
      <div class="card-header"><span class="card-title">Add Note</span></div>
      <div class="card-body">
        <form action="/lead/{{ lead.id }}/add-note" method="post">
          <div class="form-group"><textarea name="note" class="form-control" rows="4" placeholder="e.g. Spoke with principal. Demo scheduled for next week..." required></textarea><div style="font-size:11px;color:#94a3b8;margin-top:4px;">💡 Notes are auto-classified by keywords</div></div>
          <button type="submit" class="btn btn-primary">Add Note</button>
        </form>
      </div>
    </div>
  </div>
  <div>
    <div class="card" style="margin-bottom:20px;">
      <div class="card-header"><span class="card-title">📝 Notes History</span><span style="font-size:12px;color:#64748b;">{{ notes|length }} note{{ 's' if notes|length != 1 }}</span></div>
      <div class="card-body">
        {% if notes %}
        <div class="timeline">
          {% set nclass_colors = {'FEES':'#22c55e20','ATTENDANCE':'#3b82f620','PARENT_COMMUNICATION':'#8b5cf620','DEMO':'#f9731620','FOLLOWUP':'#f59e0b20','GENERAL':'#94a3b820'} %}
          {% set nclass_text = {'FEES':'#166534','ATTENDANCE':'#1e40af','PARENT_COMMUNICATION':'#5b21b6','DEMO':'#c2410c','FOLLOWUP':'#92400e','GENERAL':'#475569'} %}
          {% for n in notes %}
          <div class="timeline-item"><div class="timeline-date">{{ n.created_at }}</div>{% if n.classification %}<span class="note-class-badge" style="background:{{ nclass_colors.get(n.classification,'#f1f5f9') }};color:{{ nclass_text.get(n.classification,'#475569') }}">{{ n.classification }}</span>{% endif %}<div class="timeline-content">{{ n.note }}</div></div>
          {% endfor %}
        </div>
        {% else %}<div class="empty-state" style="padding:24px;"><div class="icon">📝</div><p>No notes yet.</p></div>{% endif %}
      </div>
    </div>
    {% if lead.notes %}
    <div class="card">
      <div class="card-header"><span class="card-title">📋 General Notes</span></div>
      <div class="card-body"><p style="font-size:13px;line-height:1.6;color:#475569;">{{ lead.notes }}</p><div style="margin-top:10px;"><span class="pill" style="background:#f1f5f9;color:#475569;font-size:11px;">🏷️ {{ classify_note(lead.notes) }}</span></div></div>
    </div>
    {% endif %}
  </div>
</div>
"""))

    # ── analytics ──
    write_template("analytics.html", BASE_HTML.replace("{% block content %}{% endblock %}", """
<div class="grid-2" style="gap:20px;margin-bottom:24px;">
  <div class="card">
    <div class="card-header"><span class="card-title">📊 Conversion Funnel</span></div>
    <div class="card-body">
      {% set funnel_colors = {'NEW':'#6366f1','CONTACTED':'#f59e0b','REPLIED':'#8b5cf6','QUALIFIED':'#06b6d4','DEMO_BOOKED':'#3b82f6','DEMO_COMPLETED':'#10b981','PILOT':'#f97316','CUSTOMER':'#22c55e','LOST':'#ef4444'} %}
      {% set total = status_counts.values()|sum %}
      {% if total > 0 %}
      <div style="display:flex;flex-direction:column;gap:8px;">
        {% for s in ['NEW','CONTACTED','REPLIED','QUALIFIED','DEMO_BOOKED','DEMO_COMPLETED','PILOT','CUSTOMER','LOST'] %}{% set cnt = status_counts.get(s, 0) %}{% set pct = ((cnt / total) * 100)|round|int %}
        <div style="display:flex;align-items:center;gap:10px;"><span style="font-size:11px;color:#64748b;min-width:120px;text-align:right;">{{ s }}</span><div style="flex:1;background:#f1f5f9;border-radius:6px;height:28px;overflow:hidden;"><div style="width:{{ pct }}%;background:{{ funnel_colors.get(s,'#94a3b8') }};height:100%;border-radius:6px;display:flex;align-items:center;padding-left:8px;font-size:11px;font-weight:700;color:white;min-width:{{ '30px' if cnt > 0 else '0' }};">{% if cnt > 0 %}{{ cnt }}{% endif %}</div></div><span style="font-size:12px;font-weight:700;color:#1e3a5f;min-width:28px;">{{ pct }}%</span></div>
        {% endfor %}
      </div>
      {% else %}<div class="empty-state"><p>No data yet.</p></div>{% endif %}
    </div>
  </div>
  <div class="card">
    <div class="card-header"><span class="card-title">🏙️ Leads by City</span></div>
    <div class="card-body">
      {% set city_colors = ['#6366f1','#f97316','#06b6d4','#22c55e','#f59e0b','#8b5cf6','#3b82f6','#10b981','#ef4444'] %}
      {% if city_counts %}<div class="bar-chart">{% set max_c = city_counts.values()|max %}{% for i, (city, cnt) in enumerate(city_counts.items()) %}<div class="bar-row"><span class="bar-label">{{ city }}</span><div class="bar-track"><div class="bar-fill" style="width:{{ ((cnt/max_c)*100)|round|int }}%;background:{{ city_colors[i % city_colors|length] }};">{{ cnt }}</div></div><span class="bar-count">{{ cnt }}</span></div>{% endfor %}</div>{% else %}<div class="empty-state"><p>No city data.</p></div>{% endif %}
    </div>
  </div>
</div>
<div class="grid-2" style="gap:20px;margin-bottom:24px;">
  <div class="card">
    <div class="card-header"><span class="card-title">💡 Leads by Pain Point</span></div>
    <div class="card-body">
      {% set pp_colors = ['#ef4444','#f97316','#f59e0b','#22c55e','#06b6d4','#6366f1','#8b5cf6'] %}
      {% if pain_counts %}<div class="bar-chart">{% set max_p = pain_counts.values()|max %}{% for i, (pp, cnt) in enumerate(pain_counts.items()) %}<div class="bar-row"><span class="bar-label">{{ pp }}</span><div class="bar-track"><div class="bar-fill" style="width:{{ ((cnt/max_p)*100)|round|int }}%;background:{{ pp_colors[i % pp_colors|length] }};">{{ cnt }}</div></div><span class="bar-count">{{ cnt }}</span></div>{% endfor %}</div>{% else %}<div class="empty-state"><p>No data.</p></div>{% endif %}
    </div>
  </div>
  <div class="card">
    <div class="card-header"><span class="card-title">📡 Leads by Source</span></div>
    <div class="card-body">
      {% set src_colors = ['#3b82f6','#10b981','#f97316','#8b5cf6','#f59e0b','#06b6d4','#22c55e','#6366f1','#ef4444'] %}
      {% if source_counts %}<div class="bar-chart">{% set max_s = source_counts.values()|max %}{% for i, (src, cnt) in enumerate(source_counts.items()) %}<div class="bar-row"><span class="bar-label">{{ src }}</span><div class="bar-track"><div class="bar-fill" style="width:{{ ((cnt/max_s)*100)|round|int }}%;background:{{ src_colors[i % src_colors|length] }};">{{ cnt }}</div></div><span class="bar-count">{{ cnt }}</span></div>{% endfor %}</div>{% else %}<div class="empty-state"><p>No data.</p></div>{% endif %}
    </div>
  </div>
</div>
<div class="card" style="margin-bottom:24px;">
  <div class="card-header"><span class="card-title">📈 Monthly Lead Growth</span></div>
  <div class="card-body">
    {% if monthly_growth %}
    <div style="display:flex;align-items:flex-end;gap:8px;height:160px;padding-bottom:20px;overflow-x:auto;">
      {% set max_m = monthly_growth.values()|max %}
      {% for month, cnt in monthly_growth.items() %}
      <div style="display:flex;flex-direction:column;align-items:center;gap:4px;min-width:52px;">
        <span style="font-size:11px;font-weight:700;color:#1e3a5f;">{{ cnt }}</span>
        <div style="width:40px;background:linear-gradient(135deg,#1e3a5f,#06b6d4);border-radius:6px 6px 0 0;height:{{ ((cnt/max_m)*120)|round|int }}px;"></div>
        <span style="font-size:10px;color:#64748b;">{{ month }}</span>
      </div>
      {% endfor %}
    </div>
    {% else %}<div class="empty-state"><p>No monthly data yet.</p></div>{% endif %}
  </div>
</div>
<div class="grid-3" style="gap:16px;">
  <div class="card"><div class="card-body" style="text-align:center;"><div style="font-size:36px;font-family:'Syne',sans-serif;font-weight:800;color:#22c55e;">{{ conversion_rate }}%</div><div style="font-size:13px;color:#64748b;margin-top:4px;">Lead → Customer Rate</div></div></div>
  <div class="card"><div class="card-body" style="text-align:center;"><div style="font-size:36px;font-family:'Syne',sans-serif;font-weight:800;color:#06b6d4;">{{ demo_rate }}%</div><div style="font-size:13px;color:#64748b;margin-top:4px;">Lead → Demo Rate</div></div></div>
  <div class="card"><div class="card-body" style="text-align:center;"><div style="font-size:36px;font-family:'Syne',sans-serif;font-weight:800;color:#f97316;">{{ total_leads }}</div><div style="font-size:13px;color:#64748b;margin-top:4px;">Total Leads in Pipeline</div></div></div>
</div>
"""))


def _base_ctx(active_page: str, page_title: str, search_query: str = "") -> Dict:
    return {
        "active_page": active_page,
        "page_title": page_title,
        "today": today_str(),
        "search_query": search_query,
        "sources": LEAD_SOURCES,
        "statuses": LEAD_STATUSES,
        "pain_points": PAIN_POINTS,
        "classify_note": classify_note,
        "enumerate": enumerate,
    }


def _build_fastapi_app():
    """Build and return the FastAPI app. Lazy import so CLI works without fastapi installed."""
    try:
        from fastapi import FastAPI, Form, HTTPException
        from fastapi.responses import HTMLResponse, RedirectResponse
        from fastapi.templating import Jinja2Templates
        from fastapi.requests import Request
    except ImportError:
        return None

    app = FastAPI(title="TechGrowth Hub CRM")
    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

    # ── Routes ────────────────────────────────────────────────────────────────

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        t = today_str()
        with db_conn() as conn:
            def count(q, *a): return conn.execute(q, a).fetchone()[0]
            total       = count("SELECT COUNT(*) FROM leads")
            new_c       = count("SELECT COUNT(*) FROM leads WHERE status='NEW'")
            qualified   = count("SELECT COUNT(*) FROM leads WHERE status='QUALIFIED'")
            demo_booked = count("SELECT COUNT(*) FROM leads WHERE status='DEMO_BOOKED'")
            customers   = count("SELECT COUNT(*) FROM leads WHERE status='CUSTOMER'")
            lost        = count("SELECT COUNT(*) FROM leads WHERE status='LOST'")
            today_fup   = count("SELECT COUNT(*) FROM leads WHERE next_followup_date=?", t)
            overdue_fup = count("SELECT COUNT(*) FROM leads WHERE next_followup_date<? AND next_followup_date IS NOT NULL AND next_followup_date != ''", t)
            conv_rate   = round((customers / total * 100), 1) if total > 0 else 0
            today_followups   = [dict(r) for r in conn.execute("SELECT * FROM leads WHERE next_followup_date=? ORDER BY institute_name", (t,)).fetchall()]
            overdue_followups = [dict(r) for r in conn.execute("SELECT * FROM leads WHERE next_followup_date<? AND next_followup_date IS NOT NULL AND next_followup_date != '' ORDER BY next_followup_date", (t,)).fetchall()]
            recent_leads      = [dict(r) for r in conn.execute("SELECT * FROM leads ORDER BY created_at DESC LIMIT 10").fetchall()]

        ctx = _base_ctx("dashboard", "Dashboard")
        ctx.update({
            "stats": type("S", (), {
                "total": total, "new": new_c, "qualified": qualified,
                "demo_booked": demo_booked, "customers": customers, "lost": lost,
                "conversion_rate": conv_rate, "today_followup": today_fup, "overdue_followup": overdue_fup
            })(),
            "today_followups": today_followups,
            "overdue_followups": overdue_followups,
            "recent_leads": recent_leads,
        })
        return templates.TemplateResponse("dashboard.html", {"request": request, **ctx})

    @app.get("/leads", response_class=HTMLResponse)
    def leads_list(request: Request, search: str = "", status: str = "", city: str = "", filter: str = ""):
        t        = today_str()
        upcoming = (date.today() + timedelta(days=7)).isoformat()
        query    = "SELECT * FROM leads WHERE 1=1"
        params: list = []
        if search:
            query += " AND (institute_name LIKE ? OR contact_person LIKE ? OR city LIKE ? OR phone LIKE ? OR email LIKE ?)"
            s = f"%{search}%"
            params.extend([s, s, s, s, s])
        if status:
            query += " AND status=?"; params.append(status)
        if city:
            query += " AND city=?"; params.append(city)
        if filter == "today_followup":
            query += " AND next_followup_date=?"; params.append(t)
        elif filter == "overdue":
            query += " AND next_followup_date<? AND next_followup_date IS NOT NULL AND next_followup_date != ''"; params.append(t)
        elif filter == "upcoming":
            query += " AND next_followup_date>? AND next_followup_date<=?"; params.extend([t, upcoming])
        query += " ORDER BY created_at DESC"
        with db_conn() as conn:
            leads  = [dict(r) for r in conn.execute(query, params).fetchall()]
            cities = [r[0] for r in conn.execute("SELECT DISTINCT city FROM leads WHERE city IS NOT NULL AND city != '' ORDER BY city").fetchall()]
        ctx = _base_ctx("leads", "All Leads", search)
        ctx.update({"leads": leads, "cities": cities, "search": search,
                    "status_filter": status, "city_filter": city, "filter_type": filter})
        return templates.TemplateResponse("leads.html", {"request": request, **ctx})

    @app.get("/add-lead", response_class=HTMLResponse)
    def add_lead_form(request: Request, msg: str = ""):
        ctx = _base_ctx("add_lead", "Add New Lead"); ctx["msg"] = msg
        return templates.TemplateResponse("add_lead.html", {"request": request, **ctx})

    @app.post("/add-lead")
    async def add_lead_submit(
        request: Request,
        institute_name: str = Form(...), contact_person: str = Form(...),
        phone: str = Form(""), email: str = Form(""), city: str = Form(""),
        lead_source: str = Form(""), status: str = Form("NEW"), pain_point: str = Form(""),
        notes: str = Form(""), last_contact_date: str = Form(""),
        next_followup_date: str = Form(""), demo_date: str = Form(""),
    ):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db_conn() as conn:
            cur = conn.execute("""
                INSERT INTO leads (institute_name, contact_person, phone, email, city, lead_source,
                status, pain_point, notes, last_contact_date, next_followup_date, demo_date, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (institute_name, contact_person, phone or None, email or None, city or None,
                  lead_source or None, status, pain_point or None, notes,
                  last_contact_date or None, next_followup_date or None, demo_date or None, now, now))
            lead_id = cur.lastrowid
            if notes.strip():
                conn.execute("INSERT INTO lead_notes (lead_id, note, classification) VALUES (?,?,?)",
                             (lead_id, notes, classify_note(notes)))
        return RedirectResponse(f"/lead/{lead_id}", status_code=303)

    @app.get("/edit-lead/{lead_id}", response_class=HTMLResponse)
    def edit_lead_form(request: Request, lead_id: int, msg: str = ""):
        lead = get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        ctx = _base_ctx("leads", f"Edit Lead – {lead['institute_name']}")
        ctx["lead"] = lead; ctx["msg"] = msg
        return templates.TemplateResponse("edit_lead.html", {"request": request, **ctx})

    @app.post("/edit-lead/{lead_id}")
    async def edit_lead_submit(
        request: Request, lead_id: int,
        institute_name: str = Form(...), contact_person: str = Form(...),
        phone: str = Form(""), email: str = Form(""), city: str = Form(""),
        lead_source: str = Form(""), status: str = Form("NEW"), pain_point: str = Form(""),
        notes: str = Form(""), last_contact_date: str = Form(""),
        next_followup_date: str = Form(""), demo_date: str = Form(""),
    ):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with db_conn() as conn:
            old = conn.execute("SELECT notes FROM leads WHERE id=?", (lead_id,)).fetchone()
            conn.execute("""
                UPDATE leads SET institute_name=?, contact_person=?, phone=?, email=?, city=?,
                lead_source=?, status=?, pain_point=?, notes=?, last_contact_date=?,
                next_followup_date=?, demo_date=?, updated_at=? WHERE id=?
            """, (institute_name, contact_person, phone or None, email or None, city or None,
                  lead_source or None, status, pain_point or None, notes,
                  last_contact_date or None, next_followup_date or None, demo_date or None, now, lead_id))
            old_notes = old["notes"] if old else ""
            if notes.strip() and notes.strip() != (old_notes or "").strip():
                conn.execute("INSERT INTO lead_notes (lead_id, note, classification) VALUES (?,?,?)",
                             (lead_id, f"[Updated notes] {notes}", classify_note(notes)))
        return RedirectResponse(f"/lead/{lead_id}", status_code=303)

    @app.get("/lead/{lead_id}", response_class=HTMLResponse)
    def lead_detail(request: Request, lead_id: int):
        lead = get_lead(lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found")
        notes = get_lead_notes(lead_id)
        ctx = _base_ctx("leads", lead["institute_name"])
        ctx["lead"] = lead; ctx["notes"] = notes
        return templates.TemplateResponse("lead_detail.html", {"request": request, **ctx})

    @app.post("/lead/{lead_id}/add-note")
    async def add_note(lead_id: int, note: str = Form(...)):
        with db_conn() as conn:
            conn.execute("INSERT INTO lead_notes (lead_id, note, classification) VALUES (?,?,?)",
                         (lead_id, note, classify_note(note)))
            conn.execute("UPDATE leads SET last_contact_date=?, updated_at=? WHERE id=?",
                         (today_str(), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), lead_id))
        return RedirectResponse(f"/lead/{lead_id}", status_code=303)

    @app.post("/delete-lead/{lead_id}")
    async def delete_lead(lead_id: int):
        with db_conn() as conn:
            conn.execute("DELETE FROM lead_notes WHERE lead_id=?", (lead_id,))
            conn.execute("DELETE FROM leads WHERE id=?", (lead_id,))
        return RedirectResponse("/leads", status_code=303)

    @app.get("/analytics", response_class=HTMLResponse)
    def analytics(request: Request):
        with db_conn() as conn:
            total_leads = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
            customers   = conn.execute("SELECT COUNT(*) FROM leads WHERE status='CUSTOMER'").fetchone()[0]
            demo_done   = conn.execute("SELECT COUNT(*) FROM leads WHERE status IN ('DEMO_BOOKED','DEMO_COMPLETED','PILOT','CUSTOMER')").fetchone()[0]
            conv_rate   = round((customers / total_leads * 100), 1) if total_leads > 0 else 0
            demo_rate   = round((demo_done / total_leads * 100), 1) if total_leads > 0 else 0
            status_counts = {r["status"]: r["cnt"] for r in conn.execute("SELECT status, COUNT(*) as cnt FROM leads GROUP BY status").fetchall()}
            city_counts   = {r["city"]: r["cnt"] for r in conn.execute("SELECT city, COUNT(*) as cnt FROM leads WHERE city IS NOT NULL AND city != '' GROUP BY city ORDER BY cnt DESC LIMIT 10").fetchall()}
            pain_counts   = {r["pain_point"]: r["cnt"] for r in conn.execute("SELECT pain_point, COUNT(*) as cnt FROM leads WHERE pain_point IS NOT NULL AND pain_point != '' GROUP BY pain_point ORDER BY cnt DESC").fetchall()}
            source_counts = {r["lead_source"]: r["cnt"] for r in conn.execute("SELECT lead_source, COUNT(*) as cnt FROM leads WHERE lead_source IS NOT NULL AND lead_source != '' GROUP BY lead_source ORDER BY cnt DESC").fetchall()}
            monthly_rows  = conn.execute("SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt FROM leads GROUP BY month ORDER BY month DESC LIMIT 12").fetchall()
            monthly_growth = dict(reversed([(r["month"], r["cnt"]) for r in monthly_rows]))
        ctx = _base_ctx("analytics", "Analytics")
        ctx.update({"total_leads": total_leads, "conversion_rate": conv_rate, "demo_rate": demo_rate,
                    "status_counts": status_counts, "city_counts": city_counts,
                    "pain_counts": pain_counts, "source_counts": source_counts,
                    "monthly_growth": monthly_growth})
        return templates.TemplateResponse("analytics.html", {"request": request, **ctx})

    return app


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 10 — CLI  ░░
# ══════════════════════════════════════════════════════════════════════════════

def _confirm(prompt: str) -> bool:
    return input(f"\n{prompt} [y/N]: ").strip().lower() in ("y", "yes")


def _get_bot_cli(headless: bool = True) -> Any:
    bot = make_bot(headless=headless)
    if bot is None:
        print("❌  Bot failed to start. Run: python techgrowth_hub.py setup")
        sys.exit(1)
    return bot


def cli_setup(args):
    print("\n🔧  FIRST-TIME SETUP")
    print("   A Chrome window will open. Scan the QR code from your phone.\n")
    bot = make_bot(headless=False)
    if bot is not None:
        print("\n✅  Session saved → cg_data/wa_session/")
        print("   You can now run: python techgrowth_hub.py run")
        bot.stop()
    else:
        print("❌  Setup failed.")


def cli_run(args):
    run_scheduler()


def cli_web(args):
    try:
        import uvicorn
    except ImportError:
        print("❌  Install uvicorn: pip install uvicorn")
        sys.exit(1)
    init_db()
    _setup_templates()
    port = int(os.environ.get("PORT", 8000))
    print(f"\n🌐  TechGrowth Hub CRM starting at http://localhost:{port}\n")
    app = _build_fastapi_app()
    if app is None:
        print("❌  Install fastapi: pip install fastapi uvicorn jinja2")
        sys.exit(1)
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


def cli_both(args=None):
    """Run web server + WhatsApp scheduler concurrently."""
    init_db()
    _setup_templates()
    port = int(os.environ.get("PORT", 8000))
    print()
    print("=" * 60)
    print(f"  🚀  {COMMUNITY_NAME}")
    print(f"  {COMMUNITY_TAGLINE}")
    print("=" * 60)
    print(f"  🌐  CRM Web UI  →  http://localhost:{port}")
    print(f"  📅  WhatsApp scheduler running in background")
    print(f"  📁  Data  →  {DATA_DIR}")
    print(f"  📋  Logs  →  {LOG_DIR}")
    print(f"  🛑  Press Ctrl+C to stop")
    print("=" * 60)
    print()
    # Start scheduler in background thread
    sched_thread = threading.Thread(target=run_scheduler, daemon=True)
    sched_thread.start()
    # Start web in foreground
    try:
        import uvicorn
    except ImportError:
        print("❌  Install uvicorn: pip install uvicorn")
        sys.exit(1)
    app = _build_fastapi_app()
    if app is None:
        print("❌  Install fastapi: pip install fastapi uvicorn jinja2")
        sys.exit(1)
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)


def cli_welcome(args):
    mid = f"m_{args.phone[-8:]}"
    ok  = sheets_add_member(mid, args.name, args.phone)
    print("✅  Added to Sheets." if ok else "⚠️   Sheets registration failed.")
    ob = OnboardingEngine()
    ob.register(mid, args.name, args.phone)
    print("📋  Onboarding sequence started.")
    msg = welcome_message(args.name)
    print(f"\n── Welcome message preview ──\n{msg}\n─────────────────────────────")
    if _confirm("Send welcome DM via WhatsApp?"):
        bot = _get_bot_cli()
        print("✅  DM sent!" if bot.send_dm(args.phone, msg) else "❌  DM failed.")
        bot.stop()


def cli_post(args):
    msg = format_content(get_content(args.type))
    print(f"\n── {args.type} preview ───\n{msg[:600]}\n─────────────────────────")
    if _confirm("Post this to the group?"):
        bot = _get_bot_cli()
        print("✅  Posted!" if bot.send_group(msg) else "❌  Failed.")
        bot.stop()


def cli_leaderboard(args):
    print("📊  Fetching leaderboard...")
    board = sheets_leaderboard(10)
    msg   = format_leaderboard(board)
    print(f"\n{msg}\n")
    if _confirm("Post leaderboard to group?"):
        bot = _get_bot_cli()
        print("✅  Posted!" if bot.send_group(msg) else "❌  Failed.")
        bot.stop()


def cli_dm(args):
    msg = " ".join(args.message)
    print(f"\n── DM to {args.phone} ──\n{msg}\n────────────────────────")
    if _confirm("Send?"):
        bot = _get_bot_cli()
        print("✅  Sent!" if bot.send_dm(args.phone, msg) else "❌  Failed.")
        bot.stop()


def cli_stats(args):
    print("📈  Fetching today's stats...")
    stats = sheets_daily_stats()
    print("\n── Today's Analytics ───")
    for k, v in stats.items():
        print(f"  {k:25s}: {v}")
    print("────────────────────────")


def cli_inactive(args):
    days = getattr(args, "days", 3)
    print(f"🔍  Members inactive > {days} days:")
    members = sheets_get_inactive(days=days)
    if not members:
        print("✅  None found."); return
    for m in members[:20]:
        print(f"  {m.get('name','?'):20s}  last: {str(m.get('last_active','?'))[:10]}  phone: {m.get('phone','?')}")
    print(f"\n  Total: {len(members)}")


def cli_referral(args):
    ok = sheets_track_referral(args.referrer_id, args.new_member_id, args.new_member_name)
    if ok:
        pts = sheets_award_points(args.referrer_id, "invite_accepted", f"Referred {args.new_member_name}")
        print(f"✅  Referral tracked. {args.referrer_id} now has {pts} pts.")
    else:
        print("❌  Referral tracking failed.")


def cli_onboarding(args):
    stats = OnboardingEngine().stats()
    print("\n── Onboarding Pipeline ──")
    print(f"  Total in pipeline : {stats['total']}")
    print(f"  In progress       : {stats['in_progress']}")
    print(f"  Completed         : {stats['completed']}")
    print("─────────────────────────")


def cli_dashboard(args):
    path = generate_community_dashboard(open_browser=True)
    print(f"✅  Community dashboard → {path}")


def cli_test(args):
    print("🧪  Running test — sending all post types now...\n")
    for name, fn in [("morning_tip", task_morning_tip), ("networking_prompt", task_networking_prompt),
                     ("free_tool", task_afternoon_tool), ("daily_challenge", task_daily_challenge)]:
        print(f"  → Sending {name}...")
        fn()
        time.sleep(2)
    print("\n✅  Test complete.")


def main():
    p = argparse.ArgumentParser(
        prog="python techgrowth_hub.py",
        description=f"🚀 {COMMUNITY_NAME} — CRM + Community Growth Automation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
COMMANDS:
  web                                 Start CRM web server (default port 8000)
  setup                               First-time WhatsApp QR scan
  run                                 Start the WhatsApp scheduler
  both                                Web server + scheduler together
  dashboard                           Generate community analytics HTML dashboard
  welcome <name> <phone>              Add + welcome a new member
  post <type>                         Send a content post now
  leaderboard                         Generate + post leaderboard
  dm <phone> <message...>             Send a custom DM
  stats                               Show today's analytics
  inactive [--days N]                 List inactive members
  referral <ref_id> <new_id> <name>   Record a referral
  onboarding                          Show onboarding pipeline status
  test                                Send all post types now (testing)

POST TYPES:
  ai_tip  coding_tip  growth_hack  networking_prompt
  free_tool  opportunity  linkedin_post  daily_challenge  motivational
        """,
    )
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("web",         help="Start CRM web server")
    sub.add_parser("setup",       help="First-time WhatsApp QR scan")
    sub.add_parser("run",         help="Start the WhatsApp scheduler")
    sub.add_parser("both",        help="Web + scheduler together")
    sub.add_parser("dashboard",   help="Generate community analytics HTML dashboard")
    sub.add_parser("test",        help="Send all post types now")
    sub.add_parser("stats",       help="Show today's analytics")
    sub.add_parser("leaderboard", help="Generate + post leaderboard")
    sub.add_parser("onboarding",  help="Show onboarding pipeline status")

    pw = sub.add_parser("welcome")
    pw.add_argument("name"); pw.add_argument("phone")

    pp = sub.add_parser("post")
    pp.add_argument("type", choices=[
        "ai_tip", "coding_tip", "growth_hack", "networking_prompt",
        "free_tool", "opportunity", "linkedin_post", "daily_challenge", "motivational",
    ])

    pd = sub.add_parser("dm")
    pd.add_argument("phone"); pd.add_argument("message", nargs="+")

    pi = sub.add_parser("inactive")
    pi.add_argument("--days", type=int, default=3)

    pr = sub.add_parser("referral")
    pr.add_argument("referrer_id"); pr.add_argument("new_member_id"); pr.add_argument("new_member_name")

    dispatch = {
        "web":         cli_web,
        "setup":       cli_setup,
        "run":         cli_run,
        "both":        cli_both,
        "welcome":     cli_welcome,
        "post":        cli_post,
        "leaderboard": cli_leaderboard,
        "dm":          cli_dm,
        "stats":       cli_stats,
        "inactive":    cli_inactive,
        "referral":    cli_referral,
        "onboarding":  cli_onboarding,
        "dashboard":   cli_dashboard,
        "test":        cli_test,
    }

    args = p.parse_args()
    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        # No command given → just run everything
        cli_both(args)


# ══════════════════════════════════════════════════════════════════════════════
# ░░  SECTION 11 — GOOGLE APPS SCRIPT  (paste into Apps Script editor)  ░░
# ══════════════════════════════════════════════════════════════════════════════
#
#  INSTRUCTIONS:
#  1. Open your Google Sheet → Extensions → Apps Script
#  2. Paste EVERYTHING between the triple-quoted string below
#  3. Run initSheets() once to create all tab headers
#  4. Deploy → New deployment → Web app
#     - Execute as: Me  |  Access: Anyone
#  5. Copy the URL → update GOOGLE_SHEETS_WEBHOOK above
#
APPS_SCRIPT_CODE = r'''
/* ===================================================================
   TechGrowth Hub — Google Apps Script Backend
   =================================================================== */

const SHEETS = {
  MEMBERS:"Members", ENGAGEMENT:"Engagement", REFERRALS:"Referrals",
  LEADERBOARD:"Leaderboard", CONTENT:"ContentSchedule",
  ANALYTICS:"Analytics", ONBOARDING:"Onboarding"
};

function doGet(e) {
  const a = e.parameter.action;
  try {
    const m = {get_rows:getRows, query_rows:queryRows,
               top_members:topMembers, daily_stats:dailyStats};
    return j(m[a] ? m[a](e.parameter) : {error:"Unknown: "+a});
  } catch(err){ return j({error:err.toString()}); }
}

function doPost(e) {
  let b; try{ b=JSON.parse(e.postData.contents); }catch(err){ return j({error:"Bad JSON"}); }
  const a = b.action;
  try {
    const m = {append_row:appendRow, update_cell:updateCell,
               increment_points:incPts, increment_field:incField,
               overwrite_sheet:overwriteSheet};
    return j(m[a] ? m[a](b) : {error:"Unknown: "+a});
  } catch(err){ return j({error:err.toString()}); }
}

function j(d){ return ContentService.createTextOutput(JSON.stringify(d)).setMimeType(ContentService.MimeType.JSON); }
function getSheet(n){ return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(n); }

function getOrCreate(n, headers) {
  let s = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(n);
  if (!s) {
    s = SpreadsheetApp.getActiveSpreadsheet().insertSheet(n);
    s.appendRow(headers);
    s.getRange(1,1,1,headers.length).setBackground("#1a73e8").setFontColor("#fff").setFontWeight("bold");
  }
  return s;
}

function getRows(p) {
  const s = getSheet(p.sheet); if(!s) return {rows:[]};
  const d = s.getDataRange().getValues(); if(d.length<2) return {rows:[]};
  const h = d[0];
  return {rows: d.slice(1).map(r=>Object.fromEntries(h.map((k,i)=>[k,r[i]])))};
}

function queryRows(p) {
  let rows = getRows(p).rows;
  if(p.status) rows = rows.filter(r=>r.status===p.status);
  if(p.filter) {
    const m = p.filter.match(/last_active < (.+)/);
    if(m){ const c=new Date(m[1]); rows=rows.filter(r=>new Date(r.last_active)<c); }
  }
  return {rows};
}

function topMembers(p) {
  const all = getRows(p).rows.filter(r=>r.status==="active");
  const f   = p.sort_by||"points", lim = parseInt(p.limit)||10;
  return {rows: all.sort((a,b)=>(Number(b[f])||0)-(Number(a[f])||0)).slice(0,lim)};
}

function dailyStats(p) {
  const s=getSheet(p.sheet); if(!s) return {};
  const d=s.getDataRange().getValues(); if(d.length<2) return {};
  const h=d[0], di=h.indexOf("date"), ti=h.indexOf("action_type"), mi=h.indexOf("member_id");
  const rows=d.slice(1).filter(r=>String(r[di]).startsWith(p.date));
  return {
    unique_members: new Set(rows.map(r=>r[mi])).size,
    total_messages: rows.filter(r=>r[ti]==="message").length,
    reactions:      rows.filter(r=>r[ti]==="reaction").length,
    shares:         rows.filter(r=>r[ti]==="share").length
  };
}

function appendRow(b) {
  const s=getOrCreate(b.sheet, Object.keys(b.row));
  const h=s.getRange(1,1,1,s.getLastColumn()).getValues()[0];
  s.appendRow(h.map(k=>b.row[k]!==undefined?b.row[k]:""));
  return {success:true};
}

function updateCell(b) {
  const s=getSheet(b.sheet); if(!s) return {success:false};
  const d=s.getDataRange().getValues(), h=d[0];
  const ki=h.indexOf(b.key_col), ci=h.indexOf(b.col);
  if(ki<0||ci<0) return {success:false};
  for(let i=1;i<d.length;i++){
    if(String(d[i][ki])===String(b.key_val)){
      s.getRange(i+1,ci+1).setValue(b.val); return {success:true};
    }
  }
  return {success:false};
}

function incPts(b) {
  const s=getSheet(b.sheet); if(!s) return {new_total:0};
  const d=s.getDataRange().getValues(), h=d[0];
  const ii=h.indexOf("member_id"), pi=h.indexOf("points");
  for(let i=1;i<d.length;i++){
    if(String(d[i][ii])===String(b.member_id)){
      const n=Number(d[i][pi]||0)+Number(b.points);
      s.getRange(i+1,pi+1).setValue(n);
      appendRow({sheet:SHEETS.ENGAGEMENT,row:{timestamp:new Date().toISOString(),
        member_id:b.member_id,action_type:b.action,content_ref:b.note||"",
        date:new Date().toISOString().slice(0,10)}});
      return {new_total:n};
    }
  }
  return {new_total:0};
}

function incField(b) {
  const s=getSheet(b.sheet); if(!s) return {success:false};
  const d=s.getDataRange().getValues(), h=d[0];
  const ki=h.indexOf(b.key_col), fi=h.indexOf(b.field);
  for(let i=1;i<d.length;i++){
    if(String(d[i][ki])===String(b.key_val)){
      s.getRange(i+1,fi+1).setValue(Number(d[i][fi]||0)+1); return {success:true};
    }
  }
  return {success:false};
}

function overwriteSheet(b) {
  if(!b.rows||!b.rows.length) return {success:false};
  const s=getOrCreate(b.sheet, Object.keys(b.rows[0]));
  if(s.getLastRow()>1) s.getRange(2,1,s.getLastRow()-1,s.getLastColumn()).clearContent();
  const h=s.getRange(1,1,1,s.getLastColumn()).getValues()[0];
  b.rows.forEach(r=>s.appendRow(h.map(k=>r[k]!==undefined?r[k]:"")));
  return {success:true};
}

function initSheets() {
  const schemas = {
    Members:["member_id","name","phone","join_date","source","referred_by","points","tier","badge","last_active","status","messages_sent","invites_sent","invites_accepted"],
    Engagement:["timestamp","member_id","action_type","content_ref","date"],
    Referrals:["timestamp","referrer_id","new_member_id","new_member_name","status","points_awarded"],
    Leaderboard:["rank","name","tier","badge","points","invites","messages"],
    ContentSchedule:["date","scheduled_time","post_type","content_preview","status","created_at"],
    Analytics:["date","timestamp","active_members","total_messages","reactions","shares","new_members","invites_sent"],
    Onboarding:["member_id","name","step_type","sent_at","status"]
  };
  Object.entries(schemas).forEach(([n,h])=>getOrCreate(n,h));
  SpreadsheetApp.getUi().alert("✅ All 7 sheets initialised!");
}
'''  # END APPS SCRIPT CODE


# ── Auto-start: runs directly without any command ─────────────────────────────
# Called by Railway / any server via:  python techgrowth_hub.py
# Also called locally the same way — no subcommand needed.

if __name__ == "__main__":
    import sys as _sys
    # If a subcommand is given (setup, post, dm, etc.) → honour it
    # If nothing is given → just boot everything (web + scheduler)
    if len(_sys.argv) > 1:
        main()
    else:
        cli_both()
