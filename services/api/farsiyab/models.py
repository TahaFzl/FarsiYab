"""Database schema. Mirrors docs/03-data-model.md."""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CONFIDENCE_LABELS = ("high", "medium", "low")
BUSINESS_STATUSES = ("active", "hidden", "removed_by_request", "closed")
LINK_KINDS = ("website", "facebook", "instagram", "telegram", "phone")
JOB_STATUSES = ("queued", "running", "done", "failed")
REPORT_REASONS = ("not_iranian", "closed", "wrong_info", "remove_request")


TZ = DateTime(timezone=True)
NOW = func.now


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB}


class Country(Base):
    __tablename__ = "country"

    code: Mapped[str] = mapped_column(String(2), primary_key=True)
    name_fa: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class City(Base):
    __tablename__ = "city"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    country_code: Mapped[str] = mapped_column(ForeignKey("country.code"))
    name_fa: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    center: Mapped[Any] = mapped_column(Geography("POINT", srid=4326))
    west: Mapped[float] = mapped_column(Float)
    south: Mapped[float] = mapped_column(Float)
    east: Mapped[float] = mapped_column(Float)
    north: Mapped[float] = mapped_column(Float)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    country: Mapped[Country] = relationship()


class Category(Base):
    __tablename__ = "category"

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    name_fa: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    parent_slug: Mapped[str | None] = mapped_column(ForeignKey("category.slug"))
    mvp: Mapped[bool] = mapped_column(Boolean, default=False)
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_mappings: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Source(Base):
    __tablename__ = "source"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name_fa: Mapped[str] = mapped_column(Text)
    name_en: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    phase: Mapped[int] = mapped_column(Integer)
    account_required: Mapped[bool] = mapped_column(Boolean, default=False)
    monthly_cap: Mapped[int | None] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    definition: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Business(Base):
    __tablename__ = "business"
    __table_args__ = (
        CheckConstraint(_in("confidence_label", CONFIDENCE_LABELS), name="confidence_label_valid"),
        CheckConstraint(_in("status", BUSINESS_STATUSES), name="status_valid"),
        Index("ix_business_city_status", "city_id", "status"),
        Index(
            "ix_business_name_latin_trgm",
            "name_latin",
            postgresql_using="gin",
            postgresql_ops={"name_latin": "gin_trgm_ops"},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"))
    name_fa: Mapped[str | None] = mapped_column(Text)
    name_latin: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    location: Mapped[Any | None] = mapped_column(Geography("POINT", srid=4326))
    phone_e164: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(Text)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_label: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    first_seen_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())
    last_verified_at: Mapped[datetime] = mapped_column(
        TZ, server_default=NOW()
    )
    website_checked_at: Mapped[datetime | None] = mapped_column(TZ)

    categories: Mapped[list["BusinessCategory"]] = relationship(cascade="all, delete-orphan")
    records: Mapped[list["SourceRecord"]] = relationship(cascade="all, delete-orphan")
    evidence: Mapped[list["Evidence"]] = relationship(cascade="all, delete-orphan")
    links: Mapped[list["BusinessLink"]] = relationship(cascade="all, delete-orphan")


class BusinessCategory(Base):
    __tablename__ = "business_category"
    __table_args__ = (Index("ix_business_category_slug", "category_slug", "business_id"),)

    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business.id", ondelete="CASCADE"), primary_key=True
    )
    category_slug: Mapped[str] = mapped_column(ForeignKey("category.slug"), primary_key=True)


class SourceRecord(Base):
    __tablename__ = "source_record"
    __table_args__ = (UniqueConstraint("source_id", "external_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(ForeignKey("source.id"))
    external_id: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    raw: Mapped[dict[str, Any] | None] = mapped_column()
    fetched_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())


class Evidence(Base):
    __tablename__ = "evidence"
    __table_args__ = (UniqueConstraint("source_record_id", "signal"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business.id", ondelete="CASCADE"), index=True
    )
    source_record_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("source_record.id", ondelete="CASCADE")
    )
    signal: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float)
    snippet: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())


class BusinessLink(Base):
    __tablename__ = "business_link"
    __table_args__ = (
        UniqueConstraint("business_id", "kind", "value"),
        CheckConstraint(_in("kind", LINK_KINDS), name="kind_valid"),
        Index("ix_business_link_kind_value", "kind", "value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("business.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)


class IndexStatus(Base):
    __tablename__ = "index_status"

    city_id: Mapped[int] = mapped_column(ForeignKey("city.id"), primary_key=True)
    last_indexed_at: Mapped[datetime | None] = mapped_column(TZ)
    per_source: Mapped[dict[str, Any]] = mapped_column(default=dict)
    category_counts: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(_in("status", JOB_STATUSES), name="status_valid"),
        Index(
            "uq_job_active_dedupe_key",
            "dedupe_key",
            unique=True,
            postgresql_where=text("status IN ('queued', 'running')"),
        ),
        Index("ix_job_claim", "status", "run_after"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run_after: Mapped[datetime] = mapped_column(TZ, server_default=NOW())
    result: Mapped[dict[str, Any] | None] = mapped_column()
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())
    started_at: Mapped[datetime | None] = mapped_column(TZ)
    finished_at: Mapped[datetime | None] = mapped_column(TZ)


class QuotaUsage(Base):
    __tablename__ = "quota_usage"

    source_id: Mapped[str] = mapped_column(ForeignKey("source.id"), primary_key=True)
    period: Mapped[str] = mapped_column(String(7), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0)


class Report(Base):
    __tablename__ = "report"
    __table_args__ = (CheckConstraint(_in("reason", REPORT_REASONS), name="reason_valid"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("business.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(Text)
    message: Mapped[str | None] = mapped_column(Text)
    contact_email: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="open")
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())


class DoNotIndex(Base):
    __tablename__ = "do_not_index"
    __table_args__ = (UniqueConstraint("kind", "value"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(Text)
    value: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TZ, server_default=NOW())
