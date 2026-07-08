import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from uuid import UUID
from typing import List, Optional

from core.database import get_db
from schemas.classroom import ClassroomCreate, ClassroomUpdate, ClassroomResponse, ClassroomDetailResponse, StudentInClassroom, EnrollStudentRequest

router = APIRouter()

@router.post("", response_model=ClassroomResponse, status_code=status.HTTP_201_CREATED)
def create_classroom(payload: ClassroomCreate, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Verify teacher exists
        cur.execute("SELECT id FROM users WHERE id = %s AND role = 'teacher';", (str(payload.teacher_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Teacher not found")

        classroom_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO classrooms (id, name, teacher_id)
            VALUES (%s, %s, %s)
            RETURNING *;
            """,
            (classroom_id, payload.name, str(payload.teacher_id))
        )
        classroom = cur.fetchone()
        conn.commit()
        return classroom

@router.get("", response_model=List[ClassroomResponse])
def list_classrooms(
    teacher_id: Optional[UUID] = None,
    limit: int = 50,
    offset: int = 0,
    conn = Depends(get_db),
):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if teacher_id:
            cur.execute(
                "SELECT * FROM classrooms WHERE teacher_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                (str(teacher_id), limit, offset)
            )
        else:
            cur.execute(
                "SELECT * FROM classrooms ORDER BY created_at DESC LIMIT %s OFFSET %s;",
                (limit, offset)
            )
        return cur.fetchall()

@router.get("/{classroom_id}", response_model=ClassroomDetailResponse)
def get_classroom(classroom_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 1. Fetch classroom details and teacher name
        cur.execute(
            """
            SELECT c.*, u.name as teacher_name FROM classrooms c
            JOIN users u ON c.teacher_id = u.id
            WHERE c.id = %s;
            """,
            (str(classroom_id),)
        )
        classroom_row = cur.fetchone()
        if not classroom_row:
            raise HTTPException(status_code=404, detail="Classroom not found")

        # 2. Fetch enrolled students
        cur.execute(
            """
            SELECT u.id, u.name, u.email FROM users u
            JOIN classroom_student cs ON u.id = cs.student_id
            WHERE cs.classroom_id = %s
            ORDER BY u.name ASC;
            """,
            (str(classroom_id),)
        )
        students_rows = cur.fetchall()

        res_dict = dict(classroom_row)
        res_dict["students"] = [dict(s) for s in students_rows]
        return res_dict

ALLOWED_CLASSROOM_COLUMNS = {"name", "teacher_id"}

@router.patch("/{classroom_id}", response_model=ClassroomResponse)
def update_classroom(classroom_id: UUID, payload: ClassroomUpdate, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM classrooms WHERE id = %s;", (str(classroom_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Classroom not found")

        if payload.teacher_id:
            cur.execute("SELECT id FROM users WHERE id = %s AND role = 'teacher';", (str(payload.teacher_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Teacher not found")

        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            cur.execute("SELECT * FROM classrooms WHERE id = %s;", (str(classroom_id),))
            return cur.fetchone()

        update_fields = []
        params = []
        for key, val in update_data.items():
            if key not in ALLOWED_CLASSROOM_COLUMNS:
                raise HTTPException(status_code=400, detail=f"Invalid field: {key}")
            update_fields.append(f"{key} = %s")
            params.append(str(val) if isinstance(val, UUID) else val)

        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        params.append(str(classroom_id))

        query = f"""
            UPDATE classrooms
            SET {', '.join(update_fields)}
            WHERE id = %s
            RETURNING *;
        """
        cur.execute(query, tuple(params))
        updated_classroom = cur.fetchone()
        conn.commit()
        return updated_classroom

@router.post("/{classroom_id}/students", status_code=status.HTTP_201_CREATED)
def enroll_student(classroom_id: UUID, payload: EnrollStudentRequest, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id FROM classrooms WHERE id = %s;", (str(classroom_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Classroom not found")

        cur.execute("SELECT id FROM users WHERE id = %s AND role = 'student';", (str(payload.student_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Student not found")

        cur.execute(
            "SELECT 1 FROM classroom_student WHERE classroom_id = %s AND student_id = %s;",
            (str(classroom_id), str(payload.student_id))
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="Student already enrolled")

        cur.execute(
            """
            INSERT INTO classroom_student (classroom_id, student_id)
            VALUES (%s, %s);
            """,
            (str(classroom_id), str(payload.student_id))
        )
        conn.commit()
        return {"message": "Student enrolled successfully"}

@router.delete("/{classroom_id}/students/{student_id}", status_code=status.HTTP_200_OK)
def unenroll_student(classroom_id: UUID, student_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "DELETE FROM classroom_student WHERE classroom_id = %s AND student_id = %s RETURNING 1;",
            (str(classroom_id), str(student_id))
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Student not found in this classroom")
        conn.commit()
        return {"message": "Student unenrolled successfully"}

@router.delete("/{classroom_id}", status_code=status.HTTP_200_OK)
def delete_classroom(classroom_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM classrooms WHERE id = %s RETURNING id;", (str(classroom_id),))
        deleted_id = cur.fetchone()
        if not deleted_id:
            raise HTTPException(status_code=404, detail="Classroom not found")
        conn.commit()
        return {"message": "Classroom deleted successfully"}
