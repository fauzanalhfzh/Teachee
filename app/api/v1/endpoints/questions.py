import json
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from uuid import UUID

from core.database import get_db
from schemas.question import QuestionUpdate, QuestionResponse
from services.ai_service import AIService

router = APIRouter()

@router.put("/{question_id}/regenerate", response_model=QuestionResponse)
def regenerate_question(question_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Fetch question and join with quiz to fetch the topic
        cur.execute(
            """
            SELECT q.id, q.quiz_id, qz.topic FROM questions q
            JOIN quizzes qz ON q.quiz_id = qz.id
            WHERE q.id = %s;
            """,
            (str(question_id),)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Question not found")

        # 2. Get a new replacement question from the AI Service
        new_q_data = AIService.regenerate_single_question(row["topic"])

        # 3. Update the question in PostgreSQL
        cur.execute(
            """
            UPDATE questions
            SET question_text = %s, options = %s, correct_answer = %s, explanation = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            RETURNING *;
            """,
            (new_q_data["question_text"], json.dumps(new_q_data["options"]), new_q_data["correct_answer"], new_q_data.get("explanation"), str(question_id))
        )
        updated_question = cur.fetchone()
        conn.commit()
        return updated_question

ALLOWED_QUESTION_COLUMNS = {"question_text", "options", "correct_answer", "explanation"}

@router.patch("/{question_id}", response_model=QuestionResponse)
def update_question(question_id: UUID, payload: QuestionUpdate, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM questions WHERE id = %s;", (str(question_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Question not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            cur.execute("SELECT * FROM questions WHERE id = %s;", (str(question_id),))
            return cur.fetchone()

        update_fields = []
        params = []
        for key, val in update_data.items():
            if key not in ALLOWED_QUESTION_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid field: {key}")
            update_fields.append(f"{key} = %s")
            params.append(json.dumps(val) if key == "options" else val)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(str(question_id))

        query = f"""
            UPDATE questions
            SET {', '.join(update_fields)}
            WHERE id = %s
            RETURNING *;
        """
        cur.execute(query, tuple(params))
        updated_question = cur.fetchone()
        conn.commit()
        return updated_question

@router.delete("/{question_id}", status_code=status.HTTP_200_OK)
def delete_question(question_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM questions WHERE id = %s RETURNING id;", (str(question_id),))
        deleted_id = cur.fetchone()
        if not deleted_id:
            raise HTTPException(status_code=404, detail="Question not found")
        
        conn.commit()
        return {"message": "Question deleted successfully"}
