# backend/scripts/init_db.py
import os
from app.database.connection import engine, Base  # Base = declarative_base() utilisé par tes modèles
from app.models import excel_model, warehouse, ai  # importe TOUS les modules qui déclarent des tables

def main():
    print("Creating tables on:", os.getenv("DATABASE_URL"))
    Base.metadata.create_all(bind=engine)
    print("Done.")

if __name__ == "__main__":
    main()
