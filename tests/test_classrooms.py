import pytest
import uuid
from core.database import get_db_connection

def test_create_classroom_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    payload = {
        "name": "Kelas 10A Fisika"
    }
    response = client.post("/api/v1/classrooms", json=payload, headers=headers)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["teacher_id"] == teacher_id
    assert "id" in data

def test_create_classroom_assigns_current_teacher(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    # teacher_id is no longer taken from the request body; it is derived from the
    # authenticated user. The created classroom must belong to the current teacher.
    payload = {"name": "Kelas Hantu"}
    response = client.post("/api/v1/classrooms", json=payload, headers=headers)
    assert response.status_code == 201
    assert response.json()["teacher_id"] == teacher_id

def test_list_classrooms(client, teacher_auth_headers, create_user):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]

    # Pre-create classrooms owned by the current teacher
    client.post("/api/v1/classrooms", json={"name": "Kelas A"}, headers=headers)
    client.post("/api/v1/classrooms", json={"name": "Kelas B"}, headers=headers)

    # Create a classroom for another teacher (must NOT appear in the list)
    other_teacher = create_user("Other Teacher", "other_teacher@school.com", "teacher")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classrooms (id, name, teacher_id) VALUES (%s, %s, %s);",
                (str(uuid.uuid4()), "Kelas Guru Lain", other_teacher["id"])
            )
        conn.commit()

    # List classrooms - only the current teacher's own classrooms should be returned
    response = client.get("/api/v1/classrooms", headers=headers)
    assert response.status_code == 200
    classrooms = response.json()
    assert len(classrooms) == 2
    for c in classrooms:
        assert c["teacher_id"] == teacher_id

def test_get_classroom_detail(client, teacher_auth_headers, create_user):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    response = client.post("/api/v1/classrooms", json={"name": "Kelas 10 Biologi"}, headers=headers)
    classroom_id = response.json()["id"]
    
    # Create student and enroll them
    student = create_user("Siswa Adit", "adit@school.com", "student")
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO classroom_student (classroom_id, student_id) VALUES (%s, %s);",
                (classroom_id, student["id"])
            )
        conn.commit()
        
    # Get classroom details
    response = client.get(f"/api/v1/classrooms/{classroom_id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Kelas 10 Biologi"
    assert data["teacher_name"] == teacher_auth_headers["user"]["name"]
    assert len(data["students"]) == 1
    assert data["students"][0]["email"] == student["email"]

def test_update_classroom(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    response = client.post("/api/v1/classrooms", json={"name": "Kelas Lama"}, headers=headers)
    classroom_id = response.json()["id"]
    
    # Update classroom name
    payload = {"name": "Kelas Baru"}
    response = client.patch(f"/api/v1/classrooms/{classroom_id}", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Kelas Baru"

def test_delete_classroom(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    teacher_id = teacher_auth_headers["user"]["id"]
    
    # Create classroom
    response = client.post("/api/v1/classrooms", json={"name": "Kelas Untuk Dihapus"}, headers=headers)
    classroom_id = response.json()["id"]
    
    # Delete classroom
    response = client.delete(f"/api/v1/classrooms/{classroom_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Classroom deleted successfully"
    
    # Get classroom should return 404
    response = client.get(f"/api/v1/classrooms/{classroom_id}", headers=headers)
    assert response.status_code == 404
