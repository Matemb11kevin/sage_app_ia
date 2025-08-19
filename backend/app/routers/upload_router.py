# app/routers/upload_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Form, Query
from typing import List, Optional
from sqlalchemy.orm import Session
import shutil
import os
import uuid

from app.database.connection import get_db
from app.security import get_current_user  # role_required n'est plus utilisé pour DELETE
from app.models.excel_model import ExcelFile, DonneeExcel
from app.schemas.excel_file import ExcelFileResponse
from app.services.ingest_service import preview_file
from app.services.load_service import load_from_path  # <-- utilisé sur /load-excel/{id}
from app.services.ingest_service import compute_sha256  # <-- [HASH] on l'importe ici

router = APIRouter(tags=["Upload fichiers Excel"])

UPLOAD_DIR = "uploaded_excels"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _role_value(u) -> str:
    r = getattr(u, "role", None)
    if hasattr(r, "value"):
        return str(r.value)
    return str(r or "")


@router.post("/upload-excel", summary="Uploader un ou plusieurs fichiers Excel")
async def upload_excel_files(
    type_fichier: str = Form(...),
    mois: str = Form(...),
    annee: int = Form(...),
    files: List[UploadFile] = File(...),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="Aucun fichier reçu.")

    last_record = None

    for file in files:
        if not file.filename.lower().endswith(".xlsx"):
            raise HTTPException(
                status_code=400,
                detail=f"❌ Seuls les fichiers .xlsx sont autorisés (fichier invalide : {file.filename})."
            )

        # 1) Sauvegarde physique
        stored_name = f"{uuid.uuid4()}_{file.filename}"
        saved_path = os.path.join(UPLOAD_DIR, stored_name)
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 2) [HASH] Calculer le hash du fichier enregistré
        content_hash = compute_sha256(saved_path)

        # 3) [DEDUP CHECK] Vérifier s'il existe déjà un fichier identique
        dup = db.query(ExcelFile).filter(
            ExcelFile.type_fichier == type_fichier,
            ExcelFile.mois == mois,
            ExcelFile.annee == annee,
            ExcelFile.file_hash == content_hash
        ).first()

        if dup:
            # Option : supprimer le fichier fraîchement écrit
            try:
                os.remove(saved_path)
            except Exception:
                pass
            raise HTTPException(
                status_code=409,
                detail=f"Fichier identique déjà traité (id={dup.id}) pour {type_fichier} {mois}/{annee}."
            )

        # 4) Enregistrer la ligne ExcelFile en BDD
        excel_record = ExcelFile(
            filename=file.filename,
            nom_stocke=stored_name,
            uploaded_by=getattr(current_user, "email", getattr(current_user, "username", "inconnu")),
            type_fichier=type_fichier,
            mois=mois,
            annee=annee,
            file_hash=content_hash,  # <-- [SAVE HASH]
        )
        db.add(excel_record)
        last_record = excel_record

    db.commit()
    if last_record:
        db.refresh(last_record)

    return {"message": "✅ Fichier(s) uploadé(s) et enregistré(s) avec succès."}


@router.get(
    "/excel-files",
    response_model=List[ExcelFileResponse],
    summary="Lister les fichiers Excel (filtrable)"
)
def list_excel_files(
    type_fichier: Optional[str] = Query(None),
    mois: Optional[str] = Query(None),
    annee: Optional[int] = Query(None),
    mine: bool = Query(False, description="Ne retourner que MES fichiers"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ExcelFile)
    if type_fichier:
        q = q.filter(ExcelFile.type_fichier == type_fichier)
    if mois:
        q = q.filter(ExcelFile.mois == mois)
    if annee:
        q = q.filter(ExcelFile.annee == annee)
    if mine:
        q = q.filter(ExcelFile.uploaded_by == getattr(current_user, "email", None))
    return q.order_by(ExcelFile.id.desc()).all()


@router.get("/validate-excel/{fichier_id}", summary="Valider la structure d’un fichier uploadé")
def validate_excel_file(
    fichier_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = _role_value(current_user).lower()
    if role != "comptable":
        raise HTTPException(status_code=403, detail="Validation réservée au rôle Comptable")

    fichier = db.query(ExcelFile).filter(ExcelFile.id == fichier_id).first()
    if not fichier:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    path = os.path.join(UPLOAD_DIR, fichier.nom_stocke)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier physique manquant sur le serveur")

    report = preview_file(
        path,
        declared_type=fichier.type_fichier,
        mois=fichier.mois,
        annee=fichier.annee,
    )
    return report.dict()


@router.post("/load-excel/{fichier_id}", summary="Charger (ETL) un fichier uploadé vers le datawarehouse")
def load_excel_file(
    fichier_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = _role_value(current_user).lower()
    if role != "comptable":
        raise HTTPException(status_code=403, detail="Chargement réservé au rôle Comptable")

    fichier = db.query(ExcelFile).filter(ExcelFile.id == fichier_id).first()
    if not fichier:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    path = os.path.join(UPLOAD_DIR, fichier.nom_stocke)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Fichier physique manquant sur le serveur")

    result = load_from_path(db, fichier, path)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Échec chargement"))

    return result


@router.delete("/delete-excel/{fichier_id}", summary="Supprimer un fichier Excel")
def delete_excel_file(
    fichier_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    role = _role_value(current_user).lower()
    if role != "comptable":
        raise HTTPException(status_code=403, detail="Suppression réservée au rôle Comptable")

    fichier = db.query(ExcelFile).filter(ExcelFile.id == fichier_id).first()
    if not fichier:
        raise HTTPException(status_code=404, detail="Fichier introuvable")

    if fichier.nom_stocke:
        path = os.path.join(UPLOAD_DIR, fichier.nom_stocke)
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    db.query(DonneeExcel).filter(DonneeExcel.fichier_id == fichier.id).delete()
    db.delete(fichier)
    db.commit()

    return {"message": f"🗑️ Fichier '{fichier.filename}' supprimé avec succès."}
