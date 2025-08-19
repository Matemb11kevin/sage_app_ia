# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Shim compat Pydantic v2 (ne rien changer, juste présent pour éviter les warnings v2)
from app.utils import pydantic_compat  # noqa: F401

from app.database.connection import Base, engine

# Routers existants
from app.routers.auth_router import auth_router
from app.routers.upload_router import router as upload_router

# 🔽 Routers ajoutés (ETL + IA)
from app.routers.etl_router import router as etl_router
from app.routers.ai_router import router as ai_router

# ⚠️ Importer tous les modèles AVANT Base.metadata.create_all
from app.models import excel_model, user  # tables users + fichiers_excel
from app.models import warehouse, ai      # modèle étoile + anomalies/alertes

app = FastAPI(
    title="SAGE App IA",
    description="Backend FastAPI pour la gestion SAGE + IA",
    version="1.0.0",
)

# CORS (local). En prod: remplace par ton domaine front exact.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Création automatique des tables après import des modèles
Base.metadata.create_all(bind=engine)

# Enregistrement des routers
app.include_router(auth_router)
app.include_router(upload_router)
app.include_router(etl_router)  # /etl/load-month
app.include_router(ai_router)   # /ai/analyze, /ai/anomalies, /ai/alerts...

@app.get("/")
def read_root():
    """Ping simple + test de connexion DB."""
    try:
        with engine.connect() as _:
            return {"message": "Connexion à PostgreSQL réussie ✅"}
    except Exception as e:
        return {"error": str(e)}

# (Optionnel) endpoint de santé technique pour load balancer/monitoring
@app.get("/health")
def health():
    return {"status": "ok"}
