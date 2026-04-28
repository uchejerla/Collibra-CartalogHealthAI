"""
tests/test_rules.py — Unit tests for the rules engine.

Covers all 6 rules with both passing and failing fixtures.
Edge cases: boundary dates, cross-domain duplicates, tag-based detection.
Run: pytest tests/test_rules.py -v --cov=rules
"""
import pytest
from datetime import datetime, timedelta, timezone
from rules.rules_engine import (
    RulesEngine,
    FindingResult,
    rule_r1_missing_owner,
    rule_r2_missing_description,
    rule_r3_stale_asset,
    rule_r4_critical_no_steward,
    rule_r5_disconnected_lineage,
    rule_r6_duplicate_name,
)

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _asset(**overrides) -> dict:
    """Base healthy asset — no rules should fire on this."""
    base = {
        "id":            "asset-001",
        "name":          "CUSTOMER_MASTER",
        "asset_type":    "Table",
        "domain":        "Customer",
        "owner":         "Sarah Chen",
        "steward":       "Mike Ross",
        "description":   "Master customer reference table.",
        "critical_flag": False,
        "pii_flag":      False,
        "last_modified": datetime.now(timezone.utc) - timedelta(days=10),
        "tags":          [],
    }
    base.update(overrides)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# R1: Missing owner
# ─────────────────────────────────────────────────────────────────────────────

def test_r1_fires_when_owner_missing():
    asset = _asset(owner=None)
    result = rule_r1_missing_owner(asset)
    assert result is not None
    assert result.severity == "High"
    assert result.issue_type == "missing_owner"
    assert result.rule_id == "R1"


def test_r1_fires_when_owner_empty_string():
    assert rule_r1_missing_owner(_asset(owner="")) is not None
    assert rule_r1_missing_owner(_asset(owner="   ")) is not None


def test_r1_does_not_fire_when_owner_present():
    assert rule_r1_missing_owner(_asset(owner="Alice")) is None


# ─────────────────────────────────────────────────────────────────────────────
# R2: Missing description
# ─────────────────────────────────────────────────────────────────────────────

def test_r2_fires_when_description_missing():
    result = rule_r2_missing_description(_asset(description=None))
    assert result is not None
    assert result.severity == "Medium"
    assert result.issue_type == "missing_description"


def test_r2_fires_when_description_whitespace():
    assert rule_r2_missing_description(_asset(description="   ")) is not None


def test_r2_does_not_fire_when_description_present():
    assert rule_r2_missing_description(_asset(description="A valid description.")) is None


# ─────────────────────────────────────────────────────────────────────────────
# R3: Stale asset (>180 days)
# ─────────────────────────────────────────────────────────────────────────────

def test_r3_fires_when_asset_is_stale():
    stale_date = datetime.now(timezone.utc) - timedelta(days=181)
    result = rule_r3_stale_asset(_asset(last_modified=stale_date))
    assert result is not None
    assert result.severity == "Medium"
    assert result.issue_type == "stale_asset"
    assert result.details["days_stale"] >= 181


def test_r3_does_not_fire_at_boundary_179_days():
    """179 days — just below threshold, should NOT fire."""
    fresh_date = datetime.now(timezone.utc) - timedelta(days=179)
    assert rule_r3_stale_asset(_asset(last_modified=fresh_date)) is None


def test_r3_fires_exactly_at_181_days():
    """181 days — just above threshold, SHOULD fire."""
    stale = datetime.now(timezone.utc) - timedelta(days=181)
    assert rule_r3_stale_asset(_asset(last_modified=stale)) is not None


def test_r3_handles_none_last_modified():
    """None last_modified → no finding (can't determine staleness)."""
    assert rule_r3_stale_asset(_asset(last_modified=None)) is None


def test_r3_handles_string_iso_date():
    stale_str = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    result = rule_r3_stale_asset(_asset(last_modified=stale_str))
    assert result is not None


# ─────────────────────────────────────────────────────────────────────────────
# R4: Critical asset with no steward
# ─────────────────────────────────────────────────────────────────────────────

def test_r4_fires_for_critical_asset_without_steward():
    asset = _asset(critical_flag=True, steward=None)
    result = rule_r4_critical_no_steward(asset)
    assert result is not None
    assert result.severity == "High"
    assert result.issue_type == "critical_no_steward"


def test_r4_fires_for_cde_tag_without_steward():
    asset = _asset(tags=["CDE"], steward="")
    result = rule_r4_critical_no_steward(asset)
    assert result is not None


def test_r4_does_not_fire_for_non_critical_asset():
    asset = _asset(critical_flag=False, steward=None, tags=[])
    assert rule_r4_critical_no_steward(asset) is None


def test_r4_does_not_fire_when_steward_present():
    asset = _asset(critical_flag=True, steward="Jane Doe")
    assert rule_r4_critical_no_steward(asset) is None


# ─────────────────────────────────────────────────────────────────────────────
# R5: Disconnected lineage (critical assets only)
# ─────────────────────────────────────────────────────────────────────────────

def test_r5_fires_for_critical_asset_not_in_lineage():
    asset = _asset(id="a1", critical_flag=True)
    result = rule_r5_disconnected_lineage(asset, asset_ids_in_lineage=set())
    assert result is not None
    assert result.severity == "High"
    assert result.issue_type == "disconnected_lineage"


def test_r5_does_not_fire_when_asset_has_lineage():
    asset = _asset(id="a1", critical_flag=True)
    assert rule_r5_disconnected_lineage(asset, asset_ids_in_lineage={"a1"}) is None


def test_r5_does_not_fire_for_non_critical_asset():
    asset = _asset(id="a1", critical_flag=False)
    assert rule_r5_disconnected_lineage(asset, asset_ids_in_lineage=set()) is None


# ─────────────────────────────────────────────────────────────────────────────
# R6: Duplicate names in same domain
# ─────────────────────────────────────────────────────────────────────────────

def test_r6_fires_for_duplicate_in_same_domain():
    asset = _asset(name="CUSTOMER_MASTER", domain="Finance")
    counts = {"finance::customer_master": 2}
    result = rule_r6_duplicate_name(asset, domain_name_counts=counts)
    assert result is not None
    assert result.severity == "Medium"
    assert result.issue_type == "duplicate_name"


def test_r6_does_not_fire_for_same_name_in_different_domain():
    """Same name but different domain → NOT a duplicate."""
    asset = _asset(name="CUSTOMER_MASTER", domain="Customer")
    # The duplicate is in Finance domain, this asset is in Customer → no match
    counts = {"finance::customer_master": 2, "customer::customer_master": 1}
    assert rule_r6_duplicate_name(asset, domain_name_counts=counts) is None


def test_r6_does_not_fire_for_unique_name():
    asset = _asset(name="UNIQUE_TABLE", domain="Finance")
    counts = {"finance::unique_table": 1}
    assert rule_r6_duplicate_name(asset, domain_name_counts=counts) is None


# ─────────────────────────────────────────────────────────────────────────────
# RulesEngine integration
# ─────────────────────────────────────────────────────────────────────────────

def test_engine_detects_all_issues_in_problematic_dataset():
    """A dataset with all 6 problems should produce findings for each."""
    stale = datetime.now(timezone.utc) - timedelta(days=200)
    assets = [
        _asset(id="a1", name="TABLE_A", domain="Finance", owner=None),         # R1
        _asset(id="a2", name="TABLE_B", domain="Finance", description=None),    # R2
        _asset(id="a3", name="TABLE_C", domain="Finance", last_modified=stale), # R3
        _asset(id="a4", name="TABLE_D", domain="Finance", critical_flag=True, steward=None),  # R4
        _asset(id="a5", name="TABLE_D", domain="Finance"),                       # R6 (dup with a4)
    ]
    engine = RulesEngine()
    findings = engine.run(assets, lineage_pairs=[])
    issue_types = {f.issue_type for f in findings}
    assert "missing_owner" in issue_types
    assert "missing_description" in issue_types
    assert "stale_asset" in issue_types
    assert "critical_no_steward" in issue_types
    assert "duplicate_name" in issue_types


def test_engine_produces_no_findings_for_clean_dataset():
    """A perfectly healthy asset should produce zero findings."""
    asset = _asset(
        id="a1",
        critical_flag=True,
        steward="Jane",
        owner="John",
        description="Full description.",
        last_modified=datetime.now(timezone.utc) - timedelta(days=10),
        tags=["CDE"],
    )
    engine = RulesEngine()
    lineage = [{"source_asset_id": "a1", "target_asset_id": "other"}]
    findings = engine.run([asset], lineage_pairs=lineage)
    assert len(findings) == 0, f"Unexpected findings: {findings}"


def test_health_score_formula():
    findings = [
        FindingResult("R1", "missing_owner", "High", "msg"),   # 5 pts
        FindingResult("R1", "missing_owner", "High", "msg"),   # 5 pts
        FindingResult("R2", "missing_desc", "Medium", "msg"),  # 3 pts
        FindingResult("R3", "stale_asset", "Low", "msg"),      # 1 pt
    ]
    score = RulesEngine.compute_health_score(findings)
    # 100 - (5*2 + 3*1 + 1*1) = 100 - 14 = 86
    assert score == 86.0


def test_health_score_clamps_at_zero():
    """Score should never go below 0."""
    findings = [FindingResult("R1", "missing_owner", "High", "msg")] * 25
    score = RulesEngine.compute_health_score(findings)
    assert score == 0.0
