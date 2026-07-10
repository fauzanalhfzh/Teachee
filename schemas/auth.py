import enum
import re
from pydantic import BaseModel, ConfigDict, field_validator
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
    avatar: Optional[str] = None

    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', v):
            raise ValueError("Invalid email format")
        return v.lower()

class UserLogin(BaseModel):
    email: str
    password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

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
