# app/models/user.py

from sqlalchemy import Column, String, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from app.database.connection import Base  # <-- utilisation du Base centralisé
import uuid
import enum

# Enum pour les rôles utilisateurs
class UserRole(enum.Enum):
    DG = "DG"
    Comptable = "Comptable"
    Membre = "Membre"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    is_default_password = Column(Boolean, default=True)
