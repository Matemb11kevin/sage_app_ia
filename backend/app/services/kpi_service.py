# app/services/kpi_service.py
from __future__ import annotations
from typing import Dict, Any, List, Tuple
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.warehouse import (
    DimDate, DimMonth, DimProduit, DimCategorieDepense,
    FactVentesJournalieres, FactDepensesMensuelles,
    FactMargeProduitMensuelle, FactBanqueMensuelle, FactCaisseMensuelle
)
from app.services.ai_rules import MONTHS, _get_month

def _to_float(x) -> float:
    if x is None: 
        return 0.0
    if isinstance(x, Decimal):
        return float(x)
    try:
        return float(x)
    except Exception:
        return 0.0

def get_summary(db: Session, *, annee: int, mois: str) -> Dict[str, Any]:
    mois_key = str(mois).strip().lower()
    m = MONTHS.get(mois_key)
    if not m:
        return {"error": "mois invalide"}

    dm: DimMonth = _get_month(db, annee, mois_key)
    # ---------- KPI ----------
    # CA total (somme des CA jour sur le mois)
    ca_total = (
        db.query(func.coalesce(func.sum(FactVentesJournalieres.ca), 0))
        .join(DimDate, FactVentesJournalieres.date_id == DimDate.id)
        .filter(DimDate.year == annee, DimDate.month == m)
        .scalar()
    )
    ca_total = _to_float(ca_total)

    # Marge% (pondérée) si données mensuelles présentes
    s_ca = (
        db.query(func.coalesce(func.sum(FactMargeProduitMensuelle.ca), 0))
        .filter(FactMargeProduitMensuelle.month_id == dm.id)
        .scalar()
    )
    s_marge = (
        db.query(func.coalesce(func.sum(FactMargeProduitMensuelle.marge), 0))
        .filter(FactMargeProduitMensuelle.month_id == dm.id)
        .scalar()
    )
    s_ca = _to_float(s_ca)
    s_marge = _to_float(s_marge)
    marge_pct = (s_marge / s_ca * 100.0) if s_ca > 0 else None

    # Dépenses total
    depenses_total = (
        db.query(func.coalesce(func.sum(FactDepensesMensuelles.montant), 0))
        .filter(FactDepensesMensuelles.month_id == dm.id)
        .scalar()
    )
    depenses_total = _to_float(depenses_total)

    # Solde banque/caisse fin de mois (somme sur banques / unique pour caisse)
    banque_solde_fin_total = (
        db.query(func.coalesce(func.sum(FactBanqueMensuelle.solde_fin), 0))
        .filter(FactBanqueMensuelle.month_id == dm.id)
        .scalar()
    )
    banque_solde_fin_total = _to_float(banque_solde_fin_total)

    caisse_solde_fin_total = (
        db.query(func.coalesce(func.sum(FactCaisseMensuelle.solde_fin), 0))
        .filter(FactCaisseMensuelle.month_id == dm.id)
        .scalar()
    )
    caisse_solde_fin_total = _to_float(caisse_solde_fin_total)

    # ---------- Séries légères ----------
    # Sparkline ventes (CA par jour)
    ventes_jour_rows: List[Tuple] = (
        db.query(
            DimDate.date,
            func.coalesce(func.sum(FactVentesJournalieres.ca), 0).label("ca")
        )
        .join(FactVentesJournalieres, FactVentesJournalieres.date_id == DimDate.id)
        .filter(DimDate.year == annee, DimDate.month == m)
        .group_by(DimDate.date)
        .order_by(DimDate.date.asc())
        .all()
    )
    ventes_jour = [{"date": d.isoformat(), "ca": _to_float(ca)} for d, ca in ventes_jour_rows]

    # Top catégories dépenses (TOP 5)
    dep_cat_rows: List[Tuple] = (
        db.query(
            DimCategorieDepense.name,
            func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).label("mnt")
        )
        .join(DimCategorieDepense, DimCategorieDepense.id == FactDepensesMensuelles.categorie_id)
        .filter(FactDepensesMensuelles.month_id == dm.id)
        .group_by(DimCategorieDepense.name)
        .order_by(func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).desc())
        .limit(5)
        .all()
    )
    depenses_top = [{"categorie": n, "montant": _to_float(mnt)} for n, mnt in dep_cat_rows]

    # Marge par produit (si dispo)
    marge_prod_rows: List[Tuple] = (
        db.query(
            DimProduit.name,
            FactMargeProduitMensuelle.marge_pct
        )
        .join(DimProduit, DimProduit.id == FactMargeProduitMensuelle.produit_id)
        .filter(FactMargeProduitMensuelle.month_id == dm.id)
        .all()
    )
    marge_par_produit = [
        {"produit": p, "marge_pct": _to_float(pct) if pct is not None else None}
        for p, pct in marge_prod_rows
    ]

    return {
        "period": {"mois": mois_key, "annee": annee},
        "kpi": {
            "ca_total": ca_total,
            "marge_pct": marge_pct,
            "depenses_total": depenses_total,
            "banque_solde_fin_total": banque_solde_fin_total,
            "caisse_solde_fin_total": caisse_solde_fin_total,
        },
        "series": {
            "ventes_jour": ventes_jour,           # [{date, ca}]
            "depenses_top": depenses_top,         # [{categorie, montant}]
            "marge_par_produit": marge_par_produit, # [{produit, marge_pct}]
        },
    }
