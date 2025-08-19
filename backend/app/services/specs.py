# app/services/specs.py
"""
Contrats de données (spécifications Excel) + utilitaires:
- Normalisation des en-têtes (accents/casse/espaces)
- Synonymes -> noms canoniques
- Spécifications par type (required, one_of, dtypes, allowed_values)
- Helpers: normalize_headers, validate_columns, dtypes_for, allowed_values_for
- Compat: validate_allowed_values(...) accepte 2 styles d'appel (df,filetype) OU (rows=..., file_type=...)
- Détection: guess_file_type_by_headers(headers)
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Tuple, Optional, Set, Any
import re
import unicodedata

# ---------------------------------------------------------
# Types de fichiers (alignés avec le front)
# ---------------------------------------------------------
class FileType(str, Enum):
    DEPENSES_MENSUELLES = "depenses_mensuelles"
    VENTES_JOURNALIERES = "ventes_journalieres"
    ACHATS_JOURNALIERS = "achats_journaliers"
    SITUATION_CLIENTS_MENSUELLE = "situation_clients_mensuelle"
    MARGE_PRODUITS_MENSUELLE = "marge_produits_mensuelle"
    STOCK_JOURNALIER = "stock_journalier"
    TRANSACTIONS_BANCAIRES_MENSUELLES = "transactions_bancaires_mensuelles"
    SOLDE_CAISSE_MENSUELLE = "solde_caisse_mensuelle"

# ---------------------------------------------------------
# Normalisation d'en-têtes
# ---------------------------------------------------------
def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def canonicalize_header(h: str) -> str:
    if h is None:
        return ""
    s = _strip_accents(str(h)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    s = re.sub(r"\s+", "_", s)
    return s

# ---------------------------------------------------------
# Synonymes
# ---------------------------------------------------------
COMMON_SYNONYMS: Dict[str, str] = {
    # généraux
    "dates": "date",
    "jour": "date",
    "journee": "date",
    "produits": "produit",
    "article": "produit",
    "articles": "produit",
    "client": "client",
    "clients": "client",
    "banque": "banque",
    "banques": "banque",
    "site": "site",
    "point_de_vente": "site",
    "pdv": "site",
    "caisse": "site",  # ✅ compat: tu utilises parfois "caisse" pour la table solde caisse

    # quantités / montants
    "quantite": "quantite",
    "quantites": "quantite",
    "qte": "quantite",
    "qt": "quantite",
    "prix": "prix_unitaire",
    "prixu": "prix_unitaire",
    "prix_unitaire_fcfa": "prix_unitaire",
    "prix_unt": "prix_unitaire",
    "montant": "montant",
    "montants": "montant",
    "total": "ca",
    "recette": "ca",
    "chiffre_affaires": "ca",
    "chiffre_d_affaires": "ca",
    "ca_total": "ca",
    "cout_unitaire": "cout_unitaire",
    "cout_unit": "cout_unitaire",
    "cump": "cout_unitaire",
    "cout_total": "cout_total",
    "cout": "cout_total",

    # stocks
    "si": "stock_initial",
    "stock_init": "stock_initial",
    "initial": "stock_initial",
    "entree": "reception",
    "entrees": "reception",
    "receptions": "reception",
    "sortie": "vente",
    "sorties": "vente",
    "ventes": "vente",
    "perte": "pertes",
    "ajustement": "regul_scdp",
    "ajustements": "regul_scdp",
    "regul": "regul_scdp",
    "sf": "stock_final",
    "stock_fin": "stock_final",

    # banques / caisse
    "solde_debut": "solde_debut",
    "solde_initial": "solde_debut",
    "solde_fin": "solde_fin",
    "encaissement": "encaissements",
    "credits": "encaissements",
    "credit": "encaissements",
    "debit": "decaissements",
    "debits": "decaissements",
    "decaissement": "decaissements",

    # clients
    "solde_client_debut": "encours_debut",
    "encours_debut_mois": "encours_debut",
    "factures": "facture",
    "facturation": "facture",
    "reglement": "regle",
    "reglements": "regle",
    "paiement": "regle",
    "paiements": "regle",

    # marge
    "cout_revient": "cogs",
    "cogs": "cogs",
    "marge_pourcent": "marge_pct",
    "marge_%": "marge_pct",
}

TYPE_SYNONYMS: Dict[FileType, Dict[str, str]] = {
    FileType.VENTES_JOURNALIERES: {
        "chiffre_affaire": "ca",
        "ventes_total": "ca",
    },
    FileType.ACHATS_JOURNALIERS: {
        "cout": "cout_total",
        "prix_achat": "cout_unitaire",
    },
    FileType.STOCK_JOURNALIER: {
        "ajust": "regul_scdp",
        "regularisation": "regul_scdp",
    },
    FileType.DEPENSES_MENSUELLES: {
        "categorie_depense": "categorie",
        "rubrique": "categorie",
        "libelle": "categorie",
        "montant_fcfa": "montant",
    },
    FileType.MARGE_PRODUITS_MENSUELLE: {
        "marge_percent": "marge_pct",
    },
}

def _synonyms_for(filetype: FileType) -> Dict[str, str]:
    m = dict(COMMON_SYNONYMS)
    m.update(TYPE_SYNONYMS.get(filetype, {}))
    return m

# ---------------------------------------------------------
# Spécifications par type
# ---------------------------------------------------------
PRODUCTS = ["super", "gasoil", "petrole", "gaz_butane", "lubrifiants", "gaz_bouteille"]
EXPENSE_CATEGORIES = [
    "transport_et_logistique",
    "entretien_equipements",
    "frais_de_personnel",
    "autres_achats",
    "services_exterieures",
    "droit_timbre_enregistrement",
    "manquant_perte_coulage",
]

SPECS: Dict[FileType, Dict[str, object]] = {
    FileType.DEPENSES_MENSUELLES: {
        "required": {"categorie", "montant"},
        "one_of": [],
        "dtypes": {"categorie": "string", "montant": "number"},
        "allowed_values": {"categorie": set(EXPENSE_CATEGORIES)},
    },
    FileType.VENTES_JOURNALIERES: {
        "required": {"date", "produit", "quantite"},
        "one_of": [{"prix_unitaire", "ca"}],
        "dtypes": {
            "date": "date", "produit": "string", "quantite": "number",
            "prix_unitaire": "number", "ca": "number",
        },
        "allowed_values": {"produit": set(PRODUCTS)},
    },
    FileType.ACHATS_JOURNALIERS: {
        "required": {"date", "produit", "quantite"},
        "one_of": [{"cout_unitaire", "cout_total"}],
        "dtypes": {
            "date": "date", "produit": "string", "quantite": "number",
            "cout_unitaire": "number", "cout_total": "number",
        },
        "allowed_values": {"produit": set(PRODUCTS)},
    },
    FileType.SITUATION_CLIENTS_MENSUELLE: {
        "required": {"client", "encours_debut", "facture", "regle", "encours_fin"},
        "one_of": [],
        "dtypes": {
            "client": "string", "encours_debut": "number", "facture": "number",
            "regle": "number", "encours_fin": "number",
        },
    },
    FileType.MARGE_PRODUITS_MENSUELLE: {
        "required": {"produit", "ca"},
        "one_of": [{"cogs", "marge"}],
        "dtypes": {
            "produit": "string", "ca": "number", "cogs": "number",
            "marge": "number", "marge_pct": "number",
        },
        "allowed_values": {"produit": set(PRODUCTS)},
    },
    FileType.STOCK_JOURNALIER: {
        "required": {
            "date", "produit", "stock_initial", "reception",
            "vente", "pertes", "regul_scdp", "stock_final",
        },
        "one_of": [],
        "dtypes": {
            "date": "date", "produit": "string", "stock_initial": "number",
            "reception": "number", "vente": "number", "pertes": "number",
            "regul_scdp": "number", "stock_final": "number",
        },
        "allowed_values": {"produit": set(PRODUCTS)},
    },
    FileType.TRANSACTIONS_BANCAIRES_MENSUELLES: {
        "required": {"banque", "solde_debut", "encaissements", "decaissements", "solde_fin"},
        "one_of": [],
        "dtypes": {
            "banque": "string", "solde_debut": "number", "encaissements": "number",
            "decaissements": "number", "solde_fin": "number",
        },
    },
    FileType.SOLDE_CAISSE_MENSUELLE: {
        "required": {"site", "solde_debut", "encaissements", "decaissements", "solde_fin"},
        "one_of": [],
        "dtypes": {
            "site": "string", "solde_debut": "number", "encaissements": "number",
            "decaissements": "number", "solde_fin": "number",
        },
    },
}

# ---------------------------------------------------------
# API normalisation + validation (colonnes)
# ---------------------------------------------------------
def normalize_headers(headers: List[str], filetype: FileType) -> Dict[str, str]:
    syn = _synonyms_for(filetype)
    out: Dict[str, str] = {}
    for h in headers:
        can = canonicalize_header(h)
        can = syn.get(can, can)
        if can in {"prix", "prix_unitaire_fcfa"}:
            can = "prix_unitaire"
        out[h] = can
    return out

def expected_columns(filetype: FileType) -> Tuple[Set[str], List[Set[str]]]:
    spec = SPECS[filetype]
    return set(spec["required"]), list(spec.get("one_of", []))

def validate_columns(canonical_headers: List[str], filetype: FileType) -> Tuple[bool, List[str]]:
    have = set(canonical_headers)
    req, groups = expected_columns(filetype)
    errors: List[str] = []
    missing = sorted(list(req - have))
    if missing:
        errors.append(f"Colonnes obligatoires manquantes: {', '.join(missing)}")
    for g in groups:
        if not (have & g):
            errors.append("Au moins une des colonnes requises doit être présente: " + " OU ".join(sorted(g)))
    return (len(errors) == 0), errors

def dtypes_for(filetype: FileType) -> Dict[str, str]:
    return dict(SPECS[filetype].get("dtypes", {}))

def allowed_values_for(filetype: FileType, column: str) -> Optional[Set[str]]:
    allow = SPECS[filetype].get("allowed_values", {})
    if not isinstance(allow, dict):
        return None
    vals = allow.get(column)
    return set(vals) if vals else None

# ---------------------------------------------------------
# Compat: validate_allowed_values (2 styles d'appel supportés)
# ---------------------------------------------------------
def _to_records(df_or_rows: Any) -> List[Dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore
        if hasattr(df_or_rows, "to_dict"):
            return df_or_rows.to_dict(orient="records")  # DataFrame
    except Exception:
        pass
    if isinstance(df_or_rows, list):
        return [dict(r) if isinstance(r, dict) else r for r in df_or_rows]
    return []

def _canon_value(v: Any) -> str:
    if v is None:
        return ""
    return canonicalize_header(str(v))

def validate_allowed_values(
    df_or_rows: Any = None,
    filetype: Optional[FileType] = None,
    *,
    rows: Optional[List[Dict[str, Any]]] = None,
    file_type: Optional[FileType] = None,
    sample_limit: Optional[int] = None,
) -> Tuple[bool, List[str]]:
    """
    Style A: validate_allowed_values(df, FileType.VENTES_JOURNALIERES)
    Style B: validate_allowed_values(rows=[...], file_type=FileType.VENTES_JOURNALIERES, sample_limit=50)
    """
    ft = filetype or file_type
    if ft is None:
        return True, []

    allow_raw = SPECS[ft].get("allowed_values", {})
    if not allow_raw:
        return True, []

    allow_map: Dict[str, Set[str]] = {col: {_canon_value(v) for v in vals} for col, vals in allow_raw.items()}

    recs: List[Dict[str, Any]] = rows if rows is not None else _to_records(df_or_rows)
    if not recs:
        return True, []

    if sample_limit and sample_limit > 0:
        recs = recs[: sample_limit]

    errors: List[str] = []
    for col, allowed in allow_map.items():
        invalid: Set[str] = set()
        for r in recs:
            if col not in r:
                continue
            vcanon = _canon_value(r.get(col))
            if vcanon and vcanon not in allowed:
                invalid.add(str(r.get(col)))
        if invalid:
            sample = ", ".join(sorted(list(invalid))[:10])
            more = "" if len(invalid) <= 10 else f" (+{len(invalid)-10} autres)"
            errors.append(f"Valeurs non reconnues pour '{col}': {sample}{more}. Attendu: {sorted(list(allowed))}")

    return (len(errors) == 0), errors

# ---------------------------------------------------------
# Détection auto du type par en-têtes
# ---------------------------------------------------------
def guess_file_type_by_headers(headers: List[str]) -> Optional[FileType]:
    if not headers:
        return None
    raw = [canonicalize_header(h) for h in headers]

    best: Optional[FileType] = None
    best_score: Tuple[int, int, int, int] = (-1, -1, -1, 0)

    for ft in FileType:
        syn = _synonyms_for(ft)
        mapped = {syn.get(h, h) for h in raw}
        req, groups = expected_columns(ft)

        required_hits = len(req & mapped)
        missing_required = len(req - mapped)
        one_of_ok = sum(1 for g in groups if mapped & g)

        scope = set(req)
        for g in groups:
            scope |= set(g)
        total_hits = len(scope & mapped)

        score = (one_of_ok, required_hits, total_hits, -missing_required)
        if score > best_score:
            best_score, best = score, ft

    if best is not None:
        syn = _synonyms_for(best)
        mapped = {syn.get(h, h) for h in raw}
        req, _ = expected_columns(best)
        if len(req & mapped) == 0:
            return None
    return best
