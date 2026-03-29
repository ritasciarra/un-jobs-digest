"""
UN Jobs Weekly Digest
Uses official RSS feeds instead of scraping (more reliable, no blocks).
Sends via Yahoo Mail SMTP.
"""

import os
import smtplib
import logging
import xml.etree.ElementTree as ET
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]
SENDER_PASSWORD = os.environ["SENDER_PASSWORD"]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UN-Jobs-Digest/1.0)"}

# ── RSS Sources ───────────────────────────────────────────────────────────────
# unjobs.org provides RSS feeds per grade — reliable and not blocked

FEEDS = [
    {"label": "P-5", "url": "https://unjobs.org/grades/p-5.rss"},
    {"label": "D-1", "url": "https://unjobs.org/grades/d-1.rss"},
]

# ── Fetch jobs from RSS ───────────────────────────────────────────────────────

def fetch_feed(label: str, url: str) -> list[dict]:
    log.info("Fetching %s feed: %s", label, url)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Failed to fetch %s: %s", url, exc)
        return []

    jobs = []
    try:
        root = ET.fromstring(resp.content)
        items = root.findall(".//item")
        for item in items:
            title    = item.findtext("title", "Untitled").strip()
            link     = item.findtext("link", "#").strip()
            desc     = item.findtext("description", "").strip()
            pub_date = item.findtext("pubDate", "").strip()

            org = "United Nations"
            if " - " in title:
                parts = title.rsplit(" - ", 1)
                title = parts[0].strip()
                org   = parts[1].strip()

            jobs.append({
                "grade":    label,
                "title":    title,
                "org":      org,
                "location": _extract_location(desc),
                "closing":  pub_date[:16] if pub_date else "See posting",
                "url":      link,
            })
    except ET.ParseError as exc:
        log.error("Failed to parse RSS for %s: %s", label, exc)

    log.info("Found %d jobs for %s", len(jobs), label)
    return jobs


def _extract_location(description: str) -> str:
    lower = description.lower()
    for keyword in ["new york", "geneva", "nairobi", "rome", "vienna",
                    "bangkok", "addis ababa", "beirut", "dakar", "cairo",
                    "brussels", "paris", "washington", "remote"]:
        if keyword in lower:
            return keyword.title()
    return "See posting"


def fetch_all_jobs() -> list[dict]:
    all_jobs = []
    for feed in FEEDS:
        all_jobs.extend(fetch_feed(feed["label"], feed["url"]))
    seen, unique = set(), []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)
    return unique


# ── Email formatting ──────────────────────────────────────────────────────────

def build_html_email(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    p5    = [j for j in jobs if j["grade"] == "P-5"]
    d1    = [j for j in jobs if j["grade"] == "D-1"]

    def rows(job_list):
        if not job_list:
            return "<tr><td colspan='4' style='color:#888;padding:12px'>No postings found this week.</td></tr>"
        out = []
        for j in job_list:
            out.append(f"""<tr>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;font-weight:500">
                <a href="{j['url']}" style="color:#1a56db;text-decoration:none">{j['title']}</a>
              </td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#555">{j['org']}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#555">{j['location']}</td>
              <td style="padding:10px 8px;border-bottom:1px solid #eee;color:#888;white-space:nowrap">{j['closing']}</td>
            </tr>""")
        return "".join(out)

    def section(grade, color, job_list):
        return f"""
        <h2 style="font-size:16px;font-weight:600;color:{color};margin:32px 0 8px">
          {grade} Positions &nbsp;<span style="font-size:13px;font-weight:400;color:#888">({len(job_list)} found)</span>
        </h2>
        <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:14px">
          <thead><tr style="background:#f5f5f5">
            <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd">Position</th>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd">Organisation</th>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd">Location</th>
            <th style="padding:8px;text-align:left;border-bottom:2px solid #ddd">Published</th>
          </tr></thead>
          <tbody>{rows(job_list)}</tbody>
        </table>"""

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f9f9f9;font-family:Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 16px">
<table width="680" cellpadding="0" cellspacing="0"
       style="background:#fff;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)">
  <tr><td style="background:#003366;padding:28px 32px;border-radius:8px 8px 0 0">
    <p style="margin:0;color:#fff;font-size:22px;font-weight:700">UN P-5 &amp; D-1 Weekly Digest</p>
    <p style="margin:6px 0 0;color:#a8c4e0;font-size:13px">Week of {today} &nbsp;·&nbsp; {len(jobs)} positions found</p>
  </td></tr>
  <tr><td style="padding:24px 32px">
    {section("P-5", "#1a56db", p5)}
    {section("D-1", "#0e7c5b", d1)}
    <p style="margin:32px 0 0;font-size:12px;color:#aaa;border-top:1px solid #eee;padding-top:16px">
      Source: <a href="https://unjobs.org" style="color:#aaa">unjobs.org</a> &nbsp;·&nbsp;
      Verify deadlines on the official posting.
    </p>
  </td></tr>
</table></td></tr></table>
</body></html>"""


def build_plain_text(jobs: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    lines = [f"UN P-5 & D-1 Weekly Digest - {today}", f"{len(jobs)} positions found", ""]
    for grade in ("P-5", "D-1"):
        grade_jobs = [j for j in jobs if j["grade"] == grade]
        lines += [f"{'─'*60}", f"  {grade} ({len(grade_jobs)} found)", f"{'─'*60}"]
        if not grade_jobs:
            lines.append("  No postings found this week.\n")
        else:
            for j in grade_jobs:
                lines += [f"  {j['title']}", f"  {j['org']} | {j['location']}",
                          f"  {j['url']}", ""]
    return "\n".join(lines)


# ── Email sending (Yahoo SMTP) ────────────────────────────────────────────────

def send_email(jobs: list[dict]) -> None:
    today   = date.today().strftime("%B %d, %Y")
    subject = f"UN P-5 & D-1 Digest - {today} ({len(jobs)} positions)"

    msg            = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(build_plain_text(jobs), "plain"))
    msg.attach(MIMEText(build_html_email(jobs),  "html"))

    log.info("Connecting to Yahoo SMTP ...")
    with smtplib.SMTP("smtp.mail.yahoo.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    log.info("Email sent to %s", RECIPIENT_EMAIL)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    log.info("Starting UN jobs digest ...")
    jobs = fetch_all_jobs()
    if not jobs:
        log.warning("No jobs found - sending empty digest.")
    send_email(jobs)
    log.info("Done. %d positions sent.", len(jobs))


if __name__ == "__main__":
    main()
