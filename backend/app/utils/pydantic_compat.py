# app/utils/pydantic_compat.py
# Compatibilité Pydantic v2 : .from_orm(...) -> .model_validate(...)
# Sans changer ton code existant.

try:
    from pydantic import BaseModel
except Exception:
    BaseModel = None

if BaseModel is not None:
    # Si from_orm n'existe pas (v2), on le fournit en le redirigeant vers model_validate.
    if not hasattr(BaseModel, "from_orm"):
        def _from_orm(cls, obj):
            # Équivalent v2 : nécessite model_config = ConfigDict(from_attributes=True) dans le schéma
            return cls.model_validate(obj)
        BaseModel.from_orm = classmethod(_from_orm)  # type: ignore[attr-defined]
