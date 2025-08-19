# app/models/ai.py
from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Numeric, Enum, Text, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database.connection import Base

# Enums Python -> stockés comme ENUM SQL
class AnomalyType(enum.Enum):
    ventes = "ventes"
    achats = "achats"
    stock = "stock"
    depenses = "depenses"
    marge = "marge"
    banque = "banque"
    caisse = "caisse"
    clients = "clients"

class Severity(enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"

class AlertStatus(enum.Enum):
    open = "open"
    ack = "ack"
    closed = "closed"

class Audience(enum.Enum):
    comptable = "comptable"
    dg = "dg"
    both = "both"

class Anomaly(Base):
    __tablename__ = "anomalies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    type = Column(Enum(AnomalyType), nullable=False)  # ex: ventes, stock...
    severity = Column(Enum(Severity), nullable=False, default=Severity.warning)

    # Cible (produit / client / banque / categorie / global)
    object_type = Column(String, nullable=True)
    object_name = Column(String, nullable=True)

    # Périmètre
    date_id = Column(Integer, ForeignKey("dim_date.id"), nullable=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=True)

    # Métrique et seuil
    metric = Column(String, nullable=True)          # ex: "zscore_quantite", "reconcile_ecart"
    value = Column(Numeric(18, 4), nullable=True)
    threshold = Column(Numeric(18, 4), nullable=True)

    message = Column(Text, nullable=False)

    # Trace fichier source
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=True)

    __table_args__ = (
        Index("ix_anom_type_sev_month", "type", "severity", "month_id"),
        Index("ix_anom_type_date", "type", "date_id"),
    )


class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    severity = Column(Enum(Severity), nullable=False, default=Severity.warning)
    status = Column(Enum(AlertStatus), nullable=False, default=AlertStatus.open)
    audience = Column(Enum(Audience), nullable=False, default=Audience.comptable)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)

    # Contexte
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=True)
    entity_type = Column(String, nullable=True)  # produit/client/banque/categorie/global
    entity_name = Column(String, nullable=True)

    source_rule = Column(String, nullable=True)  # ex: "VENTES_ZSCORE_7J", "BANQUE_RECONCILE"

    __table_args__ = (
        Index("ix_alerts_sev_status_month", "severity", "status", "month_id"),
    )
