# app/services/ai_service.py
from __future__ import annotations
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from app.models.ai import Anomaly, Alert, Severity, AlertStatus, Audience
from app.models.warehouse import DimMonth
from app.services.ai_rules import (
    anomalies_ventes, anomalies_depenses, anomalies_stock, anomalies_marge,
    anomalies_banque_caisse, anomalies_clients, _get_month
)
from app.services.ai_reco import generate_alerts  # <-- NOUVEAU


def run_analysis(db: Session, *, annee: int, mois: str, type_fichier: str | None = None) -> Dict[str, Any]:
    """
    Exécute règles d'anomalies + génère des alertes/reco lisibles.
    """
    # 1) RÈGLES D'ANOMALIES
    buckets: Dict[str, List[Anomaly]] = {
        "ventes": anomalies_ventes(db, annee, mois),
        "depenses": anomalies_depenses(db, annee, mois),
        "stock": anomalies_stock(db, annee, mois),
        "marge": anomalies_marge(db, annee, mois),
        "banque_caisse": anomalies_banque_caisse(db, annee, mois),
        "clients": anomalies_clients(db, annee, mois),
    }

    total = 0
    for _, lst in buckets.items():
        for a in lst:
            db.add(a)
        total += len(lst)

    dm: DimMonth = _get_month(db, annee, mois)  # créé si absent

    # 2) RECO / ALERTES MÉTIER
    for alert in generate_alerts(db, annee, mois):
        db.add(alert)

    # 3) ALERTES DE SYNTHÈSE
    if total > 0:
        db.add(Alert(
            severity=Severity.warning,
            status=AlertStatus.open,
            audience=Audience.both,
            title=f"Anomalies détectées pour {mois} {annee}",
            body=f"{total} signalements au total ce mois.",
            month_id=dm.id,
            entity_type="global",
            entity_name=None,
            source_rule="SUMMARY",
        ))
    crit_count = sum(1 for lst in buckets.values() for a in lst if a.severity.name == "critical")
    if crit_count > 0:
        db.add(Alert(
            severity=Severity.critical,
            status=AlertStatus.open,
            audience=Audience.dg,
            title=f"{crit_count} anomalies CRITIQUES",
            body="Priorité : écarts de stock, réconciliations, pics de ventes.",
            month_id=dm.id,
            entity_type="global",
            entity_name=None,
            source_rule="CRITICAL_SUMMARY",
        ))

    db.commit()

    return {
        "ok": True,
        "inserted_anomalies": total,
        "critical": crit_count,
        "by_rule": {k: len(v) for k, v in buckets.items()},
    }
