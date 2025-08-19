# app/routers/upload.py

from fastapi import APIRouter, File, UploadFile, Depends, HTTPException, status
from typing import List
from app.security import get_current_user, role_required
import os

router = APIRouter(
    prefix="/upload",
    tags=["Upload"]
)

UPLOAD_DIR = "uploaded_files"

# Crée le dossier s’il n’existe pas
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

@router.post("/excel-files", summary="Uploader plusieurs fichiers Excel")
def upload_excel_files(
    files: List[UploadFile] = File(...),
    current_user=Depends(role_required("DG", "Comptable"))
):
    accepted_extensions = [".xls", ".xlsx"]
    uploaded = []

    for file in files:
        filename = file.filename
        ext = os.path.splitext(filename)[1]
        if ext not in accepted_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Fichier non autorisé : {filename}. Seuls les fichiers Excel sont acceptés."
            )

        destination = os.path.join(UPLOAD_DIR, filename)
        with open(destination, "wb") as buffer:
            buffer.write(file.file.read())
        uploaded.append(filename)

    return {
        "message": f"{len(uploaded)} fichier(s) Excel téléversé(s) avec succès.",
        "fichiers": uploaded
    }
