import json
import uuid
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from uuid import UUID
from typing import List

from core.database import get_db
from app.api.v1.dependencies import get_current_user
from schemas.student import (
    StudentQuizListResponse,
    StudentQuizTakeResponse,
    QuizSubmitRequest,
    QuizSubmitResponse
)
from schemas.module import (
    StudentModuleListItem,
    StudentModuleDetailResponse,
    SubmitExercisesRequest,
    SubmitExercisesResponse,
    ExerciseResult,
    StudentModuleProgressResponse,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter()

def verify_student_role(user):
    if user["role"] != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access student endpoints"
        )

def check_quiz_time_window(quiz):
    now = datetime.now(timezone.utc)
    if quiz.get("start_time") and now < quiz["start_time"].replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This quiz has not started yet"
        )
    if quiz.get("end_time") and now > quiz["end_time"].replace(tzinfo=timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This quiz has already ended"
        )

@router.get("/quizzes", response_model=StudentQuizListResponse)
def get_student_quizzes(current_user = Depends(get_current_user), conn = Depends(get_db)):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT q.id, q.classroom_id, c.name as classroom_name, q.teacher_id,
                   q.topic, q.start_time, q.end_time, q.duration_minutes, q.created_at
            FROM quizzes q
            JOIN classrooms c ON q.classroom_id = c.id
            JOIN classroom_student cs ON c.id = cs.classroom_id
            WHERE cs.student_id = %s
              AND q.status = 'published'
              AND q.id NOT IN (
                  SELECT quiz_id FROM student_attempts WHERE student_id = %s AND score IS NOT NULL
              )
              AND (q.end_time IS NULL OR q.end_time > CURRENT_TIMESTAMP)
            ORDER BY q.created_at DESC;
            """,
            (student_id, student_id)
        )
        active_rows = cur.fetchall()

        cur.execute(
            """
            SELECT q.id, q.classroom_id, c.name as classroom_name, q.teacher_id,
                   q.topic, sa.score, sa.created_at as attempted_at
            FROM quizzes q
            JOIN classrooms c ON q.classroom_id = c.id
            JOIN student_attempts sa ON q.id = sa.quiz_id
            WHERE sa.student_id = %s AND sa.score IS NOT NULL
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
        cur.execute("SELECT * FROM quizzes WHERE id = %s;", (str(quiz_id),))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        if quiz["status"] != "published":
            raise HTTPException(status_code=403, detail="This quiz is not published yet")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(quiz["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            "SELECT 1 FROM student_attempts WHERE quiz_id = %s AND student_id = %s AND score IS NOT NULL;",
            (quiz_id_str, student_id)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="You have already submitted this quiz")

        check_quiz_time_window(quiz)

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
        cur.execute("SELECT * FROM quizzes WHERE id = %s;", (str(quiz_id),))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(quiz["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            "SELECT id, score, started_at FROM student_attempts WHERE quiz_id = %s AND student_id = %s;",
            (quiz_id_str, student_id)
        )
        existing = cur.fetchone()

        if existing and existing["score"] is not None:
            raise HTTPException(status_code=400, detail="You have already submitted this quiz")

        check_quiz_time_window(quiz)

        if quiz.get("duration_minutes") and existing and existing.get("started_at"):
            elapsed = (datetime.now(timezone.utc) - existing["started_at"].replace(tzinfo=timezone.utc)).total_seconds() / 60.0
            if elapsed > quiz["duration_minutes"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Time limit exceeded for this quiz"
                )

        cur.execute(
            "SELECT id, question_text, options, correct_answer, explanation FROM questions WHERE quiz_id = %s ORDER BY created_at ASC;",
            (quiz_id_str,)
        )
        questions = cur.fetchall()

        if not questions:
            raise HTTPException(status_code=400, detail="This quiz has no questions")

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

        if existing:
            cur.execute(
                """
                UPDATE student_attempts
                SET score = %s, answers_snapshot = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s;
                """,
                (score, json.dumps(answers_snapshot), existing["id"])
            )
            attempt_id = existing["id"]
        else:
            attempt_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO student_attempts (id, quiz_id, student_id, score, answers_snapshot, started_at)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
                """,
                (attempt_id, quiz_id_str, student_id, score, json.dumps(answers_snapshot))
            )
        conn.commit()

    return {
        "attempt_id": attempt_id,
        "score": round(score, 2),
        "results": correction_details
    }

@router.get("/modules", response_model=List[StudentModuleListItem])
def get_student_modules(current_user = Depends(get_current_user), conn = Depends(get_db)):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT lm.id, lm.classroom_id, c.name as classroom_name, lm.teacher_id,
                   lm.title, lm.topic, lm.created_at,
                   COALESCE(smp.content_completed, FALSE) as content_completed,
                   COALESCE(smp.exercises_completed, FALSE) as exercises_completed,
                   COALESCE(smp.quiz_unlocked, FALSE) as quiz_unlocked,
                   smp.exercise_score
            FROM learning_modules lm
            JOIN classrooms c ON lm.classroom_id = c.id
            JOIN classroom_student cs ON c.id = cs.classroom_id
            LEFT JOIN student_module_progress smp ON lm.id = smp.module_id AND smp.student_id = %s
            WHERE cs.student_id = %s AND lm.status = 'published'
            ORDER BY lm.created_at DESC;
            """,
            (student_id, student_id)
        )
        modules = cur.fetchall()
        return modules

@router.get("/modules/{module_id}", response_model=StudentModuleDetailResponse)
def get_student_module_detail(
    module_id: UUID,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if module["status"] != "published":
            raise HTTPException(status_code=403, detail="This module is not published yet")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(module["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            "SELECT * FROM module_sections WHERE module_id = %s ORDER BY section_order ASC;",
            (str(module_id),)
        )
        sections = cur.fetchall()

        cur.execute(
            "SELECT id, module_id, exercise_order, exercise_type, question_text, options, points FROM module_exercises WHERE module_id = %s ORDER BY exercise_order ASC;",
            (str(module_id),)
        )
        exercises = cur.fetchall()

        cur.execute(
            "SELECT * FROM student_module_progress WHERE module_id = %s AND student_id = %s;",
            (str(module_id), student_id)
        )
        progress = cur.fetchone()

        cur.execute("SELECT id FROM quizzes WHERE module_id = %s LIMIT 1;", (str(module_id),))
        quiz_row = cur.fetchone()

        result = dict(module)
        result["sections"] = [dict(s) for s in sections]
        result["exercises"] = [dict(e) for e in exercises]
        result["quiz_id"] = quiz_row["id"] if quiz_row else None
        result["content_completed"] = progress["content_completed"] if progress else False
        result["exercises_completed"] = progress["exercises_completed"] if progress else False
        result["exercise_score"] = progress["exercise_score"] if progress else None
        result["quiz_unlocked"] = progress["quiz_unlocked"] if progress else False
        return result

@router.post("/modules/{module_id}/complete-content", response_model=StudentModuleProgressResponse)
def complete_module_content(
    module_id: UUID,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, classroom_id, status FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if module["status"] != "published":
            raise HTTPException(status_code=403, detail="This module is not published yet")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(module["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            """
            INSERT INTO student_module_progress (id, module_id, student_id, content_completed, content_completed_at)
            VALUES (%s, %s, %s, TRUE, CURRENT_TIMESTAMP)
            ON CONFLICT (module_id, student_id)
            DO UPDATE SET content_completed = TRUE, content_completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
            RETURNING *;
            """,
            (str(uuid.uuid4()), str(module_id), student_id)
        )
        progress = cur.fetchone()
        conn.commit()
        return progress

@router.post("/modules/{module_id}/submit-exercises", response_model=SubmitExercisesResponse)
def submit_module_exercises(
    module_id: UUID,
    payload: SubmitExercisesRequest,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, classroom_id, status FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if module["status"] != "published":
            raise HTTPException(status_code=403, detail="This module is not published yet")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(module["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            "SELECT * FROM module_exercises WHERE module_id = %s ORDER BY exercise_order ASC;",
            (str(module_id),)
        )
        exercises = cur.fetchall()
        if not exercises:
            raise HTTPException(status_code=400, detail="This module has no exercises")

        student_answers = {str(a.exercise_id): a.answer for a in payload.answers}

        total_points = 0
        earned_points = 0
        results = []

        for ex in exercises:
            ex_id_str = str(ex["id"])
            selected = student_answers.get(ex_id_str, "")
            ex_type = ex["exercise_type"]
            correct = ex["correct_answer"]
            points = ex["points"] or 10
            total_points += points

            is_correct = False

            if ex_type == "fill_blank":
                is_correct = selected.strip().lower() == correct.strip().lower()
            elif ex_type == "true_false":
                is_correct = selected.strip().lower() == correct.strip().lower()
            elif ex_type == "matching":
                norm_sel = ";".join(sorted(selected.strip().split(";")))
                norm_cor = ";".join(sorted(correct.strip().split(";")))
                is_correct = norm_sel == norm_cor
            elif ex_type == "ordering":
                is_correct = selected.strip() == correct.strip()
            else:
                is_correct = selected.strip() == correct.strip()

            if is_correct:
                earned_points += points

            results.append(ExerciseResult(
                exercise_id=ex["id"],
                question_text=ex["question_text"],
                exercise_type=ex_type,
                selected_answer=selected,
                correct_answer=correct,
                is_correct=is_correct,
                explanation=ex.get("explanation"),
                points=points,
                points_earned=points if is_correct else 0,
            ))

        score = (earned_points / total_points * 100.0) if total_points > 0 else 0.0
        passed = score >= 70.0

        exercise_answers = {str(ex["id"]): student_answers.get(str(ex["id"]), "") for ex in exercises}

        cur.execute(
            """
            INSERT INTO student_module_progress (id, module_id, student_id, content_completed, exercises_completed,
                exercises_completed_at, exercise_answers, exercise_score, quiz_unlocked)
            VALUES (%s, %s, %s, TRUE, TRUE, CURRENT_TIMESTAMP, %s, %s, %s)
            ON CONFLICT (module_id, student_id)
            DO UPDATE SET
                exercises_completed = TRUE,
                exercises_completed_at = CURRENT_TIMESTAMP,
                exercise_answers = %s,
                exercise_score = %s,
                quiz_unlocked = %s,
                content_completed = TRUE,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *;
            """,
            (
                str(uuid.uuid4()), str(module_id), student_id,
                json.dumps(exercise_answers), round(score, 2), passed,
                json.dumps(exercise_answers), round(score, 2), passed,
            )
        )
        conn.commit()

    return SubmitExercisesResponse(
        total_points=total_points,
        earned_points=earned_points,
        score=round(score, 2),
        passed=passed,
        results=results,
    )

@router.get("/modules/{module_id}/quiz", response_model=StudentQuizTakeResponse)
def get_module_quiz(
    module_id: UUID,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, classroom_id, status FROM learning_modules WHERE id = %s;", (str(module_id),))
        module = cur.fetchone()
        if not module:
            raise HTTPException(status_code=404, detail="Module not found")
        if module["status"] != "published":
            raise HTTPException(status_code=403, detail="This module is not published yet")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(module["classroom_id"]), student_id)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=403, detail="You are not enrolled in this classroom")

        cur.execute(
            "SELECT quiz_unlocked FROM student_module_progress WHERE module_id = %s AND student_id = %s;",
            (str(module_id), student_id)
        )
        progress = cur.fetchone()
        if not progress or not progress["quiz_unlocked"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Complete the exercises first to unlock the quiz"
            )

        cur.execute("SELECT id FROM quizzes WHERE module_id = %s AND status = 'published' LIMIT 1;", (str(module_id),))
        quiz = cur.fetchone()
        if not quiz:
            raise HTTPException(status_code=404, detail="No published quiz found for this module")

        cur.execute(
            "SELECT 1 FROM student_attempts WHERE quiz_id = %s AND student_id = %s AND score IS NOT NULL;",
            (quiz["id"], student_id)
        )
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="You have already completed this quiz")

        cur.execute(
            "SELECT id, quiz_id, question_text, options FROM questions WHERE quiz_id = %s ORDER BY created_at ASC;",
            (quiz["id"],)
        )
        questions = cur.fetchall()

        cur.execute("SELECT * FROM quizzes WHERE id = %s;", (quiz["id"],))
        quiz_full = cur.fetchone()

        quiz_dict = dict(quiz_full)
        quiz_dict["questions"] = [dict(q) for q in questions]
        return quiz_dict

@router.get("/modules/{module_id}/progress", response_model=StudentModuleProgressResponse)
def get_module_progress(
    module_id: UUID,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    verify_student_role(current_user)
    student_id = str(current_user["id"])

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM student_module_progress WHERE module_id = %s AND student_id = %s;",
            (str(module_id), student_id)
        )
        progress = cur.fetchone()
        if not progress:
            return {
                "module_id": module_id,
                "content_completed": False,
                "content_completed_at": None,
                "exercises_completed": False,
                "exercises_completed_at": None,
                "exercise_score": None,
                "quiz_unlocked": False,
            }
        return progress
