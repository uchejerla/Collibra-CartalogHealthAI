"""
rules/rules_engine.py — Core governance rules engine.

6 rules that scan assets and lineage data to produce FindingResult objects.
Each rule is a pure function: takes data, returns list[FindingResult].
No side effects. Easily testable in isolation.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from app.config import get_settings

settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FindingResult:
    rule_id:    str
    issue_type: str
    severity:   str          # High | Medium | Low
    message:    str
    asset_id:   str | None = None
    asset_name: str | None = None
    agent:      str = "rules_engine"
    details:    dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Individual rules
# ─────────────────────────────────────────────────────────────────────────────

def rule_r1_missing_owner(asset: dict) -> FindingResult | None:
    """R1: If owner is missing → High Risk."""
    if not asset.get("owner") or str(asset.get("owner", "")).strip() == "":
        return FindingResult(
            rule_id="R1",
            issue_type="missing_owner",
            severity="High",
            message=f"Asset '{asset['name']}' has no assigned data owner.",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"domain": asset.get("domain"), "asset_type": asset.get("asset_type")},
        )
    return None


def rule_r2_missing_description(asset: dict) -> FindingResult | None:
    """R2: If description is blank → Medium."""
    if not asset.get("description") or str(asset.get("description", "")).strip() == "":
        return FindingResult(
            rule_id="R2",
            issue_type="missing_description",
            severity="Medium",
            message=f"Asset '{asset['name']}' has no business description.",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"domain": asset.get("domain")},
        )
    return None


def rule_r3_stale_asset(asset: dict) -> FindingResult | None:
    """R3: If last_modified > STALE_ASSET_DAYS → Stale (Medium)."""
    last_modified = asset.get("last_modified")
    if not last_modified:
        return None

    if isinstance(last_modified, str):
        try:
            last_modified = datetime.fromisoformat(last_modified)
        except ValueError:
            return None

    # Ensure timezone-aware
    if last_modified.tzinfo is None:
        last_modified = last_modified.replace(tzinfo=timezone.utc)

    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.stale_asset_days)
    if last_modified < cutoff:
        days_stale = (datetime.now(timezone.utc) - last_modified).days
        return FindingResult(
            rule_id="R3",
            issue_type="stale_asset",
            severity="Medium",
            message=f"Asset '{asset['name']}' has not been updated in {days_stale} days (threshold: {settings.stale_asset_days}).",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"last_modified": str(last_modified), "days_stale": days_stale},
        )
    return None


def rule_r4_critical_no_steward(asset: dict) -> FindingResult | None:
    """R4: If critical asset has no steward → High Risk."""
    is_critical = asset.get("critical_flag") or "CDE" in (asset.get("tags") or [])
    has_steward = asset.get("steward") and str(asset.get("steward", "")).strip() != ""
    if is_critical and not has_steward:
        return FindingResult(
            rule_id="R4",
            issue_type="critical_no_steward",
            severity="High",
            message=f"Critical asset '{asset['name']}' has no assigned data steward.",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"domain": asset.get("domain"), "critical_flag": True},
        )
    return None


def rule_r5_disconnected_lineage(
    asset: dict,
    asset_ids_in_lineage: set[str],
) -> FindingResult | None:
    """R5: If asset has no lineage connections → High Risk (for critical assets only)."""
    is_critical = asset.get("critical_flag") or "CDE" in (asset.get("tags") or [])
    if not is_critical:
        return None

    asset_id = str(asset.get("id", ""))
    if asset_id and asset_id not in asset_ids_in_lineage:
        return FindingResult(
            rule_id="R5",
            issue_type="disconnected_lineage",
            severity="High",
            message=f"Critical asset '{asset['name']}' has no lineage connections.",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"domain": asset.get("domain")},
        )
    return None


def rule_r6_duplicate_name(
    asset: dict,
    domain_name_counts: dict[str, int],
) -> FindingResult | None:
    """R6: Duplicate names within the same domain → Medium."""
    key = f"{asset.get('domain', '__no_domain__')}::{asset.get('name', '')}".lower()
    if domain_name_counts.get(key, 0) > 1:
        return FindingResult(
            rule_id="R6",
            issue_type="duplicate_name",
            severity="Medium",
            message=f"Asset name '{asset['name']}' appears {domain_name_counts[key]} times in domain '{asset.get('domain')}'.",
            asset_id=asset.get("id"),
            asset_name=asset.get("name"),
            details={"domain": asset.get("domain"), "count": domain_name_counts[key]},
        )
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main engine
# ─────────────────────────────────────────────────────────────────────────────

class RulesEngine:
    """
    Runs all 6 governance rules against a dataset.
    Returns a list of FindingResult objects.
    """

    def run(
        self,
        assets: list[dict],
        lineage_pairs: list[dict] | None = None,
    ) -> list[FindingResult]:
        lineage_pairs = lineage_pairs or []
        findings: list[FindingResult] = []

        # Pre-compute indexes for O(1) lookups
        asset_ids_in_lineage: set[str] = set()
        for lp in lineage_pairs:
            if lp.get("source_asset_id"):
                asset_ids_in_lineage.add(str(lp["source_asset_id"]))
            if lp.get("target_asset_id"):
                asset_ids_in_lineage.add(str(lp["target_asset_id"]))

        domain_name_counts: dict[str, int] = {}
        for a in assets:
            key = f"{a.get('domain', '__no_domain__')}::{a.get('name', '')}".lower()
            domain_name_counts[key] = domain_name_counts.get(key, 0) + 1

        # Run all rules
        for asset in assets:
            for rule_fn, extra_args in [
                (rule_r1_missing_owner, {}),
                (rule_r2_missing_description, {}),
                (rule_r3_stale_asset, {}),
                (rule_r4_critical_no_steward, {}),
                (rule_r5_disconnected_lineage, {"asset_ids_in_lineage": asset_ids_in_lineage}),
                (rule_r6_duplicate_name, {"domain_name_counts": domain_name_counts}),
            ]:
                result = rule_fn(asset, **extra_args) if extra_args else rule_fn(asset)
                if result:
                    findings.append(result)

        return findings

    @staticmethod
    def compute_health_score(findings: list[FindingResult]) -> float:
        """Score = 100 - (5×High + 3×Medium + 1×Low). Min = 0."""
        s = get_settings()
        high   = sum(1 for f in findings if f.severity == "High")
        medium = sum(1 for f in findings if f.severity == "Medium")
        low    = sum(1 for f in findings if f.severity == "Low")
        score  = 100 - (s.score_weight_high * high +
                        s.score_weight_medium * medium +
                        s.score_weight_low * low)
        return max(0.0, float(score))
