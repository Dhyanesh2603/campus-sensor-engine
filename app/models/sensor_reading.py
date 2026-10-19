from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    sensor_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sensor_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    sensor = relationship("Sensor", back_populates="readings")

    __table_args__ = (
        Index("ix_readings_sensor_timestamp", "sensor_id", "timestamp"),
        Index("ix_readings_type_timestamp", "sensor_type", "timestamp"),
    )
