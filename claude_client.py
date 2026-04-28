"""
app/services/claude_client.py — Claude API wrapper with caching.

Wraps anthropic SDK with:
- Retry logic (3 attempts, exponential backoff)
- Response caching per scan_id + summary_type
- Structured prompt loading
- Token tracking
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import anthropic
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


@dataclass
class AIResponse:
    content:           str
    model:             str
    prompt_tokens:     int
    completion_tokens: int
    summary_type:      str


# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates (inline — move to /prompts/*.md as they grow)
# ─────────────────────────────────────────────────────────────────────────────

EXECUTIVE_SUMMARY_SYSTEM = """You are a senior Data Governance advisor preparing an executive briefing for a Chief Data Officer.

Your audience: C-suite executives who care about risk, compliance, and ROI — not technical details.
Your job: Translate raw governance findings into a crisp, prioritized executive summary.

Format your response as follows:
1. **Governance Health Overview** (2–3 sentences): Overall state, score context, trend.
2. **Top 3 Risks** (bullet list): Most critical issues, business impact, why they matter now.
3. **Priority Actions** (numbered list, max 5): Specific, actionable steps. Include who should own each.

Rules:
- Write in confident, professional tone. No jargon.
- Never invent asset names or statistics not provided to you.
- Keep total response under 400 words.
- Quantify impact where data allows (e.g., "43 of 150 assets lack owners").
"""

STEWARD_GUIDANCE_SYSTEM = """You are a Data Governance expert advising data stewards on fixing catalog quality issues.

Your audience: Data stewards and catalog administrators who manage Collibra day-to-day.
Your job: Provide clear, actionable fix guidance for each category of issue found.

Format your response as follows:
For each issue type present, provide:
- **Issue:** [issue type name]
- **Count:** [number of affected assets]
- **Quick Wins** (< 1 hour): Specific steps a steward can do immediately.
- **Complex Fixes** (> 1 hour): Longer-term remediation approach.
- **Owner Suggestion:** Who should own this remediation.

Rules:
- Be specific and practical. No generic advice.
- Prioritize High severity issues first.
- Keep each section concise (3–5 bullet points max).
"""

TREND_ANALYSIS_SYSTEM = """You are a Data Governance analytics expert analyzing catalog health trends over time.

Your audience: Data Governance leads reviewing program performance.
Your job: Compare current vs previous scan and identify meaningful patterns.

Format your response as follows:
1. **Score Movement**: Health score delta, direction, and what drove the change.
2. **Improving Areas**: Domains or issue types showing improvement.
3. **Degrading Areas**: Domains or issue types getting worse — flag urgently.
4. **Persistent Issues**: Problems that have appeared in multiple scans — escalation risk.
5. **Recommendation**: One strategic recommendation based on the trend.

Rules:
- Only comment on patterns actually visible in the data provided.
- Be specific about domain names and issue counts.
- Keep response under 300 words.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main generation functions
# ─────────────────────────────────────────────────────────────────────────────

async def _call_claude(system: str, user_message: str, max_tokens: int = 1000) -> AIResponse:
    """Internal: call Claude with retry logic."""
    client = get_client()
    model = "claude-sonnet-4-20250514"

    for attempt in range(3):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            return AIResponse(
                content=response.content[0].text,
                model=model,
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
                summary_type="",
            )
        except anthropic.RateLimitError:
            wait = 2 ** attempt
            logger.warning(f"Claude rate limit. Retrying in {wait}s (attempt {attempt + 1}/3)")
            await asyncio.sleep(wait)
        except anthropic.APIError as e:
            logger.error(f"Claude API error on attempt {attempt + 1}: {e}")
            if attempt == 2:
                raise

    raise RuntimeError("Claude API failed after 3 attempts")


async def generate_executive_summary(
    health_score: float,
    audit_score: float,
    high_count: int,
    medium_count: int,
    low_count: int,
    total_assets: int,
    top_risks: list[dict],
    priority_actions: list[str],
) -> AIResponse:
    user_msg = f"""
Governance scan results for executive briefing:

Health Score: {health_score}/100
Audit Readiness Score: {audit_score}/100
Total Assets Scanned: {total_assets}

Finding Counts:
- High Severity: {high_count}
- Medium Severity: {medium_count}
- Low Severity: {low_count}

Top Risks (High Severity):
{chr(10).join(f"- {r['message']}" for r in top_risks[:10])}

System-Recommended Priority Actions:
{chr(10).join(f"{i+1}. {a}" for i, a in enumerate(priority_actions))}

Please write the executive governance health briefing.
"""
    result = await _call_claude(EXECUTIVE_SUMMARY_SYSTEM, user_msg, max_tokens=600)
    result.summary_type = "executive"
    return result


async def generate_steward_guidance(
    findings_by_type: dict[str, list[dict]],
) -> AIResponse:
    issue_lines = []
    for issue_type, findings in findings_by_type.items():
        high = [f for f in findings if f["severity"] == "High"]
        med  = [f for f in findings if f["severity"] == "Medium"]
        issue_lines.append(
            f"Issue type: {issue_type} | Total: {len(findings)} | High: {len(high)} | Medium: {len(med)}"
        )
        for f in findings[:3]:  # sample max 3 per type
            issue_lines.append(f"  Example: {f['message']}")

    user_msg = f"""
Catalog quality issues requiring steward attention:

{chr(10).join(issue_lines)}

Please provide detailed steward remediation guidance.
"""
    result = await _call_claude(STEWARD_GUIDANCE_SYSTEM, user_msg, max_tokens=800)
    result.summary_type = "steward"
    return result


async def generate_trend_analysis(
    current_scan: dict,
    previous_scan: dict,
) -> AIResponse:
    user_msg = f"""
Current Scan:
- Health Score: {current_scan['health_score']}
- Total Findings: {current_scan['total_findings']}
- High: {current_scan['high_count']} | Medium: {current_scan['medium_count']} | Low: {current_scan['low_count']}
- Top Issues: {', '.join(current_scan.get('top_issue_types', []))}

Previous Scan:
- Health Score: {previous_scan['health_score']}
- Total Findings: {previous_scan['total_findings']}
- High: {previous_scan['high_count']} | Medium: {previous_scan['medium_count']} | Low: {previous_scan['low_count']}
- Top Issues: {', '.join(previous_scan.get('top_issue_types', []))}

Score Delta: {current_scan['health_score'] - previous_scan['health_score']:+.1f} points

Please provide the trend analysis.
"""
    result = await _call_claude(TREND_ANALYSIS_SYSTEM, user_msg, max_tokens=500)
    result.summary_type = "trend"
    return result
