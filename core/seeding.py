import os
import uuid
import logging
from psycopg2.extras import RealDictCursor
from core.security import hash_password

logger = logging.getLogger("uvicorn.error")

SEED_PASSWORD = os.getenv("SEED_PASSWORD", "password123")

def seed_database(conn):
    # Use RealDictCursor to fetch rows as dicts
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check if teacher exists
        cur.execute("SELECT id FROM users WHERE role = 'teacher' LIMIT 1;")
        existing_teacher = cur.fetchone()
        
        if existing_teacher:
            # Query existing classroom
            cur.execute("SELECT id, name FROM classrooms LIMIT 1;")
            classroom = cur.fetchone()
            logger.info("===== DATABASE ALREADY HAS SEED DATA =====")
            logger.info(f"Teacher ID: {existing_teacher['id']}")
            if classroom:
                logger.info(f"Classroom ID: {classroom['id']} ({classroom['name']})")
            logger.info("==========================================")
            return

        logger.info("===== SEEDING DATABASE WITH TEST DATA (RAW SQL) =====")
        
        hashed_pwd = hash_password(SEED_PASSWORD)
        
        # 1. Insert Teacher
        teacher_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO users (id, name, email, password, role)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (teacher_id, "Guru Budi", "teacher@school.com", hashed_pwd, "teacher")
        )

        # 2. Insert Classroom
        classroom_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO classrooms (id, name, teacher_id)
            VALUES (%s, %s, %s);
            """,
            (classroom_id, "Kelas 10A", teacher_id)
        )

        # 3. Insert Students
        student1_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO users (id, name, email, password, role)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (student1_id, "Siswa Adit", "adit@school.com", hashed_pwd, "student")
        )

        student2_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO users (id, name, email, password, role)
            VALUES (%s, %s, %s, %s, %s);
            """,
            (student2_id, "Siswa Bambang", "bambang@school.com", hashed_pwd, "student")
        )

        # 4. Enroll Students to Classroom
        cur.execute(
            """
            INSERT INTO classroom_student (classroom_id, student_id)
            VALUES (%s, %s), (%s, %s);
            """,
            (classroom_id, student1_id, classroom_id, student2_id)
        )

        conn.commit()

        logger.info("Seeding completed successfully!")
        logger.info(f"Teacher ID:   {teacher_id} (email: teacher@school.com)")
        logger.info(f"Classroom ID: {classroom_id} (name: Kelas 10A)")
        logger.info(f"Student 1 ID: {student1_id} (email: adit@school.com)")
        logger.info(f"Student 2 ID: {student2_id} (email: bambang@school.com)")
        logger.info("==========================================")

