import pytest
import uuid
from core.database import get_db_connection

def test_access_restricted_to_students(client, teacher_auth_headers):
    # A teacher should get 403 Forbidden when trying to access student endpoints
    headers = teacher_auth_headers["headers"]
    response = client.get("/api/v1/student/quizzes", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Only students can access student endpoints"

def test_student_quiz_workflow(client, teacher_auth_headers, student_auth_headers, create_user):
    teacher_headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    student_headers = student_auth_headers["headers"]
    student_id = student_auth_headers["user"]["id"]

    # 1. Teacher creates a classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia 10A", "teacher_id": teacher_id},
        headers=teacher_headers
    )
    assert classroom_res.status_code == 201
    classroom_id = classroom_res.json()["id"]

    # 2. Enroll student in the classroom
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student_id)
            )
        conn.commit()

    # 3. Teacher generates a quiz (starts as draft)
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

    # 4. Student checks quizzes. Since it's still a draft, it should NOT be in active list.
    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["active"]) == 0
    assert len(list_res.json()["completed"]) == 0

    # 5. Teacher publishes the quiz
    publish_res = client.post(f"/api/v1/quizzes/{quiz_id}/publish", headers=teacher_headers)
    assert publish_res.status_code == 200

    # 6. Student checks quizzes again. It should now be in the active list!
    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    active_quizzes = list_res.json()["active"]
    assert len(active_quizzes) == 1
    assert active_quizzes[0]["id"] == quiz_id
    assert active_quizzes[0]["classroom_name"] == "Kimia 10A"
    assert len(list_res.json()["completed"]) == 0

    # 7. Student retrieves the quiz to start working on it (Take Quiz)
    take_res = client.get(f"/api/v1/student/quizzes/{quiz_id}/take", headers=student_headers)
    assert take_res.status_code == 200
    take_data = take_res.json()
    assert take_data["id"] == quiz_id
    assert len(take_data["questions"]) == 2
    
    # SECURITY ASSERTION: Ensure correct_answer and explanation are NOT leaked!
    for q in take_data["questions"]:
        assert "correct_answer" not in q
        assert "explanation" not in q
        assert "question_text" in q
        assert "options" in q

    # 8. Student submits answers
    # We will submit 1 correct answer and 1 incorrect/empty answer
    q1 = questions[0]
    q2 = questions[1]
    
    submit_payload = {
        "answers": [
            {
                "question_id": q1["id"],
                "selected_answer": q1["correct_answer"]  # Correct
            },
            {
                "question_id": q2["id"],
                "selected_answer": "Wrong Answer Choice"  # Incorrect
            }
        ]
    }
    
    submit_res = client.post(f"/api/v1/student/quizzes/{quiz_id}/submit", json=submit_payload, headers=student_headers)
    assert submit_res.status_code == 200
    
    submit_data = submit_res.json()
    assert "attempt_id" in submit_data
    assert submit_data["score"] == 50.0  # 1 out of 2 is correct = 50%
    assert len(submit_data["results"]) == 2
    
    # Verify correction details return answers and explanations
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

    # 9. Student checks quizzes list again. It should now be in the completed list!
    list_res = client.get("/api/v1/student/quizzes", headers=student_headers)
    assert list_res.status_code == 200
    data = list_res.json()
    assert len(data["active"]) == 0
    assert len(data["completed"]) == 1
    assert data["completed"][0]["id"] == quiz_id
    assert data["completed"][0]["score"] == 50.0
    assert "attempted_at" in data["completed"][0]

    # 10. Student tries to submit again (should be rejected)
    dup_res = client.post(f"/api/v1/student/quizzes/{quiz_id}/submit", json=submit_payload, headers=student_headers)
    assert dup_res.status_code == 400
    assert dup_res.json()["detail"] == "You have already submitted this quiz"
