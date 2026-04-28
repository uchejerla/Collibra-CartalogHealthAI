"""
app/main.py — Catalog Health AI FastAPI application.

Endpoints:
  POST /upload-assets    — ingest Collibra asset export
  POST /upload-lineage   — ingest lineage pairs
  POST /run-scan         — trigger full agent pipeline
  GET  /health-score     — latest governance health score
  GET  /issues           — paginated findings list
  GET  /summary          — AI-generated executive summary
  GET  /healthz          — service health check
"""
from __future__ import annotations
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, engine
from app.models import AISummary, Asset, Finding, Lineage, ScanRun
from app.services.ingest_service import (
    parse_assets_csv,
    parse_lineage_csv,
    upsert_assets,
    upsert_lineage,
)
from app.services.claude_client import (
    generate_executive_summary,
    generate_steward_guidance,
    generate_trend_analysis,
)
from agents import AgentOrchestrator

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# App lifecycle
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Catalog Health AI starting up...")
    yield
    logger.info("Catalog Health AI shutting down...")
    await engine.dispose()


app = FastAPI(
    title="Catalog Health AI",
    description="AI governance reliability layer for Collibra",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic response models
# ─────────────────────────────────────────────────────────────────────────────

class IngestResponse(BaseModel):
    scan_id:        str
    records_processed: int
    message:        str

class HealthScoreResponse(BaseModel):
    scan_id:        str | None
    health_score:   float
    audit_score:    float | None
    high_count:     int
    medium_count:   int
    low_count:      int
    total_findings: int
    total_assets:   int
    scanned_at:     datetime | None
    breakdown:      dict[str, Any]

class FindingResponse(BaseModel):
    id:          str
    asset_name:  str | None
    agent:       str
    rule_id:     str
    issue_type:  str
    severity:    str
    message:     str
    status:      str
    created_at:  datetime

class IssuesResponse(BaseModel):
    scan_id:     str | None
    total:       int
    page:        int
    page_size:   int
    findings:    list[FindingResponse]

class SummaryResponse(BaseModel):
    scan_id:      str | None
    executive:    str | None
    steward:      str | None
    trend:        str | None
    generated_at: datetime | None
    from_cache:   bool

class ScanRunResponse(BaseModel):
    scan_id:        str
    status:         str
    health_score:   float | None
    audit_score:    float | None
    total_assets:   int
    total_findings: int
    started_at:     datetime
    completed_at:   datetime | None


# ─────────────────────────────────────────────────────────────────────────────
# Helper: get latest scan
# ─────────────────────────────────────────────────────────────────────────────

async def _get_latest_scan(db: AsyncSession) -> ScanRun | None:
    result = await db.execute(
        select(ScanRun)
        .where(ScanRun.status == "completed")
        .order_by(ScanRun.completed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/healthz")
async def health_check():
    return {"status": "ok", "version": "1.0.0", "env": settings.app_env}


@app.post("/upload-assets", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def upload_assets(
    file: UploadFile = File(...),
    db:   AsyncSession = Depends(get_db),
):
    """Accept a Collibra asset export CSV and upsert assets into DB."""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    content = await file.read()
    records = parse_assets_csv(content)
    if not records:
        raise HTTPException(status_code=422, detail="No valid asset records found in CSV")

    scan = ScanRun(status="ingesting", total_assets=len(records))
    db.add(scan)
    await db.flush()

    await upsert_assets(db, records, scan.id)
    scan.status = "assets_ingested"
    logger.info(f"Ingested {len(records)} assets into scan {scan.id}")

    return IngestResponse(
        scan_id=str(scan.id),
        records_processed=len(records),
        message=f"Successfully ingested {len(records)} assets. Use scan_id to upload lineage.",
    )


@app.post("/upload-lineage", response_model=IngestResponse, status_code=status.HTTP_201_CREATED)
async def upload_lineage(
    file:    UploadFile = File(...),
    scan_id: str = Query(..., description="scan_id returned from /upload-assets"),
    db:      AsyncSession = Depends(get_db),
):
    """Accept a Collibra lineage export CSV and store lineage pairs."""
    try:
        scan_uuid = uuid.UUID(scan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id format")

    scan_result = await db.execute(select(ScanRun).where(ScanRun.id == scan_uuid))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

    content = await file.read()
    records = parse_lineage_csv(content)

    # Build name → ID lookup from assets in this scan
    assets_result = await db.execute(select(Asset).where(Asset.scan_id == scan_uuid))
    assets = assets_result.scalars().all()
    name_to_id = {a.name: a.id for a in assets}

    inserted = await upsert_lineage(db, records, name_to_id, scan_uuid)
    scan.status = "lineage_ingested"

    return IngestResponse(
        scan_id=scan_id,
        records_processed=inserted,
        message=f"Ingested {inserted} lineage pairs. Call POST /run-scan?scan_id={scan_id} to start analysis.",
    )


@app.post("/run-scan", response_model=ScanRunResponse)
async def run_scan(
    scan_id: str = Query(...),
    db:      AsyncSession = Depends(get_db),
):
    """Trigger the 4-agent pipeline for an ingested scan."""
    try:
        scan_uuid = uuid.UUID(scan_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid scan_id")

    scan_result = await db.execute(select(ScanRun).where(ScanRun.id == scan_uuid))
    scan = scan_result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Load assets and lineage for this scan
    assets_result  = await db.execute(select(Asset).where(Asset.scan_id == scan_uuid))
    lineage_result = await db.execute(select(Lineage).where(Lineage.scan_id == scan_uuid))

    assets       = [dict(a.__dict__) for a in assets_result.scalars().all()]
    lineage_pairs = [dict(l.__dict__) for l in lineage_result.scalars().all()]

    # Run agent pipeline
    scan.status = "running"
    orchestrator = AgentOrchestrator()
    result = await orchestrator.run(assets, lineage_pairs)

    # Persist findings
    for f in result.all_findings:
        finding = Finding(
            scan_id=scan_uuid,
            asset_id=uuid.UUID(str(f.asset_id)) if f.asset_id else None,
            asset_name=f.asset_name,
            agent=f.agent,
            rule_id=f.rule_id,
            issue_type=f.issue_type,
            severity=f.severity,
            message=f.message,
            details=f.details,
        )
        db.add(finding)

    # Update scan run
    scan.status         = "completed"
    scan.health_score   = result.summary.health_score
    scan.audit_score    = result.summary.audit_score
    scan.total_findings = len(result.all_findings)
    scan.completed_at   = datetime.now(timezone.utc)

    logger.info(f"Scan {scan_id} complete. Score: {result.summary.health_score}")
    return ScanRunResponse(
        scan_id=str(scan.id),
        status=scan.status,
        health_score=scan.health_score,
        audit_score=scan.audit_score,
        total_assets=len(assets),
        total_findings=scan.total_findings,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
    )


@app.get("/health-score", response_model=HealthScoreResponse)
async def get_health_score(db: AsyncSession = Depends(get_db)):
    """Return the governance health score from the latest completed scan."""
    scan = await _get_latest_scan(db)
    if not scan:
        return HealthScoreResponse(
            scan_id=None, health_score=0, audit_score=None,
            high_count=0, medium_count=0, low_count=0,
            total_findings=0, total_assets=0, scanned_at=None, breakdown={},
        )

    findings_result = await db.execute(select(Finding).where(Finding.scan_id == scan.id))
    findings = findings_result.scalars().all()

    high   = sum(1 for f in findings if f.severity == "High")
    medium = sum(1 for f in findings if f.severity == "Medium")
    low    = sum(1 for f in findings if f.severity == "Low")

    # Breakdown by agent
    breakdown: dict[str, Any] = {}
    for f in findings:
        breakdown.setdefault(f.agent, {"High": 0, "Medium": 0, "Low": 0})
        breakdown[f.agent][f.severity] += 1

    return HealthScoreResponse(
        scan_id=str(scan.id),
        health_score=scan.health_score or 0,
        audit_score=scan.audit_score,
        high_count=high,
        medium_count=medium,
        low_count=low,
        total_findings=len(findings),
        total_assets=scan.total_assets,
        scanned_at=scan.completed_at,
        breakdown=breakdown,
    )


@app.get("/issues", response_model=IssuesResponse)
async def get_issues(
    severity:   str | None = Query(None, description="High | Medium | Low"),
    agent:      str | None = Query(None),
    issue_type: str | None = Query(None),
    status_:    str | None = Query(None, alias="status"),
    page:       int        = Query(1, ge=1),
    page_size:  int        = Query(50, ge=1, le=200),
    db:         AsyncSession = Depends(get_db),
):
    """Paginated list of governance findings from the latest scan."""
    scan = await _get_latest_scan(db)
    if not scan:
        return IssuesResponse(scan_id=None, total=0, page=1, page_size=page_size, findings=[])

    query = select(Finding).where(Finding.scan_id == scan.id)
    if severity:
        query = query.where(Finding.severity == severity)
    if agent:
        query = query.where(Finding.agent == agent)
    if issue_type:
        query = query.where(Finding.issue_type == issue_type)
    if status_:
        query = query.where(Finding.status == status_)

    # Total count
    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    # Paginate
    query = query.order_by(
        Finding.severity.desc(),
        Finding.created_at.asc()
    ).offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    findings = result.scalars().all()

    return IssuesResponse(
        scan_id=str(scan.id),
        total=total,
        page=page,
        page_size=page_size,
        findings=[
            FindingResponse(
                id=str(f.id),
                asset_name=f.asset_name,
                agent=f.agent,
                rule_id=f.rule_id,
                issue_type=f.issue_type,
                severity=f.severity,
                message=f.message,
                status=f.status,
                created_at=f.created_at,
            )
            for f in findings
        ],
    )


@app.get("/summary", response_model=SummaryResponse)
async def get_summary(
    force_refresh: bool = Query(False, description="Bypass cache and regenerate"),
    db:            AsyncSession = Depends(get_db),
):
    """AI-generated executive summary for the latest scan (cached 24h)."""
    scan = await _get_latest_scan(db)
    if not scan:
        return SummaryResponse(
            scan_id=None, executive=None, steward=None,
            trend=None, generated_at=None, from_cache=False,
        )

    # Check cache
    if not force_refresh:
        cache_result = await db.execute(
            select(AISummary)
            .where(AISummary.scan_id == scan.id)
            .where(AISummary.expires_at > datetime.now(timezone.utc))
            .order_by(AISummary.created_at.desc())
        )
        cached = cache_result.scalars().all()
        if cached:
            summaries = {s.summary_type: s.content for s in cached}
            if "executive" in summaries:
                return SummaryResponse(
                    scan_id=str(scan.id),
                    executive=summaries.get("executive"),
                    steward=summaries.get("steward"),
                    trend=summaries.get("trend"),
                    generated_at=cached[0].created_at,
                    from_cache=True,
                )

    # Generate fresh summaries
    findings_result = await db.execute(select(Finding).where(Finding.scan_id == scan.id))
    findings = findings_result.scalars().all()

    high   = [f for f in findings if f.severity == "High"]
    medium = [f for f in findings if f.severity == "Medium"]
    low    = [f for f in findings if f.severity == "Low"]

    top_risks = [{"message": f.message} for f in sorted(high, key=lambda x: x.rule_id)[:10]]

    # Build priority actions from findings
    issue_counts: dict[str, int] = {}
    for f in high:
        issue_counts[f.issue_type] = issue_counts.get(f.issue_type, 0) + 1
    priority_actions = [f"{k}: {v} instances" for k, v in sorted(issue_counts.items(), key=lambda x: -x[1])[:5]]

    exec_response = await generate_executive_summary(
        health_score=scan.health_score or 0,
        audit_score=scan.audit_score or 0,
        high_count=len(high),
        medium_count=len(medium),
        low_count=len(low),
        total_assets=scan.total_assets,
        top_risks=top_risks,
        priority_actions=priority_actions,
    )

    # Build steward guidance input
    findings_by_type: dict[str, list[dict]] = {}
    for f in findings:
        findings_by_type.setdefault(f.issue_type, []).append({
            "message": f.message, "severity": f.severity, "asset_name": f.asset_name
        })
    steward_response = await generate_steward_guidance(findings_by_type)

    # Cache results (24h TTL)
    expires = datetime.now(timezone.utc) + timedelta(hours=24)
    for response in [exec_response, steward_response]:
        summary = AISummary(
            scan_id=scan.id,
            summary_type=response.summary_type,
            content=response.content,
            model_used=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            expires_at=expires,
        )
        db.add(summary)

    return SummaryResponse(
        scan_id=str(scan.id),
        executive=exec_response.content,
        steward=steward_response.content,
        trend=None,   # Requires 2+ scans — enabled by FEATURE_TREND_ANALYSIS
        generated_at=datetime.now(timezone.utc),
        from_cache=False,
    )
