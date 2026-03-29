# UN P-5 & D-1 Weekly Digest — Setup Guide

Every Friday morning this system scrapes **unjobs.org** (which aggregates
Inspira / UN Secretariat, UNDP, UNICEF, WHO, UNHCR, WFP, ILO, FAO and more)
for P-5 and D-1 positions and emails you a formatted digest.

---

## Files in this project

```
scraper.py                          ← main script
requirements.txt                    ← Python dependencies
.github/workflows/weekly_digest.yml ← GitHub Actions schedule
README.md                           ← this file
```

---

## Step-by-step setup

### 1. Create a GitHub repository

1. Go to https://github.com and sign in (create a free account if needed).
2. Click **New repository**.
3. Name it something like `un-jobs-digest`. Keep it **Private**.
4. Click **Create repository**.

### 2. Upload the files

Upload all four files to the root of the repository:
- `scraper.py`
- `requirements.txt`
- `.github/workflows/weekly_digest.yml`

The `.github/workflows/` folder must be created exactly as named.

### 3. Create a Gmail App Password

The scraper sends email via Gmail. You need an **App Password** (not your
normal Gmail password) because Google blocks direct password login.

1. Go to your Google Account → **Security**.
2. Enable **2-Step Verification** if not already on.
3. Search for **App passwords** → create one for "Mail" / "Other device".
4. Copy the 16-character password — you'll only see it once.

> **Alternative**: use any other SMTP provider. Change the SMTP settings
> in `scraper.py` near the `send_email` function.

### 4. Add GitHub Secrets

Your email credentials must never be stored in code. GitHub Secrets keep
them encrypted.

1. In your repository, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret** for each of the three below:

| Secret name        | Value                                      |
|--------------------|--------------------------------------------|
| `RECIPIENT_EMAIL`  | The email address where you want digests   |
| `SENDER_EMAIL`     | Your Gmail address (used to send)          |
| `SENDER_PASSWORD`  | The 16-char App Password from step 3       |

### 5. Test it manually

1. Go to the **Actions** tab in your repository.
2. Click **UN Jobs Weekly Digest** in the left sidebar.
3. Click **Run workflow** → **Run workflow**.
4. Watch the logs — it should finish in under a minute.
5. Check your inbox!

### 6. Adjust the schedule timezone

The workflow runs **Fridays at 14:00 UTC**, which equals **08:00 AM in
El Salvador (CST, UTC-6)**.

If you want a different time, edit `.github/workflows/weekly_digest.yml`
and change the cron line. Use https://crontab.guru to generate cron syntax.

```
# Format: minute hour day-of-month month day-of-week
# day-of-week: 5 = Friday
0 14 * * 5   →  Friday 14:00 UTC = 08:00 AM El Salvador
0 12 * * 5   →  Friday 12:00 UTC = 06:00 AM El Salvador
```

---

## Troubleshooting

**No jobs found in the email**
The scraper uses CSS selectors that match unjobs.org's current layout. If
unjobs.org redesigns their site, the selectors may need updating. Open an
issue or check the Actions logs for errors.

**Gmail authentication failed**
Make sure you used an App Password (step 3), not your regular Gmail password.
Also confirm 2-Step Verification is active on the sending account.

**Email goes to spam**
Add your sender address to your contacts. The plain-text fallback version
of the email helps with spam scoring.

**Want to add more grade levels** (e.g. P-4)?
Edit `scraper.py` and add another entry to the `SOURCES` list:
```python
{"label": "P-4", "url": "https://unjobs.org/duty_stations/ALL/categories/ALL/grades/P-4"},
```

---

## How it works

```
GitHub Actions (Friday 8 AM)
    │
    ▼
scraper.py
    ├── GET unjobs.org/grades/P-5   → parse job listings
    ├── GET unjobs.org/grades/D-1   → parse job listings
    ├── Deduplicate by URL
    ├── Build HTML + plain-text email
    └── Send via Gmail SMTP
```

unjobs.org aggregates postings from the entire UN system including:
Inspira (UN Secretariat), UNDP, UNICEF, WHO, UNHCR, WFP, ILO, FAO,
UNOPS, UNESCO, UNFPA, IOM, and many others.

---

## Cost

**Free.** GitHub Actions gives 2,000 free minutes/month on private repos.
This job runs in under 60 seconds per week — well within the free tier.
