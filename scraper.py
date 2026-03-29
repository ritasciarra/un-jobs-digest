"""
UN Jobs Weekly Digest Scraper
Scrapes P5 and D1 positions from:
  - unjobs.org (aggregator covering most UN agencies)
  - Inspira (UN Secretariat) via unjobs.org mirror
  - Individual agency pages via unjobs.org filters

Run manually or via GitHub Actions every Friday.
"""

import os
import smtplib
import logging
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]   # your email address
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]       # Gmail address used to send
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]    # Gmail App Password (not your login password)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UN-Jobs-Digest-Bot/1.0; "
        "personal use weekly digest)"
    )
}

# ── Sources ───────────────────────────────────────────────────────────────────
# unjobs.org is a well-structured aggregator that covers Inspira, UNDP, UNICEF,
# WHO, UNHCR, WFP, ILO, FAO, and dozens of other UN system organisations.
# We query it twice — once for P-5 and once for D-1 — using their grade filter.

SOURCES = [
    {
        "label": "P-5",
        "url": "https://unjobs.org/duty_stations/ALL/categories/ALL/grades/P-5",
    },
    {
        "label": "D-1",
        "url": "https://unjobs.org/duty_stations/ALL/categories/ALL/grades/D-1",
    },
]

# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_unjobs(url: str, grade_label: str) -> list[dict]:
    """Scrape a single unjobs.org grade page and return a list of job dicts."""
    log.info("Fetching %s", url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    jobs = []

    # unjobs.org lists jobs inside <div class="job"> or <article> elements.
    # We try both selectors for resilience against minor HTML changes.
    containers = soup.select("div.job, article.job, li.job")
    if not containers:
        # Fallback: look for any <a> whose href contains /jobs/
        containers = soup.select("a[href*='/jobs/']")

    for item in containers:
        # Title
        title_el = item.select_one("h2, h3, .job-title, a.job-title, a[href*='/jobs/']")
        title = title_el.get_text(strip=True) if title_el else "Untitled"

        # Organisation
        org_el = item.select_one(".organization, .org, .agency, .employer")
        org = org_el.get_text(strip=True) if org_el else "United Nations"

        # Location / duty station
        loc_el = item.select_one(".location, .duty-station, .city")
        location = loc_el.get_text(strip=True) if loc_el else "N/A"

        # Closing date
        date_el = item.select_one(".deadline, .closing-date, time")
        closing = date_el.get_text(strip=True) if date_el else "See posting"

        # Link
        link_el = item.select_one("a[href*='/jobs/'], a.job-title, h2 a, h3 a")
        href = link_el["href"] if link_el and link_el.has_attr("href") else "#"
        if href.startswith("/"):
            href = "https://unjobs.org" + href

        # Skip obviously unrelated results
        if not title or title == "Untitled":
            continue

        jobs.append({
            "grade":    grade_label,
            "title":    title,
            "org":      org,
            "location": location,
            "closing":  closing,
            "url":      href,
        })

    log.info("Found %d jobs for grade %s", len(jobs), grade_label)
    return jobs


def fetch_all_jobs() -> list[dict]:
    all_jobs = []
    for source in SOURCES:
        all_jobs.extend(scrape_unjobs(source["url"], source["label"]))
    # Deduplicate by URL
    seen = set()
    unique = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)
    return unique


# ── Email formatting ──────────────────────────────────────────────────────────

def build_html_email(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    p5_jobs = [j for j in jobs if j["grade"] == "P-5"]
    d1_jobs = [j for j in jobs if j["grade"] == "D-1"]

    def job_rows(job_list: list[dict]) -> str:
        if not job_list:
            return "<tr><td colspan='4' style='color:#888;padding:12px 0'>No new postings found this week.</td></tr>"
        rows = []
        for j in job_list:
            rows.append(f"""
            <tr>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-weight:500">
                <a href="{j['url']}" style="color:#1a56db;text-decoration:none">{j['title']}</a>
              </td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#555">{j['org']}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#555">{j['location']}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#888;white-space:nowrap">{j['closing']}</td>
            </tr>""")
        return "".join(rows)

    def section(grade: str, color: str, job_list: list[dict]) -> str:
        return f"""
        <h2 style="font-size:16px;font-weight:600;color:{color};margin:32px 0 8px">
          {grade} Positions &nbsp;<span style="font-size:13px;font-weight:400;color:#888">({len(job_list)} found)</span>
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0"
               style="border-collapse:collapse;font-size:14px;font-family:sans-serif">
          <thead>
            <tr style="background:#f5f5f5">
              <th style="padding:8px;text-align:left;font-weight:600;color:#333;border-bottom:2px solid #ddd">Position</th>
              <th style="padding:8px;text-align:left;font-weight:600;color:#333;border-bottom:2px solid #ddd">Organisation</th>
              <th style="padding:8px;text-align:left;font-weight:600;color:#333;border-bottom:2px solid #ddd">Location</th>
              <th style="padding:8px;text-align:left;font-weight:600;color:#333;border-bottom:2px solid #ddd">Closing</th>
            </tr>
          </thead>
          <tbody>
            {job_rows(job_list)}
          </tbody>
        </table>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9f9f9;font-family:Arial,sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0">
    <tr><td align="center" style="padding:24px 16px">
      <table width="680" cellpadding="0" cellspacing="0"
             style="background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)">

        <!-- Header -->
        <tr>
          <td style="background:#003366;padding:28px 32px">
            <p style="margin:0;color:#fff;font-size:22px;font-weight:700">
              UN P-5 &amp; D-1 Weekly Digest
            </p>
            <p style="margin:6px 0 0;color:#a8c4e0;font-size:13px">
              Week of {today} &nbsp;·&nbsp; {len(jobs)} positions found
            </p>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:24px 32px">
            {section("P-5", "#1a56db", p5_jobs)}
            {section("D-1", "#0e7c5b", d1_jobs)}

            <p style="margin:32px 0 0;font-size:12px;color:#aaa;border-top:1px solid #eee;padding-top:16px">
              Sources: <a href="https://unjobs.org" style="color:#aaa">unjobs.org</a> ·
              <a href="https://inspira.un.org" style="color:#aaa">inspira.un.org</a> ·
              Automated digest — verify deadlines on the official posting.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return html


def build_plain_text(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [
        f"UN P-5 & D-1 Weekly Digest — {today}",
        f"{len(jobs)} positions found",
        "",
    ]
    for grade in ("P-5", "D-1"):
        grade_jobs = [j for j in jobs if j["grade"] == grade]
        lines.append(f"{'─'*60}")
        lines.append(f"  {grade} POSITIONS ({len(grade_jobs)} found)")
        lines.append(f"{'─'*60}")
        if not grade_jobs:
            lines.append("  No new postings found this week.\n")
        else:
            for j in grade_jobs:
                lines += [
                    f"  {j['title']}",
                    f"  Organisation : {j['org']}",
                    f"  Location     : {j['location']}",
                    f"  Closing      : {j['closing']}",
                    f"  Link         : {j['url']}",
                    "",
                ]
    lines += [
        "─"*60,
        "Sources: unjobs.org · inspira.un.org",
        "Verify deadlines on the official posting.",
    ]
    return "\n".join(lines)


# ── Email sending ─────────────────────────────────────────────────────────────

def send_email(jobs: list[dict]) -> None:
    today = date.today().strftime("%B %d, %Y")
    subject = f"UN P-5 & D-1 Digest – {today} ({len(jobs)} positions)"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    msg.attach(MIMEText(build_plain_text(jobs), "plain"))
    msg.attach(MIMEText(build_html_email(jobs),  "html"))

    log.info("Sending email to %s …", RECIPIENT_EMAIL)
    with smtplib.SMTP("smtp.mail.yahoo.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    log.info("Email sent successfully.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    log.info("Starting UN jobs digest …")
    jobs = fetch_all_jobs()

    if not jobs:
        log.warning("No jobs found — sending 'no results' email anyway.")

    send_email(jobs)
    log.info("Done. %d total positions sent.", len(jobs))


if __name__ == "__main__":
    main()
