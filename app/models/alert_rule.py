import uuid
from sqlalchemy import Boolean, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base, TimestampMixin


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    sensor_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # "threshold" or "window"
    operator: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )  # ">", ">=", "<", "<=", "==", "!="
    threshold: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    aggregation: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )  # "AVG", "MIN", "MAX", "COUNT"
    window: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )  # "1m", "5m", "10m", "30m", "1h"
    window_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    cooldown_seconds: Mapped[int] = mapped_column(
        Integer,
        default=300,
        nullable=False,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        default="MEDIUM",
        nullable=False,
    )  # "LOW", "MEDIUM", "HIGH", "CRITICAL"

    alerts = relationship("Alert", back_populates="rule", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_rules_type_enabled", "sensor_type", "enabled"),
    )
