# app/create_tables.py
from app.database.connection import engine, Base
from app.models import user
from app.models.upload import UploadedData

print("📦 Création des tables...")

# Création de toutes les tables définies dans les modèles
Base.metadata.create_all(bind=engine)

print("✅ Tables créées avec succès !")
