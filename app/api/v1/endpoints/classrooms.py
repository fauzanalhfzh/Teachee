import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from psycopg2.extras import RealDictCursor
from uuid import UUID
from typing import List, Optional

from core.database import get_db
from schemas.classroom import ClassroomCreate, ClassroomUpdate, ClassroomResponse, ClassroomDetailResponse, StudentInClassroom

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
def list_classrooms(teacher_id: Optional[UUID] = None, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        if teacher_id:
            cur.execute("SELECT * FROM classrooms WHERE teacher_id = %s ORDER BY created_at DESC;", (str(teacher_id),))
        else:
            cur.execute("SELECT * FROM classrooms ORDER BY created_at DESC;")
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

@router.patch("/{classroom_id}", response_model=ClassroomResponse)
def update_classroom(classroom_id: UUID, payload: ClassroomUpdate, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Verify classroom exists
        cur.execute("SELECT id FROM classrooms WHERE id = %s;", (str(classroom_id),))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Classroom not found")

        # Verify teacher if updated
        if payload.teacher_id:
            cur.execute("SELECT id FROM users WHERE id = %s AND role = 'teacher';", (str(payload.teacher_id),))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Teacher not found")

        # Dynamic SQL update builder
        update_fields = []
        params = []
        update_data = payload.model_dump(exclude_unset=True)
        if not update_data:
            cur.execute("SELECT * FROM classrooms WHERE id = %s;", (str(classroom_id),))
            return cur.fetchone()

        for key, val in update_data.items():
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

@router.delete("/{classroom_id}", status_code=status.HTTP_200_OK)
def delete_classroom(classroom_id: UUID, conn = Depends(get_db)):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("DELETE FROM classrooms WHERE id = %s RETURNING id;", (str(classroom_id),))
        deleted_id = cur.fetchone()
        if not deleted_id:
            raise HTTPException(status_code=404, detail="Classroom not found")
        conn.commit()
        return {"message": "Classroom deleted successfully"}
