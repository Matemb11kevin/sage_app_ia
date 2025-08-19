# app/models/upload.py
from sqlalchemy import Column, Integer, String, Float, Date
from app.database.connection import Base

class UploadedData(Base):
    __tablename__ = "uploaded_data"

    id = Column(Integer, primary_key=True, index=True)
    nom = Column(String, nullable=False)
    valeur = Column(Float, nullable=False)
    date = Column(Date, nullable=False)
