import enum
from pydantic import BaseModel, ConfigDict, EmailStr
from uuid import UUID
from typing import Optional
from datetime import datetime

class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"

class UserRegister(BaseModel):
    name: str
    email: str # Not using EmailStr to avoid needing email-validator package, keeping it simple as in other schemas
    password: str
    role: UserRole
    avatar: Optional[str] = None

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserMeResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: UserRole
    avatar: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
