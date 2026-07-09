import pytest
import uuid
from datetime import datetime, timezone, timedelta
from core.database import get_db_connection

def test_access_restricted_to_students(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    response = client.get("/api/v1/student/quizzes", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Only students can access student endpoints"

def test_student_quiz_workflow(client, teacher_auth_headers, student_auth_headers, create_user):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia 10A", "teacher_id": teacher_id},
        headers=teacher_headers
    )
    assert classroom_res.status_code == 201
    classroom_id = classroom_res.json()["id"]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student_id)
            )
        conn.commit()

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Asam Basa",
            "num_questions": 2
        },
        headers=teacher_headers
    )
    assert quiz_res.status_code == 201
    quiz_data = quiz_res.json()
    quiz_id = quiz_data["id"]
    questions = quiz_data["questions"]
    assert len(questions) == 2

    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["active"]) == 0
    assert len(list_res.json()["completed"]) == 0

    publish_res = client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=teacher_headers)
    assert publish_res.status_code == 200

    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    active_quizzes = list_res.json()["active"]
    assert len(active_quizzes) == 1
    assert active_quizzes[0]["id"] == quiz_id
    assert active_quizzes[0]["classroom_name"] == "Kimia 10A"
    assert len(list_res.json()["completed"]) == 0

    take_res = client.get(f"/api/v1/student/quizzes/{quiz_id}/take", headers=student_headers)
    assert take_res.status_code == 200
    take_data = take_res.json()
    assert take_data["id"] == quiz_id
    assert len(take_data["questions"]) == 2

    for q in take_data["questions"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert "question_text" in q
        assert "options" in q

    q1 = questions[0]
    q2 = questions[1]

    submit_payload = {
        "answers": [
            {
                "question_id": q1["id"],
                "selected_answer": q1["correct_answer"]
            },
            {
                "question_id": q2["id"],
                "selected_answer": "Wrong Answer Choice"
            }
        ]
    }

    submit_res = client.post(f"/api/v1/student/quizzes/{quiz_id}/submit", json=submit_payload, headers=student_headers)
    assert submit_res.status_code == 200

    submit_data = submit_res.json()
    assert "attempt_id" in submit_data
    assert submit_data["score"] == 50.0
    assert len(submit_data["results"]) == 2

    res1 = [r for r in submit_data["results"] if r["question_id"] == q1["id"]][0]
    assert res1["is_correct"] is True
    assert res1["selected_answer"] == q1["correct_answer"]
    assert res1["correct_answer"] == q1["correct_answer"]
    assert res1["explanation"] == q1["explanation"]

    res2 = [r for r in submit_data["results"] if r["question_id"] == q2["id"]][0]
    assert res2["is_correct"] is False
    assert res2["selected_answer"] == "Wrong Answer Choice"
    assert res2["correct_answer"] == q2["correct_answer"]
    assert res2["explanation"] == q2["explanation"]

    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["active"]) == 0
    assert len(data["completed"]) == 1
    assert data["completed"][0]["id"] == quiz_id
    assert data["completed"][0]["score"] == 50.0
    assert "attempted_at" in data["completed"][0]

    dup_res = client.post(f"/api/v1/student/quizzes/{quiz_id}/submit", json=submit_payload, headers=student_headers)
    assert dup_res.status_code == 400
    assert dup_res.json()["detail"] == "You have already submitted this quiz"

def test_quiz_not_started_yet(client, teacher_auth_headers, student_auth_headers):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Fisika Masa Depan", "teacher_id": teacher_id},
        headers=teacher_headers
    )
    classroom_id = classroom_res.json()["id"]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student_id)
            )
        conn.commit()

    future_time = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Fisika Quantum",
            "num_questions": 1,
            "start_time": future_time,
            "end_time": (datetime.now(timezone.utc) + timedelta(days=14)).isoformat()
        },
        headers=teacher_headers
    )
    quiz_id = quiz_res.json()["id"]

    client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=teacher_headers)

    take_res = client.get(f"/api/v1/student/quizzes/{quiz_id}/take", headers=student_headers)
    assert take_res.status_code == 403
    assert "not started yet" in take_res.json()["detail"].lower()

def test_quiz_already_ended(client, teacher_auth_headers, student_auth_headers):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Sejarah Lampau", "teacher_id": teacher_id},
        headers=teacher_headers
    )
    classroom_id = classroom_res.json()["id"]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student_id)
            )
        conn.commit()

    past_time = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Sejarah Kuno",
            "num_questions": 1,
            "start_time": (datetime.now(timezone.utc) - timedelta(days=14)).isoformat(),
            "end_time": past_time
        },
        headers=teacher_headers
    )
    quiz_id = quiz_res.json()["id"]

    client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=teacher_headers)

    take_res = client.get(f"/api/v1/student/quizzes/{quiz_id}/take", headers=student_headers)
    assert take_res.status_code == 403
    assert "already ended" in take_res.json()["detail"].lower()

def test_quiz_list_excludes_ended_quizzes(client, teacher_auth_headers, student_auth_headers):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kelas Filter", "teacher_id": teacher_id},
        headers=teacher_headers
    )
    classroom_id = classroom_res.json()["id"]

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student_id)
            )
        conn.commit()

    now = datetime.now(timezone.utc)

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Quiz Aktif",
            "num_questions": 1,
            "start_time": (now - timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat()
        },
        headers=teacher_headers
    )
    active_quiz_id = quiz_res.json()["id"]
    client.post(f"/api/v1/quizzes/{active_quiz_id}/publish", headers=teacher_headers)

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Quiz Lampau",
            "num_questions": 1,
            "start_time": (now - timedelta(days=2)).isoformat(),
            "end_time": (now - timedelta(days=1)).isoformat()
        },
        headers=teacher_headers
    )
    ended_quiz_id = quiz_res.json()["id"]
    client.post(f"/api/v1/quizzes/{ended_quiz_id}/publish", headers=teacher_headers)

    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    active_ids = [q["id"] for q in data["active"]]
    assert active_quiz_id in active_ids
    assert ended_quiz_id not in active_ids
    assert len(data["active"]) == 1
