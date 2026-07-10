import json
import re
import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from psycopg2.extras import RealDictCursor
from uuid import UUID
from typing import List, Optional

from core.database import get_db
from core.limiter import limiter
from core.sql import assert_teacher_owns, safe_commit
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
from services.flux_client import FluxClient
from pathlib import Path

logger = logging.getLogger("uvicorn.error")
router = APIRouter()

@router.post("/generate", response_model=ModuleGenerateResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/hour")
def generate_module(
    request: Request,
    payload: ModuleGenerateRequest,
    force: bool = Query(False, description="Regenerate from AI even if cached module exists"),
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
        topic = re.sub(
            r'^(?:buatkan|bikin|tolong|mohon|buat|cari)\s+(?:materi|soal|latihan|modul|ringkasan)?\s*(?:tentang|mengenai|untuk)?\s+',
            '', topic, flags=re.IGNORECASE
        ).strip()

        if not force:
            cur.execute(
                """
                SELECT id FROM learning_modules
                WHERE classroom_id = %s AND LOWER(topic) = LOWER(%s)
                ORDER BY created_at DESC LIMIT 1;
                """,
                (str(payload.classroom_id), topic)
            )
            existing = cur.fetchone()
            if existing:
                cached_id = str(existing["id"])
                cur.execute("SELECT * FROM learning_modules WHERE id = %s;", (cached_id,))
                module_row = cur.fetchone()
                cur.execute(
                    "SELECT * FROM module_sections WHERE module_id = %s ORDER BY section_order ASC;",
                    (cached_id,)
                )
                section_rows = cur.fetchall()
                cur.execute(
                    "SELECT * FROM module_exercises WHERE module_id = %s ORDER BY exercise_order ASC;",
                    (cached_id,)
                )
                exercise_rows = cur.fetchall()
                cur.execute("SELECT id FROM quizzes WHERE module_id = %s LIMIT 1;", (cached_id,))
                quiz_row = cur.fetchone()

                return {
                    **dict(module_row),
                    "sections": [dict(s) for s in section_rows],
                    "exercises": [dict(e) for e in exercise_rows],
                    "quiz_id": quiz_row["id"] if quiz_row else None,
                }

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
    assert_teacher_owns(conn, "learning_modules", str(module_id), teacher_id, "Module not found")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM learning_modules WHERE id = %s;", (str(module_id),))
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
    assert_teacher_owns(conn, "learning_modules", str(module_id), teacher_id, "Module not found")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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

        safe_commit(conn)
        return {"id": result["id"], "status": result["status"]}

IMAGES_DIR = Path("static/images")

@router.post("/{module_id}/generate-images", status_code=status.HTTP_200_OK)
async def generate_module_images(
    module_id: UUID,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    assert_teacher_owns(conn, "learning_modules", str(module_id), teacher_id, "Module not found")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT id, image_prompt FROM module_sections WHERE module_id = %s AND image_url IS NULL AND image_prompt IS NOT NULL ORDER BY section_order ASC;",
            (str(module_id),)
        )
        sections = cur.fetchall()

        if not sections:
            return {"message": "No sections need image generation", "images": []}

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    async def _generate_one(sec) -> dict:
        sec_id = str(sec["id"])
        prompt = sec["image_prompt"]
        image_bytes = await FluxClient.generate_image_async(prompt)
        if not image_bytes:
            return {"section_id": sec_id, "status": "failed", "error": "FLUX unavailable"}

        file_path = IMAGES_DIR / f"{sec_id}.jpg"
        file_path.write_bytes(image_bytes)

        image_url = f"/static/images/{sec_id}.jpg"
        return {"section_id": sec_id, "status": "generated", "image_url": image_url, "_image_url": image_url}

    results = await asyncio.gather(*[_generate_one(s) for s in sections])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for r in results:
            if r["status"] == "generated":
                cur.execute(
                    "UPDATE module_sections SET image_url = %s WHERE id = %s;",
                    (r["_image_url"], r["section_id"])
                )
        safe_commit(conn)

    clean = [{"section_id": r["section_id"], "status": r["status"], "image_url": r.get("image_url"), "error": r.get("error")} for r in results]
    return {"message": f"Generated {len(clean)} images", "images": clean}

ALLOWED_MODULE_COLUMNS = {"title", "topic"}

@router.patch("/{module_id}", response_model=ModuleGenerateResponse)
def update_module(
    module_id: UUID,
    payload: ModuleUpdate,
    current_user = Depends(get_current_teacher),
    conn = Depends(get_db),
):
    teacher_id = str(current_user["id"])
    module = assert_teacher_owns(conn, "learning_modules", str(module_id), teacher_id, "Module not found")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
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

        safe_commit(conn)

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
    assert_teacher_owns(conn, "learning_modules", str(module_id), teacher_id, "Module not found")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM learning_modules WHERE id = %s RETURNING id;", (str(module_id),))
        cur.fetchone()
        safe_commit(conn)
        return {"message": "Module deleted successfully"}
