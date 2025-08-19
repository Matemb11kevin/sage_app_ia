# app/services/ingest_service.py
"""
Étape 2 : Ingestion & Validation (staging)
- Lecture Excel
- Normalisation d'en-têtes (via specs)
- Validation colonnes requises / valeurs autorisées
- Prévisualisation normalisée (quelques lignes)
- (+) Déduplication par hash (si colonne file_hash disponible côté DB)
"""

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import os
import hashlib
import pandas as pd

from app.services.specs import (
    FileType,
    normalize_headers,
    validate_columns,
    validate_allowed_values,
    guess_file_type_by_headers,
)

# ---------- Modèle de rapport renvoyé à l'API ----------
@dataclass
class IngestReport:
    ok: bool
    inferred_type: Optional[str]
    declared_type: Optional[str]
    errors: List[str]
    canonical_headers: Dict[str, str]
    missing_columns: List[str]
    normalized_preview: List[Dict]  # premières lignes après normalisation
    rows_count: int

    # (+) infos dédup
    content_hash: Optional[str] = None
    duplicate_of_id: Optional[int] = None       # id du fichier existant s'il y a doublon
    dedup_enabled: bool = False                  # True si la colonne file_hash est présente en DB

    def dict(self):
        return asdict(self)


# ---------- API principale : prévisualiser / valider un fichier ----------
def preview_file(
    file_path: str,
    *,
    declared_type: Optional[str],
    mois: Optional[str],
    annee: Optional[int],
    preview_rows: int = 5,
    db=None,  # optionnel : si fourni, on peut tester la dédup côté DB
) -> IngestReport:
    df = _read_excel(file_path)
    if df is None or df.empty:
        return IngestReport(
            ok=False,
            inferred_type=None,
            declared_type=declared_type,
            errors=["Fichier vide ou non lisible."],
            canonical_headers={},
            missing_columns=[],
            normalized_preview=[],
            rows_count=0,
        )

    # 1) détection type
    headers = list(df.columns)
    inferred = guess_file_type_by_headers(headers)
    inferred_str = inferred.value if inferred else None
    file_type = _resolve_file_type(declared_type, inferred)

    # 2) normaliser les en-têtes
    canon_map = normalize_headers(headers, file_type)
    df_norm = df.rename(columns=canon_map)

    # 3) valider colonnes requises
    ok, col_errors = validate_columns(list(canon_map.values()), file_type)

    # 4) valeurs autorisées (échantillon)
    values_ok, values_errors = validate_allowed_values(
        rows=df_norm.to_dict("records"),
        file_type=file_type,
        sample_limit=50,
    )

    all_errors = []
    if not ok:
        all_errors.extend(col_errors)
    if not values_ok:
        all_errors.extend(values_errors)

    # 5) colonnes manquantes (si erreurs colonnes)
    missing = _missing_required(list(canon_map.values()), file_type)

    # 6) preview normalisée
    preview_cols = _columns_of_interest(file_type)
    preview_df = df_norm[[c for c in preview_cols if c in df_norm.columns]].head(preview_rows)
    preview_records = preview_df.to_dict("records")

    # 7) hash contenu + dédup (si DB fournie et colonne file_hash existante)
    content_hash = compute_sha256(file_path)
    dedup_enabled = False
    duplicate_of_id = None
    if db is not None and mois and annee:
        dedup_enabled, duplicate_of_id = _check_duplicate_in_db(
            db=db,
            declared_type=file_type.value if file_type else None,
            mois=str(mois),
            annee=int(annee),
            content_hash=content_hash,
        )

    return IngestReport(
        ok=(ok and values_ok),
        inferred_type=inferred_str,
        declared_type=file_type.value if file_type else None,
        errors=all_errors,
        canonical_headers=canon_map,
        missing_columns=missing,
        normalized_preview=preview_records,
        rows_count=len(df),
        content_hash=content_hash,
        duplicate_of_id=duplicate_of_id,
        dedup_enabled=dedup_enabled,
    )


# ---------- Helpers lecture/validation ----------
def _read_excel(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_excel(path, engine="openpyxl")
        # Retire colonnes totalement vides
        df = df.loc[:, ~df.columns.astype(str).str.match(r"^Unnamed")]
        return df
    except Exception:
        return None


def _resolve_file_type(declared: Optional[str], inferred: Optional[FileType]) -> FileType:
    if declared:
        try:
            return FileType(declared)
        except Exception:
            pass
    if inferred:
        return inferred
    return FileType.VENTES_JOURNALIERES


def _missing_required(canon_headers: List[str], file_type: FileType) -> List[str]:
    from app.services.specs import SPECS
    required = set(SPECS[file_type].required)
    have = set(canon_headers)
    missing = [c for c in required if c not in have]
    return missing


def _columns_of_interest(file_type: FileType) -> List[str]:
    if file_type == FileType.STOCK_JOURNALIER:
        return ["date","produit","stock_initial","reception","vente","pertes","regul_scdp","stock_final"]
    if file_type == FileType.VENTES_JOURNALIERES:
        return ["date","produit","quantite","prix_unitaire","ca"]
    if file_type == FileType.ACHATS_JOURNALIERS:
        return ["date","produit","quantite","cout_unitaire","cout_total"]
    if file_type == FileType.DEPENSES_MENSUELLES:
        return ["categorie","montant"]
    if file_type == FileType.MARGE_PRODUITS_MENSUELLE:
        return ["produit","ca","cogs","marge","marge_pct"]
    if file_type == FileType.SITUATION_CLIENTS_MENSUELLE:
        return ["client","encours_debut","facture","regle","encours_fin"]
    if file_type == FileType.TRANSACTIONS_BANCAIRES_MENSUELLES:
        return ["banque","solde_debut","encaissements","decaissements","solde_fin"]
    if file_type == FileType.SOLDE_CAISSE_MENSUELLE:
        return ["caisse","solde_debut","encaissements","decaissements","solde_fin"]
    return []


# ---------- Dédup par hash ----------
def compute_sha256(path: str, chunk_size: int = 1 << 20) -> Optional[str]:
    """Calcule le SHA-256 d'un fichier (hex)."""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _check_duplicate_in_db(db, declared_type: Optional[str], mois: str, annee: int, content_hash: Optional[str]) -> Tuple[bool, Optional[int]]:
    """
    Retourne (dedup_enabled, duplicate_of_id).
    - dedup_enabled=True si la colonne file_hash existe dans la table fichiers_excel.
    - duplicate_of_id = id d'un fichier identique déjà traité (même (type, mois, année, hash)).
    """
    if not content_hash:
        return (False, None)

    # Import local pour éviter couplage fort
    from app.models.excel_model import ExcelFile  # type: ignore

    # La colonne file_hash peut ne pas exister (schéma ancien).
    if not hasattr(ExcelFile, "file_hash"):
        return (False, None)

    # Cherche un fichier identique (même triplet + hash)
    existing = (
        db.query(ExcelFile)
        .filter(
            ExcelFile.type_fichier == (declared_type or ""),
            ExcelFile.mois == mois,
            ExcelFile.annee == annee,
            ExcelFile.file_hash == content_hash,
        )
        .order_by(ExcelFile.id.asc())
        .first()
    )
    return (True, existing.id if existing else None)
