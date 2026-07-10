from typing import Optional
from fastapi import HTTPException, status
from psycopg2.extras import RealDictCursor


def assert_teacher_owns(
    conn,
    table: str,
    resource_id: str,
    teacher_id: str,
    not_found_message: str = "Resource not found",
    id_column: str = "id",
    owner_column: str = "teacher_id",
) -> dict:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            f"SELECT * FROM {table} WHERE {id_column} = %s;",
            (resource_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_message)
        if str(row[owner_column]) != teacher_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_message)
        return dict(row)


def safe_commit(conn) -> None:
    try:
        conn.commit()
    except Exception:
        conn.rollback()
        raise
