"""
agents/ — All four Catalog Health AI agents + orchestrator.

Execution order:
  1. MetadataCuratorAgent  ──┐
                             ├── parallel (asyncio.gather)
  2. LineageGuardianAgent  ──┘
  3. GovernanceGapAgent       ← waits for both above
  4. ExecutiveRiskAgent       ← waits for all three
"""
from __future__ import annotations
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any
import networkx as nx
from rules.rules_engine import FindingResult, RulesEngine

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Shared result container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    agent_name:  str
    findings:    list[FindingResult] = field(default_factory=list)
    metadata:    dict[str, Any]      = field(default_factory=dict)
    error:       str | None          = None


# ─────────────────────────────────────────────────────────────────────────────
# 1. Metadata Curator Agent
# ─────────────────────────────────────────────────────────────────────────────

class MetadataCuratorAgent:
    """
    Scans all assets for quality and completeness issues.
    Runs in PARALLEL with LineageGuardianAgent.
    """
    NAME = "metadata_curator"

    def __init__(self):
        self.engine = RulesEngine()

    async def run(self, assets: list[dict], lineage_pairs: list[dict]) -> AgentResult:
        logger.info(f"[MetadataCurator] Starting scan on {len(assets)} assets")
        try:
            findings = self.engine.run(assets, lineage_pairs)
            # Keep only metadata-relevant finding types
            metadata_types = {
                "missing_owner", "missing_description",
                "stale_asset", "duplicate_name",
            }
            my_findings = [f for f in findings if f.issue_type in metadata_types]
            for f in my_findings:
                f.agent = self.NAME

            logger.info(f"[MetadataCurator] Found {len(my_findings)} issues")
            return AgentResult(
                agent_name=self.NAME,
                findings=my_findings,
                metadata={
                    "assets_scanned": len(assets),
                    "missing_owners": sum(1 for f in my_findings if f.issue_type == "missing_owner"),
                    "missing_descriptions": sum(1 for f in my_findings if f.issue_type == "missing_description"),
                    "stale_assets": sum(1 for f in my_findings if f.issue_type == "stale_asset"),
                    "duplicates": sum(1 for f in my_findings if f.issue_type == "duplicate_name"),
                },
            )
        except Exception as e:
            logger.error(f"[MetadataCurator] Error: {e}")
            return AgentResult(agent_name=self.NAME, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lineage Guardian Agent
# ─────────────────────────────────────────────────────────────────────────────

class LineageGuardianAgent:
    """
    Traverses the lineage graph using NetworkX.
    Detects broken paths, orphan nodes, disconnected clusters, low-confidence edges.
    Runs in PARALLEL with MetadataCuratorAgent.
    """
    NAME = "lineage_guardian"

    async def run(self, assets: list[dict], lineage_pairs: list[dict]) -> AgentResult:
        logger.info(f"[LineageGuardian] Building graph with {len(lineage_pairs)} edges")
        findings: list[FindingResult] = []
        try:
            G = nx.DiGraph()

            # Add all asset nodes
            asset_lookup = {str(a["id"]): a for a in assets if "id" in a}
            for asset_id, asset in asset_lookup.items():
                G.add_node(asset_id, **{"name": asset.get("name", ""), "critical": asset.get("critical_flag", False)})

            # Add lineage edges
            for lp in lineage_pairs:
                src = str(lp.get("source_asset_id", ""))
                tgt = str(lp.get("target_asset_id", ""))
                conf = float(lp.get("confidence_score", 1.0))
                if src and tgt:
                    G.add_edge(src, tgt, confidence=conf)

            # Rule: Orphan nodes (no edges at all)
            for node in G.nodes():
                if G.degree(node) == 0:
                    asset = asset_lookup.get(node, {})
                    findings.append(FindingResult(
                        rule_id="LG1",
                        issue_type="orphan_node",
                        severity="Medium",
                        message=f"Asset '{asset.get('name', node)}' has no upstream or downstream lineage.",
                        asset_id=node,
                        asset_name=asset.get("name"),
                        agent=self.NAME,
                    ))

            # Rule: Low-confidence edges
            for src, tgt, data in G.edges(data=True):
                if data.get("confidence", 1.0) < 0.5:
                    src_name = asset_lookup.get(src, {}).get("name", src)
                    tgt_name = asset_lookup.get(tgt, {}).get("name", tgt)
                    findings.append(FindingResult(
                        rule_id="LG2",
                        issue_type="low_confidence_lineage",
                        severity="Low",
                        message=f"Lineage from '{src_name}' → '{tgt_name}' has low confidence ({data['confidence']:.2f}).",
                        agent=self.NAME,
                        details={"source": src_name, "target": tgt_name, "confidence": data["confidence"]},
                    ))

            # Rule: Disconnected components (weakly connected)
            undirected = G.to_undirected()
            components = list(nx.connected_components(undirected))
            if len(components) > 1:
                for i, component in enumerate(components):
                    if len(component) == 1:
                        continue  # already caught as orphan above
                    asset_names = [asset_lookup.get(n, {}).get("name", n) for n in list(component)[:3]]
                    findings.append(FindingResult(
                        rule_id="LG3",
                        issue_type="disconnected_cluster",
                        severity="Medium",
                        message=f"Isolated lineage cluster detected ({len(component)} assets: {', '.join(asset_names)}...).",
                        agent=self.NAME,
                        details={"cluster_size": len(component), "sample_assets": asset_names},
                    ))

            # Rule: Critical assets with disconnected lineage (R5)
            critical_assets_in_lineage = {
                n for n in G.nodes()
                if asset_lookup.get(n, {}).get("critical_flag")
            }
            for node in list(G.nodes()):
                asset = asset_lookup.get(node, {})
                if asset.get("critical_flag") and G.degree(node) == 0:
                    findings.append(FindingResult(
                        rule_id="R5",
                        issue_type="critical_disconnected_lineage",
                        severity="High",
                        message=f"Critical asset '{asset.get('name', node)}' has no lineage connections.",
                        asset_id=node,
                        asset_name=asset.get("name"),
                        agent=self.NAME,
                    ))

            logger.info(f"[LineageGuardian] Found {len(findings)} issues. Components: {len(components)}")
            return AgentResult(
                agent_name=self.NAME,
                findings=findings,
                metadata={
                    "total_nodes": G.number_of_nodes(),
                    "total_edges": G.number_of_edges(),
                    "connected_components": len(components),
                    "orphan_nodes": sum(1 for f in findings if f.issue_type == "orphan_node"),
                },
            )
        except Exception as e:
            logger.error(f"[LineageGuardian] Error: {e}")
            return AgentResult(agent_name=self.NAME, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Governance Gap Agent
# ─────────────────────────────────────────────────────────────────────────────

class GovernanceGapAgent:
    """
    Enforces operating model governance rules.
    Runs AFTER MetadataCuratorAgent + LineageGuardianAgent complete.
    """
    NAME = "governance_gap"

    async def run(
        self,
        assets: list[dict],
        lineage_pairs: list[dict],
        curator_result: AgentResult,
        lineage_result: AgentResult,
    ) -> AgentResult:
        logger.info(f"[GovernanceGap] Checking operating model rules on {len(assets)} assets")
        findings: list[FindingResult] = []
        try:
            lineage_asset_ids = {
                str(lp.get("source_asset_id", ""))
                for lp in lineage_pairs
            } | {
                str(lp.get("target_asset_id", ""))
                for lp in lineage_pairs
            }

            for asset in assets:
                asset_id   = str(asset.get("id", ""))
                asset_name = asset.get("name", "")
                tags       = asset.get("tags") or []
                is_cde     = asset.get("critical_flag") or "CDE" in tags
                is_kpi     = "KPI" in tags or asset.get("asset_type") == "KPI"
                is_pii     = asset.get("pii_flag") or "PII" in tags

                # GG1: Every CDE must have an owner
                if is_cde and not asset.get("owner", "").strip():
                    findings.append(FindingResult(
                        rule_id="GG1",
                        issue_type="cde_missing_owner",
                        severity="High",
                        message=f"Critical Data Element '{asset_name}' has no owner. Governance policy violation.",
                        asset_id=asset_id,
                        asset_name=asset_name,
                        agent=self.NAME,
                    ))

                # GG2: Every KPI must have lineage
                if is_kpi and asset_id not in lineage_asset_ids:
                    findings.append(FindingResult(
                        rule_id="GG2",
                        issue_type="kpi_no_lineage",
                        severity="High",
                        message=f"KPI asset '{asset_name}' has no lineage. Cannot verify data provenance.",
                        asset_id=asset_id,
                        asset_name=asset_name,
                        agent=self.NAME,
                    ))

                # GG3: Every PII asset must be classified (tagged)
                if is_pii and "PII" not in tags:
                    findings.append(FindingResult(
                        rule_id="GG3",
                        issue_type="pii_not_classified",
                        severity="High",
                        message=f"Asset '{asset_name}' contains PII but is not tagged as PII in Collibra.",
                        asset_id=asset_id,
                        asset_name=asset_name,
                        agent=self.NAME,
                    ))

                # GG4: Every critical asset must have a steward
                if is_cde and not asset.get("steward", "").strip():
                    findings.append(FindingResult(
                        rule_id="GG4",
                        issue_type="critical_no_steward",
                        severity="High",
                        message=f"Critical asset '{asset_name}' has no data steward assigned.",
                        asset_id=asset_id,
                        asset_name=asset_name,
                        agent=self.NAME,
                    ))

            logger.info(f"[GovernanceGap] Found {len(findings)} governance violations")
            return AgentResult(
                agent_name=self.NAME,
                findings=findings,
                metadata={
                    "cde_violations": sum(1 for f in findings if f.rule_id in ("GG1", "GG4")),
                    "kpi_violations": sum(1 for f in findings if f.rule_id == "GG2"),
                    "pii_violations": sum(1 for f in findings if f.rule_id == "GG3"),
                },
            )
        except Exception as e:
            logger.error(f"[GovernanceGap] Error: {e}")
            return AgentResult(agent_name=self.NAME, error=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Executive Risk Agent
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ExecutiveSummary:
    health_score:    float
    audit_score:     float
    total_findings:  int
    high_count:      int
    medium_count:    int
    low_count:       int
    top_risks:       list[FindingResult]
    priority_actions: list[str]
    agent_metadata:  dict[str, Any]


class ExecutiveRiskAgent:
    """
    Aggregates all findings from the other 3 agents.
    Computes health score, audit readiness score, and priority actions.
    Runs LAST after all other agents complete.
    """
    NAME = "executive_risk"

    def _compute_audit_score(self, findings: list[FindingResult], total_assets: int) -> float:
        """
        Audit readiness considers % of critical assets fully covered
        (owner + steward + description + lineage).
        Simple proxy: 100 - (High findings / total_assets * 100), floor 0.
        """
        high_count = sum(1 for f in findings if f.severity == "High")
        if total_assets == 0:
            return 0.0
        penalty = (high_count / total_assets) * 100
        return max(0.0, round(100 - penalty, 1))

    def _derive_priority_actions(self, findings: list[FindingResult]) -> list[str]:
        """Top 5 human-readable action items based on highest-severity clusters."""
        actions = []
        high_findings = [f for f in findings if f.severity == "High"]

        issue_counts: dict[str, int] = {}
        for f in high_findings:
            issue_counts[f.issue_type] = issue_counts.get(f.issue_type, 0) + 1

        action_map = {
            "missing_owner":             "Assign data owners to all unowned assets — start with critical data elements.",
            "critical_no_steward":       "Assign stewards to all critical/CDE assets immediately.",
            "cde_missing_owner":         "Assign owners to all CDE assets — required for audit readiness.",
            "kpi_no_lineage":            "Map lineage for all KPI assets to establish data provenance.",
            "pii_not_classified":        "Tag all PII assets in Collibra to ensure regulatory compliance.",
            "critical_disconnected_lineage": "Establish lineage paths for all disconnected critical assets.",
            "broken_lineage":            "Repair broken lineage paths to restore end-to-end data traceability.",
        }

        seen = set()
        for issue_type, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            if issue_type in action_map and issue_type not in seen:
                actions.append(f"{action_map[issue_type]} ({count} instances)")
                seen.add(issue_type)
            if len(actions) >= 5:
                break

        return actions

    async def run(
        self,
        assets: list[dict],
        curator_result: AgentResult,
        lineage_result: AgentResult,
        gap_result: AgentResult,
    ) -> tuple[ExecutiveSummary, list[FindingResult]]:
        logger.info("[ExecutiveRisk] Aggregating all findings")

        all_findings: list[FindingResult] = []
        for result in [curator_result, lineage_result, gap_result]:
            if result.findings:
                all_findings.extend(result.findings)

        high   = [f for f in all_findings if f.severity == "High"]
        medium = [f for f in all_findings if f.severity == "Medium"]
        low    = [f for f in all_findings if f.severity == "Low"]

        health_score = RulesEngine.compute_health_score(all_findings)
        audit_score  = self._compute_audit_score(all_findings, len(assets))
        top_risks    = sorted(high, key=lambda f: f.rule_id)[:10]
        actions      = self._derive_priority_actions(all_findings)

        summary = ExecutiveSummary(
            health_score=round(health_score, 1),
            audit_score=audit_score,
            total_findings=len(all_findings),
            high_count=len(high),
            medium_count=len(medium),
            low_count=len(low),
            top_risks=top_risks,
            priority_actions=actions,
            agent_metadata={
                "curator": curator_result.metadata,
                "lineage": lineage_result.metadata,
                "gap": gap_result.metadata,
            },
        )
        logger.info(f"[ExecutiveRisk] Health: {health_score} | Audit: {audit_score} | Findings: {len(all_findings)}")
        return summary, all_findings


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator — wires the four agents together
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class OrchestrationResult:
    summary:      ExecutiveSummary
    all_findings: list[FindingResult]
    agent_results: dict[str, AgentResult]


class AgentOrchestrator:
    """
    Runs all 4 agents in the correct dependency order:
      Phase 1 (parallel): MetadataCurator + LineageGuardian
      Phase 2 (sequential): GovernanceGap  (depends on Phase 1)
      Phase 3 (sequential): ExecutiveRisk  (depends on Phase 2)
    """

    def __init__(self):
        self.curator  = MetadataCuratorAgent()
        self.lineage  = LineageGuardianAgent()
        self.gap      = GovernanceGapAgent()
        self.executive = ExecutiveRiskAgent()

    async def run(
        self,
        assets: list[dict],
        lineage_pairs: list[dict],
    ) -> OrchestrationResult:
        logger.info(f"[Orchestrator] Starting pipeline: {len(assets)} assets, {len(lineage_pairs)} lineage pairs")

        # Phase 1: parallel
        curator_result, lineage_result = await asyncio.gather(
            self.curator.run(assets, lineage_pairs),
            self.lineage.run(assets, lineage_pairs),
        )

        # Phase 2: sequential (needs Phase 1 results)
        gap_result = await self.gap.run(
            assets, lineage_pairs, curator_result, lineage_result
        )

        # Phase 3: sequential (aggregates everything)
        summary, all_findings = await self.executive.run(
            assets, curator_result, lineage_result, gap_result
        )

        logger.info(f"[Orchestrator] Pipeline complete. Score: {summary.health_score}")
        return OrchestrationResult(
            summary=summary,
            all_findings=all_findings,
            agent_results={
                "curator": curator_result,
                "lineage": lineage_result,
                "gap": gap_result,
            },
        )
