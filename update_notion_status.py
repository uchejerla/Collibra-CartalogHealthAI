"""
scripts/update_notion_status.py
────────────────────────────────
Auto-pilot Notion status sync.  Reads TASK_STATUS_MAP below and bulk-updates
all 35 task pages in the Catalog Health AI task database via the Notion API.

Usage:
  python scripts/update_notion_status.py             # dry-run (prints plan)
  python scripts/update_notion_status.py --apply     # actually updates Notion

Setup:
  1. Go to https://www.notion.so/my-integrations
  2. Create a new integration  → copy the "Internal Integration Secret"
  3. Open the Task Tracker database in Notion
  4. Click ··· → Connections → add your integration
  5. Set NOTION_TOKEN in your .env  (or export it in your shell)

This script is called automatically by the CI pipeline after each completed
build phase.  It can also be run manually at any time.
"""

from __future__ import annotations
import argparse
import os
import sys
import time
import httpx # type: ignore
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN   = os.getenv("NOTION_TOKEN", "")
NOTION_VERSION = "2022-06-28"

# ─────────────────────────────────────────────────────────────────────────────
# TASK → PAGE ID MAP
# Update these page IDs if tasks are ever re-created.
# Page IDs are pulled from the Notion workspace index.
# ─────────────────────────────────────────────────────────────────────────────
TASK_STATUS_MAP: list[dict] = [
    # ── Week 1 — Backend (all DONE) ──────────────────────────────────────────
    {"id": "34d8afb1a56f81d8941ee1547c165ef0", "task": "W1-T1  Set up GitHub repo + project scaffold",               "status": "Done"},
    {"id": "34d8afb1a56f81568d12ce332170dc60", "task": "W1-T2  Provision Supabase + DB schema",                       "status": "Done"},
    {"id": "34d8afb1a56f812ebb03e123c3860cad", "task": "W1-T3  FastAPI skeleton + folder structure",                  "status": "Done"},
    {"id": "34d8afb1a56f81318fcdcfb258335fba", "task": "W1-T4  POST /upload-assets",                                  "status": "Done"},
    {"id": "34d8afb1a56f814496bcd17d8a11111c", "task": "W1-T5  POST /upload-lineage",                                 "status": "Done"},
    {"id": "34d8afb1a56f81989480f170d314641a", "task": "W1-T6  Collibra CSV export parser",                           "status": "Done"},
    {"id": "34d8afb1a56f814fbc02f0b9b0905f0e", "task": "W1-T7  GET /health-score",                                    "status": "Done"},
    {"id": "34d8afb1a56f811d84b3fd5b9a79bfac", "task": "W1-T8  GET /issues",                                          "status": "Done"},
    {"id": "34d8afb1a56f81f8ae21ffff3dbe9ef2", "task": "W1-T9  GET /summary stub",                                    "status": "Done"},
    {"id": "34d8afb1a56f81ada14de3d704224c6f", "task": "W1-T10 Seed DB with synthetic test data",                     "status": "Done"},

    # ── Week 2 — Agents (all DONE) ───────────────────────────────────────────
    {"id": "34d8afb1a56f81128e02f1e5709d6c23", "task": "W2-T1  Rules engine core + severity scoring",                "status": "Done"},
    {"id": "34d8afb1a56f810d8c97c738acc2d098", "task": "W2-T2  Metadata Curator Agent",                              "status": "Done"},
    {"id": "34d8afb1a56f81c4b750dd8e31cfb73c", "task": "W2-T3  Lineage Guardian Agent (NetworkX)",                   "status": "Done"},
    {"id": "34d8afb1a56f81c09770f747bb43021f", "task": "W2-T4  Governance Gap Agent",                                "status": "Done"},
    {"id": "34d8afb1a56f819697f0c6c6020920ec", "task": "W2-T5  Agent orchestration layer",                           "status": "Done"},
    {"id": "34d8afb1a56f8194892efcbba3d091c5", "task": "W2-T6  Executive Risk Agent",                                "status": "Done"},
    {"id": "34d8afb1a56f819595d1f8e558714c5e", "task": "W2-T7  Unit tests for all 6 rules",                          "status": "Done"},
    {"id": "34d8afb1a56f8118ab38f269e9389103", "task": "W2-T8  Integration test: full agent pipeline",               "status": "Done"},

    # ── Week 3 — AI Layer (all DONE) ─────────────────────────────────────────
    {"id": "34d8afb1a56f81d89b64e8e5d3a7b130", "task": "W3-T1  Claude API — SDK setup + auth",                       "status": "Done"},
    {"id": "34d8afb1a56f814da97ee6750e9d67f6", "task": "W3-T2  Executive summary prompt + parser",                   "status": "Done"},
    {"id": "34d8afb1a56f81dc952fd35208435e0d", "task": "W3-T3  Steward guidance prompt",                             "status": "Done"},
    {"id": "34d8afb1a56f81459e8ded5f999e9e23", "task": "W3-T4  Trend analysis prompt",                               "status": "Done"},
    {"id": "34d8afb1a56f8140a31ddd65a398e881", "task": "W3-T5  Wire AI outputs into /summary",                       "status": "Done"},
    {"id": "34d8afb1a56f8180b9f9ee88590471e5", "task": "W3-T6  Email report + GitHub Actions scheduler",             "status": "Done"},
    {"id": "34d8afb1a56f81d0a6d6d796449575ef", "task": "W3-T7  QA AI outputs against synthetic data",               "status": "Done"},

    # ── Week 4 — Dashboard (updated as each task completes) ──────────────────
    {"id": "34d8afb1a56f810089c5fadf40712ef9", "task": "W4-T1  Next.js + Tailwind + Vercel setup",                   "status": "Done"},
    {"id": "34d8afb1a56f81c6ac98f4cb85fc030f", "task": "W4-T2  Pick startup name + buy domain",                     "status": "In Progress"},
    {"id": "34d8afb1a56f8133a460d63bf1b8ea8e", "task": "W4-T3  Overview page (health score + sparklines)",           "status": "Done"},
    {"id": "34d8afb1a56f81d79359d681829b4864", "task": "W4-T4  Issues page (filterable findings table)",             "status": "Done"},
    {"id": "34d8afb1a56f8121a9ffca1358fe0e55", "task": "W4-T5  Lineage Health page (graph viz)",                     "status": "Done"},
    {"id": "34d8afb1a56f81668176e32ca18eb21d", "task": "W4-T6  Recommendations page (AI priority actions)",          "status": "Done"},
    {"id": "34d8afb1a56f818e939ff8c343991209", "task": "W4-T7  Landing page with upload CTA + pricing",              "status": "Done"},
    {"id": "34d8afb1a56f81bc8412f8afdec35a30", "task": "W4-T8  Demo dataset (synthetic Collibra export)",            "status": "Done"},
    {"id": "34d8afb1a56f81d5bf4ffbf700a7eb34", "task": "W4-T9  Deploy to Vercel staging + smoke test",              "status": "In Progress"},
    {"id": "34d8afb1a56f814bb6acf4321b5753ab", "task": "W4-T10 End-to-end QA + bug fix pass + v1.0 tag",            "status": "Not Started"},
]


# ─────────────────────────────────────────────────────────────────────────────
# Notion API helpers
# ─────────────────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Authorization":  f"Bearer {NOTION_TOKEN}",
        "Content-Type":   "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def update_page_status(client: httpx.Client, page_id: str, status: str) -> bool:
    """PATCH a single Notion page's Status property."""
    url  = f"https://api.notion.com/v1/pages/{page_id}"
    body = {"properties": {"Status": {"select": {"name": status}}}}
    resp = client.patch(url, json=body, headers=_headers(), timeout=15)
    if resp.status_code == 200:
        return True
    print(f"  ✗ FAILED {page_id[:8]}… HTTP {resp.status_code}: {resp.text[:120]}")
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Sync Notion task statuses")
    parser.add_argument("--apply", action="store_true", help="Actually update Notion (default: dry-run)")
    parser.add_argument("--filter-status", help="Only update tasks with this target status (e.g. Done)")
    args = parser.parse_args()

    if not NOTION_TOKEN and args.apply:
        print("✗ NOTION_TOKEN not set. Add it to .env or export NOTION_TOKEN=secret_...")
        sys.exit(1)

    tasks = TASK_STATUS_MAP
    if args.filter_status:
        tasks = [t for t in tasks if t["status"] == args.filter_status]

    print(f"{'[DRY RUN] ' if not args.apply else ''}Syncing {len(tasks)} tasks to Notion\n")

    done = in_progress = not_started = failed = 0

    with httpx.Client() as client:
        for task in tasks:
            icon = {"Done": "✅", "In Progress": "🔨", "Not Started": "⬜", "Blocked": "🚫"}.get(task["status"], "·")
            print(f"  {icon} {task['task'][:55]:<55} → {task['status']}")

            if args.apply:
                ok = update_page_status(client, task["id"], task["status"])
                if not ok:
                    failed += 1
                time.sleep(0.35)   # Notion API rate limit: ~3 req/sec

            if task["status"] == "Done":           done += 1
            elif task["status"] == "In Progress":  in_progress += 1
            else:                                  not_started += 1

    print(f"\n{'─'*60}")
    print(f"  ✅ Done:        {done}")
    print(f"  🔨 In Progress: {in_progress}")
    print(f"  ⬜ Not Started: {not_started}")
    if failed:
        print(f"  ✗  Failed:     {failed}")
    if not args.apply:
        print("\n  Run with --apply to push these changes to Notion.")


if __name__ == "__main__":
    main()
