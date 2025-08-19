# app/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.models.user import User
from dotenv import load_dotenv
import os

# ✅ Chargement des variables d’environnement
load_dotenv()

# 🔐 Variables sensibles
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

# 🔐 Schéma d’authentification
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def create_access_token(data: dict):
    from datetime import datetime, timedelta
    expire = datetime.utcnow() + timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    data.update({"exp": expire})
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password, hashed_password):
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Token invalide")
        user = db.query(User).filter(User.username == username).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Utilisateur introuvable")
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide")


# ✅ Décorateur de protection par rôle (facultatif)
def role_required(*roles):
    def decorator(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Accès interdit. Rôle requis: {roles}"
            )
        return current_user
    return decorator

# ℹ️ Exemple (non obligatoire) :
# from app.security import role_required
# @router.get("/dashboard-dg")
# def dashboard_dg(current_user: User = Depends(role_required("DG"))):
#     return {"message": "Bienvenue Directeur Général 🧠"}
