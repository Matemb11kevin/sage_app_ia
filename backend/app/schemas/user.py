from pydantic import BaseModel, EmailStr, ConfigDict
from enum import Enum

class UserRole(str, Enum):
    DG = "DG"
    Comptable = "Comptable"
    Membre = "Membre"

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    # ✅ Pydantic v2 : remplace Config/orm_mode par ConfigDict(from_attributes=True)
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: EmailStr
    role: UserRole
