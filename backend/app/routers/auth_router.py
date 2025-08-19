# app/routers/auth_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
import smtplib, ssl
from email.message import EmailMessage
import os

from app.database.connection import get_db
from app.models.user import User
from app.security import (
    verify_password,
    create_access_token,
    get_current_user,
    role_required,
    create_reset_token,
    decode_token,
    get_password_hash,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentification"])

# ---------- Login ----------
@auth_router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    identifier = form_data.username.strip()
    user = (
        db.query(User)
        .filter((User.username == identifier) | (User.email == identifier))
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utilisateur introuvable")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Mot de passe incorrect")

    token = create_access_token(
        {
            "uid": str(user.id),
            "sub": user.username,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        }
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        },
    }

# ---------- Forgot Password ----------
class ResetRequest(BaseModel):
    email: EmailStr

@auth_router.post("/request-reset")
def request_reset(body: ResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        # Pour ne pas divulguer les comptes existants, on retourne 200 même si inconnu
        return {"message": "Si l'email existe, un lien a été envoyé."}

    token = create_reset_token(str(user.id), minutes=30)

    # lien vers ta page frontend
    frontend_base = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")
    link = f"{frontend_base}/reset-password?token={token}"

    # envoi email
    _send_email(
        to=body.email,
        subject="Réinitialisation de votre mot de passe",
        html=f"""
        <p>Bonjour,</p>
        <p>Pour réinitialiser votre mot de passe, cliquez sur le lien ci-dessous :</p>
        <p><a href="{link}">Réinitialiser mon mot de passe</a></p>
        <p>Ce lien expire dans 30 minutes.</p>
        """,
    )
    return {"message": "Email envoyé (si l'adresse existe)."}

class ResetConfirm(BaseModel):
    token: str
    new_password: str

@auth_router.post("/confirm-reset")
def confirm_reset(body: ResetConfirm, db: Session = Depends(get_db)):
    # vérifier token
    try:
        payload = decode_token(body.token)
        if payload.get("purpose") != "reset":
            raise ValueError("Mauvais token")
        uid = payload.get("uid")
        if not uid:
            raise ValueError("Token invalide")
    except Exception:
        raise HTTPException(status_code=400, detail="Lien invalide ou expiré")

    user = db.query(User).filter(User.id == uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    # changer le mot de passe
    user.hashed_password = get_password_hash(body.new_password)
    user.is_default_password = False
    db.commit()

    return {"message": "Mot de passe mis à jour avec succès."}

# ---------- Info utilisateur / route protégée ----------
@auth_router.get("/me")
def get_me(current_user=Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role),
    }

@auth_router.get("/admin-only")
def admin_only(current_user=Depends(role_required("DG"))):
    return {"message": "Bienvenue Directeur Général 🧠"}

# ---------- util ----------
def _send_email(to: str, subject: str, html: str):
    host = os.getenv("EMAIL_HOST")
    port = int(os.getenv("EMAIL_PORT", "465"))
    user = os.getenv("EMAIL_USERNAME")
    pwd = os.getenv("EMAIL_PASSWORD")

    if not all([host, port, user, pwd]):
        # En dev: log seulement
        print("⚠️  SMTP non configuré. Contenu email :")
        print("To:", to)
        print("Subject:", subject)
        print("HTML:", html)
        return

    msg = EmailMessage()
    msg["From"] = user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content("Version texte")
    msg.add_alternative(html, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(user, pwd)
        server.send_message(msg)
