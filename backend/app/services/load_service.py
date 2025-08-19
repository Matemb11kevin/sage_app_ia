# app/services/load_service.py
"""
ETL 'Load' (Étape 4) : charge les Excel validés vers le modèle étoile.
- Récupère les ExcelFile du mois/année (+ type optionnel)
- Lecture + normalisation d'en-têtes (via specs)
- Upsert dimensions (date, mois, produit, client, banque, catégorie, fichier)
- Insert (idempotent par fichier) des facts correspondants
- Résumé des lignes chargées par table

Idempotence : on supprime les lignes FACT existantes liées à dim_fichier.id avant de (re)charger.
"""

from __future__ import annotations
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.models.excel_model import ExcelFile
from app.models.warehouse import (
    DimDate, DimMonth, DimProduit, DimClient, DimBanque, DimCategorieDepense, DimFichier,
    FactVentesJournalieres, FactAchatsJournaliers, FactStockJournalier,
    FactDepensesMensuelles, FactMargeProduitMensuelle, FactClientsMensuelle,
    FactBanqueMensuelle, FactCaisseMensuelle
)
from app.services.specs import (
    FileType, normalize_headers, SPECS, dtypes_for, canonicalize_header
)
from app.services.ai_rules import MONTHS  # mapping "janvier" -> 1, etc.

UPLOAD_DIR = "uploaded_excels"


# -------------- Public API --------------

def load_month(db: Session, *, annee: int, mois_str: str, type_fichier: Optional[str] = None) -> Dict:
    """
    Charge tous les fichiers Excel de ce mois/année (et type si précisé).
    Retourne un résumé par table + liste des fichiers traités.
    """
    mois_key = str(mois_str).strip().lower()
    if MONTHS.get(mois_key) is None:
        raise ValueError("Paramètre 'mois' invalide (ex: 'janvier', 'fevrier', ...)")

    # 1) Récupérer les fichiers concernés
    q = db.query(ExcelFile).filter(ExcelFile.annee == annee, ExcelFile.mois == mois_key)
    if type_fichier:
        q = q.filter(ExcelFile.type_fichier == type_fichier)
    files = q.order_by(ExcelFile.id.asc()).all()

    summary = {
        "mois": mois_key,
        "annee": annee,
        "type_filter": type_fichier,
        "files_count": len(files),
        "files": [],
        "rows_loaded": {
            "ventes": 0,
            "achats": 0,
            "stock": 0,
            "depenses": 0,
            "marge": 0,
            "clients": 0,
            "banque": 0,
            "caisse": 0,
        },
        "warnings": [],
        "errors": [],
    }

    if not files:
        return summary

    # 2) Assurer DimMonth pour le mois
    dm = _get_or_create_month(db, annee, MONTHS[mois_key])

    for f in files:
        try:
            fsum = _load_one_file(db, f, dm)
            # accumulate
            for k in summary["rows_loaded"].keys():
                summary["rows_loaded"][k] += fsum["rows_loaded"].get(k, 0)
            summary["files"].append({
                "id": f.id,
                "filename": f.filename,
                "type_fichier": f.type_fichier,
                "rows_loaded": fsum["rows_loaded"],
            })
        except Exception as e:
            summary["errors"].append(f"Fichier id={f.id} '{f.filename}': {e}")

    db.commit()
    return summary


def load_from_path(db: Session, excel: ExcelFile) -> Dict:
    """
    👉 Demandé par upload_router : charge **un fichier** ExcelFile déjà enregistré.
    - Résout le mois/année à partir d'excel.mois / excel.annee
    - Crée DimFichier si besoin
    - Purge les facts liés à ce fichier puis charge
    - Commit et renvoie un résumé 'rows_loaded' pour ce fichier
    """
    if not excel:
        raise ValueError("Paramètre 'excel' manquant.")
    mois_key = str(excel.mois).strip().lower()
    if MONTHS.get(mois_key) is None:
        raise ValueError(f"Mois invalide sur le fichier (id={excel.id}): {excel.mois}")

    dm = _get_or_create_month(db, excel.annee, MONTHS[mois_key])
    result = _load_one_file(db, excel, dm)
    db.commit()
    return result


# -------------- Core par fichier --------------

def _load_one_file(db: Session, f: ExcelFile, dm: DimMonth) -> Dict:
    """
    Charge UN fichier dans les facts correspondants (idempotent).
    """
    # 1) Lire Excel
    path = os.path.join(UPLOAD_DIR, f.nom_stocke)
    df = _read_excel(path)

    # 2) Normaliser colonnes selon le type déclaré
    try:
        ft = FileType(f.type_fichier)
    except Exception:
        raise ValueError(f"type_fichier inconnu: {f.type_fichier}")

    header_map = normalize_headers(list(df.columns), ft)
    df = df.rename(columns=header_map).copy()
    df = _coerce_logical_types(df, ft)  # dates / numbers

    # 3) DimFichier (1-1 avec ExcelFile)
    dfile = db.query(DimFichier).filter(DimFichier.fichier_id == f.id).first()
    if not dfile:
        dfile = DimFichier(
            fichier_id=f.id,
            type_fichier=f.type_fichier,
            mois=f.mois,
            annee=f.annee,
            uploaded_by=f.uploaded_by,
            upload_date=f.upload_date or datetime.utcnow(),
        )
        db.add(dfile)
        db.flush()

    # 4) nettoyer les facts existants pour ce fichier (idempotence)
    _delete_existing_for_file(db, dfile.id, ft)

    # 5) charger selon le type
    loaded = {
        "ventes": 0, "achats": 0, "stock": 0, "depenses": 0,
        "marge": 0, "clients": 0, "banque": 0, "caisse": 0,
    }

    if ft == FileType.VENTES_JOURNALIERES:
        loaded["ventes"] = _load_ventes(db, df, dfile.id)
    elif ft == FileType.ACHATS_JOURNALIERS:
        loaded["achats"] = _load_achats(db, df, dfile.id)
    elif ft == FileType.STOCK_JOURNALIER:
        loaded["stock"] = _load_stock(db, df, dfile.id)
    elif ft == FileType.DEPENSES_MENSUELLES:
        loaded["depenses"] = _load_depenses(db, df, dm.id, dfile.id)
    elif ft == FileType.MARGE_PRODUITS_MENSUELLE:
        loaded["marge"] = _load_marge(db, df, dm.id, dfile.id)
    elif ft == FileType.SITUATION_CLIENTS_MENSUELLE:
        loaded["clients"] = _load_clients(db, df, dm.id, dfile.id)
    elif ft == FileType.TRANSACTIONS_BANCAIRES_MENSUELLES:
        loaded["banque"] = _load_banque(db, df, dm.id, dfile.id)
    elif ft == FileType.SOLDE_CAISSE_MENSUELLE:
        loaded["caisse"] = _load_caisse(db, df, dm.id, dfile.id)
    else:
        raise ValueError(f"Type non géré: {ft}")

    return {"rows_loaded": loaded}


# -------------- Loaders par type --------------

def _load_ventes(db: Session, df: pd.DataFrame, dim_fichier_id: int) -> int:
    need_cols = {"date", "produit", "quantite"}  # one_of prix_unitaire/ca
    for c in need_cols:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (ventes): {c}")

    rows = 0
    for _, r in df.iterrows():
        d = _to_date(r.get("date"))
        if d is None:
            continue
        dd = _get_or_create_date(db, d)
        prod_name = _canon_string(r.get("produit"))
        pid = _get_or_create_product(db, prod_name)

        qte = _to_decimal(r.get("quantite"))
        prixu = _to_decimal(r.get("prix_unitaire"))
        ca = _to_decimal(r.get("ca"))
        if ca is None and (qte is not None and prixu is not None):
            ca = (qte * prixu)

        obj = FactVentesJournalieres(
            date_id=dd.id, produit_id=pid,
            quantite=qte or Decimal("0"),
            prix_unitaire=prixu, ca=ca,
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_achats(db: Session, df: pd.DataFrame, dim_fichier_id: int) -> int:
    need_cols = {"date", "produit", "quantite"}
    for c in need_cols:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (achats): {c}")

    rows = 0
    for _, r in df.iterrows():
        d = _to_date(r.get("date"))
        if d is None:
            continue
        dd = _get_or_create_date(db, d)
        prod_name = _canon_string(r.get("produit"))
        pid = _get_or_create_product(db, prod_name)

        qte = _to_decimal(r.get("quantite"))
        coutu = _to_decimal(r.get("cout_unitaire"))
        coutt = _to_decimal(r.get("cout_total"))
        if coutt is None and (qte is not None and coutu is not None):
            coutt = qte * coutu

        obj = FactAchatsJournaliers(
            date_id=dd.id, produit_id=pid,
            quantite=qte or Decimal("0"),
            cout_unitaire=coutu, cout_total=coutt,
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_stock(db: Session, df: pd.DataFrame, dim_fichier_id: int) -> int:
    need = {"date","produit","stock_initial","reception","vente","pertes","regul_scdp","stock_final"}
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (stock): {c}")

    rows = 0
    for _, r in df.iterrows():
        d = _to_date(r.get("date"))
        if d is None:
            continue
        dd = _get_or_create_date(db, d)
        prod_name = _canon_string(r.get("produit"))
        pid = _get_or_create_product(db, prod_name)

        obj = FactStockJournalier(
            date_id=dd.id, produit_id=pid,
            stock_initial=_to_decimal(r.get("stock_initial")) or Decimal("0"),
            reception=_to_decimal(r.get("reception")) or Decimal("0"),
            vente=_to_decimal(r.get("vente")) or Decimal("0"),
            pertes=_to_decimal(r.get("pertes")) or Decimal("0"),
            regul_scdp=_to_decimal(r.get("regul_scdp")) or Decimal("0"),
            stock_final=_to_decimal(r.get("stock_final")) or Decimal("0"),
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_depenses(db: Session, df: pd.DataFrame, month_id: int, dim_fichier_id: int) -> int:
    need = {"categorie", "montant"}
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (dépenses): {c}")

    rows = 0
    for _, r in df.iterrows():
        cat = _canon_string(r.get("categorie"))
        cid = _get_or_create_depense_cat(db, cat)
        montant = _to_decimal(r.get("montant")) or Decimal("0")
        obj = FactDepensesMensuelles(
            month_id=month_id, categorie_id=cid, montant=montant,
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_marge(db: Session, df: pd.DataFrame, month_id: int, dim_fichier_id: int) -> int:
    need = {"produit", "ca"}  # + (cogs ou marge)
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (marge): {c}")

    rows = 0
    for _, r in df.iterrows():
        prod = _canon_string(r.get("produit"))
        pid = _get_or_create_product(db, prod)
        ca = _to_decimal(r.get("ca")) or Decimal("0")
        cogs = _to_decimal(r.get("cogs"))
        marge = _to_decimal(r.get("marge"))
        marge_pct = _to_decimal(r.get("marge_pct"))

        if marge is None and cogs is not None:
            marge = ca - cogs
        obj = FactMargeProduitMensuelle(
            month_id=month_id, produit_id=pid, ca=ca,
            cogs=cogs or Decimal("0"), marge=marge or Decimal("0"),
            marge_pct=marge_pct, fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_clients(db: Session, df: pd.DataFrame, month_id: int, dim_fichier_id: int) -> int:
    need = {"client","encours_debut","facture","regle","encours_fin"}
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (clients): {c}")

    rows = 0
    for _, r in df.iterrows():
        cname = _canon_string(r.get("client"))
        cid = _get_or_create_client(db, cname)
        obj = FactClientsMensuelle(
            month_id=month_id, client_id=cid,
            encours_debut=_to_decimal(r.get("encours_debut")) or Decimal("0"),
            facture=_to_decimal(r.get("facture")) or Decimal("0"),
            regle=_to_decimal(r.get("regle")) or Decimal("0"),
            encours_fin=_to_decimal(r.get("encours_fin")) or Decimal("0"),
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_banque(db: Session, df: pd.DataFrame, month_id: int, dim_fichier_id: int) -> int:
    need = {"banque","solde_debut","encaissements","decaissements","solde_fin"}
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (banque): {c}")

    rows = 0
    for _, r in df.iterrows():
        bname = _canon_string(r.get("banque"))
        bid = _get_or_create_banque(db, bname)
        obj = FactBanqueMensuelle(
            month_id=month_id, banque_id=bid,
            solde_debut=_to_decimal(r.get("solde_debut")) or Decimal("0"),
            encaissements=_to_decimal(r.get("encaissements")) or Decimal("0"),
            decaissements=_to_decimal(r.get("decaissements")) or Decimal("0"),
            solde_fin=_to_decimal(r.get("solde_fin")) or Decimal("0"),
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


def _load_caisse(db: Session, df: pd.DataFrame, month_id: int, dim_fichier_id: int) -> int:
    need = {"solde_debut","encaissements","decaissements","solde_fin"}
    for c in need:
        if c not in df.columns:
            raise ValueError(f"Colonne requise manquante (caisse): {c}")

    rows = 0
    for _, r in df.iterrows():
        obj = FactCaisseMensuelle(
            month_id=month_id,
            solde_debut=_to_decimal(r.get("solde_debut")) or Decimal("0"),
            encaissements=_to_decimal(r.get("encaissements")) or Decimal("0"),
            decaissements=_to_decimal(r.get("decaissements")) or Decimal("0"),
            solde_fin=_to_decimal(r.get("solde_fin")) or Decimal("0"),
            fichier_id=dim_fichier_id,
        )
        db.add(obj)
        rows += 1
    return rows


# -------------- Dims helpers --------------

def _get_or_create_month(db: Session, year: int, month_int: int) -> DimMonth:
    dm = db.query(DimMonth).filter(DimMonth.year == year, DimMonth.month == month_int).first()
    if not dm:
        dm = DimMonth(year=year, month=month_int)
        db.add(dm); db.flush()
    return dm

def _get_or_create_date(db: Session, d: date) -> DimDate:
    dd = db.query(DimDate).filter(DimDate.date == d).first()
    if not dd:
        dd = DimDate(
            date=d, year=d.year, month=d.month, day=d.day,
            month_name=str(d.month)
        )
        db.add(dd); db.flush()
    return dd

def _get_or_create_product(db: Session, name: str) -> int:
    name = name or "inconnu"
    p = db.query(DimProduit).filter(DimProduit.name == name).first()
    if not p:
        p = DimProduit(name=name)
        db.add(p); db.flush()
    return p.id

def _get_or_create_client(db: Session, name: str) -> int:
    name = name or "inconnu"
    c = db.query(DimClient).filter(DimClient.name == name).first()
    if not c:
        c = DimClient(name=name)
        db.add(c); db.flush()
    return c.id

def _get_or_create_banque(db: Session, name: str) -> int:
    name = name or "inconnue"
    b = db.query(DimBanque).filter(DimBanque.name == name).first()
    if not b:
        b = DimBanque(name=name)
        db.add(b); db.flush()
    return b.id

def _get_or_create_depense_cat(db: Session, name: str) -> int:
    name = name or "autres"
    c = db.query(DimCategorieDepense).filter(DimCategorieDepense.name == name).first()
    if not c:
        c = DimCategorieDepense(name=name)
        db.add(c); db.flush()
    return c.id


# -------------- Utilitaires --------------

def _read_excel(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    df = pd.read_excel(path, engine="openpyxl")
    # nettoyage simple
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")
    return df

def _coerce_logical_types(df: pd.DataFrame, ft: FileType) -> pd.DataFrame:
    kinds = dtypes_for(ft)
    out = df.copy()
    for col, kind in kinds.items():
        if col not in out.columns:
            continue
        s = out[col]
        try:
            if kind == "date":
                out[col] = pd.to_datetime(s, errors="coerce").dt.date
            elif kind == "number":
                if s.dtype == object:
                    s = s.astype(str).str.replace(",", ".", regex=False)
                out[col] = pd.to_numeric(s, errors="coerce")
            else:
                out[col] = s.astype(str).str.strip()
        except Exception:
            pass
    return out

def _to_decimal(v) -> Optional[Decimal]:
    if v is None:
        return None
    if pd.isna(v):
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None

def _to_date(v) -> Optional[date]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v, errors="coerce").date()
    except Exception:
        return None

def _canon_string(v) -> str:
    if v is None:
        return ""
    return canonicalize_header(str(v))

def _delete_existing_for_file(db: Session, dim_fichier_id: int, ft: FileType) -> None:
    stmt = None
    if ft == FileType.VENTES_JOURNALIERES:
        stmt = delete(FactVentesJournalieres).where(FactVentesJournalieres.fichier_id == dim_fichier_id)
    elif ft == FileType.ACHATS_JOURNALIERS:
        stmt = delete(FactAchatsJournaliers).where(FactAchatsJournaliers.fichier_id == dim_fichier_id)
    elif ft == FileType.STOCK_JOURNALIER:
        stmt = delete(FactStockJournalier).where(FactStockJournalier.fichier_id == dim_fichier_id)
    elif ft == FileType.DEPENSES_MENSUELLES:
        stmt = delete(FactDepensesMensuelles).where(FactDepensesMensuelles.fichier_id == dim_fichier_id)
    elif ft == FileType.MARGE_PRODUITS_MENSUELLE:
        stmt = delete(FactMargeProduitMensuelle).where(FactMargeProduitMensuelle.fichier_id == dim_fichier_id)
    elif ft == FileType.SITUATION_CLIENTS_MENSUELLE:
        stmt = delete(FactClientsMensuelle).where(FactClientsMensuelle.fichier_id == dim_fichier_id)
    elif ft == FileType.TRANSACTIONS_BANCAIRES_MENSUELLES:
        stmt = delete(FactBanqueMensuelle).where(FactBanqueMensuelle.fichier_id == dim_fichier_id)
    elif ft == FileType.SOLDE_CAISSE_MENSUELLE:
        stmt = delete(FactCaisseMensuelle).where(FactCaisseMensuelle.fichier_id == dim_fichier_id)

    if stmt is not None:
        db.execute(stmt)
