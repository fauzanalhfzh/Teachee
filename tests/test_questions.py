import pytest
import uuid

def test_regenerate_question_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]
    
    # Generate quiz
    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "teacher_id": teacher_id,
            "title": "Kuis Larutan Asam Basa",
            "subject": "Kimia",
            "topic": "Asam Basa",
            "num_questions": 2
        },
        headers=headers
    )
    quiz_data = quiz_res.json()
    question_id = quiz_data["questions"][0]["id"]
    old_text = quiz_data["questions"][0]["question_text"]
    
    # Regenerate question
    response = client.put(f"/api/v1/questions/{question_id}/regenerate", headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == question_id
    assert "question_text" in data
    # Note: Because the mock AIService default bank generates random items, the text might change or remain the same depending on topic. But it should return valid keys.
    assert "options" in data
    assert "correct_answer" in data

def test_edit_question_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]
    
    # Generate quiz
    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "teacher_id": teacher_id,
            "title": "Kuis Larutan Asam Basa",
            "subject": "Kimia",
            "topic": "Asam Basa",
            "num_questions": 1
        },
        headers=headers
    )
    question_id = quiz_res.json()["questions"][0]["id"]
    
    # Edit question
    payload = {
        "question_text": "Berapa pH air murni pada 25 derajat celcius?",
        "options": ["pH = 7", "pH = 5", "pH = 9", "pH = 1"],
        "correct_answer": "pH = 7",
        "explanation": "pH air murni adalah 7 karena netral."
    }
    response = client.patch(f"/api/v1/questions/{question_id}", json=payload, headers=headers)
    assert response.status_code == 200
    
    data = response.json()
    assert data["question_text"] == payload["question_text"]
    assert data["options"] == payload["options"]
    assert data["correct_answer"] == payload["correct_answer"]
    assert data["explanation"] == payload["explanation"]

def test_delete_question_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    classroom_res = client.post(
        "/api/v1/classrooms",
        json={"name": "Kimia 10", "teacher_id": teacher_id},
        headers=headers
    )
    classroom_id = classroom_res.json()["id"]
    
    # Generate quiz
    quiz_res = client.post(
        "/api/v1/quizzes/generate",
        json={
            "classroom_id": classroom_id,
            "teacher_id": teacher_id,
            "title": "Kuis Larutan Asam Basa",
            "subject": "Kimia",
            "topic": "Asam Basa",
            "num_questions": 1
        },
        headers=headers
    )
    question_id = quiz_res.json()["questions"][0]["id"]
    
    # Delete question
    response = client.delete(f"/api/v1/questions/{question_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Question deleted successfully"
    
    # Regenerate on deleted question should fail
    response = client.put(f"/api/v1/questions/{question_id}/regenerate", headers=headers)
    assert response.status_code == 404
