import pytest
import uuid
from core.database import get_db_connection

def test_generate_quiz_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # 1. Create a classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Matematika 10", "teacher_id": teacher_id},
        headers=headers
    )
    assert classroom_res.status_code == 201
    classroom_id = classroom_res.json()["id"]
    
    # 2. Generate a quiz
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
    
    for q in data["questions"]:
        assert "question_text" in q
        assert "options" in q
        assert "correct_answer" in q

def test_publish_quiz_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Fisika 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]
    
    # Generate quiz
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
    
    # Publish quiz
    publish_res = client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=headers)
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "published"
    assert publish_res.json()["id"] == quiz_id

def test_quiz_reports_and_autoseed(client, teacher_auth_headers, create_user):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kesusastraan 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]
    
    # Enroll some students in classroom
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
        
    # Generate quiz
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
    
    # Get report. Since no attempts exist, this endpoint should automatically seed student attempts for our enrolled students.
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
