# app/database/connection.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from dotenv import load_dotenv
import os

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

# Récupérer la DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Créer le moteur de connexion SQLAlchemy
engine = create_engine(DATABASE_URL)

# Créer une session locale pour interagir avec la DB
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base commune pour tous les modèles SQLAlchemy
Base = declarative_base()

# ✅ Fonction pour obtenir une session DB (utilisée dans les dépendances FastAPI)
def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
