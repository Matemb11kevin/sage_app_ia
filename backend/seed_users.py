# backend/seed_users.py

from app.database.connection import SessionLocal
from app.models.user import User, UserRole
from app.security import get_password_hash

# Liste des utilisateurs à insérer
USERS_TO_SEED = [
    {
        "username": "comptable@yende.ia",
        "email": "comptable@yende.ia",  # Remplace si tu veux un autre email réel
        "password": "Compta@2025",
        "role": UserRole.Comptable,
    },
    {
        "username": "dg@yende.ia",
        "email": "dg@yende.ia",
        "password": "DG-Yende@2025",
        "role": UserRole.DG,
    },
    {
        "username": "membre@yende.ia",
        "email": "membre@yende.ia",
        "password": "YendeUser@2025",
        "role": UserRole.Membre,
    },
]

def seed_users():
    db = SessionLocal()
    try:
        for user_data in USERS_TO_SEED:
            # Vérifie si l'utilisateur existe déjà
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            if not existing_user:
                hashed_password = get_password_hash(user_data["password"])
                user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    hashed_password=hashed_password,
                    role=user_data["role"],
                    is_default_password=True  # Mot de passe par défaut
                )
                db.add(user)
                print(f"✅ Utilisateur créé : {user.username}")
            else:
                print(f"⚠️ Utilisateur déjà existant : {existing_user.username}")
        db.commit()
        print("🎯 Insertion terminée avec succès.")
    except Exception as e:
        print(f"❌ Erreur lors de l'insertion : {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
