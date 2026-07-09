import pytest

def test_register_user_success(client):
    payload = {
        "name": "Guru Budi",
        "email": "teacher_budi@school.com",
        "password": "secretpassword",
        "avatar": "https://avatar.iran.liara.run/public/teacher"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == payload["name"]
    assert data["email"] == payload["email"]
    assert data["role"] == "student"
    assert "id" in data
    assert "password" not in data # Ensure password is not returned in response

def test_register_user_duplicate_email(client, create_user):
    # Pre-create a user
    create_user("Guru Budi", "teacher_budi@school.com", "teacher")

    # Try to register with the same email
    payload = {
        "name": "Budi Kloning",
        "email": "teacher_budi@school.com",
        "password": "anotherpassword"
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email is already registered"

def test_login_user_success(client, create_user):
    create_user("Guru Budi", "budi@school.com", "teacher", password="correct_password")
    
    payload = {
        "email": "budi@school.com",
        "password": "correct_password"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_user_incorrect_credentials(client, create_user):
    create_user("Guru Budi", "budi@school.com", "teacher", password="correct_password")
    
    # Wrong password
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "budi@school.com", "password": "wrong_password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"
    
    # Non-existent email
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@school.com", "password": "correct_password"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect email or password"

def test_get_me_success(client, teacher_auth_headers):
    headers = teacher_auth_headers["headers"]
    user_info = teacher_auth_headers["user"]
    
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == user_info["email"]
    assert data["name"] == user_info["name"]
    assert data["id"] == user_info["id"]

def test_get_me_unauthorized(client):
    # No authorization header
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
    
    # Invalid token
    response = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalidtoken"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"
