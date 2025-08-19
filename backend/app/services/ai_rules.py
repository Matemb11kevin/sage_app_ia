# app/services/ai_rules.py
from __future__ import annotations
from typing import List, Dict, Optional, Tuple
from decimal import Decimal
from statistics import mean, pstdev

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.warehouse import (
    DimDate, DimMonth, DimProduit, DimClient, DimBanque, DimCategorieDepense,
    FactVentesJournalieres, FactAchatsJournaliers, FactStockJournalier,
    FactDepensesMensuelles, FactMargeProduitMensuelle, FactClientsMensuelle,
    FactBanqueMensuelle, FactCaisseMensuelle
)
from app.models.ai import Anomaly, Severity, AnomalyType

# -------- util --------

MONTHS = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "décembre": 12, "decembre": 12,
}

def _get_month(db: Session, annee: int, mois_str: str) -> Optional[DimMonth]:
    m = MONTHS.get(str(mois_str).strip().lower())
    if not m:
        return None
    dm = db.query(DimMonth).filter(DimMonth.year == annee, DimMonth.month == m).first()
    if not dm:
        dm = DimMonth(year=annee, month=m)
        db.add(dm); db.flush()
    return dm

# -------- RÈGLES --------
# Chaque fonction renvoie list[Anomaly] (non commit)

def anomalies_ventes(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Pic/Chute anormale des quantités vendues par produit (z-score sur le mois).
    Règle: |z| >= 3  OU variation jour/jour >= 40%.
    """
    out: List[Anomaly] = []
    m = MONTHS.get(str(mois_str).strip().lower())
    if not m:
        return out

    rows = (
        db.query(DimDate.date, DimProduit.name, FactVentesJournalieres.quantite, DimDate.id)
        .join(FactVentesJournalieres, FactVentesJournalieres.date_id == DimDate.id)
        .join(DimProduit, FactVentesJournalieres.produit_id == DimProduit.id)
        .filter(DimDate.year == annee, DimDate.month == m)
        .order_by(DimProduit.name, DimDate.date)
        .all()
    )
    if not rows:
        return out

    # Regroupe par produit
    by_prod: Dict[str, List[Tuple]] = {}
    for d, prod, qte, date_id in rows:
        by_prod.setdefault(prod, []).append((d, float(Decimal(qte or 0)), date_id))

    for prod, series in by_prod.items():
        values = [v for _, v, _ in series if v is not None]
        if len(values) < 3:
            continue
        mu = mean(values)
        sigma = pstdev(values) if len(values) > 1 else 0.0

        prev_v: Optional[float] = None
        for d, v, date_id in series:
            z = (v - mu) / sigma if sigma > 0 else 0.0
            big_change = False
            if prev_v is not None and prev_v > 0:
                delta = abs(v - prev_v) / prev_v
                big_change = delta >= 0.4
            prev_v = v

            if abs(z) >= 3.0 or big_change:
                sev = Severity.critical if abs(z) >= 3.0 else Severity.warning
                msg = f"Ventes {prod} le {d.isoformat()} inhabituelles (z={z:.2f})."
                out.append(Anomaly(
                    type=AnomalyType.ventes,
                    severity=sev,
                    object_type="produit",
                    object_name=prod,
                    date_id=date_id,
                    metric="zscore_quantite",
                    value=Decimal(f"{z:.4f}"),
                    threshold=Decimal("3.0"),
                    message=msg,
                ))
    return out


def anomalies_depenses(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Dépenses d'une catégorie anormalement élevées vs médiane 12 derniers mois (si dispo).
    Règle: montant >= médiane*1.6 ET >= 100_000 (seuil fixe modifiable).
    """
    out: List[Anomaly] = []
    dm = _get_month(db, annee, mois_str)
    if not dm:
        return out

    # montant par catégorie ce mois
    cur = (
        db.query(DimCategorieDepense.name, func.coalesce(func.sum(FactDepensesMensuelles.montant), 0))
        .join(DimCategorieDepense, FactDepensesMensuelles.categorie_id == DimCategorieDepense.id)
        .filter(FactDepensesMensuelles.month_id == dm.id)
        .group_by(DimCategorieDepense.name)
        .all()
    )
    if not cur:
        return out

    # historique 12 mois glissants (si présent)
    hist = {}
    prev_months = db.query(DimMonth.id).filter(
        (DimMonth.year < dm.year) |
        ((DimMonth.year == dm.year) & (DimMonth.month < dm.month))
    ).order_by(DimMonth.year.desc(), DimMonth.month.desc()).limit(12).all()
    prev_ids = [x[0] for x in prev_months]

    if prev_ids:
        rows = (
            db.query(DimCategorieDepense.name, FactDepensesMensuelles.montant, FactDepensesMensuelles.month_id)
            .join(DimCategorieDepense, FactDepensesMensuelles.categorie_id == DimCategorieDepense.id)
            .filter(FactDepensesMensuelles.month_id.in_(prev_ids))
            .all()
        )
        for name, mnt, mid in rows:
            hist.setdefault(name, []).append(float(Decimal(mnt or 0)))

    import statistics
    for cat, montant in cur:
        cur_val = float(Decimal(montant or 0))
        serie = hist.get(cat, [])
        med = statistics.median(serie) if serie else 0.0
        trigger = (cur_val >= max(100000.0, med * 1.6))  # seuils ajustables
        if trigger:
            out.append(Anomaly(
                type=AnomalyType.depenses,
                severity=Severity.warning if cur_val < med * 2.5 else Severity.critical,
                object_type="categorie",
                object_name=cat,
                month_id=dm.id,
                metric="depense_vs_median_12m",
                value=Decimal(f"{cur_val:.2f}"),
                threshold=Decimal(f"{(med*1.6):.2f}"),
                message=f"Dépenses '{cat}' élevées ce mois (val={cur_val:.0f}, ref≈{med:.0f})."
            ))
    return out


def anomalies_stock(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Contrôle cohérence: SI + réception − vente − pertes − régul ≈ SF
    Tolérance: max(1% du flux total, 1.0).
    """
    out: List[Anomaly] = []
    m = MONTHS.get(str(mois_str).strip().lower())
    if not m:
        return out

    rows = (
        db.query(
            DimDate.id, DimDate.date, DimProduit.name,
            FactStockJournalier.stock_initial, FactStockJournalier.reception,
            FactStockJournalier.vente, FactStockJournalier.pertes,
            FactStockJournalier.regul_scdp, FactStockJournalier.stock_final
        )
        .join(FactStockJournalier, FactStockJournalier.date_id == DimDate.id)
        .join(DimProduit, FactStockJournalier.produit_id == DimProduit.id)
        .filter(DimDate.year == annee, DimDate.month == m)
        .all()
    )
    for date_id, d, prod, si, rec, ven, per, reg, sf in rows:
        si, rec, ven, per, reg, sf = [float(Decimal(x or 0)) for x in (si, rec, ven, per, reg, sf)]
        theo = si + rec - ven - per - reg
        ecart = abs(theo - sf)
        tol = max(abs(theo) * 0.01, 1.0)
        if ecart > tol:
            out.append(Anomaly(
                type=AnomalyType.stock,
                severity=Severity.critical if ecart > tol * 2 else Severity.warning,
                object_type="produit",
                object_name=prod,
                date_id=date_id,
                metric="stock_equation_gap",
                value=Decimal(f"{ecart:.3f}"),
                threshold=Decimal(f"{tol:.3f}"),
                message=f"Incohérence stock {prod} le {d.isoformat()} (écart {ecart:.2f} > tol {tol:.2f})."
            ))
    return out


def anomalies_marge(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Marge% trop faible (< 8%) ou chute > 5 points vs médiane 6 mois.
    """
    out: List[Anomaly] = []
    dm = _get_month(db, annee, mois_str)
    if not dm:
        return out

    rows = (
        db.query(DimProduit.name, FactMargeProduitMensuelle.marge_pct)
        .join(DimProduit, FactMargeProduitMensuelle.produit_id == DimProduit.id)
        .filter(FactMargeProduitMensuelle.month_id == dm.id)
        .all()
    )
    if not rows:
        return out

    # historique 6 mois
    prev_ids = [x[0] for x in db.query(DimMonth.id).filter(
        (DimMonth.year < dm.year) |
        ((DimMonth.year == dm.year) & (DimMonth.month < dm.month))
    ).order_by(DimMonth.year.desc(), DimMonth.month.desc()).limit(6).all()]

    hist = {}
    if prev_ids:
        r2 = (
            db.query(DimProduit.name, FactMargeProduitMensuelle.marge_pct)
            .join(DimProduit, FactMargeProduitMensuelle.produit_id == DimProduit.id)
            .filter(FactMargeProduitMensuelle.month_id.in_(prev_ids))
            .all()
        )
        for prod, pct in r2:
            if pct is None:
                continue
            hist.setdefault(prod, []).append(float(Decimal(pct)))

    import statistics
    for prod, pct in rows:
        cur = float(Decimal(pct or 0))
        med = statistics.median(hist.get(prod, [cur]))
        low = cur < 8.0
        drop = (med - cur) >= 5.0
        if low or drop:
            out.append(Anomaly(
                type=AnomalyType.marge,
                severity=Severity.warning if low else Severity.info,
                object_type="produit",
                object_name=prod,
                month_id=dm.id,
                metric="marge_pct",
                value=Decimal(f"{cur:.2f}"),
                threshold=Decimal("8.0"),
                message=f"Marge {prod} faible ({cur:.1f}%) vs réf {med:.1f}%."
            ))
    return out


def anomalies_banque_caisse(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Réconciliation banque/caisse: SD + enc - déc doit = SF (tolérance 1 000).
    """
    out: List[Anomaly] = []
    dm = _get_month(db, annee, mois_str)
    if not dm:
        return out

    # Banque
    rows_b = (
        db.query(DimBanque.name, FactBanqueMensuelle.solde_debut,
                 FactBanqueMensuelle.encaissements, FactBanqueMensuelle.decaissements,
                 FactBanqueMensuelle.solde_fin)
        .join(DimBanque, FactBanqueMensuelle.banque_id == DimBanque.id)
        .filter(FactBanqueMensuelle.month_id == dm.id)
        .all()
    )
    for bank, sd, enc, dec, sf in rows_b:
        sd, enc, dec, sf = [float(Decimal(x or 0)) for x in (sd, enc, dec, sf)]
        theo = sd + enc - dec
        ecart = abs(theo - sf)
        if ecart > 1000.0:
            out.append(Anomaly(
                type=AnomalyType.banque,
                severity=Severity.warning if ecart < 10000 else Severity.critical,
                object_type="banque",
                object_name=bank,
                month_id=dm.id,
                metric="reconcile_ecart",
                value=Decimal(f"{ecart:.2f}"),
                threshold=Decimal("1000"),
                message=f"Réconciliation banque '{bank}' : écart {ecart:.0f}."
            ))

    # Caisse
    rows_c = (
        db.query(FactCaisseMensuelle.solde_debut,
                 FactCaisseMensuelle.encaissements, FactCaisseMensuelle.decaissements,
                 FactCaisseMensuelle.solde_fin)
        .filter(FactCaisseMensuelle.month_id == dm.id)
        .all()
    )
    for sd, enc, dec, sf in rows_c:
        sd, enc, dec, sf = [float(Decimal(x or 0)) for x in (sd, enc, dec, sf)]
        theo = sd + enc - dec
        ecart = abs(theo - sf)
        if ecart > 1000.0:
            out.append(Anomaly(
                type=AnomalyType.caisse,
                severity=Severity.warning if ecart < 10000 else Severity.critical,
                object_type="caisse",
                object_name="caisse",
                month_id=dm.id,
                metric="reconcile_ecart",
                value=Decimal(f"{ecart:.2f}"),
                threshold=Decimal("1000"),
                message=f"Réconciliation caisse : écart {ecart:.0f}."
            ))
    return out


def anomalies_clients(db: Session, annee: int, mois_str: str) -> List[Anomaly]:
    """
    Encours_fin ≈ Encours_debut + Facture - Réglé (tolérance 1 000).
    """
    out: List[Anomaly] = []
    dm = _get_month(db, annee, mois_str)
    if not dm:
        return out

    rows = (
        db.query(DimClient.name, FactClientsMensuelle.encours_debut,
                 FactClientsMensuelle.facture, FactClientsMensuelle.regle,
                 FactClientsMensuelle.encours_fin)
        .join(DimClient, FactClientsMensuelle.client_id == DimClient.id)
        .filter(FactClientsMensuelle.month_id == dm.id)
        .all()
    )
    for client, ed, fa, rg, ef in rows:
        ed, fa, rg, ef = [float(Decimal(x or 0)) for x in (ed, fa, rg, ef)]
        theo = ed + fa - rg
        ecart = abs(theo - ef)
        if ecart > 1000.0:
            out.append(Anomaly(
                type=AnomalyType.clients,
                severity=Severity.warning if ecart < 10000 else Severity.critical,
                object_type="client",
                object_name=client,
                month_id=dm.id,
                metric="reconcile_ecart",
                value=Decimal(f"{ecart:.2f}"),
                threshold=Decimal("1000"),
                message=f"Incohérence client '{client}' : écart {ecart:.0f}."
            ))
    return out
