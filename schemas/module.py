from pydantic import BaseModel, ConfigDict, Field
from uuid import UUID
from typing import List, Optional, Any
from datetime import datetime

class ModuleSectionResponse(BaseModel):
    id: UUID
    module_id: UUID
    section_order: int
    title: str
    content: str
    image_url: Optional[str] = None
    image_prompt: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModuleExerciseResponse(BaseModel):
    id: UUID
    module_id: UUID
    exercise_order: int
    exercise_type: str
    question_text: str
    options: Optional[Any] = None
    correct_answer: str
    explanation: Optional[str] = None
    points: int = 10
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentExerciseResponse(BaseModel):
    id: UUID
    module_id: UUID
    exercise_order: int
    exercise_type: str
    question_text: str
    options: Optional[Any] = None
    points: int = 10

    model_config = ConfigDict(from_attributes=True)

class ModuleUpdate(BaseModel):
    title: Optional[str] = None
    topic: Optional[str] = None

class ModuleGenerateRequest(BaseModel):
    classroom_id: UUID
    topic: str
    num_sections: int = Field(default=4, ge=2, le=10)
    num_exercises: int = Field(default=6, ge=3, le=15)

class ModuleGenerateResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    title: str
    topic: str
    status: str
    sections: List[ModuleSectionResponse] = []
    exercises: List[ModuleExerciseResponse] = []
    quiz_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ModuleListItem(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    title: str
    topic: str
    status: str
    section_count: int = 0
    exercise_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentModuleListItem(BaseModel):
    id: UUID
    classroom_id: UUID
    classroom_name: str
    teacher_id: UUID
    title: str
    topic: str
    content_completed: bool = False
    exercises_completed: bool = False
    quiz_unlocked: bool = False
    exercise_score: Optional[float] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class StudentModuleDetailResponse(BaseModel):
    id: UUID
    classroom_id: UUID
    teacher_id: UUID
    title: str
    topic: str
    sections: List[ModuleSectionResponse] = []
    exercises: List[StudentExerciseResponse] = []
    quiz_id: Optional[UUID] = None
    quiz_unlocked: bool = False
    content_completed: bool = False
    exercises_completed: bool = False
    exercise_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ExerciseAnswerItem(BaseModel):
    exercise_id: UUID
    answer: str

class SubmitExercisesRequest(BaseModel):
    answers: List[ExerciseAnswerItem]

class ExerciseResult(BaseModel):
    exercise_id: UUID
    question_text: str
    exercise_type: str
    selected_answer: str
    correct_answer: str
    is_correct: bool
    explanation: Optional[str] = None
    points: int = 10
    points_earned: int = 0

class SubmitExercisesResponse(BaseModel):
    total_points: int
    earned_points: int
    score: float
    passed: bool
    results: List[ExerciseResult]

    model_config = ConfigDict(from_attributes=True)

class StudentModuleProgressResponse(BaseModel):
    module_id: UUID
    content_completed: bool
    content_completed_at: Optional[datetime] = None
    exercises_completed: bool
    exercises_completed_at: Optional[datetime] = None
    exercise_score: Optional[float] = None
    quiz_unlocked: bool

    model_config = ConfigDict(from_attributes=True)
