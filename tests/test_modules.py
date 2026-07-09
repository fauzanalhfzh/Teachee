import pytest
import uuid
from core.database import get_db_connection

def test_generate_module_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Module Test Class", "teacher_id": teacher_id},
        headers=headers
    )
    assert classroom_res.status_code == 201
    classroom_id = classroom_res.json()["id"]

    payload = {
        "classroom_id": classroom_id,
        "topic": "Aljabar Linear",
        "num_sections": 2,
        "num_exercises": 3
    }
    response = client.post("/api/v1/modules/generate", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["status"] == "draft"
    assert data["topic"] == "Aljabar Linear"
    assert "title" in data
    assert len(data["sections"]) == 2
    assert len(data["exercises"]) == 3
    assert data["quiz_id"] is not None

    for sec in data["sections"]:
        assert "title" in sec
        assert "content" in sec
        assert "section_order" in sec

    for ex in data["exercises"]:
        assert "exercise_type" in ex
        assert "question_text" in ex
        assert "correct_answer" in ex
        assert ex["exercise_type"] in ("multiple_choice", "fill_blank", "true_false", "matching", "ordering")


def test_list_modules(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "List Module Class", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    for i in range(2):
        gen = client.post(
            "/api/v1/modules/generate",
            json={"classroom_id": classroom_id, "topic": f"Topik {i}", "num_sections": 2, "num_exercises": 3},
            headers=headers
        )
        assert gen.status_code == 201

    response = client.get(f"/api/v1/modules?classroom_id={classroom_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    for m in data:
        assert m["classroom_id"] == classroom_id
        assert m["section_count"] > 0
        assert m["exercise_count"] > 0


def test_get_module_detail(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Detail Module", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    gen_res = client.post(
        "/api/v1/modules/generate",
        json={"classroom_id": classroom_id, "topic": "Detail Test", "num_sections": 2, "num_exercises": 3},
        headers=headers
    )
    assert gen_res.status_code == 201
    module_id = gen_res.json()["id"]

    response = client.get(f"/api/v1/modules/{module_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == module_id
    assert len(data["sections"]) == 2
    assert len(data["exercises"]) == 3
    assert data["quiz_id"] is not None


def test_publish_module(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Publish Module", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    gen_res = client.post(
        "/api/v1/modules/generate",
        json={"classroom_id": classroom_id, "topic": "Publish Test", "num_sections": 2, "num_exercises": 3},
        headers=headers
    )
    assert gen_res.status_code == 201
    module_id = gen_res.json()["id"]
    quiz_id = gen_res.json()["quiz_id"]

    publish_res = client.post(f"/api/v1/modules/{module_id}/publish", headers=headers)
    assert publish_res.status_code == 200
    assert publish_res.json()["status"] == "published"

    response = client.get(f"/api/v1/modules/{module_id}", headers=headers)
    assert response.json()["status"] == "published"


def test_delete_module(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Delete Module", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]

    gen_res = client.post(
        "/api/v1/modules/generate",
        json={"classroom_id": classroom_id, "topic": "Delete Test", "num_sections": 2, "num_exercises": 3},
        headers=headers
    )
    assert gen_res.status_code == 201
    module_id = gen_res.json()["id"]

    del_res = client.delete(f"/api/v1/modules/{module_id}", headers=headers)
    assert del_res.status_code == 200

    get_res = client.get(f"/api/v1/modules/{module_id}", headers=headers)
    assert get_res.status_code == 404


def test_student_module_flow(client, teacher_auth_headers, student_auth_headers):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Student Module Flow", "teacher_id": teacher_id},
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

    gen_res = client.post(
        "/api/v1/modules/generate",
        json={"classroom_id": classroom_id, "topic": "Flow Test", "num_sections": 2, "num_exercises": 3},
        headers=teacher_headers
    )
    assert gen_res.status_code == 201
    module_id = gen_res.json()["id"]
    quiz_id = gen_res.json()["quiz_id"]
    exercises = gen_res.json()["exercises"]

    client.post(f"/api/v1/modules/{module_id}/publish", headers=teacher_headers)

    client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=teacher_headers)

    list_res = client.get("/api/v1/student/modules", headers=student_headers)
    assert list_res.status_code == 200
    modules = list_res.json()
    assert len(modules) == 1
    assert modules[0]["id"] == module_id

    detail_res = client.get(f"/api/v1/student/modules/{module_id}", headers=student_headers)
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert len(data["sections"]) == 2
    assert len(data["exercises"]) == 3
    assert data["quiz_unlocked"] is False
    for ex in data["exercises"]:
        assert "correct_answer" not in ex
        assert "explanation" not in ex

    content_res = client.post(f"/api/v1/student/modules/{module_id}/complete-content", headers=student_headers)
    assert content_res.status_code == 200
    assert content_res.json()["content_completed"] is True

    ex_answers = []
    for ex in exercises:
        ex_answers.append({"exercise_id": ex["id"], "answer": ex["correct_answer"]})

    submit_res = client.post(
        f"/api/v1/student/modules/{module_id}/submit-exercises",
        json={"answers": ex_answers},
        headers=student_headers
    )
    assert submit_res.status_code == 200
    sub_data = submit_res.json()
    assert sub_data["passed"] is True
    assert sub_data["score"] == 100.0
    assert len(sub_data["results"]) == 3
    for r in sub_data["results"]:
        assert r["is_correct"] is True

    quiz_res = client.get(f"/api/v1/student/modules/{module_id}/quiz", headers=student_headers)
    assert quiz_res.status_code == 200
    assert "questions" in quiz_res.json()
    assert len(quiz_res.json()["questions"]) > 0

    progress_res = client.get(f"/api/v1/student/modules/{module_id}/progress", headers=student_headers)
    assert progress_res.status_code == 200
    assert progress_res.json()["quiz_unlocked"] is True
    assert progress_res.json()["exercises_completed"] is True
    assert progress_res.json()["exercise_score"] == 100.0


def test_quiz_locked_without_exercises(client, teacher_auth_headers, student_auth_headers):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Locked Quiz", "teacher_id": teacher_id},
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

    gen_res = client.post(
        "/api/v1/modules/generate",
        json={"classroom_id": classroom_id, "topic": "Lock Test", "num_sections": 2, "num_exercises": 3},
        headers=teacher_headers
    )
    assert gen_res.status_code == 201
    module_id = gen_res.json()["id"]

    client.post(f"/api/v1/modules/{module_id}/publish", headers=teacher_headers)

    quiz_res = client.get(f"/api/v1/student/modules/{module_id}/quiz", headers=student_headers)
    assert quiz_res.status_code == 403
    assert "Complete the exercises first" in quiz_res.json()["detail"]
