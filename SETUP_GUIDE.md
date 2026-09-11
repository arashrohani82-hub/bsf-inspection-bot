# Metra / BSF – Telegram Inspection Bot Setup Guide

The same Telegram bot now keeps the two companies separate:

- **BSF Inspections:** preserves the existing façade, parking and anchor report workflows and original BSF certificate forms.
- **Metra Consultation:** provides dedicated project-definition checklists and Metra draft reports for Loi 122 façades, Loi 122 parking, Loi 16, annual anchor inspections and five-year anchor inspections.

The first `/start` screen asks for the company. Metra then asks for the legal/service family before offering **Define new project** or **Write a report**. Existing BSF projects without a company field remain BSF projects for backward compatibility.

## What you need (free)
1. **Telegram Bot Token** — from @BotFather on Telegram
2. **Anthropic API Key** — from console.anthropic.com
3. **A server to run the bot** — Railway.app (free tier works)

---

## Step 1 – Create your Telegram Bot (2 minutes)

1. Open Telegram → search **@BotFather**
2. Send `/newbot`
3. Choose a name: e.g. `BSF Inspection Bot`
4. Choose a username: e.g. `bsfinspection_bot`
5. BotFather gives you a **token** like:
   `7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
6. **Save this token.**

---

## Step 2 – Get Anthropic API Key

1. Go to https://console.anthropic.com
2. Sign in → API Keys → Create Key
3. **Save the key** (starts with `sk-ant-...`)

---

## Step 3 – Deploy on Railway (free, no credit card)

1. Go to https://railway.app → sign in with GitHub
2. Click **New Project → Deploy from GitHub repo**
3. Upload these files to a GitHub repo:
   - `inspection_bot.py`
   - `Template.docx`
   - `requirements.txt`
   - `Procfile`

4. In Railway → your project → **Variables**, add:
   ```
   TELEGRAM_TOKEN   = your_telegram_token_here
   ANTHROPIC_API_KEY = sk-ant-...your_key_here
   ```

5. Railway auto-deploys. Bot goes live in ~2 minutes.

---

## requirements.txt (create this file)
```
python-telegram-bot==21.6
anthropic
python-docx
pillow
requests
```

## Procfile (create this file)
```
worker: python inspection_bot.py
```

---

## How to use the bot on-site

| Step | Action |
|------|--------|
| 1 | Open Telegram → your bot → `/start` |
| 2 | Enter project name |
| 3 | Enter site address |
| 4 | Send a photo |
| 5 | Choose element type from keyboard |
| 6 | Type location (e.g. "Roof NE corner, Anchor #5") |
| 7 | Describe problem (or type `skip`) |
| 8 | Bot shows AI caption → confirm or edit |
| 9 | Repeat for all photos |
| 10 | Type `/done` → bot sends FR + EN Word reports |

---

## Commands
- `/start` — New inspection
- `/status` — See how many photos collected so far
- `/done` — Generate and receive both reports
- `/cancel` — Cancel current inspection

---

## Cost estimate
- Anthropic API: ~$0.01–0.03 per photo (vision call)
- For 50 photos/inspection: ~$0.50–1.50 per report
- Railway: Free tier = enough for personal use
