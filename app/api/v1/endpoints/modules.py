import json
import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from psycopg2.extras import RealDictCursor
from uuid import UUID
from typing import List, Optional

from core.database import get_db
from core.limiter import limiter
from app.api.v1.dependencies import get_current_teacher
from schemas.module import (
    ModuleGenerateRequest,
    ModuleGenerateResponse,
    ModuleListItem,
    ModuleSectionResponse,
    ModuleExerciseResponse,
    ModuleUpdate,
)
from schemas.quiz import QuizResponse
from services.ai_service import AIService

logger = logging.getLogger("uvicorn.error")
router = APIRouter()

@router.post("/generate", response_model=ModuleGenerateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
def generate_module(
    request: Request,
    payload: ModuleGenerateRequest,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, teacher_id FROM classrooms WHERE id = %s;", (str(payload.classroom_id),))
        classroom = cur.fetchone()
        if not classroom:
            raise HTTPException(status_code=404, detail="Classroom not found")
        if str(classroom["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have access to this classroom")

        topic = payload.topic.strip()
        module_id = str(uuid.uuid4())

        title = f"Materi: {topic}"

        sections = AIService.generate_module_sections(topic, payload.num_sections)
        if not sections:
            raise HTTPException(status_code=500, detail="Failed to generate module content")

        exercises = AIService.generate_module_exercises(topic, payload.num_exercises)
        if not exercises:
            raise HTTPException(status_code=500, detail="Failed to generate exercises")

        cur.execute(
            """
            INSERT INTO learning_modules (id, classroom_id, teacher_id, title, topic, status)
            VALUES (%s, %s, %s, %s, %s, 'draft')
            RETURNING *;
            """,
            (module_id, str(payload.classroom_id), teacher_id, title, topic)
        )
        module_row = cur.fetchone()

        section_rows = []
        for i, sec in enumerate(sections):
            sec_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO module_sections (id, module_id, section_order, title, content, image_prompt)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (sec_id, module_id, i + 1, sec.get("title", ""), sec.get("content", ""), sec.get("image_prompt"))
            )
            section_rows.append(cur.fetchone())

        exercise_rows = []
        for i, ex in enumerate(exercises):
            ex_id = str(uuid.uuid4())
            ex_type = ex.get("exercise_type", "multiple_choice")
            options = ex.get("options")
            cur.execute(
                """
                INSERT INTO module_exercises (id, module_id, exercise_order, exercise_type, question_text, options, correct_answer, explanation, points)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *;
                """,
                (
                    ex_id, module_id, i + 1, ex_type,
                    ex.get("question_text", ""),
                    json.dumps(options) if options else None,
                    ex.get("correct_answer", ""),
                    ex.get("explanation"),
                    ex.get("points", 10)
                )
            )
            exercise_rows.append(cur.fetchone())

        questions = AIService.generate_questions(topic, 5)
        quiz_id = None
        if questions:
            quiz_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO quizzes (id, classroom_id, teacher_id, topic, status, module_id)
                VALUES (%s, %s, %s, %s, 'draft', %s)
                RETURNING *;
                """,
                (quiz_id, str(payload.classroom_id), teacher_id, topic, module_id)
            )
            for q_data in questions:
                q_id = str(uuid.uuid4())
                cur.execute(
                    """
                    INSERT INTO questions (id, quiz_id, question_text, options, correct_answer, explanation)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING *;
                    """,
                    (q_id, quiz_id, q_data["question_text"], json.dumps(q_data["options"]), q_data["correct_answer"], q_data.get("explanation"))
                )

        conn.commit()

        return {
            **dict(module_row),
            "sections": [dict(s) for s in section_rows],
            "exercises": [dict(e) for e in exercise_rows],
            "quiz_id": quiz_id,
        }

@router.get("", response_model=List[ModuleListItem])
def list_modules(
    classroom_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if classroom_id:
            cur.execute(
                "SELECT teacher_id FROM classrooms WHERE id = %s;",
                (str(classroom_id),)
            )
            classroom = cur.fetchone()
            if not classroom:
                raise HTTPException(status_code=404, detail="Classroom not found")
            if str(classroom["teacher_id"]) != teacher_id:
                raise HTTPException(status_code=404, detail="Classroom not found")

            cur.execute(
                """
                SELECT lm.*,
                    (SELECT COUNT(*) FROM module_sections WHERE module_id = lm.id) as section_count,
                    (SELECT COUNT(*) FROM module_exercises WHERE module_id = lm.id) as exercise_count
                FROM learning_modules lm
                WHERE lm.teacher_id = %s AND lm.classroom_id = %s
                ORDER BY lm.created_at DESC
                LIMIT %s OFFSET %s;
                """,
                (teacher_id, str(classroom_id), limit, offset)
            )
        else:
            cur.execute(
                """
                SELECT lm.*,
                    (SELECT COUNT(*) FROM module_sections WHERE module_id = lm.id) as section_count,
                    (SELECT COUNT(*) FROM module_exercises WHERE module_id = lm.id) as exercise_count
                FROM learning_modules lm
                WHERE lm.teacher_id = %s
                ORDER BY lm.created_at DESC
                LIMIT %s OFFSET %s;
                """,
                (teacher_id, limit, offset)
            )
        return cur.fetchall()

@router.get("/{module_id}", response_model=ModuleGenerateResponse)
def get_module(
    module_id: UUID,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if str(module["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=404, detail="Module not found")

        cur.execute(
            "SELECT * FROM module_sections WHERE module_id = %s ORDER BY section_order ASC;",
            (str(module_id),)
        )
        sections = cur.fetchall()

        cur.execute(
            "SELECT * FROM module_exercises WHERE module_id = %s ORDER BY exercise_order ASC;",
            (str(module_id),)
        )
        exercises = cur.fetchall()

        cur.execute("SELECT id FROM quizzes WHERE module_id = %s LIMIT 1;", (str(module_id),))
        quiz_row = cur.fetchone()

        return {
            **dict(module),
            "sections": [dict(s) for s in sections],
            "exercises": [dict(e) for e in exercises],
            "quiz_id": quiz_row["id"] if quiz_row else None,
        }

@router.post("/{module_id}/publish", status_code=status.HTTP_200_OK)
def publish_module(
    module_id: UUID,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, teacher_id FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if str(module["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have permission to publish this module")

        cur.execute(
            "UPDATE learning_modules SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = %s RETURNING id, status;",
            (str(module_id),)
        )
        result = cur.fetchone()

        cur.execute("SELECT id FROM quizzes WHERE module_id = %s;", (str(module_id),))
        quiz = cur.fetchone()
        if quiz:
            cur.execute(
                "UPDATE quizzes SET status = 'published', updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
                (quiz["id"],)
            )

        conn.commit()
        return {"id": result["id"], "status": result["status"]}

ALLOWED_MODULE_COLUMNS = {"title", "topic"}

@router.patch("/{module_id}", response_model=ModuleGenerateResponse)
def update_module(
    module_id: UUID,
    payload: ModuleUpdate,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if str(module["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have permission to update this module")

        update_data = payload.model_dump(exclude_unset=True)
        if update_data:
            update_fields = []
            params = []
            for key, val in update_data.items():
                if key not in ALLOWED_MODULE_COLUMNS:
                    raise HTTPException(status_code=400, detail=f"Invalid field: {key}")
                update_fields.append(f"{key} = %s")
                params.append(val)

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(str(module_id))

            cur.execute(
                f"UPDATE learning_modules SET {', '.join(update_fields)} WHERE id = %s RETURNING *;",
                tuple(params)
            )
            module = cur.fetchone()

        cur.execute(
            "SELECT * FROM module_sections WHERE module_id = %s ORDER BY section_order ASC;",
            (str(module_id),)
        )
        sections = cur.fetchall()

        cur.execute(
            "SELECT * FROM module_exercises WHERE module_id = %s ORDER BY exercise_order ASC;",
            (str(module_id),)
        )
        exercises = cur.fetchall()

        cur.execute("SELECT id FROM quizzes WHERE module_id = %s LIMIT 1;", (str(module_id),))
        quiz_row = cur.fetchone()

        conn.commit()

        return {
            **dict(module),
            "sections": [dict(s) for s in sections],
            "exercises": [dict(e) for e in exercises],
            "quiz_id": quiz_row["id"] if quiz_row else None,
        }

@router.delete("/{module_id}", status_code=status.HTTP_200_OK)
def delete_module(
    module_id: UUID,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, teacher_id FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if str(module["teacher_id"]) != teacher_id:
            raise HTTPException(status_code=403, detail="You do not have permission to delete this module")

        cur.execute("DELETE FROM learning_modules WHERE id = %s RETURNING id;", (str(module_id),))
        cur.fetchone()
        conn.commit()
        return {"message": "Module deleted successfully"}
