# backend/tests/test_dedup.py
import io
import pandas as pd
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _xlsx_bytes():
    df = pd.DataFrame([
        {"Date": "2025-08-01", "Produit": "Super", "Quantité": 100, "Prix unitaire": 800},
        {"Date": "2025-08-02", "Produit": "Super", "Quantité": 110, "Prix unitaire": 800},
    ])
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="openpyxl") as w:
        df.to_excel(w, index=False)
    bio.seek(0)
    return bio.getvalue()

def test_dedup_same_file_twice():
    params = {"type_fichier": "ventes_journalieres", "mois": "aout", "annee": "2025"}
    files = {
        "files": ("Ventes.xlsx", _xlsx_bytes(),
                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    }

    r1 = client.post("/upload-excel", data=params, files=files)
    assert r1.status_code in (200, 201)

    r2 = client.post("/upload-excel", data=params, files=files)
    assert r2.status_code == 409
