from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ExcelFileResponse(BaseModel):
    # ✅ Pydantic v2 : lecture depuis objets SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    type_fichier: str
    mois: str
    annee: int
    uploaded_by: Optional[str] = None
    upload_date: Optional[datetime] = None
