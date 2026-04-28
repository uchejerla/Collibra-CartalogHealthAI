"""
app/models/__init__.py — SQLAlchemy ORM models.

Maps to the schema defined in backend/db/schema.sql.
All models use async-compatible SQLAlchemy 2.0 mapped_column() syntax.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, Float, ForeignKey,
    Integer, String, Text, TIMESTAMP,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────────────────────────────────────
# ScanRun — one execution of the agent pipeline
# ─────────────────────────────────────────────────────────────────────────────

class ScanRun(Base):
    __tablename__ = "scan_runs"

    id:             Mapped[uuid.UUID]      = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status:         Mapped[str]            = mapped_column(String(32), default="running")
    total_assets:   Mapped[int]            = mapped_column(Integer, default=0)
    total_findings: Mapped[int]            = mapped_column(Integer, default=0)
    health_score:   Mapped[float | None]   = mapped_column(Float, nullable=True)
    audit_score:    Mapped[float | None]   = mapped_column(Float, nullable=True)
    started_at:     Mapped[datetime]       = mapped_column(TIMESTAMP(timezone=True), default=_now)
    completed_at:   Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    error_message:  Mapped[str | None]     = mapped_column(Text, nullable=True)

    assets:     Mapped[list["Asset"]]     = relationship("Asset",     back_populates="scan_run", lazy="select")
    findings:   Mapped[list["Finding"]]   = relationship("Finding",   back_populates="scan_run", lazy="select")
    summaries:  Mapped[list["AISummary"]] = relationship("AISummary", back_populates="scan_run", lazy="select")

    def __repr__(self) -> str:
        return f"<ScanRun id={self.id} status={self.status} score={self.health_score}>"


# ─────────────────────────────────────────────────────────────────────────────
# Asset — Collibra asset record
# ─────────────────────────────────────────────────────────────────────────────

class Asset(Base):
    __tablename__ = "assets"

    id:            Mapped[uuid.UUID]         = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id:   Mapped[str | None]        = mapped_column(String(256), nullable=True, index=True)
    name:          Mapped[str]               = mapped_column(Text, nullable=False)
    asset_type:    Mapped[str | None]        = mapped_column(String(128), nullable=True)
    domain:        Mapped[str | None]        = mapped_column(String(256), nullable=True, index=True)
    owner:         Mapped[str | None]        = mapped_column(String(256), nullable=True, index=True)
    steward:       Mapped[str | None]        = mapped_column(String(256), nullable=True)
    description:   Mapped[str | None]        = mapped_column(Text, nullable=True)
    critical_flag: Mapped[bool]              = mapped_column(Boolean, default=False, index=True)
    pii_flag:      Mapped[bool]              = mapped_column(Boolean, default=False)
    last_modified: Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True), nullable=True, index=True)
    tags:          Mapped[list[str] | None]  = mapped_column(ARRAY(String), nullable=True)
    raw_metadata:  Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    scan_id:       Mapped[uuid.UUID | None]  = mapped_column(UUID(as_uuid=True), ForeignKey("scan_runs.id"), nullable=True, index=True)
    created_at:    Mapped[datetime]          = mapped_column(TIMESTAMP(timezone=True), default=_now)
    updated_at:    Mapped[datetime]          = mapped_column(TIMESTAMP(timezone=True), default=_now)
    deleted_at:    Mapped[datetime | None]   = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    scan_run: Mapped["ScanRun | None"] = relationship("ScanRun", back_populates="assets")
    findings: Mapped[list["Finding"]]  = relationship("Finding", back_populates="asset",    lazy="select")

    def __repr__(self) -> str:
        return f"<Asset id={self.id} name={self.name!r} domain={self.domain!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# Lineage — source → target data lineage edge
# ─────────────────────────────────────────────────────────────────────────────

class Lineage(Base):
    __tablename__ = "lineage"

    id:               Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_asset_id:  Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=True, index=True)
    target_asset_id:  Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=True, index=True)
    source_name:      Mapped[str | None]       = mapped_column(Text, nullable=True)
    target_name:      Mapped[str | None]       = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float]            = mapped_column(Float, default=1.0)
    lineage_type:     Mapped[str]              = mapped_column(String(64), default="data_flow")
    scan_id:          Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_runs.id"), nullable=True, index=True)
    created_at:       Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), default=_now)
    updated_at:       Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), default=_now)

    def __repr__(self) -> str:
        return f"<Lineage {self.source_name!r} → {self.target_name!r} conf={self.confidence_score}>"


# ─────────────────────────────────────────────────────────────────────────────
# Finding — one governance issue detected by an agent
# ─────────────────────────────────────────────────────────────────────────────

class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("severity IN ('High', 'Medium', 'Low')",                          name="chk_severity"),
        CheckConstraint("status IN ('Open', 'In Progress', 'Resolved', 'Suppressed')",   name="chk_status"),
    )

    id:          Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id:     Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    asset_id:    Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id",    ondelete="CASCADE"), nullable=True, index=True)
    asset_name:  Mapped[str | None]       = mapped_column(Text, nullable=True)
    agent:       Mapped[str]              = mapped_column(String(64),  nullable=False)
    rule_id:     Mapped[str]              = mapped_column(String(16),  nullable=False)
    issue_type:  Mapped[str]              = mapped_column(String(64),  nullable=False, index=True)
    severity:    Mapped[str]              = mapped_column(String(16),  nullable=False, index=True)
    message:     Mapped[str]              = mapped_column(Text, nullable=False)
    details:     Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    status:      Mapped[str]              = mapped_column(String(32), default="Open", index=True)
    resolved_by: Mapped[str | None]       = mapped_column(String(256), nullable=True)
    resolved_at: Mapped[datetime | None]  = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at:  Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), default=_now)
    updated_at:  Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), default=_now)

    scan_run: Mapped["ScanRun | None"] = relationship("ScanRun", back_populates="findings")
    asset:    Mapped["Asset | None"]   = relationship("Asset",   back_populates="findings")

    def __repr__(self) -> str:
        return f"<Finding {self.rule_id} {self.severity} {self.issue_type!r} asset={self.asset_name!r}>"


# ─────────────────────────────────────────────────────────────────────────────
# AISummary — cached Claude-generated summaries (24h TTL)
# ─────────────────────────────────────────────────────────────────────────────

class AISummary(Base):
    __tablename__ = "ai_summaries"

    id:                Mapped[uuid.UUID]        = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id:           Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    summary_type:      Mapped[str]              = mapped_column(String(32), nullable=False, index=True)
    content:           Mapped[str]              = mapped_column(Text, nullable=False)
    model_used:        Mapped[str]              = mapped_column(String(64), default="claude-sonnet-4-20250514")
    prompt_tokens:     Mapped[int | None]       = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None]       = mapped_column(Integer, nullable=True)
    expires_at:        Mapped[datetime | None]  = mapped_column(TIMESTAMP(timezone=True), nullable=True)
    created_at:        Mapped[datetime]         = mapped_column(TIMESTAMP(timezone=True), default=_now)

    scan_run: Mapped["ScanRun | None"] = relationship("ScanRun", back_populates="summaries")

    def __repr__(self) -> str:
        return f"<AISummary type={self.summary_type!r} scan_id={self.scan_id}>"


__all__ = ["Base", "ScanRun", "Asset", "Lineage", "Finding", "AISummary"]
