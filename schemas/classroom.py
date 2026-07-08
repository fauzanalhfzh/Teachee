from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import List, Optional
from datetime import datetime

class StudentInClassroom(BaseModel):
    id: UUID
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)

class ClassroomCreate(BaseModel):
    name: str
    teacher_id: UUID

class ClassroomUpdate(BaseModel):
    name: Optional[str] = None
    teacher_id: Optional[UUID] = None

class EnrollStudentRequest(BaseModel):
    student_id: UUID

class ClassroomResponse(BaseModel):
    id: UUID
    name: str
    teacher_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ClassroomDetailResponse(BaseModel):
    id: UUID
    name: str
    teacher_id: UUID
    teacher_name: str
    created_at: datetime
    updated_at: datetime
    students: List[StudentInClassroom] = []

    model_config = ConfigDict(from_attributes=True)
