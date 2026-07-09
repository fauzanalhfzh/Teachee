import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from uuid import UUID

from core.database import get_db
from app.api.v1.dependencies import get_current_user
from schemas.student import (
    StudentQuizListResponse,
    StudentQuizTakeResponse,
    QuizSubmitRequest,
    QuizSubmitResponse
)

router = APIRouter()

def verify_student_role(user):
    if user["role"] != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access student endpoints"
        )

@router.get("/quizzes", response_model=StudentQuizListResponse)
def get_student_quizzes(current_user = Depends(get_current_user), conn = Depends(get_db)):
    verify_student_role(current_user)
    student_id = str(current_user["id"])
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Active quizzes: published quizzes in student's classrooms that the student has not attempted yet
        cur.execute(
            """
            SELECT q.id, q.classroom_id, c.name as classroom_name, q.teacher_id, q.topic, q.created_at
            FROM quizzes q
            JOIN classrooms c ON q.classroom_id = c.id
            JOIN classroom_student cs ON c.id = cs.classroom_id
            WHERE cs.student_id = %s 
              AND q.status = 'published'
              AND q.id NOT IN (
                  SELECT quiz_id FROM student_attempts WHERE student_id = %s
              )
            ORDER BY q.created_at DESC;
            """,
            (student_id, student_id)
        )
        active_rows = cur.fetchall()

        # Completed quizzes: quizzes attempted by this student
        cur.execute(
            """
            SELECT q.id, q.classroom_id, c.name as classroom_name, q.teacher_id, q.topic, sa.score, sa.created_at as attempted_at
            FROM quizzes q
            JOIN classrooms c ON q.classroom_id = c.id
            JOIN student_attempts sa ON q.id = sa.quiz_id
            WHERE sa.student_id = %s
            ORDER BY sa.created_at DESC;
            """,
            (student_id,)
        )
        completed_rows = cur.fetchall()

    return {
        "active": [dict(r) for r in active_rows],
        "completed": [dict(r) for r in completed_rows]
    }

@router.get("/quizzes/{quiz_id}/take", response_model=StudentQuizTakeResponse)
def take_quiz(quiz_id: UUID, current_user = Depends(get_current_user), conn = Depends(get_db)):
    verify_student_role(current_user)
    student_id = str(current_user["id"])
    quiz_id_str = str(quiz_id)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Fetch quiz and verify it exists and is published
        cur.execute("SELECT * FROM quizzes WHERE id = %s;", (quiz_id_str,))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        if quiz["status"] != "published":
            raise HTTPException(status_code=403, detail="This quiz is not published yet")

        # 2. Verify student is enrolled in the classroom
        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(quiz["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        # 3. Fetch questions (selecting ONLY id, quiz_id, question_text, options)
        cur.execute(
            "SELECT id, quiz_id, question_text, options FROM questions WHERE quiz_id = %s ORDER BY created_at ASC;",
            (quiz_id_str,)
        )
        questions = cur.fetchall()

    quiz_dict = dict(quiz)
    quiz_dict["questions"] = [dict(q) for q in questions]
    return quiz_dict

@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmitResponse)
def submit_quiz(quiz_id: UUID, payload: QuizSubmitRequest, current_user = Depends(get_current_user), conn = Depends(get_db)):
    verify_student_role(current_user)
    student_id = str(current_user["id"])
    quiz_id_str = str(quiz_id)

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Fetch quiz
        cur.execute("SELECT * FROM quizzes WHERE id = %s;", (quiz_id_str,))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        # 2. Verify student is enrolled in the classroom
        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(quiz["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        # 3. Verify student has not already attempted this quiz
        cur.execute(
            "SELECT 1 FROM student_attempts WHERE quiz_id = %s AND student_id = %s;",
            (quiz_id_str, student_id)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="You have already submitted this quiz")

        # 4. Fetch all questions with answers
        cur.execute(
            "SELECT id, question_text, options, correct_answer, explanation FROM questions WHERE quiz_id = %s ORDER BY created_at ASC;",
            (quiz_id_str,)
        )
        questions = cur.fetchall()

        if not questions:
            raise HTTPException(status_code=400, detail="This quiz has no questions")

        # Convert student answers payload into a lookup dictionary
        student_answers_dict = {str(ans.question_id): ans.selected_answer for ans in payload.answers}

        correct_count = 0
        correction_details = []
        answers_snapshot = {}

        for q in questions:
            q_id_str = str(q["id"])
            selected = student_answers_dict.get(q_id_str, "")
            answers_snapshot[q_id_str] = selected
            
            is_correct = selected.strip() == q["correct_answer"].strip()
            if is_correct:
                correct_count += 1
            
            correction_details.append({
                "question_id": q["id"],
                "question_text": q["question_text"],
                "options": q["options"],
                "selected_answer": selected,
                "correct_answer": q["correct_answer"],
                "is_correct": is_correct,
                "explanation": q["explanation"]
            })

        score = (correct_count / len(questions)) * 100.0

        # Save the attempt
        attempt_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO student_attempts (id, quiz_id, student_id, score, answers_snapshot)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (attempt_id, quiz_id_str, student_id, score, json.dumps(answers_snapshot))
        )
        conn.commit()

    return {
        "attempt_id": attempt_id,
        "score": round(score, 2),
        "results": correction_details
    }
