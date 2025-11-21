from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    id: str
    email: Optional[str] = None
    name: Optional[str] = None

class UserInDB(User):
    hashed_password: str