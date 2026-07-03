from pydantic import BaseModel
from uuid import UUID
from typing import List
from datetime import datetime

class QuizReportStats(BaseModel):
    average_score: float
    highest_score: float
    lowest_score: float
    total_attempts: int
    total_students_in_class: int
    participation_rate_pct: float

class StudentReportResult(BaseModel):
    student_id: UUID
    student_name: str
    score: float
    submitted_at: datetime

class QuizReportResponse(BaseModel):
    quiz_id: UUID
    statistics: QuizReportStats
    student_results: List[StudentReportResult]
