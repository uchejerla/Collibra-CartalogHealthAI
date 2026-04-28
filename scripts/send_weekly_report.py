"""
scripts/send_weekly_report.py — Weekly email report via Resend.
Called by GitHub Actions cron: 0 8 * * 1 (Monday 8 AM UTC).
"""
from __future__ import annotations
import asyncio, os, sys
import httpx, resend
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

# Load .env — check backend/.env first, then project root
_script_dir = Path(__file__).resolve().parent
for _candidate in [
    _script_dir.parent / "backend" / ".env",
    _script_dir.parent / ".env",
    _script_dir / ".env",
]:
    if _candidate.exists():
        load_dotenv(_candidate)
        break

API_BASE       = os.getenv("API_BASE_URL", "http://localhost:8000")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
EMAIL_FROM     = os.getenv("EMAIL_FROM", "reports@cataloghealth.ai")
EMAIL_TO       = os.getenv("EMAIL_TO", "")
DASHBOARD_URL  = os.getenv("DASHBOARD_URL", "https://app.cataloghealth.ai")
resend.api_key = RESEND_API_KEY

def _badge(count, level):
    c = {"High":"#E24B4A","Medium":"#BA7517","Low":"#639922"}.get(level,"#888")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:12px;font-size:12px;font-weight:600">{count} {level}</span>'

def _score_color(s):
    return "#1D9E75" if s >= 80 else "#BA7517" if s >= 60 else "#E24B4A"

def build_html(health, summary_text, now):
    score, audit = health.get("health_score",0), health.get("audit_score",0) or 0
    high, medium, low = health.get("high_count",0), health.get("medium_count",0), health.get("low_count",0)
    total, assets = health.get("total_findings",0), health.get("total_assets",0)
    paras = "".join(f"<p style='margin:0 0 12px;line-height:1.6;color:#3d3d3a'>{p.strip()}</p>"
                    for p in summary_text.split("\n\n") if p.strip())
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#f5f5f0;font-family:sans-serif">
<div style="max-width:600px;margin:32px auto;background:#fff;border-radius:12px;overflow:hidden">
  <div style="background:#3C3489;padding:28px 32px">
    <div style="color:#CECBF6;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.08em">Catalog Health AI</div>
    <div style="color:#fff;font-size:22px;font-weight:600;margin-top:4px">Weekly Governance Report</div>
    <div style="color:#AFA9EC;font-size:13px">{now.strftime("%B %d, %Y")}</div>
  </div>
  <div style="display:flex;padding:24px 32px;gap:12px;border-bottom:1px solid #eee">
    <div style="flex:1;text-align:center;background:#f9f9f6;border-radius:8px;padding:16px">
      <div style="font-size:36px;font-weight:700;color:{_score_color(score)}">{score:.0f}</div>
      <div style="font-size:11px;color:#888">Health Score</div>
    </div>
    <div style="flex:1;text-align:center;background:#f9f9f6;border-radius:8px;padding:16px">
      <div style="font-size:36px;font-weight:700;color:{_score_color(audit)}">{audit:.0f}</div>
      <div style="font-size:11px;color:#888">Audit Readiness</div>
    </div>
    <div style="flex:1;text-align:center;background:#f9f9f6;border-radius:8px;padding:16px">
      <div style="font-size:36px;font-weight:700;color:#3d3d3a">{assets}</div>
      <div style="font-size:11px;color:#888">Assets Scanned</div>
    </div>
  </div>
  <div style="padding:20px 32px;border-bottom:1px solid #eee">
    <div style="font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:10px">Findings</div>
    {_badge(high,"High")} {_badge(medium,"Medium")} {_badge(low,"Low")}
    <span style="color:#888;font-size:13px"> {total} total</span>
  </div>
  <div style="padding:24px 32px;border-bottom:1px solid #eee">
    <div style="font-size:11px;font-weight:600;color:#888;text-transform:uppercase;letter-spacing:.06em;margin-bottom:14px">Executive Summary</div>
    {paras}
  </div>
  <div style="padding:24px 32px;text-align:center">
    <a href="{DASHBOARD_URL}" style="background:#3C3489;color:#fff;text-decoration:none;padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;display:inline-block">View Full Dashboard →</a>
  </div>
</div></body></html>"""

async def run():
    now = datetime.now(timezone.utc)
    print(f"Generating weekly report for {now.strftime('%Y-%m-%d')}...")
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        health = (await client.get("/health-score")).json()
        summary_data = (await client.get("/summary")).json()
    executive_text = summary_data.get("executive") or "No summary available."
    if not EMAIL_TO:
        print("EMAIL_TO not set — skipping send.\n" + executive_text[:400])
        return
    html = build_html(health, executive_text, now)
    score = health.get("health_score", 0)
    result = resend.Emails.send(resend.Emails.SendParams(
        from_=EMAIL_FROM, to=[EMAIL_TO],
        subject=f"📊 Governance Report — Score: {score:.0f}/100 | {now.strftime('%b %d')}",
        html=html,
    ))
    print(f"✅ Email sent: {result.get('id')}")

if __name__ == "__main__":
    asyncio.run(run())
