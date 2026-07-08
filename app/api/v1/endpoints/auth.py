import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from psycopg2.extras import RealDictCursor

from core.database import get_db
from core.limiter import limiter
from core.security import hash_password, verify_password, create_access_token
from app.api.v1.dependencies import get_current_user
from schemas.auth import UserRegister, UserLogin, Token, UserMeResponse

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
            (user_id, payload.name, payload.email.lower(), hashed_pwd, payload.role.value, payload.avatar)
        )
        new_user = cur.fetchone()
        conn.commit()
        return new_user

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

@router.get("/me", response_model=UserMeResponse)
def get_me(current_user = Depends(get_current_user)):
    return current_user
