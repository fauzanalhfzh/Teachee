import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg2.extras import RealDictCursor

from core.database import get_db
from core.limiter import limiter
from core.security import hash_password, verify_password, create_access_token
from app.api.v1.dependencies import get_current_user
from schemas.auth import UserRegister, UserLogin, UserUpdate, ChangePasswordRequest, Token, UserMeResponse

router = APIRouter()

@router.post("/register", response_model=UserMeResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/hour")
def register_user(request: Request, payload: UserRegister, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if email already exists
        cur.execute("SELECT id FROM users WHERE email = %s;", (payload.email.lower(),))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already registered"
            )
        
        user_id = str(uuid.uuid4())
        hashed_pwd = hash_password(payload.password)
        
        cur.execute(
            """
            INSERT INTO users (id, name, email, password, role, avatar)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *;
            """,
            (user_id, payload.name, payload.email.lower(), hashed_pwd, "student", payload.avatar)
        )
        new_user = cur.fetchone()
        conn.commit()
        return new_user

@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit("5/hour")
def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    user_id = str(current_user["id"])
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT password FROM users WHERE id = %s;", (user_id,))
        user = cur.fetchone()
        if not verify_password(payload.old_password, user["password"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        new_hashed = hash_password(payload.new_password)
        cur.execute(
            "UPDATE users SET password = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s;",
            (new_hashed, user_id)
        )
        conn.commit()
        return {"message": "Password changed successfully"}

@router.post("/login", response_model=Token)
@limiter.limit("20/minute")
def login_user(request: Request, payload: UserLogin, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Fetch user
        cur.execute("SELECT * FROM users WHERE email = %s;", (payload.email.lower(),))
        user = cur.fetchone()
        
        if not user or not verify_password(payload.password, user["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        access_token = create_access_token(data={"sub": str(user["id"])})
        return {"access_token": access_token, "token_type": "bearer"}

ALLOWED_PROFILE_FIELDS = {"name", "email", "avatar"}

@router.patch("/profile", response_model=UserMeResponse)
@limiter.limit("10/hour")
def update_profile(
    request: Request,
    payload: UserUpdate,
    current_user = Depends(get_current_user),
    conn = Depends(get_db),
):
    user_id = str(current_user["id"])
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        return current_user

    for key in update_data:
        if key not in ALLOWED_PROFILE_FIELDS:
            raise HTTPException(status_code=400, detail=f"Invalid field: {key}")

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if "email" in update_data:
            cur.execute(
                "SELECT id FROM users WHERE email = %s AND id != %s;",
                (update_data["email"], user_id)
            )
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email already in use")

        set_clauses = [f"{k} = %s" for k in update_data]
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        params = list(update_data.values()) + [user_id]

        cur.execute(
            f"UPDATE users SET {', '.join(set_clauses)} WHERE id = %s RETURNING *;",
            tuple(params)
        )
        updated = cur.fetchone()
        conn.commit()
        return updated

@router.get("/me", response_model=UserMeResponse)
def get_me(current_user = Depends(get_current_user)):
    return current_user
