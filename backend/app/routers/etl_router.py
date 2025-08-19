# app/routers/etl_router.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.security import get_current_user
from app.services.load_service import load_month

# Option: lancer l'analyse IA automatiquement après le chargement
try:
    from app.services.ai_service import run_analysis  # déjà utilisé dans ton ai_router
except Exception:
    run_analysis = None  # fallback si non dispo

router = APIRouter(prefix="/etl", tags=["ETL"])

def _role_value(u) -> str:
    r = getattr(u, "role", None)
    return getattr(r, "value", r) or ""

@router.post("/load-month")
def etl_load_month(
    mois: str = Query(..., description="Nom du mois: janvier, fevrier, ..."),
    annee: int = Query(...),
    type_fichier: str | None = Query(None, description="Optionnel: charger un type précis seulement"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Sécurité: seul le Comptable charge
    if _role_value(current_user).lower() != "comptable":
        raise HTTPException(status_code=403, detail="Chargement réservé au rôle Comptable")

    # 1) Load (ETL)
    try:
        summary = load_month(db, annee=annee, mois_str=mois, type_fichier=type_fichier)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur ETL: {e}")

    # 2) Analyse IA automatique
    analysis_result = None
    if run_analysis is not None:
        try:
            analysis_result = run_analysis(db, annee=annee, mois=mois)
        except Exception as e:
            analysis_result = {"error": f"Analyse non exécutée: {e}"}
    else:
        analysis_result = {"note": "run_analysis indisponible (app.services.ai_service non importable)."}

    return {
        "message": "Chargement terminé.",
        "etl_summary": summary,
        "analysis": analysis_result,
    }
