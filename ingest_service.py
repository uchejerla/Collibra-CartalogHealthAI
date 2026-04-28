"""
app/services/ingest_service.py — Collibra CSV/JSON ingest + DB upsert logic.

Handles:
  - CSV column mapping from Collibra export format → internal schema
  - Upsert logic (update if external_id exists, else insert)
  - Basic validation and error reporting
"""
from __future__ import annotations
import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import Asset, Lineage, ScanRun

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Collibra CSV column mappings
# Collibra export headers → internal field names
# Extend this map as you encounter different export formats
# ─────────────────────────────────────────────────────────────────────────────
ASSET_COLUMN_MAP: dict[str, str] = {
    # Standard Collibra export headers
    "Asset ID":            "external_id",
    "Asset Name":          "name",
    "Asset Type":          "asset_type",
    "Domain":              "domain",
    "Data Owner":          "owner",
    "Data Steward":        "steward",
    "Description":         "description",
    "Business Definition": "description",  # alternate header
    "Critical":            "critical_flag",
    "Critical Flag":       "critical_flag",
    "PII":                 "pii_flag",
    "Last Modified":       "last_modified",
    "Last Modified Date":  "last_modified",
    "Modified Date":       "last_modified",
    "Tags":                "tags",
    "Tag":                 "tags",
    # lowercase variants
    "asset_id":            "external_id",
    "name":                "name",
    "type":                "asset_type",
    "asset_type":          "asset_type",
    "domain":              "domain",
    "owner":               "owner",
    "steward":             "steward",
    "description":         "description",
    "critical_flag":       "critical_flag",
    "pii_flag":            "pii_flag",
    "last_modified":       "last_modified",
    "tags":                "tags",
}

LINEAGE_COLUMN_MAP: dict[str, str] = {
    "Source Asset":    "source_name",
    "Target Asset":    "target_name",
    "Source Asset ID": "source_external_id",
    "Target Asset ID": "target_external_id",
    "Confidence":      "confidence_score",
    "Type":            "lineage_type",
    # lowercase
    "source_asset":    "source_name",
    "target_asset":    "target_name",
    "source_name":     "source_name",
    "target_name":     "target_name",
    "confidence_score":"confidence_score",
    "lineage_type":    "lineage_type",
}


# ─────────────────────────────────────────────────────────────────────────────
# CSV parsing utilities
# ─────────────────────────────────────────────────────────────────────────────

def _parse_bool(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "yes", "1", "y")
    return bool(val)


def _parse_date(val: Any) -> datetime | None:
    if not val or str(val).strip() == "":
        return None
    if isinstance(val, datetime):
        return val
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(str(val).strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {val}")
    return None


def _parse_tags(val: Any) -> list[str]:
    if not val:
        return []
    if isinstance(val, list):
        return [str(t).strip() for t in val if t]
    return [t.strip() for t in str(val).split(",") if t.strip()]


def _map_row(raw_row: dict[str, Any], column_map: dict[str, str]) -> dict[str, Any]:
    """Map CSV row headers to internal field names. Unmapped headers go to raw_metadata."""
    mapped: dict[str, Any] = {}
    unmapped: dict[str, Any] = {}
    for k, v in raw_row.items():
        internal = column_map.get(k)
        if internal:
            mapped[internal] = v
        else:
            unmapped[k] = v
    mapped["_unmapped"] = unmapped
    return mapped


def parse_assets_csv(csv_content: str | bytes) -> list[dict[str, Any]]:
    """Parse a Collibra asset export CSV into a list of internal asset dicts."""
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(csv_content))
    records: list[dict[str, Any]] = []
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # start=2 (header=1)
        try:
            mapped = _map_row(dict(row), ASSET_COLUMN_MAP)
            name = mapped.get("name", "").strip()
            if not name:
                errors.append(f"Row {i}: missing required field 'name'. Skipped.")
                continue

            record = {
                "external_id":   mapped.get("external_id"),
                "name":          name,
                "asset_type":    mapped.get("asset_type"),
                "domain":        mapped.get("domain"),
                "owner":         mapped.get("owner") or None,
                "steward":       mapped.get("steward") or None,
                "description":   mapped.get("description") or None,
                "critical_flag": _parse_bool(mapped.get("critical_flag", False)),
                "pii_flag":      _parse_bool(mapped.get("pii_flag", False)),
                "last_modified": _parse_date(mapped.get("last_modified")),
                "tags":          _parse_tags(mapped.get("tags")),
                "raw_metadata":  mapped.get("_unmapped", {}),
            }
            records.append(record)
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    if errors:
        logger.warning(f"Asset CSV parse warnings ({len(errors)}): {errors[:5]}")

    logger.info(f"Parsed {len(records)} assets from CSV ({len(errors)} warnings)")
    return records


def parse_lineage_csv(csv_content: str | bytes) -> list[dict[str, Any]]:
    """Parse a Collibra lineage export CSV."""
    if isinstance(csv_content, bytes):
        csv_content = csv_content.decode("utf-8-sig")

    reader = csv.DictReader(io.StringIO(csv_content))
    records: list[dict[str, Any]] = []

    for i, row in enumerate(reader, start=2):
        mapped = _map_row(dict(row), LINEAGE_COLUMN_MAP)
        src = mapped.get("source_name") or mapped.get("source_external_id")
        tgt = mapped.get("target_name") or mapped.get("target_external_id")
        if not src or not tgt:
            logger.warning(f"Lineage row {i}: missing source or target. Skipped.")
            continue

        try:
            conf = float(str(mapped.get("confidence_score", "1.0")).strip())
        except ValueError:
            conf = 1.0

        records.append({
            "source_name":        str(src).strip(),
            "target_name":        str(tgt).strip(),
            "source_external_id": mapped.get("source_external_id"),
            "target_external_id": mapped.get("target_external_id"),
            "confidence_score":   min(1.0, max(0.0, conf)),
            "lineage_type":       mapped.get("lineage_type", "data_flow"),
        })

    logger.info(f"Parsed {len(records)} lineage pairs from CSV")
    return records


# ─────────────────────────────────────────────────────────────────────────────
# DB upsert logic
# ─────────────────────────────────────────────────────────────────────────────

async def upsert_assets(
    db: AsyncSession,
    records: list[dict[str, Any]],
    scan_id: uuid.UUID,
) -> list[Asset]:
    """Upsert assets: update if external_id exists, else insert."""
    created_assets: list[Asset] = []

    for record in records:
        existing = None
        if record.get("external_id"):
            result = await db.execute(
                select(Asset).where(Asset.external_id == record["external_id"])
            )
            existing = result.scalar_one_or_none()

        if existing:
            for k, v in record.items():
                if hasattr(existing, k) and k not in ("id", "created_at"):
                    setattr(existing, k, v)
            existing.scan_id = scan_id
            existing.updated_at = datetime.now(timezone.utc)
            created_assets.append(existing)
        else:
            asset = Asset(**{k: v for k, v in record.items() if hasattr(Asset, k)})
            asset.scan_id = scan_id
            db.add(asset)
            created_assets.append(asset)

    await db.flush()
    logger.info(f"Upserted {len(created_assets)} assets for scan {scan_id}")
    return created_assets


async def upsert_lineage(
    db: AsyncSession,
    records: list[dict[str, Any]],
    asset_name_to_id: dict[str, uuid.UUID],
    scan_id: uuid.UUID,
) -> int:
    """Insert lineage pairs, resolving asset names to IDs."""
    inserted = 0
    for record in records:
        src_id = asset_name_to_id.get(record["source_name"])
        tgt_id = asset_name_to_id.get(record["target_name"])

        if not src_id or not tgt_id:
            logger.debug(f"Skipping lineage pair: cannot resolve '{record['source_name']}' → '{record['target_name']}'")
            continue

        lineage = Lineage(
            source_asset_id=src_id,
            target_asset_id=tgt_id,
            source_name=record["source_name"],
            target_name=record["target_name"],
            confidence_score=record.get("confidence_score", 1.0),
            lineage_type=record.get("lineage_type", "data_flow"),
            scan_id=scan_id,
        )
        db.add(lineage)
        inserted += 1

    await db.flush()
    logger.info(f"Inserted {inserted} lineage pairs for scan {scan_id}")
    return inserted
