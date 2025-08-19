# app/models/warehouse.py
from __future__ import annotations
from sqlalchemy import (
    Column, Integer, String, Date, DateTime, ForeignKey, Numeric, Enum, Text,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database.connection import Base

# ---------------------------
# Dimensions
# ---------------------------

class DimDate(Base):
    __tablename__ = "dim_date"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, unique=True, nullable=False)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)   # 1..12
    day = Column(Integer, nullable=False)
    month_name = Column(String, nullable=True)
    weekday = Column(Integer, nullable=True)  # 0=lundi, 6=dimanche

    __table_args__ = (
        Index("ix_dim_date_date", "date"),
        Index("ix_dim_date_year_month", "year", "month"),
    )


class DimMonth(Base):
    __tablename__ = "dim_month"
    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1..12
    month_name = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("year", "month", name="uq_dim_month_year_month"),
        Index("ix_dim_month_year_month", "year", "month"),
    )


class DimProduit(Base):
    __tablename__ = "dim_produit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)  # Super, Gasoil, ...

class DimClient(Base):
    __tablename__ = "dim_client"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

class DimBanque(Base):
    __tablename__ = "dim_banque"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

class DimCategorieDepense(Base):
    __tablename__ = "dim_categorie_depense"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

class DimFichier(Base):
    __tablename__ = "dim_fichier"
    id = Column(Integer, primary_key=True, autoincrement=True)
    fichier_id = Column(Integer, ForeignKey("fichiers_excel.id"), nullable=False)  # lien ExcelFile
    type_fichier = Column(String, nullable=False)
    mois = Column(String, nullable=False)
    annee = Column(Integer, nullable=False)
    uploaded_by = Column(String, nullable=True)
    upload_date = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_dim_fichier_fichier_id", "fichier_id"),
        Index("ix_dim_fichier_type_mois_annee", "type_fichier", "mois", "annee"),
    )

# ---------------------------
# Tables de faits (journalier)
# ---------------------------

class FactVentesJournalieres(Base):
    __tablename__ = "fact_ventes_journalieres"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(Integer, ForeignKey("dim_date.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("dim_produit.id"), nullable=False)
    quantite = Column(Numeric(18, 3), nullable=False)
    prix_unitaire = Column(Numeric(18, 4), nullable=True)
    ca = Column(Numeric(18, 2), nullable=True)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_vj_date_prod", "date_id", "produit_id"),
    )


class FactAchatsJournaliers(Base):
    __tablename__ = "fact_achats_journaliers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(Integer, ForeignKey("dim_date.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("dim_produit.id"), nullable=False)
    quantite = Column(Numeric(18, 3), nullable=False)
    cout_unitaire = Column(Numeric(18, 4), nullable=True)
    cout_total = Column(Numeric(18, 2), nullable=True)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_aj_date_prod", "date_id", "produit_id"),
    )


class FactStockJournalier(Base):
    __tablename__ = "fact_stock_journalier"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date_id = Column(Integer, ForeignKey("dim_date.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("dim_produit.id"), nullable=False)
    stock_initial = Column(Numeric(18, 3), nullable=False)
    reception = Column(Numeric(18, 3), nullable=False)
    vente = Column(Numeric(18, 3), nullable=False)
    pertes = Column(Numeric(18, 3), nullable=False)
    regul_scdp = Column(Numeric(18, 3), nullable=False)
    stock_final = Column(Numeric(18, 3), nullable=False)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_sj_date_prod", "date_id", "produit_id"),
    )

# ---------------------------
# Tables de faits (mensuel)
# ---------------------------

class FactDepensesMensuelles(Base):
    __tablename__ = "fact_depenses_mensuelles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=False)
    categorie_id = Column(Integer, ForeignKey("dim_categorie_depense.id"), nullable=False)
    montant = Column(Numeric(18, 2), nullable=False)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_dep_mois_cat", "month_id", "categorie_id"),
    )


class FactMargeProduitMensuelle(Base):
    __tablename__ = "fact_marge_produit_mensuelle"
    id = Column(Integer, primary_key=True, autoincrement=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=False)
    produit_id = Column(Integer, ForeignKey("dim_produit.id"), nullable=False)
    ca = Column(Numeric(18, 2), nullable=False)
    cogs = Column(Numeric(18, 2), nullable=False)
    marge = Column(Numeric(18, 2), nullable=False)
    marge_pct = Column(Numeric(5, 2), nullable=True)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_marge_mois_prod", "month_id", "produit_id"),
    )


class FactClientsMensuelle(Base):
    __tablename__ = "fact_clients_mensuelle"
    id = Column(Integer, primary_key=True, autoincrement=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("dim_client.id"), nullable=False)
    encours_debut = Column(Numeric(18, 2), nullable=False)
    facture = Column(Numeric(18, 2), nullable=False)
    regle = Column(Numeric(18, 2), nullable=False)
    encours_fin = Column(Numeric(18, 2), nullable=False)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_clients_mois_client", "month_id", "client_id"),
    )


class FactBanqueMensuelle(Base):
    __tablename__ = "fact_banque_mensuelle"
    id = Column(Integer, primary_key=True, autoincrement=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=False)
    banque_id = Column(Integer, ForeignKey("dim_banque.id"), nullable=False)
    solde_debut = Column(Numeric(18, 2), nullable=False)
    encaissements = Column(Numeric(18, 2), nullable=False)
    decaissements = Column(Numeric(18, 2), nullable=False)
    solde_fin = Column(Numeric(18, 2), nullable=False)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_banque_mois_banque", "month_id", "banque_id"),
    )


class FactCaisseMensuelle(Base):
    __tablename__ = "fact_caisse_mensuelle"
    id = Column(Integer, primary_key=True, autoincrement=True)
    month_id = Column(Integer, ForeignKey("dim_month.id"), nullable=False)
    solde_debut = Column(Numeric(18, 2), nullable=False)
    encaissements = Column(Numeric(18, 2), nullable=False)
    decaissements = Column(Numeric(18, 2), nullable=False)
    solde_fin = Column(Numeric(18, 2), nullable=False)
    fichier_id = Column(Integer, ForeignKey("dim_fichier.id"), nullable=False)

    __table_args__ = (
        Index("ix_caisse_mois", "month_id"),
    )
