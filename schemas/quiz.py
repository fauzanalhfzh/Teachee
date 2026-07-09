from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from schemas.question import QuestionResponse

class QuizStatus:
    DRAFT = "draft"
    PUBLISHED = "published"

class QuizGenerateRequest(BaseModel):
    classroom_id: UUID
    topic: str
    num_questions: int = Field(default=5, ge=1, le=50)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1)

class QuizUpdateRequest(BaseModel):
    topic: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=1)

class QuizListItem(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    topic: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class QuizResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    topic: str
    status: str
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    questions: List[QuestionResponse] = []

    model_config = ConfigDict(from_attributes=True)

class QuizPublishResponse(BaseModel):
    id: UUID
    status: str

    model_config = ConfigDict(from_attributes=True)
