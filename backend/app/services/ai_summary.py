# app/services/ai_summary.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.warehouse import (
    DimDate, DimMonth, DimProduit, DimCategorieDepense, DimBanque, DimClient,
    FactVentesJournalieres, FactDepensesMensuelles, FactMargeProduitMensuelle,
    FactStockJournalier, FactBanqueMensuelle, FactCaisseMensuelle
)
from app.models.ai import Anomaly, Severity
from app.services.ai_rules import _get_month

def _to_float(x) -> float:
    if x is None:
        return 0.0
    try:
        return float(Decimal(x))
    except Exception:
        try:
            return float(x)
        except Exception:
            return 0.0

def compute_month_summary(db: Session, *, annee: int, mois: str) -> Dict[str, Any]:
    """
    Résumé analytique d'un mois :
      - KPIs : CA, Dépenses, Marge%, Coverage stock (jours), écarts banque/caisse/clients
      - TOPs : Produits par CA, Dépenses par catégorie
      - Highlights : 5 messages explicites issus des anomalies les plus importantes
    """
    dm: Optional[DimMonth] = _get_month(db, annee, mois)
    if not dm:
        return {
            "mois": mois, "annee": annee, "kpis": {}, "top": {}, "highlights": [],
            "message": "Aucun mois correspondant."
        }

    # ---------------- KPIs ----------------
    # CA (si 'ca' est nul, on approxime par quantite * prix_unitaire)
    ca_expr = func.coalesce(FactVentesJournalieres.ca,
                            FactVentesJournalieres.quantite * func.coalesce(FactVentesJournalieres.prix_unitaire, 0))
    ca_total = db.query(func.coalesce(func.sum(ca_expr), 0)) \
                 .join(DimDate, FactVentesJournalieres.date_id == DimDate.id) \
                 .filter(DimDate.year == dm.year, DimDate.month == dm.month) \
                 .scalar()

    depenses_total = db.query(func.coalesce(func.sum(FactDepensesMensuelles.montant), 0)) \
                       .filter(FactDepensesMensuelles.month_id == dm.id) \
                       .scalar()

    # Marge% globale (pondéré par CA)
    rows_marge = db.query(FactMargeProduitMensuelle.ca,
                          FactMargeProduitMensuelle.marge).filter(
        FactMargeProduitMensuelle.month_id == dm.id
    ).all()
    ca_sum = sum(_to_float(r[0]) for r in rows_marge)
    marge_sum = sum(_to_float(r[1]) for r in rows_marge)
    marge_pct = (marge_sum / ca_sum * 100.0) if ca_sum > 0 else None

    # Coverage stock (jours) = Stock_final_total_du_dernier_jour / vente_moyenne_journalière
    # 1) dernier jour du mois présent dans les ventes
    last_date = db.query(DimDate).filter(
        DimDate.year == dm.year, DimDate.month == dm.month
    ).order_by(DimDate.date.desc()).first()

    coverage_days = None
    if last_date:
        # stock final à cette date (tous produits)
        stock_final_total = db.query(func.coalesce(func.sum(FactStockJournalier.stock_final), 0)) \
            .filter(FactStockJournalier.date_id == last_date.id).scalar()

        # vente journalière moyenne (quantité) sur le mois
        vente_qte_total = db.query(func.coalesce(func.sum(FactVentesJournalieres.quantite), 0)) \
            .join(DimDate, FactVentesJournalieres.date_id == DimDate.id) \
            .filter(DimDate.year == dm.year, DimDate.month == dm.month) \
            .scalar()

        nb_jours_data = db.query(func.count(func.distinct(DimDate.date))) \
            .join(FactVentesJournalieres, FactVentesJournalieres.date_id == DimDate.id) \
            .filter(DimDate.year == dm.year, DimDate.month == dm.month) \
            .scalar()

        vente_moy_j = (vente_qte_total / nb_jours_data) if nb_jours_data else 0
        if vente_moy_j and vente_moy_j > 0:
            coverage_days = float(Decimal(stock_final_total)) / float(Decimal(vente_moy_j))

    # Réconciliations (écarts absolus agrégés)
    def _sum_abs_diff_bank() -> float:
        rows = db.query(FactBanqueMensuelle.solde_debut,
                        FactBanqueMensuelle.encaissements,
                        FactBanqueMensuelle.decaissements,
                        FactBanqueMensuelle.solde_fin) \
                 .filter(FactBanqueMensuelle.month_id == dm.id).all()
        total = 0.0
        for sd, enc, dec, sf in rows:
            theo = _to_float(sd) + _to_float(enc) - _to_float(dec)
            total += abs(theo - _to_float(sf))
        return total

    def _sum_abs_diff_caisse() -> float:
        rows = db.query(FactCaisseMensuelle.solde_debut,
                        FactCaisseMensuelle.encaissements,
                        FactCaisseMensuelle.decaissements,
                        FactCaisseMensuelle.solde_fin) \
                 .filter(FactCaisseMensuelle.month_id == dm.id).all()
        total = 0.0
        for sd, enc, dec, sf in rows:
            theo = _to_float(sd) + _to_float(enc) - _to_float(dec)
            total += abs(theo - _to_float(sf))
        return total

    def _sum_abs_diff_clients() -> float:
        rows = db.query(FactClientsMensuelle.encours_debut,
                        FactClientsMensuelle.facture,
                        FactClientsMensuelle.regle,
                        FactClientsMensuelle.encours_fin) \
                 .filter(FactClientsMensuelle.month_id == dm.id).all()
        total = 0.0
        for ed, fa, rg, ef in rows:
            theo = _to_float(ed) + _to_float(fa) - _to_float(rg)
            total += abs(theo - _to_float(ef))
        return total

    kpis = {
        "ca_total": _to_float(ca_total),
        "depenses_total": _to_float(depenses_total),
        "marge_pct": (float(round(marge_pct, 2)) if marge_pct is not None else None),
        "stock_coverage_days": (float(round(coverage_days, 1)) if coverage_days is not None else None),
        "banque_ecart_total": float(round(_sum_abs_diff_bank(), 2)),
        "caisse_ecart_total": float(round(_sum_abs_diff_caisse(), 2)),
        "clients_ecart_total": float(round(_sum_abs_diff_clients(), 2)),
    }

    # ---------------- TOPS ----------------
    # Top produits par CA
    top_produits = db.query(
        DimProduit.name.label("produit"),
        func.coalesce(func.sum(ca_expr), 0).label("ca")
    ).join(FactVentesJournalieres, FactVentesJournalieres.produit_id == DimProduit.id) \
     .join(DimDate, FactVentesJournalieres.date_id == DimDate.id) \
     .filter(DimDate.year == dm.year, DimDate.month == dm.month) \
     .group_by(DimProduit.name) \
     .order_by(func.coalesce(func.sum(ca_expr), 0).desc()) \
     .limit(5).all()

    # Top dépenses par catégorie
    top_depenses = db.query(
        DimCategorieDepense.name.label("categorie"),
        func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).label("montant")
    ).join(DimCategorieDepense, FactDepensesMensuelles.categorie_id == DimCategorieDepense.id) \
     .filter(FactDepensesMensuelles.month_id == dm.id) \
     .group_by(DimCategorieDepense.name) \
     .order_by(func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).desc()) \
     .limit(5).all()

    top = {
        "ventes_par_produit": [{"produit": p, "ca": _to_float(ca)} for (p, ca) in top_produits],
        "depenses_par_categorie": [{"categorie": c, "montant": _to_float(m)} for (c, m) in top_depenses],
    }

    # ---------------- Highlights (messages explicites) ----------------
    # On récupère les anomalies du mois, triées par sévérité
    anomalies = db.query(Anomaly).filter(
        (Anomaly.month_id == dm.id) | (Anomaly.date_id.isnot(None))
    ).order_by(Anomaly.severity.desc(), Anomaly.id.desc()).limit(50).all()

    # On filtre vraiment sur le mois si date_id est utilisé
    def _is_in_month(a: Anomaly) -> bool:
        if a.month_id == dm.id:
            return True
        if a.date_id:
            d = db.query(DimDate).filter(DimDate.id == a.date_id).first()
            return bool(d and d.year == dm.year and d.month == dm.month)
        return False
    anomalies = [a for a in anomalies if _is_in_month(a)]

    # On formate 5 messages courts et parlants
    sev_label = {Severity.critical: "CRITIQUE", Severity.warning: "Avertissement", Severity.info: "Info"}
    highlights: List[str] = []
    for a in anomalies[:5]:
        lab = sev_label.get(a.severity, "Info")
        obj = f"{a.object_type} {a.object_name}" if a.object_type and a.object_name else ""
        msg = f"[{lab}] {a.type.value if hasattr(a.type, 'value') else a.type} – {obj}: {a.message}"
        highlights.append(msg)

    return {
        "mois": mois,
        "annee": annee,
        "month_id": dm.id,
        "kpis": kpis,
        "top": top,
        "highlights": highlights
    }
