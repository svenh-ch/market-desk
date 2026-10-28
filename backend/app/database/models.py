from sqlalchemy import Boolean, Column, Integer, String, Float, Text, DateTime, UniqueConstraint
from sqlalchemy.sql import func
from app.database.connection import Base


class Company(Base):
    """Auswahlliste bekannter Wertpapiere (nur Stammdaten, keine Kurse/Kennzahlen)."""
    __tablename__ = "companies"

    id       = Column(Integer, primary_key=True, index=True)
    symbol   = Column(String, unique=True, index=True, nullable=False)
    name     = Column(String, nullable=False)
    sector   = Column(String)
    exchange = Column(String)


class CompanyRelationship(Base):
    """
    Lieferketten-Verbindungen. Nur mit Quelle erlaubt (source_doc, source_year).
    Wird erst durch die SEC-Auswertung befüllt; aktuell leer.
    """
    __tablename__ = "company_relationships"

    id                = Column(Integer, primary_key=True, index=True)
    company_a         = Column(String, index=True, nullable=False)
    company_b         = Column(String, index=True, nullable=False)
    relationship_type = Column(String, nullable=False)  # customer | supplier
    revenue_share     = Column(Float)                    # in Prozent, falls im Bericht genannt
    confidence        = Column(String)                   # bestätigt | wahrscheinlich
    source_doc        = Column(String, nullable=False)   # z. B. "SEC 10-K (2025-09-27)"
    source_year       = Column(Integer)
    source_url        = Column(String)
    section           = Column(String)                   # z. B. "Item 1A – Risikofaktoren"
    description       = Column(Text)                     # Originalsatz aus dem Bericht
    name_in_report    = Column(String)                   # Name, wie er im Bericht steht
    mapping_certain   = Column(Boolean)                  # Ticker-Zuordnung sicher?
    origin            = Column(String)                   # own_filing | mention | esef
    method            = Column(String)                   # Regeln (Textmuster) | Claude API

    __table_args__ = (
        UniqueConstraint("company_a", "company_b", "relationship_type", name="uq_relationship"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id       = Column(Integer, primary_key=True, index=True)
    symbol   = Column(String, unique=True, index=True, nullable=False)
    notes    = Column(Text)
    added_at = Column(DateTime(timezone=True), server_default=func.now())


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id           = Column(String, primary_key=True)
    symbol       = Column(String, index=True, nullable=False)
    condition    = Column(String, nullable=False)  # above | below
    threshold    = Column(Float, nullable=False)
    note         = Column(Text)
    triggered_at = Column(DateTime(timezone=True))
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class PortfolioPosition(Base):
    __tablename__ = "portfolio_positions"

    id        = Column(String, primary_key=True)
    symbol    = Column(String, index=True, nullable=False)
    quantity  = Column(Float, nullable=False)
    avg_cost  = Column(Float, nullable=False)
    notes     = Column(Text)
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
