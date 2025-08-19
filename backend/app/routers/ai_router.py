# app/routers/ai_router.py
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.connection import get_db
from app.security import get_current_user
from app.models.ai import Anomaly, Alert, Severity, AlertStatus
from app.models.warehouse import (
    DimMonth, DimDate, DimProduit,
    FactVentesJournalieres, FactMargeProduitMensuelle,
    FactDepensesMensuelles, FactBanqueMensuelle, FactCaisseMensuelle
)
from app.services.ai_service import run_analysis
from app.services.ai_rules import MONTHS, _get_month

router = APIRouter(prefix="/ai", tags=["IA - Anomalies & Alertes"])

# --------- Utils ---------
def _role_value(u) -> str:
    r = getattr(u, "role", None)
    return getattr(r, "value", r) or ""

class AnalyzeRequest(BaseModel):
    mois: str
    annee: int
    type_fichier: Optional[str] = None

# --------- Analyse ---------
@router.post("/analyze")
def analyze(
    body: Optional[AnalyzeRequest] = Body(None, description="Alternative JSON: {mois, annee, type_fichier?}"),
    mois: Optional[str] = Query(None),
    annee: Optional[int] = Query(None),
    type_fichier: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _role_value(current_user).lower()
    if role != "comptable":
        raise HTTPException(status_code=403, detail="Analyse réservée au rôle Comptable")

    if body is not None:
        mois_in, annee_in, type_in = body.mois, body.annee, body.type_fichier or type_fichier
    else:
        if not (mois and annee):
            raise HTTPException(status_code=400, detail="Fournir mois+annee (JSON ou query).")
        mois_in, annee_in, type_in = mois, annee, type_fichier

    if MONTHS.get(str(mois_in).strip().lower()) is None:
        raise HTTPException(status_code=400, detail="Paramètre 'mois' invalide.")

    try:
        result = run_analysis(db, annee=annee_in, mois=mois_in, type_fichier=type_in)
    except TypeError:
        result = run_analysis(db, annee=annee_in, mois=mois_in)
    return result


# --------- KPI / Résumé ---------
@router.get("/summary")
def kpi_summary(
    mois: str = Query(...),
    annee: int = Query(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Renvoie un petit résumé : CA total, marge% globale, top catégories de dépenses,
    solde banque + caisse, et un mini-serie ventes/jour (tous produits).
    """
    dm = _get_month(db, annee, mois)
    if not dm:
        raise HTTPException(status_code=400, detail="Mois invalide")

    # CA total (ventes)
    ca_total = (
        db.query(func.coalesce(func.sum(FactVentesJournalieres.ca), 0))
        .join(DimDate, DimDate.id == FactVentesJournalieres.date_id)
        .filter(DimDate.year == dm.year, DimDate.month == dm.month)
        .scalar()
    ) or 0

    # Marge% globale (pondérée par CA)
    tot_ca = (
        db.query(func.coalesce(func.sum(FactMargeProduitMensuelle.ca), 0))
        .filter(FactMargeProduitMensuelle.month_id == dm.id).scalar()
    ) or 0
    tot_marge = (
        db.query(func.coalesce(func.sum(FactMargeProduitMensuelle.marge), 0))
        .filter(FactMargeProduitMensuelle.month_id == dm.id).scalar()
    ) or 0
    marge_pct = (float(tot_marge) / float(tot_ca) * 100.0) if float(tot_ca) > 0 else None

    # Dépenses top 5 catégories
    dep_rows = (
        db.query(FactDepensesMensuelles.categorie_id,
                 func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).label("mnt"))
        .filter(FactDepensesMensuelles.month_id == dm.id)
        .group_by(FactDepensesMensuelles.categorie_id)
        .order_by(func.coalesce(func.sum(FactDepensesMensuelles.montant), 0).desc())
        .limit(5).all()
    )
    depenses_top = [{"categorie_id": cid, "montant": float(mnt)} for cid, mnt in dep_rows]

    # Trésorerie fin de mois
    bank_fin = (
        db.query(func.coalesce(func.sum(FactBanqueMensuelle.solde_fin), 0))
        .filter(FactBanqueMensuelle.month_id == dm.id).scalar()
    ) or 0
    cash_fin = (
        db.query(func.coalesce(func.sum(FactCaisseMensuelle.solde_fin), 0))
        .filter(FactCaisseMensuelle.month_id == dm.id).scalar()
    ) or 0

    # Série ventes/jour (CA total par jour)
    series_rows = (
        db.query(DimDate.date, func.coalesce(func.sum(FactVentesJournalieres.ca), 0))
        .join(FactVentesJournalieres, FactVentesJournalieres.date_id == DimDate.id)
        .filter(DimDate.year == dm.year, DimDate.month == dm.month)
        .group_by(DimDate.date).order_by(DimDate.date).all()
    )
    ventes_jour = [{"date": d.isoformat(), "ca": float(v)} for d, v in series_rows]

    return {
        "mois": mois,
        "annee": annee,
        "ca_total": float(ca_total),
        "marge_pct": float(marge_pct) if marge_pct is not None else None,
        "depenses_top": depenses_top,
        "tresorerie_fin": {"banque": float(bank_fin), "caisse": float(cash_fin)},
        "ventes_par_jour": ventes_jour,
    }


# --------- Listing anomalies ---------
@router.get("/anomalies")
def list_anomalies(
    mois: str = Query(...),
    annee: int = Query(...),
    type: Optional[str] = Query(None, description="ventes, stock, depenses, marge, banque, caisse, clients"),
    severity: Optional[str] = Query(None, description="info|warning|critical"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dm = _get_month(db, annee, mois)
    if not dm:
        return []

    q = db.query(Anomaly)
    if severity:
        try:
            q = q.filter(Anomaly.severity == Severity(severity))
        except Exception:
            pass
    if type:
        q = q.filter(Anomaly.type == type)

    anomalies = q.all()

    from app.models.warehouse import DimDate
    ids_month = [dm.id]
    def _match_month(a: Anomaly) -> bool:
        if a.month_id and a.month_id in ids_month:
            return True
        if a.date_id:
            d = db.query(DimDate).filter(DimDate.id == a.date_id).first()
            return (d and d.year == dm.year and d.month == dm.month)
        return False

    out = [a for a in anomalies if _match_month(a)]
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda x: (order.get(getattr(x.severity, "name", str(x.severity)), 9), x.id))

    return [
        {
            "id": a.id,
            "created_at": a.created_at,
            "type": a.type.value if hasattr(a.type, "value") else str(a.type),
            "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
            "object_type": a.object_type,
            "object_name": a.object_name,
            "message": a.message,
            "metric": a.metric,
            "value": str(a.value) if a.value is not None else None,
            "threshold": str(a.threshold) if a.threshold is not None else None,
        }
        for a in out
    ]


# --------- Listing alertes ---------
@router.get("/alerts")
def list_alerts(
    mois: str = Query(...), annee: int = Query(...),
    status: Optional[str] = Query(None, description="open|ack|closed"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    dm = _get_month(db, annee, mois)
    if not dm:
        return []
    q = db.query(Alert).filter(Alert.month_id == dm.id)
    if status:
        try:
            q = q.filter(Alert.status == AlertStatus(status))
        except Exception:
            pass
    q = q.order_by(Alert.severity.desc(), Alert.id.desc())
    lst = q.all()
    return [
        {
            "id": a.id,
            "created_at": a.created_at,
            "severity": a.severity.value if hasattr(a.severity, "value") else str(a.severity),
            "status": a.status.value if hasattr(a.status, "value") else str(a.status),
            "title": a.title,
            "body": a.body,
            "source_rule": a.source_rule,
        } for a in lst
    ]


# --------- Acknowledge / Close ---------
@router.post("/alerts/{alert_id}/ack")
def ack_alert(alert_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    a.status = AlertStatus.ack
    db.commit()
    return {"message": "Alerte marquée comme lue."}

@router.post("/alerts/{alert_id}/close")
def close_alert(alert_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    a = db.query(Alert).filter(Alert.id == alert_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    a.status = AlertStatus.closed
    db.commit()
    return {"message": "Alerte clôturée."}

# --- AJOUT : résumé analytique du mois (lecture DG/Comptable/Membre) ---
from fastapi import Query
from app.services.ai_summary import compute_month_summary

def _can_read_analysis(u) -> bool:
    # Rôles autorisés à voir les résumés/anomalies
    r = getattr(u, "role", None)
    val = getattr(r, "value", r) or ""
    return str(val).lower() in {"comptable", "dg", "membre", "utilisateur", "user", "admin"}

@router.get("/summary")
def month_summary(
    mois: str = Query(...),
    annee: int = Query(...),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if not _can_read_analysis(current_user):
        # lecture autorisée à DG / Comptable / Membres
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Accès réservé (DG/Comptable/Membres).")

    return compute_month_summary(db, annee=annee, mois=mois)
