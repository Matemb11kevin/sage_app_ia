# app/models/excel_model.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database.connection import Base


class ExcelFile(Base):
    """
    Modèle pour stocker les informations sur les fichiers Excel téléchargés.
    """
    __tablename__ = "fichiers_excel"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)          # nom original
    nom_stocke = Column(String, nullable=False)        # nom physique stocké (UUID_nom.xlsx)
    uploaded_by = Column(String, nullable=False)       # email ou username de l'uploader
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    type_fichier = Column(String, nullable=False)      # dép..., ventes..., etc.
    mois = Column(String, nullable=False)              # janvier, février, ...
    annee = Column(Integer, nullable=True)             # 2025, 2026, ...

    # ✅ AJOUT : hash de contenu pour la déduplication
    file_hash = Column(String(64), nullable=True, index=True)

    # Relation avec les données extraites
    donnees = relationship("DonneeExcel", back_populates="fichier", cascade="all, delete-orphan")


class DonneeExcel(Base):
    """
    Modèle pour stocker les données extraites des fichiers Excel.
    Chaque ligne de données correspond à une ligne dans le fichier.
    """
    __tablename__ = "donnees_excel"

    id = Column(Integer, primary_key=True, index=True)
    fichier_id = Column(Integer, ForeignKey("fichiers_excel.id"), nullable=False)
    colonne1 = Column(String)
    colonne2 = Column(String)
    colonne3 = Column(String)
    colonne4 = Column(String)

    # Lien vers le fichier parent
    fichier = relationship("ExcelFile", back_populates="donnees")
