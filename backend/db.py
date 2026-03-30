from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean
from datetime import datetime, timezone
from config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class AlertRecord(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    log_text = Column(Text, nullable=False)
    label = Column(String(100))
    confidence = Column(Float)
    risk_score = Column(Float)
    risk_tier = Column(String(20))
    explanation = Column(Text)
    mitre_technique = Column(String(200))
    source_ip = Column(String(50))
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    feedback = Column(String(20), nullable=True)
    feedback_label = Column(String(100), nullable=True)
    # Ensemble: JSON blob — {"svm": "auth-failed", "bert": null, ...}
    model_votes = Column(Text, nullable=True)


class AttackChainRecord(Base):
    __tablename__ = "attack_chains"

    id = Column(Integer, primary_key=True, index=True)
    chain_name = Column(String(200))
    chain_type = Column(String(100))
    alert_ids = Column(Text)
    source_ip = Column(String(50))
    severity = Column(String(20))
    detected_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    description = Column(Text)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add model_votes column to existing DBs that predate this field
        try:
            await conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE alerts ADD COLUMN model_votes TEXT"
                )
            )
        except Exception:
            pass  # column already exists — fine


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()