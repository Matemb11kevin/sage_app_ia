# app/services/ai_reco.py
from __future__ import annotations
from typing import List, Dict, Tuple
from decimal import Decimal

from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.models.ai import Alert, Severity, AlertStatus, Audience
from app.models.warehouse import (
    DimMonth, DimDate, DimProduit,
    FactVentesJournalieres, FactStockJournalier,
    FactDepensesMensuelles, FactMargeProduitMensuelle,
    FactBanqueMensuelle, FactCaisseMensuelle,
)
from app.services.ai_rules import _get_month


# --- helpers ---

def _sum_decimal(x) -> float:
    try:
        return float(Decimal(x or 0))
    except Exception:
        return 0.0


def _avg_daily_sales(db: Session, dm: DimMonth, produit_id: int) -> float:
    q = (
        db.query(func.coalesce(func.sum(FactVentesJournalieres.quantite), 0))
        .join(DimDate, DimDate.id == FactVentesJournalieres.date_id)
        .filter(DimDate.year == dm.year, DimDate.month == dm.month,
                FactVentesJournalieres.produit_id == produit_id)
    ).scalar()
    # moyenne sur le nombre de jours où il y a eu des ventes (évite de diluer sur tout le mois)
    days = (
        db.query(func.count(func.distinct(DimDate.date)))
        .join(FactVentesJournalieres, FactVentesJournalieres.date_id == DimDate.id)
        .filter(DimDate.year == dm.year, DimDate.month == dm.month,
                FactVentesJournalieres.produit_id == produit_id)
    ).scalar() or 0
    if days <= 0:
        return 0.0
    return _sum_decimal(q) / days


def _last_stock_final(db: Session, dm: DimMonth, produit_id: int) -> float:
    row = (
        db.query(FactStockJournalier.stock_final)
        .join(DimDate, DimDate.id == FactStockJournalier.date_id)
        .filter(DimDate.year == dm.year, DimDate.month == dm.month,
                FactStockJournalier.produit_id == produit_id)
        .order_by(desc(DimDate.date))
        .first()
    )
    return _sum_decimal(row[0]) if row else 0.0


# --- générateurs d'alertes/reco ---

def reco_reappro_stock(db: Session, annee: int, mois: str) -> List[Alert]:
    """
    Recommande un réappro si la couverture < 5 jours (critique si < 2).
    couverture = stock_final_dernier_jour / moy_ventes_journalières
    """
    out: List[Alert] = []
    dm = _get_month(db, annee, mois)
    if not dm:
        return out

    produits = db.query(DimProduit).all()
    for p in produits:
        avg = _avg_daily_sales(db, dm, p.id)
        if avg <= 0:
            continue
        sf = _last_stock_final(db, dm, p.id)
        coverage = sf / avg if avg > 0 else 0.0
        if coverage < 5.0:
            sev = Severity.critical if coverage < 2.0 else Severity.warning
            out.append(Alert(
                severity=sev,
                status=AlertStatus.open,
                audience=Audience.both,
                title=f"Réapprovisionnement recommandé : {p.name}",
                body=f"Couverture {coverage:.1f} j — stock final {sf:.0f} vs ventes moy. {avg:.1f}/j.",
                month_id=dm.id,
                entity_type="produit",
                entity_name=p.name,
                source_rule="RECO_REAPPRO",
            ))
    return out


def reco_depenses_surchauffe(db: Session, annee: int, mois: str) -> List[Alert]:
    """
    Alerte si une catégorie de dépenses est >= 1.5x la médiane des 3 mois précédents
    et > 100k FCFA. (alerte lisible côté DG/Comptable)
    """
    out: List[Alert] = []
    dm = _get_month(db, annee, mois)
    if not dm:
        return out

    # Montant du mois par catégorie
    rows = (
        db.query(FactDepensesMensuelles.categorie_id,
                 func.coalesce(func.sum(FactDepensesMensuelles.montant), 0))
        .filter(FactDepensesMensuelles.month_id == dm.id)
        .group_by(FactDepensesMensuelles.categorie_id).all()
    )
    if not rows:
        return out

    # 3 mois précédents
    prev = db.query(DimMonth.id).filter(
        (DimMonth.year < dm.year) |
        ((DimMonth.year == dm.year) & (DimMonth.month < dm.month))
    ).order_by(DimMonth.year.desc(), DimMonth.month.desc()).limit(3).all()
    prev_ids = [x[0] for x in prev]

    import statistics
    med_cache: Dict[int, float] = {}
    if prev_ids:
        hist = (
            db.query(FactDepensesMensuelles.categorie_id,
                     FactDepensesMensuelles.montant)
            .filter(FactDepensesMensuelles.month_id.in_(prev_ids))
            .all()
        )
        buckets: Dict[int, List[float]] = {}
        for cid, m in hist:
            buckets.setdefault(cid, []).append(_sum_decimal(m))
        for cid, serie in buckets.items():
            if serie:
                med_cache[cid] = statistics.median(serie)

    # Compose alertes
    for cid, cur_m in rows:
        cur = _sum_decimal(cur_m)
        med = med_cache.get(cid, 0.0)
        if cur >= max(100000.0, med * 1.5):
            sev = Severity.warning if cur < med * 2.5 else Severity.critical
            out.append(Alert(
                severity=sev,
                status=AlertStatus.open,
                audience=Audience.both,
                title="Dépenses élevées",
                body=f"Catégorie #{cid} : {cur:,.0f} FCFA vs médiane 3m ≈ {med:,.0f}.",
                month_id=dm.id,
                entity_type="categorie",
                entity_name=str(cid),
                source_rule="RECO_DEPENSES",
            ))
    return out


def reco_marge_faible(db: Session, annee: int, mois: str) -> List[Alert]:
    """
    Alerte lisible si marge% < 8%.
    """
    out: List[Alert] = []
    dm = _get_month(db, annee, mois)
    if not dm:
        return out

    rows = (
        db.query(DimProduit.name, FactMargeProduitMensuelle.marge_pct)
        .join(DimProduit, DimProduit.id == FactMargeProduitMensuelle.produit_id)
        .filter(FactMargeProduitMensuelle.month_id == dm.id).all()
    )
    for prod, pct in rows:
        v = _sum_decimal(pct)
        if v < 8.0:
            out.append(Alert(
                severity=Severity.warning,
                status=AlertStatus.open,
                audience=Audience.dg,
                title=f"Marge faible : {prod}",
                body=f"Marge {v:.1f}% (< 8%).",
                month_id=dm.id,
                entity_type="produit",
                entity_name=prod,
                source_rule="RECO_MARGE",
            ))
    return out


def reco_tresorerie_basse(db: Session, annee: int, mois: str) -> List[Alert]:
    """
    Alerte si solde fin banque + caisse < seuil.
    """
    out: List[Alert] = []
    dm = _get_month(db, annee, mois)
    if not dm:
        return out

    bank_sf = (
        db.query(func.coalesce(func.sum(FactBanqueMensuelle.solde_fin), 0))
        .filter(FactBanqueMensuelle.month_id == dm.id).scalar()
    )
    cash_sf = (
        db.query(func.coalesce(func.sum(FactCaisseMensuelle.solde_fin), 0))
        .filter(FactCaisseMensuelle.month_id == dm.id).scalar()
    )
    total = _sum_decimal(bank_sf) + _sum_decimal(cash_sf)
    if total < 500_000:  # seuil ajustable
        out.append(Alert(
            severity=Severity.warning,
            status=AlertStatus.open,
            audience=Audience.dg,
            title="Trésorerie basse",
            body=f"Solde fin cumulé ≈ {total:,.0f} FCFA.",
            month_id=dm.id,
            entity_type="tresorerie",
            entity_name=None,
            source_rule="RECO_TREASURY",
        ))
    return out


def generate_alerts(db: Session, annee: int, mois: str) -> List[Alert]:
    """
    Regroupe toutes les reco/alertes 'métier'.
    """
    alerts: List[Alert] = []
    alerts.extend(reco_reappro_stock(db, annee, mois))
    alerts.extend(reco_depenses_surchauffe(db, annee, mois))
    alerts.extend(reco_marge_faible(db, annee, mois))
    alerts.extend(reco_tresorerie_basse(db, annee, mois))
    return alerts
