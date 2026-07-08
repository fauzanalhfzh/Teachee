import enum
from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import List, Optional
from datetime import datetime
from schemas.question import QuestionResponse

class QuizStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"

class QuizGenerateRequest(BaseModel):
    classroom_id: UUID
    teacher_id: UUID
    topic: str
    num_questions: int = Field(default=5, ge=1, le=50)

class QuizResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    title: str
    subject: str
    topic: str
    status: QuizStatus
    created_at: datetime
    updated_at: datetime
    questions: List[QuestionResponse] = []

    model_config = ConfigDict(from_attributes=True)

class QuizPublishResponse(BaseModel):
    id: UUID
    status: QuizStatus

    model_config = ConfigDict(from_attributes=True)
