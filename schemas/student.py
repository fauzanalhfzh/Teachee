from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import List, Optional
from datetime import datetime

class StudentQuestionResponse(BaseModel):
    id: UUID
    quiz_id: UUID
    question_text: str
    options: List[str]

    model_config = ConfigDict(from_attributes=True)

class StudentQuizTakeResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    topic: str
    created_at: datetime
    updated_at: datetime
    questions: List[StudentQuestionResponse]

    model_config = ConfigDict(from_attributes=True)

class StudentAnswerInput(BaseModel):
    question_id: UUID
    selected_answer: str

class QuizSubmitRequest(BaseModel):
    answers: List[StudentAnswerInput]

class QuestionCorrectionDetail(BaseModel):
    question_id: UUID
    question_text: str
    options: List[str]
    selected_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None

class QuizSubmitResponse(BaseModel):
    attempt_id: UUID
    score: float
    results: List[QuestionCorrectionDetail]

    model_config = ConfigDict(from_attributes=True)

class ActiveQuizResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    classroom_name: str
    teacher_id: UUID
    topic: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CompletedQuizResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    classroom_name: str
    teacher_id: UUID
    topic: str
    score: float
    attempted_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentQuizListResponse(BaseModel):
    active: List[ActiveQuizResponse]
    completed: List[CompletedQuizResponse]
