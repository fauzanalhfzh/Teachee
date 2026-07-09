from fastapi import APIRouter
from app.api.v1.endpoints import quizzes, questions, classrooms, auth, students, modules

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(quizzes.router, prefix="/quizzes", tags=["quizzes"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(classrooms.router, prefix="/classrooms", tags=["classrooms"])
api_router.include_router(students.router, prefix="/student", tags=["student"])
api_router.include_router(modules.router, prefix="/modules", tags=["modules"])


