import pytest
import uuid
from datetime import datetime, timezone, timedelta
from core.database import get_db_connection

def test_generate_quiz_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Matematika 10", "teacher_id": teacher_id},
        headers=headers
    )
    assert classroom_res.status_code == 201
    classroom_id = classroom_res.json()["id"]

    payload = {
        "classroom_id": classroom_id,
        "topic": "Aljabar",
        "num_questions": 3
    }
    response = client.post("/api/v1/quizzes/generate", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "draft"
    assert len(data["questions"]) == 3
    assert "id" in data
    assert data["start_time"] is None
    assert data["end_time"] is None
    assert data["duration_minutes"] is None

    for q in data["questions"]:
        assert "question_text" in q
        assert "options" in q
        assert "correct_answer" in q

def test_generate_quiz_with_time_window(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Fisika Waktu", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    now = datetime.now(timezone.utc)
    start_time = (now + timedelta(hours=1)).isoformat()
    end_time = (now + timedelta(hours=2)).isoformat()

    payload = {
        "classroom_id": classroom_id,
        "topic": "Kinematika",
        "num_questions": 2,
        "start_time": start_time,
        "end_time": end_time,
        "duration_minutes": 30
    }
    response = client.post("/api/v1/quizzes/generate", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["start_time"] is not None
    assert data["end_time"] is not None
    assert data["duration_minutes"] == 30
    assert data["status"] == "draft"

def test_generate_quiz_invalid_time_range(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Invalid Time", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    now = datetime.now(timezone.utc)
    payload = {
        "classroom_id": classroom_id,
        "topic": "Aljabar",
        "num_questions": 2,
        "start_time": (now + timedelta(hours=2)).isoformat(),
        "end_time": (now + timedelta(hours=1)).isoformat(),
    }
    response = client.post("/api/v1/quizzes/generate", json=payload, headers=headers)
    assert response.status_code == 400
    assert "start_time must be before end_time" in response.json()["detail"]

def test_list_quizzes_by_classroom(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Biologi 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    for i in range(3):
        client.post(
            "/api/v1/quizzes/generate",
            json={"classroom_id": classroom_id, "topic": f"Topik {i}", "num_questions": 1},
            headers=headers
        )

    response = client.get(f"/api/v1/quizzes?classroom_id={classroom_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    for q in data:
        assert q["classroom_id"] == classroom_id

def test_update_quiz(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia Update", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={"classroom_id": classroom_id, "topic": "Termokimia", "num_questions": 1},
        headers=headers
    )
    quiz_id = quiz_res.json()["id"]

    now = datetime.now(timezone.utc)
    update_payload = {
        "start_time": (now + timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(hours=3)).isoformat(),
        "duration_minutes": 45
    }
    response = client.patch(f"/api/v1/quizzes/{quiz_id}", json=update_payload, headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["duration_minutes"] == 45
    assert data["start_time"] is not None
    assert data["end_time"] is not None

def test_get_quiz(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Get Quiz Test", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={"classroom_id": classroom_id, "topic": "Fisika Inti", "num_questions": 2},
        headers=headers
    )
    quiz_id = quiz_res.json()["id"]

    response = client.get(f"/api/v1/quizzes/{quiz_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == quiz_id
    assert len(data["questions"]) == 2
    assert data["classroom_id"] == classroom_id

def test_publish_quiz_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Fisika 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Gravitasi",
            "num_questions": 2
        },
        headers=headers
    )
    quiz_id = quiz_res.json()["id"]

    publish_res = client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=headers)
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "published"
    assert publish_res.json()["id"] == quiz_id

def test_quiz_reports_and_autoseed(client, teacher_auth_headers, create_user):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kesusastraan 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    student1 = create_user("Murid Satu", "student1@school.com", "student")
    student2 = create_user("Murid Dua", "student2@school.com", "student")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO classroom_student (classroom_id, student_id)
                VALUES (%s, %s), (%s, %s);
                """,
                (classroom_id, student1["id"], classroom_id, student2["id"])
            )
        conn.commit()

    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "topic": "Sastra",
            "num_questions": 2
        },
        headers=headers
    )
    quiz_id = quiz_res.json()["id"]

    response = client.get(f"/api/v1/quizzes/{quiz_id}/reports", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["quiz_id"] == quiz_id

    stats = data["statistics"]
    assert stats["total_attempts"] == 2
    assert stats["total_students_in_class"] == 2
    assert stats["participation_rate_pct"] == 100.0
    assert stats["average_score"] > 0
    assert stats["highest_score"] >= stats["lowest_score"]

    results = data["student_results"]
    assert len(results) == 2
    student_ids = [r["student_id"] for r in results]
    assert student1["id"] in student_ids
    assert student2["id"] in student_ids
